"""Reviewable work suggestions from connected-channel titles only."""
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from app.database.db import get_session
from app.api.descriptions import channel_service
from app.services.description_service import normalize

router = APIRouter(prefix="/work-catalog", tags=["work-catalog"])
GENRES = ("Dobrado", "Marcha", "Maxixe", "Valsa", "Bolero", "Fantasia", "Suíte", "Polca", "Samba", "Hino", "Canção", "Choro")


def title_suggestion(video):
    title = video.get("snippet", {}).get("title", "")
    parts = [part.strip() for part in re.split(r"\s+[—–|]\s+", title) if part.strip()]
    name = parts[0] if parts else ""
    genre = ""
    for candidate in GENRES:
        match = re.match(re.escape(candidate) + r"\s+", name, re.I)
        if match:
            genre, name = candidate, name[match.end():]
            break
    composer, arranger = "", ""
    for part in parts[1:]:
        arranged = re.match(r"^(?:arr\.|arranjo)(?:\s+(?:de|por))?\s*:?\s*(.+)$", part, re.I)
        if arranged:
            arranger = arranged.group(1).strip()
        elif not composer and not re.search(r"filarm[oô]nica|banda|retreta|concerto|orquestra|casar[aã]o|noite", part, re.I):
            composer = part
    return {"name": name, "genre": genre, "composer": composer, "arranger": arranger,
            "aliases": "", "notes": "", "sources": [{"video_id": video["id"], "title": title,
            "url": "https://www.youtube.com/watch?v=" + video["id"]}]}


def suggestions(videos):
    grouped = {}
    for video in videos:
        item = title_suggestion(video)
        if not item["name"]:
            continue
        # Distinct composers/arrangers stay distinct even for identical work names.
        key = tuple(normalize(item[field]) for field in ("name", "composer", "arranger"))
        if key in grouped:
            grouped[key]["sources"].extend(item["sources"])
        else:
            grouped[key] = item
    return sorted(grouped.values(), key=lambda item: normalize(item["name"]))


@router.get("/{channel_id}/suggestions")
def channel_suggestions(channel_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        service = channel_service(channel_id, session, request)
        return suggestions(service.list_all_video_resources())
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Não foi possível consultar os títulos do canal.") from error
