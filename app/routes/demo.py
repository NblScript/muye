"""Demo endpoints for image upload and reset."""

import io
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from modules.infra.common import IMAGES_DIR, ensure_runtime_dirs
import modules.infra.event_bus as event_bus
import app.services.workflow_service as workflow_service


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _save_uploaded_image(file, content: bytes) -> Path:
    """Save uploaded image to disk."""
    ensure_runtime_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = workflow_service.sanitize_filename(file.filename)
    target = IMAGES_DIR / f"{timestamp}-{filename}"
    target.write_bytes(content)
    return target


async def upload_demo_image(file: UploadFile = File(...)) -> dict[str, str]:
    """Demo image upload endpoint handler."""
    # Check for monkeypatched _save_uploaded_image in this module
    import app.routes.demo as demo_module
    saver = getattr(demo_module, "_save_uploaded_image", _save_uploaded_image)

    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="unsupported_file_type")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="invalid_image_content") from exc

    target = saver(file, content)
    return {
        "filename": target.name,
        "path": str(target),
    }


async def reset_demo_events(confirm: bool = False) -> dict[str, str]:
    """Demo reset events endpoint handler."""
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm_required")

    workflow_service.clear_demo_runtime_state()
    event_bus.FileEventBus().clear()
    return {"status": "cleared"}


def register_demo_routes(app: FastAPI) -> None:
    """Register demo routes."""
    app.post("/demo/upload-image")(upload_demo_image)
    app.post("/api/demo/upload-image", include_in_schema=False)(upload_demo_image)
    app.post("/demo/reset-events")(reset_demo_events)
    app.post("/api/demo/reset-events", include_in_schema=False)(reset_demo_events)
