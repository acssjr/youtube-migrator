"""Replace explicit playlist blocks while retaining all editorial prose verbatim."""
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session
from app.api.acervo import acervo_owner, record_for
from app.api.descriptions import channel_service
from app.database.db import get_session
from app.models.acervo_models import AcervoRecordVersion
from app.services.description_service import normalize, is_follow_block

router = APIRouter(prefix="/footer-templates", tags=["footer-templates"])


def safe_link_block(block: str) -> bool:
    """Never classify biographies or prose containing a URL as replaceable."""
    plain = normalize(block)
    if plain.startswith("sobre ") or is_follow_block(block):
        return False
    if re.match(r"^(?:projeto retreta|projeto musica no casarao|playlists?)(?:\b)", plain) and len(block) < 150 and not re.search(r"[.!?]\s+\w", block):
        return True
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and all(re.fullmatch(r"[^A-Za-z\n]*https?://(?:www\.)?(?:youtube\.com/playlist\?[^\s]+|youtu\.be/[^\s]+)\s*", line) for line in lines)


def replace_footer(description: str, template: str) -> tuple[str, str]:
    # Split without normalizing the contents of any retained paragraph.
    segments = re.split(r"(\r?\n[ \t]*\r?\n)", description)
    replaced = False
    output = []
    for index, segment in enumerate(segments):
        if index % 2 == 0 and safe_link_block(segment):
            if not replaced:
                output.append(template)
                replaced = True
            elif output and re.fullmatch(r"\r?\n[ \t]*\r?\n", output[-1]):
                output.pop()
        else:
            output.append(segment)
    result = "".join(output)
    if not replaced:
        result = description + ("\n\n" if description else "") + template
    # Follow is already the first block in approved descriptions; preserve it exactly.
    return result, "Blocos explícitos de playlists substituídos; demais textos preservados." if replaced else "Nenhum bloco seguro encontrado. O rodapé será acrescentado, sem apagar texto existente."


class FooterPreview(BaseModel):
    channel_id: str
    record_id: str
    version_id: str | None = None
    video_ids: list[str] = Field(min_length=1, max_length=50)


@router.post("/preview")
def preview(payload: FooterPreview, request: Request, session: Session = Depends(get_session)):
    from app.api.revisions import writable_snippet
    from app.models.revision_models import MetadataRevision
    owner = acervo_owner(request)
    record = record_for(session, payload.record_id, owner)
    if record.kind != "footer":
        raise HTTPException(400, "Selecione um rodapé.")
    template_data = record.payload
    if payload.version_id:
        version = session.get(AcervoRecordVersion, payload.version_id)
        if not version or version.owner_id != owner or version.record_id != record.id:
            raise HTTPException(404, "Versão não encontrada.")
        template_data = version.payload
    text = template_data.get("text", "")
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise HTTPException(400, "Preencha um rodapé de até 5000 caracteres.")
    if any(normalize(block).startswith("sobre ") or is_follow_block(block) for block in re.split(r"\n\s*\n", text)):
        raise HTTPException(400, "Guarde aqui apenas o rodapé de links. O SIGA e as biografias existentes serão preservados.")
    if len(set(payload.video_ids)) != len(payload.video_ids):
        raise HTTPException(400, "Selecione vídeos distintos.")
    service = channel_service(payload.channel_id, session, request)
    videos = {video["id"]: video for video in service.list_all_video_resources()}
    revisions, results = [], []
    for identifier in payload.video_ids:
        video = videos.get(identifier)
        if not video or video["snippet"].get("channelId") != payload.channel_id:
            raise HTTPException(403, "Vídeo fora do canal conectado.")
        ensemble = template_data.get("ensemble", "").strip()
        ensemble_key = re.sub(r"^(?:sociedade )?filarmonica ", "", normalize(ensemble))
        if ensemble_key and ensemble_key not in normalize(video["snippet"]["title"]):
            raise HTTPException(409, "A filarmônica do modelo não corresponde a um vídeo selecionado. Confira a seleção.")
        before = writable_snippet(video)
        after, warning = replace_footer(before["description"], text)
        if len(after) > 5000:
            raise HTTPException(400, "Uma descrição excederia 5000 caracteres.")
        revision = MetadataRevision(owner_id=owner, channel_id=payload.channel_id, video_id=identifier,
                                    before_snippet=before, after_snippet=dict(before, description=after))
        revisions.append(revision)
        results.append({"revision_id": revision.id, "video_id": identifier, "title": before["title"], "before": before["description"], "after": after, "warning": warning})
    session.add_all(revisions)
    session.commit()
    return results
