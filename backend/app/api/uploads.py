"""Metadata preparation and short-lived authorization for browser-to-YouTube uploads."""

from urllib.parse import urlparse
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.api.descriptions import IdentityOverride, channel_service
from app.database.db import get_session
from app.services.description_service import identity, propose

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadDraft(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    identity: IdentityOverride = Field(default_factory=IdentityOverride)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value: str) -> str:
        if not value.strip() or "<" in value or ">" in value:
            raise ValueError("Use um título preenchido, sem < ou >.")
        return value.strip()


class PreviewUploads(BaseModel):
    channel_id: str
    items: list[UploadDraft] = Field(min_length=1, max_length=50)


class AuthorizeUpload(BaseModel):
    channel_id: str


def published_person_name(value: str) -> str:
    """Extract a name, never a full biography or a fragment from 'compositores'."""
    name = re.split(r"\s+(?:foi|é|era|nasceu|nascido|atuou|teve|interpretado|interpretada|compositor|regente)\b|,", value, maxsplit=1, flags=re.I)[0].strip()
    if not name or not name[0].isupper() or len(name) > 100 or len(name.split()) > 8:
        return ""
    return name


@router.get("/{channel_id}/catalog")
def catalog(channel_id: str, request: Request, response: Response, session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    service = channel_service(channel_id, session, request)
    try:
        videos = service.list_all_video_resources()
        composers, arrangers, ensembles = set(), set(), set()
        for video in videos:
            known = identity(video)
            if name := published_person_name(known["composer"]):
                composers.add(name)
            if name := published_person_name(known["arranger"]):
                arrangers.add(name)
            for part in re.split(r"\s+[|–—-]\s+", video.get("snippet", {}).get("title", "")):
                if re.match(r"^(?:Sociedade\s+)?Filarm[oô]nica\s+", part.strip(), re.I):
                    # Keep the published spelling; an event suffix is not part of the name.
                    name = re.split(r"\s*\(", part.strip(), maxsplit=1)[0].strip()
                    ensembles.add(name)
        return {"composers": sorted(composers, key=str.casefold),
                "arrangers": sorted(arrangers, key=str.casefold),
                "ensembles": sorted(ensembles, key=str.casefold)}
    except Exception as error:
        raise HTTPException(502, "Não foi possível carregar os nomes do acervo.") from error


@router.post("/preview")
def preview(payload: PreviewUploads, request: Request, session: Session = Depends(get_session)):
    if len({item.id for item in payload.items}) != len(payload.items):
        raise HTTPException(400, "Os arquivos devem ter identificadores distintos.")
    service = channel_service(payload.channel_id, session, request)
    try:
        videos = service.list_all_video_resources()
        playlists = service.list_playlists()
        # A local draft has no YouTube ID yet. Reuse the same conservative matching rules.
        return [propose({"id": item.id, "snippet": {"title": item.title, "description": ""}},
                        videos, item.identity.model_dump(), playlists) for item in payload.items]
    except Exception as error:
        raise HTTPException(502, "Não foi possível consultar o acervo para este lote.") from error


@router.post("/authorize")
def authorize(payload: AuthorizeUpload, request: Request, response: Response,
              session: Session = Depends(get_session)):
    # The upload bearer is returned only to our own browser origin and never cached.
    origin = urlparse(request.headers.get("origin", ""))
    local = origin.hostname in {"localhost", "127.0.0.1"} and request.url.hostname in {"localhost", "127.0.0.1"}
    if not origin.hostname or (not local and (origin.hostname != request.url.hostname or origin.scheme != "https")):
        raise HTTPException(403, "Inicie o envio pela página do Acervo.")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    service = channel_service(payload.channel_id, session, request)
    credentials = service.credentials
    scopes = set(credentials.scopes or [])
    if not scopes.intersection({"https://www.googleapis.com/auth/youtube.upload",
                                "https://www.googleapis.com/auth/youtube",
                                "https://www.googleapis.com/auth/youtube.force-ssl"}):
        raise HTTPException(403, "Reconecte este canal para autorizar uploads.")
    try:
        if credentials.refresh_token:
            credentials.refresh(GoogleRequest())
        elif not credentials.valid:
            raise ValueError("expired")
    except Exception as error:
        raise HTTPException(401, "A autorização expirou. Reconecte o canal em Configurações.") from error
    if not credentials.token:
        raise HTTPException(401, "Reconecte o canal em Configurações.")
    return {"access_token": credentials.token}
