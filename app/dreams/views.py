"""Dream journal view handlers (business logic + responses)."""

from flask import Response, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from app.dreams.helpers import (
    STYLES,
    flash_mock_ai_notice_if_needed,
    get_owned_dream,
    parse_dream_form,
    persist_analysis_row,
    persist_panel_image_url,
    save_analysis,
)
from app.extensions import db
from app.models import DreamAnalysis, DreamEntry, DreamSymbol, DreamSymbolLink
from app.services.ai import generate_dream_analysis
from app.services.analysis_utils import analysis_to_storage, parse_analysis
from app.services.images import delete_dream_images, generate_one_panel_image
from app.services.postcard import build_postcard_svg


def home():
    return render_template("home.html", styles=STYLES)


def create_dream():
    original_text, mood, style = parse_dream_form()

    if len(original_text) < 10:
        flash("Please write a bit more about your dream (at least 10 characters).", "error")
        return redirect(url_for("dreams.home"))

    analysis = generate_dream_analysis(
        dream_text=original_text,
        mood=mood,
        style=style,
    )

    entry = DreamEntry(
        user_id=g.user.id,
        original_text=original_text,
        mood=mood,
        style=style,
        analysis=DreamAnalysis(**analysis_to_storage(analysis)),
    )
    db.session.add(entry)
    db.session.commit()

    save_analysis(entry, analysis)
    flash_mock_ai_notice_if_needed()
    flash("Comic ready — drawing all three scenic panels at once.", "info")
    return redirect(url_for("dreams.dream_detail", dream_id=entry.id))


def journal():
    dreams = (
        DreamEntry.query.filter_by(user_id=g.user.id)
        .order_by(DreamEntry.created_at.desc())
        .all()
    )
    cards = []
    for dream in dreams:
        preview = " ".join(dream.original_text.split())
        if len(preview) > 120:
            preview = f"{preview[:117]}..."
        cards.append(
            {
                "id": dream.id,
                "title": dream.analysis.title if dream.analysis else f"Dream #{dream.id}",
                "preview": preview,
                "style": dream.style,
                "created_at": dream.created_at,
            }
        )
    return render_template("journal.html", dreams=cards)


def dream_detail(dream_id: int):
    dream = get_owned_dream(dream_id)
    analysis = parse_analysis(dream.analysis) if dream.analysis else None
    dream_symbols = (
        DreamSymbol.query.join(DreamSymbolLink)
        .filter(DreamSymbolLink.dream_id == dream.id, DreamSymbol.user_id == g.user.id)
        .order_by(DreamSymbol.mention_count.desc())
        .all()
    )
    pending_panels = []
    if analysis and current_app.config.get("GENERATE_IMAGES", False):
        pending_panels = [
            panel.panel_number for panel in analysis.panels if not panel.image_url
        ]
    return render_template(
        "detail.html",
        dream=dream,
        analysis=analysis,
        dream_symbols=dream_symbols,
        pending_panels=pending_panels,
    )


def dream_postcard(dream_id: int):
    dream = get_owned_dream(dream_id)
    if not dream.analysis:
        flash("Generate a comic before opening the postcard.", "error")
        return redirect(url_for("dreams.dream_detail", dream_id=dream.id))
    analysis = parse_analysis(dream.analysis)
    return render_template("postcard.html", dream=dream, analysis=analysis)


def dream_postcard_svg(dream_id: int):
    dream = get_owned_dream(dream_id)
    if not dream.analysis:
        from flask import abort

        abort(404)
    analysis = parse_analysis(dream.analysis)
    svg = build_postcard_svg(analysis=analysis, dream_id=dream.id)
    filename = f"dreamframe-{dream.id}-postcard.svg"
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def edit_dream(dream_id: int):
    dream = get_owned_dream(dream_id)
    return render_template("edit.html", dream=dream, styles=STYLES)


def update_dream(dream_id: int):
    dream = get_owned_dream(dream_id)
    original_text, mood, style = parse_dream_form()

    if len(original_text) < 10:
        flash("Please write a bit more about your dream (at least 10 characters).", "error")
        return redirect(url_for("dreams.edit_dream", dream_id=dream.id))

    dream.original_text = original_text
    dream.mood = mood
    dream.style = style
    db.session.commit()

    reanalyze = request.form.get("reanalyze") == "1"
    if reanalyze:
        analysis = generate_dream_analysis(
            dream_text=original_text,
            mood=mood,
            style=style,
        )
        save_analysis(dream, analysis)
        flash("Dream updated. Drawing scenic panels in parallel.", "info")
    else:
        flash("Dream text saved. Use Regenerate to rebuild the comic.", "info")

    return redirect(url_for("dreams.dream_detail", dream_id=dream.id))


def regenerate_dream(dream_id: int):
    dream = get_owned_dream(dream_id)
    analysis = generate_dream_analysis(
        dream_text=dream.original_text,
        mood=dream.mood,
        style=dream.style,
    )
    save_analysis(dream, analysis)
    flash("Comic regenerated. Drawing scenic panels in parallel.", "info")
    return redirect(url_for("dreams.dream_detail", dream_id=dream.id))


def regenerate_images(dream_id: int):
    dream = get_owned_dream(dream_id)
    if not dream.analysis:
        flash("No comic to regenerate images for. Use Regenerate first.", "error")
        return redirect(url_for("dreams.dream_detail", dream_id=dream.id))

    analysis = parse_analysis(dream.analysis)
    for panel in analysis.panels:
        panel.image_url = None
    delete_dream_images(dream.id)
    persist_analysis_row(dream, analysis)
    flash("Redrawing scenic panels in parallel.", "info")
    return redirect(url_for("dreams.dream_detail", dream_id=dream.id))


def generate_panel_image(dream_id: int, panel_number: int):
    dream = get_owned_dream(dream_id)
    if not dream.analysis:
        return jsonify({"ok": False, "error": "No comic to illustrate."}), 404

    analysis = parse_analysis(dream.analysis)
    existing = next((p for p in analysis.panels if p.panel_number == panel_number), None)
    if existing is None:
        return jsonify({"ok": False, "error": "Panel not found."}), 404

    analysis, image_url, error = generate_one_panel_image(
        analysis,
        dream_id=dream.id,
        style=dream.style,
        dream_text=dream.original_text,
        panel_number=panel_number,
        force=False,
    )
    if image_url:
        persist_panel_image_url(dream, panel_number=panel_number, image_url=image_url)
        return jsonify({"ok": True, "panel_number": panel_number, "image_url": image_url})
    return jsonify({"ok": False, "panel_number": panel_number, "error": error or "Could not draw panel."}), 503


def delete_dream(dream_id: int):
    dream = get_owned_dream(dream_id)
    linked_symbol_ids = [
        link.symbol_id for link in DreamSymbolLink.query.filter_by(dream_id=dream.id).all()
    ]
    delete_dream_images(dream.id)
    db.session.delete(dream)
    db.session.commit()

    for symbol_id in linked_symbol_ids:
        symbol = db.session.get(DreamSymbol, symbol_id)
        if symbol is None:
            continue
        count = DreamSymbolLink.query.filter_by(symbol_id=symbol.id).count()
        if count == 0:
            db.session.delete(symbol)
        else:
            symbol.mention_count = count
    db.session.commit()

    flash("Dream deleted.", "info")
    return redirect(url_for("dreams.journal"))
