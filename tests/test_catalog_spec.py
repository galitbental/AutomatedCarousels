from pathlib import Path

import pytest

from app.catalog import (Catalog, image_similarity, infer_events, infer_gender, parse_poem_text, split_values,
                         suggestions_from_card, variant_score)
from app.sku import parse_sku
from app.spec import BRAND_TAGS, count_emoji, lint_plan, sentences, with_brand_tags
from app.styles import DEFAULT_TYPES, StyleTable
from tests.make_demo import _img

T = StyleTable(DEFAULT_TYPES)


def info(sku):
    return parse_sku(sku, T).to_dict()


def jt(sku):
    return T.by_name(info(sku)["jewelry_type"])


# ---------------------------------------------------------------- parsing
def test_parse_plain_format():
    d = parse_poem_text("Header: To my Daughter\n\nBody: Line one\nLine two\n\nClosing: None\n\n"
                        "From: Mother, Sister\n\nTo: Daughter\n\nRelationCircle: 1\n")
    assert d["header"] == "To my Daughter" and d["body"] == "Line one\nLine two" and d["closing"] == ""
    assert d["from"] == ["mother", "sister"] and d["to"] == ["daughter"] and d["relation_circle"] == "1"


def test_parse_markdown_format_with_bullets():
    d = parse_poem_text("**Header:** Hi\n\n**Body:**\n\nPara 1\n\nPara 2\n\n**Closing:** Love you!\n\n"
                        "**From:**\n* Mother\n* Sister\n\n**To:**\n- Daughter\n")
    assert d["header"] == "Hi" and d["body"] == "Para 1\nPara 2" and d["closing"] == "Love you!"
    assert d["from"] == ["mother", "sister"] and d["to"] == ["daughter"]


def test_split_values():
    assert split_values("Aunt/Mother/Wife") == ["aunt", "mother", "wife"]
    assert split_values("Mom or Dad and Grandma") == ["mom", "dad", "grandma"]
    assert split_values("None") == []


def test_infer_events_gender():
    assert infer_events("Daughter10", "To my Daughter on your wedding day") == ["Wedding"]
    assert infer_events("1stGrade1", "Wishing you an amazing First day of 1st Grade") == ["First day of school"]
    assert infer_events("Fatherloss6", "") == ["Sympathy / memorial"]
    assert infer_events("Sister25", "My Sister My Friend") == ["Just because"]
    assert infer_gender(["son"]) == "male" and infer_gender(["daughter", "son"]) == "female"


def test_suggestions_header_wins_over_body():
    card = {"header": "My Sister My Friend", "body": "Thank you for being the best sister", "closing": "",
            "from": ["sister"], "to": ["sister"]}
    s = suggestions_from_card(card, info("Sister25_G_D6"))
    assert s["event"] == ["Just because"] and "Thank you / appreciation" in s["event_options"]
    assert s["from"] == ["sister"] and s["card_headline"] == "My Sister My Friend" and s["tone"] == "joyful"


def test_variant_score():
    assert variant_score("COM033", info("Niece11_S_COM033"), jt("Niece11_S_COM033")) == 3
    assert variant_score("COM009", info("Niece11_S_COM033"), jt("Niece11_S_COM033")) == 2  # same family
    assert variant_score("Pearl", info("Daughter10_R_PP"), jt("Daughter10_R_PP")) == 2
    assert variant_score("R(18)_PP", info("Daughter10_R_PP"), jt("Daughter10_R_PP")) == 3
    assert variant_score("Drop", info("Sister25_G_D6"), jt("Sister25_G_D6")) == 2
    assert variant_score("Cross", info("Sister25_G_D6"), jt("Sister25_G_D6")) == 0
    assert variant_score("", info("Sister25_G_D6"), jt("Sister25_G_D6")) == 1


# ---------------------------------------------------------------- matching
def test_find_steps(catalog_dir, proj):
    cat = Catalog(catalog_dir)
    # step 2: poem + variant (IC beats the generic card)
    m = cat.find(info("GodDaughter1_G_IC"), jt("GodDaughter1_G_IC"), None)
    assert m.status == "found" and m.method == "poem+variant" and m.chosen.key == "GodDaughter1_IC"
    assert {c["key"] for c in m.candidates} == {"GodDaughter1_IC", "GodDaughter1"}  # EXPLAIN image ignored
    # case-insensitive poem name; variant Drop chosen over COM009
    m = cat.find(info("sister25_G_D6"), jt("Sister25_G_D6"), None)
    assert m.chosen.key == "Sister25_Drop"
    assert cat.find(info("Nobody1_G_IC"), jt("Nobody1_G_IC"), None).status == "not_found"
    assert Catalog(catalog_dir / "missing").find(info("GodDaughter1_G_IC"), None, None).status == "unavailable"


