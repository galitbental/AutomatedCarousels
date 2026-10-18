"""User settings (data/settings.json)."""
from __future__ import annotations

from pathlib import Path

from .jsonio import read_json, write_json
from .paths import Project

IMAGE_STYLE_SUFFIX = (
    "Style and rules: photorealistic premium lifestyle photograph, 4:5 portrait. "
    "Dark, warm, candlelit luxury mood: black and dark marble surfaces with gold veins, warm gold bokeh, "
    "baby's breath flowers, gold ribbon, soft cinematic light. "
    "Do NOT add any text, captions, letters or watermarks to the image. "
    "The only allowed text is the poem card itself and the Be Wished logo printed on the box. "
    "If the gift box lid or the closed box is visible, it must be the BLACK Be Wished box with the gold "
    "'BE WISHED Handmade & Personalized' logo exactly like the reference. "
    "If the poem card is visible, keep its text, layout and flowers exactly as in the reference photo. "
    "The jewelry must look identical to the reference photo (shape, size, metal color, stones/pearls). "
    "Natural hands and faces, no distortions."
)

DEFAULTS: dict = {
    "claude_cmd": "claude",
    "model": "sonnet",
    "image_backend": "claude_chrome",
    "downloads_dir": str(Path.home() / "Downloads"),
    "catalog_dir": r"V:\Amazon\Catalog\AllCatalog\_ALL_SKU_POEM_CARDS",
    "chatgpt_url": "https://chatgpt.com/",
    "text_timeout": 300,
    "image_timeout": 600,
    "qa_enabled": True,
    "max_auto_retries": 1,
    "overlap_threshold": 0.7,
    "bell_sound": True,
    "image_style_suffix": IMAGE_STYLE_SUFFIX,
    "port": 8765,
}


def settings_path(project: Project) -> Path:
    return project.data / "settings.json"


def load_settings(project: Project) -> dict:
    stored = read_json(settings_path(project), {}) or {}
    merged = {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}
    if not settings_path(project).exists():
        write_json(settings_path(project), merged)
    return merged


def save_settings(project: Project, values: dict) -> dict:
    current = load_settings(project)
    for k, v in values.items():
        if k not in DEFAULTS:
            continue
        default = DEFAULTS[k]
        if isinstance(default, bool):
            v = bool(v)
        elif isinstance(default, (int, float)) and not isinstance(default, bool):
            v = type(default)(v)
        else:
            v = str(v)
        current[k] = v
    write_json(settings_path(project), current)
    return current
