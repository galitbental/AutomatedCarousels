"""SKU parsing (DESIGN §4)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .styles import BIRTH_MONTHS, StyleTable

METALS = {"G": "Gold", "R": "Rose gold", "S": "Silver"}
LOSS_WORDS = ("loss", "memorial", "sympathy", "remembrance", "condolence", "bereavement",
              "grief", "heaven", "inmemory", "passing")


class SkuError(ValueError):
    """The SKU cannot be mapped to a jewelry type."""


@dataclass
class SkuInfo:
    sku: str
    poem_name: str
    poem_base: str
    poem_words: str
    poem_number: str
    metal_raw: str
    metal: str
    type_code: str
    family: str
    jewelry_type: str
    style_folder: str
    men: bool
    kind: str
    birth_month: int | None = None
    birth_month_name: str | None = None
    birth_color: str | None = None
    chain_length: str | None = None
    engraving_style: str | None = None
    loss_hint: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _split_words(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def parse_sku(sku: str, table: StyleTable) -> SkuInfo:
    fields = sku.split("_")
    if len(fields) < 3 or not all(fields[:3]):
        raise SkuError(f"SKU '{sku}' needs at least 3 fields separated by '_'")
    poem, f2, f3 = fields[0], fields[1], fields[2]

    m = re.match(r"^(.*?)(\d*)$", poem)
    poem_base, poem_number = m.group(1), m.group(2)

    chain_length = engraving = None
    family = ""
    if f2 in table.special:
        jtype = table.special[f2]
        type_code = f2
        family = f2
        if f2 == "Cub":
            chain_length = f3
        else:
            engraving = f3
        metal_raw = ""
    else:
        type_code = f3
        metal_raw = f2
        jtype = table.exact.get(type_code)
        if jtype:
            family = type_code
        else:
            base = re.sub(r"-P\d+$", "", type_code)
            jtype = table.exact.get(base)
            family = base
            if not jtype:
                family = re.sub(r"\d+$", "", base)
                jtype = table.families.get(family) if family else None
        if not jtype:
            raise SkuError(f"Unknown jewelry type code '{type_code}' in SKU '{sku}'")
        if jtype.special and f2 != jtype.special:
            engraving = type_code  # e.g. a standalone TRI### code

    metal = METALS.get(metal_raw[:1], "Unknown") if metal_raw else "Unknown"
    m_len = re.search(r"\((\d+)\)", metal_raw)
    if m_len and not chain_length:
        chain_length = m_len.group(1)

    birth_month = birth_name = birth_color = None
    if jtype.birthstone:
        digits = re.search(r"(\d+)$", re.sub(r"-P\d+$", "", type_code))
        if not digits or not 1 <= int(digits.group(1)) <= 12:
            raise SkuError(f"Birthstone code '{type_code}' must end with a month number 1-12")
        birth_month = int(digits.group(1))
        birth_name, birth_color = BIRTH_MONTHS[birth_month]

    poem_lower = poem.lower()
    return SkuInfo(
        sku=sku, poem_name=poem, poem_base=poem_base, poem_words=_split_words(poem_base),
        poem_number=poem_number, metal_raw=metal_raw, metal=metal, type_code=type_code,
        family=family, jewelry_type=jtype.name, style_folder=jtype.folder, men=jtype.men,
        kind=jtype.kind, birth_month=birth_month, birth_month_name=birth_name,
        birth_color=birth_color, chain_length=chain_length, engraving_style=engraving,
        loss_hint=any(w in poem_lower for w in LOSS_WORDS),
    )
