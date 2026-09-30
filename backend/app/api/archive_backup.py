"""Portable metadata backups. Imports affect Acervo records only."""
import csv
import io
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select
from app.api.acervo import KINDS, RecordCreate, acervo_owner, public_record
from app.api.descriptions import channel_service
from app.database.db import get_session
from app.models.acervo_models import AcervoRecord, AcervoRecordVersion
from app.models.revision_models import MetadataRevision

router = APIRouter(prefix="/archive-backup", tags=["archive-backup"])
FORMAT = "youtube-acervo-metadata"
SECRET_KEYS = {"owner_id", "token", "token_data", "access_token", "refresh_token", "client_secret", "credentials", "encrypted_token", "authorization", "cookie", "password", "api_key"}


def safe_tree(value, reject=False):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                if reject:
                    raise ValueError("O arquivo contém campos de credenciais. Use um backup de metadados.")
                continue
            result[key] = safe_tree(item, reject)
        return result
    if isinstance(value, list):
        return [safe_tree(item, reject) for item in value]
    return value


def fingerprint(kind, payload):
    return (kind, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def backup_date(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


class ImportRequest(BaseModel):
    archive: dict
    confirm: bool = False

    @field_validator("archive")
    @classmethod
    def valid_archive(cls, value):
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 20 * 1024 * 1024:
            raise ValueError("O backup excede 20 MB.")
        safe_tree(value, reject=True)
        if value.get("format") != FORMAT or value.get("version") != 1:
            raise ValueError("Formato ou versão de backup não reconhecido.")
        for collection in ("records", "record_versions"):
            entries = value.get(collection, [])
            if not isinstance(entries, list) or len(entries) > 50000:
                raise ValueError("Coleção de registros inválida.")
            for item in entries:
                if not isinstance(item, dict):
                    raise ValueError("Registro inválido.")
                RecordCreate(kind=item.get("kind"), payload=item.get("payload"))
                for key in ("created_at", "updated_at"):
                    if key in item:
                        backup_date(item[key])
                if collection == "records" and not isinstance(item.get("id"), str):
                    raise ValueError("Registro sem identificador.")
                if collection == "record_versions" and not isinstance(item.get("record_id"), str):
                    raise ValueError("Versão sem referência ao registro.")
        identifiers = [item["id"] for item in value.get("records", [])]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("O backup possui identificadores repetidos.")
        return value


@router.get("/export")
def export(request: Request, channel_id: str | None = None, session: Session = Depends(get_session)):
    owner = acervo_owner(request)
    archive = {"format": FORMAT, "version": 1, "exported_at": datetime.now(timezone.utc).isoformat(),
               "channel_id": channel_id, "videos": [], "playlists": [],
               "records": [safe_tree(public_record(item)) for item in session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == owner)).all()],
               "record_versions": [safe_tree(public_record(item)) for item in session.exec(select(AcervoRecordVersion).where(AcervoRecordVersion.owner_id == owner)).all()]}
    revision_query = select(MetadataRevision).where(MetadataRevision.owner_id == owner)
    if channel_id:
        revision_query = revision_query.where(MetadataRevision.channel_id == channel_id)
    archive["metadata_revisions"] = [safe_tree(public_record(item)) for item in session.exec(revision_query).all()]
    if channel_id:
        service = channel_service(channel_id, session, request)
        # Batch authoritative status alongside the exact published snippets.
        videos = service.list_all_video_resources()
        for start in range(0, len(videos), 50):
            ids = [item["id"] for item in videos[start:start + 50]]
            resources = service.youtube.videos().list(part="snippet,status", id=",".join(ids)).execute().get("items", [])
            archive["videos"].extend({"id": item["id"], "snippet": item.get("snippet", {}), "status": item.get("status", {})} for item in resources)
        for playlist in service.list_playlists():
            archive["playlists"].append({"id": playlist["id"], "snippet": playlist.get("snippet", {}), "status": playlist.get("status", {}), "video_ids": service.playlist_video_ids(playlist["id"])})
    body = json.dumps(archive, ensure_ascii=False, default=lambda item: item.isoformat(), indent=2)
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="acervo-metadados.json"', "Cache-Control": "no-store"})


def csv_cell(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/csv")
def export_csv(channel_id: str, request: Request, session: Session = Depends(get_session)):
    service = channel_service(channel_id, session, request)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["video_id", "titulo", "descricao", "publicado_em", "url"])
    for video in service.list_all_video_resources():
        snippet = video.get("snippet", {})
        writer.writerow([csv_cell(value) for value in (video["id"], snippet.get("title"), snippet.get("description"), snippet.get("publishedAt"), "https://www.youtube.com/watch?v=" + video["id"])])
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="acervo-metadados.csv"', "Cache-Control": "no-store"})


@router.post("/import")
def import_backup(payload: ImportRequest, request: Request, session: Session = Depends(get_session)):
    owner = acervo_owner(request)
    existing = session.exec(select(AcervoRecord).where(AcervoRecord.owner_id == owner)).all()
    known = {fingerprint(item.kind, item.payload): item.id for item in existing}
    id_map = {}
    additions = []
    skipped = 0
    for item in payload.archive.get("records", []):
        key = fingerprint(item["kind"], item["payload"])
        if key in known:
            id_map[item["id"]] = known[key]; skipped += 1
        else:
            record = AcervoRecord(owner_id=owner, kind=item["kind"], payload=item["payload"])
            for key in ("created_at", "updated_at"):
                if item.get(key):
                    setattr(record, key, backup_date(item[key]))
            additions.append(record); known[key] = record.id; id_map[item["id"]] = record.id
    existing_versions = session.exec(select(AcervoRecordVersion).where(AcervoRecordVersion.owner_id == owner)).all()
    version_known = {(item.record_id, *fingerprint(item.kind, item.payload)) for item in existing_versions}
    historical_targets = {fingerprint(item.kind, item.payload): item.record_id for item in existing_versions}
    versions = []
    for item in payload.archive.get("record_versions", []):
        target = id_map.setdefault(item["record_id"], historical_targets.get(fingerprint(item["kind"], item["payload"]), uuid.uuid4().hex))
        key = (target, *fingerprint(item["kind"], item["payload"]))
        if key in version_known:
            continue
        version_known.add(key)
        version = AcervoRecordVersion(owner_id=owner, record_id=target, kind=item["kind"], payload=item["payload"])
        if item.get("created_at"):
            version.created_at = backup_date(item["created_at"])
        versions.append(version)
    if payload.confirm:
        for item in additions + versions:
            session.add(item)
        session.commit()
    return {"imported": payload.confirm, "new_records": len(additions), "duplicate_records": skipped, "historical_versions": len(versions), "youtube_changes": 0}
