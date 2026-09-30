"""Criterion previews and explicitly reviewed playlist publication."""
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session
from app.api.descriptions import channel_service
from app.database.db import get_session
from app.services.description_service import identity, normalize, work_key

router = APIRouter(prefix="/smart-playlists", tags=["smart-playlists"])


class Criteria(BaseModel):
    work: str = Field(default="", max_length=200)
    composer: str = Field(default="", max_length=200)
    arranger: str = Field(default="", max_length=200)
    ensemble: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)


class Preview(BaseModel):
    channel_id: str
    criteria: Criteria = Field(default_factory=Criteria)


class Publish(Preview):
    title: str = Field(min_length=1, max_length=150)
    playlist_id: str | None = None
    privacy: Literal["private", "unlisted", "public"] = "private"
    video_ids: list[str] = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip() or "<" in value or ">" in value:
            raise ValueError("Informe um título válido.")
        return value.strip()


def ensemble_key(value):
    return re.sub(r"^(?:sociedade\s+)?filarmonica\s+", "", normalize(value))


def video_matches(video, criteria):
    known = identity(video)
    title = video.get("snippet", {}).get("title", "")
    if criteria.work and work_key(criteria.work) != work_key(known["work"]):
        return False
    for field in ("composer", "arranger"):
        expected = getattr(criteria, field)
        if expected and normalize(expected) != normalize(known[field]):
            return False
    # Ensemble credit must occur in the title, never in another band's biography.
    if criteria.ensemble:
        expected = ensemble_key(criteria.ensemble)
        if not expected or f" {expected} " not in f" {normalize(title)} ":
            return False
    if criteria.genre:
        genre = normalize(criteria.genre)
        if not genre or not normalize(known["work"]).startswith(genre + " "):
            return False
    return True


def matching_videos(service, criteria):
    seen, result = set(), []
    for video in service.list_all_video_resources():
        if video["id"] not in seen and video_matches(video, criteria):
            result.append(video)
            seen.add(video["id"])
    return result


@router.post("/preview")
def preview(payload: Preview, request: Request, response: Response, session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    service = channel_service(payload.channel_id, session, request)
    videos = matching_videos(service, payload.criteria)
    return {"videos": [{"id": v["id"], "title": v["snippet"]["title"], "published_at": v["snippet"].get("publishedAt", "")} for v in videos],
            "playlists": [{"id": p["id"], "title": p["snippet"]["title"]} for p in service.list_playlists()]}


@router.post("/publish")
def publish(payload: Publish, request: Request, session: Session = Depends(get_session)):
    service = channel_service(payload.channel_id, session, request)
    ids = list(dict.fromkeys(payload.video_ids))
    matching = {v["id"] for v in matching_videos(service, payload.criteria)}
    if any(identifier not in matching for identifier in ids):
        raise HTTPException(409, "Um vídeo deixou de corresponder aos critérios. Atualize a prévia.")
    owned = service.list_playlists()
    if payload.playlist_id:
        chosen = next((p for p in owned if p["id"] == payload.playlist_id), None)
        if not chosen:
            raise HTTPException(403, "Escolha uma playlist do canal conectado.")
        playlist_id, title = chosen["id"], chosen["snippet"]["title"]
        existing = set(service.playlist_video_ids(playlist_id))
    else:
        same_title = [p for p in owned if p["snippet"]["title"] == payload.title]
        if same_title:
            raise HTTPException(409, "Já existe uma playlist com este título. Selecione-a para adicionar os vídeos.")
        playlist_id = service.create_playlist(payload.title, privacy_status=payload.privacy)
        title = payload.title
        existing = set()
    results = []
    for identifier in ids:
        if identifier in existing:
            results.append({"video_id": identifier, "status": "existing"})
            continue
        try:
            service.add_video_to_playlist(playlist_id, identifier)
            existing.add(identifier)
            results.append({"video_id": identifier, "status": "added"})
        except Exception:
            results.append({"video_id": identifier, "status": "error", "message": "Não foi possível adicionar este vídeo. Você pode tentar novamente."})
    return {"id": playlist_id, "title": title, "url": f"https://www.youtube.com/playlist?list={playlist_id}", "items": results,
            "complete": all(item["status"] != "error" for item in results)}
