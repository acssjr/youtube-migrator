"""Combined archive search, with explicit provenance and no guessed event dates."""
import re
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select
from app.database.db import get_session
from app.models.acervo_models import AcervoRecord
from app.api.acervo import acervo_owner
from app.api.descriptions import channel_service
from app.services.description_service import identity, normalize, work_key

router = APIRouter(prefix="/acervo-search", tags=["acervo-search"])
GENRES = ("Dobrado", "Marcha", "Maxixe", "Valsa", "Bolero", "Fantasia", "Suíte", "Hino", "Polca", "Samba", "Choro", "Frevo", "Seleção", "Pot-pourri")


def build_catalog(videos, records, channel_id):
    works = [r.payload for r in records if r.kind == "work" and (not r.payload.get("channel_id") or r.payload["channel_id"] == channel_id)]
    events = [r.payload for r in records if r.kind == "event" and (not r.payload.get("channel_id") or r.payload["channel_id"] == channel_id)]
    def work_names(work):
        aliases = work.get("aliases", "")
        aliases = aliases if isinstance(aliases, list) else re.split(r"[;\n]", str(aliases))
        return [work.get("name", ""), *aliases]
    result = []
    for video in videos:
        snippet = video.get("snippet", {})
        if snippet.get("channelId") and snippet["channelId"] != channel_id:
            continue
        parsed = identity(video)
        # A saved source is stronger than title parsing. Never join by work name alone.
        matches = [w for w in works if any(s.get("video_id") == video["id"] for s in w.get("sources", []) if isinstance(s, dict))]
        if not matches and parsed["composer"]:
            matches = [w for w in works if any(work_key(name) == work_key(parsed["work"]) for name in work_names(w)) and normalize(w.get("composer", "")) == normalize(parsed["composer"]) and normalize(w.get("arranger", "")) == normalize(parsed["arranger"])]
        work = matches[0] if len(matches) == 1 else {}
        event_matches = [e for e in events if video["id"] in e.get("video_ids", [])]
        title_parts = re.split(r"\s+[|–—-]\s+", snippet.get("title", ""))
        ensemble = next((part for part in reversed(title_parts) if re.search(r"filarm[oô]nica|orquestra|banda", part, re.I)), "")
        genre = next((g for g in GENRES if normalize(parsed["work"]).startswith(normalize(g) + " ")), "")
        result.append({"id": video["id"], "title": snippet.get("title", ""), "description": snippet.get("description", ""),
            "work": work.get("name") or parsed["work"], "composer": work.get("composer") or parsed["composer"],
            "arranger": work.get("arranger") or parsed["arranger"], "genre": work.get("genre") or genre,
            "ensemble": ensemble, "published_at": snippet.get("publishedAt", ""),
            "events": [{"name": e.get("name", ""), "project": e.get("project", ""), "performed_at": e.get("performed_at", ""), "ensemble": e.get("ensemble", ""), "venue": e.get("venue", "")} for e in event_matches],
            "identity_source": "catalog" if work else "title", "catalog_ambiguous": len(matches) > 1})
    return result


def matches_filters(item, q="", work="", composer="", arranger="", ensemble="", genre="", project="", date_from="", date_to="", date_basis="published"):
    for field, value in (("work", work), ("composer", composer), ("arranger", arranger), ("genre", genre)):
        if value and normalize(value) not in normalize(item[field]):
            return False
    if ensemble and not any(normalize(ensemble) in normalize(value) for value in [item["ensemble"], *[e["ensemble"] for e in item["events"]]]):
        return False
    if project and not any(normalize(project) in normalize(e["name"] + " " + e["project"]) for e in item["events"]):
        return False
    if q and normalize(q) not in normalize(" ".join([item["title"], item["description"], item["work"], item["composer"], item["arranger"], *[e["name"] for e in item["events"]]])):
        return False
    dates = [e["performed_at"][:10] for e in item["events"] if e["performed_at"]] if date_basis == "performed" else [item["published_at"][:10]]
    return not (date_from or date_to) or any(d and (not date_from or d >= date_from) and (not date_to or d <= date_to) for d in dates)


@router.get("/{channel_id}")
def search(channel_id: str, request: Request, response: Response, q: str = "", work: str = "", composer: str = "", arranger: str = "", ensemble: str = "", genre: str = "", project: str = "", date_from: str = "", date_to: str = "", date_basis: str = "published", session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    if date_basis not in {"published", "performed"}:
        raise HTTPException(400, "Escolha a data de publicação ou da apresentação.")
    if any(value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in (date_from, date_to)) or (date_from and date_to and date_from > date_to):
        raise HTTPException(400, "Confira o intervalo de datas.")
    try:
        service = channel_service(channel_id, session, request)
        records = session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == acervo_owner(request))).all()
        catalog = build_catalog(service.list_all_video_resources(), records, channel_id)
        items = [item for item in catalog if matches_filters(item, q, work, composer, arranger, ensemble, genre, project, date_from, date_to, date_basis)]
        items.sort(key=lambda item: max((e["performed_at"] for e in item["events"]), default="") if date_basis == "performed" else item["published_at"], reverse=True)
        return {"items": items, "total": len(catalog)}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Não foi possível pesquisar o canal. Tente novamente.") from error
