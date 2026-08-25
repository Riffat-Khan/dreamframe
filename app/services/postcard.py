from __future__ import annotations

import base64
import html
import mimetypes
import re
from pathlib import Path

from app.config import BASE_DIR
from app.services.ai import AnalysisResult


def _wrap(text: str, width: int = 42, max_lines: int = 3) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [""]


def _panel_image_data_uri(image_url: str | None) -> str | None:
    if not image_url:
        return None
    # Expect /static/generated/...
    match = re.search(r"/static/(.+)$", image_url)
    if not match:
        return None
    path = BASE_DIR / "app" / "static" / match.group(1).split("?")[0]
    if not path.exists():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_postcard_svg(*, analysis: AnalysisResult, dream_id: int) -> str:
    """Shareable postcard: title, one-line summary, 3 panels, Dreamframe mark."""
    title = html.escape((analysis.title or "Untitled dream")[:60])
    one_liner = html.escape(" ".join((analysis.summary or "").split())[:110])
    panels = list(analysis.panels[:3])
    while len(panels) < 3:
        panels.append(panels[-1] if panels else None)

    panel_blocks = []
    for index, panel in enumerate(panels):
        x = 48 + index * 300
        if panel is None:
            continue
        caption_lines = _wrap(panel.caption or "", 28, 3)
        data_uri = _panel_image_data_uri(panel.image_url)
        if data_uri:
            media = (
                f'<image href="{data_uri}" x="{x}" y="168" width="276" height="276" '
                f'preserveAspectRatio="xMidYMid slice" clip-path="url(#rounded{index})"/>'
            )
        else:
            scene_lines = _wrap(panel.scene_description or "A dream moment", 28, 6)
            scene_text = "".join(
                f'<text x="{x + 16}" y="{210 + i * 22}" fill="#d7d2e8" font-size="13" '
                f'font-family="Georgia, serif">{html.escape(line)}</text>'
                for i, line in enumerate(scene_lines)
            )
            media = (
                f'<rect x="{x}" y="168" width="276" height="276" rx="18" fill="#1a2033" '
                f'stroke="rgba(255,255,255,0.12)"/>{scene_text}'
            )

        caption_svg = "".join(
            f'<text x="{x + 8}" y="{470 + i * 20}" fill="#f4f1ea" font-size="14" '
            f'font-family="Georgia, serif">{html.escape(line)}</text>'
            for i, line in enumerate(caption_lines)
        )
        panel_blocks.append(
            f"""
            <defs>
              <clipPath id="rounded{index}">
                <rect x="{x}" y="168" width="276" height="276" rx="18"/>
              </clipPath>
            </defs>
            <rect x="{x}" y="168" width="276" height="276" rx="18" fill="#121826"/>
            {media}
            <text x="{x + 8}" y="160" fill="#7dd3c7" font-size="12" letter-spacing="2"
                  font-family="Arial, sans-serif">PANEL {panel.panel_number}</text>
            {caption_svg}
            """
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="1080" height="620" viewBox="0 0 1080 620">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f1220"/>
      <stop offset="55%" stop-color="#171b2e"/>
      <stop offset="100%" stop-color="#1a1430"/>
    </linearGradient>
    <radialGradient id="glow" cx="20%" cy="10%" r="55%">
      <stop offset="0%" stop-color="#f0a6ca" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="#f0a6ca" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1080" height="620" fill="url(#bg)"/>
  <rect width="1080" height="620" fill="url(#glow)"/>
  <rect x="28" y="28" width="1024" height="564" rx="28" fill="none"
        stroke="rgba(255,255,255,0.14)" stroke-width="2"/>

  <text x="56" y="78" fill="#f0a6ca" font-size="13" letter-spacing="3"
        font-family="Arial, sans-serif">DREAMFRAME</text>
  <text x="56" y="118" fill="#f4f1ea" font-size="34" font-weight="700"
        font-family="Georgia, serif">{title}</text>
  <text x="56" y="148" fill="#b7b3c8" font-size="16"
        font-family="Arial, sans-serif">{one_liner}</text>

  {''.join(panel_blocks)}

  <text x="56" y="560" fill="#7dd3c7" font-size="14" font-family="Georgia, serif">
    Dreamframe — for reflection and fun, not therapy.
  </text>
  <text x="820" y="560" fill="rgba(255,255,255,0.45)" font-size="12"
        font-family="Arial, sans-serif">dream #{dream_id}</text>
</svg>
"""
    return svg


def save_postcard_svg(*, analysis: AnalysisResult, dream_id: int) -> Path:
    out_dir = BASE_DIR / "app" / "static" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dream_{dream_id}_postcard.svg"
    path.write_text(build_postcard_svg(analysis=analysis, dream_id=dream_id), encoding="utf-8")
    return path
