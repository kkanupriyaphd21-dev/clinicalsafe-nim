"""CSR async pipeline routes."""
import logging
import os
import pickle
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.api.csr_docx_builder import (
    build_csr_docx,
    build_csr_qc_report_docx,
    build_csr_audit_log,
)
from src.data_processing.csr_parser import CSRParser
from src.models.database import get_db, SessionLocal
from src.models.schemas import CSRProgress, CSRTaskResponse
from src.services.csr_synthesizer import CSRNIMSynthesizer, CSRSummaryResult
from src.services.csr_quality_checks import run_quality_checks

import asyncio
import json
from src.models.database import get_db, SessionLocal, CSRTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/csr", tags=["CSR Pipeline"])

CSR_CACHE_DIR = Path(tempfile.gettempdir()) / "clinicalsafe_nim_csr_cache"
CSR_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ProgressTracker:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "processing"
        self.stage = "queued"
        self.current = 0
        self.total = 0
        self.message = "Queued…"
        self.start_time = time.time()
        self.result_data = None
        self.error = None
        self._write_to_db()

    def _write_to_db(self):
        elapsed = time.time() - self.start_time
        progress = self.current / max(self.total, 1) if self.total > 0 else 0
        eta = round((elapsed / max(progress, 0.001)) * max(1 - progress, 0), 1) if progress > 0 else 0
        
        with SessionLocal() as db:
            task = db.query(CSRTask).filter(CSRTask.id == self.task_id).first()
            if not task:
                task = CSRTask(id=self.task_id)
                db.add(task)
            
            task.status = self.status
            task.stage = self.stage
            task.progress = round(min(progress, 1.0), 4)
            task.current = self.current
            task.total = self.total
            task.message = self.message
            task.elapsed_seconds = round(elapsed, 1)
            task.eta_seconds = eta
            
            if self.status == "complete" and self.result_data:
                task.result_data = json.dumps(self.result_data)
            if self.error:
                task.error_message = self.error
                
            db.commit()

    def update(self, stage: str, current: int, total: int, message: str):
        self.stage = stage
        self.current = current
        self.total = total
        self.message = message
        self._write_to_db()

    def succeed(self, result_data: dict):
        self.status = "complete"
        self.stage = "complete"
        self.current = self.total or 1
        self.total = self.total or 1
        self.message = "Complete"
        self.result_data = result_data
        self._write_to_db()

    def fail(self, error: str):
        self.status = "error"
        self.stage = "error"
        self.message = error
        self.error = error
        self._write_to_db()

    def to_dict(self) -> Dict:
        elapsed = time.time() - self.start_time
        progress = self.current / max(self.total, 1) if self.total > 0 else 0
        eta = round((elapsed / max(progress, 0.001)) * max(1 - progress, 0), 1) if progress > 0 else 0
        d: Dict = {
            "status": self.status,
            "stage": self.stage,
            "progress": round(min(progress, 1.0), 4),
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": eta,
        }
        if self.status == "complete" and self.result_data:
            d["result"] = self.result_data
        if self.error:
            d["error"] = self.error
        return d


def _clean_csr_cache(max_age_hours: int = 2):
    now = time.time()
    for f in CSR_CACHE_DIR.iterdir():
        if f.is_file() and now - f.stat().st_mtime > max_age_hours * 3600:
            f.unlink()


_clean_csr_cache()


def _save_csr_cache(summary: CSRSummaryResult) -> str:
    token = uuid.uuid4().hex[:16]
    path = CSR_CACHE_DIR / f"{token}.pkl"
    with open(path, "wb") as f:
        pickle.dump(summary, f)
    return token


def _load_csr_cache(token: str):
    path = CSR_CACHE_DIR / f"{token}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _make_progress_callback(tracker: ProgressTracker):
    def cb(stage, current, total, message):
        tracker.update(stage, current, total, message)
    return cb


