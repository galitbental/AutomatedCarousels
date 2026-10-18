"""The Claude Code Stop hook that writes the Obsidian project log (.claude/hooks/obsidian_log.py)."""
import importlib.util
import json
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "obsidian_log.py"


@pytest.fixture
def ol(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("obsidian_log", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "VAULT_DIR", tmp_path / "vault" / "InstagramCarousel")
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "claude_summary", lambda turn: None)  # no Claude call in tests
    monkeypatch.delenv(mod.CHILD_ENV, raising=False)
    return mod


def transcript(tmp_path, rows):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return json.dumps({"transcript_path": str(p)})


def user(text, uuid="u1"):
    return {"type": "user", "uuid": uuid, "message": {"role": "user", "content": text}}


def assistant(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def tool(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


def test_work_is_logged_with_files(ol, tmp_path):
    rows = [user("old request", "u0"), assistant({"type": "text", "text": "old"}),
            user("add a bell sound", "u1"),
            assistant(tool("Read", file_path="C:/x/a.py"), tool("Edit", file_path=str(ol.PROJECT_DIR / "app" / "web" / "app.js"))),
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
            {"type": "user", "isMeta": True, "message": {"content": "<system-reminder>x</system-reminder>"}},
            assistant(tool("Write", file_path=str(ol.PROJECT_DIR / "app" / "web" / "app.js")),
                      {"type": "text", "text": "The bell plays when generation finishes."})]
    assert ol.hook(transcript(tmp_path, rows), background=False) == "logged"
    log = (ol.VAULT_DIR / "Log.md").read_text(encoding="utf-8")
    assert "· add a bell sound" in log and "`app/web/app.js`" in log and log.count("app.js") == 1
    assert "**Done:** The bell plays when generation finishes." in log and "**Next:**" in log
    # Stop can fire again for the same request: no second entry
    assert ol.hook(transcript(tmp_path, rows), background=False) == "already logged"


def test_chat_only_and_guards(ol, tmp_path, monkeypatch):
    rows = [user("what does this do?"), assistant({"type": "text", "text": "It renders slides."}),
            assistant(tool("ToolSearch", query="x"))]
    assert ol.hook(transcript(tmp_path, rows), background=False) == "no work"
    assert not (ol.VAULT_DIR / "Log.md").exists()
    assert ol.hook("not json") == "bad input"
    assert ol.hook(json.dumps({"transcript_path": str(tmp_path / "missing.jsonl")})) == "no transcript"
    monkeypatch.setenv(ol.CHILD_ENV, "1")  # the summarizing Claude call must not log itself
    assert ol.hook(transcript(tmp_path, [user("x"), assistant(tool("Bash", command="ls"))])) == "child"


def test_entry_format(ol):
    from datetime import datetime
    turn = {"request": "x", "files": [], "texts": []}
    e = ol.format_entry(turn, {"title": "Bell\nsound", "done": "Added.", "open_tasks": "none", "next_step": "Review"},
                        datetime(2026, 10, 18, 9, 5))
    assert e == ("\n### 2026-10-18 09:05 · Bell sound\n- **Done:** Added.\n- **Files:** none\n"
                 "- **Open:** none\n- **Next:** Review\n")
