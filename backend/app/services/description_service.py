"""Conservative, explainable reuse of descriptions already published by a channel."""

import re
import unicodedata
from difflib import SequenceMatcher


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def work_key(value: str) -> str:
    plain = normalize(value)
    plain = re.sub(r"^(?:dobrado|marcha|maxixe|valsa|fantasia|suite|bolero)\s+", "", plain)
    plain = re.sub(r"^(?:n|no|numero)\s*\d+\s+", "", plain)
    return plain


def identity(video: dict, override: dict | None = None) -> dict:
    override = override or {}
    title = video.get("snippet", {}).get("title", "")
    # Titles normally put the work before a separator and credits after it.
    parts = re.split(r"\s+[|–—-]\s+", title)
    work = override.get("work") or parts[0]
    composer = override.get("composer") or ""
    arranger = override.get("arranger") or ""
    text = title + "\n" + video.get("snippet", {}).get("description", "")[:1200]
    if not composer:
        for part in parts[1:]:
            candidate = re.split(r"\s*\(", part, maxsplit=1)[0].strip()
            words = candidate.split()
            if (2 <= len(words) <= 4 and all(word[:1].isupper() for word in words)
                    and not re.search(r"banda|filarm[oô]nica|retreta|concerto|apresenta[cç][aã]o|casar[aã]o|orquestra|projeto", candidate, re.I)):
                composer = candidate
                break
        if not composer:
            match = re.search(r"(?:composi(?:ç|c)[aã]o|compositor|comp\.?|m[uú]sica\s+de)\s*[:\-–]?\s*([^\n|;]+)", text, re.I)
            if match:
                composer = match.group(1).strip()
    if not arranger:
        match = re.search(r"(?:arranjo|arr\.)\s*(?:de|por|:)?\s*([^\n|;\)–—]+)", text, re.I)
        if match:
            arranger = match.group(1).strip()
    return {"work": work.strip(), "composer": composer.strip(), "arranger": arranger.strip()}


