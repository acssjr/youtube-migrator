from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select
from app.database.db import get_session
from app.models.acervo_models import AcervoRecord, AcervoRecordVersion
from app.services.cloud_session import cloud_mode, read_session

router = APIRouter(prefix="/acervo", tags=["acervo"])
KINDS = {"work", "performance", "event", "ensemble_preset", "approved_text", "footer", "alias", "original", "favorite", "preferences", "backup", "note"}


def acervo_owner(request: Request) -> str:
    return read_session(request)["owner_id"] if cloud_mode() else "local"


class RecordCreate(BaseModel):
    kind: str
    payload: dict

    @field_validator("kind")
    @classmethod
    def known_kind(cls, value):
        if value not in KINDS:
            raise ValueError("Tipo de registro inválido.")
        return value

    @field_validator("payload")
    @classmethod
    def valid_payload(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 200000:
            raise ValueError("Registro muito grande.")
        return value


class RecordUpdate(BaseModel):
    payload: dict
    expected_updated_at: str | None = None
    _valid = field_validator("payload")(RecordCreate.valid_payload.__func__)


def record_for(session, identifier, owner_id):
    record = session.get(AcervoRecord, identifier)
    if not record or record.owner_id != owner_id:
        raise HTTPException(404, "Registro não encontrado.")
    return record


def snapshot(session, record):
    session.add(AcervoRecordVersion(record_id=record.id, owner_id=record.owner_id, kind=record.kind, payload=dict(record.payload)))


def public_record(record):
    return record.model_dump(exclude={"owner_id"})


@router.get("/records")
def records(request: Request, response: Response, kind: str | None = None, session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    statement = select(AcervoRecord).where(AcervoRecord.owner_id == acervo_owner(request))
    if kind:
        if kind not in KINDS:
            raise HTTPException(400, "Tipo de registro inválido.")
        statement = statement.where(AcervoRecord.kind == kind)
    return [public_record(record) for record in session.exec(statement.order_by(AcervoRecord.updated_at.desc())).all()]


@router.post("/records", status_code=201)
def create(payload: RecordCreate, request: Request, session: Session = Depends(get_session)):
    record = AcervoRecord(owner_id=acervo_owner(request), kind=payload.kind, payload=payload.payload)
    session.add(record); session.commit(); session.refresh(record)
    return public_record(record)


@router.patch("/records/{identifier}")
def update(identifier: str, payload: RecordUpdate, request: Request, session: Session = Depends(get_session)):
    record = record_for(session, identifier, acervo_owner(request))
    if payload.expected_updated_at and record.updated_at.isoformat() != payload.expected_updated_at:
        raise HTTPException(409, "O registro mudou. Recarregue antes de salvar.")
    snapshot(session, record)
    record.payload = payload.payload; record.updated_at = datetime.utcnow()
    session.add(record); session.commit(); session.refresh(record)
    return public_record(record)


@router.delete("/records/{identifier}")
def remove(identifier: str, request: Request, session: Session = Depends(get_session)):
    record = record_for(session, identifier, acervo_owner(request))
    snapshot(session, record); session.delete(record); session.commit()
    return {"deleted": True}


@router.get("/records/{identifier}/versions")
def versions(identifier: str, request: Request, session: Session = Depends(get_session)):
    return [public_record(record) for record in session.exec(select(AcervoRecordVersion).where(AcervoRecordVersion.record_id == identifier,
                        AcervoRecordVersion.owner_id == acervo_owner(request)).order_by(AcervoRecordVersion.created_at.desc())).all()]
