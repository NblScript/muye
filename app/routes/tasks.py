"""Task endpoints for retrieving task images and reports."""

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from PIL import Image, ImageDraw

import app.services.workflow_service as workflow_service


def annotate_image(image_path: str | Path, detections: list[dict[str, Any]]) -> Image.Image | None:
    """Annotate an image with detection boxes."""
    target = Path(image_path)
    if not target.exists():
        return None

    image = Image.open(target).convert("RGB")
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    width = max(2, int(min(image.size) * 0.005))

    for detection in detections:
        position = detection.get("position", {})
        box = (
            float(position.get("x1", 0)),
            float(position.get("y1", 0)),
            float(position.get("x2", 0)),
            float(position.get("y2", 0)),
        )
        label = f"{detection.get('pest_type', 'unknown')} {float(detection.get('confidence', 0)):.2f}"
        draw.rectangle(box, outline="#FF7A00", width=width)
        text_anchor = (box[0] + 4, max(box[1] - 20, 0))
        draw.rectangle(
            (
                text_anchor[0] - 2,
                text_anchor[1] - 2,
                text_anchor[0] + len(label) * 7,
                text_anchor[1] + 16,
            ),
            fill="#FF7A00",
        )
        draw.text(text_anchor, label, fill="white")

    return annotated


async def get_task_original_image(request_id: str) -> FileResponse:
    """Get original task image endpoint handler."""
    task = workflow_service.load_task_by_request_id(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    image_path = Path(str(task["image_path"]))
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="image_file_not_found")

    return FileResponse(image_path, media_type=workflow_service.image_media_type(image_path))


