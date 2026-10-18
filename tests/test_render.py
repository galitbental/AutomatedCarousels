"""Rendering: unit checks plus HTML and pixel regression baselines (UPDATE_GOLDEN=1 to regenerate)."""
import re
import shutil

import pytest
from PIL import Image, ImageChops, ImageStat

from app.jobs import new_job
from app.render import HEIGHT, WIDTH, Renderer, markup
from app.imagegen import add_version
from tests.conftest import GOLDEN, UPDATE, golden_text

LAYOUT_SLIDES = [
    dict(n=1, layout="hook", headline="A necklace from grandma is never just a necklace"),
    dict(n=2, layout="overlay-bottom", headline="You want it to be more than just a gift.",
         subtext="It should carry *love, blessing and protection*,\nand those are the hardest things to put into words."),
    dict(n=3, layout="overlay-top", subtext="It should be personal and unique.\nJust the right words, *from your heart to hers*."),
    dict(n=4, layout="list", headline="Make it truly hers:", items=["Customize engraving", "Add her birthstone",
                                                                     "Personalize the poem", "Add your own words"]),
    dict(n=5, layout="panel", headline="Choose *just the right* engraving for her.", subtext="Her name. Her initial."),
    dict(n=6, layout="overlay-bottom", subtext="Crafted in *Sterling Silver* or *14K Gold Filled*."),
    dict(n=7, layout="cta", headline="Arrives ready to gift.", subtext="Boxed, bagged, and ready to hand over.",
         button="SHOP THE LINK IN BIO", logo=True),
    dict(n=8, layout="framed", headline="To my beloved *Goddaughter*", subtext="Exactly as she receives it."),
    dict(n=9, layout="statement", headline="Because it feels *chosen*.", quote="\u201cI did not get to choose you.\u201d",
         source="none"),
    dict(n=10, layout="checklist", headline="Personalized name?", subtext="We write the poem. You add her name."),
    dict(n=11, layout="guide", eyebrow="Gratitude + love", headline="For Mom", subtext="Send her the thank you.",
         note="So she can keep your picture close.", script="Forever"),
]


def test_markup_escapes_and_accents():
    m = str(markup("<b>Hi</b> *gold* & more\nline"))
    assert "&lt;b&gt;" in m and '<span class="accent">gold</span>' in m and "<br>" in m and "&amp;" in m


def _job_with_images(proj, slides):
    job = new_job("GodDaughter1_G_IC", "DataFromUser/GodDaughter1_G_IC.jpg", {})
    (proj.work / job["sku"]).mkdir(parents=True, exist_ok=True)
    job["plan"]["slides"] = [dict(s, text_pos=s.get("text_pos", "top"), shade=0.55) for s in slides]
    for s in slides:
        if s.get("source") == "none":
            continue
        src = proj.common / ("Box.png" if s["layout"] == "cta" else "BoxExample1.png")
        add_version(proj, job, s["n"], src, "test")
    return job


@pytest.mark.parametrize("slide", LAYOUT_SLIDES, ids=[s["layout"] + str(s["n"]) for s in LAYOUT_SLIDES])
def test_html_golden(proj, slide):
    r = Renderer(proj)
    html = r.html(dict(slide, shade=0.55, text_pos="top"),
                  None if slide.get("source") == "none" else proj.common / "BoxExample1.png",
                  proj.common / "GOlden Logo2.jpg" if slide.get("logo") else None, is_last=slide["n"] == 7)
    html = re.sub(r"file:///[^\"]+", "FILE", html)
    assert ("class=\"arrow\"" in html) == (slide["n"] != 7)
    golden_text(f"html/slide_{slide['n']}_{slide['layout']}.html", html)


def _diff(a: Image.Image, b: Image.Image) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


def test_png_regression(proj):
    job = _job_with_images(proj, LAYOUT_SLIDES)
    files = Renderer(proj).render_job(job, log=lambda m: None)
    assert len(files) == len(LAYOUT_SLIDES)
    failures = []
    for s in LAYOUT_SLIDES:
        png = proj.abs(files[str(s["n"])])
        im = Image.open(png)
        assert im.size == (WIDTH, HEIGHT)
        gold = GOLDEN / "png" / f"slide_{s['n']}_{s['layout']}.png"
        if UPDATE or not gold.exists():
            gold.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, gold)
            continue
        d = _diff(im, Image.open(gold))
        if d > 1.5:
            failures.append(f"{gold.name}: mean pixel difference {d:.2f}")
    assert not failures, "Visual regression (set UPDATE_GOLDEN=1 if intended): " + "; ".join(failures)


def test_partial_render_and_cleanup(proj):
    job = _job_with_images(proj, LAYOUT_SLIDES[:3])
    r = Renderer(proj)
    r.render_job(job, log=lambda m: None)
    stale = proj.work / job["sku"] / "slides" / "bewished_slide_9.png"
    stale.write_bytes(b"x")
    files = r.render_job(job, only=[2], log=lambda m: None)
    assert set(files) == {"1", "2", "3"} and stale.exists()  # partial render keeps others
    r.render_job(job, log=lambda m: None)
    assert not stale.exists()  # full render removes PNGs of deleted slides


def test_long_text_is_fitted(proj):
    long = dict(n=1, layout="hook", headline=" ".join(["Wonderfully"] * 40))
    job = _job_with_images(proj, [long])
    files = Renderer(proj).render_job(job, log=lambda m: None)
    assert Image.open(proj.abs(files["1"])).size == (WIDTH, HEIGHT)


def test_missing_image_raises(proj):
    from app.jobs import JobError
    job = new_job("A", "x", {})
    job["plan"]["slides"] = [dict(n=1, layout="hook", headline="x")]
    with pytest.raises(JobError):
        Renderer(proj).render_job(job)
