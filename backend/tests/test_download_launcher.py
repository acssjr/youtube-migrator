import base64
import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlparse

spec = importlib.util.spec_from_file_location("launcher", Path(__file__).resolve().parents[2] / "run_downloads.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def link(self, payload):
        data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return "ytacervo://prepare?data=" + data

    def test_valid_transfer_is_clean_and_autostarts(self):
        payload = {"sources": ["abcdefghijk"], "format": "mp3", "resolution": 1080, "command": "unsafe"}
        target = launcher.transfer_url(self.link(payload))
        self.assertEqual(urlparse(target).netloc, "127.0.0.1:8011")
        clean = json.loads(parse_qs(urlparse(target).fragment)["transfer"][0])
        self.assertEqual(clean, {"sources": ["abcdefghijk"], "format": "mp3", "resolution": 1080, "autostart": True})

    def test_rejects_commands_urls_and_invalid_settings(self):
        for argument in ["https://evil.example", "ytacervo://prepare?data=bad!", self.link({"sources": ["https://evil.example"], "format": "mp3", "resolution": 1080}), self.link({"sources": [], "format": "mp3", "resolution": 1080}), self.link({"sources": ["abcdefghijk"], "format": "exe", "resolution": 1080})]:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                launcher.transfer_url(argument)

    def test_regular_launch_does_not_start_jobs(self):
        self.assertEqual(launcher.transfer_url(), "http://127.0.0.1:8011/downloads")
