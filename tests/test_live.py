"""Live smoke tests with the real Claude CLI and real ChatGPT (opt-in: pytest -m live). They cost money.

They work on a temporary copy of the real sample photos; the real project folders are never modified.
"""
import shutil
import time
from pathlib import Path

import pytest
from PIL import Image

from app.paths import Project
from app.render import Renderer
from app.server import build_studio

pytestmark = pytest.mark.live
REAL = Path(__file__).resolve().parent.parent
SKU = "GodDaughter1_G_IC"
STYLE = "InterlockingCircelsNecklace"


@pytest.fixture
def live(tmp_path):
    src = REAL / "DataFromUser" / f"{SKU}.jpg"
    if not src.exists() or not (REAL / "RealProductPhotos" / STYLE).is_dir():
        pytest.skip("real sample photos not available")
    (tmp_path / "DataFromUser").mkdir()
    shutil.copy2(src, tmp_path / "DataFromUser" / src.name)
    for d in ("Common", STYLE):
        shutil.copytree(REAL / "RealProductPhotos" / d, tmp_path / "RealProductPhotos" / d)
    project = Project(tmp_path)
    studio = build_studio(project, fake=False, echo=True)
    studio.save_settings({"max_auto_retries": 0})
    return studio


def wait(studio, task, timeout=900):
    t = studio.tasks.wait(task.id, timeout)
    assert t.status == "done", f"{t.label}: {t.status} {t.error}"
    return t.result


def test_live_claude_pipeline(live):
    st = live
    st.start_job(SKU)
    res = wait(st, st.task_read_card(SKU))
    print("CARD:", res)
    assert "goddaughter" in " ".join(res["to"]).lower()
    assert "aunt" in " ".join(res["from"]).lower() or "morgan" in res["giver_name"].lower()
    st.patch_job(SKU, {"intake": {"event": ["Baptism"]}})
    st.approve(SKU, "intake")
    wait(st, st.task_draft_facts(STYLE, SKU))
    facts = st.get_facts(STYLE)["text"]
    print("FACTS:", facts)
    assert "14K" in facts or "gold" in facts.lower()
    st.approve(SKU, "facts")
    wait(st, st.task_plan(SKU, "all"))
    plan = st.store.load(SKU)["plan"]
    print("HOOKS:", plan["hooks"])
    print("CAPTION:", plan["caption"])
    print("TAGS:", len(plan["hashtags"]), plan["hashtags"], "target", plan["hashtag_target"])
    assert 7 <= len(plan["slides"]) <= 10 and all(plan["hooks"])
    assert plan["hashtags"][-3:] == ["#bewished", "#bewishedgifts", "#morethanjewelry"]
    print("VOICE/TYPE:", plan["voice"], plan["carousel_type"])
    for s in plan["slides"]:
        print(" ", s["n"], s["layout"], s["source"], "|", s["headline"], "|", s["subtext"].replace("\n", " / "))
    from app.spec import lint_plan
    print("LINT:", lint_plan(plan))
    assert 3 <= len(plan["hashtags"]) <= 30
    assert abs(len(plan["hashtags"]) - plan["hashtag_target"]) <= 2


def test_live_chatgpt_image(live):
    st = live
    st.start_job(SKU)
    st.patch_job(SKU, {"intake": {"from": ["aunt"], "to": ["goddaughter"], "event": ["Baptism"]}})
    st.approve(SKU, "intake")
    st.put_facts(STYLE, "# IC\n- 14K gold-filled or sterling silver", True)
    st.put_facts("_Common", "# Common\n- Handmade", True)
    st.approve(SKU, "facts", force=True)
    st.baseline_plan(SKU)
    st.patch_job(SKU, {"plan": {"hashtags": f"#live{int(time.time())} #goddaughtergift #bewished"}})
    st.approve(SKU, "plan", force=True)
    started = time.time()
    version = wait(st, st.task_generate_image(SKU, 1), timeout=900)
    print("IMAGE:", version, f"{time.time() - started:.0f}s")
    path = st.project.abs(version["file"])
    im = Image.open(path)
    assert im.size[0] >= 512
    job = st.store.load(SKU)
    assert job["chat_url"].startswith("https://chatgpt.com/")
    print("QA:", version.get("qa") or job["images"]["1"]["versions"][-1].get("qa"))
    # render that one slide with the real image
    job["plan"]["slides"] = job["plan"]["slides"][:1]
    files = Renderer(st.project).render_job(job)
    shutil.copy2(st.project.abs(files["1"]), REAL / "doc" / "live_test_slide_1.png")
