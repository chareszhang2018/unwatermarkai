"""InvisibleEngine singleton wrapper for SynthID removal."""

from __future__ import annotations

import app.config  # noqa: F401  # load .env before ML imports

import threading
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

import os

from app.config import PIPELINE
from remove_ai_watermarks.invisible_engine import InvisibleEngine, is_available

# Cap long side during diffusion to avoid OOM on 16GB Macs (0 = native, no cap).
MAX_RESOLUTION = int(os.environ.get("MAX_RESOLUTION", "1024"))

_engine: InvisibleEngine | None = None
_engine_lock = threading.Lock()
_progress_callback: Callable[[str], None] | None = None


def set_progress_callback(callback: Callable[[str], None] | None) -> None:
    """Set a callback invoked with progress messages during processing."""
    global _progress_callback
    _progress_callback = callback


def _on_progress(message: str) -> None:
    if _progress_callback is not None:
        _progress_callback(message)


def get_engine() -> InvisibleEngine:
    """Return the shared InvisibleEngine instance, creating it on first use."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = InvisibleEngine(
                pipeline=PIPELINE,
                device=None,
                progress_callback=_on_progress,
            )
            _engine.preload()
        return _engine


def gpu_available() -> bool:
    return is_available()


def is_model_loaded() -> bool:
    return _engine is not None


def detect_device() -> str:
    """Detect compute device without loading the diffusion model."""
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def get_device() -> str:
    """Return the device string used by the engine (mps/cuda/cpu)."""
    if _engine is not None:
        return _engine._remover.device  # noqa: SLF001
    return detect_device()


def remove_synthid(input_path: Path, output_path: Path) -> Path:
    """Run SynthID removal on an image file."""
    engine = get_engine()

    with Image.open(input_path) as img:
        img = ImageOps.exif_transpose(img)
        long_side = max(img.size)

    use_tile = long_side > 1024 or (MAX_RESOLUTION > 0 and long_side > MAX_RESOLUTION)

    return engine.remove_watermark(
        image_path=input_path,
        output_path=output_path,
        strength=None,
        num_inference_steps=50,
        guidance_scale=None,
        adaptive_polish=True,
        min_resolution=1024,
        max_resolution=MAX_RESOLUTION,
        tile=use_tile,
        tile_size=1024,
        tile_overlap=128,
    )
