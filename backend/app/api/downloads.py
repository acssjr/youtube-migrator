"""Browser-facing API, backed by the local queue or a persistent remote worker."""
from datetime import datetime
import re
import secrets
from typing import Literal
from urllib.parse import urlparse, urlencode, parse_qs
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from googleapiclient.errors import HttpError
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
import requests
from sqlmodel import Session, select

from app.api.descriptions import channel_service
from app.config.config import settings
from app.database.db import get_session
from app.models.models import DownloadJob
from app.services.cloud_session import cloud_mode
from app.services.download_engine import download_engine
from app.services.download_jobs import download_queue, get_job, job_directory, video_id

router = APIRouter(prefix="/downloads", tags=["downloads"])
COOKIE = "yt_download_owner"


class DownloadRequest(BaseModel):
    sources: list[str] = Field(min_length=1)
    format: Literal["mp3", "mp4"]
    resolution: Literal[360, 720, 1080] = 1080
    channel_id: str | None = None

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, values):
        identifiers = [video_id(value) for value in values]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Remova os vídeos repetidos do lote.")
        return identifiers


def owner(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    value = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        value = secrets.token_urlsafe(32)
        response.set_cookie(COOKIE, value, max_age=365 * 24 * 3600, httponly=True,
                            secure=cloud_mode() or request.url.scheme == "https", samesite="lax")
    return value


def remote(method, path, **kwargs):
    base = settings.DOWNLOAD_WORKER_URL.rstrip("/")
    if not base or not settings.DOWNLOAD_WORKER_TOKEN:
        raise HTTPException(503, "O servidor de downloads ainda não foi configurado.")
    parsed = urlparse(base)
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
        raise HTTPException(503, "Configure um endereço HTTPS para o servidor de downloads.")
    try:
        result = requests.request(method, base + "/api/download-worker" + path,
                                  headers={"Authorization": "Bearer " + settings.DOWNLOAD_WORKER_TOKEN},
                                  timeout=15, allow_redirects=False, **kwargs)
        if result.status_code >= 400:
            try:
                detail = result.json().get("detail", "O servidor de downloads não respondeu.")
            except ValueError:
                detail = "O servidor de downloads não respondeu."
            raise HTTPException(result.status_code, detail)
        if not 200 <= result.status_code < 300:
            raise HTTPException(502, "Resposta inválida do servidor de downloads.")
        return result.json()
    except (requests.RequestException, ValueError) as error:
        raise HTTPException(503, "O servidor de downloads está indisponível. Tente novamente.") from error


def use_remote():
    return cloud_mode() or bool(settings.DOWNLOAD_WORKER_URL)


def serialize(job: DownloadJob, file_url: str | None = None):
    return {"id": job.id, "video_id": job.video_id, "title": job.title or job.video_id,
            "format": job.format, "resolution": job.resolution, "status": job.status,
            "progress": job.progress, "message": job.message, "file_size": job.file_size,
            "expires_at": job.expires_at.isoformat(),
            "file_url": file_url if job.status == "completed" and job.expires_at > datetime.utcnow() else None}


def media_response(session, job_id, owner_id):
    job = get_job(session, job_id, owner_id)
    if job.expires_at <= datetime.utcnow() or job.status == "expired":
        raise HTTPException(410, "O arquivo expirou. Solicite novamente.")
    if job.status != "completed":
        raise HTTPException(409, "O arquivo ainda não está pronto.")
    path = job_directory(job.id) / ("media." + job.format)
    if not path.is_file():
        raise HTTPException(410, "O arquivo não está mais disponível. Solicite novamente.")
    title = re.sub(r"[^\w .()-]", "_", job.title, flags=re.UNICODE).strip(" .")[:100] or job.video_id
    return FileResponse(path, media_type="audio/mpeg" if job.format == "mp3" else "video/mp4",
                        filename=f"{title}.{job.format}", headers={"Cache-Control": "private, no-store"})


@router.get("/status")
def status(request: Request, response: Response):
    owner(request, response)
    if cloud_mode() and not settings.DOWNLOAD_WORKER_URL:
        return {"available": True, "mode": "companion", "retention_hours": settings.DOWNLOAD_RETENTION_HOURS,
                "engine": None, "local_url": "http://127.0.0.1:8011/downloads"}
    if use_remote():
        return remote("GET", "/status")
    return {"available": True, "mode": "local", "retention_hours": settings.DOWNLOAD_RETENTION_HOURS,
            "engine": download_engine.status()}


@router.post("/handoff")
def handoff(payload: DownloadRequest, request: Request, session: Session = Depends(get_session)):
    if payload.channel_id:
        try:
            resources = channel_service(payload.channel_id, session, request).list_all_video_resources()
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(502, "Não foi possível verificar os vídeos do canal.") from error
        if not set(payload.sources).issubset({video["id"] for video in resources}):
            raise HTTPException(403, "A seleção contém vídeo externo ao canal conectado.")
    # Browser navigation only; no OAuth data, network access to localhost or automatic execution.
    transfer = {"sources": payload.sources, "format": payload.format, "resolution": payload.resolution}
    return {"url": "http://127.0.0.1:8011/downloads#" + urlencode({"transfer": json.dumps(transfer)})}


@router.get("/channel/{channel_id}")
def channel_videos(channel_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        videos = channel_service(channel_id, session, request).list_all_video_resources()
        return [{"id": v["id"], "title": v["snippet"]["title"],
                 "published_at": v["snippet"].get("publishedAt", ""),
                 "thumbnail_url": v["snippet"].get("thumbnails", {}).get("medium", {}).get("url", "")}
                for v in videos]
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Não foi possível consultar os vídeos do canal.") from error


def playlist_identifier(source: str) -> str:
    value = source.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com") or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError("Informe um link de playlist do YouTube válido.")
        value = parse_qs(parsed.query).get("list", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", value):
        raise ValueError("Informe um link ou ID de playlist do YouTube válido.")
    return value


@router.get("/playlist/{channel_id}")
def playlist_videos(channel_id: str, request: Request, response: Response,
                    source: str = Query(min_length=1, max_length=2048), session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    try:
        identifier = playlist_identifier(source)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    service = channel_service(channel_id, session, request)
    try:
        catalog = service.playlist_download_catalog(identifier)
        catalog["videos"] = [{"id": video["id"], "title": video["snippet"]["title"],
                              "published_at": video["snippet"].get("publishedAt", ""),
                              "thumbnail_url": video["snippet"].get("thumbnails", {}).get("medium", {}).get("url", "")}
                             for video in catalog["videos"]]
        return catalog
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    except HttpError as error:
        code = error.resp.status
        raise HTTPException(code if code in (403, 404) else 502,
                            "Não foi possível consultar a playlist. Confira se ela existe e se esta conta tem acesso.") from error
    except Exception as error:
        raise HTTPException(502, "Não foi possível consultar a playlist. Tente novamente.") from error


@router.post("/jobs", status_code=202)
def create(payload: DownloadRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    owner_id = owner(request, response)
    if payload.channel_id:
        try:
            resources = channel_service(payload.channel_id, session, request).list_all_video_resources()
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(502, "Não foi possível verificar os vídeos do canal.") from error
        owned = {v["id"] for v in resources}
        if any(identifier not in owned for identifier in payload.sources):
            raise HTTPException(403, "A seleção contém vídeo externo ao canal conectado.")
    if use_remote():
        return remote("POST", "/jobs", json={**payload.model_dump(exclude={"channel_id"}), "owner_id": owner_id})
    return [serialize(job) for job in download_queue.create(session, owner_id, payload.sources, payload.format, payload.resolution)]


@router.get("/jobs")
def list_jobs(request: Request, response: Response, session: Session = Depends(get_session)):
    owner_id = owner(request, response)
    if use_remote():
        return remote("GET", "/jobs", params={"owner_id": owner_id})
    jobs = session.exec(select(DownloadJob).where(DownloadJob.owner_id == owner_id)
                        .order_by(DownloadJob.created_at.desc())).all()
    return [serialize(job, f"/api/downloads/jobs/{job.id}/file") for job in jobs]


@router.get("/jobs/{job_id}/file")
def download_file(job_id: str, request: Request, response: Response, session: Session = Depends(get_session)):
    if use_remote():
        raise HTTPException(400, "Atualize a lista para obter o link do servidor de downloads.")
    return media_response(session, job_id, owner(request, response))
