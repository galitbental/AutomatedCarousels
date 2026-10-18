"""Drives the real UI in headless Chrome through all six stages (fake Claude/ChatGPT)."""
import threading

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app.fakes import placeholder_image
from app.server import create_app

pytestmark = pytest.mark.ui
SKU = "GodDaughter1_G_IC"


@pytest.fixture
def server(studio):
    app = create_app(studio)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def page(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        pg = browser.new_page(viewport={"width": 1500, "height": 950})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(server)
        yield pg
        browser.close()
        assert not errors, f"JavaScript errors: {errors}"


def approve(page, stage):
    page.click("#btn-approve")
    expect(page.locator(f"#step-{stage}.approved")).to_be_visible(timeout=15000)


def test_full_flow_in_ui(page, proj, studio):
    T = 40000
    # queue
    expect(page.locator(f"#card-{SKU}")).to_be_visible()
    expect(page.locator("#card-Mystery1_G_XYZ")).to_contain_text("Unknown jewelry type code")
    expect(page.locator("#start-Mystery1_G_XYZ")).to_have_count(0)
    page.click(f"#start-{SKU}")

    # 1 intake: prefilled from the catalog card, multi-select chips, no confirmation boxes
    expect(page.locator("#step-intake.current")).to_be_visible()
    expect(page.locator("#catalog-status")).to_have_text("Found")
    expect(page.locator("#catalog-chosen")).to_have_text("GodDaughter1_IC")
    expect(page.locator("#intake-source")).to_contain_text("GodDaughter1_IC")
    expect(page.locator("#ms-from .opt.on")).to_have_count(2)
    expect(page.locator("#ms-to .opt.on")).to_have_text(["✓ goddaughter"])
    assert page.locator("[id^=conf-]").count() == 0
    page.click("#ms-event .opt[data-v='Just because']")  # deselect -> no event
    page.wait_for_timeout(800)
    page.click("#btn-approve")
    expect(page.locator(".toast.error").last).to_contain_text("event")
    page.click("#ms-event-more")  # "+ more" reveals the full list
    page.click("#ms-event .opt[data-v='Baptism']")
    page.fill("#ms-event-add", "Godmother's day")
    page.press("#ms-event-add", "Enter")
    expect(page.locator("#ms-event .opt.on")).to_have_count(2)
    page.click("#ms-age_group .opt[data-v='teen']")
    page.click("#in-tone button[data-v='gentle']")
    expect(page.locator("#in-tone button.on")).to_have_text("Gentle")
    page.wait_for_timeout(900)
    approve(page, "intake")

    # 2 facts: suggested automatically from the photos
    expect(page.locator("#step-facts.current")).to_be_visible()
    expect(page.locator("#facts-text-InterlockingCircelsNecklace")).to_have_value(
        "# Interlocking circles necklace: facts\n\n## Materials & metals\n- 14K gold-filled or 925 sterling silver\n", timeout=T)
    approve(page, "facts")

    # 3 plan: hook cards, storyboard, slide inspector with live preview
    page.select_option("#plan-voice", "founder")
    page.click("#btn-gen-plan")
    expect(page.locator("#hook-0")).to_be_visible(timeout=T)
    expect(page.locator("#storyboard .sb:not(.add)")).to_have_count(7)
    expect(page.locator("#pv-1 iframe")).to_be_visible()
    page.click("#hook-card-2")
    expect(page.locator("#hook-card-2.sel")).to_be_visible()
    expect(page.locator("#sl-1-headline")).to_have_value(page.locator("#hook-2").input_value())
    page.wait_for_timeout(900)
    page.click("#sb-2")
    expect(page.locator("#sl-2-quote")).to_have_value("\u201cA quote on a black slide.\u201d")
    expect(page.locator("#slide-card-2")).to_contain_text("Black slide")
    # toggle the black slide to an image slide and back
    page.click("#kind-seg-2 button[data-v='image']")
    expect(page.locator("#sl-2-prompt")).to_be_visible()
    expect(page.locator("#refs-2 img")).to_have_count(1)
    expect(page.locator("#sl-2-layout")).to_have_value("overlay-bottom")
    page.click("#kind-seg-2 button[data-v='black']")
    expect(page.locator("#sl-2-prompt")).to_have_count(0)
    expect(page.locator("#sl-2-layout")).to_have_value("statement")
    # reference picker: a photo added to the style folder while the app runs appears after Refresh
    page.click("#sb-3")
    page.click("#btn-refs-3")
    expect(page.locator("#ref-picker .pick").first).to_be_visible()
    added = proj.photos / "InterlockingCircelsNecklace" / "Added today.png"
    placeholder_image(added, "added")
    rel = "RealProductPhotos/InterlockingCircelsNecklace/Added today.png"
    expect(page.locator(f"#ref-picker .pick[data-file='{rel}']")).to_have_count(0)
    page.click("#btn-refs-refresh")
    page.click(f"#ref-picker .pick[data-file='{rel}']")
    expect(page.locator(f"#ref-picker .pick.on[data-file='{rel}'] .ord")).to_be_visible()
    before = page.locator("#refs-3 img").count()
    page.click("#modal-ok")
    expect(page.locator("#refs-3 img")).to_have_count(before + 1)
    assert rel in studio.store.load(SKU)["plan"]["slides"][2]["references"]
    page.click("#sb-7")
    expect(page.locator("#slide-card-7")).to_be_visible()
    page.fill("#plan-caption", "Edited caption.\n\nShop through the link in bio.")
    expect(page.locator("#tag-check .badge")).to_contain_text("hashtags")
    expect(page.locator("#lint-check .statusrow.ok").first).to_be_visible()
    page.wait_for_timeout(900)  # autosave
    approve(page, "plan")

    # 4 images: storyboard shows status per slide
    expect(page.locator("#sb-7 .st.ok")).to_be_visible()  # autofilled from the library
    expect(page.locator("#sb-2 .st.none")).to_be_visible()  # black slide, no image needed
    page.evaluate("window.bellCount = 0; window.bell = () => { window.bellCount += 1; }; 0")
    page.click("#btn-gen-missing")
    for n in (1, 3, 4, 5, 6, 7):
        expect(page.locator(f"#sb-{n} .st.ok")).to_be_visible(timeout=T)
    page.wait_for_function("window.bellCount >= 1", timeout=T)  # the bell rings when all are generated
    page.wait_for_timeout(2500)
    assert page.evaluate("window.bellCount") == 1  # exactly once
    page.click("#sb-1")
    expect(page.locator("#imgrow-1 .msg.ok")).to_contain_text("QA: OK")
    page.click("#sb-2")
    expect(page.locator("#imgrow-2")).to_contain_text("Black slide")
    page.click("#sb-4")
    page.click("#black-4")  # on the Images stage too: make slide 4 black, then back with its image
    expect(page.locator("#sb-4 .st.none")).to_be_visible()
    page.click("#kind-seg-4 button[data-v='image']")
    expect(page.locator("#sb-4 .st.ok")).to_be_visible()
    approve(page, "images")

    # 5 slides
    page.click("#btn-render")
    for n in range(1, 8):
        expect(page.locator(f"#sb-{n} .mini img")).to_be_visible(timeout=60000)
        expect(page.locator(f"#sb-{n} .st.ok")).to_be_visible()
    page.click("#sb-2")
    page.fill("#st-2-headline", "A new *headline*")
    expect(page.locator("#slide-status")).to_have_text("Needs render")
    expect(page.locator("#sb-2 .st.warn")).to_be_visible()
    page.wait_for_timeout(900)
    page.click("#btn-approve")  # dirty -> refused
    expect(page.locator(".toast.error").last).to_contain_text("Render again")
    page.click("#btn-render")
    expect(page.locator("#sb-2 .st.ok")).to_be_visible(timeout=60000)
    approve(page, "slides")

    # 6 final
    expect(page.locator("#final-caption")).to_have_value("Edited caption.\n\nShop through the link in bio.")
    page.click("#btn-finalize")
    page.click("#modal-ok")
    expect(page.locator("#done-panel")).to_be_visible(timeout=T)
    assert not (proj.inputs / f"{SKU}.jpg").exists()
    outs = [p for p in proj.carousels.iterdir() if p.name != "_work"]
    assert len(outs) == 1 and (outs[0] / "bewished_slide_7.png").exists()
    page.click("#btn-next")
    expect(page.locator(f"#card-{SKU}")).to_have_count(0)


def test_other_views(page):
    page.click("#nav-library")
    expect(page.locator("#view")).to_contain_text("All styles (_Common)")
    page.click("#nav-settings")
    expect(page.locator("#btn-save-settings")).to_be_visible()
    page.click("#btn-test-bell")  # plays the bell (silent in headless Chrome); must not throw
    page.click("#btn-save-settings")
    expect(page.locator(".toast.ok")).to_contain_text("Settings saved")
    page.click("#nav-system")
    expect(page.locator("#view")).to_contain_text("Style folders", timeout=30000)
    page.click("#loghead")
    expect(page.locator("#logdrawer")).not_to_have_class("collapsed")


def test_discard_job(page, proj):
    page.click(f"#start-{SKU}")
    expect(page.locator("#btn-discard")).to_be_visible()
    page.click("#btn-discard")
    page.click("#modal-ok")
    expect(page.locator(f"#start-{SKU}")).to_have_text("Start carousel")
    assert (proj.inputs / f"{SKU}.jpg").exists()
