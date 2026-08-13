#!/usr/bin/env python
"""Seed historical decisions by running mock rounds with pest images."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.infra.common import DATA_DIR, load_environment
from modules.decision.rag.knowledge_loader import build_historical_decision_document
from modules.decision.rag.vectorstore import COLLECTION_DECISIONS, VectorStoreManager

# Map YOLO class labels to Chinese pest names and canonical pest types
PEST_MAP = {
    "aphids": {"zh": "蚜虫", "canonical": "aphid", "crops": ["冬小麦", "夏玉米", "棉花"]},
    "rice leaf roller": {"zh": "稻纵卷叶螟", "canonical": "rice-leaf-roller", "crops": ["水稻"]},
    "rice leafhopper": {"zh": "稻飞虱", "canonical": "rice-planthopper", "crops": ["水稻"]},
    "corn borer": {"zh": "玉米螟", "canonical": "corn-borer", "crops": ["夏玉米"]},
    "armyworm": {"zh": "粘虫", "canonical": "armyworm", "crops": ["冬小麦", "夏玉米"]},
    "wheat sawfly": {"zh": "小麦叶蜂", "canonical": "wheat-sawfly", "crops": ["冬小麦"]},
    "grub": {"zh": "蛴螬", "canonical": "grub", "crops": ["冬小麦", "夏玉米"]},
    "red spider": {"zh": "红蜘蛛", "canonical": "red-spider", "crops": ["冬小麦", "棉花"]},
    "asiatic rice borer": {"zh": "二化螟", "canonical": "rice-stem-borer", "crops": ["水稻"]},
    "yellow rice borer": {"zh": "三化螟", "canonical": "rice-stem-borer", "crops": ["水稻"]},
}

# Pesticide recommendations per pest type
PESTICIDE_DB = {
    "aphid": {"name": "吡虫啉", "conc": "10%", "ratio": "1000-1500倍液", "total": "60mL/亩"},
    "rice-leaf-roller": {"name": "氯虫苯甲酰胺", "conc": "20%", "ratio": "1500-2500倍液", "total": "40mL/亩"},
    "rice-planthopper": {"name": "噻嗪酮", "conc": "25%", "ratio": "1000-1500倍液", "total": "50mL/亩"},
    "corn-borer": {"name": "氯虫苯甲酰胺", "conc": "20%", "ratio": "1500-2500倍液", "total": "40mL/亩"},
    "armyworm": {"name": "甲维盐", "conc": "5%", "ratio": "2000-3000倍液", "total": "30mL/亩"},
    "wheat-sawfly": {"name": "高效氯氟氰菊酯", "conc": "2.5%", "ratio": "1500-2000倍液", "total": "50mL/亩"},
    "grub": {"name": "辛硫磷", "conc": "40%", "ratio": "800-1000倍液", "total": "80mL/亩"},
    "red-spider": {"name": "阿维菌素", "conc": "1.8%", "ratio": "1500-2000倍液", "total": "50mL/亩"},
    "rice-stem-borer": {"name": "三唑磷", "conc": "20%", "ratio": "1000-1500倍液", "total": "60mL/亩"},
}

ADVICE_POOL = [
    "施药后7-10天检查防治效果，如有必要可轮换用药",
    "选择无风或微风天气施药效果更佳",
    "建议上午或傍晚施药，避开高温时段",
    "施药时请佩戴防护装备，避免药液接触皮肤和眼睛",
    "保持田间排水良好，避免高湿环境利于病害发生",
    "加强田间管理，注意观察作物生长状况并适时灌溉施肥",
    "当前害虫处于初发期，建议立即施药控制",
    "可加入有机硅助剂提高药液附着性",
    "注意轮换使用不同作用机制的农药以延缓抗药性",
    "施药后观察3-5天，若虫情未得到控制可考虑二次施药",
]


def parse_label_file(label_path: Path) -> list[dict]:
    """Parse YOLO label file and return detections."""
    detections = []
    if not label_path.exists():
        return detections
    for line in label_path.read_text().strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 5:
            class_id = int(parts[0])
            detections.append({"class_id": class_id})
    return detections


def build_decision_for_pest(pest_type: str, crop_name: str) -> dict:
    """Build a mock decision for a given pest and crop."""
    pest_info = PEST_MAP.get(pest_type, {})
    canonical = pest_info.get("canonical", pest_type)
    pesticide = PESTICIDE_DB.get(canonical, PESTICIDE_DB["aphid"])

    advice = random.sample(ADVICE_POOL, min(3, len(ADVICE_POOL)))
    return {
        "用药": {
            "农药名称": pesticide["name"],
            "浓度": pesticide["conc"],
            "配比": pesticide["ratio"],
            "总量": pesticide["total"],
            "安全提示": ["低毒，施药时请佩戴防护装备"],
        },
        "农事建议": advice,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed historical decisions from pest images")
    parser.add_argument("--source", type=str, required=True, help="Source images directory")
    parser.add_argument("--count", type=int, default=100, help="Number of images to process")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild decisions collection first")
    args = parser.parse_args()

    load_environment()

    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        sys.exit(1)

    # Check for label files (same directory structure or labels subdir)
    label_dir = source_dir.parent / "labels" if (source_dir.parent / "labels").exists() else source_dir

    # Get all image files
    images = sorted(source_dir.glob("*.jpg")) + sorted(source_dir.glob("*.png"))
    if not images:
        print("No images found")
        sys.exit(1)

    sample = random.sample(images, min(args.count, len(images)))
    print(f"Processing {len(sample)} images from {source_dir}")

    vector_store = VectorStoreManager()
    if args.rebuild:
        print("Rebuilding decisions collection...")
        vector_store.delete_collection(COLLECTION_DECISIONS)

    fields = ["px4-sitl-demo", "field-kaifeng", "field-xinxiang", "field-zhumadian", "field-luoyang", "field-nanyang"]
    crops = ["冬小麦", "夏玉米", "水稻", "棉花", "大豆"]

    documents = []
    for i, img_path in enumerate(sample):
        # Try to find corresponding label file
        label_path = label_dir / (img_path.stem + ".txt")
        detections = parse_label_file(label_path)

        if not detections:
            # Randomly assign a pest type if no label
            pest_type = random.choice(list(PEST_MAP.keys()))
        else:
            # Use first detection's class_id to pick pest type
            # IP102 dataset class mapping (simplified)
            pest_keys = list(PEST_MAP.keys())
            class_id = detections[0]["class_id"]
            pest_type = pest_keys[class_id % len(pest_keys)]

        pest_info = PEST_MAP.get(pest_type, {})
        canonical = pest_info.get("canonical", pest_type)
        zh_name = pest_info.get("zh", pest_type)
        crop_name = random.choice(pest_info.get("crops", crops))
        field_id = random.choice(fields)

        decision = build_decision_for_pest(pest_type, crop_name)
        request_id = f"seed-{img_path.stem}-{int(time.time())}"

        doc = build_historical_decision_document(
            request_id=request_id,
            decision=decision,
            pest_types=[canonical],
            field_id=field_id,
            crop_name=crop_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        if doc:
            documents.append(doc)

        if (i + 1) % 50 == 0:
            print(f"  Built {i + 1}/{len(sample)} documents...")

    if documents:
        print(f"Indexing {len(documents)} historical decisions...")
        ids = vector_store.add_documents(COLLECTION_DECISIONS, documents)
        print(f"Indexed {len(ids)} documents into {COLLECTION_DECISIONS}")
    else:
        print("No documents to index")


if __name__ == "__main__":
    main()
