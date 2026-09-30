"""Start the local download companion. Keep this window open until jobs finish."""
import json
import base64
import re
from urllib.parse import urlparse, parse_qs, urlencode
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = "http://localhost:8011"
PROCESS_OPTIONS = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" and sys.stdout is None else {}


def running():
    try:
        with urlopen(URL + "/api/downloads/status", timeout=2) as response:
            status = json.load(response)
        if status.get("mode") != "local":
            raise RuntimeError("A porta 8011 está ocupada por outro serviço.")
        return True
    except (OSError, ValueError):
        return False


def transfer_url(argument=None):
    if not argument:
        return URL + "/downloads"
    parsed = urlparse(argument)
    if parsed.scheme != "ytacervo" or parsed.netloc != "prepare" or parsed.path not in ("", "/"):
        raise ValueError("Link do aplicativo inválido.")
    encoded = parse_qs(parsed.query).get("data", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,30000}", encoded):
        raise ValueError("Seleção inválida.")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if (not isinstance(payload, dict) or not isinstance(payload.get("sources"), list) or not payload["sources"]
            or not all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", x) for x in payload["sources"])
            or payload.get("format") not in ("mp3", "mp4") or payload.get("resolution") not in (360, 720, 1080)):
        raise ValueError("Seleção inválida.")
    clean = {key: payload[key] for key in ("sources", "format", "resolution")}
    clean["autostart"] = True
    return URL + "/downloads#" + urlencode({"transfer": json.dumps(clean)})


def register_protocol():
    if os.name != "nt":
        return
    import winreg
    python = Path(sys.executable).with_name("pythonw.exe")
    if not python.exists():
        python = Path(sys.executable)
    base = r"Software\Classes\ytacervo"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:YouTube Acervo")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{python}" "{ROOT / "run_downloads.py"}" "%1"')


def main():
    if "--register-only" in sys.argv:
        register_protocol()
        return
    target = transfer_url(sys.argv[1] if len(sys.argv) > 1 else None)
    register_protocol()
    if running():
        webbrowser.open(target)
        print("O aplicativo local já está aberto. Mantenha sua janela em execução.")
        return
    for command in ("uv", "node", "ffmpeg", "ffprobe"):
        if not shutil.which(command):
            raise RuntimeError(f"Instale {command} e abra este iniciador novamente. Veja docs/downloads.md.")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Instale Node.js com npm.")
    subprocess.run(["uv", "sync", "--frozen"], cwd=ROOT / "backend", check=True, **PROCESS_OPTIONS)
    if not (ROOT / "frontend/node_modules").is_dir():
        subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True, **PROCESS_OPTIONS)
    dist = ROOT / "frontend/dist/index.html"
    sources = list((ROOT / "frontend/src").rglob("*")) + [ROOT / "frontend/package-lock.json", ROOT / "frontend/index.html"]
    if not dist.exists() or any(p.is_file() and p.stat().st_mtime > dist.stat().st_mtime for p in sources):
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True, **PROCESS_OPTIONS)
    env = dict(os.environ, VERCEL="", DOWNLOAD_WORKER_URL="", DEBUG="false",
               DATABASE_URL="sqlite:///database/youtube_migrator.db", DOWNLOAD_AUTO_UPDATE="true")
    python = ROOT / "backend/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    process = subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"], cwd=ROOT / "backend", env=env, **PROCESS_OPTIONS)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("O aplicativo não iniciou. Confira a mensagem acima.")
            if running():
                webbrowser.open(target)
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
    if os.name == "nt" and sys.stdout is None:
        log = open(ROOT / "downloads-launcher.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    try:
        main()
    except KeyboardInterrupt:
        print("Aplicativo encerrado.")
    except Exception as error:
        print(f"Não foi possível iniciar: {error}", file=sys.stderr)
        sys.exit(1)
