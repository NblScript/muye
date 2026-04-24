# 牧野（muye）Claude Code 插件配置指南

## 项目概况

- **项目**: 智慧农业害虫防治系统（害虫检测→气象采集→AI决策→无人机执行→大屏展示）
- **后端**: Python FastAPI（3个独立服务：主API:8000、无人机API:8001、YOLO API:8002）
- **前端**: React + Vite（:5173）
- **领域**: detection / decision / drone / infra
- **测试**: 77个 pytest 用例

---

## 插件一：Oh My ClaudeCode (OMC) — 多智能体编排

### 是什么
31k star 的 Claude Code 多智能体编排框架，支持 Team/Autopilot/Ultrawork 等模式，
19个专业agent自动分工协作。

### 安装

```bash
# 方式一：插件市场（推荐）
claude
# 在会话中依次输入（必须一行一行输入，不能同时粘贴）:
/plugin marketplace add https://github.com/Yeachan-Heo/oh-my-claudecode
/plugin install oh-my-claudecode

# 方式二：npm CLI
npm i -g oh-my-claude-sisyphus@latest
```

### 设置

```bash
# 在 Claude Code 会话中执行
/setup
/omc-setup
```

### 开启 Team 模式

编辑 `~/.claude/settings.json`：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### muye 专用 .omc/ 目录结构

```
muye/
├── .omc/
│   ├── skills/                    # 项目级技能
│   │   ├── muye-architecture.md   # 牧野架构知识
│   │   ├── muye-testing.md        # 测试约定
│   │   └── muye-domains.md        # 领域边界说明
│   ├── artifacts/                 # 工作产物
│   │   └── ask/                   # /ask 命令输出
│   ├── sessions/                  # 会话记录
│   └── state/                     # 运行状态
└── CLAUDE.md                      # 项目级指令（OMC 会读取）
```

### muye 专用 .omc/skills/ 内容

#### .omc/skills/muye-architecture.md
```markdown
---
name: muye-architecture
description: 牧野系统架构知识，用于帮助 agent 理解项目结构
triggers: ["muye", "牧野", "architecture", "架构"]
source: extracted
---

# 牧野系统架构

## 端口拓扑
- 8000: app/main.py（主API + 静态文件）
- 8001: app/drone_api.py（无人机API）
- 8002: app/yolo_api.py（YOLO API）
- 5173: frontend/（Vite 开发服务器）

## 数据流
用户上传图片 → YOLO检测 → 天气采集 → RAG检索 → Qwen决策 → 任务规划 → 无人机执行 → 大屏展示

## 关键约定
1. import 路径: `from modules.<domain>.<module>`
2. 配置加载: `app.config.get_config()`
3. 事件总线: `modules.infra.event_bus` 是跨模块唯一通道
4. 数据存储: `modules.infra.sqlite_store` 是唯一持久层
5. 启动命令: `.venv/bin/uvicorn app.main:api_app --reload`

## 外部依赖
- 和风天气 API (QWEATHER_API_KEY)
- 千问/DashScope API (DASHSCOPE_API_KEY)
- PX4 SITL（无人机仿真）
- YOLO ONNX 模型（本地推理）
```

#### .omc/skills/muye-testing.md
```markdown
---
name: muye-testing
description: 牧野项目测试约定和运行方式
triggers: ["test", "测试", "pytest"]
source: extracted
---

# 牧野测试约定

## 运行测试
```bash
.venv/bin/python -m pytest -q tests/
```

## 测试结构
- tests/ 目录下 77 个测试
- 使用 pytest + pytest-asyncio
- 每个 domain 有对应测试文件

## 约定
1. 改代码前先跑测试确认基线
2. 改完后必须重新运行全量测试
3. 新功能必须添加测试
```

#### .omc/skills/muye-domains.md
```markdown
---
name: muye-domains
description: 牧野系统四大领域边界和职责
triggers: ["detection", "decision", "drone", "infra", "领域"]
source: extracted
---

# 牧野四大领域

## detection（检测域）
- 入口: app/yolo_api.py
- 核心: modules/detection/ — YOLO推理 + 图像处理
- 数据流: 上传图片 → YOLO推理 → 标注图片 + 害虫列表

## decision（决策域）
- 入口: app/services/workflow_service.py
- 核心: modules/decision/ — AI决策 + RAG知识增强
- 数据流: 害虫+天气 → RAG检索 → Qwen API → 用药建议

## drone（无人机域）
- 入口: app/drone_api.py
- 核心: modules/drone/ — 控制器 + 任务规划 + PX4
- 数据流: 决策结果 → 任务规划 → 航线生成 → PX4执行

## infra（基础设施域）
- 核心: modules/infra/ — 事件总线 + SQLite + 天气
- 事件总线 EventBus 是跨域唯一通道
```

