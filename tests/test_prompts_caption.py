from app import prompts as P
from app.caption import caption_file_text, chosen_hook, plan_markdown
from app.jobs import new_job
from app.sku import parse_sku
from app.styles import load_table
from tests.conftest import golden_text


def _job(proj, sku="GodDaughter1_G_IC", **intake):
    table = load_table(proj)
    info = parse_sku(sku, table).to_dict()
    job = new_job(sku, f"DataFromUser/{sku}.jpg", info)
    job["intake"].update({"from": ["aunt"], "to": ["goddaughter"], "event": ["Baptism"], **intake})
    return job, table.by_name(info["jewelry_type"])


def test_baseline(proj):
    job, t = _job(proj)
    slides = P.baseline_slides(proj, job, t)
    assert len(slides) == 7
    assert [s["source"] for s in slides] == ["generate", "none", "generate", "generate", "library", "library", "common"]
    assert slides[0]["headline"] == "A necklace from her aunt is never just a necklace"
    assert slides[1]["layout"] == "statement" and slides[1]["references"] == []
    assert slides[0]["references"][0] == job["input_file"]
    assert "BLACK Be Wished" in slides[0]["prompt"]
    assert "RealProductPhotos/InterlockingCircelsNecklace/Model20Gold.jpg" in slides[4]["references"]
    # infographics come after clean photos
    assert slides[4]["references"][0].endswith("Model20Gold.jpg")
    assert "joyful" in slides[2]["prompt"]


def test_baseline_gentle_and_male(proj):
    job, t = _job(proj, tone="gentle", gender="male", to=["son"], **{"from": ["grandma", "mom"]})
    slides = P.baseline_slides(proj, job, t)
    assert "comforting" in slides[2]["prompt"]
    assert "his" in slides[3]["subtext"] and "him" in slides[4]["headline"]
    assert slides[0]["headline"].startswith("A necklace from Grandma")


def test_sanitize_plan(proj):
    job, t = _job(proj)
    base = P.baseline_slides(proj, job, t)
    raw = {"hooks": ["Hook A", " "], "slides": [
        {"layout": "weird", "source": "generate", "references": ["RealProductPhotos/Common/Box2.png", "nope.png", "../x"],
         "headline": "ignored", "prompt": "p1"},
        {"layout": "panel", "source": "library", "slot": "bad", "items": ["a", " "], "headline": "H2"},
        {"layout": "cta", "source": "common", "slot": "options"},
    ], "caption": " Cap ", "hashtags": ["Gift", "#gift", "#Two"]}
    plan = P.sanitize_plan(raw, proj, base, 5)
    assert plan["hooks"][0] == "Hook A" and len(plan["hooks"]) == 3
    s1, s2, s3 = plan["slides"]
    assert s1["layout"] == "hook" and s1["headline"] == "Hook A"
    assert s1["references"] == ["RealProductPhotos/Common/Box2.png"]
    assert s2["slot"] == "options" and s2["items"] == ["a"] and s2["prompt"] == base[1]["prompt"] == ""
    assert s3["slot"] == "cta"
    assert plan["caption"] == "Cap" and plan["hashtag_target"] == 5
    assert plan["hashtags"] == ["#gift", "#two", "#bewished", "#bewishedgifts", "#morethanjewelry"]
    assert plan["voice"] == "" and plan["carousel_type"] == ""
    statement = P.sanitize_plan({"slides": [{"layout": "statement", "source": "generate", "prompt": "x",
                                             "references": ["RealProductPhotos/Common/Box2.png"]}]}, proj, base)
    assert statement["slides"][0]["source"] == "none" and statement["slides"][0]["references"] == []


def test_plan_prompt_contents(proj):
    job, t = _job(proj, card_text="You are a treasure")
    base = P.baseline_slides(proj, job, t)
    txt = P.plan_prompt(job, t, "FACT-STYLE", "FACT-COMMON", base, ["Old hook"], [["#a", "#b"]], 17,
                        P.available_references(proj, t), recent_posts=[{"voice": "founder", "carousel_type": "because"}])
    for needle in ("FACT-STYLE", "FACT-COMMON", "Old hook", "#a #b", "exactly 17 hashtags", "#bewished",
                   "You are a treasure", "Baptism", "she/her/her", "RealProductPhotos/Common/Box.png",
                   "NEVER mention price", "MUST differ from the previous carousel's voice (founder)",
                   "Two circles that hold", "Caption template", "statement: pure black slide"):
        assert needle in txt, needle
    fixed = P.plan_prompt(job, t, "", "", base, [], [], 9, [], voice="brand", carousel_type="checklist")
    assert "Use the brand voice." in fixed and "Carousel type: checklist" in fixed


def test_other_prompts(proj):
    job, _ = _job(proj, sku="AugustBday2_G_D8")
    assert job["input_file"] in P.card_prompt(job)
    c = P.chrome_agent_prompt("FULL", ["C:/a.png"], "", "https://chatgpt.com/")
    assert "NEW chat" in c and "C:/a.png" in c and "FULL" in c
    assert "existing ChatGPT conversation: https://chatgpt.com/c/1" in P.chrome_agent_prompt("F", [], "https://chatgpt.com/c/1", "u")
    assert "x.png" in P.qa_prompt("x.png", "in.jpg", "card", {"purpose": "p", "prompt": "q"})
    assert P.image_prompt(" a ", " b ") == "a\n\nb"


def _plan_job(proj):
    job, t = _job(proj)
    job["plan"] = {"hooks": ["Hook one", "Hook two", "Hook three"], "hook_choice": 1,
                   "slides": P.baseline_slides(proj, job, t), "caption": "Line 1.\n\nShop through the link in bio.",
                   "hashtags": ["#b", "#a", "#c"]}
    return job


def test_caption_golden(proj):
    job = _plan_job(proj)
    assert chosen_hook(job["plan"]) == "Hook two"
    text = caption_file_text(job["plan"])
    assert text.startswith("POST CAPTION and HASHTAGS\n")
    golden_text("caption.txt", text)


def test_plan_markdown(proj):
    md = plan_markdown(_plan_job(proj))
    for needle in ("# Carousel GodDaughter1_G_IC", "**Hook two**", "### Slide 7: Trust & CTA", "## Hashtags", "#b #a #c"):
        assert needle in md