def paragraphs(description: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", description or "") if p.strip()]


def is_footer_block(paragraph: str) -> bool:
    if is_institution_block(paragraph):
        return False
    if re.search(r"https?://|youtube\.com/playlist|youtu\.be/", paragraph, re.I):
        return True
    plain = normalize(paragraph)
    return bool(re.search(r"^(?:playlists?\b|assista (?:tambem|mais)\b|musica no casarao\b|projeto retreta\b|"
                          r"(?:apaixonado por musica de filarmonica|explore minhas playlists|projeto musica no casarao)\b)", plain))


def is_institution_block(paragraph: str) -> bool:
    return bool(re.match(r"^sobre a (?:sociedade )?filarmonica\b", normalize(paragraph)))


def institution_passage(description: str, ensemble: str) -> str:
    """Reuse the institution's published text, without an age that goes stale."""
    if not ensemble:
        return ""
    for paragraph in paragraphs(description):
        plain = normalize(paragraph)
        if not any(plain.startswith(prefix + ensemble + " ") for prefix in ("sobre a ", "sobre a sociedade ")):
            continue
        paragraph = re.sub(r"(?m)^\s*_{3,}\s*$", "", paragraph).strip()
        paragraph = re.sub(r"\bCom\s+(?:mais\s+de\s+)?\d+\s+anos\s+de\s+hist[oó]ria\s*,", "Ao longo de sua história,", paragraph, flags=re.I)
        paragraph = re.sub(r"\bCom\s+(?:mais\s+de\s+)?\d+\s+anos\s+de\s+hist[oó]ria\s*\.", "", paragraph, flags=re.I).strip()
        if paragraph and not paragraph.endswith(":") and len(paragraph) <= 2000 and not event_specific(paragraph):
            return paragraph
    return ""


def current_links(description: str, ensemble: str = "") -> str:
    """Keep only link/playlist blocks from the newest description, never its work trivia."""
    selected = []
    for paragraph in paragraphs(description):
        if not is_footer_block(paragraph):
            continue
        plain = normalize(paragraph)
        # A video from our channel can still promote a guest filarmônica.
        if ensemble and re.search(r"\bsiga\s+(?:a\s+)?(?:sociedade\s+)?filarmonica\b", plain):
            if ensemble not in plain:
                continue
        selected.append(paragraph)
    if not any(re.search(r"https?://", paragraph, re.I) for paragraph in selected):
        return ""
    return "\n\n".join(selected)


def is_follow_block(paragraph: str) -> bool:
    return bool(re.search(r"^siga\s+(?:a\s+)?(?:sociedade\s+)?filarmonica\b", normalize(paragraph)))


def playlist_ids(paragraph: str) -> list[str]:
    return re.findall(r"[?&]list=([A-Za-z0-9_-]+)", paragraph)


def retreta_playlist_ids(description: str) -> list[str]:
    """Read playlist links only inside a published Projeto Retreta section."""
    found = []
    in_retreta = False
    for paragraph in paragraphs(description):
        plain = normalize(paragraph)
        if plain.startswith("projeto retreta"):
            in_retreta = True
            continue
        if in_retreta and plain.startswith("projeto "):
            in_retreta = False
        if in_retreta:
            found.extend(playlist_ids(paragraph))
    return list(dict.fromkeys(found))


def channel_retreta_playlists(playlists: list[dict], ensemble: str) -> list[str]:
    """Use public Retreta nights for this ensemble, in performance order."""
    nights = {}
    for playlist in playlists:
        title = normalize(playlist.get("snippet", {}).get("title", ""))
        if (not title.startswith("retreta ") or not ensemble or ensemble not in title
                or playlist.get("status", {}).get("privacyStatus") != "public"):
            continue
        match = re.search(r"\b(\d+)\s*(?:a|o)?\s+noite\b", title)
        if match and playlist.get("id"):
            nights[int(match.group(1))] = playlist["id"]
    return [nights[night] for night in sorted(nights)]


def complete_retreta_links(footer: str, playlist_ids_to_use: list[str]) -> str:
    """Use one consistent Retreta section, including newly listed playlists."""
    if not playlist_ids_to_use:
        return footer
    blocks = paragraphs(footer)
    start = next((index for index, block in enumerate(blocks) if normalize(block).startswith("projeto retreta")), -1)
    if start < 0:
        start = next((index for index, block in enumerate(blocks) if normalize(block).startswith("projeto musica no casarao")), len(blocks))
        blocks.insert(start, "🎺 Projeto Retreta — Só RARIDADES!")
    end = start + 1
    while end < len(blocks) and not normalize(blocks[end]).startswith("projeto "):
        end += 1
    numbered = [f"{index}\ufe0f\u20e3 https://www.youtube.com/playlist?list={playlist_id}"
                if index < 10 else f"{index}. https://www.youtube.com/playlist?list={playlist_id}"
                for index, playlist_id in enumerate(playlist_ids_to_use, 1)]
    return "\n\n".join((*blocks[:start + 1], *numbered, *blocks[end:]))


def without_links(description: str) -> str:
    return "\n\n".join(p for p in paragraphs(description) if not is_footer_block(p))


def composer_is_subject(paragraph: str, composer: str) -> bool:
    """Distinguish the subject of a biography from a name mentioned in passing."""
    name = normalize(composer)
    parts = name.split()
    if len(parts) < 2:
        return False
    plain = normalize(paragraph)
    if plain.startswith("sobre o compositor"):
        subject = re.split(r"\b(?:foi|e|era)\b", plain.removeprefix("sobre o compositor").strip(), maxsplit=1)[0]
        subject = subject.split(" compositor")[0].strip()
        return parts[0] in subject.split() and parts[-1] in subject.split()
    return plain.startswith(name + " ") or plain.startswith(name + " foi")


def trim_other_works(paragraph: str) -> str:
    """A composer biography can be reused without its list of unrelated works."""
    paragraph = re.sub(r"(?m)^\s*_{3,}\s*$", "", paragraph).strip()
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    return " ".join(sentence for sentence in sentences if not re.search(r"\bincluindo\b[^.!?]*[\"“”]", sentence, re.I)).strip()


def event_specific(paragraph: str) -> bool:
    plain = normalize(paragraph)
    return bool(re.search(
        r"\b(?:dia do samba|no dia \d|em \d+ de [a-z]+|nesta apresentacao|neste concerto|"
        r"na apresentacao de|no concerto de|hoje a|neste video a)\b", plain,
    ))


def clean_work_body(description: str, composer: str) -> str:
    """Keep work text while removing claims tied to an earlier event."""
    cleaned = []
    for paragraph in paragraphs(without_links(description)):
        paragraph = re.sub(r"(?m)^\s*_{3,}\s*$", "", paragraph).strip()
        plain = normalize(paragraph)
        if (not paragraph or paragraph.lstrip().startswith("#")
                or is_institution_block(paragraph)
                or len(re.findall(r"#\w+", paragraph)) >= 3
                or re.search(r"^(?:oportunidade para|clique no link para se inscrever|sobre a sociedade filarmonica|"
                             r"apaixonado por musica de filarmonica|projeto musica no casarao)\b", plain)):
            continue
        if event_specific(paragraph):
            continue
        cleaned.append(paragraph)
    return "\n\n".join(cleaned)


def composer_passage(description: str, composer: str) -> str:
    """Copy the channel's own dedicated composer paragraph without rewriting it."""
    for paragraph in paragraphs(without_links(description)):
        plain = normalize(paragraph)
        if not plain.startswith("sobre o compositor") or not composer_is_subject(paragraph, composer):
            continue
        if len(paragraph) > 1500 or event_specific(paragraph):
            continue
        return re.sub(r"(?m)^\s*_{3,}\s*$", "", paragraph).strip()
    return ""


def arranger_passage(description: str, arranger: str, other_work: str = "") -> str:
    name = normalize(arranger)
    for paragraph in paragraphs(without_links(description)):
        plain = normalize(paragraph)
        if not plain.startswith("sobre o arranjador") or name not in plain[:120]:
            continue
        if event_specific(paragraph) or (other_work and normalize(other_work) in plain):
            continue
        cleaned = trim_other_works(paragraph)
        if cleaned and len(cleaned) <= 1000:
            return cleaned
    return ""


def published(video: dict) -> str:
    return video.get("snippet", {}).get("publishedAt", "")


def ensemble_marker(title: str) -> str:
    plain = normalize(title)
    match = re.search(r"(?:filarmonica|s\s+f|sf)\s+(\d+\s+de\s+[a-z]+|[a-z]+(?:\s+[a-z]+){0,2})", plain)
    return "filarmonica " + match.group(1) if match else ""


def propose(target: dict, sources: list[dict], overrides: dict | None = None,
            playlists: list[dict] | None = None) -> dict:
    target_id = identity(target, overrides)
    references = [v for v in sources if v.get("id") != target.get("id") and v.get("snippet", {}).get("description", "").strip()]
    references.sort(key=published, reverse=True)
    ensemble = ensemble_marker(target["snippet"]["title"])
    institution_reference = next(((candidate, passage) for candidate in references
                                  if (passage := institution_passage(candidate["snippet"]["description"], ensemble))), None)
    link_references = [v for v in references if current_links(v["snippet"]["description"], ensemble)]
    if ensemble:
        link_references = [v for v in link_references if ensemble in normalize(v["snippet"]["title"])]
    def footer_rank(video: dict) -> tuple[int, int, str]:
        description = video["snippet"]["description"]
        return (len(retreta_playlist_ids(description)),
                len(set(playlist_ids(description))), published(video))

    newest = max(link_references, key=footer_rank) if link_references else None
    footer = current_links(newest["snippet"]["description"], ensemble) if newest else ""
    if newest:
        all_retreta = channel_retreta_playlists(playlists or [], ensemble)
        for candidate in link_references:
            for playlist_id in retreta_playlist_ids(candidate["snippet"]["description"]):
                if playlist_id not in all_retreta:
                    all_retreta.append(playlist_id)
        footer = complete_retreta_links(footer, all_retreta)
    work = work_key(target_id["work"])
    composer = normalize(target_id["composer"])
    arranger = normalize(target_id["arranger"])

    composer_reference = next(
        ((candidate, passage) for candidate in references
         if (passage := composer_passage(candidate["snippet"]["description"], target_id["composer"]))),
        None,
    ) if composer else None

    exact = []
    if work:
        for candidate in references:
            known = identity(candidate)
            other_work = work_key(known["work"])
            score = SequenceMatcher(None, work, other_work).ratio()
            if score >= .88 and (not composer or (known["composer"] and normalize(known["composer"]) == composer)):
                exact.append((score, candidate))
    if exact:
        exact.sort(key=lambda pair: (published(pair[1]), pair[0]), reverse=True)
        source = exact[0][1]
        body = clean_work_body(source["snippet"]["description"], target_id["composer"])
        kind = "same_work"
        if composer_reference and not any(normalize(part).startswith("sobre o compositor") for part in paragraphs(body)):
            had_work_body = bool(body)
            body = "\n\n".join(part for part in (body, composer_reference[1]) if part)
            if not had_work_body:
                source, kind = composer_reference[0], "composer"
    else:
        source = None
        body = ""
        kind = "none"
        if composer_reference:
            source, body = composer_reference
            kind = "composer"
        if not source and arranger:
            arranger_options = []
            for candidate in references:
                known = identity(candidate)
                if normalize(known["arranger"]) == arranger:
                    biography = arranger_passage(candidate["snippet"]["description"], target_id["arranger"], known["work"])
                    arranger_options.append((bool(biography), published(candidate), candidate, biography))
            if arranger_options:
                _, _, source, biography = max(arranger_options, key=lambda option: (option[0], option[1]))
                body = "\n\n".join(p for p in (f"Arranjo: {target_id['arranger']}", biography) if p)
                kind = "arranger"

    footer_blocks = paragraphs(footer)
    follow_blocks = [paragraph for paragraph in footer_blocks if is_follow_block(paragraph)]
    playlist_blocks = [paragraph for paragraph in footer_blocks if not is_follow_block(paragraph)]
    institution = institution_reference[1] if institution_reference else ""
    result = "\n\n".join(p for p in (*follow_blocks, body, institution, *playlist_blocks) if p).strip()
    if not body or not result or len(result) > 5000:
        kind, result = "none", ""
    return {
        "video_id": target["id"], "title": target["snippet"]["title"],
        "published_at": published(target), "identity": target_id,
        "description": result, "match_type": kind,
        "source": {"id": source["id"], "title": source["snippet"]["title"]} if source and kind != "none" else None,
        "links_source": {"id": newest["id"], "title": newest["snippet"]["title"]} if footer and newest else None,
        "institution_source": {"id": institution_reference[0]["id"], "title": institution_reference[0]["snippet"]["title"]} if institution and result else None,
        "reason": "Revise a correspondência e o texto antes de aplicar." if result else "Não foi encontrada uma descrição confiável para compor este vídeo.",
    }
