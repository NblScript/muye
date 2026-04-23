"""Demo endpoints for image upload and reset."""

import io
import sys
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from modules.infra.common import IMAGES_DIR, ensure_runtime_dirs
from modules.infra.event_bus import FileEventBus as _OriginalEventBus
from app.services.workflow_service import clear_demo_runtime_state as _original_clear_demo, sanitize_filename


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _get_main_module():
    return (
        sys.modules.get("app.main")
        or sys.modules.get("main")
        or sys.modules.get("__main__")
    )


def _get_event_bus():
    """Get the event bus class, checking for monkeypatching."""
    main_module = _get_main_module()
    if main_module is not None:
        patched = getattr(main_module, "FileEventBus", None)
        if patched is not None:
            return patched
    return _OriginalEventBus


def _get_clear_demo_state():
    """Get the clear demo state function, checking for monkeypatching."""
    main_module = _get_main_module()
    if main_module is not None:
        patched = getattr(main_module, "_clear_demo_runtime_state", None)
        if patched is not None:
            return patched
    return _original_clear_demo


def _save_uploaded_image(file, content: bytes) -> Path:
    """Save uploaded image to disk."""
    ensure_runtime_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = sanitize_filename(file.filename)
    target = IMAGES_DIR / f"{timestamp}-{filename}"
    target.write_bytes(content)
    return target


async def upload_demo_image(file: UploadFile = File(...)) -> dict[str, str]:
    """Demo image upload endpoint handler."""
    # Check for monkeypatched _save_uploaded_image
    main_module = _get_main_module()
    saver = _save_uploaded_image
    if main_module is not None:
        patched_saver = getattr(main_module, "_save_uploaded_image", None)
        if patched_saver is not None:
            saver = patched_saver

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

    clear_fn = _get_clear_demo_state()
    clear_fn()
    FileEventBusClass = _get_event_bus()
    FileEventBusClass().clear()
    return {"status": "cleared"}


def register_demo_routes(app: FastAPI) -> None:
    """Register demo routes."""
    app.post("/demo/upload-image")(upload_demo_image)
    app.post("/api/demo/upload-image", include_in_schema=False)(upload_demo_image)
    app.post("/demo/reset-events")(reset_demo_events)
    app.post("/api/demo/reset-events", include_in_schema=False)(reset_demo_events)
