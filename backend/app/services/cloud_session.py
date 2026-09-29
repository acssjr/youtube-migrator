"""Browser ownership and encrypted OAuth tokens for cloud accounts."""

import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request

from app.config.config import settings

COOKIE_NAME = "yt_acervo_owner"
COOKIE_AGE = 365 * 24 * 3600


def cloud_mode() -> bool:
    return bool(settings.VERCEL)


def cipher() -> Fernet:
    if not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET na Vercel.")
    digest = hashlib.sha256(("youtube-acervo-session:" + settings.GOOGLE_CLIENT_SECRET).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encode_session(data: dict) -> str:
    return cipher().encrypt(json.dumps(data).encode()).decode()


def read_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) != 43:
        raise HTTPException(401, "Conecte o canal em Configurações.")
    return {"owner_id": token}


def new_owner_id() -> str:
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> dict:
    try:
        return json.loads(cipher().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(401, "Credenciais inválidas. Conecte o canal novamente.")