@router.post("", response_model=CSRTaskResponse)
async def start_csr(
    file: UploadFile = File(...),
    model: str = Form("meta/llama-3.3-70b-instruct"),
    max_workers: int = Form(5),
    max_tokens: int = Form(1024),
    temperature: float = Form(0.0),
    db: Session = Depends(get_db),
):
    content_type = file.content_type or ""
    filename = file.filename or "csr_upload"
    suffix = Path(filename).suffix.lower()

    if suffix != ".pdf" and content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="CSR endpoint only accepts PDF files")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    task_id = uuid.uuid4().hex[:16]
    tracker = ProgressTracker(task_id)
    tracker.update("parsing", 0, 0, "Queued — waiting for background thread…")

    with _csr_tasks_lock:
        _csr_tasks[task_id] = tracker

    def _run_bg():
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            tracker.update("parsing", 0, 0, "Parsing PDF and detecting sections…")
            parser = CSRParser(tmp_path, use_gpu_ocr=False)
            doc = parser.parse()

            total_tables_all = sum(len(s.tables) for s in doc.sections)
            tracker.update("parsing", 0, total_tables_all, f"Found {len(doc.sections)} sections, {total_tables_all} tables")

            synthesizer = CSRNIMSynthesizer(
                session_factory=SessionLocal,
                model=model,
                max_workers=max_workers,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            summary = synthesizer.summarize_document(
                doc,
                progress_callback=_make_progress_callback(tracker),
            )

            total_ms = round((time.time() - tracker.start_time) * 1000, 2)
            download_token = _save_csr_cache(summary)

            quality_report = run_quality_checks(summary)

            result = {
                "filename": summary.filename,
                "total_pages": summary.total_pages,
                "total_tables": summary.total_tables,
                "verified_tables": summary.verified_tables,
                "overall_numeric_accuracy": summary.overall_numeric_accuracy,
                "consistency_warnings": summary.consistency_warnings,
                "errors": summary.errors,
                "total_inference_time_ms": total_ms,
                "document_synthesis": summary.document_synthesis,
                "sections": [s.to_dict() for s in summary.sections],
                "download_token": download_token,
                "quality_report": quality_report.to_dict(),
            }
            tracker.succeed(result)
        except Exception as e:
            logger.exception("csr background processing failed")
            tracker.fail(str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    t = threading.Thread(target=_run_bg, daemon=True)
    t.start()

    return CSRTaskResponse(
        task_id=task_id,
        status="processing",
        message="CSR NIM processing started. Poll GET /csr/progress/{task_id} for updates.",
    )


@router.get("/progress/{task_id}")
async def get_csr_progress(task_id: str, db: Session = Depends(get_db)):
    task = db.query(CSRTask).filter(CSRTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found or already expired")
    
    result = {
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "current": task.current,
        "total": task.total,
        "message": task.message,
        "elapsed_seconds": task.elapsed_seconds,
        "eta_seconds": task.eta_seconds,
    }
    if task.result_data:
        result["result"] = json.loads(task.result_data)
    if task.error_message:
        result["error"] = task.error_message
    return result


@router.get("/download/{token}")
async def download_csr_docx(token: str):
    summary = await asyncio.to_thread(_load_csr_cache, token)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="CSR result not found or expired. Please re-upload the PDF.",
        )
    docx_bytes = await asyncio.to_thread(build_csr_docx, summary)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="csr-nim-{int(time.time())}.docx"',
            "X-Verified-Tables": str(summary.verified_tables),
            "X-Total-Tables": str(summary.total_tables),
            "X-Consistency-Warnings": str(len(summary.consistency_warnings)),
        },
    )


@router.get("/download/{token}/qc")
async def download_csr_qc_report(token: str):
    summary = await asyncio.to_thread(_load_csr_cache, token)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="CSR result not found or expired. Please re-upload the PDF.",
        )
    docx_bytes = await asyncio.to_thread(build_csr_qc_report_docx, summary)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="csr-nim-qc-{int(time.time())}.docx"',
            "X-Verified-Tables": str(summary.verified_tables),
            "X-Total-Tables": str(summary.total_tables),
            "X-Consistency-Warnings": str(len(summary.consistency_warnings)),
        },
    )


@router.get("/download/{token}/audit")
async def download_csr_audit_log(token: str):
    summary = await asyncio.to_thread(_load_csr_cache, token)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="CSR result not found or expired. Please re-upload the PDF.",
        )
    audit_json = await asyncio.to_thread(build_csr_audit_log, summary)
    return Response(
        content=audit_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="csr-nim-audit-{int(time.time())}.json"',
        },
    )
