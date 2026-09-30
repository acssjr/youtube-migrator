"""Disk-backed packages of files already prepared by the local download queue."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import time
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session
from starlette.background import BackgroundTask

from app.api.downloads import owner, use_remote, remote
from app.config.config import settings
from app.database.db import get_session
from app.services.download_jobs import get_job, job_directory

router = APIRouter(prefix="/download-packages", tags=["download-packages"])


class PackageRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1)
    title: str = Field(default="Meu acervo", max_length=120)

    @field_validator("job_ids")
    @classmethod
    def valid_ids(cls, values):
        if any(not re.fullmatch(r"[0-9a-f]{32}", value) for value in values) or len(values) != len(set(values)):
            raise ValueError("Selecione downloads válidos, sem repetições.")
        return values


def safe_name(value: str) -> str:
    return re.sub(r"[^\w .()–—-]", "_", value, flags=re.UNICODE).strip(" .")[:100] or "Acervo"


def packages_directory() -> Path:
    return settings.downloads_path / "packages"


def owner_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def require_local():
    if use_remote():
        raise HTTPException(503, "Abra o aplicativo local para salvar um pacote. O servidor remoto ainda não oferece esta função.")


@router.post("", status_code=201)
def create_package(payload: PackageRequest, request: Request, response: Response,
                   session: Session = Depends(get_session)):
    owner_id = owner(request, response)
    if use_remote():
        return remote("POST", "/packages", json={**payload.model_dump(), "owner_id": owner_id})
    return create_package_for_owner(payload, owner_id, session)


def create_package_for_owner(payload: PackageRequest, owner_id: str, session: Session):
    """Worker-safe helper: bearer authorization must precede calling this function."""
    # Check every requested item before creating an archive or reading any media.
    jobs = [get_job(session, identifier, owner_id) for identifier in payload.job_ids]
    root = packages_directory()
    root.mkdir(parents=True, exist_ok=True)
    for stale in root.iterdir():
        if stale.is_dir() and re.fullmatch(r"[0-9a-f]{32}", stale.name) and stale.stat().st_mtime < time.time() - 3600:
            shutil.rmtree(stale, ignore_errors=True)
    identifier = uuid.uuid4().hex
    target = root / identifier
    target.mkdir()
    tracks = io.StringIO()
    writer = csv.writer(tracks)
    writer.writerow(["Ordem", "Título", "Vídeo", "Formato", "Arquivo", "Situação"])
    errors = []
    included = 0
    width = max(2, len(str(len(jobs))))
    try:
        # ZIP_STORED avoids CPU-heavy recompression of already compressed MP3/MP4.
        with zipfile.ZipFile(target / "package.zip", "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for position, job in enumerate(jobs, 1):
                title = job.title or job.video_id
                filename = f"{position:0{width}d} — {safe_name(title)}.{job.format}"
                reason = ""
                path = job_directory(job.id) / ("media." + job.format)
                if job.format not in ("mp3", "mp4"):
                    reason = "Formato inválido."
                elif job.status != "completed":
                    reason = job.message or "Download ainda não concluído."
                elif job.expires_at <= datetime.utcnow():
                    reason = "Arquivo expirado."
                elif not path.is_file() or path.is_symlink():
                    reason = "Arquivo não está mais disponível."
                else:
                    try:
                        archive.write(path, filename)
                        included += 1
                    except FileNotFoundError:
                        reason = "Arquivo removido durante a preparação."
                writer.writerow([position, title, f"https://www.youtube.com/watch?v={job.video_id}", job.format,
                                 filename if not reason else "", reason or "Incluído"])
                if reason:
                    errors.append(f"{position:0{width}d} — {title}: {reason}")
            archive.writestr("lista-de-faixas.csv", tracks.getvalue().encode("utf-8-sig"))
            archive.writestr("relatorio.txt", (f"{payload.title.strip() or 'Meu acervo'}\n"
                f"Arquivos incluídos: {included} de {len(jobs)}\n\n" +
                ("Itens não incluídos:\n" + "\n".join(errors) if errors else "Todos os arquivos foram incluídos.") + "\n").encode("utf-8"))
        (target / "metadata.json").write_text(json.dumps({"owner": owner_hash(owner_id),
            "created_at": time.time(), "filename": safe_name(payload.title) + ".zip"}), encoding="utf-8")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return {"id": identifier, "url": f"/api/download-packages/{identifier}/file", "included": included,
            "missing": len(errors), "total": len(jobs)}


@router.get("/{identifier}/file")
def package_file(identifier: str, request: Request, response: Response):
    require_local()
    return package_response_for_owner(identifier, owner(request, response))


def package_response_for_owner(identifier: str, owner_id: str):
    """Call only after authenticating the browser cookie or worker signed URL."""
    return package_response(identifier, expected_owner_hash=owner_hash(owner_id))


def signed_package_response(identifier: str):
    """Worker only: caller MUST verify signature bound to 'package:' + identifier first."""
    return package_response(identifier)


def package_response(identifier: str, expected_owner_hash: str | None = None):
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise HTTPException(404, "Pacote não encontrado.")
    target = packages_directory() / identifier
    try:
        metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(404, "Pacote não encontrado. Prepare-o novamente.")
    if expected_owner_hash is not None and metadata.get("owner") != expected_owner_hash:
        raise HTTPException(404, "Pacote não encontrado.")
    if metadata.get("created_at", 0) < time.time() - 3600:
        shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(410, "O pacote expirou. Prepare-o novamente.")
    return FileResponse(target / "package.zip", media_type="application/zip", filename=metadata["filename"],
                        headers={"Cache-Control": "private, no-store"},
                        background=BackgroundTask(shutil.rmtree, target, ignore_errors=True))
