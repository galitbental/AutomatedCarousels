"""Carousel Studio workflow: every operation the UI can perform."""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

from . import prompts as P
from .catalog import Catalog, suggestions_from_card
from .facts import COMMON as FACTS_COMMON, read_facts, write_facts
from .finalize import finalize as do_finalize
from .imagegen import add_version, pick_download
from .jobs import (MULTI, STAGES, JobError, JobStore, add_log, approve, as_list, current_image, editable,
                   mark_dirty, now, reopen, require_approved, require_editable)
from .ledgers import Ledgers, parse_hashtags
from .library import COMMON as LIB_COMMON, Library
from .paths import IMAGE_EXTS, Project, list_images
from .render import Renderer, find_browser
from .settings import load_settings, save_settings
from .sku import SkuError, parse_sku
from .spec import CAROUSEL_TYPES, VOICES, lint_plan, with_brand_tags
from .styles import JewelryType, folder_status, load_table
from .tasks import ActivityLog, TaskManager

INTAKE_FIELDS = {"from", "giver_name", "to", "gender", "age_group", "event", "tone", "card_headline",
                 "card_text", "signature", "placeholder_name", "notes"}
SLIDE_FIELDS = {"purpose", "layout", "source", "slot", "prompt", "references", "headline", "subtext", "items",
                "button", "text_pos", "shade", "img_pos", "logo", "eyebrow", "note", "quote", "script",
                "image_source", "image_layout"}
TEXT_ONLY_LAYOUTS = ("statement", "cta")  # layouts that also work as a black slide
TEXT_FIELDS = {"headline", "subtext", "items", "button", "text_pos", "shade", "img_pos", "logo", "eyebrow", "note",
               "quote", "script"}


class NeedsConfirm(JobError):
    """Approval has warnings; the UI must ask the user and resend with force=true."""

    def __init__(self, warnings: list[str]):
        super().__init__("Please confirm: " + " ".join(warnings), 409)
        self.warnings = warnings


