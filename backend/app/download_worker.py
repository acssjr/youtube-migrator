"""Dedicated persistent worker. Expose only authenticated JSON APIs and signed files."""
from contextlib import asynccontextmanager
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import field_validator
from sqlmodel import Session, select

from app.api.downloads import DownloadRequest, media_response, serialize
from app.config.config import settings
from app.database.db import get_session, init_db
from app.models.models import DownloadJob
from app.services.download_engine import download_engine
from app.services.download_jobs import download_queue


@asynccontextmanager
async def lifespan(app):
    if not settings.DOWNLOAD_WORKER_TOKEN or not settings.DOWNLOAD_PUBLIC_URL.startswith("https://"):
        raise RuntimeError("Configure DOWNLOAD_WORKER_TOKEN e DOWNLOAD_PUBLIC_URL (HTTPS).")
    init_db()
    download_queue.start()
    yield
    download_queue.stop()


app = FastAPI(title="Acervo Download Worker", lifespan=lifespan)
PREFIX = "/api/download-worker"


def authorize(authorization: str = Header(default="")):
    if not settings.DOWNLOAD_WORKER_TOKEN or not secrets.compare_digest(
        authorization, "Bearer " + settings.DOWNLOAD_WORKER_TOKEN
    ):
        raise HTTPException(401, "Acesso ao servidor de downloads não autorizado.")


def sign_file(job_id, expires):
    return hmac.new(settings.DOWNLOAD_WORKER_TOKEN.encode(), f"{job_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def signed_file(job):
    expires = int(time.time()) + 600
    query = urlencode({"expires": expires, "signature": sign_file(job.id, expires)})
    return f"{settings.DOWNLOAD_PUBLIC_URL.rstrip('/')}{PREFIX}/files/{job.id}?{query}"


class WorkerRequest(DownloadRequest):
    owner_id: str

    @field_validator("owner_id")
    @classmethod
    def validate_owner(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
            raise ValueError("Identificador de navegador inválido.")
        return value


@app.get(PREFIX + "/status", dependencies=[Depends(authorize)])
def status():
    return {"available": True, "mode": "remote", "retention_hours": settings.DOWNLOAD_RETENTION_HOURS,
            "engine": download_engine.status()}


@app.post(PREFIX + "/jobs", status_code=202, dependencies=[Depends(authorize)])
def create(payload: WorkerRequest, session: Session = Depends(get_session)):
    return [serialize(job) for job in download_queue.create(session, payload.owner_id, payload.sources,
                                                          payload.format, payload.resolution)]


@app.get(PREFIX + "/jobs", dependencies=[Depends(authorize)])
def jobs(owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
    records = session.exec(select(DownloadJob).where(DownloadJob.owner_id == owner_id)
                           .order_by(DownloadJob.created_at.desc())).all()
    return [serialize(job, signed_file(job)) for job in records]


@app.get(PREFIX + "/files/{job_id}")
def file(job_id: str, expires: int, signature: str, session: Session = Depends(get_session)):
    if not settings.DOWNLOAD_WORKER_TOKEN or expires < time.time() or expires > time.time() + 610:
        raise HTTPException(403, "Link expirado. Atualize a lista de downloads.")
    expected = sign_file(job_id, expires)
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(403, "Link de download inválido.")
    job = session.get(DownloadJob, job_id)
    if not job:
        raise HTTPException(404, "Download não encontrado.")
    return media_response(session, job_id, job.owner_id)