async def get_task_annotated_image(request_id: str) -> StreamingResponse:
    """Get annotated task image endpoint handler."""
    task = workflow_service.load_task_by_request_id(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    # Use module-level reference for monkeypatching
    import app.routes.tasks as tasks_module
    annotate_fn = tasks_module.annotate_image

    annotated = annotate_fn(str(task["image_path"]), task.get("detections", []) or [])
    if annotated is None:
        raise HTTPException(status_code=404, detail="annotated_image_not_found")

    buffer = io.BytesIO()
    annotated.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


async def get_task_report(request_id: str) -> PlainTextResponse:
    """Generate a Markdown report for a completed task."""
    task = workflow_service.load_task_by_request_id(request_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")

    lines: list[str] = []
    lines.append(f"# 智能施药任务报告")
    lines.append("")
    lines.append(f"**请求 ID**: {task.get('request_id', '--')}")
    updated = task.get("updated_at")
    if updated:
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**任务状态**: {task.get('status', '--')}")
    lines.append("")

    # 地块信息
    field = task.get("field") or {}
    if field:
        lines.append("## 地块信息")
        lines.append("")
        for key in ("field_name", "field_id", "area_mu"):
            if field.get(key):
                label = {"field_name": "地块名称", "field_id": "地块 ID", "area_mu": "面积(亩)"}.get(key, key)
                lines.append(f"- {label}: {field[key]}")
        crop = field.get("crop_cycle")
        if isinstance(crop, dict) and crop.get("crop_name"):
            lines.append(f"- 作物: {crop['crop_name']}")
        lines.append("")

    # 虫害检测
    detections = task.get("detections") or []
    if detections:
        lines.append("## 虫害检测")
        lines.append("")
        lines.append("| 害虫类型 | 置信度 | 危害等级 |")
        lines.append("|----------|--------|----------|")
        for d in detections:
            pest = d.get("pest_type", "未知")
            conf = d.get("confidence", 0)
            level = "高" if conf >= 0.8 else ("中" if conf >= 0.5 else "低")
            lines.append(f"| {pest} | {conf:.0%} | {level} |")
        lines.append("")

    # 天气数据
    weather = task.get("weather") or {}
    if weather:
        lines.append("## 气象数据")
        lines.append("")
        temp = weather.get("temperature")
        hum = weather.get("humidity")
        wind = weather.get("wind_speed") or weather.get("windSpeed")
        if temp is not None:
            lines.append(f"- 温度: {temp}°C")
        if hum is not None:
            lines.append(f"- 湿度: {hum}%")
        if wind is not None:
            lines.append(f"- 风速: {wind}m/s")
        lines.append("")

    # 合规审核
    compliance = task.get("compliance") or {}
    if compliance:
        lines.append("## 合规审核")
        lines.append("")
        lines.append(f"- **审核结果**: {compliance.get('status', '--')}")
        lines.append(f"- **合规分数**: {compliance.get('score', '--')}分")
        reasons = compliance.get("blocking_reasons") or []
        if reasons:
            lines.append("- **拦截原因**:")
            for r in reasons:
                lines.append(f"  - {r}")
        warnings = compliance.get("warnings") or []
        if warnings:
            lines.append("- **风险提示**:")
            for w in warnings:
                lines.append(f"  - {w}")
        lines.append("")

    # AI 决策
    decision = task.get("decision") or {}
    medication = decision.get("用药") if isinstance(decision, dict) else {}
    if medication:
        lines.append("## AI 决策 — 用药方案")
        lines.append("")
        for key, label in [("农药名称", "农药"), ("浓度", "浓度"), ("配比", "配比"), ("总量", "总量")]:
            val = medication.get(key)
            if val:
                lines.append(f"- **{label}**: {val}")
        tips = medication.get("安全提示")
        if isinstance(tips, list) and tips:
            lines.append("")
            lines.append("### 安全提示")
            lines.append("")
            for tip in tips:
                lines.append(f"- {tip}")
        lines.append("")

    # RAG 会诊
    rag = task.get("rag_context") or {}
    consultation = rag.get("consultation_detail") if isinstance(rag, dict) else None
    if consultation and isinstance(consultation, dict):
        experts = consultation.get("experts") or {}
        if experts:
            lines.append("## 多智能体会诊")
            lines.append("")
            lines.append(f"- **决策路径**: {rag.get('decision_path', '--')}")
            lines.append(f"- **置信度**: {rag.get('confidence', 0):.0%}")
            lines.append(f"- **一致度**: {rag.get('agreement', '--')}")
            lines.append("")
            lines.append("| 专家 | 推荐农药 | 用量 |")
            lines.append("|------|----------|------|")
            for role, info in experts.items():
                name = info.get("name", role) if isinstance(info, dict) else role
                pesticide = info.get("农药名称", "--") if isinstance(info, dict) else "--"
                dosage = info.get("总量", "--") if isinstance(info, dict) else "--"
                lines.append(f"| {name} | {pesticide} | {dosage} |")
            lines.append("")

    # 无人机执行
    drone = task.get("drone") or {}
    if drone and isinstance(drone, dict):
        lines.append("## 无人机执行")
        lines.append("")
        if drone.get("task_id"):
            lines.append(f"- 任务 ID: {drone['task_id']}")
        if drone.get("status"):
            lines.append(f"- 状态: {drone['status']}")
        spray = task.get("spray_summary") or {}
        if spray.get("spray_area_mu"):
            lines.append(f"- 喷洒面积: {spray['spray_area_mu']:.2f} 亩")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告由牧野智农系统自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")


def register_tasks_routes(app: FastAPI) -> None:
    """Register tasks routes."""
    app.get("/tasks/{request_id}/original-image")(get_task_original_image)
    app.get("/api/tasks/{request_id}/original-image", include_in_schema=False)(get_task_original_image)
    app.get("/tasks/{request_id}/annotated-image")(get_task_annotated_image)
    app.get("/api/tasks/{request_id}/annotated-image", include_in_schema=False)(get_task_annotated_image)
    app.get("/tasks/{request_id}/report")(get_task_report)
    app.get("/api/tasks/{request_id}/report", include_in_schema=False)(get_task_report)
