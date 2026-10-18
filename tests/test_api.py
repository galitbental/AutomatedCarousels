"""API + service: every endpoint, gating, confinement, and the full pipeline end to end."""
import io
import json
import time

import pytest

from app.fakes import placeholder_image

SKU = "GodDaughter1_G_IC"


def wait(client, task, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        t = client.get(f"/api/tasks/{task['id']}").get_json()
        if t["status"] != "running":
            return t
        time.sleep(0.05)
    raise AssertionError("task did not finish")


def ok(resp, code=200):
    assert resp.status_code == code, resp.get_data(as_text=True)
    return resp.get_json()


def to_intake_done(client):
    ok(client.post("/api/jobs", json={"sku": SKU}))  # the catalog card fills from / to / event
    ok(client.patch(f"/api/jobs/{SKU}", json={"intake": {"event": ["Baptism", "Christmas"]}}))
    return ok(client.post(f"/api/jobs/{SKU}/approve/intake"))


def to_facts_done(client):
    to_intake_done(client)
    t = wait(client, ok(client.post("/api/facts/InterlockingCircelsNecklace/draft", json={"sku": SKU})))
    assert t["status"] == "done", t
    return ok(client.post(f"/api/jobs/{SKU}/approve/facts"))


def to_plan_done(client):
    to_facts_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "all"})))
    assert t["status"] == "done", t
    return ok(client.post(f"/api/jobs/{SKU}/approve/plan"))


def to_images_done(client):
    to_plan_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/images/generate-missing")))
    assert t["status"] == "done", t
    return ok(client.post(f"/api/jobs/{SKU}/approve/images"))


def to_slides_done(client):
    to_images_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/render", json={})))
    assert t["status"] == "done", t
    return ok(client.post(f"/api/jobs/{SKU}/approve/slides"))


# ---------------------------------------------------------------- basics
def test_index_and_static(client):
    assert b"Carousel Studio" in client.get("/").data
    assert client.get("/web/app.js").status_code == 200
    assert ok(client.get("/api/ping"))["app"] == "carousel-studio"


def test_queue_statuses(client):
    q = ok(client.get("/api/queue"))
    st = {i["sku"]: (i["status"], i["reason"]) for i in q["inputs"]}
    assert st[SKU][0] == "ready" and st["Sister25_G_D6"][0] == "ready"
    assert st["Mystery1_G_XYZ"][0] == "blocked" and "Unknown" in st["Mystery1_G_XYZ"][1]
    assert st["Niece11_S_COM033"][0] == "blocked" and "empty" in st["Niece11_S_COM033"][1]
    ok(client.post("/api/jobs", json={"sku": SKU}))
    q = ok(client.get("/api/queue"))
    assert {i["sku"]: i["status"] for i in q["inputs"]}[SKU] == "in_progress"
    assert q["jobs"][0]["sku"] == SKU


def test_start_blocked_and_missing(client):
    assert client.post("/api/jobs", json={"sku": "Niece11_S_COM033"}).status_code == 400
    assert client.post("/api/jobs", json={"sku": "Nope_G_IC"}).status_code == 404
    assert client.get("/api/jobs/Nope_G_IC").status_code == 404


def test_file_confinement(client):
    assert client.get("/file?path=DataFromUser/GodDaughter1_G_IC.jpg").status_code == 200
    assert client.get("/file?path=../../Windows/win.ini").status_code == 400
    assert client.get("/file?path=C:/Windows/win.ini").status_code == 400
    assert client.get("/file?path=missing.png").status_code == 404


def test_open_path(client, studio):
    ok(client.post("/api/open", json={"path": "DataFromUser"}))
    assert studio.opened[-1].name == "DataFromUser"
    assert client.post("/api/open", json={"path": "nope"}).status_code == 404


