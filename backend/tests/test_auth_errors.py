import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from app.api.auth import get_auth_url, oauth_error
from app.services.auth_service import AuthService


class AuthErrorTests(unittest.TestCase):
    def test_missing_credentials_returns_service_error_instead_of_bad_url(self):
        with patch("app.api.auth.cloud_mode", return_value=False), patch.object(AuthService, "get_flow", side_effect=ValueError("missing")):
            with self.assertRaises(HTTPException) as error:
                get_auth_url("Channel")
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("GOOGLE_CLIENT_ID", error.exception.detail)

    def test_old_error_url_redirects_to_settings_with_readable_message(self):
        with patch("app.api.auth.cloud_mode", return_value=False), patch.dict("os.environ", {"FRONTEND_URL": "http://localhost:5173"}):
            response = oauth_error()
        parsed = urlparse(response.headers["location"])
        self.assertEqual(parsed.path, "/settings")
        self.assertEqual(parse_qs(parsed.query)["auth"], ["error"])
