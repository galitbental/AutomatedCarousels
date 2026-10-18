"""HTML/CSS slide templates rendered to 1080x1350 PNG with headless Chrome."""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .jobs import JobError, current_image, now
from .paths import Project

WIDTH, HEIGHT = 1080, 1350
TEMPLATES = Path(__file__).parent / "templates"
FONTS = TEMPLATES / "fonts"
SCRIPT_POS = ("top-right", "top-left", "bottom-right")
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def markup(text: str) -> Markup:
    """Escape text; *word* -> gold accent span; newline -> <br>."""
    t = html.escape(text or "")
    t = re.sub(r"\*(.+?)\*", r'<span class="accent">\1</span>', t)
    return Markup(t.replace("\n", "<br>"))


def find_browser() -> Path | None:
    return next((p for p in CHROME_PATHS if p.exists()), None)


class Renderer:
    def __init__(self, project: Project):
        self.project = project
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)

    def html(self, slide: dict, image: Path | str | None, logo: Path | str | None = None, is_last: bool = False,
             fonts: str | None = None) -> str:
        """Slide HTML. image/logo are file paths (rendering) or ready URLs (live preview in the UI)."""
        shade = max(0.0, min(1.0, float(slide.get("shade", 0.55))))
        uri = lambda v: (v if isinstance(v, str) else v.resolve().as_uri()) if v else ""  # noqa: E731
        return self.env.get_template("slide.html").render(
            layout=slide.get("layout", "overlay-top"),
            image=uri(image),
            logo=uri(logo),
            fonts=fonts or FONTS.resolve().as_uri(),
            headline=markup(slide.get("headline", "")),
            subtext=markup(slide.get("subtext", "")),
            eyebrow=slide.get("eyebrow", "") or "",
            quote=markup(slide.get("quote", "") or ""),
            note=markup(slide.get("note", "") or ""),
            script=markup(slide.get("script", "") or ""),
            script_pos=slide.get("script_pos") if slide.get("script_pos") in SCRIPT_POS else "top-right",
            is_last=is_last,
            items=[markup(i) for i in slide.get("items", []) if i.strip()],
            button=slide.get("button", ""),
            text_pos=slide.get("text_pos") if slide.get("text_pos") in ("top", "bottom") else "top",
            img_pos=slide.get("img_pos") if slide.get("img_pos") in ("top", "center", "bottom") else "center",
            shade=round(shade, 2),
        )

    def render_job(self, job: dict, only: list[int] | None = None, log=print) -> dict:
        """Render slides (all, or only the given numbers) into the job's slides/ folder."""
        work = self.project.work / job["sku"]
        slides_dir, html_dir = work / "slides", work / "render"
        slides_dir.mkdir(parents=True, exist_ok=True)
        html_dir.mkdir(parents=True, exist_ok=True)
        slides = job["plan"]["slides"]
        todo = [s for s in slides if only is None or s["n"] in only]
        jobs = []
        last_n = slides[-1]["n"] if slides else None
        for s in todo:
            img = current_image(job, s["n"])
            if not img and s.get("source") != "none":
                raise JobError(f"Slide {s['n']} has no image.")
            logo = self.project.common / "GOlden Logo2.jpg" if s.get("logo") else None
            page_html = self.html(s, self.project.abs(img["file"]) if img and s.get("source") != "none" else None,
                                  logo if logo and logo.exists() else None, is_last=s["n"] == last_n)
            hp = html_dir / f"slide_{s['n']}.html"
            hp.write_text(page_html, encoding="utf-8")
            jobs.append((s["n"], hp, slides_dir / f"bewished_slide_{s['n']}.png"))
        if only is None:  # full render: drop PNGs of slides that no longer exist
            keep = {p.name for _, _, p in jobs}
            for old in slides_dir.glob("bewished_slide_*.png"):
                if old.name not in keep:
                    old.unlink()
        self._screenshot(jobs, log)
        files = job["render"].get("files", {}) if only is not None else {}
        for n, _, png in jobs:
            files[str(n)] = self.project.rel(png)
        job["render"]["files"] = files
        job["render"]["rendered_at"] = now()
        return files

    def _screenshot(self, jobs: list[tuple[int, Path, Path]], log) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(channel="chrome")
            except Exception:
                exe = find_browser()
                if not exe:
                    raise JobError("No Chrome or Edge found for rendering.")
                browser = p.chromium.launch(executable_path=str(exe))
            try:
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
                try:
                    cdp = page.context.new_cdp_session(page)
                except Exception:
                    cdp = None
                for n, hp, png in jobs:
                    page.goto(hp.resolve().as_uri())
                    page.wait_for_function("window.__fitDone === true", timeout=15000)
                    clip = {"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT}
                    try:  # Chrome's fast PNG encoder: about twice as fast as page.screenshot
                        data = cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True,
                                                                   "clip": {**clip, "scale": 1}})
                        png.write_bytes(base64.b64decode(data["data"]))
                    except Exception:
                        page.screenshot(path=str(png), clip=clip)
                    log(f"Rendered slide {n}")
            finally:
                browser.close()
