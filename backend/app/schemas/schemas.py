from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# Auth Schemas
class AuthURLResponse(BaseModel):
    url: str

class CallbackRequest(BaseModel):
    code: str
    state: str
    account_name: str

class AccountResponse(BaseModel):
    id: int
    account_name: str
    channel_id: str
    channel_title: str
    created_at: datetime

# YouTube Discovery Schemas
class VideoDiscoveryRequest(BaseModel):
    # Can be channel URL, playlist URL, comma-separated list of URLs, or video IDs
    source_url: str

class VideoInfo(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[str] = None # e.g. "10:30" or "PT10M30S"
    published_at: Optional[str] = None
    view_count: Optional[int] = 0
    status: Optional[str] = None
    playlist_title: Optional[str] = None
    tags: Optional[List[str]] = []
    category_id: Optional[str] = None
    default_language: Optional[str] = None

class PlaylistInfo(BaseModel):
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_count: int

class DiscoveryResponse(BaseModel):
    playlist: Optional[PlaylistInfo] = None
    videos: List[VideoInfo]

# Migration Task Schemas
class TaskCreateRequest(BaseModel):
    video_id: str
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    category_id: Optional[str] = "22" # Default category (People & Blogs)
    language: Optional[str] = "pt"
    thumbnail_url: Optional[str] = None
    
    source_channel_id: str
    source_channel_title: str
    target_channel_id: str
    privacy_status: str = "private" # public, unlisted, private
    scheduled_at: Optional[datetime] = None

class QueueMigrationRequest(BaseModel):
    tasks: List[TaskCreateRequest]
    create_playlist: Optional[bool] = False
    playlist_name: Optional[str] = None
    playlist_description: Optional[str] = ""
    playlist_privacy: Optional[str] = "private"
    playlist_thumbnail_url: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    video_id: str
    title: str
    description: Optional[str] = None
    tags: Optional[str] = None
    category_id: Optional[str] = None
    language: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    source_channel_id: str
    source_channel_title: str
    target_channel_id: str
    target_channel_title: Optional[str] = None
    
    status: str
    progress: float
    error_message: Optional[str] = None
    privacy_status: str
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# Settings Schemas
class SettingsUpdateRequest(BaseModel):
    default_account_id: Optional[str] = None
    default_channel_id: Optional[str] = None
    temp_downloads_dir: Optional[str] = None
    theme: Optional[str] = "dark" # "light" or "dark"

class SettingsResponse(BaseModel):
    settings: dict
