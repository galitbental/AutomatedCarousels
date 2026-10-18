"""Claude CLI adapter and the high-level assistant tasks."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from . import prompts as P


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict | None:
    """First JSON object found in text."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


class ClaudeRunner:
    """Runs `claude -p` headless and returns the structured JSON result."""

    def __init__(self, cwd: Path, settings: Callable[[], dict], popen=subprocess.Popen):
        self.cwd = cwd
        self.settings = settings
        self.popen = popen

    def command(self, prompt: str, schema: dict, chrome: bool = False) -> list[str]:
        s = self.settings()
        exe = shutil.which(s["claude_cmd"]) or s["claude_cmd"]
        # The prompt goes through stdin (no command-line length limit).
        cmd = [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
               "--model", s["model"], "--no-session-persistence", "--add-dir", str(self.cwd)]
        if chrome:
            cmd += ["--chrome", "--permission-mode", "bypassPermissions",
                    "--disallowedTools", "Bash", "PowerShell", "Edit", "Write", "NotebookEdit"]
        else:
            cmd += ["--allowedTools", "Read", "--permission-mode", "dontAsk"]
        return cmd

    def run(self, prompt: str, schema: dict, *, chrome: bool = False, timeout: float | None = None,
            cancel: threading.Event | None = None, log: Callable[[str], None] | None = None) -> dict:
        s = self.settings()
        timeout = timeout or (s["image_timeout"] if chrome else s["text_timeout"])
        cmd = self.command(prompt, schema, chrome)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = self.popen(cmd, cwd=str(self.cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                              creationflags=flags)
        except FileNotFoundError as e:
            raise LLMError(f"Claude CLI not found ({s['claude_cmd']}). Check Settings.") from e
        out: dict[str, str] = {}

        def pump():
            out["stdout"], out["stderr"] = proc.communicate(prompt)

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        start = time.time()
        while t.is_alive():
            t.join(0.5)
            if cancel is not None and cancel.is_set():
                proc.kill()
                t.join(5)
                raise LLMError("Cancelled")
            if time.time() - start > timeout:
                proc.kill()
                t.join(5)
                raise LLMError(f"Claude timed out after {int(timeout)} s")
        stdout, stderr = out.get("stdout", ""), out.get("stderr", "")
        if proc.returncode != 0:
            raise LLMError(f"Claude exited with code {proc.returncode}: {(stderr or stdout)[-800:]}")
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"Unreadable Claude output: {stdout[-500:]}") from e
        if envelope.get("is_error"):
            raise LLMError(f"Claude error: {envelope.get('result', '')[-800:]}")
        if log:
            cost = envelope.get("total_cost_usd")
            log(f"Claude finished in {time.time() - start:.0f} s" + (f" (${cost:.2f})" if cost else ""))
        result = envelope.get("structured_output")
        if not isinstance(result, dict):
            result = extract_json(envelope.get("result") or "")
        if not isinstance(result, dict):
            raise LLMError(f"Claude returned no structured result: {str(envelope.get('result'))[-500:]}")
        return result


class Assistant:
    """Business-level Claude tasks. Tests and demo mode substitute a fake with the same methods."""

    def __init__(self, runner: ClaudeRunner):
        self.runner = runner

    def read_card(self, job: dict, **kw) -> dict:
        return self.runner.run(P.card_prompt(job), P.CARD_SCHEMA, **kw)

    def draft_facts(self, jtype, files: list[str], **kw) -> str:
        return self.runner.run(P.facts_prompt(jtype, files), P.FACTS_SCHEMA, **kw)["markdown"]

    def make_plan(self, prompt: str, **kw) -> dict:
        return self.runner.run(prompt, P.PLAN_SCHEMA, **kw)

    def qa_image(self, image_rel: str, input_rel: str, card_text: str, slide: dict, **kw) -> dict:
        return self.runner.run(P.qa_prompt(image_rel, input_rel, card_text, slide), P.QA_SCHEMA, **kw)

    def chatgpt_generate(self, full_prompt: str, refs_abs: list[str], chat_url: str, chatgpt_url: str,
                         **kw) -> dict:
        return self.runner.run(P.chrome_agent_prompt(full_prompt, refs_abs, chat_url, chatgpt_url),
                               P.CHROME_SCHEMA, chrome=True, **kw)