def test_settings_roundtrip(client):
    s = ok(client.get("/api/settings"))
    assert s["model"] == "sonnet"
    s2 = ok(client.put("/api/settings", json={"model": "opus", "text_timeout": "120", "qa_enabled": False, "bogus": 1}))
    assert s2["model"] == "opus" and s2["text_timeout"] == 120 and s2["qa_enabled"] is False and "bogus" not in s2


def test_system(client):
    s = ok(client.get("/api/system"))
    assert s["folders"]["inputs"] and s["image_backend"] == "fake"
    assert any(x["folder"] == "InterlockingCircelsNecklace" and x["status"] == "ready" for x in s["styles"])


def test_log_and_tasks(client):
    ok(client.post("/api/jobs", json={"sku": SKU}))
    t = ok(client.post(f"/api/jobs/{SKU}/intake/read"))
    wait(client, t)
    log = ok(client.get("/api/log?after=0"))
    assert any("Read poem card" in e["msg"] for e in log["items"])
    assert client.get("/api/tasks/zzz").status_code == 404
    assert client.post("/api/tasks/zzz/cancel").status_code == 404


# ---------------------------------------------------------------- intake
def test_intake_prefilled_from_catalog(client):
    v = ok(client.post("/api/jobs", json={"sku": SKU}))
    it, cat = v["job"]["intake"], v["job"]["catalog"]
    assert cat["status"] == "found" and cat["chosen"] == "GodDaughter1_IC" and cat["method"] == "poem+variant"
    assert it["from"] == ["aunt", "godmother"] and it["to"] == ["goddaughter"] and it["event"] == ["Just because"]
    assert it["card_headline"] == "To my beloved Goddaughter" and it["source"] == "catalog:GodDaughter1_IC"
    assert "godmother" in v["context"]["relations"] and "Wedding" in v["context"]["events"]
    # choose the other card -> form refilled from it
    v = ok(client.post(f"/api/jobs/{SKU}/intake/catalog", json={"key": "GodDaughter1"}))
    assert v["job"]["intake"]["from"] == ["mother"] and v["job"]["catalog"]["method"] == "chosen by user"
    assert client.post(f"/api/jobs/{SKU}/intake/catalog", json={"key": "Nope_X"}).status_code == 404
    v = ok(client.post(f"/api/jobs/{SKU}/intake/catalog", json={}))
    assert v["job"]["catalog"]["chosen"] == "GodDaughter1_IC"
    img = client.get("/api/catalog/image?name=GodDaughter1_IC_MainImage.jpg")
    assert img.status_code == 200 and img.mimetype.startswith("image/")
    assert client.get("/api/catalog/image?name=../secret.jpg").status_code == 404
    assert client.get("/api/catalog/image?name=GodDaughter1_IC_PoemText.txt").status_code == 404
    # multi-select: empty list blocks, several values are kept; no confirmation needed
    ok(client.patch(f"/api/jobs/{SKU}", json={"intake": {"event": []}}))
    r = client.post(f"/api/jobs/{SKU}/approve/intake")
    assert r.status_code == 400 and "event" in r.get_json()["error"]
    v = ok(client.patch(f"/api/jobs/{SKU}", json={"intake": {"event": ["Baptism", "Birthday"], "age_group": "teen"}}))
    assert v["job"]["intake"]["event"] == ["Baptism", "Birthday"] and v["job"]["intake"]["age_group"] == ["teen"]
    v = ok(client.post(f"/api/jobs/{SKU}/approve/intake"))
    assert v["job"]["stages"]["intake"] == "approved" and v["job"]["stages"]["facts"] == "open"
    # approved stage is read-only until reopened
    assert client.patch(f"/api/jobs/{SKU}", json={"intake": {"from": "x"}}).status_code == 409
    v = ok(client.post(f"/api/jobs/{SKU}/reopen/intake"))
    assert v["job"]["stages"]["intake"] == "open"


