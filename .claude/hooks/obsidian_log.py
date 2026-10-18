"""Claude Code Stop hook: append a short entry to the Obsidian project log after each finished task.

Called by Claude Code with the hook input (JSON) on stdin. It reads the session transcript, takes the last user
request and everything the agent did after it, and, if the agent used tools (i.e. did work rather than only
answer), writes an entry to <vault>/InstagramCarousel/Log.md:

    ### <date time> · <title>
    - **Done:** ...
    - **Files:** ...
    - **Open:** ...
    - **Next:** ...

The summary is written by a small headless Claude call (haiku) in a detached background process, so the hook
returns at once. If that call fails, a plain entry is written from the transcript instead.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

VAULT_DIR = Path(os.environ.get("OBSIDIAN_PROJECT_DIR", r"C:\Work\GalitProjects\FirstProject\InstagramCarousel"))
PROJECT_DIR = Path(__file__).resolve().parents[2]
STATE_FILE = Path(__file__).with_name(".obsidian_log_state.json")
CHILD_ENV = "OBSIDIAN_LOG_CHILD"  # set for the summarizing Claude call, so its own Stop hook does nothing
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
QUIET_TOOLS = {"ToolSearch", "TodoWrite"}  # using only these does not count as doing work
SYSTEM_PREFIXES = ("<system-reminder>", "<command-", "<local-command", "<task-notification>", "Caveat:")


# ---------------------------------------------------------------- transcript
def read_transcript(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def _user_text(row: dict) -> str | None:
    """Text of a real user request, or None for tool results and system messages."""
    if row.get("type") != "user" or row.get("isMeta") or row.get("isSidechain"):
        return None
    content = row.get("message", {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content):
            return None
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    else:
        return None
    text = text.strip()
    if not text or text.startswith(SYSTEM_PREFIXES):
        return None
    return text


def last_turn(rows: list[dict]) -> dict | None:
    """The last user request and what the agent did after it."""
    start = next((i for i in range(len(rows) - 1, -1, -1) if _user_text(rows[i]) is not None), None)
    if start is None:
        return None
    tools, files, texts = [], [], []
    for row in rows[start + 1:]:
        if row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        for b in row.get("message", {}).get("content") or []:
            if b.get("type") == "text" and b.get("text", "").strip():
                texts.append(b["text"].strip())
            elif b.get("type") == "tool_use":
                tools.append(b.get("name", ""))
                fp = (b.get("input") or {}).get("file_path") or (b.get("input") or {}).get("notebook_path")
                if b.get("name") in EDIT_TOOLS and fp and fp not in files:
                    files.append(fp)
    return {"id": rows[start].get("uuid") or rows[start].get("promptId") or str(start),
            "request": _user_text(rows[start]), "tools": tools, "files": files, "texts": texts}


def did_work(turn: dict) -> bool:
    return any(t not in QUIET_TOOLS for t in turn["tools"])


def short_path(p: str) -> str:
    path = Path(p)
    for base in (PROJECT_DIR, VAULT_DIR.parent):
        try:
            return path.resolve().relative_to(base.resolve()).as_posix()
        except (ValueError, OSError):
            continue
    return path.as_posix()


# ---------------------------------------------------------------- entry
def fallback_summary(turn: dict) -> dict:
    first_line = turn["request"].splitlines()[0]
    final = turn["texts"][-1] if turn["texts"] else ""
    done = " ".join(final.split())[:400] or "Task finished (no summary)."
    return {"title": first_line[:70] + ("…" if len(first_line) > 70 else ""), "done": done,
            "open_tasks": "see the session", "next_step": "see the session"}


def summary_prompt(turn: dict) -> str:
    final = "\n\n".join(turn["texts"][-3:])[-6000:]
    return (
        "You write one entry for a project log in Obsidian. Project: automated Instagram carousels for the "
        "Be Wished jewelry shop (app 'Carousel Studio'). Summarize the finished task below.\n"
        "Rules: plain English, short. title: at most 8 words. done: 1-2 sentences, what was achieved. "
        "open_tasks: what is still open or waiting for the owner (or 'none'). next_step: the single next step.\n\n"
        f"USER REQUEST:\n{turn['request'][:3000]}\n\n"
        f"FILES CHANGED: {', '.join(short_path(f) for f in turn['files']) or 'none'}\n\n"
        f"AGENT'S FINAL MESSAGES:\n{final}\n"
    )


SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["title", "done", "open_tasks", "next_step"],
          "properties": {k: {"type": "string"} for k in ("title", "done", "open_tasks", "next_step")}}


def claude_summary(turn: dict, timeout: int = 180) -> dict | None:
    exe = shutil.which("claude")
    if not exe:
        return None
    env = {**os.environ, CHILD_ENV: "1"}
    try:
        r = subprocess.run([exe, "-p", "--model", "haiku", "--output-format", "json",
                            "--json-schema", json.dumps(SCHEMA), "--tools", ""],
                           input=summary_prompt(turn), capture_output=True, text=True, encoding="utf-8",
                           timeout=timeout, env=env, cwd=tempfile.gettempdir())
        out = json.loads(r.stdout)
        data = out.get("structured_output") or json.loads(out.get("result", "{}"))
        return data if all(isinstance(data.get(k), str) and data[k].strip() for k in SCHEMA["required"]) else None
    except Exception:
        return None


def one_line(s: str) -> str:
    return " ".join(s.split())


def format_entry(turn: dict, summary: dict, when: datetime) -> str:
    files = ", ".join(f"`{short_path(f)}`" for f in turn["files"]) or "none"
    return (f"\n### {when:%Y-%m-%d %H:%M} · {one_line(summary['title'])}\n"
            f"- **Done:** {one_line(summary['done'])}\n"
            f"- **Files:** {files}\n"
            f"- **Open:** {one_line(summary['open_tasks'])}\n"
            f"- **Next:** {one_line(summary['next_step'])}\n")


def append_entry(text: str, log: Path | None = None) -> Path:
    log = log or VAULT_DIR / "Log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text("---\nproject: InstagramCarousel\n---\n\n# Log\n\nBack to [[InstagramCarousel]]\n", encoding="utf-8")
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return log


# ---------------------------------------------------------------- state (one entry per request)
def already_logged(turn_id: str) -> bool:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("last") == turn_id
    except (OSError, ValueError):
        return False


def remember(turn_id: str) -> None:
    try:
        STATE_FILE.write_text(json.dumps({"last": turn_id}), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- entry points
def write_log(turn_file: Path) -> None:
    """Background part: summarize (slow) and append."""
    turn = json.loads(turn_file.read_text(encoding="utf-8"))
    turn_file.unlink(missing_ok=True)
    summary = claude_summary(turn) or fallback_summary(turn)
    append_entry(format_entry(turn, summary, datetime.fromisoformat(turn["when"])))


def hook(stdin_text: str, background: bool = True) -> str:
    """Hook part: decide quickly whether to log, then hand off. Returns what it did (for tests)."""
    if os.environ.get(CHILD_ENV):
        return "child"
    try:
        data = json.loads(stdin_text or "{}")
    except ValueError:
        return "bad input"
    path = data.get("transcript_path")
    if not path or not Path(path).is_file():
        return "no transcript"
    turn = last_turn(read_transcript(Path(path)))
    if not turn or not did_work(turn):
        return "no work"
    if already_logged(turn["id"]):
        return "already logged"
    remember(turn["id"])
    turn["when"] = datetime.now().isoformat(timespec="minutes")
    fd, name = tempfile.mkstemp(prefix="obsidian_log_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(turn, f)
    if not background:
        write_log(Path(name))
        return "logged"
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--write", name],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)
    return "started"


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        write_log(Path(sys.argv[2]))
        return
    try:
        hook(sys.stdin.read())
    except Exception:
        pass  # never block or disturb the session because of the log
    sys.exit(0)


if __name__ == "__main__":
    main()
