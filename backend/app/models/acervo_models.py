from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field, Column, JSON


class AcervoRecord(SQLModel, table=True):
    __tablename__ = "acervo_records"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(index=True)
    kind: str = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AcervoRecordVersion(SQLModel, table=True):
    __tablename__ = "acervo_record_versions"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    record_id: str = Field(index=True)
    owner_id: str = Field(index=True)
    kind: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
