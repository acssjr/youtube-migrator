"""Standalone child process: works with the installed or an isolated updated yt-dlp."""
import json
from pathlib import Path
import sys


def options(config, hook):
    root = Path(config["directory"])
    result = {
        "outtmpl": str(root / "media.%(ext)s"),
        "noplaylist": True, "quiet": True, "no_warnings": True, "noprogress": True,
        "socket_timeout": 30, "retries": 3, "fragment_retries": 3,
        "max_filesize": config["max_bytes"], "overwrites": True,
        "progress_hooks": [hook], "postprocessor_hooks": [hook],
        "js_runtimes": {"node": {}, "deno": {}},
        "match_filter": lambda info, **kwargs: "Transmissões ao vivo não são suportadas." if info.get("is_live") else None,
    }
    if config.get("cookies"):
        result["cookiefile"] = config["cookies"]
    if config["format"] == "mp3":
        result.update(format="bestaudio/best", postprocessors=[{
            "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}])
    else:
        height = config["resolution"]
        # Require MP4 video + AAC audio, avoiding an unannounced lossy transcode.
        result.update(format=f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/best[ext=mp4][height<={height}]",
                      merge_output_format="mp4")
    return result


def run(config):
    import yt_dlp
    root = Path(config["directory"])
    def write(name, data):
        tmp = root / (name + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(root / name)
    def hook(data):
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        downloaded = data.get("downloaded_bytes", 0)
        if downloaded > config["max_bytes"]:
            raise ValueError("O arquivo excede o limite de tamanho.")
        write("progress.json", {"progress": min(95, downloaded / total * 95) if total else 0,
                                "message": "Convertendo arquivo..." if data.get("status") in ("finished", "started") else "Baixando..."})
    try:
        with yt_dlp.YoutubeDL(options(config, hook)) as downloader:
            info = downloader.extract_info("https://www.youtube.com/watch?v=" + config["video_id"], download=True)
        path = root / ("media." + config["format"])
        if not info or not path.is_file():
            raise ValueError("O YouTube não disponibilizou o formato solicitado.")
        if path.stat().st_size > config["max_bytes"]:
            path.unlink()
            raise ValueError("O arquivo excede o limite de tamanho.")
        write("result.json", {"title": info.get("title", config["video_id"]), "file_size": path.stat().st_size})
    except Exception:
        # yt-dlp errors can contain cookie paths and network details. Keep the UI error actionable.
        write("result.json", {"error": "Não foi possível baixar este vídeo. Ele pode estar privado, restrito ou temporariamente bloqueado pelo YouTube. Confira a conexão e a atualização do motor."})
        return 1
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "--self-test":
        import yt_dlp
        from yt_dlp.version import __version__
        for kind in ("mp3", "mp4"):
            with yt_dlp.YoutubeDL(options({"directory": ".", "format": kind, "resolution": 720,
                                         "max_bytes": 1000}, lambda _: None)):
                pass
        print(json.dumps({"version": __version__}))
    else:
        sys.exit(run(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))
