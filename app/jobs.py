"""Job (one carousel in progress) storage and stage state machine."""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import Project

STAGES = ["intake", "facts", "plan", "images", "slides", "final"]
SAFE_SKU = re.compile(r"^[\w\-\(\)\. ]+$")


class JobError(Exception):
    """A user-facing error; status is the HTTP code the API should return."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_job(sku: str, input_rel: str, sku_info: dict) -> dict:
    return {
        "sku": sku,
        "input_file": input_rel,
        "created": now(),
        "updated": now(),
        "sku_info": sku_info,
        "stages": {s: ("open" if s == "intake" else "locked") for s in STAGES},
        "intake": {"from": [], "giver_name": "", "to": [], "gender": "female", "age_group": [],
                   "event": [], "tone": "gentle" if sku_info.get("loss_hint") else "joyful",
                   "card_headline": "", "card_text": "", "signature": "", "placeholder_name": "",
                   "notes": "", "suggested": {}, "suggested_events": [], "source": ""},
        "catalog": {},
        "plan": {"hooks": ["", "", ""], "hook_choice": 0, "slides": [], "caption": "", "hashtags": [],
                 "hashtag_target": None, "voice": "", "carousel_type": ""},
        "images": {},
        "chat_url": "",
        "render": {"files": {}, "rendered_at": "", "dirty": {}},
        "final": {"dest": ""},
        "log": [],
    }


MULTI = ("from", "to", "event", "age_group")


def as_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [v.strip()] if isinstance(v, str) and v.strip() else []


def joined(v, sep: str = " / ") -> str:
    """Multi-select value as readable text ("mom / grandma")."""
    return sep.join(as_list(v))


def migrate(job: dict) -> dict:
    """Bring jobs saved by older versions up to date."""
    it = job["intake"]
    for k in MULTI:
        it[k] = as_list(it.get(k))
    it.pop("confirmed", None)
    it.setdefault("source", "")
    job.setdefault("catalog", {})
    job["plan"].setdefault("voice", "")
    job["plan"].setdefault("carousel_type", "")
    return job


def approve(job: dict, stage: str) -> None:
    i = STAGES.index(stage)
    job["stages"][stage] = "approved"
    if i + 1 < len(STAGES) and job["stages"][STAGES[i + 1]] == "locked":
        job["stages"][STAGES[i + 1]] = "open"


def reopen(job: dict, stage: str) -> None:
    if job["stages"][stage] not in ("approved", "stale"):
        raise JobError(f"Stage '{stage}' is not approved.", 409)
    job["stages"][stage] = "open"
    for later in STAGES[STAGES.index(stage) + 1:]:
        if job["stages"][later] == "approved":
            job["stages"][later] = "stale"


def editable(job: dict, stage: str) -> bool:
    return job["stages"][stage] in ("open", "stale")


def require_editable(job: dict, stage: str) -> None:
    if not editable(job, stage):
        state = job["stages"][stage]
        hint = " Reopen it first." if state == "approved" else ""
        raise JobError(f"Stage '{stage}' is {state}.{hint}", 409)


def require_approved(job: dict, *stages: str) -> None:
    for s in stages:
        if job["stages"][s] != "approved":
            raise JobError(f"Approve the '{s}' stage first.", 409)


def add_log(job: dict, msg: str) -> None:
    job["log"].append({"ts": now(), "msg": msg})
    job["log"] = job["log"][-300:]


def mark_dirty(job: dict, n: int | None = None) -> None:
    """Record that slide n (or every slide) changed since its last render."""
    dirty = job["render"].setdefault("dirty", {})
    ts = time.time()
    for x in ([s["n"] for s in job["plan"]["slides"]] if n is None else [n]):
        dirty[str(x)] = ts


def current_image(job: dict, n: int) -> dict | None:
    entry = job["images"].get(str(n))
    if not entry or not entry["versions"]:
        return None
    return entry["versions"][entry["current"]]


class JobStore:
    def __init__(self, project: Project):
        self.project = project

    def dir(self, sku: str) -> Path:
        if not SAFE_SKU.match(sku) or ".." in sku:
            raise JobError(f"Invalid SKU '{sku}'")
        return self.project.work / sku

    def exists(self, sku: str) -> bool:
        return (self.dir(sku) / "job.json").exists()

    def load(self, sku: str) -> dict:
        job = read_json(self.dir(sku) / "job.json")
        if job is None:
            raise JobError(f"No job for '{sku}'", 404)
        return migrate(job)

    def save(self, job: dict) -> dict:
        job["updated"] = now()
        write_json(self.dir(job["sku"]) / "job.json", job)
        return job

    def create(self, sku: str, input_rel: str, sku_info: dict) -> dict:
        if self.exists(sku):
            return self.load(sku)
        d = self.dir(sku)
        for sub in ("raw", "render", "slides"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        return self.save(new_job(sku, input_rel, sku_info))

    def list(self) -> list[dict]:
        out = []
        if self.project.work.is_dir():
            for d in sorted(self.project.work.iterdir()):
                job = read_json(d / "job.json") if d.is_dir() else None
                if job:
                    current = next((s for s in STAGES if job["stages"][s] != "approved"), "final")
                    out.append({"sku": job["sku"], "updated": job["updated"], "stage": current,
                                "stages": job["stages"], "input_file": job["input_file"],
                                "jewelry_type": job["sku_info"].get("jewelry_type", "")})
        return out

    def delete(self, sku: str) -> None:
        d = self.dir(sku)
        if not self.project.is_inside(d, self.project.work) or d == self.project.work:
            raise JobError("Refusing to delete outside the work folder", 500)
        if d.exists():
            shutil.rmtree(d)
