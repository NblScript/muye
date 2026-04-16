from __future__ import annotations

import html
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageDraw
from streamlit.components.v1 import html as st_html
from streamlit_autorefresh import st_autorefresh

from modules.common import DATA_DIR, IMAGES_DIR, ensure_runtime_dirs
from modules.event_bus import FileEventBus, build_task_views, load_events
from modules.sqlite_store import SqliteStore


EVENT_BUS = FileEventBus()

DRONE_STAGE_LABELS = {
    "submitted": "任务提交",
    "queued": "任务接收",
    "connecting": "链路连接",
    "connected": "飞控连接",
    "ready": "定位就绪",
    "uploaded": "航线上传",
    "armed": "解锁待飞",
    "takeoff": "起飞",
    "enroute": "前往作业区",
    "spraying": "喷洒执行",
    "returning": "返航",
    "completed": "任务完成",
    "error": "异常",
    "failed": "失败",
}

DRONE_STAGE_SEQUENCES = {
    "px4": [
        "connecting",
        "connected",
        "ready",
        "uploaded",
        "armed",
        "takeoff",
        "spraying",
        "completed",
    ],
    "virtual_api": [
        "submitted",
        "queued",
        "takeoff",
        "enroute",
        "spraying",
        "returning",
        "completed",
    ],
    "simulated": [
        "queued",
        "takeoff",
        "spraying",
        "completed",
    ],
    "generic": [
        "submitted",
        "queued",
        "connecting",
        "connected",
        "ready",
        "uploaded",
        "armed",
        "takeoff",
        "enroute",
        "spraying",
        "returning",
        "completed",
    ],
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --bg: #f3f4f6;
            --card: rgba(255, 255, 255, 0.88);
            --card-solid: #ffffff;
            --forest: #064e3b;
            --forest-soft: #0f766e;
            --green-glow: #22c55e;
            --blue-glow: #38bdf8;
            --ink: #1f2937;
            --muted: #4b5563;
            --line: rgba(15, 23, 42, 0.08);
            --shadow: 0 18px 38px rgba(15, 23, 42, 0.10);
            --shadow-strong: 0 24px 52px rgba(15, 23, 42, 0.14);
        }

        .stApp {
            background-color: var(--bg);
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1600' height='260' viewBox='0 0 1600 260'%3E%3Cpath fill='%23dcfce7' d='M0 96C89 125 178 154 267 149.3C356 144 444 106 533 101.3C622 96 711 122 800 133.3C889 144 978 138 1067 117.3C1156 96 1244 58 1333 42.7C1422 27 1511 37 1600 46.7V0H0Z'/%3E%3Cpath fill='%23bbf7d0' d='M0 148C89 154 178 160 267 149.3C356 138 444 112 533 106.7C622 101 711 117 800 133.3C889 149 978 165 1067 149.3C1156 133 1244 85 1333 74.7C1422 64 1511 90 1600 117.3V0H0Z' opacity='0.9'/%3E%3C/svg%3E"),
                radial-gradient(circle at 10% 20%, rgba(34,197,94,0.08), transparent 24%),
                radial-gradient(circle at 90% 12%, rgba(14,165,233,0.07), transparent 20%);
            background-repeat: no-repeat, no-repeat, no-repeat;
            background-size: 100% 260px, 520px 520px, 420px 420px;
            background-position: top center, top left, top right;
            color: var(--ink);
            font-family: "Inter", "Roboto", "PingFang SC", "Noto Sans SC", sans-serif;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1320px;
            padding-top: 1.3rem;
            padding-bottom: 2.5rem;
        }

        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at top right, rgba(34,197,94,0.18), transparent 22%),
                linear-gradient(180deg, rgba(6, 78, 59, 0.98), rgba(6, 78, 59, 0.94));
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        [data-testid="stSidebar"] * {
            color: #ecfdf5;
        }

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
            background: rgba(255,255,255,0.06);
            border: 1.5px dashed rgba(255,255,255,0.28);
            border-radius: 20px;
            padding: 1.4rem 1rem;
            transition: all 0.2s ease;
        }

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
            border-color: rgba(34,197,94,0.95);
            background: rgba(255,255,255,0.10);
            transform: translateY(-2px);
            box-shadow: 0 14px 28px rgba(0,0,0,0.18);
        }

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] section::before {
            content: "⇪";
            display: block;
            font-size: 2rem;
            margin-bottom: 0.45rem;
            color: #86efac;
            text-align: center;
        }

        [data-testid="stSidebar"] .stButton > button {
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.07);
            color: #f0fdf4;
            transition: all 0.2s ease;
            box-shadow: none;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            transform: translateY(-2px);
            background: #22c55e;
            border-color: #22c55e;
            color: #052e16;
            box-shadow: 0 12px 28px rgba(34,197,94,0.28);
        }

        [data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(10px);
            transition: all 0.2s ease;
        }

        [data-testid="stMetric"]:hover,
        .muye-card-wrap:hover,
        .muye-upload-shell:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-strong);
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-size: 0.86rem;
        }

        [data-testid="stMetricValue"] {
            color: var(--ink);
            font-weight: 700;
        }

        div[data-testid="stImage"] img {
            border-radius: 26px;
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
            transition: all 0.2s ease;
        }

        div[data-testid="stImage"] img:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-strong);
        }

        .muye-hero {
            background:
                linear-gradient(135deg, rgba(255,255,255,0.70), rgba(255,255,255,0.52)),
                linear-gradient(120deg, rgba(34,197,94,0.16), rgba(14,165,233,0.10));
            border-radius: 30px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.1rem;
            color: var(--ink);
            border: 1px solid rgba(255,255,255,0.5);
            box-shadow: var(--shadow-strong);
            backdrop-filter: blur(16px);
        }

        .muye-hero h1 {
            margin: 0;
            font-size: 2.15rem;
            line-height: 1.08;
            letter-spacing: -0.03em;
            color: var(--ink);
        }

        .muye-hero p {
            margin: 0.55rem 0 0;
            color: var(--muted);
            font-size: 0.98rem;
        }

        .muye-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
        }

        .muye-badge {
            padding: 0.42rem 0.8rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.66);
            border: 1px solid rgba(15,23,42,0.08);
            color: var(--ink);
            font-size: 0.9rem;
            box-shadow: 0 6px 18px rgba(15,23,42,0.06);
        }

        .muye-card-wrap {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(12px);
            transition: all 0.2s ease;
        }

        .muye-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.85rem;
        }

        .muye-card {
            background: var(--card-solid);
            border: 1px solid rgba(15,23,42,0.05);
            border-radius: 18px;
            padding: 0.9rem;
            transition: all 0.2s ease;
        }

        .muye-card:hover {
            transform: translateY(-2px);
        }

        .muye-card-label {
            color: var(--muted);
            font-size: 0.8rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .muye-card-value {
            color: var(--ink);
            font-size: 1.04rem;
            font-weight: 700;
            line-height: 1.28;
        }

        .muye-pill-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.7rem;
        }

        .muye-pill {
            padding: 0.42rem 0.76rem;
            border-radius: 999px;
            background: rgba(255,251,235,0.95);
            color: #92400e;
            border: 1px solid rgba(245,158,11,0.28);
            font-size: 0.9rem;
            font-weight: 600;
        }

        .muye-mode-row {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.6rem;
            margin-bottom: 0.75rem;
        }

        .muye-mode-pill {
            border-radius: 16px;
            padding: 0.75rem 0.8rem;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            transition: all 0.2s ease;
        }

        .muye-mode-pill:hover {
            transform: translateY(-2px);
            background: rgba(255,255,255,0.10);
        }

        .muye-mode-label {
            color: rgba(236,253,245,0.72);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.25rem;
        }

        .muye-mode-value {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 72px;
            padding: 0.26rem 0.65rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
            color: #ecfdf5;
            background: rgba(255,255,255,0.10);
        }

        .muye-mode-value.real {
            background: linear-gradient(135deg, #34d399, #10b981);
            color: #052e16;
            box-shadow: 0 10px 22px rgba(16,185,129,0.30);
        }

        .muye-mode-value.mock {
            background: linear-gradient(135deg, #f59e0b, #fbbf24);
            color: #451a03;
            box-shadow: 0 10px 22px rgba(245,158,11,0.24);
        }

        .muye-mode-value.virtual {
            background: linear-gradient(135deg, #38bdf8, #2563eb);
            color: #eff6ff;
            box-shadow: 0 10px 22px rgba(37,99,235,0.24);
        }

        .muye-pest-banner {
            background: linear-gradient(135deg, rgba(240,253,244,0.98), rgba(220,252,231,0.94));
            border: 1px solid rgba(34,197,94,0.20);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: var(--shadow);
        }

        .muye-weather-main {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            margin-bottom: 0.9rem;
        }

        .muye-weather-icon {
            width: 58px;
            height: 58px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(52,211,153,0.18), rgba(56,189,248,0.18));
            font-size: 1.9rem;
        }

        .muye-weather-temp {
            color: var(--ink);
            font-size: 2rem;
            font-weight: 800;
            line-height: 1;
        }

        .muye-weather-text {
            color: var(--muted);
            font-size: 0.94rem;
            margin-top: 0.18rem;
        }

        .muye-highlight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 0.35rem;
        }

        .muye-highlight-card {
            background: linear-gradient(135deg, rgba(220,252,231,0.90), rgba(240,253,244,0.96));
            border: 1px solid rgba(16,185,129,0.16);
            border-radius: 18px;
            padding: 0.95rem;
        }

        .muye-safety-box {
            margin-top: 0.85rem;
            background: #fffbeb;
            border: 1px solid rgba(251,146,60,0.35);
            border-left: 4px solid #f59e0b;
            border-radius: 18px;
            padding: 0.95rem 1rem;
        }

        .muye-progress-shell {
            margin-top: 0.35rem;
            padding: 1rem 1.05rem;
            border-radius: 24px;
            background: var(--card);
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }

        .muye-progress-track {
            height: 16px;
            border-radius: 999px;
            background: rgba(148,163,184,0.18);
            overflow: hidden;
            position: relative;
        }

        .muye-progress-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #22c55e, #14b8a6, #38bdf8);
            background-size: 200% 100%;
            animation: muye-flow 2.4s linear infinite;
            box-shadow: inset 0 0 12px rgba(255,255,255,0.24);
        }

        @keyframes muye-flow {
            0% { background-position: 0% 50%; }
            100% { background-position: 200% 50%; }
        }

        .muye-telemetry {
            margin-top: 0.9rem;
            background: #0f172a;
            color: #dbeafe;
            border-radius: 18px;
            padding: 0.95rem 1rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            border: 1px solid rgba(148,163,184,0.16);
            white-space: pre-wrap;
        }

        .muye-map-shell {
            margin-top: 0.9rem;
            background: #ffffff;
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 22px;
            padding: 0.9rem;
            box-shadow: var(--shadow);
        }

        .muye-map-title {
            color: var(--muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.55rem;
        }

        .muye-command-shell {
            margin-top: 0.35rem;
            padding: 1.05rem;
            border-radius: 26px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.92), rgba(255,255,255,0.84)),
                linear-gradient(135deg, rgba(34,197,94,0.10), rgba(56,189,248,0.08));
            border: 1px solid rgba(15,23,42,0.08);
            box-shadow: var(--shadow);
        }

        .muye-command-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: 0.9rem;
            flex-wrap: wrap;
        }

        .muye-command-kicker {
            color: var(--muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.3rem;
        }

        .muye-command-title {
            color: var(--ink);
            font-size: 1.16rem;
            font-weight: 800;
            line-height: 1.25;
        }

        .muye-command-subtitle {
            margin-top: 0.3rem;
            color: var(--muted);
            font-size: 0.92rem;
        }

        .muye-command-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            background: rgba(6,78,59,0.08);
            color: #065f46;
            border: 1px solid rgba(16,185,129,0.16);
            font-size: 0.88rem;
            font-weight: 700;
        }

        .muye-stage-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
            gap: 0.65rem;
            margin-bottom: 0.9rem;
        }

        .muye-stage-chip {
            border-radius: 18px;
            padding: 0.72rem 0.78rem;
            border: 1px solid rgba(148,163,184,0.20);
            background: rgba(248,250,252,0.92);
            min-height: 86px;
        }

        .muye-stage-chip.done {
            background: linear-gradient(135deg, rgba(220,252,231,0.96), rgba(240,253,244,0.96));
            border-color: rgba(34,197,94,0.22);
        }

        .muye-stage-chip.current {
            background: linear-gradient(135deg, rgba(224,242,254,0.98), rgba(236,254,255,0.96));
            border-color: rgba(56,189,248,0.32);
            box-shadow: 0 14px 26px rgba(56,189,248,0.12);
        }

        .muye-stage-chip.pending {
            opacity: 0.8;
        }

        .muye-stage-status {
            color: var(--muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.32rem;
        }

        .muye-stage-name {
            color: var(--ink);
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .muye-stage-meta {
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 0.42rem;
            line-height: 1.35;
        }

        .muye-telemetry-note {
            margin-top: 0.8rem;
            padding: 0.88rem 0.95rem;
            border-radius: 18px;
            background: rgba(15,23,42,0.04);
            border: 1px solid rgba(148,163,184,0.18);
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.55;
        }

        .muye-outcome-shell {
            margin-top: 0.85rem;
            padding: 1rem 1.05rem;
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(248,250,252,0.96), rgba(255,255,255,0.92));
            border: 1px solid rgba(148,163,184,0.16);
            box-shadow: var(--shadow);
        }

        .muye-outcome-shell.success {
            background: linear-gradient(135deg, rgba(220,252,231,0.94), rgba(240,253,244,0.96));
            border-color: rgba(34,197,94,0.22);
        }

        .muye-outcome-shell.running {
            background: linear-gradient(135deg, rgba(224,242,254,0.96), rgba(239,246,255,0.96));
            border-color: rgba(56,189,248,0.24);
        }

        .muye-outcome-shell.error {
            background: linear-gradient(135deg, rgba(254,242,242,0.96), rgba(255,247,237,0.96));
            border-color: rgba(248,113,113,0.26);
        }

        .muye-outcome-kicker {
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.34rem;
        }

        .muye-outcome-title {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 800;
            line-height: 1.28;
        }

        .muye-outcome-summary {
            margin-top: 0.4rem;
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.55;
        }

        .muye-alert-box {
            margin-top: 0.85rem;
            border-radius: 18px;
            padding: 0.9rem 0.95rem;
            background: linear-gradient(135deg, rgba(254,242,242,0.96), rgba(255,247,237,0.96));
            border: 1px solid rgba(248,113,113,0.26);
            color: #7f1d1d;
        }

        .muye-alert-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.32rem;
            color: #991b1b;
            font-weight: 700;
        }

        .muye-history-meta {
            margin-top: 0.85rem;
            padding-top: 0.85rem;
            border-top: 1px dashed rgba(148,163,184,0.26);
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem;
        }

        .muye-history-meta-card {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 16px;
            padding: 0.78rem 0.82rem;
        }

        .muye-history-meta-label {
            color: var(--muted);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.28rem;
        }

        .muye-history-meta-value {
            color: var(--ink);
            font-size: 0.94rem;
            font-weight: 700;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(latest_task: dict[str, Any] | None, event_count: int) -> None:
    request_id = latest_task["request_id"][:8] if latest_task else "-"
    stage = latest_task["current_stage"] if latest_task else "waiting"
    status = latest_task["status"] if latest_task else "idle"
    drone = latest_task.get("drone", {}) if latest_task else {}
    drone_timeline = latest_task.get("drone_timeline", []) if latest_task else []
    _, backend_label = infer_drone_backend(drone, drone_timeline)
    st.markdown(
        f"""
        <section class="muye-hero">
          <h1>牧野智能农业演示面板</h1>
          <p>聚焦虫情识别、天气感知、AI 决策和无人机执行的完整演示闭环，适合比赛现场展示任务流与 PX4 执行状态。</p>
          <div class="muye-badges">
            <span class="muye-badge">当前请求：{request_id}</span>
            <span class="muye-badge">当前阶段：{stage}</span>
            <span class="muye-badge">任务状态：{status}</span>
            <span class="muye-badge">执行链路：{backend_label}</span>
            <span class="muye-badge">事件总数：{event_count}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def current_mode_labels() -> dict[str, str]:
    return {
        "yolo": "real",
        "weather": "mock" if os.getenv("QWEATHER_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"} else "real",
        "qwen": "mock" if os.getenv("QWEN_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"} else "real",
        "drone": "virtual",
    }


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


def summarize_pests(detections: list[dict[str, Any]]) -> tuple[list[str], str]:
    if not detections:
        return [], "未识别到害虫目标"

    counts: dict[str, int] = {}
    for detection in detections:
        pest_name = str(detection.get("pest_type", "unknown"))
        counts[pest_name] = counts.get(pest_name, 0) + 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    labels = [f"{name} × {count}" for name, count in ordered]
    summary = "，".join(labels)
    return labels, summary


def render_info_cards(title: str, items: list[tuple[str, str]]) -> None:
    cards = "".join(
        f"""
        <div class="muye-card">
          <div class="muye-card-label">{html.escape(label)}</div>
          <div class="muye-card-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in items
    )
    st.markdown(
        f"""
        <div class="muye-card-wrap">
          <h3 style="margin:0 0 0.65rem;color:#17372a;">{html.escape(title)}</h3>
          <div class="muye-card-grid">{cards}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_number(value: Any, *, digits: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if number.is_integer():
        text = str(int(number))
    else:
        text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def format_timestamp_display(value: Any, *, include_date: bool = False) -> str:
    if not value:
        return "-"
    try:
        normalized = str(value).replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(normalized)
        return timestamp.strftime("%m-%d %H:%M:%S" if include_date else "%H:%M:%S")
    except ValueError:
        text = str(value)
        return text[:19] if include_date else text[11:19]


def infer_drone_backend(
    drone: dict[str, Any] | None,
    timeline: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    active_drone = drone or {}
    timeline = timeline or []
    task_id = str(active_drone.get("task_id") or "").lower()
    statuses = {str(item.get("status") or "").lower() for item in timeline}
    current_status = str(active_drone.get("status") or "").lower()
    if current_status:
        statuses.add(current_status)

    if task_id.startswith("px4-") or statuses.intersection({"connecting", "connected", "ready", "uploaded", "armed"}):
        return "px4", "PX4 SITL"
    if task_id.startswith("vd-") or statuses.intersection({"submitted", "enroute", "returning"}):
        return "virtual_api", "虚拟无人机 API"
    if task_id.startswith("sim-"):
        return "simulated", "内置模拟"
    return "generic", "无人机链路"


def build_drone_stage_sequence(
    backend_key: str,
    timeline: list[dict[str, Any]],
    current_status: str,
) -> list[str]:
    sequence = list(DRONE_STAGE_SEQUENCES.get(backend_key, DRONE_STAGE_SEQUENCES["generic"]))
    seen_statuses = [
        str(item.get("status") or "").lower()
        for item in timeline
        if str(item.get("status") or "").strip()
    ]
    if current_status and current_status not in sequence:
        sequence.append(current_status)
    for status in seen_statuses:
        if status and status not in sequence:
            sequence.append(status)
    if backend_key == "generic" and seen_statuses:
        ordered_seen = []
        for status in seen_statuses:
            if status not in ordered_seen:
                ordered_seen.append(status)
        return ordered_seen
    return sequence


def build_drone_stage_markup(
    timeline: list[dict[str, Any]],
    current_status: str,
    backend_key: str,
) -> str:
    sequence = build_drone_stage_sequence(backend_key, timeline, current_status)
    timeline_by_status = {
        str(item.get("status") or "").lower(): item
        for item in timeline
        if str(item.get("status") or "").strip()
    }
    current_index = sequence.index(current_status) if current_status in sequence else -1
    cards = []
    for index, status in enumerate(sequence):
        timeline_item = timeline_by_status.get(status, {})
        if status == current_status:
            state_class = "current"
            state_label = "当前"
        elif timeline_item:
            state_class = "done"
            state_label = "已达成"
        elif current_index >= 0 and index < current_index:
            state_class = "done"
            state_label = "已达成"
        else:
            state_class = "pending"
            state_label = "待执行"
        message = str(timeline_item.get("message") or "等待进入该阶段")
        timestamp = format_timestamp_display(timeline_item.get("timestamp"))
        cards.append(
            f"""
            <div class="muye-stage-chip {state_class}">
              <div class="muye-stage-status">{html.escape(state_label)}</div>
              <div class="muye-stage-name">{html.escape(DRONE_STAGE_LABELS.get(status, status or '-'))}</div>
              <div class="muye-stage-meta">{html.escape(message)}<br/>{html.escape(timestamp)}</div>
            </div>
            """
        )
    return "".join(cards)


def build_field_snapshot(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {}

    field = dict(task.get("field") or {})
    drone = task.get("drone") or {}
    instruction = drone.get("instruction", {}) if isinstance(drone.get("instruction"), dict) else {}

    if not field.get("field_id"):
        field["field_id"] = task.get("field_id")
    if not field.get("field_name"):
        field["field_name"] = instruction.get("field_name")
    if not field.get("field_code"):
        field["field_code"] = field.get("field_id")
    if not field.get("geofence"):
        coverage = instruction.get("覆盖区域", {}) if isinstance(instruction, dict) else {}
        if isinstance(coverage, dict):
            field["geofence"] = coverage.get("coordinates", [])
    if field.get("area_mu") in (None, ""):
        spray_summary = task.get("spray_summary") or {}
        field["area_mu"] = spray_summary.get("spray_area_mu")
    return field


def infer_operation_outcome(task: dict[str, Any] | None) -> dict[str, str]:
    if not task:
        return {
            "tone": "running",
            "result_label": "等待任务",
            "verdict": "等待完整处理链路启动。",
            "summary": "当前还没有可用于说明比赛闭环的有效任务。",
        }

    spray_summary = task.get("spray_summary") or {}
    drone = task.get("drone") or {}
    decision = task.get("decision") or {}
    detections = task.get("detections") or []
    result_status = str(spray_summary.get("result_status") or "").lower()
    task_status = str(task.get("status") or "").lower()
    drone_status = str(drone.get("status") or "").lower()
    medication = decision.get("用药", {}) if isinstance(decision, dict) else {}

    if result_status == "completed" or drone_status == "completed" or task_status == "completed":
        tone = "success"
        result_label = "闭环完成"
        verdict = "虫害识别、决策生成、任务执行和作业记录已形成完整闭环。"
    elif result_status in {"failed", "cancelled"} or task_status == "error":
        tone = "error"
        result_label = "执行异常"
        verdict = "当前任务未正常闭环，需检查飞控状态、接口响应或作业参数。"
    else:
        tone = "running"
        result_label = "执行中"
        verdict = "系统正在推进识别、决策与喷洒执行链路。"

    area_text = format_number(spray_summary.get("spray_area_mu"), digits=1, suffix="亩")
    dosage_text = format_number(spray_summary.get("total_dosage"), digits=1, suffix="L")
    pest_count = len(detections)
    pesticide_name = str(medication.get("农药名称") or "-")
    summary = (
        f"当前批次识别到 {pest_count} 个目标，建议药剂 {pesticide_name}，"
        f"计划/记录作业面积 {area_text}，总药量 {dosage_text}。"
    )
    return {
        "tone": tone,
        "result_label": result_label,
        "verdict": verdict,
        "summary": summary,
    }


def render_operation_closure_panel(task: dict[str, Any] | None) -> None:
    outcome = infer_operation_outcome(task)
    task = task or {}
    spray_summary = task.get("spray_summary") or {}
    drone = task.get("drone") or {}
    latest_time = format_timestamp_display(
        spray_summary.get("spray_date") or task.get("updated_at"),
        include_date=True,
    )
    render_info_cards(
        "闭环摘要",
        [
            ("作业批次", str(task.get("request_id", "-"))[:8]),
            ("记录时间", latest_time),
            ("执行结果", outcome["result_label"]),
            ("结果状态", str(spray_summary.get("result_status") or drone.get("status") or task.get("status") or "-")),
            ("飞控任务号", str(drone.get("task_id", "-"))),
            ("任务闭环", outcome["verdict"]),
        ],
    )
    st.markdown(
        f"""
        <div class="muye-outcome-shell {html.escape(outcome['tone'])}">
          <div class="muye-outcome-kicker">Operation Outcome</div>
          <div class="muye-outcome-title">{html.escape(outcome['result_label'])}</div>
          <div class="muye-outcome-summary">
            {html.escape(outcome['summary'])}<br/>
            {html.escape(outcome['verdict'])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_history_detail_markup(task: dict[str, Any]) -> str:
    field = build_field_snapshot(task)
    spray_summary = task.get("spray_summary") or {}
    drone = task.get("drone") or {}
    outcome = infer_operation_outcome(task)
    medication = (task.get("decision") or {}).get("用药", {}) if isinstance(task.get("decision"), dict) else {}
    detail_items = [
        ("地块", str(field.get("field_name") or field.get("field_code") or field.get("field_id") or "-")),
        ("闭环结果", outcome["result_label"]),
        ("作业面积", format_number(spray_summary.get("spray_area_mu"), digits=1, suffix=" 亩")),
        ("总药量", format_number(spray_summary.get("total_dosage"), digits=1, suffix=" L")),
        ("农药", str(medication.get("农药名称") or "-")),
        ("飞控任务号", str(drone.get("task_id") or "-")),
    ]
    return "".join(
        f"""
        <div class="muye-history-meta-card">
          <div class="muye-history-meta-label">{html.escape(label)}</div>
          <div class="muye-history-meta-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in detail_items
    )


def build_history_timeline_text(task: dict[str, Any]) -> str:
    drone_timeline = task.get("drone_timeline") or []
    if not drone_timeline:
        return "暂无无人机阶段记录"
    labels = []
    for item in drone_timeline:
        status = str(item.get("status") or "").lower()
        label = DRONE_STAGE_LABELS.get(status, status or "-")
        if label not in labels:
            labels.append(label)
    return " -> ".join(labels) if labels else "暂无无人机阶段记录"


def render_field_operations_panel(task: dict[str, Any] | None) -> None:
    field = build_field_snapshot(task)
    if not field:
        st.info("等待地块上下文与农田边界数据。")
        return

    spray_summary = task.get("spray_summary", {}) if task else {}
    geofence = field.get("geofence") if isinstance(field.get("geofence"), list) else []
    boundary_svg = None
    if geofence:
        boundary_svg = build_route_map_svg({"覆盖区域": {"coordinates": geofence}})

    location_parts = [field.get("province"), field.get("city"), field.get("county")]
    location_text = "".join(str(item) for item in location_parts if item)
    render_info_cards(
        "地块概况",
        [
            ("地块名称", str(field.get("field_name") or "-")),
            ("地块编号", str(field.get("field_code") or field.get("field_id") or "-")),
            ("所属区域", location_text or "-"),
            ("农田面积", format_number(field.get("area_mu"), digits=1, suffix=" 亩")),
            ("折合公顷", format_number(field.get("area_hectare"), digits=2, suffix=" ha")),
            ("边界顶点", str(len(geofence))),
        ],
    )

    spray_items = [
        ("作业面积", format_number(spray_summary.get("spray_area_mu"), digits=1, suffix=" 亩")),
        ("预计总药量", format_number(spray_summary.get("total_dosage"), digits=1, suffix=" L")),
        ("亩均剂量", format_number(spray_summary.get("dosage_per_mu"), digits=2, suffix=" L/亩")),
        ("喷洒配比", str(spray_summary.get("dilution_ratio") or "-")),
        ("作业流量", format_number(spray_summary.get("spray_rate_lpm"), digits=1, suffix=" L/min")),
        ("飞行高度", format_number(spray_summary.get("flight_height_m"), digits=1, suffix=" m")),
    ]
    render_info_cards("作业指标", spray_items)
    render_operation_closure_panel(task)

    if boundary_svg:
        st.markdown(
            f"""
            <div class="muye-map-shell">
              <div class="muye-map-title">农田边界</div>
              {boundary_svg}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("当前任务还没有可视化的地块边界。")


def render_drone_command_panel(task: dict[str, Any] | None) -> None:
    drone = task.get("drone", {}) if task else {}
    if not drone:
        st.info("等待无人机任务状态。")
        return

    instruction = drone.get("instruction", {}) if isinstance(drone.get("instruction"), dict) else {}
    drone_timeline = task.get("drone_timeline", []) if task else []
    progress_value = max(0, min(100, int(drone.get("progress", 0) or 0)))
    current_status = str(drone.get("status") or "").lower()
    backend_key, backend_label = infer_drone_backend(drone, drone_timeline)
    route_points = instruction.get("飞行路径", []) if isinstance(instruction.get("飞行路径", []), list) else []
    coverage_points = instruction.get("覆盖区域", {}).get("coordinates", []) if isinstance(instruction.get("覆盖区域", {}), dict) else []
    route_svg = build_route_map_svg(instruction) if instruction else None
    last_stage_time = "-"
    if drone_timeline:
        last_stage_time = format_timestamp_display(drone_timeline[-1].get("timestamp"), include_date=True)

    st.markdown(
        f"""
        <div class="muye-command-shell">
          <div class="muye-command-top">
            <div>
              <div class="muye-command-kicker">Mission Command</div>
              <div class="muye-command-title">{html.escape(str(drone.get('message', '无人机任务执行中')))}</div>
              <div class="muye-command-subtitle">
                请求 {html.escape(str(task.get('request_id', '-'))[:8])}
                · 最近更新 {html.escape(last_stage_time)}
                · 当前阶段 {html.escape(DRONE_STAGE_LABELS.get(current_status, current_status or '-'))}
              </div>
            </div>
            <div class="muye-command-badge">{html.escape(backend_label)} · {progress_value}%</div>
          </div>
          <div class="muye-stage-row">
            {build_drone_stage_markup(drone_timeline, current_status, backend_key)}
          </div>
          <div class="muye-progress-track">
            <div class="muye-progress-fill" style="width:{progress_value}%;"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_info_cards(
        "任务遥测",
        [
            ("执行后端", backend_label),
            ("飞控任务号", str(drone.get("task_id", "-"))),
            ("当前航点", str(drone.get("current_waypoint_index", 0))),
            ("航点数量", str(len(route_points))),
            ("覆盖顶点", str(len(coverage_points))),
            ("飞行高度", f"{instruction.get('高度', '-')} m"),
            ("飞行速度", f"{instruction.get('速度', '-')} m/s"),
            ("喷洒速率", str(instruction.get("喷洒速率", "-"))),
        ],
    )

    if route_svg:
        map_cols = st.columns([1.2, 1])
        with map_cols[0]:
            st.markdown(
                f"""
                <div class="muye-map-shell">
                  <div class="muye-map-title">航线地图</div>
                  {route_svg}
                </div>
                """,
                unsafe_allow_html=True,
            )
        with map_cols[1]:
            st.markdown(
                f"""
                <div class="muye-telemetry">
当前航点: {html.escape(str(drone.get('current_waypoint_index', 0)))}
航点数量: {html.escape(str(len(route_points)))}
飞控任务号: {html.escape(str(drone.get('task_id', '-')))}
当前状态: {html.escape(DRONE_STAGE_LABELS.get(current_status, current_status or '-'))}
                </div>
                <div class="muye-telemetry-note">
                  航线围栏已与覆盖区域同步展示，适合在评审时解释喷洒边界、飞行路径和当前执行进度。
                </div>
                """,
                unsafe_allow_html=True,
            )


def weather_icon(summary: str) -> str:
    label = summary or ""
    if any(keyword in label for keyword in ["雨", "雪", "雷"]):
        return "🌧"
    if any(keyword in label for keyword in ["晴", "日"]):
        return "☀️"
    if any(keyword in label for keyword in ["阴", "云", "雾"]):
        return "☁️"
    return "🌿"


def build_route_map_svg(instruction: dict[str, Any]) -> str | None:
    flight_path = instruction.get("飞行路径", []) if isinstance(instruction, dict) else []
    coverage = (
        instruction.get("覆盖区域", {}).get("coordinates", [])
        if isinstance(instruction, dict)
        else []
    )
    points = [point for point in [*coverage, *flight_path] if isinstance(point, (list, tuple)) and len(point) == 2]
    if len(points) < 2:
        return None

    width = 520
    height = 250
    padding = 26
    lons = [float(point[0]) for point in points]
    lats = [float(point[1]) for point in points]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    lon_span = max(max_lon - min_lon, 1e-9)
    lat_span = max(max_lat - min_lat, 1e-9)

    def normalize(point: list[float] | tuple[float, float]) -> tuple[float, float]:
        lon, lat = float(point[0]), float(point[1])
        x = padding + ((lon - min_lon) / lon_span) * (width - padding * 2)
        y = height - padding - ((lat - min_lat) / lat_span) * (height - padding * 2)
        return round(x, 2), round(y, 2)

    normalized_flight = [normalize(point) for point in flight_path if isinstance(point, (list, tuple)) and len(point) == 2]
    normalized_coverage = [normalize(point) for point in coverage if isinstance(point, (list, tuple)) and len(point) == 2]

    if normalized_coverage and normalized_coverage[0] != normalized_coverage[-1]:
        normalized_coverage.append(normalized_coverage[0])

    coverage_points = " ".join(f"{x},{y}" for x, y in normalized_coverage)
    flight_points = " ".join(f"{x},{y}" for x, y in normalized_flight)

    waypoint_markup = []
    for index, (x, y) in enumerate(normalized_flight, start=1):
        waypoint_markup.append(
            f"""
            <circle cx="{x}" cy="{y}" r="8" fill="#ffffff" stroke="#0f766e" stroke-width="3" />
            <text x="{x}" y="{y + 4}" text-anchor="middle" font-size="10" font-weight="700" fill="#0f172a">{index}</text>
            """
        )

    return f"""
    <svg viewBox="0 0 {width} {height}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="routeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#22c55e" />
          <stop offset="100%" stop-color="#38bdf8" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="{width}" height="{height}" rx="20" fill="#f8fafc"/>
      <g opacity="0.32" stroke="#cbd5e1" stroke-width="1">
        <line x1="24" y1="60" x2="{width - 24}" y2="60" />
        <line x1="24" y1="125" x2="{width - 24}" y2="125" />
        <line x1="24" y1="190" x2="{width - 24}" y2="190" />
        <line x1="90" y1="24" x2="90" y2="{height - 24}" />
        <line x1="{width / 2}" y1="24" x2="{width / 2}" y2="{height - 24}" />
        <line x1="{width - 90}" y1="24" x2="{width - 90}" y2="{height - 24}" />
      </g>
      <text x="28" y="34" fill="#475569" font-size="12" font-weight="700">覆盖区域 / 飞行航线</text>
      <text x="{width - 34}" y="34" fill="#94a3b8" font-size="11" text-anchor="end">N</text>
      {'<polygon points="' + coverage_points + '" fill="rgba(34,197,94,0.16)" stroke="#22c55e" stroke-width="2" />' if coverage_points else ''}
      {'<polyline points="' + flight_points + '" fill="none" stroke="url(#routeGrad)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />' if flight_points else ''}
      {''.join(waypoint_markup)}
    </svg>
    """


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


def load_sqlite_task_views(
    *,
    limit: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        return store.fetch_task_views(limit=limit, status=status, search=search)
    finally:
        store.close()


def merge_sqlite_tasks_with_events(
    sqlite_tasks: list[dict[str, Any]],
    event_tasks: list[dict[str, Any]],
    *,
    include_event_only: bool = True,
) -> list[dict[str, Any]]:
    event_by_request = {str(task["request_id"]): task for task in event_tasks}
    merged: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()

    for sqlite_task in sqlite_tasks:
        request_id = str(sqlite_task["request_id"])
        event_task = event_by_request.get(request_id)
        merged_task = dict(sqlite_task)
        if event_task:
            merged_task["updated_at"] = event_task.get("updated_at") or sqlite_task.get("updated_at")
            merged_task["current_stage"] = event_task.get("current_stage") or sqlite_task.get("current_stage")
            merged_task["status"] = event_task.get("status") or sqlite_task.get("status")
            merged_task["message"] = event_task.get("message") or sqlite_task.get("message")
            merged_task["image_path"] = sqlite_task.get("image_path") or event_task.get("image_path")
            merged_task["field"] = sqlite_task.get("field") or event_task.get("field", {})
            merged_task["spray_summary"] = sqlite_task.get("spray_summary") or event_task.get("spray_summary", {})
            merged_task["detections"] = sqlite_task.get("detections") or event_task.get("detections", [])
            merged_task["weather"] = sqlite_task.get("weather") or event_task.get("weather", {})
            merged_task["decision"] = sqlite_task.get("decision") or event_task.get("decision", {})
            merged_task["drone"] = sqlite_task.get("drone") or event_task.get("drone", {})
            merged_task["drone_timeline"] = event_task.get("drone_timeline", [])
            merged_task["events"] = event_task.get("events", [])
            merged_task["error"] = event_task.get("error") or sqlite_task.get("error")
        seen_request_ids.add(request_id)
        merged.append(merged_task)

    if include_event_only:
        for event_task in event_tasks:
            request_id = str(event_task["request_id"])
            if request_id not in seen_request_ids:
                merged.append(event_task)

    merged.sort(
        key=lambda task: str(task.get("updated_at") or task.get("created_at") or ""),
        reverse=True,
    )
    return merged


def render_task_history(tasks: list[dict[str, Any]]) -> None:
    st.subheader("任务历史检索")
    if not tasks:
        st.info("当前筛选条件下暂无结构化任务记录。")
        return

    for task in tasks:
        detections = task.get("detections", [])
        pest_labels, pest_summary = summarize_pests(detections)
        weather = task.get("weather", {})
        decision = task.get("decision", {})
        medication = decision.get("用药", {}) if isinstance(decision, dict) else {}
        drone = task.get("drone", {})
        spray_summary = task.get("spray_summary", {})
        outcome = infer_operation_outcome(task)
        updated_at = str(task.get("updated_at") or task.get("created_at") or "-")
        updated_display = updated_at.replace("T", " ")[:19] if updated_at != "-" else "-"
        pills: list[str] = [
            f'<span class="muye-pill">{html.escape(str(task.get("status", "-")))}</span>',
            f'<span class="muye-pill" style="background:rgba(34,197,94,0.12);color:#166534;border-color:rgba(34,197,94,0.18);">{html.escape(str(task.get("current_stage", "-")))}</span>',
            f'<span class="muye-pill" style="background:rgba(15,23,42,0.06);color:#0f172a;border-color:rgba(148,163,184,0.22);">{html.escape(outcome["result_label"])}</span>',
        ]
        for label in pest_labels[:3]:
            pills.append(
                f'<span class="muye-pill" style="background:rgba(14,165,233,0.10);color:#0f766e;border-color:rgba(56,189,248,0.22);">{html.escape(label)}</span>'
            )

        summary_items = [
            ("请求号", str(task.get("request_id", "-"))[:8]),
            ("最近更新", updated_display),
            ("害虫摘要", pest_summary),
            ("天气", str(weather.get("summary", "-")) if weather else "-"),
            ("建议农药", str(medication.get("农药名称", "-")) if medication else "-"),
            ("作业面积", format_number(spray_summary.get("spray_area_mu"), digits=1, suffix=" 亩")),
        ]
        content = "".join(
            f"""
            <div class="muye-card">
              <div class="muye-card-label">{html.escape(label)}</div>
              <div class="muye-card-value">{html.escape(value)}</div>
            </div>
            """
            for label, value in summary_items
        )
        st.markdown(
            f"""
            <div class="muye-card-wrap" style="margin-bottom:0.9rem;">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap;">
                <div>
                  <div style="font-size:1.02rem;font-weight:700;color:#17372a;">任务 {html.escape(str(task.get("request_id", "-"))[:8])}</div>
                  <div style="font-size:0.86rem;color:#4b5563;margin-top:0.2rem;">{html.escape(str(task.get("message", "-")))}</div>
                </div>
                <div class="muye-pill-wrap" style="margin-top:0;">{''.join(pills)}</div>
              </div>
              <div class="muye-card-grid" style="margin-top:0.9rem;">{content}</div>
              <div class="muye-history-meta">
                {build_history_detail_markup(task)}
              </div>
              <div style="margin-top:0.8rem;color:#4b5563;font-size:0.9rem;line-height:1.55;">
                <strong style="color:#17372a;">执行路径：</strong>{html.escape(build_history_timeline_text(task))}
              </div>
              <div style="margin-top:0.45rem;color:#4b5563;font-size:0.9rem;line-height:1.55;">
                <strong style="color:#17372a;">任务结论：</strong>{html.escape(outcome["verdict"])}
              </div>
              {
                '<div class="muye-alert-box"><div class="muye-alert-title">异常原因</div><div style="font-size:0.92rem;line-height:1.55;">'
                + html.escape(str(task.get("error") or "-"))
                + '</div></div>'
                if task.get("error") else ''
              }
              {
                '<div style="margin-top:0.8rem;color:#4b5563;font-size:0.9rem;line-height:1.55;"><strong style="color:#17372a;">无人机状态：</strong>'
                + html.escape(str(drone.get("message", "-")) if drone else "-")
                + '</div>'
                if drone else ''
              }
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard() -> None:
    events = load_events(limit=500)
    event_tasks = build_task_views(events)
    tasks = merge_sqlite_tasks_with_events(
        load_sqlite_task_views(limit=80),
        event_tasks,
    )
    latest_task = tasks[0] if tasks else None
    history_status = st.session_state.get("history_status", "all")
    history_search = st.session_state.get("history_search", "").strip()
    history_limit = int(st.session_state.get("history_limit", 12))
    history_tasks = merge_sqlite_tasks_with_events(
        load_sqlite_task_views(
            limit=history_limit,
            status=None if history_status == "all" else history_status,
            search=history_search or None,
        ),
        event_tasks,
        include_event_only=False,
    )

    inject_styles()
    render_hero(latest_task, len(events))

    summary_cols = st.columns(4)
    summary_cols[0].metric("当前请求", latest_task["request_id"][:8] if latest_task else "-")
    summary_cols[1].metric("当前阶段", latest_task["current_stage"] if latest_task else "waiting")
    summary_cols[2].metric("任务状态", latest_task["status"] if latest_task else "idle")
    summary_cols[3].metric("总事件数", len(events))

    latest_uploaded_path = st.session_state.get("latest_uploaded_path")
    original_image_path = latest_task["image_path"] if latest_task and latest_task.get("image_path") else latest_uploaded_path
    detections = latest_task.get("detections", []) if latest_task else []
    pest_labels, pest_summary = summarize_pests(detections)

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

    st.subheader("害虫识别摘要")
    pest_cols = st.columns(2)
    pest_cols[0].metric("识别害虫种类", str(len(pest_labels)))
    pest_cols[1].metric("识别目标总数", str(len(detections)))
    if pest_labels:
        pills = "".join(
            f'<span class="muye-pill" style="background:rgba(34,197,94,0.12);color:#166534;border-color:rgba(34,197,94,0.18);">{html.escape(label)}</span>'
            for label in pest_labels
        )
        st.markdown(
            f"""
            <div class="muye-pest-banner">
              <div style="font-size:0.86rem;color:#166534;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.45rem;">识别结果</div>
              <div style="font-size:1.08rem;font-weight:700;color:#14532d;">{html.escape(pest_summary)}</div>
              <div class="muye-pill-wrap">{pills}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("等待 YOLO 返回害虫名称。")

    st.subheader("作业地块")
    field_cols = st.columns([1, 1.15])
    with field_cols[0]:
        render_field_operations_panel(latest_task)
    with field_cols[1]:
        render_drone_command_panel(latest_task)

    section_cols = st.columns(2)
    with section_cols[0]:
        st.subheader("天气信息")
        weather = latest_task.get("weather", {}) if latest_task else {}
        if weather:
            icon = weather_icon(str(weather.get("summary", "")))
            st.markdown(
                f"""
                <div class="muye-card-wrap" style="margin-bottom:0.85rem;">
                  <div class="muye-weather-main">
                    <div class="muye-weather-icon">{icon}</div>
                    <div>
                      <div class="muye-weather-temp">{html.escape(str(weather.get("temperature", "-")))}°C</div>
                      <div class="muye-weather-text">{html.escape(str(weather.get("summary", "-")))}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_info_cards(
                "天气信息",
                [
                    ("温度", f"{weather.get('temperature', '-')} ℃"),
                    ("湿度", f"{weather.get('humidity', '-')} %"),
                    ("风向", str(weather.get("wind_direction", "-"))),
                    ("风力", str(weather.get("wind_scale_text", "-"))),
                    ("风速上限", f"{weather.get('wind_speed', '-')} m/s"),
                ],
            )
        else:
            st.info("等待后端获取天气信息。")

    with section_cols[1]:
        st.subheader("千问建议")
        decision = latest_task.get("decision", {}) if latest_task else {}
        medication = decision.get("用药", {})
        agronomy_tips = decision.get("农事建议", []) if isinstance(decision, dict) else []
        instruction = (latest_task.get("drone", {}) if latest_task else {}).get("instruction", {})
        if decision:
            st.markdown(
                f"""
                <div class="muye-card-wrap">
                  <h3 style="margin:0 0 0.65rem;color:#17372a;">决策摘要</h3>
                  <div class="muye-highlight-grid">
                    <div class="muye-highlight-card">
                      <div class="muye-card-label">农药名称</div>
                      <div class="muye-card-value">{html.escape(str(medication.get("农药名称", "-")))}</div>
                    </div>
                    <div class="muye-highlight-card">
                      <div class="muye-card-label">浓度</div>
                      <div class="muye-card-value">{html.escape(str(medication.get("浓度", "-")))}</div>
                    </div>
                    <div class="muye-highlight-card">
                      <div class="muye-card-label">配比</div>
                      <div class="muye-card-value">{html.escape(str(medication.get("配比", "-")))}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_info_cards(
                "系统规划参数",
                [
                    ("总量", str(medication.get("总量", "-"))),
                    ("飞行高度", f"{instruction.get('高度', '-')} m"),
                    ("飞行速度", f"{instruction.get('速度', '-')} m/s"),
                    ("喷洒速率", str(instruction.get("喷洒速率", "-"))),
                ],
            )
            safety_tips = medication.get("安全提示", [])
            if safety_tips:
                pills = "".join(
                    f'<span class="muye-pill" style="background:#fff7ed;color:#9a3412;border-color:rgba(251,146,60,0.24);">{html.escape(str(item))}</span>'
                    for item in safety_tips
                )
                st.markdown(
                    f"""
                    <div class="muye-safety-box">
                      <h3 style="margin:0;color:#17372a;">安全提示</h3>
                      <div class="muye-pill-wrap">{pills}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if agronomy_tips:
                tips = "".join(
                    f'<span class="muye-pill" style="background:rgba(14,165,233,0.10);color:#0f766e;border-color:rgba(56,189,248,0.22);">{html.escape(str(item))}</span>'
                    for item in agronomy_tips
                )
                st.markdown(
                    f"""
                    <div class="muye-safety-box">
                      <h3 style="margin:0;color:#17372a;">农事建议</h3>
                      <div class="muye-pill-wrap">{tips}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with st.expander("查看完整决策 JSON"):
                st.json(decision)
        else:
            st.info("等待千问生成决策。")

    st.subheader("实时事件日志")
    render_log_box(latest_task["events"] if latest_task else events)
    render_task_history(history_tasks)


def sidebar_controls() -> None:
    with st.sidebar:
        modes = current_mode_labels()
        st.header("运行模式")
        st.markdown(
            f"""
            <div class="muye-mode-row">
              <div class="muye-mode-pill">
                <div class="muye-mode-label">YOLO</div>
                <div class="muye-mode-value {modes['yolo']}">{modes['yolo']}</div>
              </div>
              <div class="muye-mode-pill">
                <div class="muye-mode-label">天气</div>
                <div class="muye-mode-value {modes['weather']}">{modes['weather']}</div>
              </div>
              <div class="muye-mode-pill">
                <div class="muye-mode-label">千问</div>
                <div class="muye-mode-value {modes['qwen']}">{modes['qwen']}</div>
              </div>
              <div class="muye-mode-pill">
                <div class="muye-mode-label">无人机</div>
                <div class="muye-mode-value {modes['drone']}">{modes['drone']}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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

        st.header("历史检索")
        st.selectbox(
            "任务状态",
            options=["all", "queued", "running", "completed", "error"],
            index=0,
            key="history_status",
        )
        st.text_input(
            "结构化检索",
            key="history_search",
            placeholder="request_id / 图片路径 / 害虫类型",
        )
        st.slider(
            "历史任务数",
            min_value=5,
            max_value=30,
            value=12,
            step=1,
            key="history_limit",
        )


def main() -> None:
    st.set_page_config(page_title="牧野演示面板", layout="wide")
    st_autorefresh(interval=1500, key="muye-dashboard-refresh")
    ensure_runtime_dirs()
    sidebar_controls()
    render_dashboard()


if __name__ == "__main__":
    main()
