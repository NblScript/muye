"""Task endpoints for retrieving task images."""

import io
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageDraw

from services.workflow_service import image_media_type, load_task_by_request_id as _original_load_task


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


def _get_annotate_fn():
    """Get the annotate function, checking for monkeypatching."""
    main_module = sys.modules.get("main")
    if main_module is not None:
        patched = getattr(main_module, "_annotate_image", None)
        if patched is not None:
            return patched
    return annotate_image


def _get_loader():
    """Get the task loader function, checking for monkeypatching."""
    # Check if main module has a monkeypatched version
    main_module = sys.modules.get("main")
    if main_module is not None:
        patched = getattr(main_module, "_load_task_by_request_id", None)
        if patched is not None and patched is not _original_load_task:
            return patched
    return _original_load_task


async def get_task_original_image(request_id: str) -> FileResponse:
    """Get original task image endpoint handler."""
    loader = _get_loader()
    task = loader(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    image_path = Path(str(task["image_path"]))
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="image_file_not_found")

    return FileResponse(image_path, media_type=image_media_type(image_path))


async def get_task_annotated_image(request_id: str) -> StreamingResponse:
    """Get annotated task image endpoint handler."""
    loader = _get_loader()
    task = loader(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    annotate_fn = _get_annotate_fn()
    annotated = annotate_fn(str(task["image_path"]), task.get("detections", []) or [])
    if annotated is None:
        raise HTTPException(status_code=404, detail="annotated_image_not_found")

    buffer = io.BytesIO()
    annotated.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


def register_tasks_routes(app: FastAPI) -> None:
    """Register tasks routes."""
    app.get("/tasks/{request_id}/original-image")(get_task_original_image)
    app.get("/api/tasks/{request_id}/original-image", include_in_schema=False)(get_task_original_image)
    app.get("/tasks/{request_id}/annotated-image")(get_task_annotated_image)
    app.get("/api/tasks/{request_id}/annotated-image", include_in_schema=False)(get_task_annotated_image)
