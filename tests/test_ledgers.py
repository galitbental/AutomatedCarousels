from app.ledgers import Ledgers, normalize_hook, normalize_tag, overlap, parse_hashtags


def test_normalize_and_parse():
    assert normalize_tag("  #Gift Ideas ") == "#giftideas"
    assert normalize_tag("#") == ""
    assert parse_hashtags("#A #b, c;#A  d#e") == ["#a", "#b", "#c", "#d", "#e"]
    assert parse_hashtags(["#One", "two", "#one"]) == ["#one", "#two"]


def test_hook_normalization():
    assert normalize_hook("A gift, never JUST a gift!") == normalize_hook("a gift never just a gift")


def test_overlap():
    assert overlap({"#a", "#b"}, {"#a", "#b", "#c", "#d"}) == 1.0
    assert overlap(set(), {"#a"}) == 0.0


def test_check_range(proj):
    L = Ledgers(proj)
    assert L.check_hashtags(["#a", "#b"])["errors"]
    assert not L.check_hashtags(["#a", "#b", "#c"])["errors"]
    assert L.check_hashtags([f"#t{i}" for i in range(31)])["errors"]
    assert not L.check_hashtags([f"#t{i}" for i in range(30)])["errors"]


def test_duplicate_set_is_error_order_insensitive(proj):
    L = Ledgers(proj)
    L.add_hashtags(["#a", "#b", "#c", "#d"], "SKU1")
    res = L.check_hashtags("#D #c #b #a")
    assert any("Identical" in e for e in res["errors"])
    assert not res["warnings"]


def test_overlap_warning(proj):
    L = Ledgers(proj)
    L.add_hashtags(["#a", "#b", "#c", "#d", "#e"], "SKU1")
    res = L.check_hashtags(["#a", "#b", "#c", "#d", "#x"], threshold=0.7)
    assert not res["errors"] and res["warnings"]
    assert res["closest"]["sku"] == "SKU1"
    res = L.check_hashtags(["#a", "#x", "#y", "#z"], threshold=0.7)
    assert not res["warnings"]


def test_hooks_and_usage(proj):
    L = Ledgers(proj)
    assert L.hook_used("Never just a necklace") is None
    L.add_hook("Never just a necklace.", "S1")
    assert L.hook_used("never just a necklace")["sku"] == "S1"
    L.add_library_usage("Style", "options", "v1.png", "S1")
    assert L.library_usage()[0]["variant"] == "v1.png"
