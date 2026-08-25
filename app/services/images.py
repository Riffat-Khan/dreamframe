from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import quote

import httpx
from flask import current_app, url_for

from app.config import BASE_DIR
from app.services.ai import AnalysisResult, Panel


STYLE_HINTS = {
    "soft": "soft watercolor comic illustration, gentle cinematic lighting",
    "surreal": "surreal dreamlike cinematic illustration, strange atmosphere, not scary",
    "funny": "lighthearted comic illustration, warm playful mood",
}


def _has_usable_api_key(api_key: str) -> bool:
    if not api_key:
        return False
    lowered = api_key.lower()
    return "your-key" not in lowered and "your_token" not in lowered


def _generated_dir() -> Path:
    path = BASE_DIR / "app" / "static" / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def delete_dream_images(dream_id: int) -> None:
    folder = _generated_dir()
    for path in folder.glob(f"dream_{dream_id}_panel_*.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Could not delete image file %s", path)


def delete_panel_image(dream_id: int, panel_number: int) -> None:
    folder = _generated_dir()
    for path in folder.glob(f"dream_{dream_id}_panel_{panel_number}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Could not delete image file %s", path)


def _build_scenic_prompt(panel: Panel, *, style: str, dream_text: str) -> str:
    hint = STYLE_HINTS.get(style, STYLE_HINTS["soft"])
    scene = panel.scene_description.strip()[:260]
    caption = panel.caption.strip()[:120]
    excerpt = " ".join(dream_text.split())[:180]
    return (
        f"Detailed scenic illustration of this dream moment: {scene}. "
        f"Moment: {caption}. Dream: {excerpt}. "
        f"{hint}, clear environment, characters in the scene, "
        "no text, no speech bubbles, no watermark"
    )


def _extension_for_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if data[:4] == b"RIFF":
        return "webp"
    return "jpg"


def _generate_pollinations(*, prompt: str, out_path: Path) -> Path:
    """Free anonymous Pollinations images (no signup). ~1 request / 15–20s."""
    encoded = quote(prompt[:450])
    # Anonymous free endpoint — do NOT use gen.pollinations.ai without pollen balance.
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=768&height=768&nologo=true&model=flux&seed={int(time.time()) % 100000}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 Dreamframe/1.0",
        "Accept": "image/jpeg,image/png,image/*",
    }

    last_error: Exception | None = None
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        for attempt in range(4):
            response = client.get(url, headers=headers)
            if response.status_code in {402, 429}:
                wait_for = max(int(response.headers.get("Retry-After", 20)), 20)
                current_app.logger.warning(
                    "Free image API busy (attempt %s). Waiting %ss…",
                    attempt + 1,
                    wait_for,
                )
                time.sleep(wait_for)
                last_error = RuntimeError(f"rate limited ({response.status_code})")
                continue
            response.raise_for_status()
            data = response.content
            if len(data) < 2000:
                last_error = RuntimeError("image too small / invalid")
                time.sleep(12)
                continue
            ext = _extension_for_bytes(data)
            final_path = out_path.with_suffix(f".{ext}")
            final_path.write_bytes(data)
            return final_path

    if last_error:
        raise last_error
    raise RuntimeError("Free Pollinations image generation failed")


def _generate_huggingface(*, prompt: str, out_path: Path) -> Path:
    token = (current_app.config.get("HF_TOKEN") or "").strip()
    if not _has_usable_api_key(token):
        raise RuntimeError("HF_TOKEN missing")

    model = current_app.config.get("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/png",
    }
    payload = {"inputs": prompt, "parameters": {"num_inference_steps": 4, "width": 768, "height": 768}}
    endpoints = [
        f"https://router.huggingface.co/hf-inference/models/{model}",
        f"https://api-inference.huggingface.co/models/{model}",
    ]
    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        for url in endpoints:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                continue
            data = response.content
            if len(data) < 2000:
                continue
            ext = _extension_for_bytes(data)
            final_path = out_path.with_suffix(f".{ext}")
            final_path.write_bytes(data)
            return final_path
    raise RuntimeError("Hugging Face image generation failed")


def _generate_one_image(*, prompt: str, out_path: Path) -> Path:
    provider = (current_app.config.get("IMAGE_PROVIDER") or "pollinations").lower()
    if provider == "huggingface":
        return _generate_huggingface(prompt=prompt, out_path=out_path)
    if provider == "auto":
        try:
            return _generate_pollinations(prompt=prompt, out_path=out_path)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("Pollinations failed, trying HF: %s", exc)
            return _generate_huggingface(prompt=prompt, out_path=out_path)
    # Default free platform
    return _generate_pollinations(prompt=prompt, out_path=out_path)


def generate_one_panel_image(
    analysis: AnalysisResult,
    *,
    dream_id: int,
    style: str,
    dream_text: str,
    panel_number: int,
    force: bool = False,
) -> tuple[AnalysisResult, str | None, str | None]:
    """Draw a single panel. Returns (analysis, image_url, error)."""
    if not current_app.config.get("GENERATE_IMAGES", False):
        return analysis, None, "Image generation is turned off."

    target = next((p for p in analysis.panels if p.panel_number == panel_number), None)
    if target is None:
        return analysis, None, "Panel not found."
    if target.image_url and not force:
        return analysis, target.image_url, None

    delete_panel_image(dream_id, panel_number)
    base = _generated_dir() / f"dream_{dream_id}_panel_{panel_number}"
    try:
        prompt = _build_scenic_prompt(target, style=style, dream_text=dream_text)
        final_path = _generate_one_image(prompt=prompt, out_path=base)
        image_url = url_for("static", filename=f"generated/{final_path.name}")
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Scenic image failed for panel %s: %s", panel_number, exc)
        return analysis, None, "The free image API was busy. Try this panel again in a moment."

    updated: list[Panel] = []
    for panel in analysis.panels:
        if panel.panel_number == panel_number:
            updated.append(
                Panel(
                    panel_number=panel.panel_number,
                    caption=panel.caption,
                    scene_description=panel.scene_description,
                    image_url=image_url,
                    reflection_question=panel.reflection_question,
                )
            )
        else:
            updated.append(panel)
    analysis.panels = updated
    return analysis, image_url, None


def attach_panel_images(
    analysis: AnalysisResult,
    *,
    dream_id: int,
    style: str,
    dream_text: str,
) -> tuple[AnalysisResult, int]:
    """Generate all scenic panels (used only if you need a blocking batch)."""
    if not current_app.config.get("GENERATE_IMAGES", False):
        return analysis, 0

    failed = 0
    for panel in list(analysis.panels):
        analysis, _url, error = generate_one_panel_image(
            analysis,
            dream_id=dream_id,
            style=style,
            dream_text=dream_text,
            panel_number=panel.panel_number,
            force=True,
        )
        if error:
            failed += 1
    return analysis, failed