def test_read_card_fills_empty_fields(client, proj):
    placeholder_image(proj.inputs / "Nocard1_G_IC.jpg", "x")
    v = ok(client.post("/api/jobs", json={"sku": "Nocard1_G_IC"}))
    assert v["job"]["catalog"]["status"] == "not_found" and v["job"]["intake"]["from"] == []
    wait(client, ok(client.post("/api/jobs/Nocard1_G_IC/intake/read")))
    it = ok(client.get("/api/jobs/Nocard1_G_IC"))["job"]["intake"]
    assert it["from"] == ["aunt"] and it["to"] == ["goddaughter"] and it["event"] == ["Baptism"]


def test_catalog_offline_does_not_block(client, studio):
    studio.save_settings({"catalog_dir": r"Z:\\no\\such\\catalog"})
    v = ok(client.post("/api/jobs", json={"sku": SKU}))
    assert v["job"]["catalog"]["status"] == "unavailable"


def test_read_card_failure_is_reported(client, studio):
    studio.assistant.fail.add("read_card")
    ok(client.post("/api/jobs", json={"sku": SKU}))
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/intake/read")))
    assert t["status"] == "error" and "fake failure" in t["error"]


def test_loss_poem_gentle(client, proj):
    placeholder_image(proj.inputs / "Fatherloss6_S(18)_IC.jpg", "loss")
    v = ok(client.post("/api/jobs", json={"sku": "Fatherloss6_S(18)_IC"}))
    assert v["job"]["intake"]["tone"] == "gentle"


# ---------------------------------------------------------------- facts
def test_facts_endpoints_and_auto_approve(client, proj):
    f = ok(client.get("/api/facts/_Common"))
    assert not f["approved"] and "14K" in f["text"]
    assert client.get("/api/facts/NotAStyle").status_code == 404
    ok(client.put("/api/facts/InterlockingCircelsNecklace", json={"text": "# IC", "approved": True}))
    ok(client.put("/api/facts/_Common", json={"text": f["text"], "approved": True}))
    v = to_intake_done(client)
    assert v["job"]["stages"]["facts"] == "approved"  # both already approved -> skipped
    assert v["job"]["stages"]["plan"] == "open"


def test_facts_drafted_automatically(client, studio):
    v = to_intake_done(client)
    assert any(c.startswith("draft_facts") for c in studio.assistant.calls) or v["context"]["tasks"]
    import time as _t
    end = _t.time() + 10
    while _t.time() < end and not ok(client.get("/api/facts/InterlockingCircelsNecklace"))["text"]:
        _t.sleep(0.05)
    f = ok(client.get("/api/facts/InterlockingCircelsNecklace"))
    assert f["text"].startswith("# Interlocking circles necklace") and not f["approved"]


def test_facts_stage_requires_text(client, studio):
    studio.assistant.fail.add("draft_facts")
    to_intake_done(client)
    r = client.post(f"/api/jobs/{SKU}/approve/facts")
    assert r.status_code == 400 and "empty" in r.get_json()["error"]


# ---------------------------------------------------------------- plan
def test_plan_generation_and_gating(client):
    assert client.post(f"/api/jobs/{SKU}/plan/generate").status_code == 404
    to_facts_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "all"})))
    assert t["status"] == "done"
    v = ok(client.get(f"/api/jobs/{SKU}"))
    plan = v["job"]["plan"]
    assert len(plan["slides"]) == 7 and plan["slides"][0]["headline"] == plan["hooks"][0]
    assert 3 <= len(plan["hashtags"]) <= 30 and plan["hashtag_target"] == len(plan["hashtags"])
    assert plan["hashtags"][-3:] == ["#bewished", "#bewishedgifts", "#morethanjewelry"]
    assert plan["voice"] == "giver" and plan["carousel_type"] == "story"
    assert plan["slides"][1]["source"] == "none" and plan["slides"][1]["prompt"] == ""
    assert plan["slides"][5]["eyebrow"] and plan["slides"][4]["script"]
    assert v["context"]["hashtag_check"]["errors"] == []
    # regenerate one part only
    before = plan["slides"]
    wait(client, ok(client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "caption"})))
    assert ok(client.get(f"/api/jobs/{SKU}"))["job"]["plan"]["slides"] == before
    assert client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "bogus"}).status_code == 400


