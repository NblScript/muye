# Phase 0 — 真实模型验收执行计划

> 把"已构建但从未实跑"的真实 YOLO 容器验收链跑通，产出真实检测证据，消除答辩硬伤。

## 状态

- 状态：待执行
- 优先级：高
- 创建日期：2026-08-13
- 前置条件：重训 `models/best.pt`（旧权重已丢失，2026-08-13 确认）+ Docker 安装

## 背景

真实模型验收链的全部代码已就绪且被单元测试与 CI 配置校验覆盖：

- `docker-compose.real-smoke.yml`：隔离数据卷、只读挂载 `config/` 与 `models/`、回环端口（API 18081 / 前端 5175）、永不设置 `MUYE_CONTAINER_SMOKE`。
- `scripts/docker_real_smoke.sh`：预检（docker、compose v2、权重非空、样本存在）→ 构建 → 等待健康 → 验收。
- `scripts/container_smoke.py --mode real`：验收 `/health` 中 `yolo_model` 非模拟，上传样本后轮询 workflow state，逐条校验检测结果（`pest_type` 非空、`confidence∈[0,1]`、`coordinate_space=image_pixel`、正数原图尺寸）。
- `tests/test_container_real_smoke.py`：验收脚本的单元回归。

当前未实跑的环境缺口：

1. WSL2 环境未安装 Docker（Ubuntu 26.04，systemd 已启用，网络可达）。
2. `models/best.pt` 已丢失（本机与 C 盘均已排查，Git 历史从未提交过权重）。

已确认的训练环境事实：

- 现有 `.venv`（Python 3.14）内 `torch 2.13.0+cu130`，`torch.cuda.is_available()=True`，GPU 为 RTX 4060 Laptop 8GB。
- HuggingFace / Google Drive 不可达；Kaggle、Roboflow、ModelScope 可达。
- Kaggle 存在 IP102 完整框标注版 `leonidkulyk/ip102-yolov5`（810MB，约 19,000 张带框图片，YOLO 格式）。

## 已确定的决策

1. 使用 IP102 数据集重训 YOLO 演示模型（8 个演示虫类子集），替代丢失的旧权重；权重不进入 Git 版本控制。
2. 数据集优先采用 Kaggle `leonidkulyk/ip102-yolov5`（完整 IP102 框标注、YOLO 格式）；下载需 Kaggle API Key，由用户提供。
3. 训练在本机现有 `.venv`（torch cu130）执行，不新建环境；训练产物 `best.pt` 最终拷贝到 `models/best.pt`。
4. 演示图片（`data/samples/` 8 张）必须排除在训练集之外（held-out），训练前按文件名/哈希显式剔除。
5. 训练模型的类名直接使用系统规范害虫名（`PEST_SYNONYMS` 键），避免运行时名称映射层。
6. 不修改验收链代码，除非环境现实暴露兼容性问题；任何代码改动都需补充测试并同步文档。
7. 先跑无权重容器冒烟（`docker_smoke.sh`）验证 Docker 基础设施，再跑真实模型验收。
8. 容器内 YOLO 推理为 CPU 模式（`python:3.11-slim` 无 CUDA），单张演示图推理在可接受范围内。

## 实施阶段

### 阶段 1：Docker 环境安装

- [ ] 安装 Docker Engine（优先官方 apt 源 docker-ce；若 Ubuntu 26.04 尚无对应发布，退回 `docker.io`）与 docker compose v2 插件
- [ ] 将当前用户加入 `docker` 组，免 sudo 运行
- [ ] 启动并验证 `dockerd`（systemd 已启用，`systemctl enable --now docker`）

**验收**：`docker run hello-world` 成功；`docker compose version` 输出 v2；仓库根目录与两个冒烟 compose 文件 `docker compose config --quiet` 全部通过。

### 阶段 2：IP102 数据集获取

- [ ] 用户提供 Kaggle API Key（`kaggle.json`），下载 `leonidkulyk/ip102-yolov5`（810MB）
- [ ] 解压并审查目录结构：train/val 划分、images/labels 组织、classes 文件、标注格式
- [ ] 确认 8 个演示虫类在该数据集中的类目存在性：
  rice leaf roller(1)、yellow rice borer(5)、brown plant hopper(8)、mole cricket(16)、corn borer(23)、army worm(24)、aphids(25)、beet fly(37)
- [ ] 数据集归档到 `/mnt/c/muye/` 或 WSL 磁盘（不进 Git）；记录来源、license（IP102 学术用途）与下载日期

**验收**：数据集可被 ultralytics 直接加载（YOLO 格式），8 个目标类均有足够样本（每类 ≥ 100 张）。

### 阶段 3：训练数据子集与类名映射

- [ ] 编写训练准备脚本（`scripts/train_demo_model.py` 或 `scripts/prepare_train_subset.py`，位置按仓库惯例）：
  - 从全量 IP102 抽取 8 类子集
  - 按文件名/内容哈希剔除 `data/samples/` 的演示图片（held-out 保证）
  - 重映射类名到系统规范名：`aphid`、`rice-planthopper`、`rice-leaf-roller`、`corn-borer`、`armyworm`、`mole-cricket`、`yellow-rice-borer`、`beet-fly`
