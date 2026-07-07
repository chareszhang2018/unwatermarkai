"""FastAPI application for SynthID removal web service."""

from __future__ import annotations

import app.config  # noqa: F401  # load .env before ML imports

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import engine, jobs

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="SynthID Remover", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    import os

    gpu_ok = engine.gpu_available()
    return {
        "status": "ok",
        "gpu_available": gpu_ok,
        "device": engine.detect_device(),
        "model_loaded": engine.is_model_loaded(),
        "pipeline": os.environ.get("PIPELINE", "sdxl"),
        "hf_endpoint": os.environ.get("HF_ENDPOINT", "https://huggingface.co"),
    }


@app.post("/api/remove-synthid")
async def remove_synthid(file: UploadFile = File(...)) -> dict:
    if not engine.gpu_available():
        raise HTTPException(
            status_code=503,
            detail="GPU 依赖未安装。请运行: pip install 'remove-ai-watermarks[gpu]'",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    content = await file.read()
    try:
        job = jobs.create_job(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return jobs.job_to_dict(job)


@app.get("/api/jobs/{job_id}/download")
def download_result(job_id: str) -> FileResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status != "done" or job.output_path is None or not job.output_path.exists():
        raise HTTPException(status_code=404, detail="结果尚未就绪")

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    ext = job.output_path.suffix.lower()
    media_type = media_types.get(ext, "application/octet-stream")

    stem = Path(job.input_name).stem
    download_name = f"{stem}_clean{ext}"

    return FileResponse(
        path=job.output_path,
        media_type=media_type,
        filename=download_name,
    )
