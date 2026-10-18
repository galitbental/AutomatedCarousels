"""Slide images: Downloads pickup, version storage, ChatGPT backend."""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from .jobs import JobError, now
from .paths import IMAGE_EXTS, Project
from . import prompts as P


def pick_download(downloads: Path, since: float, timeout: float = 60, poll: float = 1.0,
                  stable_secs: float = 1.5, cancel: threading.Event | None = None) -> Path | None:
    """Newest image in downloads modified after `since`, once its size stops changing."""
    deadline = time.time() + timeout
    while True:
        candidates = []
        if downloads.is_dir():
            for p in downloads.iterdir():
                try:
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.stat().st_mtime >= since:
                        candidates.append(p)
                except OSError:
                    continue
        if candidates:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            size = newest.stat().st_size
            time.sleep(stable_secs)
            if newest.exists() and newest.stat().st_size == size and size > 0:
                return newest
            continue
        if time.time() >= deadline or (cancel is not None and cancel.is_set()):
            return None
        time.sleep(poll)


def add_version(project: Project, job: dict, n: int, src: Path, origin: str, prompt: str = "",
                move: bool = False, extra: dict | None = None) -> dict:
    """Store src as the next version of slide n (raw/slide_<n>_<k>.<ext>) and make it current."""
    raw = project.work / job["sku"] / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    entry = job["images"].setdefault(str(n), {"versions": [], "current": 0})
    k = len(entry["versions"]) + 1
    while any((raw / f"slide_{n}_{k}{e}").exists() for e in IMAGE_EXTS):
        k += 1
    dest = raw / f"slide_{n}_{k}{src.suffix.lower()}"
    if move:
        shutil.move(str(src), dest)
    else:
        shutil.copy2(src, dest)
    version = {"file": project.rel(dest), "origin": origin, "prompt": prompt, "created": now(), "qa": None}
    if extra:
        version.update(extra)
    entry["versions"].append(version)
    entry["current"] = len(entry["versions"]) - 1
    return version


def resolve_refs(project: Project, refs: list[str]) -> list[str]:
    out = []
    for r in refs:
        try:
            p = project.abs(r)
        except ValueError:
            continue
        if p.exists():
            out.append(str(p))
    return out


UPLOAD_MAX_PX = 2048
UPLOAD_MAX_BYTES = 8 * 1024 * 1024


def upload_copies(paths: list[str], folder: Path) -> list[str]:
    """Upload-friendly copies of reference images (ChatGPT rejects files over ~10 MB)."""
    from PIL import Image, ImageOps

    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i, p in enumerate(paths, start=1):
        src = Path(p)
        try:
            with Image.open(src) as im:
                small_enough = src.stat().st_size <= UPLOAD_MAX_BYTES and max(im.size) <= UPLOAD_MAX_PX
                if small_enough:
                    out.append(str(src))
                    continue
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((UPLOAD_MAX_PX, UPLOAD_MAX_PX))
                dest = folder / f"ref{i}_{src.stem[:40]}.jpg"
                im.save(dest, "JPEG", quality=90)
                out.append(str(dest))
        except OSError:
            out.append(str(src))
    return out


class ChatGPTChromeBackend:
    """Generates via ChatGPT, driven by a headless Claude session with Claude in Chrome."""

    name = "claude_chrome"

    def __init__(self, project: Project, assistant, settings: Callable[[], dict]):
        self.project = project
        self.assistant = assistant
        self.settings = settings

    def generate(self, job: dict, slide: dict, cancel: threading.Event | None = None,
                 log: Callable[[str], None] = print) -> tuple[Path, str]:
        s = self.settings()
        full = P.image_prompt(slide["prompt"], s["image_style_suffix"])
        refs = upload_copies(resolve_refs(self.project, slide.get("references", [])),
                             self.project.work / job["sku"] / "upload_refs")
        started = time.time() - 2
        log(f"ChatGPT: generating slide {slide['n']} with {len(refs)} reference image(s)…")
        result = self.assistant.chatgpt_generate(full, refs, job.get("chat_url", ""), s["chatgpt_url"],
                                                 cancel=cancel, log=log)
        status = result.get("status")
        if status == "limit":
            raise JobError(f"ChatGPT usage limit: {result.get('message', '')}. Try later or use the manual path.")
        if status != "done":
            raise JobError(f"ChatGPT generation failed: {result.get('message', '')}")
        log("Waiting for the download to appear in the Downloads folder…")
        path = pick_download(Path(s["downloads_dir"]), started, timeout=90, cancel=cancel)
        if not path:
            raise JobError("ChatGPT finished but no new image appeared in the Downloads folder. "
                           "Download it manually and use 'Import latest download'.")
        return path, result.get("chat_url", "")
