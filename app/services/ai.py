from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

import httpx
from flask import current_app


@dataclass
class Panel:
    panel_number: int
    caption: str
    scene_description: str
    image_url: str | None = None
    reflection_question: str | None = None


@dataclass
class DreamSymbolItem:
    name: str
    kind: str  # person | place | object | motif


@dataclass
class AnalysisResult:
    title: str
    summary: str
    themes: list[str]
    emotions: list[str]
    panels: list[Panel]
    symbols: list[DreamSymbolItem] | None = None


MOCK_ANALYSIS = AnalysisResult(
    title="The Locked Door",
    summary=(
        "You may be circling a decision that feels bigger than it looks. "
        "This is for reflection and fun — not therapy or medical advice."
    ),
    themes=["avoidance", "transition", "curiosity"],
    emotions=["uneasy", "hopeful"],
    panels=[
        Panel(
            panel_number=1,
            caption="I keep walking past the same door.",
            scene_description="Night hallway, one glowing door, person hesitating at a distance",
        ),
        Panel(
            panel_number=2,
            caption="Every time I reach for the handle, it slides farther away.",
            scene_description="Surreal stretchy corridor, melting clock, soft moonlight",
        ),
        Panel(
            panel_number=3,
            caption="I wake up still holding the key.",
            scene_description="Morning bedroom light, open hand with a small key, calm expression",
        ),
    ],
)

SYSTEM_PROMPT = """You are a kind dream interpreter and comic writer.
Turn dreams into a short reflective comic. This is for reflection and fun — not therapy or medical advice.
Never fear-monger. Never claim medical diagnoses. Keep tone warm and curious.

CRITICAL for panels:
- Each panel must depict concrete people, places, objects, and actions FROM THE DREAMER'S OWN WORDS.
- Do NOT invent a different story (no random locked doors, keys, melting clocks) unless those appear in the dream text.
- scene_description must be a clear visual instruction an illustrator can draw, using details from the dream.
- Captions can be poetic, but scenes must stay faithful to what was dreamed.

Return ONLY valid JSON with this exact shape:
{
  "title": "string",
  "summary": "1-2 sentences about what the dream might be reflecting",
  "themes": ["3 short theme words"],
  "emotions": ["2-4 emotion words"],
  "symbols": [
    {"name": "short concrete noun from the dream", "kind": "person|place|object|motif"}
  ],
  "panels": [
    {
      "panel_number": 1,
      "caption": "short comic caption in first person, grounded in the dream",
      "scene_description": "detailed visual of that moment from the dream (who, where, what is happening)",
      "reflection_question": "one gentle curious question about this moment (not therapy advice)"
    }
  ]
}
Exactly 3 panels covering beginning → middle → end of the dream.
Include 3–8 symbols that actually appear in the dream text (people, places, objects, recurring motifs).
Reflection questions should feel soft and human, e.g. "What felt unfinished here?" — never diagnostic.
No markdown. No extra keys."""


def _has_usable_api_key(api_key: str) -> bool:
    if not api_key:
        return False
    lowered = api_key.lower()
    return "your-key" not in lowered and "your_key" not in lowered


FALLBACK_QUESTIONS = (
    "What felt unfinished here?",
    "Where did your attention linger?",
    "What would you whisper back to this moment?",
)


def fallback_reflection_question(panel_number: int) -> str:
    return FALLBACK_QUESTIONS[(panel_number - 1) % len(FALLBACK_QUESTIONS)]


