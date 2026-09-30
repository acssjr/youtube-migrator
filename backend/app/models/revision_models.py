from datetime import datetime
from uuid import uuid4
from sqlmodel import SQLModel, Field, Column, JSON


class MetadataRevision(SQLModel, table=True):
    __tablename__ = "metadata_revisions"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    owner_id: str = Field(index=True)
    channel_id: str = Field(index=True)
    video_id: str = Field(index=True)
    before_snippet: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    after_snippet: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="preview", index=True)
    error: str = ""
    restores_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
