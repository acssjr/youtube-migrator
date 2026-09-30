from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session
from app.database.db import get_session
from app.api.descriptions import channel_service
from app.services.approved_texts import published_blocks

router = APIRouter(prefix="/approved-texts", tags=["approved-texts"])


@router.get("/{channel_id}/{video_id}/blocks")
def blocks(channel_id: str, video_id: str, request: Request, response: Response,
           session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    service = channel_service(channel_id, session, request)
    video = service.get_video_resource(video_id)
    if video.get("snippet", {}).get("channelId") != channel_id:
        raise HTTPException(403, "O vídeo não pertence ao canal conectado.")
    return {"source_url": f"https://www.youtube.com/watch?v={video_id}",
            "title": video["snippet"].get("title", ""),
            "blocks": published_blocks(video["snippet"].get("description", ""))}
