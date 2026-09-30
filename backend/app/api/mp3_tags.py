"""Explicit edits to downloaded MP3 metadata; never changes YouTube videos."""
from datetime import datetime
import os
import re
import shutil
import tempfile
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TPE1, TCOM, TALB, TCON, TRCK, TDRC, COMM
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.api.downloads import owner, remote, use_remote
from app.database.db import get_session
from app.services.download_jobs import get_job, job_directory

router = APIRouter(prefix="/mp3-tags", tags=["MP3"])
edit_lock = threading.Lock()
FRAMES = {"title": TIT2, "artist": TPE1, "composer": TCOM, "album": TALB,
          "genre": TCON, "track": TRCK, "year": TDRC}


class TagsRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1)
    tags: dict[str, str]

    @field_validator("job_ids")
    @classmethod
    def ids(cls, values):
        if len(set(values)) != len(values) or any(not re.fullmatch(r"[a-f0-9]{32}", v) for v in values):
            raise ValueError("Seleção de arquivos inválida.")
        return values

    @field_validator("tags")
    @classmethod
    def fields(cls, values):
        if not values or set(values) - (set(FRAMES) | {"notes"}):
            raise ValueError("Campos de identificação inválidos.")
        if any(len(v) > 10000 or "\x00" in v for v in values.values()):
            raise ValueError("Texto de identificação inválido.")
        if values.get("year") and not re.fullmatch(r"\d{4}", values["year"]):
            raise ValueError("Informe o ano com quatro dígitos.")
        if values.get("track") and not re.fullmatch(r"\d+(?:/\d+)?", values["track"]):
            raise ValueError("Informe a faixa como 1 ou 1/8.")
        return values


def media_path(session, identifier, owner_id):
    job = get_job(session, identifier, owner_id)
    if job.format != "mp3" or job.status != "completed":
        raise HTTPException(409, "Selecione apenas MP3 prontos.")
    path = job_directory(job.id) / "media.mp3"
    if job.expires_at <= datetime.utcnow() or not path.is_file() or path.is_symlink():
        raise HTTPException(410, "O arquivo não está mais disponível.")
    return job, path


def read_tags(session, identifier, owner_id):
    _, path = media_path(session, identifier, owner_id)
    try:
        audio = MP3(path)
        tags = audio.tags
        values = {key: str(tags.get(cls.__name__, "")) if tags else "" for key, cls in FRAMES.items()}
        comments = tags.getall("COMM") if tags else []
        own_comment = next((comment for comment in comments if comment.desc == "Acervo"), None)
        values["notes"] = str(own_comment) if own_comment else ""
        return {"job_id": identifier, "tags": values}
    except Exception as error:
        raise HTTPException(422, "Não foi possível ler a identificação deste MP3.") from error


def apply_tags(payload, owner_id, session):
    # Validate every ownership and file before touching any file.
    targets = [media_path(session, identifier, owner_id) for identifier in payload.job_ids]
    results = []
    with edit_lock:
        for job, path in targets:
            temporary = None
            try:
                handle, temporary = tempfile.mkstemp(prefix="tags-", suffix=".mp3", dir=path.parent)
                os.close(handle)
                shutil.copyfile(path, temporary)
                audio = MP3(temporary)
                if audio.tags is None:
                    audio.add_tags()
                for key, value in payload.tags.items():
                    if key == "notes":
                        # Only the application's comment; preserve other comment languages/descriptions.
                        audio.tags.delall("COMM:Acervo")
                        if value:
                            audio.tags.add(COMM(encoding=3, lang="por", desc="Acervo", text=[value]))
                    else:
                        cls = FRAMES[key]
                        audio.tags.delall(cls.__name__)
                        if value:
                            audio.tags.add(cls(encoding=3, text=[value]))
                audio.save()
                os.replace(temporary, path)
                temporary = None
                job.file_size = path.stat().st_size
                session.add(job)
                session.commit()
                results.append({"job_id": job.id, "applied": True})
            except Exception:
                session.rollback()
                results.append({"job_id": job.id, "applied": False, "error": "Não foi possível salvar. Feche o arquivo se estiver em uso e tente novamente."})
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
    return {"results": results}


@router.get("/{job_id}")
def read(job_id: str, request: Request, response: Response, session: Session = Depends(get_session)):
    owner_id = owner(request, response)
    return remote("GET", "/tags/" + job_id, params={"owner_id": owner_id}) if use_remote() else read_tags(session, job_id, owner_id)


@router.post("")
def apply(payload: TagsRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    owner_id = owner(request, response)
    return remote("POST", "/tags", json={**payload.model_dump(), "owner_id": owner_id}) if use_remote() else apply_tags(payload, owner_id, session)


def install_worker_routes(app, authorize):
    class WorkerTagsRequest(TagsRequest):
        owner_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")

    @app.get("/api/download-worker/tags/{job_id}", dependencies=[Depends(authorize)])
    def worker_read(job_id: str, owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
        return read_tags(session, job_id, owner_id)

    @app.post("/api/download-worker/tags", dependencies=[Depends(authorize)])
    def worker_apply(payload: WorkerTagsRequest, session: Session = Depends(get_session)):
        return apply_tags(payload, payload.owner_id, session)
