# 演示图片说明

图片由 `scripts/prepare.sh` 从使用者本地 IP102 验证集选取。IP102 官方类别表见 <https://github.com/xpwu95/IP102/blob/master/classes.txt>。

IP102 图片文件名前缀（例如 `IP024`）使用 0 起始类别编号，官方 `classes.txt` 使用 1 起始编号。因此准备脚本必须按“前缀 + 1”映射类别。当前脚本使用以下已核对映射：

| 源图片 | 官方类别 ID | 官方类别 | 目标文件 |
|---|---:|---|---|
| `IP000000000.jpg` | 1 | rice leaf roller | `rice_leaf_roller_01.jpg` |
| `IP007000004.jpg` | 8 | brown plant hopper | `brown_planthopper_01.jpg` |
| `IP004000001.jpg` | 5 | yellow rice borer | `yellow_rice_borer_01.jpg` |
| `IP023000056.jpg` | 24 | army worm | `army_worm_01.jpg` |
| `IP024000016.jpg` | 25 | aphids | `aphids_01.jpg` |
| `IP022000006.jpg` | 23 | corn borer | `corn_borer_01.jpg` |
| `IP036000049.jpg` | 37 | beet fly | `beet_fly_01.jpg` |
| `IP015000008.jpg` | 16 | mole cricket | `mole_cricket_01.jpg` |

仓库中可能仍存在旧版准备脚本生成的历史文件名。业务与评测代码不得仅凭文件名宣称虫种；应同时保存数据集原始图片 ID、类别 ID、模型检测结果和来源标记。运行新版 `prepare.sh --images-only` 前，可清理或另行备份旧演示图片后重新准备。
