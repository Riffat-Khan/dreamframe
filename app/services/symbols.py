from __future__ import annotations

import re
from datetime import datetime, timezone

from app.extensions import db
from app.models import DreamEntry, DreamSymbol, DreamSymbolLink
from app.services.ai import DreamSymbolItem

SYMBOL_KINDS = ("person", "place", "object", "motif")

# Lightweight fallback extractor so the map still fills without LLM symbols.
HEURISTIC_TERMS: dict[str, str] = {
    "friend": "person",
    "mother": "person",
    "father": "person",
    "sister": "person",
    "brother": "person",
    "stranger": "person",
    "teacher": "person",
    "stairs": "place",
    "staircase": "place",
    "hallway": "place",
    "corridor": "place",
    "bench": "object",
    "door": "object",
    "key": "object",
    "bedroom": "place",
    "school": "place",
    "house": "place",
    "ocean": "place",
    "forest": "place",
    "bridge": "place",
    "train": "object",
    "car": "object",
    "phone": "object",
    "shirt": "object",
    "orange shirt": "object",
}


def normalize_symbol_name(name: str) -> tuple[str, str]:
    cleaned = " ".join(name.lower().strip().split())
    cleaned = re.sub(r"[^a-z0-9\s\-']", "", cleaned).strip()
    display = cleaned.title() if cleaned else "Unknown"
    return cleaned[:120], display[:120]


def heuristic_symbols(dream_text: str) -> list[DreamSymbolItem]:
    text = dream_text.lower()
    found: list[DreamSymbolItem] = []
    # Longer phrases first
    for term in sorted(HEURISTIC_TERMS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", text):
            found.append(DreamSymbolItem(name=term, kind=HEURISTIC_TERMS[term]))
    # Dedupe by normalized key
    unique: dict[str, DreamSymbolItem] = {}
    for item in found:
        key, _ = normalize_symbol_name(item.name)
        if key and key not in unique:
            unique[key] = item
    return list(unique.values())[:12]


def merge_symbols(*groups: list[DreamSymbolItem]) -> list[DreamSymbolItem]:
    merged: dict[str, DreamSymbolItem] = {}
    for group in groups:
        for item in group:
            key, display = normalize_symbol_name(item.name)
            if not key:
                continue
            kind = item.kind if item.kind in SYMBOL_KINDS else "motif"
            if key not in merged:
                merged[key] = DreamSymbolItem(name=display, kind=kind)
    return list(merged.values())[:12]


def sync_dream_symbols(*, user_id: int, dream: DreamEntry, symbols: list[DreamSymbolItem]) -> None:
    """Replace this dream's symbol links and refresh mention counts."""
    # Drop old links for this dream
    old_links = DreamSymbolLink.query.filter_by(dream_id=dream.id).all()
    touched_ids = {link.symbol_id for link in old_links}
    for link in old_links:
        db.session.delete(link)
    db.session.flush()

    now = datetime.now(timezone.utc)
    for item in symbols:
        key, display = normalize_symbol_name(item.name)
        if not key:
            continue
        kind = item.kind if item.kind in SYMBOL_KINDS else "motif"
        symbol = DreamSymbol.query.filter_by(user_id=user_id, name_key=key).first()
        if symbol is None:
            symbol = DreamSymbol(
                user_id=user_id,
                name_key=key,
                display_name=display,
                kind=kind,
                mention_count=0,
                last_seen_at=now,
            )
            db.session.add(symbol)
            db.session.flush()
        else:
            symbol.display_name = display
            symbol.kind = kind
            symbol.last_seen_at = now

        exists = DreamSymbolLink.query.filter_by(symbol_id=symbol.id, dream_id=dream.id).first()
        if exists is None:
            db.session.add(DreamSymbolLink(symbol_id=symbol.id, dream_id=dream.id))
        touched_ids.add(symbol.id)

    db.session.flush()

    # Recompute counts for touched symbols
    for symbol_id in touched_ids:
        symbol = db.session.get(DreamSymbol, symbol_id)
        if symbol is None:
            continue
        count = DreamSymbolLink.query.filter_by(symbol_id=symbol.id).count()
        if count == 0:
            db.session.delete(symbol)
        else:
            symbol.mention_count = count

    db.session.commit()


def rebuild_user_dream_map(user_id: int) -> int:
    """Re-sync symbols for all of a user's dreams. Returns dream count processed."""
    dreams = DreamEntry.query.filter_by(user_id=user_id).all()
    for dream in dreams:
        symbols: list[DreamSymbolItem] = []
        if dream.analysis and dream.analysis.symbols_json:
            import json

            raw = json.loads(dream.analysis.symbols_json or "[]")
            for item in raw:
                if isinstance(item, dict) and item.get("name"):
                    symbols.append(
                        DreamSymbolItem(
                            name=str(item["name"]),
                            kind=str(item.get("kind") or "motif"),
                        )
                    )
        symbols = merge_symbols(symbols, heuristic_symbols(dream.original_text))
        sync_dream_symbols(user_id=user_id, dream=dream, symbols=symbols)
    return len(dreams)
