from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database.db import get_session
from app.models.models import OAuthToken, CloudOAuthAccount
from app.services.description_service import propose
from app.services.youtube_service import YoutubeService
from app.services.cloud_session import cloud_mode, read_session, decode_token

router = APIRouter(prefix="/descriptions", tags=["descriptions"])


class IdentityOverride(BaseModel):
    work: str = ""
    composer: str = ""
    arranger: str = ""


class PreviewRequest(BaseModel):
    channel_id: str
    video_ids: list[str]
    overrides: dict[str, IdentityOverride] = Field(default_factory=dict)


class ApplyItem(BaseModel):
    video_id: str
    description: str = Field(min_length=1, max_length=5000)


class ApplyRequest(BaseModel):
    channel_id: str
    items: list[ApplyItem]


def channel_service(channel_id: str, session: Session, request: Request) -> YoutubeService:
    if cloud_mode():
        owner_id = read_session(request)["owner_id"]
        account = session.exec(select(CloudOAuthAccount).where(
            CloudOAuthAccount.owner_id == owner_id,
            CloudOAuthAccount.channel_id == channel_id)).first()
        if not account:
            raise HTTPException(403, "Este canal não está conectado nesta sessão.")
        return YoutubeService(decode_token(account.encrypted_token))
    record = session.exec(select(OAuthToken).where(OAuthToken.channel_id == channel_id)).first()
    if not record:
        raise HTTPException(404, "Canal não conectado.")
    return YoutubeService(record.token_data)


@router.get("/{channel_id}/empty")
def empty_videos(channel_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        videos = channel_service(channel_id, session, request).list_all_video_resources()
        return [{"id": v["id"], "title": v["snippet"]["title"],
                 "published_at": v["snippet"].get("publishedAt", ""),
                 "thumbnail_url": v["snippet"].get("thumbnails", {}).get("medium", {}).get("url", "")}
                for v in videos if not v["snippet"].get("description", "").strip()]
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, f"Falha ao consultar o canal: {error}") from error


@router.post("/preview")
def preview(payload: PreviewRequest, request: Request, session: Session = Depends(get_session)):
    if not payload.video_ids or len(payload.video_ids) > 50 or len(set(payload.video_ids)) != len(payload.video_ids):
        raise HTTPException(400, "Selecione entre 1 e 50 vídeos distintos.")
    try:
        service = channel_service(payload.channel_id, session, request)
        videos = service.list_all_video_resources()
        playlists = service.list_playlists()
        by_id = {v["id"]: v for v in videos}
        if any(video_id not in by_id or by_id[video_id]["snippet"].get("description", "").strip() for video_id in payload.video_ids):
            raise HTTPException(409, "A seleção contém vídeo externo ao canal ou com descrição preenchida.")
        from app.api.acervo import acervo_owner
        from app.models.acervo_models import AcervoRecord
        from app.services.approved_texts import enrich_proposal
        records = session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == acervo_owner(request), AcervoRecord.kind == "approved_text")).all()
        from app.services.description_structure import attach_structure
        presets = session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == acervo_owner(request), AcervoRecord.kind == "ensemble_preset")).all()
        return [attach_structure(enrich_proposal(propose(by_id[video_id], videos, payload.overrides.get(video_id).model_dump() if video_id in payload.overrides else None, playlists), records), videos, playlists, presets)
                for video_id in payload.video_ids]
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, f"Falha ao consultar o canal: {error}") from error


@router.post("/apply")
def apply(payload: ApplyRequest, request: Request, session: Session = Depends(get_session)):
    from app.api.revisions import publish_revision, owner
    if not payload.items or len(payload.items) > 50 or len({item.video_id for item in payload.items}) != len(payload.items):
        raise HTTPException(400, "Envie entre 1 e 50 vídeos distintos.")
    service = channel_service(payload.channel_id, session, request)
    try:
        owned = {v["id"] for v in service.list_all_video_resources()}
    except Exception as error:
        raise HTTPException(502, f"Falha ao verificar o canal: {error}") from error
    results = []
    for item in payload.items:
        if item.video_id not in owned:
            results.append({"video_id": item.video_id, "status": "error", "message": "Vídeo não pertence ao canal."})
            continue
        try:
            video = service.get_video_resource(item.video_id)
            if video["snippet"].get("description", "").strip():
                results.append({"video_id": item.video_id, "status": "skipped", "message": "Descrição já preenchida; nenhuma alteração feita."})
                continue
            publish_revision(session, service, payload.channel_id, owner(request), video, item.description)
            results.append({"video_id": item.video_id, "status": "updated", "message": "Descrição publicada."})
        except Exception as error:
            results.append({"video_id": item.video_id, "status": "error", "message": str(error)})
    return results
