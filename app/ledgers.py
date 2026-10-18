"""Hook, hashtag and library-usage ledgers (data/*.json)."""
from __future__ import annotations

import re
from datetime import date

from .jsonio import read_json, write_json
from .paths import Project

MIN_TAGS, MAX_TAGS = 3, 30


def normalize_tag(tag: str) -> str:
    t = re.sub(r"[^0-9a-z_]", "", tag.strip().lower().lstrip("#"))
    return f"#{t}" if t else ""


def parse_hashtags(value: str | list[str]) -> list[str]:
    """Normalized, de-duplicated tags (order kept) from text or a list."""
    items = value if isinstance(value, list) else re.split(r"[\s,;]+", value or "")
    out: list[str] = []
    for item in items:
        for part in str(item).replace("#", " #").split():
            t = normalize_tag(part)
            if t and t not in out:
                out.append(t)
    return out


def normalize_hook(hook: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", hook.lower())).strip()


def overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


class Ledgers:
    def __init__(self, project: Project):
        self.project = project

    def _path(self, name: str):
        return self.project.data / f"{name}.json"

    def _load(self, name: str) -> list:
        return read_json(self._path(name), []) or []

    def _append(self, name: str, entry: dict) -> None:
        items = self._load(name)
        items.append(entry)
        write_json(self._path(name), items)

    # hooks
    def hooks(self) -> list[dict]:
        return self._load("hooks")

    def hook_used(self, hook: str) -> dict | None:
        n = normalize_hook(hook)
        return next((h for h in self.hooks() if normalize_hook(h["hook"]) == n), None) if n else None

    def add_hook(self, hook: str, sku: str) -> None:
        self._append("hooks", {"hook": hook, "sku": sku, "date": date.today().isoformat()})

    # hashtags
    def hashtag_sets(self) -> list[dict]:
        return self._load("hashtags")

    def add_hashtags(self, tags: list[str], sku: str) -> None:
        self._append("hashtags", {"sku": sku, "date": date.today().isoformat(), "tags": parse_hashtags(tags)})

    def check_hashtags(self, tags: list[str] | str, threshold: float = 0.7) -> dict:
        """Count, hard errors (range, exact duplicate) and soft warnings (overlap)."""
        tags = parse_hashtags(tags)
        errors: list[str] = []
        warnings: list[str] = []
        if not MIN_TAGS <= len(tags) <= MAX_TAGS:
            errors.append(f"Use between {MIN_TAGS} and {MAX_TAGS} hashtags (now {len(tags)}).")
        current = set(tags)
        closest = None
        for entry in self.hashtag_sets():
            prev = set(parse_hashtags(entry["tags"]))
            if prev == current and current:
                errors.append(f"Identical hashtag set already used by {entry['sku']} ({entry['date']}).")
            ov = overlap(current, prev)
            if closest is None or ov > closest["overlap"]:
                closest = {"sku": entry["sku"], "date": entry["date"], "overlap": round(ov, 2)}
        if closest and closest["overlap"] > threshold and not any("Identical" in e for e in errors):
            warnings.append(f"{int(closest['overlap'] * 100)}% overlap with {closest['sku']} "
                            f"({closest['date']}); threshold {int(threshold * 100)}%.")
        return {"tags": tags, "count": len(tags), "errors": errors, "warnings": warnings, "closest": closest}

    # posts (voice / carousel type rotation)
    def posts(self) -> list[dict]:
        return self._load("posts")

    def add_post(self, sku: str, voice: str, carousel_type: str, hook: str) -> None:
        self._append("posts", {"sku": sku, "date": date.today().isoformat(), "voice": voice,
                               "carousel_type": carousel_type, "hook": hook})

    # library usage
    def library_usage(self) -> list[dict]:
        return self._load("library_usage")

    def add_library_usage(self, style: str, slot: str, variant: str, sku: str) -> None:
        self._append("library_usage", {"style": style, "slot": slot, "variant": variant, "sku": sku,
                                        "date": date.today().isoformat()})
