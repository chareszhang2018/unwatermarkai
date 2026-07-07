#!/usr/bin/env bash
# Pre-download SDXL models via HuggingFace mirror.
# Set PIPELINE=controlnet in .env to also fetch the ControlNet weights (~5 GB extra).
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PIPELINE="${PIPELINE:-sdxl}"
echo "HF_ENDPOINT=${HF_ENDPOINT:-https://huggingface.co}"
# XET downloads hit cas-server.xethub.hf.co and fail (401) behind HF mirrors.
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
echo "HF_HUB_DISABLE_XET=${HF_HUB_DISABLE_XET}"
echo "PIPELINE=${PIPELINE}"
if [ "$PIPELINE" = "controlnet" ]; then
  echo "Downloading models (SDXL + ControlNet, about 17 GB, may take a while)..."
else
  echo "Downloading models (SDXL only, about 13 GB, may take a while)..."
fi

python3 <<'PY'
import os
from huggingface_hub import snapshot_download

endpoint = os.environ.get("HF_ENDPOINT", "")
if endpoint:
    print(f"Using mirror: {endpoint}")

pipeline = os.environ.get("PIPELINE", "sdxl").strip().lower()
if pipeline not in {"sdxl", "controlnet"}:
    pipeline = "sdxl"
print(f"Pipeline: {pipeline}")

token = os.environ.get("HF_TOKEN") or None
if token:
    print("Using HF_TOKEN for authenticated download")

# The Hub repo lists ~72 GB across 57 files (ONNX/Flax/OpenVINO/fp16 duplicates).
# Diffusers on MPS only needs the fp32 PyTorch layout (~13 GB).
SDXL_IGNORE = [
    "*.onnx",
    "*.onnx_data",
    "*openvino*",
    "*flax*",
    "*.msgpack",
    "*.ckpt",
    "*.bin",
    "sd_xl_base_1.0*.safetensors",
    "*.fp16.safetensors",
]

models = [
    ("stabilityai/stable-diffusion-xl-base-1.0", SDXL_IGNORE),
]
if pipeline == "controlnet":
    models.append(("xinsir/controlnet-canny-sdxl-1.0", ["*.fp16.safetensors"]))

for model, ignore in models:
    print(f"\n>>> Downloading {model} (essential files only) ...")
    snapshot_download(model, token=token, ignore_patterns=ignore)
    print(f"    Done: {model}")

print("\nAll models downloaded.")
PY
