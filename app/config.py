"""Load environment variables before any ML model imports."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Ensure HF mirror/endpoint is set before huggingface_hub is used.
if endpoint := os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = endpoint

# XET storage uses cas-server.xethub.hf.co and fails (401) behind HF mirrors.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# Pipeline: "sdxl" (~16 GB, no ControlNet) or "controlnet" (~20 GB, better text/faces).
PIPELINE = os.environ.get("PIPELINE", "sdxl").strip().lower()
if PIPELINE not in {"sdxl", "controlnet"}:
    PIPELINE = "sdxl"
os.environ["PIPELINE"] = PIPELINE
