# 固定热力图回归集

`manifest.json` 固定了 6 个离线场景，用来回归 8×10 相对热力网格、变量喷洒计划和安全降级。运行：

```bash
python scripts/eval_fixed_set.py --output data/eval/latest_report.md
```

## 数据来源与边界

- 三类正样本来自项目现有的 IP102 验证集选图，清单保留了原始图片编号、官方类别编号和文件 SHA-256。IP102 官方项目说明数据集包含 102 类害虫、75,222 张分类图和 18,976 张框标注图，并限定为学术用途：<https://github.com/xpwu95/IP102>。
- 论文与项目页：<https://openaccess.thecvf.com/content_CVPR_2019/html/Wu_IP102_A_Large-Scale_Benchmark_Dataset_for_Insect_Pest_Recognition_CVPR_2019_paper.html>、<https://mmcheng.net/ip102/>。
- 本目录没有重新下载或复制完整 IP102 数据集；图片仍位于 `data/samples/`，由 `scripts/prepare.sh` 从使用者本地数据集准备。
- `detections` 是为了算法确定性而人工固定的回归标注，不是 IP102 官方框，也不是当前 YOLO 模型的实测输出。异常场景明确标为 synthetic edge case，不可用于宣称识别精度或真实药效。
- IP102 图片文件名前缀是 0 起始类别编号，而官方 `classes.txt` 是 1 起始编号；清单按“前缀 + 1”保存 `source_class_id`。项目早期曾把部分演示文件错一类命名，`scripts/prepare.sh` 已按官方映射修正，回归集只把核对无误的 3 类图片作为正样本。

## 基线语义

每个场景同时校验：图片内容哈希、检测坐标接纳/拒绝数量、完整地理热力网格、规划模式、航线、喷洒速率表及分档策略。稳定负载经过规范 JSON 序列化后生成 SHA-256；生产算法有意变化时，应人工审阅结果后再更新对应基线，禁止测试运行自动覆盖基线。

当前覆盖：

1. 蚜虫、褐飞虱、稻纵卷叶螟三类有效坐标输入。
2. 检测结果为空时均匀喷洒降级。
3. 检测存在但缺少坐标时均匀喷洒降级。
4. 地块围栏非法时明确失败。
