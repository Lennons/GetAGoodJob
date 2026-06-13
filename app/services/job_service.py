"""
Shared job/resume helper functions.
Extracted from main.py to keep the router file lean.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Event, Job, Resume, Setting
from app.services.settings import get_app_settings
from app.services.text import clean_jd_text, compact_text, normalize_source_key
from app.services.deepseek import _salary_to_display_k


def dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def resume_to_dict(resume: Resume) -> dict[str, Any]:
    return {
        "id": resume.id,
        "filename": resume.filename,
        "file_path": resume.file_path,
        "analysis": resume.analysis,
        "is_active": resume.is_active,
        "created_at": dt(resume.created_at),
        "updated_at": dt(resume.updated_at),
    }


def job_to_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "seq": job.seq,
        "resume_id": job.resume_id,
        "source_key": job.source_key,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "salary": job.salary,
        "salary_display": _salary_to_display_k(job.salary_display or job.salary or ""),
        "city": job.city,
        "description": job.description,
        "raw": job.raw,
        "score": job.score,
        "decision": job.decision,
        "status": job.status,
        "reasons": job.reasons,
        "risks": job.risks,
        "initial_message": job.initial_message,
        "created_at": dt(job.created_at),
        "updated_at": dt(job.updated_at),
    }


def event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "payload": event.payload,
        "created_at": dt(event.created_at),
    }


def get_active_resume(db: Session, resume_id: Optional[str] = None) -> Resume:
    if resume_id:
        resume = db.get(Resume, resume_id)
    else:
        settings = get_app_settings(db)
        active_resume_id = settings.get("active_resume_id")
        resume = db.get(Resume, active_resume_id) if active_resume_id else None
        if not resume:
            resume = db.scalar(
                select(Resume).where(Resume.is_active.is_(True)).order_by(desc(Resume.created_at))
            )
    if not resume:
        raise HTTPException(status_code=400, detail="请先上传并激活一份简历")
    return resume


def set_active_resume(db: Session, resume: Resume) -> None:
    db.query(Resume).update({Resume.is_active: False}, synchronize_session=False)
    db.query(Resume).filter(Resume.id == resume.id).update(
        {Resume.is_active: True}, synchronize_session=False
    )
    resume.is_active = True
    settings = get_app_settings(db)
    settings["active_resume_id"] = resume.id
    row = db.get(Setting, "global")
    if row:
        row.value = settings
    else:
        db.add(Setting(key="global", value=settings))


def upsert_job(
    db: Session,
    job_payload: dict[str, Any],
    resume_id: Optional[str] = None,
    evaluation: Optional[dict] = None,
    batch_id: Optional[str] = None,
) -> Job:
    source_key = normalize_source_key(job_payload)
    existing = db.scalar(select(Job).where(Job.source_key == source_key))
    evaluation = evaluation or {}
    values = {
        "resume_id": resume_id,
        "source_key": source_key,
        "url": compact_text(job_payload.get("url"), 1024),
        "title": compact_text(job_payload.get("title"), 255),
        "company": compact_text(job_payload.get("company"), 255),
        "salary": compact_text(job_payload.get("salary"), 255),
        "salary_display": compact_text(evaluation.get("salary_display") or job_payload.get("salary_display", ""), 255),
        "city": compact_text(job_payload.get("city"), 255),
        "description": clean_jd_text(job_payload.get("description", "")),
        "raw": job_payload.get("raw") or job_payload,
        "score": int(evaluation.get("score") or 0),
        "decision": compact_text(evaluation.get("decision") or "review", 32),
        "status": compact_text(evaluation.get("status") or "evaluated", 32),
        "reasons": evaluation.get("reasons") or [],
        "risks": evaluation.get("risks") or [],
        "initial_message": compact_text(evaluation.get("initial_message"), 1000),
    }
    if batch_id:
        values["batch_id"] = batch_id
    if existing:
        if existing.status == "skipped" and values.get("status") not in ("skipped",):
            pass
        elif existing.status == "chat_started" and values.get("status") == "evaluated":
            values.pop("status", None)
            for key, value in values.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            if not batch_id and existing.batch_id:
                pass
            db.commit()
            db.refresh(existing)
            return existing

    max_seq = db.scalar(select(func.max(Job.seq))) or 0
    values["seq"] = max_seq + 1
    job = Job(**values)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.source_key == source_key))
        if not existing:
            raise
        return existing
    db.refresh(job)
    return job
