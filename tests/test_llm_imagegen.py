import json
import threading
import time
from pathlib import Path

import pytest

from app.fakes import FakeAssistant, placeholder_image
from app.imagegen import ChatGPTChromeBackend, add_version, pick_download, resolve_refs
from app.jobs import JobError, new_job
from app.llm import ClaudeRunner, LLMError, extract_json
from app.settings import DEFAULTS


# ---------------------------------------------------------------- extract_json
def test_extract_json():
    assert extract_json('noise {"a": {"b": "}"}} tail') == {"a": {"b": "}"}}
    assert extract_json("```json\n{\"x\": 1}\n```") == {"x": 1}
    assert extract_json("{broken {\"ok\": true}") == {"ok": True}
    assert extract_json("nothing") is None


# ---------------------------------------------------------------- ClaudeRunner with a fake process
class FakeProc:
    def __init__(self, stdout="", stderr="", code=0, delay=0.0):
        self._out, self._err, self.returncode, self.delay = stdout, stderr, code, delay
        self.killed = False
        self.input = None

    def communicate(self, input=None):
        self.input = input
        end = time.time() + self.delay
        while time.time() < end and not self.killed:
            time.sleep(0.02)
        return self._out, self._err

    def kill(self):
        self.killed = True


def runner(proc, tmp_path, **settings):
    calls = []

    def popen(cmd, **kw):
        calls.append((cmd, kw))
        return proc

    s = {**DEFAULTS, **settings}
    return ClaudeRunner(tmp_path, lambda: s, popen=popen), calls


SCHEMA = {"type": "object"}


def test_runner_structured_output(tmp_path):
    proc = FakeProc(json.dumps({"is_error": False, "structured_output": {"a": 1}, "result": "x", "total_cost_usd": 0.1}))
    r, calls = runner(proc, tmp_path)
    logs = []
    assert r.run("hello", SCHEMA, log=logs.append) == {"a": 1}
    cmd = calls[0][0]
    assert "-p" in cmd and "--json-schema" in cmd and "--allowedTools" in cmd and "--chrome" not in cmd
    assert "hello" not in cmd and proc.input == "hello"  # prompt via stdin
    assert logs and "$0.10" in logs[0]


def test_runner_fallback_to_result_text(tmp_path):
    r, _ = runner(FakeProc(json.dumps({"result": 'Here: {"b": 2}'})), tmp_path)
    assert r.run("p", SCHEMA) == {"b": 2}


def test_runner_errors(tmp_path):
    r, _ = runner(FakeProc("", "boom", code=1), tmp_path)
    with pytest.raises(LLMError, match="boom"):
        r.run("p", SCHEMA)
    r, _ = runner(FakeProc(json.dumps({"is_error": True, "result": "bad"})), tmp_path)
    with pytest.raises(LLMError, match="bad"):
        r.run("p", SCHEMA)
    r, _ = runner(FakeProc("not json"), tmp_path)
    with pytest.raises(LLMError):
        r.run("p", SCHEMA)
    r, _ = runner(FakeProc(json.dumps({"result": "no json here"})), tmp_path)
    with pytest.raises(LLMError, match="no structured"):
        r.run("p", SCHEMA)


def test_runner_timeout_and_cancel(tmp_path):
    proc = FakeProc("{}", delay=5)
    r, _ = runner(proc, tmp_path, text_timeout=0.3)
    with pytest.raises(LLMError, match="timed out"):
        r.run("p", SCHEMA)
    assert proc.killed
    proc = FakeProc("{}", delay=5)
    r, _ = runner(proc, tmp_path)
    ev = threading.Event()
    threading.Timer(0.3, ev.set).start()
    with pytest.raises(LLMError, match="Cancelled"):
        r.run("p", SCHEMA, cancel=ev)


def test_runner_chrome_flags(tmp_path):
    r, calls = runner(FakeProc(json.dumps({"structured_output": {}})), tmp_path)
    r.run("p", SCHEMA, chrome=True)
    cmd = calls[0][0]
    assert "--chrome" in cmd and "bypassPermissions" in cmd and "--disallowedTools" in cmd