def test_plan_validation(client):
    to_facts_done(client)
    v = ok(client.post(f"/api/jobs/{SKU}/plan/baseline"))
    slides = v["job"]["plan"]["slides"]
    v = ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"hashtags": "#a #b #bewished"}}))
    assert v["job"]["plan"]["hashtags"] == ["#a", "#b", "#bewished", "#bewishedgifts", "#morethanjewelry"]
    ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"slides": slides[:6]}}))
    assert "7 to 10" in client.post(f"/api/jobs/{SKU}/approve/plan").get_json()["error"]
    bad = [dict(s) for s in slides]
    bad[1]["headline"] = "So happy 💛"
    ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"slides": bad}}))
    assert "No emoji" in client.post(f"/api/jobs/{SKU}/approve/plan").get_json()["error"]
    ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"slides": slides, "hooks": ["", "", ""]}}))
    assert "hook" in client.post(f"/api/jobs/{SKU}/approve/plan").get_json()["error"]


def test_plan_warnings_need_confirmation(client, studio):
    studio.ledgers.add_hook("Used hook", "OLD")
    studio.ledgers.add_hashtags(["#a", "#b", "#c", "#d", "#bewished", "#bewishedgifts", "#morethanjewelry"], "OLD")
    studio.ledgers.add_post("OLD", "giver", "story", "Used hook")
    to_facts_done(client)
    ok(client.post(f"/api/jobs/{SKU}/plan/baseline"))
    ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"hooks": ["Used hook", "", ""], "hashtags": "#a #b #c #e",
                                                         "voice": "giver", "caption": "Affordable gift. Link in bio."}}))
    v = ok(client.get(f"/api/jobs/{SKU}"))
    assert v["context"]["hook_used"]["sku"] == "OLD" and v["context"]["hashtag_check"]["warnings"]
    assert v["context"]["last_post"]["voice"] == "giver" and v["context"]["lint"]["warnings"]
    r = client.post(f"/api/jobs/{SKU}/approve/plan")
    body = r.get_json()
    assert r.status_code == 409 and body["needs_confirm"] and len(body["warnings"]) == 4
    assert any("voice" in w for w in body["warnings"]) and any("price" in w for w in body["warnings"])
    v = ok(client.post(f"/api/jobs/{SKU}/approve/plan", json={"force": True}))
    assert v["job"]["stages"]["plan"] == "approved"


def test_plan_duplicate_hashtags_blocked(client, studio):
    studio.ledgers.add_hashtags(["#a", "#b", "#c", "#bewished", "#bewishedgifts", "#morethanjewelry"], "OLD")
    to_facts_done(client)
    ok(client.post(f"/api/jobs/{SKU}/plan/baseline"))
    ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"hashtags": "#c #b #a"}}))
    r = client.post(f"/api/jobs/{SKU}/approve/plan", json={"force": True})
    assert r.status_code == 400 and "Identical" in r.get_json()["error"]


def test_slide_reorder_keeps_images(client):
    to_images_done(client)
    ok(client.post(f"/api/jobs/{SKU}/reopen/plan"))
    v = ok(client.get(f"/api/jobs/{SKU}"))
    job = v["job"]
    img3 = job["images"]["3"]["versions"][0]["file"]
    assert "2" not in job["images"]  # black statement slide has no image
    slides = job["plan"]["slides"]
    slides[0], slides[2] = slides[2], slides[0]
    v = ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"slides": slides}}))
    assert v["job"]["images"]["1"]["versions"][0]["file"] == img3
    assert [s["n"] for s in v["job"]["plan"]["slides"]] == list(range(1, 8))
    assert v["job"]["stages"]["images"] == "stale"


