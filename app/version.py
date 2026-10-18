"""Code fingerprint: lets a new launch detect (and replace) a server started from older code."""
from __future__ import annotations

import hashlib
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SUFFIXES = {".py", ".js", ".css", ".html", ".svg"}


def code_version(root: Path = APP_DIR) -> str:
    h = hashlib.sha1()
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:12]
