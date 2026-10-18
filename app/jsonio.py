"""Atomic JSON read/write."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.RLock()


def read_json(path: Path, default: Any = None) -> Any:
    with _lock:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    write_text(path, json.dumps(obj, indent=2, ensure_ascii=False))


def write_text(path: Path, text: str) -> None:
    """Write via temp file + rename so a crash never leaves a half-written file."""
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=path.suffix)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            for attempt in range(5):  # Windows: target may be briefly locked by a reader
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.1)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
