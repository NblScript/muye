import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'

import { installApiMocks } from './fixtures'

type Rect = { x: number; y: number; width: number; height: number; right: number; bottom: number }

async function rect(locator: Locator): Promise<Rect> {
  const box = await locator.boundingBox()
  expect(box, `missing layout box for ${await locator.getAttribute('data-testid') ?? 'element'}`).not.toBeNull()
  return {
    x: box!.x,
    y: box!.y,
    width: box!.width,
    height: box!.height,
    right: box!.x + box!.width,
    bottom: box!.y + box!.height,
  }
}

function overlapArea(left: Rect, right: Rect) {
  const width = Math.max(0, Math.min(left.right, right.right) - Math.max(left.x, right.x))
  const height = Math.max(0, Math.min(left.bottom, right.bottom) - Math.max(left.y, right.y))
  return width * height
}

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    horizontal: document.documentElement.scrollWidth - window.innerWidth,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
  }))
  expect(overflow.horizontal).toBeLessThanOrEqual(1)
  return overflow
}

async function attachViewport(page: Page, testInfo: TestInfo, name: string) {
  await testInfo.attach(`${name}-${testInfo.project.name}`, {
    body: await page.screenshot({ animations: 'disabled' }),
    contentType: 'image/png',
  })
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page)
})

test('command screen stays inside the viewport without panel collisions', async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  // ?e2e=1 跳过 3D Canvas：几何验收只测 DOM 面板布局，
  // 避免 swiftshader 软件渲染在 CI 上占满主线程导致断言饥饿。
  await page.goto('/?e2e=1')
  await expect(page.getByTestId('field-title')).toContainText('昆虫密度热力值地图')
  await expect(page.getByLabel('首页虫种筛选')).toHaveValue('all')
  // prefers-reduced-motion（本工程全部 e2e 项目启用）下面板跳过入场动画直接显示；
  // 轮询只验证最终状态，不依赖动画时序。30s 上限远高于任何正常路径。
  await expect.poll(async () => page.getByTestId('panel-pests').evaluate((element) => {
    const style = getComputedStyle(element)
    return Number(style.opacity) === 1
      && (style.transform === 'none' || style.transform === 'matrix(1, 0, 0, 1, 0, 0)')
  }), { timeout: 30_000 }).toBe(true)

  const viewport = await expectNoDocumentOverflow(page)
  const screen = await rect(page.getByTestId('command-screen'))
  expect(screen.x).toBeCloseTo(0, 0)
  expect(screen.y).toBeCloseTo(0, 0)
  expect(screen.width).toBeCloseTo(viewport.viewportWidth, 0)
  expect(screen.height).toBeCloseTo(viewport.viewportHeight, 0)

  const panelIds = [
    'panel-pests', 'panel-weather', 'panel-pipeline',
    'panel-decision', 'panel-drone', 'panel-evaluation',
  ]
  const cards = await Promise.all(panelIds.map((id) => rect(page.getByTestId(id))))
  for (const card of cards) {
    expect(card.width).toBeGreaterThan(180)
    expect(card.height).toBeGreaterThan(100)
    expect(card.x).toBeGreaterThanOrEqual(-1)
    expect(card.y).toBeGreaterThanOrEqual(-1)
    expect(card.right).toBeLessThanOrEqual(viewport.viewportWidth + 1)
    expect(card.bottom).toBeLessThanOrEqual(viewport.viewportHeight + 1)
  }
  for (let left = 0; left < cards.length; left += 1) {
    for (let right = left + 1; right < cards.length; right += 1) {
      expect(overlapArea(cards[left], cards[right])).toBeLessThan(2)
    }
  }

  const leftColumnRight = Math.max(...cards.slice(0, 3).map((card) => card.right))
  const rightColumnLeft = Math.min(...cards.slice(3).map((card) => card.x))
  expect(leftColumnRight).toBeLessThan(viewport.viewportWidth * 0.32)
  expect(rightColumnLeft).toBeGreaterThan(viewport.viewportWidth * 0.68)

  const title = await rect(page.getByTestId('field-title'))
  const legend = await rect(page.getByTestId('heat-legend'))
  expect(title.x).toBeGreaterThan(leftColumnRight)
  expect(title.right).toBeLessThan(rightColumnLeft)
  expect(legend.x).toBeGreaterThan(leftColumnRight)
  expect(legend.right).toBeLessThan(rightColumnLeft)
  expect(pageErrors).toEqual([])

  await attachViewport(page, testInfo, 'command-screen')
})

test('history analysis keeps wide content in local scroll containers', async ({ page }, testInfo) => {
  await page.goto('/history')
  await expect(page.getByRole('heading', { name: '作业历史与虫情分析' })).toBeVisible()
  await expect(page.getByText('检测数量', { exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '请求 ID' })).toBeVisible()

  const viewport = await expectNoDocumentOverflow(page)
  const historyPage = await rect(page.getByTestId('history-page'))
  const taskTableWrap = page.locator('table.history-table:not(.heatmap-snapshot-table)').locator('..')
  const tableWrap = await rect(taskTableWrap)
  expect(historyPage.x).toBeGreaterThanOrEqual(0)
  expect(historyPage.right).toBeLessThanOrEqual(viewport.viewportWidth + 1)
  expect(tableWrap.right).toBeLessThanOrEqual(viewport.viewportWidth + 1)

  const localOverflow = await taskTableWrap.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    overflowX: getComputedStyle(element).overflowX,
  }))
  expect(localOverflow.overflowX).toBe('auto')
  expect(localOverflow.scrollWidth).toBeGreaterThanOrEqual(localOverflow.clientWidth)

  const filters = page.locator('.heatmap-filter-grid')
  await expect(filters).toBeVisible()
  const filterRect = await rect(filters)
  expect(filterRect.right).toBeLessThanOrEqual(viewport.viewportWidth + 1)

  await attachViewport(page, testInfo, 'history-analysis')
})
