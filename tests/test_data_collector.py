"""Smoke tests for modules/detection/data_collector.py"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from modules.detection.data_collector import (
    CollectorError,
    DataCollectorService,
    MINIMAL_JPEG,
)


@pytest.fixture
def images_dir(tmp_path: Path) -> Path:
    d = tmp_path / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def drone_config() -> dict:
    return {
        "monitoring": {
            "capture_interval_hours": 1,
            "capture_on_startup": False,
            "simulate_capture": True,
        },
        "execution": {"request_timeout_seconds": 5},
        "network": {"client_ip": "127.0.0.1"},
    }


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.collector")


@pytest.mark.asyncio
async def test_data_collector_service_initializes(
    images_dir: Path,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Test that DataCollectorService can be instantiated."""
    captured_images: list[Path] = []

    async def on_new_image(path: Path) -> None:
        captured_images.append(path)

    service = DataCollectorService(
        images_dir=images_dir,
        drone_config=drone_config,
        on_new_image=on_new_image,
        logger=logger,
    )

    assert service.images_dir == images_dir
    assert service.simulate_capture is True


@pytest.mark.asyncio
async def test_data_collector_capture_simulated_image(
    images_dir: Path,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Test simulated image capture creates a JPEG file."""
    captured_images: list[Path] = []

    async def on_new_image(path: Path) -> None:
        captured_images.append(path)

    service = DataCollectorService(
        images_dir=images_dir,
        drone_config=drone_config,
        on_new_image=on_new_image,
        logger=logger,
    )

    result = await service.capture_image()
    assert result.exists()
    assert result.suffix == ".jpg"
    assert result.read_bytes() == MINIMAL_JPEG
    assert len(captured_images) == 1
    assert captured_images[0] == result


@pytest.mark.asyncio
async def test_data_collector_start_and_shutdown(
    images_dir: Path,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Test service can start and shutdown cleanly."""
    captured_images: list[Path] = []

    async def on_new_image(path: Path) -> None:
        captured_images.append(path)

    service = DataCollectorService(
        images_dir=images_dir,
        drone_config=drone_config,
        on_new_image=on_new_image,
        logger=logger,
    )

    await service.start(enable_scheduler=False, capture_on_startup=False)
    await service.shutdown()


@pytest.mark.asyncio
async def test_data_collector_capture_creates_directory(
    tmp_path: Path,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Test that capture creates the images directory if it doesn't exist."""
    images_dir = tmp_path / "nonexistent" / "images"
    assert not images_dir.exists()

    captured_images: list[Path] = []

    async def on_new_image(path: Path) -> None:
        captured_images.append(path)

    service = DataCollectorService(
        images_dir=images_dir,
        drone_config=drone_config,
        on_new_image=on_new_image,
        logger=logger,
    )

    result = await service.capture_image()
    assert images_dir.exists()
    assert result.parent == images_dir