def test_runner_missing_cli(tmp_path):
    def popen(*a, **k):
        raise FileNotFoundError()
    r = ClaudeRunner(tmp_path, lambda: {**DEFAULTS, "claude_cmd": "no-such-claude"}, popen=popen)
    with pytest.raises(LLMError, match="not found"):
        r.run("p", SCHEMA)


# ---------------------------------------------------------------- downloads pickup
def test_pick_download_ignores_old_and_partial(tmp_path):
    old = placeholder_image(tmp_path / "old.png", "old")
    past = time.time() - 100
    import os
    os.utime(old, (past, past))
    (tmp_path / "x.crdownload").write_bytes(b"123")
    since = time.time() - 1
    assert pick_download(tmp_path, since, timeout=0.2, stable_secs=0.05) is None
    new = placeholder_image(tmp_path / "ChatGPT Image.png", "new")
    assert pick_download(tmp_path, since, timeout=1, stable_secs=0.05) == new


def test_pick_download_waits_for_file(tmp_path):
    since = time.time() - 1

    def later():
        time.sleep(0.4)
        placeholder_image(tmp_path / "late.webp", "late")
    threading.Thread(target=later).start()
    assert pick_download(tmp_path, since, timeout=3, poll=0.1, stable_secs=0.1).name == "late.webp"


def test_add_version_and_refs(proj):
    job = new_job("S1_G_IC", "DataFromUser/GodDaughter1_G_IC.jpg", {})
    src = proj.common / "Box2.png"
    v1 = add_version(proj, job, 3, src, "upload")
    v2 = add_version(proj, job, 3, src, "upload", extra={"library_variant": "v1.png"})
    assert v1["file"].endswith("raw/slide_3_1.png") and v2["file"].endswith("raw/slide_3_2.png")
    assert job["images"]["3"]["current"] == 1 and v2["library_variant"] == "v1.png"
    assert src.exists()  # copied, not moved
    refs = resolve_refs(proj, ["RealProductPhotos/Common/Box2.png", "missing.png", "../outside.png"])
    assert len(refs) == 1 and refs[0].endswith("Box2.png")


# ---------------------------------------------------------------- ChatGPT backend
class DownloadingAssistant(FakeAssistant):
    def __init__(self, downloads: Path, status="done", write=True):
        super().__init__()
        self.downloads, self.status, self.write = downloads, status, write
        self.args = None

    def chatgpt_generate(self, full_prompt, refs_abs, chat_url, chatgpt_url, **kw):
        self.args = (full_prompt, refs_abs, chat_url, chatgpt_url)
        if self.write:
            placeholder_image(self.downloads / "ChatGPT Image.png", "gen")
        return {"status": self.status, "chat_url": "https://chatgpt.com/c/123", "message": "msg"}


def _backend(proj, downloads, **kw):
    a = DownloadingAssistant(downloads, **kw)
    s = {**DEFAULTS, "downloads_dir": str(downloads)}
    return ChatGPTChromeBackend(proj, a, lambda: s), a


SLIDE = {"n": 1, "prompt": "A scene", "references": ["RealProductPhotos/Common/Box2.png"]}


def test_backend_success(proj, downloads):
    b, a = _backend(proj, downloads)
    job = new_job("S", "x", {})
    path, url = b.generate(job, SLIDE, log=lambda m: None)
    assert path.name == "ChatGPT Image.png" and url.endswith("/123")
    assert "A scene" in a.args[0] and "Do NOT add any text" in a.args[0]
    assert a.args[1][0].endswith("Box2.png")


@pytest.mark.parametrize("status,write,match", [("limit", True, "limit"), ("failed", True, "failed"),
                                                ("done", False, "no new image")])
def test_backend_failures(proj, downloads, status, write, match, monkeypatch):
    import app.imagegen as ig
    real = ig.pick_download
    monkeypatch.setattr(ig, "pick_download", lambda *a, **k: real(a[0], a[1], timeout=0.2, stable_secs=0.05))
    b, _ = _backend(proj, downloads, status=status, write=write)
    with pytest.raises(JobError, match=match):
        b.generate(new_job("S", "x", {}), SLIDE, log=lambda m: None)
