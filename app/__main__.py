"""Entry point: python -m app [--fake] [--no-window] [--port N]"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from .paths import Project
from .render import CHROME_PATHS
from .version import code_version

ROOT = Path(__file__).resolve().parent.parent


def _get(url: str, timeout: float = 1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def running_server(url: str) -> dict | None:
    """Ping info of a Carousel Studio already listening at url, else None."""
    try:
        info = _get(url + "/api/ping")
    except Exception:
        return None
    return info if info.get("app") == "carousel-studio" else None


def replace_server(url: str, info: dict) -> bool:
    """Stop an older server so the updated code can start. False if it is busy with a task."""
    try:
        if _get(url + "/api/log?after=999999999").get("tasks"):
            return False
    except Exception:
        pass
    try:
        req = urllib.request.Request(url + "/api/shutdown", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).close()
    except Exception:  # servers from before /api/shutdown existed: end the process by its pid
        try:
            os.kill(int(info["pid"]), signal.SIGTERM)
        except Exception:
            return False
    for _ in range(50):
        if not running_server(url):
            return True
        time.sleep(0.2)
    return False


def open_window(url: str) -> None:
    """Chrome/Edge app-mode window; default browser as last resort."""
    for exe in CHROME_PATHS:
        if exe.exists():
            subprocess.Popen([str(exe), f"--app={url}", "--window-size=1500,950", "--new-window"])
            return
    webbrowser.open(url)


def main() -> None:
    ap = argparse.ArgumentParser(description="Carousel Studio")
    ap.add_argument("--fake", action="store_true", help="demo mode: no Claude/ChatGPT calls")
    ap.add_argument("--no-window", action="store_true")
    ap.add_argument("--port", type=int)
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args()

    project = Project(args.root.resolve())
    project.ensure()
    from .settings import load_settings
    port = args.port or int(load_settings(project)["port"])
    url = f"http://127.0.0.1:{port}"
    info = running_server(url)
    if info and info.get("version") == code_version():
        print(f"Carousel Studio is already running at {url}. Opening the window.")
        if not args.no_window:
            open_window(url)
        return
    if info:
        print("An older version of Carousel Studio is running. Replacing it with the updated version...")
        if not replace_server(url, info):
            print("The running version is busy with a task. Finish or cancel it, then start again.")
            if not args.no_window:
                open_window(url)
            return

    from .server import build_studio, create_app
    fake = args.fake or os.environ.get("CAROUSEL_FAKE") == "1"
    studio = build_studio(project, fake=fake)
    app = create_app(studio)
    print(f"Carousel Studio{' (DEMO MODE)' if fake else ''} running at {url}")
    print("Close this window to stop the application.")
    if not args.no_window:
        threading.Thread(target=lambda: (time.sleep(1.0), open_window(url)), daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    sys.exit(main())
