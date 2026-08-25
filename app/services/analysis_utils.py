from __future__ import annotations

import json

from app.services.ai import AnalysisResult, DreamSymbolItem, Panel, analysis_as_dict, fallback_reflection_question


def analysis_to_storage(analysis: AnalysisResult) -> dict[str, str]:
    payload = analysis_as_dict(analysis)
    return {
        "title": payload["title"],
        "summary": payload["summary"],
        "themes_json": json.dumps(payload["themes"]),
        "emotions_json": json.dumps(payload["emotions"]),
        "panels_json": json.dumps(payload["panels"]),
        "symbols_json": json.dumps(payload.get("symbols") or []),
    }


def parse_analysis(analysis_row) -> AnalysisResult:
    panels_raw = json.loads(analysis_row.panels_json or "[]")
    panels = []
    for index, panel in enumerate(panels_raw, start=1):
        if not isinstance(panel, dict):
            continue
        question = str(panel.get("reflection_question") or "").strip()
        panels.append(
            Panel(
                panel_number=int(panel.get("panel_number") or index),
                caption=str(panel.get("caption") or ""),
                scene_description=str(panel.get("scene_description") or ""),
                image_url=panel.get("image_url"),
                reflection_question=question or fallback_reflection_question(index),
            )
        )
    symbols_raw = []
    if getattr(analysis_row, "symbols_json", None):
        symbols_raw = json.loads(analysis_row.symbols_json or "[]")
    symbols = [
        DreamSymbolItem(name=str(item.get("name") or ""), kind=str(item.get("kind") or "motif"))
        for item in symbols_raw
        if isinstance(item, dict) and item.get("name")
    ]
    return AnalysisResult(
        title=analysis_row.title,
        summary=analysis_row.summary,
        themes=json.loads(analysis_row.themes_json or "[]"),
        emotions=json.loads(analysis_row.emotions_json or "[]"),
        panels=panels,
        symbols=symbols,
    )
