"""HTTP API + static UI."""
from __future__ import annotations

import io
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

from .jobs import JobError
from .paths import Project
from .service import NeedsConfirm, Studio
from .version import code_version

WEB = Path(__file__).parent / "web"
FONTS = Path(__file__).parent / "templates" / "fonts"


def build_studio(project: Project, fake: bool = False, echo: bool = True) -> Studio:
    if fake:
        from .fakes import FakeAssistant, FakeImageBackend
        return Studio(project, FakeAssistant(), FakeImageBackend(), echo=echo)
    from .imagegen import ChatGPTChromeBackend
    from .llm import Assistant, ClaudeRunner
    from .settings import load_settings
    settings = lambda: load_settings(project)  # noqa: E731
    assistant = Assistant(ClaudeRunner(project.root, settings))
    return Studio(project, assistant, ChatGPTChromeBackend(project, assistant, settings), echo=echo)


def create_app(studio: Studio) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
    st = studio
    version = code_version()
    thumbs: dict[tuple, bytes] = {}

    @app.errorhandler(JobError)
    def job_error(e: JobError):
        body = {"error": str(e)}
        if isinstance(e, NeedsConfirm):
            body["warnings"] = e.warnings
            body["needs_confirm"] = True
        return jsonify(body), e.status

    @app.errorhandler(ValueError)
    def value_error(e):
        return jsonify({"error": str(e)}), 400

    def body() -> dict:
        return request.get_json(silent=True) or {}

    def task_json(t):
        return jsonify(t.to_dict())

    # ---------------------------------------------------------------- UI & files
    @app.get("/")
    def index():
        resp = send_from_directory(WEB, "index.html", max_age=0)
        resp.headers["Cache-Control"] = "no-cache"  # always revalidate, so an updated UI is never stale
        return resp

    @app.get("/web/<path:name>")
    def web(name):
        resp = send_from_directory(WEB, name, max_age=0)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.get("/fonts/<path:name>")
    def fonts(name):
        return send_from_directory(FONTS, name, max_age=86400)

    @app.get("/api/jobs/<sku>/preview/<int:n>")
    def preview(sku, n):
        resp = app.response_class(st.preview_html(sku, n), mimetype="text/html")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/file")
    def file():
        p = st.project.abs(request.args.get("path", ""))
        if not p.is_file():
            return jsonify({"error": "not found"}), 404
        resp = send_file(p, max_age=0)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/thumb")
    def thumb():
        """Small JPEG of a project image (reference picker); cached by path + modification time."""
        p = st.project.abs(request.args.get("path", ""))
        if not p.is_file():
            return jsonify({"error": "not found"}), 404
        key = (str(p), p.stat().st_mtime)
        if key not in thumbs:
            from PIL import Image
            with Image.open(p) as im:
                im.thumbnail((320, 320))
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=82)
            if len(thumbs) > 500:
                thumbs.clear()
            thumbs[key] = buf.getvalue()
        return app.response_class(thumbs[key], mimetype="image/jpeg", headers={"Cache-Control": "no-cache"})

    @app.post("/api/open")
    def open_path():
        st.open_path(body()["path"])
        return jsonify({"ok": True})

    @app.get("/api/ping")
    def ping():
        return jsonify({"app": "carousel-studio", "pid": os.getpid(), "version": version,
                        "busy": len(st.tasks.running())})

    @app.post("/api/shutdown")
    def shutdown():
        """Used by a newer launch to replace this server. Refused while tasks are running."""
        if st.tasks.running() and not body().get("force"):
            return jsonify({"error": "tasks are running"}), 409
        stop = getattr(app, "stop_server", None) or (lambda: os._exit(0))
        threading.Thread(target=lambda: (time.sleep(0.3), stop()), daemon=True).start()
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- queue, system, settings, log
    @app.get("/api/queue")
    def queue():
        return jsonify(st.queue())

    @app.get("/api/system")
    def system():
        return jsonify(st.system())

    @app.get("/api/settings")
    def get_settings():
        return jsonify(st.settings())

    @app.put("/api/settings")
    def put_settings():
        return jsonify(st.save_settings(body()))

    @app.get("/api/log")
    def log():
        return jsonify({"items": st.log.since(int(request.args.get("after", 0))), "tasks": st.tasks.running()})

    @app.get("/api/tasks/<tid>")
    def task(tid):
        t = st.tasks.get(tid)
        return (task_json(t) if t else (jsonify({"error": "no such task"}), 404))

    @app.post("/api/tasks/<tid>/cancel")
    def cancel(tid):
        t = st.tasks.get(tid)
        if not t:
            return jsonify({"error": "no such task"}), 404
        t.cancel.set()
        st.log.add(f"Cancel requested: {t.label}", "warn", t.sku)
        return task_json(t)

    # ---------------------------------------------------------------- jobs
    @app.post("/api/jobs")
    def start_job():
        st.start_job(body()["sku"])
        return jsonify(st.job_view(body()["sku"]))

    @app.get("/api/jobs/<sku>")
    def get_job(sku):
        return jsonify(st.job_view(sku))

    @app.patch("/api/jobs/<sku>")
    def patch_job(sku):
        st.patch_job(sku, body())
        return jsonify(st.job_view(sku))

    @app.delete("/api/jobs/<sku>")
    def discard(sku):
        st.discard(sku)
        return jsonify({"ok": True})

    @app.post("/api/jobs/<sku>/approve/<stage>")
    def approve(sku, stage):
        st.approve(sku, stage, force=bool(body().get("force")))
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/reopen/<stage>")
    def reopen(sku, stage):
        st.reopen(sku, stage)
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/intake/read")
    def read_card(sku):
        return task_json(st.task_read_card(sku))

    @app.post("/api/jobs/<sku>/intake/catalog")
    def catalog_lookup(sku):
        st.catalog_lookup(sku, body().get("key") or None)
        return jsonify(st.job_view(sku))

    @app.get("/api/catalog/image")
    def catalog_image():
        resp = send_file(st.catalog_image(request.args.get("name", "")), max_age=3600)
        return resp

    @app.post("/api/jobs/<sku>/plan/generate")
    def plan_generate(sku):
        b = body()
        return task_json(st.task_plan(sku, b.get("part", "all"), b.get("voice", ""), b.get("carousel_type", "")))

    @app.post("/api/jobs/<sku>/plan/baseline")
    def plan_baseline(sku):
        st.baseline_plan(sku)
        return jsonify(st.job_view(sku))

    @app.get("/api/jobs/<sku>/references")
    def reference_options(sku):
        return jsonify(st.reference_options(sku))

    @app.put("/api/jobs/<sku>/slides/<int:n>/references")
    def set_references(sku, n):
        st.set_slide_references(sku, n, [str(r) for r in body().get("references", [])])
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/slides/<int:n>/kind")
    def set_kind(sku, n):
        st.set_slide_kind(sku, n, bool(body().get("black")))
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/images/generate-missing")
    def gen_missing(sku):
        return task_json(st.task_generate_missing(sku))

    @app.post("/api/jobs/<sku>/images/<int:n>/generate")
    def gen_one(sku, n):
        return task_json(st.task_generate_image(sku, n))

    @app.post("/api/jobs/<sku>/images/<int:n>/qa")
    def qa(sku, n):
        return task_json(st.task_qa(sku, n))

    @app.post("/api/jobs/<sku>/images/<int:n>/import")
    def import_dl(sku, n):
        st.import_download(sku, n)
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/images/<int:n>/upload")
    def upload(sku, n):
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "no file"}), 400
        st.upload_image(sku, n, f.filename, f.read())
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/images/<int:n>/use")
    def use(sku, n):
        b = body()
        st.use_source(sku, n, b.get("kind", ""), b)
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/images/<int:n>/library")
    def to_library(sku, n):
        st.save_to_library(sku, n, body().get("slot", "options"))
        return jsonify(st.job_view(sku))

    @app.post("/api/jobs/<sku>/render")
    def render(sku):
        only = body().get("only")
        return task_json(st.task_render(sku, [int(x) for x in only] if only else None))

    @app.post("/api/jobs/<sku>/finalize")
    def finalize(sku):
        return jsonify(st.finalize(sku))

    # ---------------------------------------------------------------- facts & library
    @app.get("/api/facts/<style>")
    def get_facts(style):
        return jsonify(st.get_facts(style))

    @app.put("/api/facts/<style>")
    def put_facts(style):
        b = body()
        return jsonify(st.put_facts(style, b.get("text", ""), bool(b.get("approved"))))

    @app.post("/api/facts/<style>/draft")
    def draft_facts(style):
        return task_json(st.task_draft_facts(style, body().get("sku", "")))

    @app.get("/api/library")
    def library():
        return jsonify(st.library_overview())

    @app.post("/api/library")
    def library_set():
        b = body()
        st.library_set(b["style"], b["slot"], b["variant"], b.get("approved"), bool(b.get("remove")))
        return jsonify(st.library_overview())

    return app