# ---------------------------------------------------------------- images
def test_autofill_library_and_common(client, studio):
    v = to_plan_done(client)
    job = v["job"]
    assert job["images"]["7"]["versions"][0]["origin"] == "library"  # seeded _Common/cta Box.png
    assert "5" not in job["images"]  # options library empty -> must be generated


def test_image_operations(client, studio, downloads):
    to_plan_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/images/1/generate")))
    assert t["status"] == "done", t
    v = ok(client.get(f"/api/jobs/{SKU}"))
    cur = v["job"]["images"]["1"]["versions"][-1]
    assert cur["origin"] == "fake" and cur["qa"]["ok"] and "Do NOT add any text" in cur["prompt"]
    assert v["job"]["chat_url"]
    # import from downloads
    assert client.post(f"/api/jobs/{SKU}/images/2/import").status_code == 400
    placeholder_image(downloads / "ChatGPT Image 1.png", "dl")
    v = ok(client.post(f"/api/jobs/{SKU}/images/2/import"))
    assert v["job"]["images"]["2"]["versions"][-1]["origin"] == "download"  # allowed even on a black slide
    assert not (downloads / "ChatGPT Image 1.png").exists()  # moved into the job
    # upload
    buf = io.BytesIO()
    placeholder_image(downloads / "u.png", "u")
    buf.write((downloads / "u.png").read_bytes())
    buf.seek(0)
    v = ok(client.post(f"/api/jobs/{SKU}/images/3/upload", data={"file": (buf, "mine.png")},
                       content_type="multipart/form-data"))
    assert v["job"]["images"]["3"]["versions"][-1]["origin"] == "upload"
    bad = client.post(f"/api/jobs/{SKU}/images/3/upload", data={"file": (io.BytesIO(b"x"), "a.txt")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400
    # use input / common / library
    v = ok(client.post(f"/api/jobs/{SKU}/images/4/use", json={"kind": "input"}))
    assert v["job"]["images"]["4"]["versions"][-1]["origin"] == "input"
    v = ok(client.post(f"/api/jobs/{SKU}/images/4/use", json={"kind": "common", "file": "RealProductPhotos/Common/BoxExample3.png"}))
    assert v["job"]["images"]["4"]["versions"][-1]["origin"] == "common"
    assert client.post(f"/api/jobs/{SKU}/images/4/use", json={"kind": "common", "file": "DataFromUser/GodDaughter1_G_IC.jpg"}).status_code == 400
    # version switch
    v = ok(client.patch(f"/api/jobs/{SKU}", json={"images_current": {"4": 0}}))
    assert v["job"]["images"]["4"]["current"] == 0
    # save to library, then it is offered for that slot
    wait(client, ok(client.post(f"/api/jobs/{SKU}/images/5/generate")))
    v = ok(client.post(f"/api/jobs/{SKU}/images/5/library", json={"slot": "options"}))
    assert v["context"]["library"]["options"][0]["approved"]
    lib = ok(client.get("/api/library"))
    assert any(s["style"] == "InterlockingCircelsNecklace" for s in lib["styles"])
    # QA on demand
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/images/5/qa")))
    assert t["status"] == "done" and t["result"]["ok"]


def test_qa_retry(client, studio):
    calls = {"n": 0}
    orig = studio.assistant.qa_image

    def flaky(*a, **k):
        calls["n"] += 1
        return {"ok": False, "issues": ["box is grey"], "prompt_fix": "Make the box black."} if calls["n"] == 1 else orig(*a, **k)
    studio.assistant.qa_image = flaky
    to_plan_done(client)
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/images/1/generate")))
    assert t["status"] == "done" and calls["n"] == 2
    versions = ok(client.get(f"/api/jobs/{SKU}"))["job"]["images"]["1"]["versions"]
    assert len(versions) == 2 and "Make the box black." in versions[-1]["prompt"]


def test_images_approval_requires_all(client):
    to_plan_done(client)
    r = client.post(f"/api/jobs/{SKU}/approve/images")
    assert r.status_code == 400 and "without image" in r.get_json()["error"]


def test_cancel_generation(client, studio):
    import threading
    gate = threading.Event()
    orig = studio.backend.generate

    def slow(job, slide, cancel=None, log=print):
        gate.wait(5)
        if cancel.is_set():
            raise RuntimeError("cancelled")
        return orig(job, slide, cancel, log)
    studio.backend.generate = slow
    to_plan_done(client)
    t = ok(client.post(f"/api/jobs/{SKU}/images/1/generate"))
    ok(client.post(f"/api/tasks/{t['id']}/cancel"))
    gate.set()
    assert wait(client, t)["status"] == "cancelled"


# ---------------------------------------------------------------- slides & final
def test_render_dirty_tracking(client):
    to_images_done(client)
    r = client.post(f"/api/jobs/{SKU}/approve/slides")
    assert r.status_code == 400 and "not rendered" in r.get_json()["error"]
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/render", json={})))
    assert t["status"] == "done", t
    ok(client.patch(f"/api/jobs/{SKU}", json={"slide_text": {"3": {"headline": "Changed *gold*", "bogus": 1}}}))
    v = ok(client.get(f"/api/jobs/{SKU}"))
    assert v["job"]["plan"]["slides"][2]["headline"] == "Changed *gold*" and "bogus" not in v["job"]["plan"]["slides"][2]
    r = client.post(f"/api/jobs/{SKU}/approve/slides")
    assert r.status_code == 400 and "3" in r.get_json()["error"]
    wait(client, ok(client.post(f"/api/jobs/{SKU}/render", json={"only": [3]})))
    ok(client.post(f"/api/jobs/{SKU}/approve/slides"))


def test_full_pipeline_end_to_end(client, proj, studio):
    v = to_slides_done(client)
    assert v["job"]["stages"]["final"] == "open"
    ok(client.patch(f"/api/jobs/{SKU}", json={"final_text": {"caption": "Final caption.\n\nShop through the link in bio."}}))
    res = ok(client.post(f"/api/jobs/{SKU}/finalize"))
    dest = proj.abs(res["dest"])
    assert dest.name.startswith(time.strftime("%Y-%m-%d")) and dest.name.endswith("_GodDaughter1_G_IC_baptism")
    assert studio.ledgers.posts()[0] == {**studio.ledgers.posts()[0], "sku": SKU, "voice": "giver", "carousel_type": "story"}
    names = {p.name for p in dest.iterdir()}
    assert {f"bewished_slide_{i}.png" for i in range(1, 8)} <= names
    assert {"POST CAPTION and HASHTAGS.txt", "plan.md", "job.json", "raw"} <= names
    cap = (dest / "POST CAPTION and HASHTAGS.txt").read_text(encoding="utf-8")
    assert cap.startswith("POST CAPTION and HASHTAGS\nFinal caption.")
    saved = json.loads((dest / "job.json").read_text(encoding="utf-8"))
    assert saved["stages"]["final"] == "approved"
    # cleanup + ledgers
    assert not (proj.inputs / f"{SKU}.jpg").exists()
    assert not (proj.work / SKU).exists()
    assert studio.ledgers.hooks()[0]["sku"] == SKU
    assert studio.ledgers.hashtag_sets()[0]["tags"]
    assert studio.ledgers.library_usage()[0]["slot"] == "cta"
    assert SKU not in {i["sku"] for i in ok(client.get("/api/queue"))["inputs"]}
    assert client.get(f"/api/jobs/{SKU}").status_code == 404


def test_finalize_failure_deletes_nothing(client, proj, studio):
    to_slides_done(client)
    png = proj.work / SKU / "slides" / "bewished_slide_4.png"
    png.unlink()
    r = client.post(f"/api/jobs/{SKU}/finalize")
    assert r.status_code == 400
    assert (proj.inputs / f"{SKU}.jpg").exists() and (proj.work / SKU).exists()
    assert not [p for p in proj.carousels.iterdir() if p.name != "_work"]
    assert studio.ledgers.hooks() == []


def test_finalize_requires_all_stages(client):
    to_plan_done(client)
    assert client.post(f"/api/jobs/{SKU}/finalize").status_code == 409


def test_destination_collision(client, proj):
    to_plan_done(client)
    from app.finalize import destination
    job = ok(client.get(f"/api/jobs/{SKU}"))["job"]
    first = destination(proj, job)
    (proj.carousels / first).mkdir()
    assert destination(proj, job) == first + "-2"


def test_discard_keeps_input(client, proj):
    ok(client.post("/api/jobs", json={"sku": SKU}))
    ok(client.delete(f"/api/jobs/{SKU}"))
    assert (proj.inputs / f"{SKU}.jpg").exists() and not (proj.work / SKU).exists()


def test_second_carousel_cannot_reuse_hashtags(client, proj, studio):
    to_slides_done(client)
    tags = ok(client.get(f"/api/jobs/{SKU}"))["job"]["plan"]["hashtags"]
    ok(client.post(f"/api/jobs/{SKU}/finalize"))
    other = "Sister25_G_D6"
    ok(client.post("/api/jobs", json={"sku": other}))
    ok(client.patch(f"/api/jobs/{other}", json={"intake": {"event": ["Birthday"]}}))
    ok(client.post(f"/api/jobs/{other}/approve/intake"))
    ok(client.put("/api/facts/DropBirthstoneNecklace", json={"text": "# Drop", "approved": True}))
    ok(client.post(f"/api/jobs/{other}/approve/facts"))
    ok(client.post(f"/api/jobs/{other}/plan/baseline"))
    ok(client.patch(f"/api/jobs/{other}", json={"plan": {"hashtags": list(reversed(tags))}}))
    r = client.post(f"/api/jobs/{other}/approve/plan", json={"force": True})
    assert r.status_code == 400 and "Identical" in r.get_json()["error"]

def test_live_preview_and_fonts(client):
    to_plan_done(client)
    html = client.get(f"/api/jobs/{SKU}/preview/1").get_data(as_text=True)
    assert "/web/placeholder.svg" in html and "/fonts/PlayfairDisplay.ttf" in html and 'class="arrow"' in html
    black = client.get(f"/api/jobs/{SKU}/preview/2").get_data(as_text=True)
    assert "layout-statement" in black and "placeholder" not in black
    last = client.get(f"/api/jobs/{SKU}/preview/7").get_data(as_text=True)
    assert "/file?path=" in last and 'class="arrow"' not in last  # library image, last slide
    assert client.get(f"/api/jobs/{SKU}/preview/99").status_code == 404
    assert client.get("/fonts/PlayfairDisplay.ttf").status_code == 200
    assert client.get("/fonts/../server.py").status_code == 404
    assert client.get("/web/placeholder.svg").status_code == 200


# ---------------------------------------------------------------- black / image toggle, reference picker
def test_toggle_black_and_image_slide(client):
    to_facts_done(client)
    wait(client, ok(client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "all"})))
    s3 = ok(client.get(f"/api/jobs/{SKU}"))["job"]["plan"]["slides"][2]
    assert s3["source"] != "none"
    v = ok(client.post(f"/api/jobs/{SKU}/slides/3/kind", json={"black": True}))
    b3 = v["job"]["plan"]["slides"][2]
    assert b3["source"] == "none" and b3["layout"] == "statement"
    v = ok(client.post(f"/api/jobs/{SKU}/slides/3/kind", json={"black": False}))  # back: layout + source restored
    r3 = v["job"]["plan"]["slides"][2]
    assert (r3["source"], r3["layout"], r3["prompt"]) == (s3["source"], s3["layout"], s3["prompt"])
    # the black statement slide 2 becomes an image slide with a starting prompt and the input photo as reference
    v = ok(client.post(f"/api/jobs/{SKU}/slides/2/kind", json={"black": False}))
    s2 = v["job"]["plan"]["slides"][1]
    assert s2["source"] == "generate" and s2["layout"] == "overlay-bottom" and s2["text_pos"] == "bottom"
    assert "Be Wished gift box" in s2["prompt"] and s2["references"] == [v["job"]["input_file"]]
    # the plan autosave keeps the toggle (statement would force a black slide)
    v = ok(client.patch(f"/api/jobs/{SKU}", json={"plan": {"slides": v["job"]["plan"]["slides"]}}))
    assert v["job"]["plan"]["slides"][1]["source"] == "generate"


