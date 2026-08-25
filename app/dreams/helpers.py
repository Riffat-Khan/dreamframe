"""Shared dream helpers used by dream views."""

import threading

from flask import abort, current_app, flash, g, request

from app.extensions import db
from app.models import DreamAnalysis, DreamEntry
from app.services.analysis_utils import analysis_to_storage, parse_analysis
from app.services.images import delete_dream_images
from app.services.symbols import heuristic_symbols, merge_symbols, sync_dream_symbols

_write_locks: dict[int, threading.Lock] = {}
_write_locks_guard = threading.Lock()


def _dream_write_lock(dream_id: int) -> threading.Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(dream_id, threading.Lock())

STYLES = ("soft", "surreal", "funny")


def parse_dream_form():
    original_text = (request.form.get("original_text") or "").strip()
    mood = (request.form.get("mood") or "").strip() or None
    style = (request.form.get("style") or "soft").strip().lower()
    if style not in STYLES:
        style = "soft"
    return original_text, mood, style


def get_owned_dream(dream_id: int) -> DreamEntry:
    dream = DreamEntry.query.get_or_404(dream_id)
    if dream.user_id != g.user.id:
        abort(404)
    return dream


def persist_analysis_row(entry: DreamEntry, analysis) -> None:
    stored = analysis_to_storage(analysis)
    if entry.analysis is None:
        entry.analysis = DreamAnalysis(**stored)
    else:
        entry.analysis.title = stored["title"]
        entry.analysis.summary = stored["summary"]
        entry.analysis.themes_json = stored["themes_json"]
        entry.analysis.emotions_json = stored["emotions_json"]
        entry.analysis.panels_json = stored["panels_json"]
        entry.analysis.symbols_json = stored["symbols_json"]
    db.session.commit()

    if entry.user_id:
        symbols = merge_symbols(
            analysis.symbols or [],
            heuristic_symbols(entry.original_text),
        )
        sync_dream_symbols(user_id=entry.user_id, dream=entry, symbols=symbols)


def save_analysis(entry: DreamEntry, analysis, *, with_images: bool = False) -> int:
    """Persist comic text. Images are drawn in parallel from the detail page."""
    if not with_images:
        delete_dream_images(entry.id)
        for panel in analysis.panels:
            panel.image_url = None
    persist_analysis_row(entry, analysis)
    return 0


def persist_panel_image_url(entry: DreamEntry, *, panel_number: int, image_url: str) -> None:
    """Merge one panel URL into the DB so parallel draws don't overwrite each other."""
    if entry.analysis is None:
        return
    with _dream_write_lock(entry.id):
        db.session.refresh(entry.analysis)
        analysis = parse_analysis(entry.analysis)
        for panel in analysis.panels:
            if panel.panel_number == panel_number:
                panel.image_url = image_url
        entry.analysis.panels_json = analysis_to_storage(analysis)["panels_json"]
        db.session.commit()


def flash_image_failures(image_failures: int) -> None:
    if image_failures:
        flash(
            f"{image_failures} scenic panel(s) failed — free image API was busy. "
            "Wait about a minute, then tap Regenerate.",
            "info",
        )


def flash_mock_ai_notice_if_needed() -> None:
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    force_mock = current_app.config.get("USE_MOCK_AI", True)
    can_call_llm = (not force_mock) and bool(api_key) and "your-key" not in api_key.lower()
    if not can_call_llm:
        flash(
            "Using sample comic text. Add a free Groq key in .env (console.groq.com/keys) for real AI writing.",
            "info",
        )
