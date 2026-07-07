from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlmodel import Session, select

from app.schemas.schemas import VideoDiscoveryRequest, DiscoveryResponse, VideoInfo, PlaylistInfo
from app.services.downloader_service import DownloaderService
from app.database.db import get_session
from app.models.models import OAuthToken
from app.services.youtube_service import YoutubeService

router = APIRouter(prefix="/channels", tags=["channels"])
downloader_service = DownloaderService()

@router.post("/discover", response_model=DiscoveryResponse)
def discover_videos(payload: VideoDiscoveryRequest):
    """Discover videos and optional playlist metadata from a URL."""
    try:
        data = downloader_service.discover_videos(payload.source_url)
        
        playlist_data = None
        if data.get("playlist"):
            playlist_data = PlaylistInfo(**data["playlist"])
            
        videos_data = [VideoInfo(**v) for v in data["videos"]]
        
        return DiscoveryResponse(playlist=playlist_data, videos=videos_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{channel_id}/videos", response_model=List[VideoInfo])
def get_channel_videos(channel_id: str, session: Session = Depends(get_session)):
    """Fetch videos uploaded by a connected YouTube channel using its authenticated token."""
    token_record = session.exec(
        select(OAuthToken).where(OAuthToken.channel_id == channel_id)
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Channel not connected or authenticated.")
        
    try:
        yt_service = YoutubeService(token_record.token_data)
        videos = yt_service.list_channel_videos()
        return [VideoInfo(**v) for v in videos]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
