import '@testing-library/jest-dom/vitest'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = ResizeObserverMock
}

if (!globalThis.URL.createObjectURL) {
  globalThis.URL.createObjectURL = () => ''
}
