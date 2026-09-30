import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config.config import settings
from app.database.db import engine
from app.models.models import DownloadJob
from app.services.download_engine import download_engine


def video_id(source: str) -> str:
    source = source.strip()
    if re.fullmatch(r"[\w-]{11}", source, flags=re.ASCII):
        return source
    url = urlparse(source)
    if url.scheme not in ("http", "https") or url.username or url.password or url.port not in (None, 80, 443):
        raise ValueError("Informe um link de vídeo do YouTube válido.")
    host = (url.hostname or "").lower()
    parts = url.path.strip("/").split("/")
    identifier = ""
    if host in ("youtu.be", "www.youtu.be") and len(parts) == 1:
        identifier = parts[0]
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if url.path == "/watch":
            identifier = parse_qs(url.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in ("shorts", "live", "embed"):
            identifier = parts[1]
    if not re.fullmatch(r"[\w-]{11}", identifier, flags=re.ASCII):
        raise ValueError("Informe um link de vídeo do YouTube válido; playlists não são aceitas.")
    return identifier


def job_directory(job_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404, "Download não encontrado.")
    return settings.downloads_path / "exports" / job_id


def get_job(session: Session, job_id: str, owner: str) -> DownloadJob:
    job = session.get(DownloadJob, job_id)
    if not job or job.owner_id != owner:
        raise HTTPException(404, "Download não encontrado.")
    return job


def terminate_download(process):
    # Stop FFmpeg children as well as the runner when shutting down or timing out.
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


class DownloadQueue:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.update_thread = None
        self.create_lock = threading.Lock()

    def create(self, session, owner, sources, kind, resolution):
        identifiers = [video_id(source) for source in sources]
        if len(set(identifiers)) != len(identifiers):
            raise HTTPException(400, "Remova os vídeos repetidos do lote.")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise HTTPException(503, "Instale FFmpeg e FFprobe no servidor para baixar MP3 e MP4.")
        with self.create_lock:
            jobs = [DownloadJob(id=uuid.uuid4().hex, owner_id=owner, video_id=identifier,
                                format=kind, resolution=resolution,
                                expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.DOWNLOAD_RETENTION_HOURS)))
                    for identifier in identifiers]
            for job in jobs:
                session.add(job)
            session.commit()
            for job in jobs:
                session.refresh(job)
            return jobs

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        with Session(engine) as session:
            for job in session.exec(select(DownloadJob).where(DownloadJob.status == "running")).all():
                job.status = "error"
                job.message = "O servidor reiniciou durante o download. Solicite novamente."
                session.add(job)
            session.commit()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        if settings.DOWNLOAD_AUTO_UPDATE:
            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()

    def update_loop(self):
        while not self.stop_event.is_set():
            download_engine.update()
            if self.stop_event.wait(max(1, settings.DOWNLOAD_UPDATE_HOURS) * 3600):
                break

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.cleanup()
                with Session(engine) as session:
                    job = session.exec(select(DownloadJob).where(DownloadJob.status == "queued")
                                       .order_by(DownloadJob.created_at)).first()
                    if job:
                        self.execute(session, job)
            except Exception:
                from loguru import logger
                logger.exception("Falha no processamento da fila de downloads")
            self.stop_event.wait(1)

    def cleanup(self):
        with Session(engine) as session:
            expired = session.exec(select(DownloadJob).where(DownloadJob.expires_at < datetime.utcnow(),
                                                            DownloadJob.status.in_(["completed", "error"]))).all()
            for job in expired:
                root = job_directory(job.id).resolve()
                if root.is_relative_to((settings.downloads_path / "exports").resolve()):
                    shutil.rmtree(root, ignore_errors=True)
                job.status = "expired"
                job.message = "Arquivo expirado. Solicite o download novamente."
                session.add(job)
            # Limit historical rows as well as media retention.
            for job in session.exec(select(DownloadJob).where(DownloadJob.status == "expired",
                       DownloadJob.expires_at < datetime.utcnow() - timedelta(days=7))).all():
                session.delete(job)
            session.commit()

    def execute(self, session, job):
        root = job_directory(job.id)
        root.mkdir(parents=True, exist_ok=True)
        job.status, job.message = "running", "Preparando download..."
        session.add(job)
        session.commit()
        config = {"directory": str(root), "video_id": job.video_id, "format": job.format,
                  "resolution": job.resolution, "max_bytes": settings.DOWNLOAD_MAX_BYTES,
                  "cookies": settings.DOWNLOAD_COOKIES_FILE}
        (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
        python, _ = download_engine.snapshot()
        process = None
        try:
            process = subprocess.Popen([python, str(Path(__file__).with_name("download_runner.py")), str(root / "config.json")],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=os.name != "nt")
            deadline = time.monotonic() + min(86400, max(60, settings.DOWNLOAD_TIMEOUT_SECONDS))
            while process.poll() is None:
                if self.stop_event.wait(1) or time.monotonic() > deadline:
                    terminate_download(process)
                    raise ValueError("Download interrompido ou tempo limite excedido. Solicite novamente.")
                try:
                    progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
                    job.progress, job.message = progress["progress"], progress["message"]
                    session.add(job)
                    session.commit()
                except (OSError, ValueError, KeyError):
                    pass
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            if process.returncode or result.get("error"):
                raise ValueError(result.get("error", "Falha ao converter o arquivo."))
            if not (root / ("media." + job.format)).is_file():
                raise ValueError("O arquivo final não foi gerado.")
            job.status, job.progress, job.message = "completed", 100, "Arquivo pronto."
            job.title, job.file_size = result["title"], result["file_size"]
            job.expires_at = datetime.utcnow() + timedelta(hours=max(1, settings.DOWNLOAD_RETENTION_HOURS))
        except Exception as error:
            job.status, job.message = "error", str(error) if isinstance(error, ValueError) else "Falha ao processar o download. Solicite novamente."
            for path in root.glob("media.*"):
                if path.is_file():
                    path.unlink()
        finally:
            if process and process.poll() is None:
                terminate_download(process)
            session.add(job)
            session.commit()


download_queue = DownloadQueue()
