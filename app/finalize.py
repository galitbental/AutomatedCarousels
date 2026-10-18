"""Approve & Save: write the final carousel folder, update ledgers, then clean up (SRS FR-FIN-2/3)."""
from __future__ import annotations

import re
import shutil
from datetime import date

from .caption import caption_file_text, chosen_hook, plan_markdown
from .jobs import STAGES, JobError, JobStore, approve, as_list, now, require_approved
from .jsonio import write_json, write_text
from .ledgers import Ledgers
from .paths import Project


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:40] or "carousel"


def destination(project: Project, job: dict, today: date | None = None) -> str:
    today = today or date.today()
    events = as_list(job["intake"].get("event"))
    base = f"{today.isoformat()}_{job['sku']}_{slug(events[0] if events else '')}"
    name, i = base, 2
    while (project.carousels / name).exists():
        name = f"{base}-{i}"
        i += 1
    return name


def finalize(project: Project, store: JobStore, ledgers: Ledgers, job: dict, threshold: float = 0.7,
             log=print) -> dict:
    require_approved(job, *STAGES[:-1])
    check = ledgers.check_hashtags(job["plan"]["hashtags"], threshold)
    if check["errors"]:
        raise JobError(" ".join(check["errors"]))
    slides = job["plan"]["slides"]
    pngs = [project.abs(job["render"]["files"].get(str(s["n"]), "")) for s in slides]
    if any(not p.is_file() for p in pngs):
        raise JobError("Some slides are not rendered. Render and approve the Slides stage again.")

    dest = project.carousels / destination(project, job)
    work = store.dir(job["sku"])
    try:
        dest.mkdir(parents=True)
        written = []
        for i, png in enumerate(pngs, start=1):
            target = dest / f"bewished_slide_{i}.png"
            shutil.copy2(png, target)
            written.append(target)
        cap = dest / "POST CAPTION and HASHTAGS.txt"
        write_text(cap, caption_file_text(job["plan"]))
        md = dest / "plan.md"
        write_text(md, plan_markdown(job))
        written += [cap, md]
        if (work / "raw").is_dir():
            shutil.copytree(work / "raw", dest / "raw")
        job = dict(job)
        job["final"] = {"dest": project.rel(dest), "saved": now()}
        approve(job, "final")
        write_json(dest / "job.json", job)
        written.append(dest / "job.json")
        missing = [p.name for p in written if not p.is_file() or p.stat().st_size == 0]
        if missing:
            raise JobError(f"Verification failed, missing: {', '.join(missing)}")
    except Exception:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        raise
    log(f"Saved carousel to {project.rel(dest)}")

    # Ledgers (only after a verified save)
    ledgers.add_hook(chosen_hook(job["plan"]), job["sku"])
    ledgers.add_hashtags(job["plan"]["hashtags"], job["sku"])
    ledgers.add_post(job["sku"], job["plan"].get("voice", ""), job["plan"].get("carousel_type", ""),
                     chosen_hook(job["plan"]))
    for s in slides:
        entry = job["images"].get(str(s["n"]), {})
        versions = entry.get("versions") or []
        cur = versions[entry.get("current", 0)] if versions else {}
        if cur.get("library_variant"):
            ledgers.add_library_usage(cur["library_style"], cur["library_slot"], cur["library_variant"], job["sku"])

    # Cleanup: the specific input photo, then the work folder
    warnings = []
    try:
        inp = project.abs(job["input_file"])
        if project.is_inside(inp, project.inputs) and inp.is_file():
            inp.unlink()
            log(f"Deleted input photo {job['input_file']}")
    except Exception as e:  # saved already; report but don't fail
        warnings.append(f"Could not delete input photo: {e}")
    try:
        store.delete(job["sku"])
    except Exception as e:
        warnings.append(f"Could not remove work folder: {e}")
    return {"dest": project.rel(dest), "warnings": warnings}
