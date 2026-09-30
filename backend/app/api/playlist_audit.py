"""Read-only playlist inventory. Never edits playlist membership."""
from collections import Counter
import unicodedata
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from app.api.descriptions import channel_service
from app.api.acervo import acervo_owner
from app.database.db import get_session
from app.models.acervo_models import AcervoRecord

router = APIRouter(prefix="/playlist-audit", tags=["playlist-audit"])


def title_key(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def audit_playlists(service, events=()):
    playlists = service.list_playlists()
    channel_videos = service.list_all_video_resources()
    titles = Counter(title_key(p.get("snippet", {}).get("title", "")) for p in playlists)
    all_members = set()
    results = []
    for playlist in playlists:
        identifier = playlist["id"]
        items = []
        query = service.youtube.playlistItems().list(part="snippet,contentDetails,status", playlistId=identifier, maxResults=50)
        while query:
            response = query.execute()
            items.extend(response.get("items", []))
            query = service.youtube.playlistItems().list_next(query, response)
        ids = [i.get("contentDetails", {}).get("videoId") or i.get("snippet", {}).get("resourceId", {}).get("videoId") for i in items]
        counts = Counter(i for i in ids if i)
        all_members.update(counts)
        resources = {}
        unique = list(counts)
        for start in range(0, len(unique), 50):
            response = service.youtube.videos().list(part="snippet,status", id=",".join(unique[start:start+50])).execute()
            resources.update({v["id"]: v for v in response.get("items", [])})
        entries = []
        for item, video_id in zip(items, ids):
            video = resources.get(video_id)
            entries.append({"item_id": item["id"], "video_id": video_id,
                            "position": item.get("snippet", {}).get("position", len(entries)),
                            "title": (video or item).get("snippet", {}).get("title", "Vídeo indisponível"),
                            "unavailable": video is None,
                            "privacy": (video or {}).get("status", {}).get("privacyStatus", "unknown"),
                            "duplicate": counts.get(video_id, 0) > 1})
        expected = set()
        for event in events:
            payload = event.payload if hasattr(event, "payload") else event
            event_playlist = payload.get("playlist_id") or parse_qs(urlparse(str(payload.get("playlist_url", ""))).query).get("list", [""])[0]
            if event_playlist == identifier:
                raw = payload.get("video_ids", [])
                expected.update(raw if isinstance(raw, list) else [x.strip() for x in raw.replace(",", "\n").splitlines() if x.strip()])
        missing = sorted(expected - set(counts))
        results.append({"id": identifier, "title": playlist.get("snippet", {}).get("title", ""),
                        "privacy": playlist.get("status", {}).get("privacyStatus", "unknown"),
                        "items": entries, "empty": not entries,
                        "duplicate_title": titles[title_key(playlist.get("snippet", {}).get("title", ""))] > 1,
                        "duplicate_count": sum(count-1 for count in counts.values()),
                        "unavailable_count": sum(e["unavailable"] for e in entries),
                        "private_count": sum(e["privacy"] == "private" for e in entries),
                        "missing_expected": missing})
    return {"playlists": results, "unassigned": [{"id": v["id"], "title": v.get("snippet", {}).get("title", "")} for v in channel_videos if v["id"] not in all_members],
            "video_count": len(channel_videos)}


@router.get("/{channel_id}")
def audit(channel_id: str, request: Request, session: Session = Depends(get_session)):
    service = channel_service(channel_id, session, request)
    events = session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == acervo_owner(request), AcervoRecord.kind == "event")).all()
    try:
        return audit_playlists(service, [e for e in events if not e.payload.get("channel_id") or e.payload["channel_id"] == channel_id])
    except Exception as error:
        raise HTTPException(502, "Não foi possível concluir a auditoria das playlists. Tente novamente.") from error