def _chunk_dream_for_panels(dream_text: str) -> list[str]:
    """Split the dreamer's words into ~3 visual beats for mock / fallback panels."""
    cleaned = " ".join(dream_text.split())
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    if len(parts) >= 3:
        # Take start, middle, end sentences
        mid = len(parts) // 2
        return [parts[0], parts[mid], parts[-1]]
    if len(parts) == 2:
        return [parts[0], parts[1], cleaned[-180:]]
    # No clear sentences — hard-split the text
    third = max(len(cleaned) // 3, 1)
    return [
        cleaned[:third].strip() or cleaned,
        cleaned[third : third * 2].strip() or cleaned,
        cleaned[third * 2 :].strip() or cleaned,
    ]


def _mock_result(*, dream_text: str, mood: str | None, style: str) -> AnalysisResult:
    from app.services.symbols import heuristic_symbols

    beats = _chunk_dream_for_panels(dream_text)
    panels = [
        Panel(
            panel_number=index,
            caption=beat[:120] + ("…" if len(beat) > 120 else ""),
            scene_description=(
                f"Illustrate exactly this moment from the dreamer's account: {beat}"
            ),
            reflection_question=fallback_reflection_question(index),
        )
        for index, beat in enumerate(beats, start=1)
    ]
    result = AnalysisResult(
        title=f"Dream sketch ({style})",
        summary=(
            "A quick visual take on what you wrote — for reflection and fun, "
            "not therapy or medical advice."
        ),
        themes=["memory", "feeling", "imagery"],
        emotions=[mood] if mood else ["curious"],
        panels=panels,
        symbols=heuristic_symbols(dream_text),
    )
    return result


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _parse_analysis_payload(payload: dict) -> AnalysisResult:
    panels_raw = payload.get("panels") or []
    if not isinstance(panels_raw, list) or not (3 <= len(panels_raw) <= 4):
        raise ValueError("Expected 3–4 panels")

    panels: list[Panel] = []
    for index, raw in enumerate(panels_raw[:4], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Invalid panel")
        question = str(raw.get("reflection_question") or "").strip()
        panels.append(
            Panel(
                panel_number=int(raw.get("panel_number") or index),
                caption=str(raw.get("caption") or "").strip() or f"Panel {index}",
                scene_description=str(raw.get("scene_description") or "").strip()
                or "A soft dreamlike scene",
                image_url=raw.get("image_url"),
                reflection_question=question[:160] or fallback_reflection_question(index),
            )
        )

    themes = [str(t).strip() for t in (payload.get("themes") or []) if str(t).strip()]
    emotions = [str(e).strip() for e in (payload.get("emotions") or []) if str(e).strip()]

    symbols: list[DreamSymbolItem] = []
    for raw in payload.get("symbols") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        kind = str(raw.get("kind") or "motif").strip().lower()
        if not name:
            continue
        if kind not in {"person", "place", "object", "motif"}:
            kind = "motif"
        symbols.append(DreamSymbolItem(name=name[:80], kind=kind))

    return AnalysisResult(
        title=str(payload.get("title") or "Untitled Dream").strip()[:200],
        summary=str(payload.get("summary") or "").strip()
        or "A quiet reflection of something your mind is turning over.",
        themes=themes[:6] or ["dream", "memory", "feeling"],
        emotions=emotions[:6] or ["curious"],
        panels=panels,
        symbols=symbols[:12],
    )


def _call_llm(*, dream_text: str, mood: str | None, style: str) -> AnalysisResult:
    api_key = current_app.config["OPENAI_API_KEY"]
    base_url = current_app.config["OPENAI_BASE_URL"].rstrip("/")
    model = current_app.config["OPENAI_MODEL"]

    user_prompt = {
        "dream_text": dream_text,
        "mood": mood or "unspecified",
        "style": style,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Style knob: {style} (soft / surreal / funny).\n"
                "Stay faithful to the dreamer's imagery — panels must show what THEY described.\n"
                f"Dream JSON:\n{json.dumps(user_prompt)}"
            ),
        },
    ]
    body = {
        "model": model,
        "temperature": 0.8,
        "messages": messages,
    }

    # Some free providers support JSON mode; others ignore / reject it.
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={**body, "response_format": {"type": "json_object"}},
        )
        if response.status_code >= 400:
            current_app.logger.warning(
                "LLM JSON-mode request failed (%s): %s",
                response.status_code,
                response.text[:300],
            )
            response = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"LLM error {response.status_code}: {response.text[:400]}",
                request=response.request,
                response=response,
            )
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    return _parse_analysis_payload(_extract_json(content))


def generate_dream_analysis(*, dream_text: str, mood: str | None, style: str) -> AnalysisResult:
    from app.services.symbols import heuristic_symbols, merge_symbols

    use_mock = current_app.config.get("USE_MOCK_AI", True)
    api_key = current_app.config.get("OPENAI_API_KEY", "")

    if use_mock or not _has_usable_api_key(api_key):
        return _mock_result(dream_text=dream_text, mood=mood, style=style)

    try:
        result = _call_llm(dream_text=dream_text, mood=mood, style=style)
    except Exception as exc:  # noqa: BLE001 — fall back so the journal still works
        current_app.logger.exception("LLM analysis failed: %s", exc)
        return _mock_result(dream_text=dream_text, mood=mood, style=style)

    result.symbols = merge_symbols(result.symbols or [], heuristic_symbols(dream_text))
    for panel in result.panels:
        if not panel.reflection_question:
            panel.reflection_question = fallback_reflection_question(panel.panel_number)
    return result


def analysis_as_dict(analysis: AnalysisResult) -> dict:
    return asdict(analysis)
