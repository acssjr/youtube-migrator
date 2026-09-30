"""Editable institutional structure independent of music reference matching."""
import re
from app.services.description_service import (normalize, paragraphs, is_follow_block, is_institution_block,
    is_footer_block, current_links, published, retreta_playlist_ids, playlist_ids, complete_retreta_links,
    channel_retreta_playlists, institution_passage, ensemble_marker)


def ensemble_name(title):
    parts = re.split(r"\s+[|–—-]\s+", title)
    for part in reversed(parts):
        if re.search(r"filarm[oô]nica|sociedade|banda|orquestra|s\.?\s*f\.", part, re.I):
            return part.strip()
    return ""


def attach_structure(proposal, videos, playlists, presets):
    ensemble = ensemble_name(proposal["title"])
    references = sorted((v for v in videos if v.get("snippet", {}).get("description", "").strip()), key=published, reverse=True)
    main = [v for v in references if ensemble_marker(v["snippet"].get("title", "")) == "filarmonica 25 de marco"]
    link_sources = [v for v in (main or references) if current_links(v["snippet"]["description"])]
    latest = max(link_sources, key=lambda v: (len(retreta_playlist_ids(v["snippet"]["description"])), len(set(playlist_ids(v["snippet"]["description"]))), published(v)), default=None)
    footer = current_links(latest["snippet"]["description"]) if latest else ""
    retreta = channel_retreta_playlists(playlists, "filarmonica 25 de marco")
    for v in main:
        for pid in retreta_playlist_ids(v["snippet"]["description"]):
            if pid not in retreta: retreta.append(pid)
    footer = complete_retreta_links(footer, retreta)
    main_follow = next((p for v in main for p in paragraphs(v["snippet"]["description"]) if is_follow_block(p) and "25 de marco" in normalize(p)), "")
    preset = next((r.payload for r in presets if normalize(r.payload.get("name", "")) == normalize(ensemble) or (ensemble_marker(proposal["title"]) and ensemble_marker(r.payload.get("name", "")) == ensemble_marker(proposal["title"]))), {})
    ensemble = preset.get("name", ensemble)
    main_preset = next((r.payload for r in presets if ensemble_marker(r.payload.get("name", "")) == "filarmonica 25 de marco"), {})
    main_follow = main_preset.get("socialLinks", "") or main_follow
    marker = ensemble_marker(proposal["title"])
    history = preset.get("institutionalText", "") or next((p for v in references for p in paragraphs(v["snippet"]["description"]) if marker and normalize(p).startswith("sobre a ") and marker in normalize(p)[:200]), "")
    body = []
    for p in paragraphs(proposal["description"]):
        plain = normalize(p)
        if is_follow_block(p) or is_institution_block(p) or re.match(r"^sobre a (?:sociedade|banda|instituicao|filarmonica)\b", plain) or plain.startswith("esta partitura pertence") or plain.startswith("essa partitura pertence"):
            continue
        if plain.startswith(("sobre o compositor", "sobre o arranjador", "sobre a obra", "sobre a musica")) or not is_footer_block(p):
            body.append(p)
    return dict(proposal, structure={"ensemble": ensemble, "history": history, "social_text": preset.get("socialLinks", ""),
        "main_follow": main_follow, "playlists": "\n\n".join(p for p in paragraphs(footer) if not is_follow_block(p)),
        "body": "\n\n".join(body), "source": {"id": latest["id"], "title": latest["snippet"]["title"]} if latest else None})
