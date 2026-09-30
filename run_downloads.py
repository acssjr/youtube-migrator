"""Start the local download companion. Keep this window open until jobs finish."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8011"


def running():
    try:
        with urlopen(URL + "/api/downloads/status", timeout=2) as response:
            status = json.load(response)
        if status.get("mode") != "local":
            raise RuntimeError("A porta 8011 está ocupada por outro serviço.")
        return True
    except (OSError, ValueError):
        return False


def main():
    if running():
        webbrowser.open(URL + "/downloads")
        print("O aplicativo local já está aberto. Mantenha sua janela em execução.")
        return
    for command in ("uv", "node", "ffmpeg", "ffprobe"):
        if not shutil.which(command):
            raise RuntimeError(f"Instale {command} e abra este iniciador novamente. Veja docs/downloads.md.")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Instale Node.js com npm.")
    subprocess.run(["uv", "sync", "--frozen"], cwd=ROOT / "backend", check=True)
    if not (ROOT / "frontend/node_modules").is_dir():
        subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True)
    dist = ROOT / "frontend/dist/index.html"
    sources = list((ROOT / "frontend/src").rglob("*")) + [ROOT / "frontend/package-lock.json", ROOT / "frontend/index.html"]
    if not dist.exists() or any(p.is_file() and p.stat().st_mtime > dist.stat().st_mtime for p in sources):
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    env = dict(os.environ, VERCEL="", DOWNLOAD_WORKER_URL="", DEBUG="false",
               DATABASE_URL="sqlite:///database/youtube_migrator.db", DOWNLOAD_AUTO_UPDATE="true")
    python = ROOT / "backend/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    process = subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"], cwd=ROOT / "backend", env=env)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("O aplicativo não iniciou. Confira a mensagem acima.")
            if running():
                webbrowser.open(URL + "/downloads")
                print("Downloads disponíveis. Mantenha esta janela aberta; Ctrl+C para encerrar.")
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("O aplicativo demorou para iniciar. Confira a mensagem acima.")
        process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Aplicativo encerrado.")
    except Exception as error:
        print(f"Não foi possível iniciar: {error}", file=sys.stderr)
        sys.exit(1)
