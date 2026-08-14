# 竞赛材料索引

> 竞赛答辩相关的解说词、计划书、PPT 内容与提交产物统一存放在本目录。

## 文档列表

| 文档 | 用途 |
|------|------|
| [demo-script.md](demo-script.md) | 演示解说词（配合 `./scripts/demo.sh` 使用） |
| [competition-materials.md](competition-materials.md) | 竞赛素材要点（核心指标、创新点、FAQ 口径） |
| [project-plan.md](project-plan.md) | 项目计划书 |
| [project-ppt-content.md](project-ppt-content.md) | PPT 演示内容大纲 |

## 提交产物（由脚本生成）

| 文件 | 生成脚本 |
|------|----------|
| `2026002224-作品信息概要表.docx` | `scripts/generate_competition_info_form.py` |
| `2026002224-作品报告.docx` | `scripts/generate_competition_report.py` |
| `2026002224-03设计与开发文档-readme.txt` | `scripts/generate_competition_info_form.py` |

生成命令：

```bash
.venv/bin/python scripts/generate_competition_info_form.py
.venv/bin/python scripts/generate_competition_report.py
```