### muye 常用 OMC 命令

```bash
# Team 模式：多 agent 协作
/team 3:executor "为 detection 模块添加批量图片上传接口"

# Autopilot：自主完成
/autopilot "为 drone 模块添加航线规划 API 端点"

# 深度访谈：需求澄清
/deep-interview "我想实现害虫识别结果实时推送到前端"

# 多模型协作
/ccg 审查 drone 模块的 PX4 仿真代码，架构由 Codex 审查，UI 由 Gemini 审查

# 持久模式：确保完成
/ralph "修复 tests/ 中所有失败的测试用例"
```

---

## 插件二：Superpowers 中文版 — Skills 技能增强

### 是什么
Superpowers 原版（14个skills）的完整汉化 + 6个中国原创skills，
提供 TDD、调试、代码审查等最佳实践自动注入。

### 安装

```bash
# 方式一：npx 一键安装（推荐）
cd /home/qingking/muye
npx superpowers-zh

# 方式二：插件市场
claude
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
# 然后单独安装中文版 skills:
npx superpowers-zh

# 方式三：官方市场
/plugin install superpowers@claude-plugins-official
```

### 安装后文件位置

```
~/.claude/skills/                    # 用户级 skills（所有项目共享）
  ├── brainstorming/SKILL.md
  ├── writing-plans/SKILL.md
  ├── executing-plans/SKILL.md
  ├── test-driven-development/SKILL.md
  ├── systematic-debugging/SKILL.md
  ├── requesting-code-review/SKILL.md
  ├── receiving-code-review/SKILL.md
  ├── verification-before-completion/SKILL.md
  ├── dispatching-parallel-agents/SKILL.md
  ├── subagent-driven-development/SKILL.md
  ├── using-git-worktrees/SKILL.md
  ├── finishing-a-development-branch/SKILL.md
  ├── writing-skills/SKILL.md
  ├── using-superpowers/SKILL.md
  ├── chinese-code-review/SKILL.md      # 中国原创
  ├── chinese-git-workflow/SKILL.md     # 中国原创
  ├── chinese-documentation/SKILL.md    # 中国原创
  ├── chinese-commit-conventions/SKILL.md  # 中国原创
  ├── mcp-builder/SKILL.md              # 中国原创
  └── workflow-runner/SKILL.md          # 中国原创

muye/.claude/skills/                  # 项目级 skills（可覆盖用户级）
  └── （可放项目特定的 skills）
```

### 不需要手动配置 settings.json

Superpowers 通过 SessionStart hook 自动注入 `using-superpowers` skill，
无需手动配置 `~/.claude/settings.json`。

### muye 推荐使用的 skills

| 场景 | 使用哪个 skill |
|------|---------------|
| 新增 API 端点 | test-driven-development |
| 修复 bug | systematic-debugging |
| 审查 PR | requesting-code-review + chinese-code-review |
| 规划大功能 | writing-plans → executing-plans |
| 提交代码 | chinese-commit-conventions + chinese-git-workflow |
| 写文档 | chinese-documentation |

---

## 插件三：ECC (Everything Claude Code) — 配置生成器

### 是什么
通过自然语言描述需求，一键生成 agents、commands、skills、rules 配置模板。
适合项目初始化阶段快速搭建 Claude Code 配置。

### 安装

```bash
# 方式一：插件市场
claude
/plugin marketplace add https://github.com/zhongkai/ECC
/plugin install claude-code-config-generator

# 方式二：手动克隆
git clone https://github.com/zhongkai/ECC.git /tmp/ecc
cp -r /tmp/ecc/.claude-plugin ~/.claude/plugins/claude-code-config-generator/
rm -rf /tmp/ecc
```

### 使用方式

```bash
# 在 Claude Code 会话中

# 1. 生成配置（描述你的需求）
/config-gen 我需要一个 Python FastAPI 智慧农业项目的配置，关注 TDD、代码审查、安全和中文文档

# 2. 预览生成的配置
/config-preview

# 3. 安装到 ~/.claude/
/config-install
```

### ECC 生成的配置会包含

- **Agents**: config-advisor, planner, code-reviewer, tdd-guide
- **Commands**: /config-gen, /config-preview, /config-install
- **Skills**: 配置生成技能、TDD工作流、编码标准、前端模式
- **Rules**: 安全规则、编码风格、测试要求、Git工作流