def test_find_single_card_by_poem(tmp_path):
    _img(tmp_path / "Solo3_Pearl_MainImage.jpg", (1, 2, 3), "solo")
    m = Catalog(tmp_path).find(info("Solo3_G_IC"), jt("Solo3_G_IC"), None)
    assert m.status == "found" and m.method == "poem" and m.chosen.key == "Solo3_Pearl"


def test_find_by_image_comparison(tmp_path):
    _img(tmp_path / "Twin1_COM009_MainImage.jpg", (200, 30, 30), "a")
    _img(tmp_path / "Twin1_COM033_MainImage.jpg", (30, 30, 200), "b")
    photo = tmp_path / "photo.jpg"
    _img(photo, (30, 30, 205), "b")
    sku = info("Twin1_G_COM044")  # neither card is exact -> both family matches -> compare images
    m = Catalog(tmp_path).find(sku, jt("Twin1_G_COM044"), photo)
    assert m.method == "image" and m.chosen.key == "Twin1_COM033" and m.status == "found"
    assert m.candidates[0]["similarity"] > m.candidates[1]["similarity"]
    same = tmp_path / "same"
    same.mkdir()
    for k in ("Twin2_COM009", "Twin2_COM033"):
        _img(same / f"{k}_MainImage.jpg", (50, 50, 50), "x")
    m = Catalog(same).find(info("Twin2_G_COM044"), jt("Twin2_G_COM044"), photo)
    assert m.status == "ambiguous"


def test_image_similarity(tmp_path):
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _img(a, (10, 10, 10), "a")
    _img(b, (10, 10, 10), "a")
    _img(c, (250, 250, 250), "c")
    assert image_similarity(a, b) > image_similarity(a, c)


def test_index_cache_refresh(catalog_dir):
    cat = Catalog(catalog_dir)
    assert "goddaughter1" in cat.index()
    _img(catalog_dir / "New9_IC_MainImage.jpg", (5, 5, 5), "n")
    assert "new9" in cat.index(refresh=True)


# ---------------------------------------------------------------- spec
def test_brand_tags_always_last():
    assert with_brand_tags(["#bewished", "#a", "#b"]) == ["#a", "#b"] + BRAND_TAGS
    assert len(with_brand_tags([f"#t{i}" for i in range(40)])) == 30
    assert with_brand_tags([])[-3:] == BRAND_TAGS


def test_emoji_and_sentences():
    assert count_emoji("Hi 💛 there 🔖") == 2 and count_emoji("Checklist ✓ ok") == 0
    assert sentences("One. Two? Three!") == 3 and sentences("This made her cry… I gave it to her.") == 2


def _plan(**kw):
    slides = [{"n": i, "headline": "Clean", "subtext": "", "items": []} for i in range(1, 8)]
    base = {"slides": slides, "caption": "Hook 💛\n\nSave this for your next gift idea 🔖\nShop through the link in bio.",
            "hooks": ["Short hook.", "", ""], "hook_choice": 0}
    base.update(kw)
    return base


def test_lint_clean():
    assert lint_plan(_plan()) == {"errors": [], "warnings": []}


@pytest.mark.parametrize("change,kind,needle", [
    (dict(slides=[{"n": 1, "headline": "x"}] * 6), "errors", "7 to 10"),
    (dict(slides=[{"n": i, "headline": "x 💛" if i == 2 else "x"} for i in range(1, 8)]), "errors", "No emoji"),
    (dict(caption="a 💛 b 🔖 c 🎁 link in bio"), "warnings", "emoji"),
    (dict(caption="Affordable luxury. Shop through the link in bio."), "warnings", "price"),
    (dict(hooks=["One. Two. Three.", "", ""]), "warnings", "more than 2 sentences"),
    (dict(caption="No call to action here."), "warnings", "no CTA"),
    (dict(caption="Not just her size. Link in bio."), "warnings", "Body"),
])
def test_lint_rules(change, kind, needle):
    res = lint_plan(_plan(**change))
    assert any(needle.lower() in m.lower() for m in res[kind]), res
