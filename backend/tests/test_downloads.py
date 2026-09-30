import json
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.api import downloads
from app.config.config import settings
from app.database.db import get_session
from app.main import app
from app.models.models import DownloadJob
from app.services.download_jobs import DownloadQueue, video_id, job_directory
from app.services.download_runner import options, run
from app.services.download_engine import DownloadEngine
from app.services.youtube_service import YoutubeService
from app import download_worker

ID = "BaW_jenozKc"


class UrlTests(unittest.TestCase):
    def test_playlist_paginates_preserves_order_and_removes_duplicates_and_unavailable(self):
        service = YoutubeService.__new__(YoutubeService)
        service.youtube = MagicMock()
        service.youtube.playlists.return_value.list.return_value.execute.return_value = {"items": [{"snippet": {"title": "Retreta"}}]}
        identifiers = [f"{i:011d}" for i in range(51)]
        first, second = MagicMock(), MagicMock()
        first.execute.return_value = {"items": [{"contentDetails": {"videoId": identifier}} for identifier in identifiers[:50]], "nextPageToken": "next"}
        second.execute.return_value = {"items": [{"contentDetails": {"videoId": identifiers[50]}}, {"contentDetails": {"videoId": identifiers[0]}}]}
        service.youtube.playlistItems.return_value.list.return_value = first
        service.youtube.playlistItems.return_value.list_next.side_effect = [second, None]
        service.youtube.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": identifier, "snippet": {"title": identifier}} for identifier in reversed(identifiers[:49])]},
            {"items": [{"id": identifiers[50], "snippet": {"title": "Last"}}]}]
        result = service.playlist_download_catalog("PLexample123")
        self.assertEqual([video["id"] for video in result["videos"]], identifiers[:49] + identifiers[50:])
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["unavailable_count"], 1)

    def test_normalizes_video_only_youtube_sources(self):
        for source in [ID, f"https://youtu.be/{ID}?t=3", f"https://www.youtube.com/watch?v={ID}&list=example",
                       f"https://youtube.com/shorts/{ID}", f"https://m.youtube.com/live/{ID}"]:
            self.assertEqual(video_id(source), ID)

    def test_rejects_other_hosts_playlists_files_and_injection(self):
        for source in ["https://youtube.com.evil.com/watch?v=" + ID, "http://127.0.0.1/secret", "file:///etc/passwd",
                       "https://youtube.com/playlist?list=abc", "https://youtube.com/watch?v=../passwd",
                       "https://youtube.com@evil.com/watch?v=" + ID, "https://youtube.com:bad/watch?v=" + ID]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                video_id(source)

    def test_own_channel_catalog_paginates_beyond_fifty_uploads(self):
        service = YoutubeService.__new__(YoutubeService)
        service.youtube = MagicMock()
        service.youtube.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads"}}}]}
        first, second = MagicMock(), MagicMock()
        identifiers = [f"{i:011d}" for i in range(51)]
        first.execute.return_value = {"items": [{"contentDetails": {"videoId": id}} for id in identifiers[:50]], "nextPageToken": "next"}
        second.execute.return_value = {"items": [{"contentDetails": {"videoId": identifiers[50]}}]}
        service.youtube.playlistItems.return_value.list.return_value = first
        service.youtube.playlistItems.return_value.list_next.side_effect = [second, None]
        service.youtube.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": id, "snippet": {"title": id}} for id in identifiers[:50]]},
            {"items": [{"id": identifiers[50], "snippet": {"title": "Old upload"}}]}]
        self.assertEqual(len(service.list_all_video_resources()), 51)
        calls = service.youtube.videos.return_value.list.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].kwargs["id"], identifiers[50])


class DownloadsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.directory = tempfile.TemporaryDirectory()
        self.owner = secrets.token_urlsafe(32)
        self.saved = {key: getattr(settings, key) for key in ("VERCEL", "DOWNLOAD_WORKER_URL", "DOWNLOAD_WORKER_TOKEN", "DOWNLOAD_PUBLIC_URL", "DOWNLOADS_DIR")}
        settings.VERCEL = ""
        settings.DOWNLOAD_WORKER_URL = ""
        settings.DOWNLOAD_WORKER_TOKEN = "test-worker-secret"
        settings.DOWNLOAD_PUBLIC_URL = "https://worker.example"
        settings.DOWNLOADS_DIR = self.directory.name
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_session] = session
        download_worker.app.dependency_overrides[get_session] = session
        # Do not enter lifespan: queue and updater must not make live downloads in unit tests.
        self.client = TestClient(app)
        self.client.cookies.set(downloads.COOKIE, self.owner)
        self.worker = TestClient(download_worker.app)
        self.ffmpeg = patch("app.services.download_jobs.shutil.which", return_value="ffmpeg")
        self.ffmpeg.start()

    def tearDown(self):
        self.ffmpeg.stop()
        self.client.close()
        self.worker.close()
        app.dependency_overrides.clear()
        download_worker.app.dependency_overrides.clear()
        for key, value in self.saved.items():
            setattr(settings, key, value)
        self.engine.dispose()
        self.directory.cleanup()

    def create(self, **kwargs):
        return self.client.post("/api/downloads/jobs", json={"sources": [ID], "format": "mp3", **kwargs})

    def test_playlist_catalog_uses_connected_account_and_reports_unavailable_items(self):
        service = MagicMock()
        service.playlist_download_catalog.return_value = {"id": "PLexample123", "title": "Retreta", "videos": [
            {"id": ID, "snippet": {"title": "Performance", "publishedAt": "2026-09-30"}}
        ], "unavailable_count": 1, "duplicate_count": 2}
        with patch.object(downloads, "channel_service", return_value=service) as authorization:
            response = self.client.get("/api/downloads/playlist/own", params={"source": "https://www.youtube.com/playlist?list=PLexample123"})
        self.assertEqual(response.status_code, 200)
        authorization.assert_called_once()
        service.playlist_download_catalog.assert_called_once_with("PLexample123")
        self.assertEqual(response.json()["videos"][0]["id"], ID)
        self.assertEqual(response.json()["unavailable_count"], 1)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_playlist_rejects_bad_links_and_handles_missing_or_foreign_account(self):
        for value in ["https://evil.example/playlist?list=PLexample123", "https://youtube.com:bad/playlist?list=PLexample123", "https://youtube.com/watch?v=" + ID]:
            self.assertEqual(self.client.get("/api/downloads/playlist/own", params={"source": value}).status_code, 400)
        with patch.object(downloads, "channel_service", side_effect=downloads.HTTPException(403, "foreign account")):
            self.assertEqual(self.client.get("/api/downloads/playlist/foreign", params={"source": "PLexample123"}).status_code, 403)
        service = MagicMock()
        service.playlist_download_catalog.side_effect = ValueError("Playlist não encontrada.")
        with patch.object(downloads, "channel_service", return_value=service):
            self.assertEqual(self.client.get("/api/downloads/playlist/own", params={"source": "PLexample123"}).status_code, 404)

    def test_validation_and_browser_isolation(self):
        self.assertEqual(self.create(format="exe").status_code, 422)
        self.assertEqual(self.create(sources=[ID] * 11).status_code, 422)
        self.assertEqual(self.create(sources=[ID, "https://youtu.be/" + ID]).status_code, 422)
        response = self.create()
        self.assertEqual(response.status_code, 202)
        job_id = response.json()[0]["id"]
        self.assertEqual(len(self.client.get("/api/downloads/jobs").json()), 1)
        self.client.cookies.set(downloads.COOKIE, secrets.token_urlsafe(32))
        self.assertEqual(self.client.get("/api/downloads/jobs").json(), [])
        self.assertEqual(self.client.get(f"/api/downloads/jobs/{job_id}/file").status_code, 404)

    def test_large_batch_and_additional_jobs_are_accepted_without_truncating_history(self):
        identifiers = [f"{i:011d}" for i in range(125)]
        result = self.create(sources=identifiers)
        self.assertEqual(result.status_code, 202)
        self.assertEqual(len(result.json()), 125)
        self.assertEqual(len(self.client.get("/api/downloads/jobs").json()), 125)
        self.assertEqual(self.create().status_code, 202)
        with patch("app.services.download_jobs.shutil.which", return_value=None):
            # Existing work is reusable without a new conversion; new work still needs FFmpeg.
            self.assertEqual(self.create().status_code, 202)
            self.assertEqual(self.create(sources=["abcdefghijk"]).status_code, 503)

    def test_waiting_download_does_not_expire_before_processing(self):
        job_id = self.create().json()[0]["id"]
        with Session(self.engine) as db:
            job = db.get(DownloadJob, job_id)
            job.expires_at = datetime.utcnow() - timedelta(days=2)
            db.add(job)
            db.commit()
        with patch("app.services.download_jobs.engine", self.engine):
            DownloadQueue().cleanup()
        with Session(self.engine) as db:
            self.assertEqual(db.get(DownloadJob, job_id).status, "queued")

    def test_channel_lists_filled_and_empty_videos_and_checks_membership(self):
        resources = [{"id": ID, "snippet": {"title": "Own video", "description": "already filled"}}]
        service = MagicMock()
        service.list_all_video_resources.return_value = resources
        with patch.object(downloads, "channel_service", return_value=service):
            self.assertEqual(self.client.get("/api/downloads/channel/own").json()[0]["id"], ID)
            self.assertEqual(self.create(channel_id="own").status_code, 202)
            self.assertEqual(self.create(channel_id="own", sources=["abcdefghijk"]).status_code, 403)

    def complete(self):
        job_id = self.create().json()[0]["id"]
        with Session(self.engine) as db:
            job = db.get(DownloadJob, job_id)
            job.status, job.title, job.file_size = "completed", "Test / video", 4
            db.add(job)
            db.commit()
        directory = job_directory(job_id)
        directory.mkdir(parents=True)
        (directory / "media.mp3").write_bytes(b"test")
        return job_id

    def test_completed_file_and_expiration_cleanup(self):
        job_id = self.complete()
        result = self.client.get(f"/api/downloads/jobs/{job_id}/file")
        self.assertEqual(result.content, b"test")
        self.assertIn("audio/mpeg", result.headers["content-type"])
        with Session(self.engine) as db:
            job = db.get(DownloadJob, job_id)
            job.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.add(job)
            db.commit()
        self.assertEqual(self.client.get(f"/api/downloads/jobs/{job_id}/file").status_code, 410)
        with patch("app.services.download_jobs.engine", self.engine):
            DownloadQueue().cleanup()
        self.assertFalse(job_directory(job_id).exists())

    def test_worker_requires_secret_and_signed_files_reject_tampering(self):
        self.assertEqual(self.worker.get("/api/download-worker/jobs", params={"owner_id": self.owner}).status_code, 401)
        job_id = self.complete()
        result = self.worker.get("/api/download-worker/jobs", params={"owner_id": self.owner}, headers={"Authorization": "Bearer test-worker-secret"})
        url = result.json()[0]["file_url"]
        self.assertEqual(self.worker.get(url).content, b"test")
        self.assertEqual(self.worker.get(url + "a").status_code, 403)
        self.assertEqual(self.worker.get(f"/api/download-worker/files/{job_id}?expires=1&signature=wrong").status_code, 403)

    def test_cloud_proxies_json_without_exposing_secret(self):
        settings.VERCEL = "1"
        settings.DOWNLOAD_WORKER_URL = "https://worker.example"
        upstream = MagicMock(status_code=200)
        upstream.json.return_value = []
        with patch.object(downloads.requests, "request", return_value=upstream) as request:
            self.assertEqual(self.client.get("/api/downloads/jobs").json(), [])
            self.assertEqual(request.call_args.kwargs["params"]["owner_id"], self.owner)
            self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer test-worker-secret")
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
        settings.DOWNLOAD_WORKER_URL = ""
        result = self.client.get("/api/downloads/status")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["mode"], "companion")
        self.assertIsNone(result.json()["engine"])

    def test_handoff_validates_selection_without_creating_jobs(self):
        from urllib.parse import urlparse, parse_qs
        response = self.client.post("/api/downloads/handoff", json={"sources": ["https://youtu.be/" + ID], "format": "mp4", "resolution": 720})
        self.assertEqual(response.status_code, 200)
        url = urlparse(response.json()["url"])
        self.assertEqual(url.netloc, "127.0.0.1:8011")
        self.assertEqual(json.loads(parse_qs(url.fragment)["transfer"][0]), {"sources": [ID], "format": "mp4", "resolution": 720})
        self.assertEqual(self.client.get("/api/downloads/jobs").json(), [])
        self.assertEqual(self.client.post("/api/downloads/handoff", json={"sources": ["http://evil.example/video"], "format": "mp3"}).status_code, 422)
        service = MagicMock()
        service.list_all_video_resources.return_value = [{"id": ID}]
        with patch.object(downloads, "channel_service", return_value=service):
            self.assertEqual(self.client.post("/api/downloads/handoff", json={"sources": [ID], "format": "mp3", "channel_id": "own"}).status_code, 200)
            self.assertEqual(self.client.post("/api/downloads/handoff", json={"sources": ["abcdefghijk"], "format": "mp3", "channel_id": "own"}).status_code, 403)

    def test_queue_process_success_failure_and_restart(self):
        job_id = self.create().json()[0]["id"]
        def child(*args, **kwargs):
            root = job_directory(job_id)
            (root / "media.mp3").write_bytes(b"audio")
            (root / "result.json").write_text(json.dumps({"title": "Converted", "file_size": 5}))
            return MagicMock(poll=MagicMock(return_value=0), returncode=0)
        queue = DownloadQueue()
        with Session(self.engine) as db, patch("app.services.download_jobs.subprocess.Popen", side_effect=child):
            queue.execute(db, db.get(DownloadJob, job_id))
            self.assertEqual(db.get(DownloadJob, job_id).status, "completed")
        def failed(*args, **kwargs):
            root = job_directory(job_id)
            (root / "media.mp3").write_bytes(b"partial")
            (root / "result.json").write_text(json.dumps({"error": "Unavailable"}))
            return MagicMock(poll=MagicMock(return_value=1), returncode=1)
        with Session(self.engine) as db, patch("app.services.download_jobs.subprocess.Popen", side_effect=failed):
            queue.execute(db, db.get(DownloadJob, job_id))
            self.assertEqual(db.get(DownloadJob, job_id).status, "error")
            self.assertFalse((job_directory(job_id) / "media.mp3").exists())

    def test_restart_marks_interrupted_jobs_and_preserves_queued(self):
        job_id = self.create().json()[0]["id"]
        queued = self.create(sources=["abcdefghijk"]).json()[0]["id"]
        with Session(self.engine) as db:
            job = db.get(DownloadJob, job_id)
            job.status = "running"
            db.add(job)
            db.commit()
        queue = DownloadQueue()
        with patch("app.services.download_jobs.engine", self.engine), patch("app.services.download_jobs.threading.Thread"), patch.object(settings, "DOWNLOAD_AUTO_UPDATE", False):
            queue.start()
        with Session(self.engine) as db:
            self.assertEqual(db.get(DownloadJob, job_id).status, "error")
            self.assertEqual(db.get(DownloadJob, queued).status, "queued")


class RunnerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required for conversion integration")
    def test_real_mp3_and_mp4_generation_with_local_media_fixture(self):
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        import yt_dlp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=0.3",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", str(source)], check=True, capture_output=True, timeout=30)
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=directory, **kwargs)
                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def fixture(downloader, url, download):
                self.assertEqual(url, "https://www.youtube.com/watch?v=" + ID)
                return downloader.process_ie_result({"id": ID, "title": "Conversion fixture", "ext": "mp4",
                        "url": f"http://127.0.0.1:{server.server_port}/fixture.mp4", "height": 180, "width": 320,
                        "vcodec": "h264", "acodec": "aac", "format_id": "test", "protocol": "http",
                        "webpage_url": url}, download=download)
            try:
                for kind in ("mp3", "mp4"):
                    destination = root / kind
                    destination.mkdir()
                    config = {"directory": str(destination), "video_id": ID, "format": kind, "resolution": 720, "max_bytes": 1024 * 1024}
                    with patch.object(yt_dlp.YoutubeDL, "extract_info", fixture):
                        self.assertEqual(run(config), 0, (destination / "result.json").read_text())
                    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
                                             "-of", "json", str(destination / ("media." + kind))],
                                            check=True, capture_output=True, text=True, timeout=30)
                    streams = json.loads(result.stdout)["streams"]
                    self.assertTrue(any(s["codec_type"] == "audio" for s in streams))
                    if kind == "mp4":
                        self.assertTrue(any(s["codec_type"] == "video" for s in streams))
                    else:
                        self.assertEqual(streams[0]["codec_name"], "mp3")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_selectors_have_audio_conversion_and_mp4_audio(self):
        config = {"directory": ".", "format": "mp3", "resolution": 720, "max_bytes": 1000}
        self.assertEqual(options(config, lambda _: None)["postprocessors"][0]["preferredcodec"], "mp3")
        config["format"] = "mp4"
        self.assertIn("+bestaudio[ext=m4a]", options(config, lambda _: None)["format"])
        self.assertIn("height<=720", options(config, lambda _: None)["format"])

    def test_runner_requires_final_file_and_canonicalizes_url(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"directory": directory, "video_id": ID, "format": "mp3", "resolution": 720, "max_bytes": 1000}
            mock = MagicMock()
            mock.__enter__.return_value.extract_info.return_value = {"title": "Test"}
            with patch("yt_dlp.YoutubeDL", return_value=mock):
                self.assertEqual(run(config), 1)
                self.assertIn("error", json.loads((Path(directory) / "result.json").read_text()))
                (Path(directory) / "media.mp3").write_bytes(b"audio")
                self.assertEqual(run(config), 0)
                self.assertEqual(mock.__enter__.return_value.extract_info.call_args.args[0], "https://www.youtube.com/watch?v=" + ID)

    def test_failed_update_preserves_active_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            updater = DownloadEngine()
            updater.root = Path(directory)
            baseline = updater.snapshot()
            with patch("app.services.download_engine.venv.create", side_effect=RuntimeError("offline")):
                self.assertFalse(updater.update())
            self.assertEqual(updater.snapshot(), baseline)
            self.assertTrue(updater.last_error)
            self.assertFalse(updater.updating)

    def test_update_activates_only_after_adapter_check_and_supports_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            updater = DownloadEngine()
            updater.root = Path(directory)
            previous = updater.root / "old" / "python"
            previous.parent.mkdir()
            previous.touch()
            (updater.root / "active.json").write_text(json.dumps({"python": "old/python", "version": "previous"}))
            def install(path, **kwargs):
                import os
                python = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                python.parent.mkdir(parents=True)
                python.touch()
            with patch("app.services.download_engine.venv.create", side_effect=install), patch("app.services.download_engine.subprocess.run", return_value=MagicMock(stdout='{"version":"new"}')):
                self.assertTrue(updater.update())
            self.assertEqual(updater.snapshot()[1], "new")
            self.assertTrue(updater.rollback())
            self.assertEqual(updater.snapshot()[1], "previous")
            with patch("app.services.download_engine.venv.create", side_effect=install), patch("app.services.download_engine.subprocess.run", side_effect=RuntimeError("incompatible adapter")):
                self.assertFalse(updater.update())
            self.assertEqual(updater.snapshot()[1], "previous")


if __name__ == "__main__":
    unittest.main()
