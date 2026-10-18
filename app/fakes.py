"""Offline stand-ins for Claude and ChatGPT (tests and CAROUSEL_FAKE=1 demo mode)."""
from __future__ import annotations

import random
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageDraw


def placeholder_image(path: Path, label: str, size=(1024, 1280), seed: int = 0) -> Path:
    rng = random.Random(seed)
    img = Image.new("RGB", size, (20, 16, 12))
    d = ImageDraw.Draw(img)
    for y in range(size[1]):
        k = y / size[1]
        d.line([(0, y), (size[0], y)], fill=(int(40 + 60 * k), int(30 + 40 * k), int(20 + 20 * k)))
    for _ in range(40):
        x, y, r = rng.randint(0, size[0]), rng.randint(0, size[1]), rng.randint(8, 40)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(200, 160, 90))
    d.rectangle([size[0] // 4, size[1] // 3, 3 * size[0] // 4, 2 * size[1] // 3], outline=(226, 200, 135), width=8)
    d.text((size[0] // 4 + 20, size[1] // 3 + 20), label, fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


class FakeAssistant:
    """Returns realistic canned results instantly."""

    def __init__(self, fail: set[str] | None = None):
        self.fail = fail or set()
        self.calls: list[str] = []

    def _check(self, name):
        self.calls.append(name)
        if name in self.fail:
            from .llm import LLMError
            raise LLMError(f"fake failure in {name}")

    def read_card(self, job, **kw):
        self._check("read_card")
        return {"card_headline": "To my beloved Goddaughter", "card_text": "You are a treasure with a heart "
                "that is kind and true.", "signature": "Aunt Morgan - December 2025", "placeholder_name": "Emma",
                "to": ["goddaughter"], "from": ["aunt"], "giver_name": "Morgan", "event_stated": "",
                "suggested_events": ["Baptism", "Christmas", "Birthday", "Just because"], "tone": "joyful",
                "gender": "female", "age_group": ["adult"], "notes": "Event not stated on the card."}

    def draft_facts(self, jtype, files, **kw):
        self._check("draft_facts")
        return f"# {jtype.name}: facts\n\n## Materials & metals\n- 14K gold-filled or 925 sterling silver\n"

    def make_plan(self, prompt, **kw):
        self._check("make_plan")
        import re
        m = re.search(r"exactly (\d+) hashtags", prompt)
        n = max(0, (int(m.group(1)) if m else 12) - 3)  # the 3 brand tags are added by the app
        pool = ["#goddaughtergift", "#giftsforher", "#personalizedjewelry", "#handmadejewelry", "#heirloomgift",
                "#interlockingcircles", "#baptismgift", "#auntgift", "#poemcard", "#keepsakejewelry",
                "#meaningfulgifts", "#jewelrygift", "#goldfilled", "#sterlingsilver", "#giftideas",
                "#christmasgift", "#birthdaygift", "#godmother", "#shopsmall", "#giftforgoddaughter",
                "#necklacegift", "#customjewelry", "#giftsforgoddaughter", "#faithjewelry", "#forever",
                "#lovegift", "#jewelrylover", "#giftwrapped", "#boxedgift", "#readytogift"]
        rnd = random.Random(prompt)
        tags = rnd.sample(pool, min(n, len(pool)))
        slides = []
        for i, (layout, source) in enumerate([("hook", "generate"), ("statement", "none"),
                                              ("panel", "generate"), ("checklist", "generate"),
                                              ("panel", "library"), ("guide", "library"),
                                              ("cta", "common")], start=1):
            slides.append({"purpose": f"Slide {i}", "layout": layout, "source": source,
                           "slot": {5: "options", 6: "quality", 7: "cta"}.get(i, ""),
                           "prompt": "" if source == "none" else f"Fake prompt for slide {i}", "references": [],
                           "eyebrow": "Gratitude + love" if i == 6 else "", "note": "Small grey note" if i == 6 else "",
                           "quote": "\u201cA quote on a black slide.\u201d" if i == 2 else "",
                           "script": "Forever connected" if i == 5 else "",
                           "headline": "" if i == 3 else f"Headline {i} with *gold* words",
                           "subtext": "Line one\nLine *two*" if i in (2, 3, 5, 6, 7) else "",
                           "items": ["Personalize the poem", "Add your own words", "Choose the metal"] if i == 4 else [],
                           "button": "SHOP THE LINK IN BIO" if i == 7 else ""})
        return {"voice": "giver", "carousel_type": "story", "hooks": ["An aunt's love, worn every day", "Some bonds are chosen by heart",
                          "Two circles, one forever"], "slides": slides,
                "caption": "An aunt's love, worn every day.\n\nShop through the link in bio.", "hashtags": tags}

    def qa_image(self, image_rel, input_rel, card_text, slide, **kw):
        self._check("qa_image")
        return {"ok": True, "issues": [], "prompt_fix": ""}

    def chatgpt_generate(self, full_prompt, refs_abs, chat_url, chatgpt_url, **kw):
        self._check("chatgpt_generate")
        return {"status": "done", "chat_url": chat_url or "https://chatgpt.com/c/fake", "message": ""}


class FakeImageBackend:
    """Produces placeholder images instead of calling ChatGPT."""

    name = "fake"

    def __init__(self):
        self.count = 0
        self._dir = Path(tempfile.mkdtemp(prefix="fake_gen_"))

    def generate(self, job, slide, cancel: threading.Event | None = None, log=print):
        self.count += 1
        p = placeholder_image(self._dir / f"gen_{self.count}.png", f"slide {slide['n']}", seed=self.count)
        return p, job.get("chat_url") or "https://chatgpt.com/c/fake"
