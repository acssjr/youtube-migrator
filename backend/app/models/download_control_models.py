"""Owner-scoped persistent queue preferences, without changing existing jobs."""
from sqlmodel import SQLModel, Field


class DownloadQueueControl(SQLModel, table=True):
    __tablename__ = "download_queue_controls"
    owner_id: str = Field(primary_key=True)
    paused: bool = False


class DownloadJobControl(SQLModel, table=True):
    __tablename__ = "download_job_controls"
    job_id: str = Field(primary_key=True)
    owner_id: str = Field(index=True)
    cancelled: bool = False
    position: int = 0
