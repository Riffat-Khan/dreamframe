"""Dream map view handlers."""

from flask import flash, g, redirect, render_template, url_for

from app.models import DreamEntry, DreamSymbol, DreamSymbolLink
from app.services.symbols import rebuild_user_dream_map


def dream_map():
    symbols = (
        DreamSymbol.query.filter_by(user_id=g.user.id)
        .order_by(DreamSymbol.mention_count.desc(), DreamSymbol.display_name.asc())
        .all()
    )
    grouped = {"person": [], "place": [], "object": [], "motif": []}
    for symbol in symbols:
        grouped.setdefault(symbol.kind, []).append(symbol)
    recurring = [s for s in symbols if s.mention_count >= 2]
    return render_template(
        "map.html",
        symbols=symbols,
        grouped=grouped,
        recurring=recurring,
    )


def rebuild_map():
    count = rebuild_user_dream_map(g.user.id)
    flash(f"Dream map refreshed from {count} dream(s).", "info")
    return redirect(url_for("map.dream_map"))


def symbol_detail(symbol_id: int):
    symbol = DreamSymbol.query.filter_by(id=symbol_id, user_id=g.user.id).first_or_404()
    links = (
        DreamSymbolLink.query.filter_by(symbol_id=symbol.id)
        .join(DreamEntry)
        .order_by(DreamEntry.created_at.desc())
        .all()
    )
    dreams = []
    for link in links:
        dream = link.dream
        if dream is None or dream.user_id != g.user.id:
            continue
        dreams.append(
            {
                "id": dream.id,
                "title": dream.analysis.title if dream.analysis else f"Dream #{dream.id}",
                "preview": " ".join(dream.original_text.split())[:140],
                "created_at": dream.created_at,
                "style": dream.style,
            }
        )
    return render_template("symbol_detail.html", symbol=symbol, dreams=dreams)
