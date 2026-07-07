"""In-memory job queue and background processing for SynthID removal."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from app.engine import remove_synthid, set_progress_callback

JobStatus = Literal["queued", "processing", "done", "error"]

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
JOB_RETENTION = timedelta(hours=1)


@dataclass
class Job:
    id: str
    status: JobStatus
    message: str
    input_name: str
    input_path: Path
    output_path: Path | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_worker_lock = threading.Lock()


def _ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_jobs() -> None:
    cutoff = datetime.now() - JOB_RETENTION
    with _jobs_lock:
        expired = [jid for jid, job in _jobs.items() if job.created_at < cutoff]
        for jid in expired:
            job = _jobs.pop(jid)
            for path in (job.input_path, job.output_path):
                if path and path.exists():
                    path.unlink(missing_ok=True)


def create_job(filename: str, content: bytes) -> Job:
    _ensure_dirs()
    _cleanup_old_jobs()

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大，最大 {MAX_FILE_SIZE // (1024 * 1024)} MB")

    job_id = uuid.uuid4().hex
    input_path = UPLOADS_DIR / f"{job_id}{ext}"
    input_path.write_bytes(content)

    job = Job(
        id=job_id,
        status="queued",
        message="排队中…",
        input_name=filename,
        input_path=input_path,
    )

    with _jobs_lock:
        _jobs[job_id] = job

    threading.Thread(target=_process_queue, daemon=True).start()
    return job


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs: object) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        for key, value in kwargs.items():
            setattr(job, key, value)


def _process_queue() -> None:
    if not _worker_lock.acquire(blocking=False):
        return

    try:
        while True:
            job_id = None
            with _jobs_lock:
                for jid, job in _jobs.items():
                    if job.status == "queued":
                        job_id = jid
                        job.status = "processing"
                        job.message = "正在处理…"
                        break

            if job_id is None:
                break

            _run_job(job_id)
    finally:
        _worker_lock.release()


def _run_job(job_id: str) -> None:
    job = get_job(job_id)
    if job is None:
        return

    ext = job.input_path.suffix
    output_path = OUTPUTS_DIR / f"{job_id}{ext}"

    def on_progress(message: str) -> None:
        _update_job(job_id, message=message)

    set_progress_callback(on_progress)

    try:
        _update_job(job_id, message="正在加载模型…")
        result = remove_synthid(job.input_path, output_path)
        _update_job(
            job_id,
            status="done",
            message="处理完成",
            output_path=result,
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="error",
            message="处理失败",
            error=str(exc),
        )
        if output_path.exists():
            output_path.unlink(missing_ok=True)
    finally:
        set_progress_callback(None)
        if job.input_path.exists():
            job.input_path.unlink(missing_ok=True)


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "message": job.message,
        "input_name": job.input_name,
        "error": job.error,
        "download_ready": job.status == "done" and job.output_path is not None,
    }