class Studio:
    def __init__(self, project: Project, assistant, backend, renderer: Renderer | None = None,
                 opener=None, echo: bool = True):
        self.project = project
        project.ensure()
        self.assistant = assistant
        self.backend = backend
        self.renderer = renderer or Renderer(project)
        self.opener = opener or _open_in_explorer
        self.store = JobStore(project)
        self.ledgers = Ledgers(project)
        self.library = Library(project)
        self.log = ActivityLog(echo=echo)
        self.tasks = TaskManager(self.log)
        self._locks: dict[str, threading.RLock] = defaultdict(threading.RLock)
        self._catalog: Catalog | None = None
        self.library.seed_common()
        self.settings()
        load_table(project)

    # ------------------------------------------------------------ basics
    def settings(self) -> dict:
        return load_settings(self.project)

    def save_settings(self, values: dict) -> dict:
        s = save_settings(self.project, values)
        self.log.add("Settings saved")
        return s

    @property
    def catalog(self) -> Catalog:
        folder = Path(self.settings()["catalog_dir"])
        if self._catalog is None or self._catalog.folder != folder:
            self._catalog = Catalog(folder)
        return self._catalog

    def jtype(self, job_or_info: dict) -> JewelryType:
        info = job_or_info.get("sku_info", job_or_info)
        t = load_table(self.project).by_name(info["jewelry_type"])
        if not t:
            raise JobError(f"Jewelry type '{info['jewelry_type']}' is no longer in data/styles.json")
        return t

    def _lock(self, sku: str) -> threading.RLock:
        return self._locks[sku]

    def _mutate(self, sku: str, fn):
        """Load, modify and save a job under its lock."""
        with self._lock(sku):
            job = self.store.load(sku)
            out = fn(job)
            self.store.save(job)
            return out if out is not None else job

    # ------------------------------------------------------------ queue & system
    def _input_for(self, sku: str) -> Path | None:
        return next((p for p in list_images(self.project.inputs) if p.stem == sku), None)

    def queue(self) -> dict:
        table = load_table(self.project)
        items = []
        for p in list_images(self.project.inputs):
            sku = p.stem
            item = {"sku": sku, "file": self.project.rel(p), "jewelry_type": "", "style_folder": "",
                    "status": "ready", "reason": ""}
            try:
                info = parse_sku(sku, table)
                item["jewelry_type"], item["style_folder"] = info.jewelry_type, info.style_folder
                st, photos = folder_status(self.project, table.by_name(info.jewelry_type))
                if st == "no_folder":
                    item["status"], item["reason"] = "blocked", (
                        f"Style folder RealProductPhotos/{info.style_folder} does not exist. Add product photos.")
                elif st == "empty":
                    item["status"], item["reason"] = "blocked", (
                        f"Style folder RealProductPhotos/{info.style_folder} is empty. Add product photos.")
            except SkuError as e:
                item["status"], item["reason"] = "blocked", str(e)
            if item["status"] == "ready" and self.store.exists(sku):
                item["status"] = "in_progress"
            items.append(item)
        return {"inputs": items, "jobs": self.store.list()}

    def system(self) -> dict:
        s = self.settings()
        claude = shutil.which(s["claude_cmd"])
        version = ""
        if claude:
            try:
                version = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=20,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
            except Exception as e:
                version = f"error: {e}"
        table = load_table(self.project)
        styles = []
        for t in table.types:
            st, photos = folder_status(self.project, t)
            styles.append({"type": t.name, "folder": t.folder, "status": st, "photos": len(photos)})
        dl = Path(s["downloads_dir"])
        return {
            "python": sys.version.split()[0],
            "browser": str(find_browser() or ""),
            "claude": claude or "", "claude_version": version,
            "downloads": {"path": str(dl), "exists": dl.is_dir()},
            "folders": {name: getattr(self.project, name).is_dir() for name in
                        ("inputs", "photos", "common", "library", "carousels", "data", "doc")},
            "styles": styles,
            "image_backend": getattr(self.backend, "name", "?"),
        }

    # ------------------------------------------------------------ jobs
    def start_job(self, sku: str) -> dict:
        inp = self._input_for(sku)
        if not inp:
            raise JobError(f"No input photo for '{sku}' in DataFromUser.", 404)
        if self.store.exists(sku):
            return self.store.load(sku)
        table = load_table(self.project)
        try:
            info = parse_sku(sku, table)
        except SkuError as e:
            raise JobError(str(e)) from e
        st, _ = folder_status(self.project, table.by_name(info.jewelry_type))
        if st != "ready":
            raise JobError(f"Style folder for {info.jewelry_type} is missing or empty.")
        job = self.store.create(sku, self.project.rel(inp), info.to_dict())
        self.log.add(f"Job created ({info.jewelry_type})", sku=sku)
        try:
            job = self.catalog_lookup(sku)
        except Exception as e:  # the catalog is a convenience; never block job creation
            self.log.add(f"Catalog lookup failed: {e}", "warn", sku)
        return job

    # ------------------------------------------------------------ catalog
    def catalog_lookup(self, sku: str, key: str | None = None) -> dict:
        """Find the poem card in the catalog (or use `key`) and fill the intake suggestions."""
        job = self.store.load(sku)
        require_editable(job, "intake")
        t = self.jtype(job)
        cat = self.catalog
        if key:
            entry = cat.card(key)
            if not entry:
                raise JobError(f"Catalog card '{key}' not found.", 404)
            match_info = {**job.get("catalog", {}), "status": "found", "method": "chosen by user", "chosen": entry.key}
        else:
            m = cat.find(job["sku_info"], t, self.project.abs(job["input_file"]))
            entry = m.chosen
            match_info = {"status": m.status, "method": m.method, "chosen": entry.key if entry else "",
                          "candidates": m.candidates, "message": m.message, "dir": str(cat.folder)}
        card = cat.read(entry) if entry else None
        if entry:
            match_info["image"] = entry.image.name if entry.image else ""
            match_info["card"] = card

        def apply(j):
            j["catalog"] = match_info
            if card:
                sug = suggestions_from_card(card, j["sku_info"])
                it = j["intake"]
                for k in ("from", "to", "event", "age_group", "gender", "card_headline", "card_text", "signature",
                          "tone"):
                    it[k] = sug[k]
                it["suggested"] = sug
                it["suggested_events"] = sug["event_options"]
                it["source"] = f"catalog:{entry.key}"
            add_log(j, f"Catalog: {match_info['status']} ({match_info.get('method', '')}) {match_info.get('chosen', '')}")
        job = self._mutate(sku, apply)
        self.log.add(f"Catalog card: {match_info['status']} {match_info.get('chosen', '')} "
                     f"({match_info.get('method') or match_info.get('message', '')})",
                     "info" if match_info["status"] == "found" else "warn", sku)
        return job

    def catalog_image(self, name: str) -> Path:
        cat = self.catalog
        p = (cat.folder / name).resolve()
        if p.parent != cat.folder.resolve() or not p.is_file() or not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise JobError("Not a catalog image.", 404)
        return p

    def job_view(self, sku: str) -> dict:
        job = self.store.load(sku)
        t = self.jtype(job)
        st, photos = folder_status(self.project, t)
        s = self.settings()
        style_facts, common_facts = read_facts(self.project, t.folder), read_facts(self.project, FACTS_COMMON)
        plan = job["plan"]
        hook = plan["hooks"][plan["hook_choice"]] if plan["hooks"] else ""
        posts = self.ledgers.posts()
        it = job["intake"]
        return {
            "job": job,
            "context": {
                "style": {"name": t.name, "folder": t.folder, "status": st, "men": t.men,
                          "photos": [self.project.rel(p) for p in photos]},
                "facts": {"style": style_facts["approved"], "common": common_facts["approved"]},
                "events": list(dict.fromkeys(as_list(it.get("suggested_events")) + P.EVENTS)),
                "relations": list(dict.fromkeys(as_list(it.get("suggested", {}).get("from"))
                                                + as_list(it.get("suggested", {}).get("to")) + P.RELATIONS)),
                "age_groups": P.AGE_GROUPS, "layouts": P.LAYOUTS, "sources": P.SOURCES,
                "voices": {k: v for k, v in VOICES.items()},
                "carousel_types": {k: v[0] for k, v in CAROUSEL_TYPES.items()},
                "last_post": posts[-1] if posts else None,
                "lint": lint_plan(plan) if plan["slides"] else {"errors": [], "warnings": []},
                "tasks": [x for x in self.tasks.running() if x["sku"] == sku],
                "suffix": s["image_style_suffix"], "chatgpt_url": s["chatgpt_url"],
                "backend": getattr(self.backend, "name", "?"),
                "library": {"options": self.library.variants(t.folder, "options"),
                            "quality": self.library.variants(t.folder, "quality"),
                            "cta": self.library.variants(LIB_COMMON, "cta")},
                "common_photos": [self.project.rel(p) for p in list_images(self.project.common)],
                "references": P.available_references(self.project, t),
                "hashtag_check": self.ledgers.check_hashtags(plan["hashtags"], s["overlap_threshold"]),
                "hook_used": self.ledgers.hook_used(hook) if hook else None,
                "baseline": P.baseline_slides(self.project, job, t) if not plan["slides"] else None,
            },
        }

    def patch_job(self, sku: str, patch: dict) -> dict:
        def fn(job):
            if "intake" in patch:
                require_editable(job, "intake")
                for k, v in patch["intake"].items():
                    if k in INTAKE_FIELDS:
                        job["intake"][k] = as_list(v) if k in MULTI else v
            if "plan" in patch:
                require_editable(job, "plan")
                self._patch_plan(job, patch["plan"])
            if "slide_text" in patch:
                require_editable(job, "slides")
                for n, fields in patch["slide_text"].items():
                    slide = self._slide(job, int(n))
                    for k, v in fields.items():
                        if k in TEXT_FIELDS:
                            slide[k] = v
                    mark_dirty(job, int(n))
            if "final_text" in patch:
                require_editable(job, "final")
                ft = patch["final_text"]
                if "caption" in ft:
                    job["plan"]["caption"] = ft["caption"]
                if "hashtags" in ft:
                    job["plan"]["hashtags"] = with_brand_tags(parse_hashtags(ft["hashtags"]))
            if "images_current" in patch:
                require_editable(job, "images")
                for n, idx in patch["images_current"].items():
                    entry = job["images"].get(str(n))
                    if entry and 0 <= int(idx) < len(entry["versions"]):
                        entry["current"] = int(idx)
                        mark_dirty(job, int(n))
            return job

        return self._mutate(sku, fn)

    def _patch_plan(self, job: dict, p: dict) -> None:
        plan = job["plan"]
        if "hooks" in p:
            plan["hooks"] = [str(h) for h in p["hooks"]][:3]
        if "hook_choice" in p:
            plan["hook_choice"] = max(0, min(int(p["hook_choice"]), len(plan["hooks"]) - 1))
        if "caption" in p:
            plan["caption"] = p["caption"]
        if "hashtags" in p:
            plan["hashtags"] = with_brand_tags(parse_hashtags(p["hashtags"]))
        for k, allowed in (("voice", VOICES), ("carousel_type", CAROUSEL_TYPES)):
            if k in p:
                plan[k] = p[k] if p[k] in allowed else ""
        if "slides" in p:
            old_images = job["images"]
            new_slides, new_images = [], {}
            for i, s in enumerate(p["slides"][:10], start=1):
                slide = {k: v for k, v in s.items() if k in SLIDE_FIELDS}
                slide.setdefault("text_pos", "top")
                if slide.get("layout") == "statement":
                    slide["source"] = "none"
                slide.setdefault("shade", 0.55)
                slide["n"] = i
                orig = s.get("n")
                if orig is not None and str(orig) in old_images:
                    new_images[str(i)] = old_images[str(orig)]
                new_slides.append(slide)
            plan["slides"] = new_slides
            job["images"] = new_images
        mark_dirty(job)

    @staticmethod
    def _slide(job: dict, n: int) -> dict:
        slide = next((s for s in job["plan"]["slides"] if s["n"] == n), None)
        if not slide:
            raise JobError(f"No slide {n}", 404)
        return slide

    @staticmethod
    def _require_slide_editable(job: dict) -> None:
        """Image source and references can change while the plan or the images stage is open."""
        if not (editable(job, "plan") or editable(job, "images")):
            raise JobError("Reopen the Plan or Images stage to change this slide.", 409)

    def set_slide_kind(self, sku: str, n: int, black: bool) -> dict:
        """Toggle a slide between a black text slide and a slide with an image.

        The image settings are remembered, so switching back restores the previous layout and source."""
        t = None

        def fn(job):
            nonlocal t
            self._require_slide_editable(job)
            t = t or self.jtype(job)
            s = self._slide(job, n)
            if black:
                if s["source"] == "none":
                    return job
                s["image_source"], s["image_layout"] = s["source"], s["layout"]
                s["source"] = "none"
                if s["layout"] not in TEXT_ONLY_LAYOUTS:
                    s["layout"] = "statement"
                add_log(job, f"Slide {n}: black slide")
            else:
                if s["source"] != "none":
                    return job
                s["source"] = s.pop("image_source", None) or "generate"
                layout = s.pop("image_layout", None) or s["layout"]
                s["layout"] = "overlay-bottom" if layout == "statement" else layout
                if s["layout"] in ("overlay-bottom", "hook"):
                    s["text_pos"] = "bottom"
                if not s.get("prompt"):
                    s["prompt"] = P.default_image_prompt(t, s)
                if not s.get("references"):
                    s["references"] = [job["input_file"]]
                add_log(job, f"Slide {n}: slide with image ({s['source']})")
            mark_dirty(job, n)
            return job

        self._mutate(sku, fn)
        return self.store.load(sku)

    def set_slide_references(self, sku: str, n: int, refs: list[str]) -> dict:
        def fn(job):
            self._require_slide_editable(job)
            clean = []
            for r in refs:
                p = self.project.abs(r)  # raises for paths outside the project
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS and self.project.rel(p) not in clean:
                    clean.append(self.project.rel(p))
            self._slide(job, n)["references"] = clean
            return job

        return self._mutate(sku, fn)

    def reference_options(self, sku: str) -> dict:
        """Every image that can be uploaded to ChatGPT as a reference, scanned fresh on each call
        so photos added to the folders while the app runs show up after Refresh."""
        job = self.store.load(sku)
        t = self.jtype(job)
        rel = self.project.rel
        style_dir = self.project.photos / t.folder
        groups = [{"key": "input", "title": "Input photo", "folder": rel(self.project.inputs),
                   "files": [job["input_file"]] if self.project.abs(job["input_file"]).is_file() else []},
                  {"key": "style", "title": f"{t.name} photos", "folder": rel(style_dir),
                   "files": [rel(p) for p in _images_deep(style_dir)]},
                  {"key": "common", "title": "Common (box, logo)", "folder": rel(self.project.common),
                   "files": [rel(p) for p in _images_deep(self.project.common)]},
                  {"key": "library", "title": "Style library", "folder": rel(self.project.library),
                   "files": [v["file"] for slot in ("options", "quality") for v in self.library.variants(t.folder, slot)]
                   + [v["file"] for v in self.library.variants(LIB_COMMON, "cta")]}]
        others = []
        if self.project.photos.is_dir():
            for d in sorted(p for p in self.project.photos.iterdir() if p.is_dir()):
                if d.resolve() not in (style_dir.resolve(), self.project.common.resolve()):
                    others += [rel(p) for p in _images_deep(d)]
        groups.append({"key": "other", "title": "Other styles", "folder": rel(self.project.photos), "files": others})
        return {"groups": groups}

    def discard(self, sku: str) -> None:
        with self._lock(sku):
            self.store.delete(sku)
        self.log.add("Job discarded (input photo kept)", "warn", sku)

    # ------------------------------------------------------------ approvals
    def approve(self, sku: str, stage: str, force: bool = False) -> dict:
        if stage not in STAGES[:-1]:
            raise JobError(f"Stage '{stage}' cannot be approved here.")

        def fn(job):
            if job["stages"][stage] in ("locked",):
                raise JobError(f"Stage '{stage}' is locked.", 409)
            for prev in STAGES[:STAGES.index(stage)]:
                if job["stages"][prev] != "approved":
                    raise JobError(f"Approve '{prev}' first.", 409)
            warnings = getattr(self, f"_validate_{stage}")(job)
            if warnings and not force:
                raise NeedsConfirm(warnings)
            approve(job, stage)
            add_log(job, f"Approved {stage}")
            if stage == "intake":
                t = self.jtype(job)
                if (read_facts(self.project, t.folder)["approved"]
                        and read_facts(self.project, FACTS_COMMON)["approved"]
                        and job["stages"]["facts"] == "open"):
                    approve(job, "facts")
                    add_log(job, "Facts already approved")
            if stage == "plan":
                self._autofill(job)
            return job

        job = self._mutate(sku, fn)
        self.log.add(f"Approved stage: {stage}", sku=sku)
        if stage == "intake" and job["stages"]["facts"] != "approved":
            folder = self.jtype(job).folder
            if not read_facts(self.project, folder)["text"].strip():  # suggest facts from the photos right away
                try:
                    self.task_draft_facts(folder, sku)
                except JobError as e:
                    self.log.add(f"Could not draft facts automatically: {e}", "warn", sku)
        return job

    def reopen(self, sku: str, stage: str) -> dict:
        def fn(job):
            reopen(job, stage)
            add_log(job, f"Reopened {stage}")
        job = self._mutate(sku, fn)
        self.log.add(f"Reopened stage: {stage}", sku=sku)
        return job

    def _validate_intake(self, job) -> list[str]:
        it = job["intake"]
        missing = [k for k in ("from", "to", "event") if not as_list(it.get(k))]
        if missing:
            raise JobError(f"Choose at least one value for: {', '.join(missing)}.")
        return []

    def _validate_facts(self, job) -> list[str]:
        t = self.jtype(job)
        for style in (t.folder, FACTS_COMMON):
            f = read_facts(self.project, style)
            if not f["text"].strip():
                raise JobError(f"Facts for {style} are empty. Draft or write them first.")
            if not f["approved"]:
                write_facts(self.project, style, f["text"], True)
        return []

    def _validate_plan(self, job) -> list[str]:
        plan = job["plan"]
        hook = plan["hooks"][plan["hook_choice"]] if plan["hooks"] else ""
        if not hook.strip():
            raise JobError("Choose or write a hook.")
        for s in plan["slides"]:
            if s.get("source") not in P.SOURCES:
                raise JobError(f"Slide {s['n']} has no image source.")
            if s["source"] == "generate" and not s.get("prompt", "").strip():
                raise JobError(f"Slide {s['n']} needs an image prompt.")
        lint = lint_plan(plan)
        if lint["errors"]:
            raise JobError(" ".join(lint["errors"]))
        chk = self.ledgers.check_hashtags(plan["hashtags"], self.settings()["overlap_threshold"])
        if chk["errors"]:
            raise JobError(" ".join(chk["errors"]))
        warnings = list(chk["warnings"]) + lint["warnings"]
        posts = self.ledgers.posts()
        if plan.get("voice") and posts and posts[-1].get("voice") == plan["voice"]:
            warnings.append(f"The previous carousel ({posts[-1]['sku']}) also used the {plan['voice']} voice.")
        used = self.ledgers.hook_used(hook)
        if used:
            warnings.append(f"This hook was already used for {used['sku']} ({used['date']}).")
        return warnings

    def _validate_images(self, job) -> list[str]:
        missing = [s["n"] for s in job["plan"]["slides"] if s["source"] != "none" and not current_image(job, s["n"])]
        if missing:
            raise JobError(f"Slides without image: {', '.join(map(str, missing))}.")
        bad = [s["n"] for s in job["plan"]["slides"]
               if (current_image(job, s["n"]) or {}).get("qa") and not current_image(job, s["n"])["qa"].get("ok")]
        return [f"QA reported issues on slide(s) {', '.join(map(str, bad))}."] if bad else []

    def _validate_slides(self, job) -> list[str]:
        r = job["render"]
        files = r.get("files", {})
        for s in job["plan"]["slides"]:
            f = files.get(str(s["n"]))
            if not f or not self.project.abs(f).is_file():
                raise JobError(f"Slide {s['n']} is not rendered. Click 'Render all'.")
        dirty = sorted(int(n) for n in r.get("dirty", {}))
        if dirty:
            raise JobError(f"Slide(s) {', '.join(map(str, dirty))} changed after the last render. Render again.")
        return []

    def _autofill(self, job: dict) -> None:
        """Pre-fill library/common/input slides that have no image yet."""
        t = self.jtype(job)
        usage = self.ledgers.library_usage()
        for s in job["plan"]["slides"]:
            if current_image(job, s["n"]):
                continue
            if s["source"] == "library" and s.get("slot"):
                v = self.library.lru_pick(t.folder, s["slot"], usage)
                if v:
                    self._use_library_variant(job, s["n"], t.folder, s["slot"], v["variant"])
            elif s["source"] == "common":
                v = self.library.lru_pick(LIB_COMMON, "cta", usage)
                if v:
                    self._use_library_variant(job, s["n"], LIB_COMMON, "cta", v["variant"])
            elif s["source"] == "input":
                add_version(self.project, job, s["n"], self.project.abs(job["input_file"]), "input")

    # ------------------------------------------------------------ intake
    def task_read_card(self, sku: str):
        job = self.store.load(sku)
        require_editable(job, "intake")

        def run(task):
            res = self.assistant.read_card(job, cancel=task.cancel, log=task.log)

            def apply(j):
                it = j["intake"]
                it["suggested"] = res
                it["suggested_events"] = res.get("suggested_events", [])
                for k in ("card_headline", "card_text", "signature", "placeholder_name", "giver_name"):
                    if res.get(k) and not it.get(k):
                        it[k] = res[k]
                for k in ("from", "to", "age_group"):  # fill only what the catalog/user left empty
                    if as_list(res.get(k)) and not as_list(it.get(k)):
                        it[k] = as_list(res[k])
                if not as_list(it.get("event")):
                    it["event"] = as_list(res.get("event_stated")) or as_list(res.get("suggested_events"))[:1]
                if res.get("gender") and not it.get("source"):
                    it["gender"] = res["gender"]
                if res.get("tone") == "gentle" or j["sku_info"].get("loss_hint"):
                    it["tone"] = "gentle"
                add_log(j, "Card read by Claude")
            self._mutate(sku, apply)
            return res

        return self.tasks.start("read_card", sku, "Read poem card with Claude", run)

    # ------------------------------------------------------------ facts
    def get_facts(self, style: str) -> dict:
        self._check_style(style)
        return {"style": style, **read_facts(self.project, style)}

    def put_facts(self, style: str, text: str, approved: bool) -> dict:
        self._check_style(style)
        out = write_facts(self.project, style, text, approved)
        self.log.add(f"Facts saved for {style}" + (" (approved)" if approved else ""))
        return {"style": style, **out}

    def _check_style(self, style: str) -> None:
        if style != FACTS_COMMON and not load_table(self.project).by_folder(style):
            raise JobError(f"Unknown style '{style}'", 404)

    def task_draft_facts(self, style: str, sku: str = ""):
        self._check_style(style)
        if style == FACTS_COMMON:
            files = [self.project.rel(p) for p in list_images(self.project.common)]
            for t in load_table(self.project).types:
                files += [self.project.rel(p) for p in list_images(self.project.photos / t.folder)
                          if "quality" in p.stem.lower()][:1]
            jtype = JewelryType(name="All Be Wished jewelry (shared facts)", folder=FACTS_COMMON)
        else:
            jtype = load_table(self.project).by_folder(style)
            files = [self.project.rel(p) for p in list_images(self.project.photos / style)]
        if not files:
            raise JobError(f"No photos to read for {style}.")

        def run(task):
            md = self.assistant.draft_facts(jtype, files, cancel=task.cancel, log=task.log)
            write_facts(self.project, style, md, False)
            return {"style": style, "text": md}

        return self.tasks.start(f"facts:{style}", sku or style, f"Draft facts for {style}", run)

    # ------------------------------------------------------------ plan
    def task_plan(self, sku: str, part: str = "all", voice: str = "", carousel_type: str = ""):
        voice = voice if voice in VOICES else ""
        carousel_type = carousel_type if carousel_type in CAROUSEL_TYPES else ""
        job = self.store.load(sku)
        require_approved(job, "intake", "facts")
        require_editable(job, "plan")
        if part not in ("all", "hooks", "caption", "hashtags"):
            raise JobError(f"Unknown plan part '{part}'")
        t = self.jtype(job)

        def run(task):
            baseline = P.baseline_slides(self.project, job, t)
            target = random.Random().choice(range(6, 31))  # varies per carousel; includes the 3 brand tags
            prompt = P.plan_prompt(
                job, t, read_facts(self.project, t.folder)["text"], read_facts(self.project, FACTS_COMMON)["text"],
                job["plan"]["slides"] if (part != "all" and job["plan"]["slides"]) else baseline,
                [h["hook"] for h in self.ledgers.hooks()],
                [e["tags"] for e in self.ledgers.hashtag_sets()], target,
                P.available_references(self.project, t),
                voice or job["plan"].get("voice", "") if part != "all" else voice,
                carousel_type or job["plan"].get("carousel_type", "") if part != "all" else carousel_type,
                self.ledgers.posts())
            raw = self.assistant.make_plan(prompt, cancel=task.cancel, log=task.log)
            new = P.sanitize_plan(raw, self.project, baseline, target)

            def apply(j):
                require_editable(j, "plan")
                plan = j["plan"]
                if part == "all":
                    j["plan"] = new
                    j["images"] = {}
                elif part == "hooks":
                    plan["hooks"], plan["hook_choice"] = new["hooks"], 0
                    if plan["slides"]:
                        plan["slides"][0]["headline"] = new["hooks"][0]
                elif part == "caption":
                    plan["caption"] = new["caption"]
                else:
                    plan["hashtags"], plan["hashtag_target"] = new["hashtags"], target
                mark_dirty(j)
                add_log(j, f"Plan generated ({part})")
            self._mutate(sku, apply)
            return {"part": part, "hashtag_target": target}

        return self.tasks.start("plan", sku, f"Generate plan ({part}) with Claude", run)

    def baseline_plan(self, sku: str) -> dict:
        """Fill the plan with the baseline slides (no Claude), e.g. to write copy by hand."""
        def fn(job):
            require_approved(job, "intake", "facts")
            require_editable(job, "plan")
            slides = P.baseline_slides(self.project, job, self.jtype(job))
            job["plan"].update({"slides": slides, "hooks": [slides[0]["headline"], "", ""], "hook_choice": 0})
            job["images"] = {}
            mark_dirty(job)
        return self._mutate(sku, fn)

    # ------------------------------------------------------------ images
    def task_generate_image(self, sku: str, n: int):
        job = self.store.load(sku)
        require_editable(job, "images")
        self._slide(job, n)

        def run(task):
            return self._generate_one(sku, n, task)

        return self.tasks.start(f"gen:{n}", sku, f"Generate image for slide {n}", run)

    def _generate_one(self, sku: str, n: int, task) -> dict:
        s = self.settings()
        retries = int(s["max_auto_retries"])
        fix = ""
        for attempt in range(retries + 1):
            job = self.store.load(sku)
            slide = dict(self._slide(job, n))
            if fix:
                slide["prompt"] = slide["prompt"].rstrip() + " " + fix
            path, chat_url = self.backend.generate(job, slide, cancel=task.cancel, log=task.log)
            full_prompt = P.image_prompt(slide["prompt"], s["image_style_suffix"])

            def store_it(j):
                j["chat_url"] = chat_url or j.get("chat_url", "")
                v = add_version(self.project, j, n, Path(path), self.backend.name, full_prompt, move=True)
                mark_dirty(j, n)
                add_log(j, f"Slide {n}: new image {v['file']}")
                return v
            version = self._mutate(sku, store_it)
            task.log(f"Slide {n}: image saved ({version['file']})")
            if not s["qa_enabled"] or task.cancel.is_set():
                return version
            qa = self._qa(sku, n, task)
            if qa.get("ok") or attempt == retries:
                return version
            fix = qa.get("prompt_fix", "")
            task.log(f"Slide {n}: QA found issues, retrying ({attempt + 1}/{retries}): {'; '.join(qa['issues'])}")
        return version

    def _qa(self, sku: str, n: int, task) -> dict:
        job = self.store.load(sku)
        img = current_image(job, n)
        if not img:
            raise JobError(f"Slide {n} has no image to check.")
        task.log(f"Slide {n}: QA with Claude…")
        qa = self.assistant.qa_image(img["file"], job["input_file"], job["intake"].get("card_text", ""),
                                     self._slide(job, n), cancel=task.cancel, log=task.log)

        def apply(j):
            cur = current_image(j, n)
            if cur and cur["file"] == img["file"]:
                cur["qa"] = qa
        self._mutate(sku, apply)
        task.log(f"Slide {n}: QA {'OK' if qa.get('ok') else 'issues: ' + '; '.join(qa.get('issues', []))}")
        return qa

    def task_qa(self, sku: str, n: int):
        self.store.load(sku)
        return self.tasks.start(f"qa:{n}", sku, f"QA slide {n}", lambda task: self._qa(sku, n, task))

    def task_generate_missing(self, sku: str):
        job = self.store.load(sku)
        require_editable(job, "images")

        def run(task):
            done = []
            for s in self.store.load(sku)["plan"]["slides"]:
                if task.cancel.is_set():
                    break
                if s["source"] in ("generate", "library") and not current_image(self.store.load(sku), s["n"]):
                    self._generate_one(sku, s["n"], task)
                    done.append(s["n"])
            return {"generated": done}

        return self.tasks.start("gen:all", sku, "Generate all missing images", run)

    def import_download(self, sku: str, n: int) -> dict:
        dl = Path(self.settings()["downloads_dir"])
        path = pick_download(dl, time.time() - 3 * 3600, timeout=0, stable_secs=0.5)
        if not path:
            raise JobError(f"No image from the last 3 hours in {dl}.")

        def fn(job):
            require_editable(job, "images")
            slide = self._slide(job, n)
            v = add_version(self.project, job, n, path, "download",
                            P.image_prompt(slide["prompt"], self.settings()["image_style_suffix"]), move=True)
            mark_dirty(job, n)
            add_log(job, f"Slide {n}: imported {path.name}")
            return v
        v = self._mutate(sku, fn)
        self.log.add(f"Slide {n}: imported {path.name} from Downloads", sku=sku)
        return v

    def upload_image(self, sku: str, n: int, filename: str, data: bytes) -> dict:
        ext = Path(filename).suffix.lower()
        if ext not in IMAGE_EXTS:
            raise JobError("Upload a .jpg, .png or .webp image.")
        tmp = self.project.work / sku / f"_upload{ext}"

        def fn(job):
            require_editable(job, "images")
            self._slide(job, n)
            tmp.write_bytes(data)
            v = add_version(self.project, job, n, tmp, "upload", move=True)
            mark_dirty(job, n)
            add_log(job, f"Slide {n}: uploaded {filename}")
            return v
        v = self._mutate(sku, fn)
        self.log.add(f"Slide {n}: uploaded {filename}", sku=sku)
        return v

    def _use_library_variant(self, job: dict, n: int, style: str, slot: str, variant: str) -> dict:
        src = self.project.library / style / slot / variant
        if not src.is_file():
            raise JobError(f"Library image {style}/{slot}/{variant} not found.", 404)
        return add_version(self.project, job, n, src, "library", extra={
            "library_style": style, "library_slot": slot, "library_variant": variant})

    def use_source(self, sku: str, n: int, kind: str, ref: dict) -> dict:
        def fn(job):
            require_editable(job, "images")
            self._slide(job, n)
            if kind == "library":
                v = self._use_library_variant(job, n, ref["style"], ref["slot"], ref["variant"])
            elif kind == "common":
                src = self.project.abs(ref["file"])
                if not (self.project.is_inside(src, self.project.photos)
                        or self.project.is_inside(src, self.project.library)) or not src.is_file():
                    raise JobError("Choose an image from RealProductPhotos or StyleLibrary.")
                v = add_version(self.project, job, n, src, "common")
            elif kind == "input":
                v = add_version(self.project, job, n, self.project.abs(job["input_file"]), "input")
            else:
                raise JobError(f"Unknown source '{kind}'")
            mark_dirty(job, n)
            add_log(job, f"Slide {n}: using {kind} image")
            return v
        return self._mutate(sku, fn)

    def save_to_library(self, sku: str, n: int, slot: str) -> dict:
        def fn(job):
            img = current_image(job, n)
            if not img:
                raise JobError(f"Slide {n} has no image.")
            t = self.jtype(job)
            style = LIB_COMMON if slot == "cta" else t.folder
            v = self.library.add_variant(style, slot, self.project.abs(img["file"]), approved=True,
                                         prompt=img.get("prompt", ""), sku=sku)
            img.update({"library_style": style, "library_slot": slot, "library_variant": v["variant"]})
            add_log(job, f"Slide {n}: saved to library {style}/{slot}/{v['variant']}")
            return v
        v = self._mutate(sku, fn)
        self.log.add(f"Saved slide {n} image to library ({v['style']}/{slot})", sku=sku)
        return v

    # ------------------------------------------------------------ render & final
    def task_render(self, sku: str, only: list[int] | None = None):
        job = self.store.load(sku)
        require_approved(job, "images")
        require_editable(job, "slides")

        def run(task):
            snapshot = self.store.load(sku)
            started = time.time()
            files = self.renderer.render_job(snapshot, only, log=task.log)

            def apply(j):
                j["render"]["files"] = {**(j["render"].get("files", {}) if only else {}), **files}
                j["render"]["rendered_at"] = now()
                dirty = j["render"].setdefault("dirty", {})
                for n in files:  # keep slides edited while rendering marked dirty
                    if dirty.get(n, 0) <= started:
                        dirty.pop(n, None)
                add_log(j, "Rendered " + ("all slides" if only is None else f"slide(s) {only}"))
            self._mutate(sku, apply)
            return {"files": files}

        return self.tasks.start("render", sku, "Render slides", run)

    def finalize(self, sku: str) -> dict:
        with self._lock(sku):
            job = self.store.load(sku)
            res = do_finalize(self.project, self.store, self.ledgers, job, self.settings()["overlap_threshold"],
                              log=lambda m: self.log.add(m, sku=sku))
        for w in res["warnings"]:
            self.log.add(w, "warn", sku)
        self._locks.pop(sku, None)
        return res

    def preview_html(self, sku: str, n: int) -> str:
        """Live slide preview for the UI: the real slide template with http URLs instead of file paths."""
        from urllib.parse import quote
        job = self.store.load(sku)
        slide = self._slide(job, n)
        img = current_image(job, n)
        if slide.get("source") == "none":
            image = None
        elif img:
            image = f"/file?path={quote(img['file'])}&v={quote(img.get('created', ''))}"
        else:
            image = "/web/placeholder.svg"
        logo = self.project.common / "GOlden Logo2.jpg"
        logo_url = f"/file?path={quote(self.project.rel(logo))}" if slide.get("logo") and logo.exists() else None
        last = job["plan"]["slides"][-1]["n"] if job["plan"]["slides"] else n
        return self.renderer.html(slide, image, logo_url, is_last=n == last, fonts="/fonts")

    # ------------------------------------------------------------ library & files
    def library_overview(self) -> dict:
        usage = self.ledgers.library_usage()
        counts: dict[str, int] = defaultdict(int)
        for u in usage:
            counts[f"{u['style']}/{u['slot']}/{u['variant']}"] += 1
        data = self.library.overview()
        for style in data:
            for slot, variants in style["slots"].items():
                for v in variants:
                    v["uses"] = counts.get(f"{style['style']}/{slot}/{v['variant']}", 0)
        return {"styles": data}

    def library_set(self, style: str, slot: str, variant: str, approved: bool | None, remove: bool) -> None:
        if remove:
            self.library.remove(style, slot, variant)
            self.log.add(f"Library: removed {style}/{slot}/{variant}", "warn")
        elif approved is not None:
            self.library.set_approved(style, slot, variant, approved)
            self.log.add(f"Library: {'approved' if approved else 'unapproved'} {style}/{slot}/{variant}")

    def open_path(self, rel: str) -> None:
        p = self.project.abs(rel)
        if not p.exists():
            raise JobError(f"Not found: {rel}", 404)
        self.opener(p)


def _images_deep(folder: Path) -> list[Path]:
    """Images in folder and its subfolders (photos may be organized in subfolders), sorted by path."""
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                  key=lambda p: str(p).lower())


def _open_in_explorer(p: Path) -> None:
    if os.name == "nt":
        if p.is_dir():
            os.startfile(str(p))  # noqa: S606 (local desktop app)
        else:
            subprocess.Popen(["explorer", "/select,", str(p)])
    else:  # pragma: no cover
        subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