---

## 三插件协同配置方案

### 推荐安装顺序

```
第1步: Superpowers 中文版（基础 skills 注入）
  cd /home/qingking/muye && npx superpowers-zh

第2步: Oh My ClaudeCode（编排引擎）
  claude
  /plugin marketplace add https://github.com/Yeachan-Heo/oh-my-claudecode
  /plugin install oh-my-claudecode
  /setup

第3步: ECC（按需使用，快速生成额外配置）
  /plugin marketplace add https://github.com/zhongkai/ECC
  /plugin install claude-code-config-generator
  /config-gen Python FastAPI 智慧农业害虫防治系统，需要 TDD、代码审查、安全检查
```

### 最终 muye 项目目录结构

```
muye/
├── .claude/                       # Claude Code 项目配置
│   ├── settings.json              # 项目级设置
│   └── skills/                    # 项目级 skills（覆盖全局）
│       └── muye-specific/         # 项目特定技能
├── .omc/                          # OMC 工作目录
│   ├── skills/                    # OMC 项目级技能
│   │   ├── muye-architecture.md
│   │   ├── muye-testing.md
│   │   └── muye-domains.md
│   ├── artifacts/                 # 工作产物
│   ├── sessions/                  # 会话记录
│   └── state/                     # 运行状态
├── CLAUDE.md                      # Claude Code 项目指令（重要！）
├── app/                           # FastAPI 应用层
├── modules/                       # 核心业务逻辑
├── models/                        # 数据模型
├── frontend/                      # React 前端
├── tests/                         # 测试
└── docs/                          # 文档
```

### CLAUDE.md（核心配置文件）

```markdown
# 牧野（muye）— Claude Code 项目指令

## 项目定位
智慧农业害虫防治系统：害虫检测→气象采集→AI决策→无人机执行→大屏展示

## 技术栈
- 后端: Python 3.x + FastAPI + SQLAlchemy + LangChain + ChromaDB
- 前端: React + Vite
- AI: YOLOv8 (检测) + Qwen (决策) + RAG (知识增强)
- 仿真: PX4 SITL (无人机)

## 端口
- 8000: 主API | 8001: 无人机API | 8002: YOLO API | 5173: 前端

## 关键约定
1. import: `from modules.<domain>.<module>`
2. 配置: `app.config.get_config()`
3. 事件总线: `modules.infra.event_bus`（跨域唯一通道）
4. 存储: `modules.infra.sqlite_store`（唯一持久层）

## 开发流程
1. 先读 ARCHITECTURE.md 理解全局
2. 改代码前先跑测试: `.venv/bin/python -m pytest -q tests/`
3. 改完必须跑全量测试
4. 新功能必须写测试
5. 更新相关文档

## 领域边界
- detection: YOLO推理 + 图像处理
- decision: AI决策 + RAG知识增强
- drone: 控制器 + 任务规划 + PX4仿真
- infra: 事件总线 + SQLite + 天气API

## 外部依赖
- QWEATHER_API_KEY (和风天气)
- DASHSCOPE_API_KEY (千问/DashScope)
```

### ~/.claude/settings.json（全局设置）

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "allow": [
      "Bash(.venv/bin/python -m pytest*)",
      "Bash(.venv/bin/uvicorn*)",
      "Bash(git *)"
    ],
    "deny": []
  }
}
```

---

## 实际使用场景示例

### 场景1：新增害虫批量检测接口
```bash
claude
# OMC Team 模式分工
/team 3:executor "为 detection 模块添加批量图片上传和检测接口，
需要支持多图并发推理，返回统一结果。遵循 TDD 模式。"
```
→ Superpowers 自动注入 TDD skill
→ OMC 分配 3 个 executor agent 并行工作

### 场景2：修复无人机航线规划 bug
```bash
claude
# Superpowers 调试流程
"modules/drone/mission_planner.py 的航线生成在边界条件下报错，
使用 systematic-debugging 流程排查"
```
→ 自动加载 systematic-debugging skill
→ 按 定位→分析→假设→修复 四步执行

### 场景3：全项目代码审查
```bash
claude
/ccg 对牧野项目做全面代码审查，关注安全性和架构合理性
```
→ Codex 审查架构，Gemini 审查前端，Claude 综合输出

### 场景4：用 ECC 生成初始配置
```bash
claude
/config-gen Python FastAPI 农业物联网系统，4个微服务，需要 TDD、
代码审查、安全检查、中文文档规范、Git工作流
```
→ 生成完整的 agents/commands/skills/rules 配置
→ /config-preview 预览
→ /config-install 安装
