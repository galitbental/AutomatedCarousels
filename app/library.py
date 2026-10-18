"""Reusable style library (StyleLibrary/<Style>/<slot>/)."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import IMAGE_EXTS, Project

COMMON = "_Common"
SLOTS = ("options", "quality", "cta")


class Library:
    def __init__(self, project: Project):
        self.project = project

    def _meta_path(self, style: str) -> Path:
        return self.project.library / style / "library.json"

    def _meta(self, style: str) -> dict:
        return read_json(self._meta_path(style), {}) or {}

    def variants(self, style: str, slot: str) -> list[dict]:
        folder = self.project.library / style / slot
        if not folder.is_dir():
            return []
        meta = self._meta(style)
        out = []
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                key = f"{slot}/{p.name}"
                m = meta.get(key, {})
                out.append({"style": style, "slot": slot, "variant": p.name, "file": self.project.rel(p),
                            "approved": m.get("approved", False), "prompt": m.get("prompt", ""),
                            "sku": m.get("sku", ""), "date": m.get("date", "")})
        return out

    def add_variant(self, style: str, slot: str, src: Path, approved: bool = False,
                    prompt: str = "", sku: str = "") -> dict:
        if slot not in SLOTS:
            raise ValueError(f"Unknown library slot '{slot}'")
        folder = self.project.library / style / slot
        folder.mkdir(parents=True, exist_ok=True)
        n = 1
        while any((folder / f"v{n}{ext}").exists() for ext in IMAGE_EXTS):
            n += 1
        dest = folder / f"v{n}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        meta = self._meta(style)
        meta[f"{slot}/{dest.name}"] = {"approved": approved, "prompt": prompt, "sku": sku,
                                       "date": date.today().isoformat()}
        write_json(self._meta_path(style), meta)
        return next(v for v in self.variants(style, slot) if v["variant"] == dest.name)

    def set_approved(self, style: str, slot: str, variant: str, approved: bool) -> None:
        meta = self._meta(style)
        meta.setdefault(f"{slot}/{variant}", {})["approved"] = approved
        write_json(self._meta_path(style), meta)

    def remove(self, style: str, slot: str, variant: str) -> None:
        p = self.project.library / style / slot / variant
        if not self.project.is_inside(p, self.project.library):
            raise ValueError("Invalid library path")
        if p.exists():
            p.unlink()
        meta = self._meta(style)
        meta.pop(f"{slot}/{variant}", None)
        write_json(self._meta_path(style), meta)

    def lru_pick(self, style: str, slot: str, usage: list[dict]) -> dict | None:
        """Least-recently-used approved variant (never-used first)."""
        approved = [v for v in self.variants(style, slot) if v["approved"]]
        if not approved:
            return None
        last_use: dict[str, int] = {}
        for i, u in enumerate(usage):
            if u.get("style") == style and u.get("slot") == slot:
                last_use[u["variant"]] = i
        return min(approved, key=lambda v: last_use.get(v["variant"], -1))

    def seed_common(self) -> None:
        """Use the user's finished packaging image as the first CTA background."""
        box = self.project.common / "Box.png"
        if box.exists() and not self.variants(COMMON, "cta"):
            self.add_variant(COMMON, "cta", box, approved=True, prompt="RealProductPhotos/Common/Box.png")

    def overview(self) -> list[dict]:
        out = []
        if self.project.library.is_dir():
            for d in sorted(self.project.library.iterdir()):
                if d.is_dir():
                    out.append({"style": d.name,
                                "slots": {s: self.variants(d.name, s) for s in SLOTS if (d / s).is_dir()}})
        return out
