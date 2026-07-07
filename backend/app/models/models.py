from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON

class OAuthToken(SQLModel, table=True):
    __tablename__ = "oauth_tokens"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    account_name: str = Field(index=True) # e.g. "Conta Pessoal", "Conta da Filarmonica"
    channel_id: str = Field(index=True)
    channel_title: str
    token_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class MigrationTask(SQLModel, table=True):
    __tablename__ = "migration_tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: str = Field(index=True)
    title: str
    description: Optional[str] = None
    tags: Optional[str] = None # Comma-separated or serialized
    category_id: Optional[str] = None
    language: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    source_channel_id: str
    source_channel_title: str
    target_channel_id: str
    target_channel_title: Optional[str] = None
    
    # pending, downloading, uploading, completed, error
    status: str = Field(default="pending", index=True)
    progress: float = Field(default=0.0) # 0 to 100
    error_message: Optional[str] = None
    
    privacy_status: str = Field(default="private") # public, unlisted, private
    scheduled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    temp_file_path: Optional[str] = None
    target_playlist_id: Optional[str] = None

class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"
    
    key: str = Field(primary_key=True)
    value: str
