import pytest

from app.facts import COMMON, MARKER, facts_path, is_approved, read_facts, write_facts
from app.jobs import JobError, JobStore, approve, editable, mark_dirty, new_job, reopen, require_editable
from app.library import Library


# ---------------------------------------------------------------- facts
def test_common_default_draft(proj):
    f = read_facts(proj, COMMON)
    assert not f["exists"] and not f["approved"] and "14K" in f["text"]


def test_write_and_approve_facts(proj):
    write_facts(proj, "FloatingPearlNecklace", "# Pearl\n- white", False)
    assert not is_approved(proj, "FloatingPearlNecklace")
    write_facts(proj, "FloatingPearlNecklace", "# Pearl\n- white", True)
    raw = facts_path(proj, "FloatingPearlNecklace").read_text()
    assert raw.startswith(MARKER)
    f = read_facts(proj, "FloatingPearlNecklace")
    assert f["approved"] and f["text"].startswith("# Pearl")
    write_facts(proj, "FloatingPearlNecklace", f["text"], False)
    assert not is_approved(proj, "FloatingPearlNecklace")


# ---------------------------------------------------------------- jobs
def _job():
    return new_job("A1_G_IC", "DataFromUser/A1_G_IC.jpg", {"loss_hint": False})


def test_new_job_stages():
    j = _job()
    assert j["stages"]["intake"] == "open"
    assert all(j["stages"][s] == "locked" for s in ("facts", "plan", "images", "slides", "final"))
    assert new_job("A", "x", {"loss_hint": True})["intake"]["tone"] == "gentle"


def test_approve_reopen_stale():
    j = _job()
    for s in ("intake", "facts", "plan"):
        approve(j, s)
    assert j["stages"]["images"] == "open"
    reopen(j, "facts")
    assert j["stages"]["facts"] == "open"
    assert j["stages"]["plan"] == "stale"
    assert j["stages"]["intake"] == "approved"
    assert editable(j, "plan") and editable(j, "facts")
    with pytest.raises(JobError):
        require_editable(j, "intake")
    with pytest.raises(JobError):
        reopen(j, "images")  # open, not approved


def test_mark_dirty():
    j = _job()
    j["plan"]["slides"] = [{"n": 1}, {"n": 2}]
    mark_dirty(j, 2)
    assert set(j["render"]["dirty"]) == {"2"}
    mark_dirty(j)
    assert set(j["render"]["dirty"]) == {"1", "2"}


def test_store(proj):
    st = JobStore(proj)
    job = st.create("A1_G_IC", "DataFromUser/A1_G_IC.jpg", {"jewelry_type": "X"})
    assert st.exists("A1_G_IC")
    assert (proj.work / "A1_G_IC" / "raw").is_dir()
    assert st.create("A1_G_IC", "other", {})["input_file"] == job["input_file"]  # idempotent
    assert st.list()[0]["stage"] == "intake"
    st.delete("A1_G_IC")
    assert not st.exists("A1_G_IC")
    with pytest.raises(JobError):
        st.dir("../evil")
    with pytest.raises(JobError) as e:
        st.load("missing")
    assert e.value.status == 404


# ---------------------------------------------------------------- library
def test_library_variants_lru(proj):
    lib = Library(proj)
    src = proj.common / "Box2.png"
    v1 = lib.add_variant("InterlockingCircelsNecklace", "options", src, approved=True)
    v2 = lib.add_variant("InterlockingCircelsNecklace", "options", src, approved=True)
    v3 = lib.add_variant("InterlockingCircelsNecklace", "options", src, approved=False)
    assert [v1["variant"], v2["variant"], v3["variant"]] == ["v1.png", "v2.png", "v3.png"]
    usage = [{"style": "InterlockingCircelsNecklace", "slot": "options", "variant": "v1.png"}]
    assert lib.lru_pick("InterlockingCircelsNecklace", "options", usage)["variant"] == "v2.png"
    usage.append({"style": "InterlockingCircelsNecklace", "slot": "options", "variant": "v2.png"})
    assert lib.lru_pick("InterlockingCircelsNecklace", "options", usage)["variant"] == "v1.png"
    lib.set_approved("InterlockingCircelsNecklace", "options", "v3.png", True)
    assert lib.lru_pick("InterlockingCircelsNecklace", "options", usage)["variant"] == "v3.png"
    lib.remove("InterlockingCircelsNecklace", "options", "v3.png")
    assert len(lib.variants("InterlockingCircelsNecklace", "options")) == 2
    with pytest.raises(ValueError):
        lib.add_variant("X", "badslot", src)
    assert lib.lru_pick("X", "options", []) is None


def test_seed_common(proj):
    lib = Library(proj)
    lib.seed_common()
    lib.seed_common()  # idempotent
    v = lib.variants("_Common", "cta")
    assert len(v) == 1 and v[0]["approved"]
    assert lib.overview()[0]["style"] == "_Common"
