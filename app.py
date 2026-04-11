from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageDraw
from streamlit.components.v1 import html as st_html
from streamlit_autorefresh import st_autorefresh

from modules.common import IMAGES_DIR, ensure_runtime_dirs
from modules.event_bus import FileEventBus, build_task_views, load_events


EVENT_BUS = FileEventBus()


def sanitize_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".jpg"
    stem = Path(filename).stem
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", stem).strip("-")
    return f"{normalized or 'upload'}{suffix}"


def save_uploaded_image(uploaded_file: Any) -> Path:
    ensure_runtime_dirs()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = sanitize_filename(uploaded_file.name)
    target = IMAGES_DIR / f"{timestamp}-{filename}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def annotate_image(image_path: str | Path, detections: list[dict[str, Any]]) -> Image.Image | None:
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
        label = f"{detection.get('pest_type', 'unknown')} {detection.get('confidence', 0):.2f}"
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


def render_log_box(events: list[dict[str, Any]]) -> None:
    log_lines = []
    for event in events[-80:]:
        timestamp = str(event.get("timestamp", ""))[11:19]
        line = f"[{timestamp}] {event.get('stage')} / {event.get('status')} - {event.get('message')}"
        log_lines.append(html.escape(line))

    content = "<br/>".join(log_lines) if log_lines else "暂无事件"
    st_html(
        f"""
        <div id="logbox" style="
            height: 320px;
            overflow-y: auto;
            background: #0f172a;
            color: #e2e8f0;
            padding: 14px;
            border-radius: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 13px;
            line-height: 1.5;
            border: 1px solid #1e293b;
        ">{content}</div>
        <script>
          const box = document.getElementById("logbox");
          if (box) {{
            box.scrollTop = box.scrollHeight;
          }}
        </script>
        """,
        height=340,
    )


def render_dashboard() -> None:
    events = load_events(limit=500)
    tasks = build_task_views(events)
    latest_task = tasks[0] if tasks else None

    st.title("牧野智能农业演示面板")

    summary_cols = st.columns(4)
    summary_cols[0].metric("当前请求", latest_task["request_id"][:8] if latest_task else "-")
    summary_cols[1].metric("当前阶段", latest_task["current_stage"] if latest_task else "waiting")
    summary_cols[2].metric("任务状态", latest_task["status"] if latest_task else "idle")
    summary_cols[3].metric("总事件数", len(events))

    latest_uploaded_path = st.session_state.get("latest_uploaded_path")
    original_image_path = latest_task["image_path"] if latest_task and latest_task.get("image_path") else latest_uploaded_path
    detections = latest_task.get("detections", []) if latest_task else []

    image_cols = st.columns(2)
    with image_cols[0]:
        st.subheader("原始图片")
        if original_image_path and Path(original_image_path).exists():
            st.image(str(original_image_path), use_container_width=True)
            st.caption(str(original_image_path))
        else:
            st.info("请在左侧上传一张图片，或等待后端捕获图片。")

    with image_cols[1]:
        st.subheader("YOLO 识别结果")
        if original_image_path and Path(original_image_path).exists():
            annotated = annotate_image(original_image_path, detections)
            if annotated:
                st.image(annotated, use_container_width=True)
            if detections:
                st.caption(f"识别到 {len(detections)} 个目标")
            else:
                st.caption("暂无检测框，可能正在识别或未发现目标。")
        else:
            st.info("等待识别结果。")

    section_cols = st.columns(2)
    with section_cols[0]:
        st.subheader("天气信息")
        weather = latest_task.get("weather", {}) if latest_task else {}
        metric_cols = st.columns(4)
        metric_cols[0].metric("温度", f"{weather['temperature']} ℃" if weather else "-")
        metric_cols[1].metric("湿度", f"{weather['humidity']} %" if weather else "-")
        metric_cols[2].metric("风向", weather.get("wind_direction", "-") if weather else "-")
        metric_cols[3].metric("风力", weather.get("wind_scale_text", "-") if weather else "-")
        if weather:
            st.caption(f"天气概况：{weather.get('summary', '-')}")
            st.caption(f"推算风速上限：{weather.get('wind_speed', '-')} m/s")
        else:
            st.info("等待后端获取天气信息。")

    with section_cols[1]:
        st.subheader("千问建议")
        decision = latest_task.get("decision", {}) if latest_task else {}
        medication = decision.get("用药", {})
        instruction = decision.get("指令", {})
        detail_cols = st.columns(2)
        detail_cols[0].metric("农药名称", medication.get("农药名称", "-"))
        detail_cols[1].metric("喷洒速率", str(instruction.get("喷洒速率", "-")))
        if decision:
            st.json(decision)
        else:
            st.info("等待千问生成决策。")

    st.subheader("无人机状态")
    drone = latest_task.get("drone", {}) if latest_task else {}
    progress_value = int(drone.get("progress", 0)) if drone else 0
    st.progress(progress_value / 100 if progress_value else 0)
    if drone:
        instruction = drone.get("instruction", {})
        st.caption(
            f"状态：{drone.get('message', '-')}"
            f" | 任务号：{drone.get('task_id', '-')}"
            f" | 进度：{progress_value}%"
            f" | 当前航点：{drone.get('current_waypoint_index', 0)}"
        )
        if instruction:
            st.code(
                f"飞行路径: {instruction.get('飞行路径', [])}\n"
                f"覆盖区域: {instruction.get('覆盖区域', {}).get('coordinates', [])}",
                language="text",
            )
    else:
        st.info("等待无人机任务状态。")

    st.subheader("实时事件日志")
    render_log_box(latest_task["events"] if latest_task else events)


def sidebar_controls() -> None:
    with st.sidebar:
        st.header("图片投喂")
        uploaded_file = st.file_uploader("上传农田图片", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None and st.button("发送到后端", use_container_width=True):
            target = save_uploaded_image(uploaded_file)
            st.session_state["latest_uploaded_path"] = str(target)
            st.success(f"图片已写入 {target.name}，后端将自动处理。")

        if st.button("清空演示事件", use_container_width=True):
            EVENT_BUS.clear()
            st.session_state.pop("latest_uploaded_path", None)
            st.rerun()

        st.caption("后端会监听 data/images/ 目录。上传完成后，稍等片刻即可在主面板看到处理结果。")
        st.code("python main.py --with-demo-stack", language="bash")


def main() -> None:
    st.set_page_config(page_title="牧野演示面板", layout="wide")
    st_autorefresh(interval=1500, key="muye-dashboard-refresh")
    ensure_runtime_dirs()
    sidebar_controls()
    render_dashboard()


if __name__ == "__main__":
    main()
