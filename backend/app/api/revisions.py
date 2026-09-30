"""Durable metadata snapshots. Import publish_revision in descriptions.apply.

publish_revision(session, service, channel_id, owner_id, video, description,
                 title=None) commits the snapshot BEFORE a YouTube write.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from app.api.descriptions import channel_service
from app.database.db import get_session
from app.models.revision_models import MetadataRevision
from app.services.cloud_session import cloud_mode, read_session

router = APIRouter(prefix="/revisions", tags=["revisions"])
WRITABLE = ("title", "description", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage")


def writable_snippet(video):
    snippet = video["snippet"]
    result = {key: snippet[key] for key in WRITABLE if key in snippet}
    result.setdefault("description", "")
    # Missing and empty tag lists mean the same thing in the API.
    result.setdefault("tags", [])
    return result


def owner(request):
    return read_session(request)["owner_id"] if cloud_mode() else "local"


def assert_owned(video, channel_id):
    if video.get("snippet", {}).get("channelId") != channel_id:
        raise HTTPException(403, "O vídeo não pertence ao canal conectado.")


def write_snapshot(session, service, revision):
    revision.status = "pending"
    revision.updated_at = datetime.utcnow()
    session.add(revision)
    session.commit()
    try:
        service.youtube.videos().update(part="snippet", body={
            "id": revision.video_id, "snippet": revision.after_snippet}).execute()
        revision.status = "applied"
    except Exception:
        # A network error can happen after YouTube committed; retain the snapshot.
        revision.status = "failed"
        revision.error = "A API não confirmou a publicação. Confira o vídeo antes de tentar novamente."
        session.add(revision)
        session.commit()
        raise
    revision.updated_at = datetime.utcnow()
    session.add(revision)
    session.commit()
    return revision


def publish_revision(session, service, channel_id, owner_id, video, description, title=None):
    assert_owned(video, channel_id)
    before = writable_snippet(video)
    after = dict(before, description=description)
    if title is not None:
        after["title"] = title
    revision = MetadataRevision(owner_id=owner_id, channel_id=channel_id,
                                video_id=video["id"], before_snippet=before, after_snippet=after)
    return write_snapshot(session, service, revision)


class Change(BaseModel):
    video_id: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=5000)
    title: str | None = Field(default=None, min_length=1, max_length=100)


class Preview(BaseModel):
    channel_id: str
    items: list[Change] = Field(min_length=1, max_length=50)


class Apply(BaseModel):
    channel_id: str
    revision_ids: list[str] = Field(min_length=1, max_length=50)


def find_revision(session, identifier, channel_id, owner_id):
    revision = session.get(MetadataRevision, identifier)
    if not revision or revision.owner_id != owner_id or revision.channel_id != channel_id:
        raise HTTPException(404, "Revisão não encontrada neste canal.")
    return revision


@router.get("/{channel_id}", response_model=list[MetadataRevision], response_model_exclude={"__all__": {"owner_id"}})
def history(channel_id: str, request: Request, session: Session = Depends(get_session)):
    channel_service(channel_id, session, request)
    records = session.exec(select(MetadataRevision).where(
        MetadataRevision.owner_id == owner(request), MetadataRevision.channel_id == channel_id
    ).order_by(MetadataRevision.created_at.desc()).limit(200)).all()
    return records


@router.get("/{channel_id}/videos")
def videos(channel_id: str, request: Request, session: Session = Depends(get_session)):
    service = channel_service(channel_id, session, request)
    return [{"id": video["id"], "title": video["snippet"]["title"],
             "description": video["snippet"].get("description", "")}
            for video in service.list_all_video_resources()]


@router.post("/preview", response_model=list[MetadataRevision], response_model_exclude={"__all__": {"owner_id"}})
def preview(payload: Preview, request: Request, session: Session = Depends(get_session)):
    if len({item.video_id for item in payload.items}) != len(payload.items):
        raise HTTPException(400, "Selecione vídeos distintos.")
    service = channel_service(payload.channel_id, session, request)
    revisions = []
    for item in payload.items:
        if item.title is not None and (not item.title.strip() or "<" in item.title or ">" in item.title):
            raise HTTPException(400, "Confira o título do vídeo.")
        video = service.get_video_resource(item.video_id)
        assert_owned(video, payload.channel_id)
        before = writable_snippet(video)
        after = dict(before, description=item.description)
        if item.title is not None:
            after["title"] = item.title
        revisions.append(MetadataRevision(owner_id=owner(request), channel_id=payload.channel_id,
                         video_id=item.video_id, before_snippet=before, after_snippet=after))
    session.add_all(revisions)
    session.commit()
    return revisions


@router.post("/apply")
def apply(payload: Apply, request: Request, session: Session = Depends(get_session)):
    if len(set(payload.revision_ids)) != len(payload.revision_ids):
        raise HTTPException(400, "Selecione revisões distintas.")
    service = channel_service(payload.channel_id, session, request)
    revisions = [find_revision(session, rid, payload.channel_id, owner(request)) for rid in payload.revision_ids]
    # Validate all previews before publishing the first one; later API errors return per-item results.
    for revision in revisions:
        if revision.status != "preview":
            raise HTTPException(409, "Esta revisão já foi processada. Gere uma nova prévia.")
        current = service.get_video_resource(revision.video_id)
        assert_owned(current, payload.channel_id)
        if writable_snippet(current) != revision.before_snippet:
            raise HTTPException(409, "O vídeo mudou desde a prévia. Gere uma nova comparação.")
    results = []
    for revision in revisions:
        try:
            write_snapshot(session, service, revision)
            results.append({"id": revision.id, "status": "applied"})
        except Exception:
            results.append({"id": revision.id, "status": "failed", "message": revision.error})
    return results


@router.post("/{channel_id}/{revision_id}/restore", response_model=MetadataRevision, response_model_exclude={"owner_id"})
def restore(channel_id: str, revision_id: str, request: Request, session: Session = Depends(get_session)):
    service = channel_service(channel_id, session, request)
    revision = find_revision(session, revision_id, channel_id, owner(request))
    if revision.status not in {"applied", "failed", "pending"}:
        raise HTTPException(409, "Esta revisão não pode ser restaurada.")
    current = service.get_video_resource(revision.video_id)
    assert_owned(current, channel_id)
    if writable_snippet(current) != revision.after_snippet:
        raise HTTPException(409, "O vídeo mudou depois desta revisão. A restauração foi bloqueada para preservar suas alterações.")
    rollback = MetadataRevision(owner_id=owner(request), channel_id=channel_id,
        video_id=revision.video_id, before_snippet=revision.after_snippet,
        after_snippet=revision.before_snippet, restores_id=revision.id)
    try:
        write_snapshot(session, service, rollback)
    except Exception as error:
        raise HTTPException(502, rollback.error) from error
    revision.status = "restored"
    revision.updated_at = datetime.utcnow()
    session.add(revision)
    session.commit()
    return rollback