def test_toggle_on_images_stage_and_locked(client):
    to_plan_done(client)
    v = ok(client.post(f"/api/jobs/{SKU}/slides/2/kind", json={"black": False}))  # plan approved, images open
    assert v["job"]["plan"]["slides"][1]["source"] == "generate"
    r = client.post(f"/api/jobs/{SKU}/approve/images")
    assert r.status_code == 400  # slide 2 now needs an image
    ok(client.post(f"/api/jobs/{SKU}/slides/2/kind", json={"black": True}))
    t = wait(client, ok(client.post(f"/api/jobs/{SKU}/images/generate-missing")))
    assert t["status"] == "done" and t["kind"] == "gen:all"  # the UI rings the bell for this task kind
    ok(client.post(f"/api/jobs/{SKU}/approve/images"))
    r = client.post(f"/api/jobs/{SKU}/slides/2/kind", json={"black": False})
    assert r.status_code == 409 and "Reopen" in r.get_json()["error"]


def test_reference_picker_sees_new_files(client, proj):
    to_facts_done(client)
    wait(client, ok(client.post(f"/api/jobs/{SKU}/plan/generate", json={"part": "all"})))
    groups = {g["key"]: g for g in ok(client.get(f"/api/jobs/{SKU}/references"))["groups"]}
    assert groups["input"]["files"] == [f"DataFromUser/{SKU}.jpg"]
    assert "RealProductPhotos/Common/Box.png" in groups["common"]["files"]
    assert "RealProductPhotos/DropBirthstoneNecklace/Model7.jpg" in groups["other"]["files"]
    # a photo added while the app runs (also in a subfolder) shows up on the next call
    new = proj.photos / "InterlockingCircelsNecklace" / "New" / "Hands close-up.png"
    placeholder_image(new, "new")
    groups = {g["key"]: g for g in ok(client.get(f"/api/jobs/{SKU}/references"))["groups"]}
    rel = "RealProductPhotos/InterlockingCircelsNecklace/New/Hands close-up.png"
    assert rel in groups["style"]["files"]
    v = ok(client.put(f"/api/jobs/{SKU}/slides/1/references", json={"references": [rel, rel, f"DataFromUser/{SKU}.jpg"]}))
    assert v["job"]["plan"]["slides"][0]["references"] == [rel, f"DataFromUser/{SKU}.jpg"]  # order kept, no duplicates
    assert client.put(f"/api/jobs/{SKU}/slides/1/references", json={"references": ["../outside.png"]}).status_code == 400
    th = client.get("/thumb", query_string={"path": rel})
    assert th.status_code == 200 and th.mimetype == "image/jpeg"
    assert client.get("/thumb", query_string={"path": "nope.png"}).status_code == 404


def test_version_ping_shutdown_and_no_cache(client, studio, flask_app):
    p = ok(client.get("/api/ping"))
    assert len(p["version"]) == 12 and p["busy"] == 0
    assert client.get("/web/app.js").headers["Cache-Control"] == "no-cache"
    assert client.get("/").headers["Cache-Control"] == "no-cache"
    stopped = []
    flask_app.stop_server = lambda: stopped.append(1)
    ok(client.post("/api/shutdown"))
    end = time.time() + 3
    while not stopped and time.time() < end:
        time.sleep(0.05)
    assert stopped
    assert ok(client.get("/api/settings"))["bell_sound"] is True
