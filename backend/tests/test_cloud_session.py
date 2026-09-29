import unittest

from starlette.requests import Request

from app.config.config import settings
from app.services.cloud_session import COOKIE_NAME, encode_session, decode_token, read_session, new_owner_id


class CloudSessionTests(unittest.TestCase):
    def test_encrypted_cookie_round_trip_and_rejects_tampering(self):
        original = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_SECRET = "test-only-secret"
        try:
            value = encode_session({"refresh_token": "private"})
            self.assertNotIn("private", value)
            self.assertEqual(decode_token(value)["refresh_token"], "private")
            owner_id = new_owner_id()
            request = Request({"type": "http", "headers": [(b"cookie", f"{COOKIE_NAME}={owner_id}".encode())]})
            self.assertEqual(read_session(request)["owner_id"], owner_id)
            corrupted = value[:-2] + "zz"
            with self.assertRaises(Exception):
                decode_token(corrupted)
        finally:
            settings.GOOGLE_CLIENT_SECRET = original


if __name__ == "__main__":
    unittest.main()
