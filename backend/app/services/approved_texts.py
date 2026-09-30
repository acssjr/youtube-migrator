"""Identity-bound approved text. Never summarize or rewrite an approved passage."""
import re
import unicodedata

ROLES = {"composer", "arranger", "work", "ensemble"}


def name_key(value: str) -> str:
    # Punctuation is significant: do not silently merge distinct catalog identities.
    value = unicodedata.normalize("NFKD", value or "")
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).casefold().split())


def approved_for_identity(records: list, identities: dict) -> dict:
    """Newest approved record for each exact role/name, including source provenance."""
    selected = {}
    def field(record, key, default=None):
        return record.get(key, default) if isinstance(record, dict) else getattr(record, key, default)
    for record in sorted(records, key=lambda item: str(field(item, "updated_at", "")), reverse=True):
        payload = field(record, "payload", {})
        role = payload.get("role")
        text = payload.get("text")
        if (role not in ROLES or role in selected or payload.get("approved") is not True
                or not isinstance(text, str) or not text.strip()):
            continue
        target = name_key(identities.get(role, ""))
        if target and target == name_key(payload.get("name", "")):
            selected[role] = {"text": text, "record_id": field(record, "id"),
                              "source_url": payload.get("source_url", ""), "name": payload["name"]}
    return selected


def published_blocks(description: str) -> list[dict]:
    """Return heading-led published blocks verbatim, without guessing their author."""
    starts = list(re.finditer(r"(?im)^[ \t]*Sobre (?:o compositor|o arranjador|a obra|a m[uú]sica|a (?:sociedade )?filarm[oô]nica)\s*:", description))
    output = []
    for start in starts:
        role_text = name_key(start.group())
        role = "composer" if "compositor" in role_text else "arranger" if "arranjador" in role_text else "ensemble" if "filarmonica" in role_text else "work"
        tail = description[start.start():]
        # Blank line closes a published paragraph. Preserve all bytes within it.
        end = re.search(r"\r?\n[ \t]*\r?\n", tail)
        text = tail[:end.start()] if end else tail
        output.append({"role": role, "text": text})
    return output


def enrich_proposal(proposal, records):
    """Replace approved identity blocks verbatim; all other paragraphs remain intact."""
    approved = approved_for_identity(records, proposal.get("identity", {}))
    description = proposal.get("description", "")
    used = {}
    for role in ("composer", "arranger", "work"):
        if role not in approved:
            continue
        passage = approved[role]["text"]
        blocks = published_blocks(description)
        matches = [block for block in blocks if block["role"] == role]
        if matches:
            description = description.replace(matches[0]["text"], passage, 1)
            for duplicate in matches[1:]:
                description = description.replace(duplicate["text"], "", 1)
        else:
            paragraphs = description.split("\n\n") if description else []
            insertion = next((i for i, block in enumerate(paragraphs) if re.search(r"(?i)playlist|retreta", block)), len(paragraphs))
            paragraphs.insert(insertion, passage)
            description = "\n\n".join(paragraphs)
        used[role] = approved[role]
    if len(description) <= 5000 and used:
        proposal = dict(proposal, description=description, approved_sources=used,
                        reason="Texto aprovado preservado. Confira as referências e a descrição antes de publicar.")
    return proposal
