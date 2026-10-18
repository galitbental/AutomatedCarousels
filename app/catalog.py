"""Poem-card catalog lookup (V:\\Amazon\\Catalog\\AllCatalog\\_ALL_SKU_POEM_CARDS).

Files come in pairs: <Poem>[_<Variant>]_MainImage.<jpg|png> and <Poem>[_<Variant>]_PoemText.txt.
Matching (owner's rules):
  1. poem name (first SKU field) == first field of the catalog file name (case-insensitive)
  2. still more than one -> the catalog file's second field (variant) must fit the SKU
  3. still more than one -> compare the card images with the input photo
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

from .styles import JewelryType

SUFFIX_IMG = re.compile(r"_MainImage\.(jpe?g|png|webp)$", re.I)
SUFFIX_TXT = re.compile(r"_PoemText\.txt$", re.I)
KEYS = {"header": "header", "body": "body", "closing": "closing", "from": "from", "to": "to",
        "relationcircle": "relation_circle", "relation circle": "relation_circle"}
KEY_LINE = re.compile(r"^\s*\**\s*(header|body|closing|from|to|relation ?circle)\s*:\s*\**\s*:?\s*(.*)$", re.I)

EVENT_RULES = [  # (pattern over poem name + header + body, event label)
    (r"wedding|bride|groom|aisle|bridal|marry|married", "Wedding"),
    (r"baptis|christening", "Baptism"),
    (r"confirmation", "Confirmation"),
    (r"communion", "Communion"),
    (r"graduat", "Graduation"),
    (r"first day|1st grade|2nd grade|3rd grade|\d+th grade|kindergarten|back to school|new school year", "First day of school"),
    (r"last day of school|end of (the )?school", "Last day of school"),
    (r"birthday|bday|sweet ?16|sweet sixteen|\b(16|18|21|30|40|50)th\b", "Birthday"),
    (r"christmas|xmas", "Christmas"),
    (r"mother'?s day", "Mother's Day"),
    (r"valentine", "Valentine's Day"),
    (r"bat ?mitzvah", "Bat Mitzvah"),
    (r"retire", "Retirement"),
    (r"loss|memorial|sympathy|heaven|in memory|passed away|grief|remembrance", "Sympathy / memorial"),
    (r"warrior|survivor|cancer|chemo|recovery|get well|hard time|hard season", "Encouragement"),
    (r"pregnan|mama to be|mom to be|new baby|baby shower|expecting", "Pregnancy / new baby"),
    (r"anniversary", "Anniversary"),
    (r"thank you|appreciation|teacher|nurse|boss|coworker|administrator", "Thank you / appreciation"),
]
MALE_WORDS = {"son", "grandson", "boy", "brother", "father", "dad", "husband", "nephew", "godson", "man", "him",
              "groom", "boyfriend", "stepson", "bonus son", "grandpa", "grandfather", "uncle", "papa"}
CHILD_WORDS = r"\bgrade\b|kindergarten|first day|little|baby|girl\b|flower girl|communion|baptism|christening"
TEEN_WORDS = r"sweet ?16|teen|confirmation|bat ?mitzvah|graduat|16th|18th"


@dataclass
class Entry:
    key: str            # file stem without the _MainImage / _PoemText suffix, e.g. "Sister25_Drop"
    poem: str           # first field
    variant: str        # rest after the first "_" ("" when none)
    image: Path | None = None
    text: Path | None = None


@dataclass
class Match:
    status: str                       # found | ambiguous | not_found | unavailable
    method: str = ""                  # poem | poem+variant | image
    chosen: Entry | None = None
    candidates: list[dict] = field(default_factory=list)
    message: str = ""


def split_values(v: str) -> list[str]:
    out = []
    for part in re.split(r"[/,;\n*•]|\bor\b|\band\b", v or ""):
        p = part.strip().strip(".-").strip()
        if p and p.lower() not in ("none", "n/a", "-"):
            out.append(p.lower())
    return list(dict.fromkeys(out))


def parse_poem_text(text: str) -> dict:
    """Parse 'Header: …' / '**Header:** …' files (values may span lines)."""
    vals: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        m = KEY_LINE.match(line)
        if m:
            cur = KEYS[m.group(1).lower()]
            vals.setdefault(cur, [])
            rest = m.group(2).strip().strip("*").strip()
            if rest:
                vals[cur].append(rest)
        elif cur and line.strip():
            vals[cur].append(re.sub(r"^\s*[*•-]\s+", "", line.strip()) if cur in ("from", "to") else line.strip())
    get = lambda k, sep="\n": sep.join(vals.get(k, [])).strip()  # noqa: E731
    people = lambda k: split_values("\n".join(vals.get(k, [])))  # noqa: E731
    closing = get("closing", " ")
    return {
        "header": get("header", " "),
        "body": get("body"),
        "closing": "" if closing.lower() in ("none", "") else closing,
        "from": people("from"),
        "to": people("to"),
        "relation_circle": get("relation_circle", " "),
    }


def infer_events(*texts: str) -> list[str]:
    blob = " ".join(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t or "") for t in texts).lower()
    found = [label for pat, label in EVENT_RULES if re.search(pat, blob)]
    return list(dict.fromkeys(found)) or ["Just because"]


def infer_age_groups(*texts: str) -> list[str]:
    blob = " ".join(texts).lower()
    groups = []
    if re.search(CHILD_WORDS, blob):
        groups.append("child")
    if re.search(TEEN_WORDS, blob):
        groups.append("teen")
    return groups or ["adult"]


def infer_gender(to_values: list[str]) -> str:
    return "male" if to_values and all(t.lower() in MALE_WORDS for t in to_values) else "female"


def _variant_tokens(variant: str) -> set[str]:
    toks = set()
    for t in variant.lower().split("_"):
        t = t.strip()
        if not t:
            continue
        toks |= {t, re.sub(r"\(\d+\)", "", t), re.sub(r"\d+$", "", re.sub(r"\(\d+\)", "", t))}
    toks.add(variant.lower())
    return {t for t in toks if t}


def variant_score(variant: str, sku_info: dict, jtype: JewelryType | None) -> int:
    """3 = exact SKU code, 2 = alias of the jewelry type, 1 = generic card (no variant), 0 = other product."""
    if not variant:
        return 1
    toks = _variant_tokens(variant)
    code = (sku_info.get("type_code") or "").lower()
    if code and code in toks:
        return 3
    aliases = {a.lower() for a in (jtype.catalog if jtype else [])}
    fam = (sku_info.get("family") or "").lower()
    if fam:
        aliases.add(fam)
    return 2 if toks & aliases else 0


def image_similarity(a: Path, b: Path) -> float:
    """0..1, higher is more similar (small grayscale + color thumbnails)."""
    def thumb(p):
        im = Image.open(p)
        im = ImageOps.exif_transpose(im).convert("RGB")
        return ImageOps.fit(im, (64, 64))
    ta, tb = thumb(a), thumb(b)
    diff = ImageStat.Stat(ImageChops.difference(ta, tb)).mean
    color = 1 - sum(diff) / (3 * 255)
    ga, gb = ImageOps.grayscale(ta), ImageOps.grayscale(tb)
    edges = 1 - ImageStat.Stat(ImageChops.difference(ga, gb)).mean[0] / 255
    return round(0.5 * color + 0.5 * edges, 4)


class Catalog:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._index: dict[str, list[Entry]] | None = None
        self._mtime = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        try:
            return self.folder.is_dir()
        except OSError:
            return False

    def index(self, refresh: bool = False) -> dict[str, list[Entry]]:
        with self._lock:
            try:
                mtime = self.folder.stat().st_mtime
            except OSError:
                return {}
            if self._index is not None and not refresh and mtime == self._mtime:
                return self._index
            entries: dict[str, Entry] = {}
            with os.scandir(self.folder) as it:  # scandir: no extra network round-trip per file
                names = [d.name for d in it if d.is_file()]
            for name in names:
                p = self.folder / name
                m = SUFFIX_IMG.search(name) or SUFFIX_TXT.search(name)
                if not m:
                    continue
                key = name[:m.start()]
                e = entries.setdefault(key.lower(), Entry(key=key, poem=key.split("_")[0],
                                                          variant="_".join(key.split("_")[1:])))
                if SUFFIX_IMG.search(name):
                    e.image = p
                else:
                    e.text = p
            by_poem: dict[str, list[Entry]] = {}
            for e in entries.values():
                by_poem.setdefault(e.poem.lower(), []).append(e)
            self._index, self._mtime = by_poem, mtime
            return by_poem

    def card(self, key: str) -> Entry | None:
        for entries in self.index().values():
            for e in entries:
                if e.key.lower() == key.lower():
                    return e
        return None

    def read(self, e: Entry) -> dict:
        data = parse_poem_text(e.text.read_text(encoding="utf-8", errors="replace")) if e.text else parse_poem_text("")
        data["key"] = e.key
        return data

    def find(self, sku_info: dict, jtype: JewelryType | None, input_image: Path | None) -> Match:
        if not self.available():
            return Match("unavailable", message=f"Catalog folder not reachable: {self.folder}")
        cands = list(self.index().get(sku_info["poem_name"].lower(), []))
        if not cands:
            return Match("not_found", message=f"No catalog card named '{sku_info['poem_name']}'.")

        def row(e, **extra):
            return {"key": e.key, "variant": e.variant, "image": e.image.name if e.image else "",
                    "has_text": bool(e.text), **extra}

        if len(cands) == 1:
            return Match("found", "poem", cands[0], [row(cands[0])])
        scored = [(variant_score(e.variant, sku_info, jtype), e) for e in cands]
        best = max(s for s, _ in scored)
        step2 = [e for s, e in scored if s == best]
        rows = [row(e, variant_score=s) for s, e in sorted(scored, key=lambda x: -x[0])]
        if len(step2) == 1:
            return Match("found", "poem+variant", step2[0], rows)
        if input_image and input_image.exists():
            sims = []
            for e in step2:
                sim = image_similarity(input_image, e.image) if e.image else 0.0
                sims.append((sim, e))
            sims.sort(key=lambda x: -x[0])
            sim_by_key = {e.key: s for s, e in sims}
            for r in rows:
                if r["key"] in sim_by_key:
                    r["similarity"] = sim_by_key[r["key"]]
            rows.sort(key=lambda r: (-(r.get("variant_score", 0)), -r.get("similarity", -1)))
            top, second = sims[0][0], (sims[1][0] if len(sims) > 1 else 0)
            status = "found" if top - second >= 0.03 else "ambiguous"
            return Match(status, "image", sims[0][1], rows,
                         "" if status == "found" else "Several cards look alike. Please confirm the right one.")
        return Match("ambiguous", "poem+variant", step2[0], rows, "Several cards match. Please choose one.")


def suggestions_from_card(card: dict, sku_info: dict) -> dict:
    """Intake suggestions from a parsed catalog card.

    The poem name and card header decide the defaults; the poem body only adds extra options.
    """
    strong = (sku_info.get("poem_name", ""), card.get("header", ""))
    strong_events = [e for e in infer_events(*strong) if e != "Just because"]
    body_events = [e for e in infer_events(card.get("body", "")) if e != "Just because"]
    events = strong_events or ["Just because"]
    age = [a for a in infer_age_groups(*strong) if a != "adult"]
    if not age:
        age = ["adult"] if (set(events) & {"Wedding", "Pregnancy / new baby", "Retirement", "Anniversary"}
                            or not re.search(CHILD_WORDS, card.get("body", "").lower())) else ["any"]
    to = card.get("to") or []
    return {
        "from": card.get("from") or [],
        "to": to,
        "event": events,
        "event_options": list(dict.fromkeys(events + body_events)),
        "age_group": age,
        "gender": infer_gender(to),
        "card_headline": card.get("header", ""),
        "card_text": card.get("body", ""),
        "signature": card.get("closing", ""),
        "tone": "gentle" if (sku_info.get("loss_hint") or "Sympathy / memorial" in events) else "joyful",
    }
