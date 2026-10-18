import json

import pytest

from app.sku import SkuError, parse_sku
from app.styles import DEFAULT_TYPES, StyleTable, folder_status, load_table
from tests.conftest import golden_text

T = StyleTable(DEFAULT_TYPES)


@pytest.mark.parametrize("sku,jtype,extra", [
    ("Granddaughter4_G_COM033_Nm", "Engraved pendant necklace", {"metal": "Gold", "poem_base": "Granddaughter"}),
    ("Daughter10_S_WP", "Floating pearl necklace", {"metal": "Silver"}),
    ("BonusSon1_Cub_18", "Cuban link necklace", {"chain_length": "18", "men": True}),
    ("Confirmation5_CubTE_TRI019", "Triangle pendant necklace", {"engraving_style": "TRI019", "men": True}),
    ("AugustBday2_G_D8", "Drop birthstone necklace", {"birth_month": 8, "birth_month_name": "August"}),
    ("Fatherloss6_S(18)_ONY", "Gemstone necklace", {"metal": "Silver", "chain_length": "18", "loss_hint": True}),
    ("School9_R_STE001", "Star pendant necklace", {"metal": "Rose gold"}),
    ("GodDaughter1_G_IC", "Interlocking circles necklace", {"poem_words": "God Daughter"}),
    ("Sister25_G_D6", "Drop birthstone necklace", {"birth_month": 6}),
    ("X1_G_COM043", "Silver pendant necklace with engraved picture", {}),
    ("X1_G_COM012", "Engraved pendant necklace", {}),
    ("X1_G_SD12", "Drop birthstone necklace", {"birth_month": 12}),
    ("X1_G_S3", "Satellite and birthstone necklace", {"birth_month": 3}),
    ("X1_G_7", "Birthstone and circle necklace", {"birth_month": 7}),
    ("X1_G_SatP", "Satellite pearl necklace", {}),
    ("X1_G_SZ", "Satellite CZ diamond necklace", {}),
    ("X1_G_SHL", "Heart locket necklace", {}),
    ("X1_G_SHLE1-P2", "Heart locket necklace", {}),
    ("X1_G_LHL-P1", "Heart locket necklace", {}),
    ("X1_G_BR3", "Diamond tennis bracelet", {"kind": "bracelet"}),
    ("X1_G_BR", "2 hearts bracelet", {"kind": "bracelet"}),
    ("X1_G_BRM", "Men's/boys bracelet", {"men": True}),
    ("X1_G_BRME", "Men's/boys bracelet", {}),
    ("X1_G_SCP", "Small circle pearl necklace", {}),
    ("X1_G_CP", "Circle pearl necklace", {}),
    ("X1_G_ST", "Star pendant necklace", {}),
    ("X1_G_CR", "Cross pendant necklace", {}),
    ("X1_G_MUS", "Mustard seed necklace", {}),
    ("X1_G_RI", "Baroque pearl necklace", {}),
    ("X1_G_LV", "Lava stone necklace", {}),
    ("X1_G_CC", "Small and large circles necklace", {}),
    ("X1_G_TUR", "Gemstone necklace", {}),
    ("X1_G_PP", "Floating pearl necklace", {}),
    ("X1_G_DP", "Floating pearl necklace", {}),
    ("X1_G_TRI002", "Triangle pendant necklace", {"engraving_style": "TRI002"}),
])
def test_parse(sku, jtype, extra):
    info = parse_sku(sku, T)
    assert info.jewelry_type == jtype
    for k, v in extra.items():
        assert getattr(info, k) == v, k


@pytest.mark.parametrize("sku", ["Only_Two", "A_G_XYZ", "A_G_BR5", "A_G_D13", "A_G_D", "A_G_18", "A__IC", "A_G_sd1"])
def test_errors(sku):
    with pytest.raises(SkuError):
        parse_sku(sku, T)


def test_prefix_overlaps_are_exact():
    assert parse_sku("A_G_S1", T).jewelry_type != parse_sku("A_G_SD1", T).jewelry_type
    assert parse_sku("A_G_CP", T).jewelry_type != parse_sku("A_G_SCP", T).jewelry_type
    assert parse_sku("A_G_BR", T).jewelry_type != parse_sku("A_G_BR4", T).jewelry_type


def test_table_file_roundtrip(proj):
    table = load_table(proj)  # writes data/styles.json
    assert (proj.data / "styles.json").exists()
    assert len(table.types) == len(DEFAULT_TYPES)
    data = json.loads((proj.data / "styles.json").read_text())
    data["types"][0]["families"].append("NEWP")
    (proj.data / "styles.json").write_text(json.dumps(data))
    assert parse_sku("A_G_NEWP", load_table(proj)).jewelry_type == "Floating pearl necklace"


def test_folder_status(proj):
    t = load_table(proj)
    assert folder_status(proj, t.by_name("Interlocking circles necklace"))[0] == "ready"
    assert folder_status(proj, t.by_name("Engraved pendant necklace"))[0] == "empty"
    assert folder_status(proj, t.by_name("Cuban link necklace"))[0] == "no_folder"


def test_golden_parse_table():
    skus = ["Granddaughter4_G_COM033_Nm", "Daughter10_S_WP", "BonusSon1_Cub_18", "Confirmation5_CubTE_TRI019",
            "AugustBday2_G_D8", "Fatherloss6_S(18)_ONY", "School9_R_STE001", "Baptism1_R_PP", "Daughter10_R_PP",
            "GodDaughter1_G_IC", "Niece11_S_COM033", "Sister25_G_D6"]
    out = {s: parse_sku(s, T).to_dict() for s in skus}
    golden_text("sku_parse.json", json.dumps(out, indent=1, sort_keys=True) + "\n")
