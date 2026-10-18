"""Project folder layout and path confinement."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class Project:
    """All folders of one Carousel Studio project, derived from its root."""

    root: Path

    @property
    def inputs(self) -> Path:
        return self.root / "DataFromUser"

    @property
    def photos(self) -> Path:
        return self.root / "RealProductPhotos"

    @property
    def common(self) -> Path:
        return self.photos / "Common"

    @property
    def library(self) -> Path:
        return self.root / "StyleLibrary"

    @property
    def carousels(self) -> Path:
        return self.root / "Carousels"

    @property
    def work(self) -> Path:
        return self.carousels / "_work"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def doc(self) -> Path:
        return self.root / "doc"

    @property
    def facts(self) -> Path:
        return self.doc / "facts"

    def ensure(self) -> None:
        for d in (self.inputs, self.photos, self.library, self.carousels,
                  self.work, self.data, self.facts):
            d.mkdir(parents=True, exist_ok=True)

    def rel(self, path: Path | str) -> str:
        """Project-relative POSIX path."""
        return Path(path).resolve().relative_to(self.root.resolve()).as_posix()

    def abs(self, rel: str | Path) -> Path:
        """Absolute path for a project-relative path; refuses anything outside the root."""
        p = Path(rel)
        p = p if p.is_absolute() else self.root / p
        p = p.resolve()
        root = self.root.resolve()
        if p != root and root not in p.parents:
            raise ValueError(f"Path outside project: {rel}")
        return p

    def is_inside(self, path: Path, folder: Path) -> bool:
        path, folder = path.resolve(), folder.resolve()
        return path == folder or folder in path.parents


def list_images(folder: Path) -> list[Path]:
    """Image files directly inside folder, sorted by name."""
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                  key=lambda p: p.name.lower())