- [ ] 同步 `PEST_SYNONYMS`：补充缺失条目 `yellow-rice-borer`（三化螟）、`beet-fly`（甜菜/菠菜潜叶蝇），补充对应单元测试
- [ ] 生成的子集数据目录不进 Git（`.gitignore` 增加数据集路径）

**验收**：子集 images/labels 结构合法、演示图片零泄漏（脚本内断言）、`PEST_SYNONYMS` 测试通过、`verify_docs.py` 通过。

### 阶段 4：模型训练

- [ ] 训练配置：YOLOv8n、`imgsz=640`、预训练 COCO 骨干、batch 按 8GB 显存适配（16-32）、`epochs` 以早停为准（初始 50-100）、默认数据增强
- [ ] 在本机 `.venv`（torch cu130）执行训练，记录训练时长、mAP50、val 混淆矩阵
- [ ] 训练产物：`runs/detect/.../weights/best.pt` → 拷贝为 `models/best.pt`

**验收**：训练正常收敛（mAP50 ≥ 0.7 目标，最低 0.5）；`models/best.pt` 可被 ultralytics 8.4.37 加载。

### 阶段 5：本地真实推理预检（容器前快筛）

- [ ] 用本地 YOLO API（`python -m app.main --with-yolo-api`）对 `data/samples/` 演示图逐张推理
- [ ] 记录每张图检出类别、数量、置信度；校验 `coordinate_space=image_pixel` 与正数原图尺寸
- [ ] 蚜虫/褐飞虱/稻纵卷叶螟至少可检出；检出失败先调 `confidence_threshold`（同步数据契约文档），仍失败则增补训练数据

**验收**：演示样本可检出目标虫；检测结果满足像素坐标契约。

### 阶段 6：无权重容器冒烟

- [ ] `./scripts/docker_smoke.sh`（首次执行含双镜像构建，约 10-20 分钟）
- [ ] 确认链路输出 `container smoke passed: frontend -> backend -> watchdog -> fake YOLO -> workflow`

**验收**：fake YOLO 全链路通过，证明 Docker 基础设施、Compose 网络、nginx 代理、目录监听与工作流轮询在本机可用。

### 阶段 7：真实模型容器验收

- [ ] `MUYE_REAL_SMOKE_KEEP=1 ./scripts/docker_real_smoke.sh`
- [ ] 输出 `real-model container smoke passed: ... detections={...}`
- [ ] 保留栈期间人工复查：大屏（5175）真实热力帧、历史页快照、`/health` 中 `yolo_model` 状态

**验收**：脚本内建校验全部通过（模型非模拟、检测结果逐条合规）；真实检测驱动完整管线（检测 → mock 决策 → 合规 → 规划 → animated_demo 喷洒 → 热力快照 → mission 创建）。

### 阶段 8：证据归档

- [ ] 保存训练指标摘要、验收控制台输出、`/health` 响应、workflow state JSON 快照
- [ ] 大屏真实热力截图 + 历史页快照截图（至少 1920×1080 一张）
- [ ] 归档到 `data/eval/real-model-acceptance-YYYYMMDD/`，附 README 记录训练配置、数据集来源、验收结论

### 阶段 9：文档同步（项目强制约定）

- [ ] `PLANS.md`：三条"待实跑"条目改为已完成并标注日期
- [ ] `docs/exec-plans/index.md`：本计划状态改为已完成
- [ ] `CHANGELOG.md`：Unreleased 新增"重训演示模型 + 真实模型容器验收"条目
- [ ] `AGENTS.md` 当前活跃计划：同步更新
- [ ] `QUALITY_SCORE.md`：如验证基线数字变化则更新
- [ ] 收尾回归：`./scripts/check.sh` + `scripts/verify_docs.py` 全部通过

## 风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| Kaggle 下载慢/失败 | 中 | 断点续传；备选 Roboflow IP102 或用户旧数据集 |
| 数据集无 train/val 划分或格式异常 | 中 | 阶段 2 审查后自行按类分层切分 |
| 演示图片与训练集重叠 | 低 | 阶段 3 按哈希剔除 + 脚本断言，验收必查 |
| 8 类中个别类样本过少（<100 张） | 低 | 类别合并或剔除该演示类，同步调整演示样本 |
| 训练不收敛（mAP50 < 0.5） | 低 | 调整 epochs/学习率/输入尺寸；RTX 4060 8GB 对 v8n@640 足够 |
| Ubuntu 26.04 无官方 docker-ce 包 | 中 | 退回 `docker.io`（功能等价，版本略旧） |
| 容器 CPU 推理超时 | 低 | 单图推理秒级，`PIPELINE_TIMEOUT` 默认 120s 充足 |
| 训练环境与容器 ultralytics 版本不一致 | 低 | 本机与容器均为 8.4.37；训练产物加载前本地验证 |

## 验收标准总览

1. `models/best.pt` 由 IP102 8 类子集重训而来，演示图片 held-out，类名与 `PEST_SYNONYMS` 对齐。
2. `docker_real_smoke.sh` 一次跑通，输出真实检测统计。
3. 证据目录包含训练指标、控制台输出、健康检查响应、大屏截图，可供答辩引用。
4. 文档同步完成，`check.sh` 与 `verify_docs.py` 通过。
5. 验收链核心逻辑零改动；所有代码改动（同义词补充、训练脚本）附带单元测试。
