# Worklog

## Current Session Summary

本轮已完成一次针对当前仓库状态的重新核对，重点是纠正工程记忆与实际代码之间的偏差。

- 已逐项检查当前仓库中的核心文件：
  - `main.py`
  - `app.py`
  - `modules/*.py`
  - `scripts/*.sh`
  - `scripts/*.py`
  - `tests/*.py`
  - `README.md`
  - `config/drone_config.json`
  - `.env.example`
  - `PROJECT_MEMORY.md`
  - `CHANGELOG.md`
- 已确认此前记忆文件存在明显滞后：
  - 旧文档仍写着“PX4 尚未落入仓库代码改动”
  - 旧文档仍把 PX4 接入描述成“环境确认后再开始”
  - 这与当前仓库真实状态不一致

## Confirmed From Code Inspection

- PX4 backend 已经接入：
  - `modules/px4_simulator.py` 已存在
  - `modules/drone_controller.py` 已支持 `backend=px4`
  - `main.py` 已支持 `--drone-backend px4`
  - `.env.example` / `config/drone_config.json` 已有 PX4 配置
- 仓库已经有完整的一键 PX4 演示脚本：
  - `scripts/run_px4_demo.sh`
  - `scripts/start_px4_visual_demo.sh`
  - `scripts/start_competition_mode.sh`
  - `scripts/start_all_in_one.sh`
- PX4 演示已不是只做“连接后端”：
  - 已包含 Zurich SITL demo field
  - 已包含 MAVSDK 地址配置
  - 已包含比赛模式/QGC/浏览器启动包装
- 非 PX4 演示入口也仍然保留：
  - `scripts/start_demo.sh`
  - 可作为 PX4 环境不可用时的稳定回退链路
- SQLite 也已经不是简单起步版：
  - 主 pipeline 已写入 `tasks / detections / weather_snapshots / decisions`
  - 无人机状态流已写入 `drone_mission_updates`
  - 作业摘要已写入 `spray_records`
  - 农业数据层已扩展到 `fields / crop_catalog / field_crop_cycles / soil_records / weather_history_daily / pesticide_catalog / data_sources / agri_statistical_indicators`
  - 旧库迁移脚本 `scripts/migrate_to_v1_1.py` 和 `v1.1.1` 发布线也仍然有效
- 前端读取层已接到 SQLite：
  - `app.py` 会优先读取 SQLite 任务历史
  - 再用 `JSONL` 事件流补实时阶段与日志

## Documentation Fixes Completed

- 已重写 `PROJECT_MEMORY.md`，使其反映当前真实状态：
  - PX4 backend 已落地
  - 一键演示脚本已落地
  - SQLite 深化接入已落地
  - 旧的“尚未接入 PX4”叙述已移除
- 已更新 `CHANGELOG.md` 的 `Unreleased` 段落：
  - 补入 PX4 backend / demo scripts / demo field / tests
  - 保留 SQLite、seed、schema、前端历史检索等近期变更
- 已将本 `docs/WORKLOG.md` 改为当前状态汇总，而不是继续保留旧的接入前 handoff 文本

## Verification

- 本轮已实际执行测试：
  - `PYTHONPATH=/home/qingking/muye /home/qingking/muye/.venv/bin/pytest -q`
  - 结果：`53 passed in 5.32s`
- 重点确认的测试方向：
  - PX4 backend override
  - PX4 demo field
  - PX4 状态写库
  - 主流程 SQLite 写库
  - `spray_records` / `pesticide_catalog` 关联
  - SQLite 结构化历史读取
  - mission planner 演示航线与 presentation profile

## Next Handoff Point

下一轮如果继续推进，直接承接当前真实状态：

1. PX4 backend 已经在仓库中，不需要再从“设计接入点”开始。
2. 优先在目标环境做真实演示验证：
   - `./scripts/run_px4_demo.sh`
   - 或 `./scripts/start_px4_visual_demo.sh --sample-image IP000000042.jpg`
3. 如果现场展示优先级最高，继续完善：
   - competition mode
   - QGC / browser 拉起
   - 演示失败时的回退和提示
4. 如果数据层优先级更高，继续完善：
   - 正式农药目录
   - 河南真实天气 CSV 入库
   - 更细的结构化查询与报表

## Notes

- 这次更新的重点不是新增业务代码，而是把“工程记忆”纠正到和当前仓库一致。
- 后续凡是再改动 PX4 演示脚本、backend 路由、SQLite schema 或关键验证结论，都必须同步更新：
  - `PROJECT_MEMORY.md`
  - `CHANGELOG.md`
  - `docs/WORKLOG.md`
