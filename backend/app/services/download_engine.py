"""Install updates in separate environments; existing downloads keep their snapshot."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import venv

from app.config.config import settings


class DownloadEngine:
    def __init__(self):
        self.root = settings.downloads_path / "engines"
        self.lock = threading.Lock()
        self.updating = False
        self.last_error = ""
        self.last_check = None

    def snapshot(self):
        from yt_dlp.version import __version__
        try:
            data = json.loads((self.root / "active.json").read_text())
            path = (self.root / data["python"]).resolve()
            if path.is_relative_to(self.root.resolve()) and path.is_file():
                return str(path), data["version"]
        except (OSError, ValueError, KeyError):
            pass
        return sys.executable, __version__

    def update(self):
        # One worker process per database/volume. Do not mutate its application venv.
        if not self.lock.acquire(blocking=False):
            return False
        candidate = self.root / uuid.uuid4().hex
        self.updating = True
        try:
            from datetime import datetime, timezone
            self.last_check = datetime.now(timezone.utc).isoformat()
            candidate.mkdir(parents=True)
            venv.create(candidate, with_pip=True)
            python = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command = [str(python), "-m", "pip", "--isolated", "install", "--index-url",
                       "https://pypi.org/simple", "--disable-pip-version-check", "--upgrade", "yt-dlp[default]"]
            if settings.DOWNLOAD_UPDATE_CHANNEL == "nightly":
                command.append("--pre")
            subprocess.run(command, check=True, capture_output=True, timeout=300)
            # Exercise the adapter without downloading media before activating it.
            runner = Path(__file__).with_name("download_runner.py")
            result = subprocess.run([str(python), str(runner), "--self-test"],
                                    check=True, capture_output=True, text=True, timeout=30)
            version = json.loads(result.stdout)["version"]
            active = self.root / "active.json"
            if active.is_file():
                (self.root / "previous.json").write_text(active.read_text())
            pointer = candidate / "active.tmp"
            pointer.write_text(json.dumps({"python": str(python.relative_to(self.root)), "version": version}))
            pointer.replace(self.root / "active.json")
            self.last_error = ""
            # Jobs have a maximum execution time of one day; keep older engines for a week.
            import time
            import shutil
            for directory in self.root.iterdir():
                if directory.is_dir() and directory != candidate and directory.stat().st_mtime < time.time() - 7 * 86400:
                    if directory.resolve().is_relative_to(self.root.resolve()):
                        shutil.rmtree(directory, ignore_errors=True)
            return True
        except Exception:
            self.last_error = "Não foi possível atualizar o motor; a versão anterior continua ativa."
            # Candidate is exclusively owned by this updater, inside the engine root.
            if candidate.resolve().is_relative_to(self.root.resolve()):
                import shutil
                shutil.rmtree(candidate, ignore_errors=True)
            return False
        finally:
            self.updating = False
            self.lock.release()

    def rollback(self):
        with self.lock:
            try:
                previous = json.loads((self.root / "previous.json").read_text())
                python = (self.root / previous["python"]).resolve()
                if not python.is_relative_to(self.root.resolve()) or not python.is_file():
                    return False
                pointer = self.root / (uuid.uuid4().hex + ".tmp")
                pointer.write_text(json.dumps(previous))
                pointer.replace(self.root / "active.json")
                return True
            except (OSError, ValueError, KeyError):
                return False

    def status(self):
        import shutil
        return {"version": self.snapshot()[1], "updating": self.updating,
                "last_check": self.last_check, "update_error": self.last_error,
                "auto_update": settings.DOWNLOAD_AUTO_UPDATE,
                "update_hours": max(1, settings.DOWNLOAD_UPDATE_HOURS),
                "channel": settings.DOWNLOAD_UPDATE_CHANNEL,
                "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
                "javascript": bool(shutil.which("node") or shutil.which("deno"))}


download_engine = DownloadEngine()
