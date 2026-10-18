"""Brand content rules from doc/BRAND_CONTENT_SPEC.md that the app enforces or checks."""
from __future__ import annotations

import re

BRAND_TAGS = ["#bewished", "#bewishedgifts", "#morethanjewelry"]
MIN_SLIDES, MAX_SLIDES = 7, 10
MAX_CAPTION_EMOJI = 2

VOICES = {
    "giver": "Giver voice: the 'I' is the person giving the gift (grandma, mother of the bride, mother-in-law…), "
             "e.g. \"I gave it to her in the getting-ready room, before anyone else came in.\"",
    "founder": "Founder story: the shop owner tells a short personal moment the reader recognizes herself in, "
               "e.g. \"I still remember the necklace my grandmother gave me. I was twelve.\" Never invent sensitive "
               "facts about the owner (loss of a parent, illness, family details).",
    "brand": "Brand voice: Be Wished speaking ('we' / third person), e.g. \"So the words are already written for you.\"",
}

CAROUSEL_TYPES = {
    "story": ("Recipient / product story",
              "Hook on a photo → problem → personalization → options/engraving → materials → packaging + CTA"),
    "because": ("\"Because…\" reasons",
                "Question cover (e.g. 'Why she'll remember this gift') → one reason per slide, mostly black "
                "statement slides → closing statement + button"),
    "objection": ("Objection",
                  "Quote cover (e.g. 'For the woman who says \"I don't need anything.\"') → 3–4 black statement "
                  "slides building the argument → emotional photo + CTA"),
    "checklist": ("Checklist",
                  "Cover → one checklist slide per item (question + short answer, e.g. 'Personalized name?' / "
                  "'We write the poem. You add her name.') → 'That is a BeWished gift.' + button"),
    "guide": ("Gift guide by recipient",
              "Cover → one recipient per slide (eyebrow 'GRATITUDE + LOVE', title 'For Mom', gold subline, small "
              "grey note) → packaging CTA"),
    "educational": ("Educational list",
                    "Title (e.g. '3 signs it's time for a granddaughter gift') → one point per slide → 'Save this' closing"),
}

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF☀-⛿✀-✒✔-➿️]")
PRICE = re.compile(r"\$\s?\d|\bprice[sd]?\b|\bcheap\b|\bexpensive\b|\baffordable\b|\bcosts?\b|\bdiscount|\bsale\b|"
                   r"\d+\s?%\s?off|\bbudget\b", re.I)
BODY = re.compile(r"\b(her|your|his) size\b|\bdiet|\bweight\b|\bslim\b|\bskinny\b", re.I)


def with_brand_tags(tags: list[str]) -> list[str]:
    """Brand tags always last; other tags keep their order; total never above 30."""
    others = [t for t in tags if t not in BRAND_TAGS]
    return others[:30 - len(BRAND_TAGS)] + BRAND_TAGS


def count_emoji(text: str) -> int:
    return len(EMOJI.findall(text or ""))


def sentences(text: str) -> int:
    parts = [p for p in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if re.search(r"\w", p)]
    return len(parts)


def slide_texts(slide: dict) -> list[str]:
    return [slide.get(k, "") or "" for k in ("headline", "subtext", "quote", "eyebrow", "note", "script", "button")] \
        + list(slide.get("items") or [])


def lint_plan(plan: dict) -> dict:
    """Spec checks. Errors block approval; warnings need a confirmation."""
    errors, warnings = [], []
    slides = plan.get("slides") or []
    if not MIN_SLIDES <= len(slides) <= MAX_SLIDES:
        errors.append(f"A carousel has {MIN_SLIDES} to {MAX_SLIDES} slides (now {len(slides)}).")
    emoji_slides = [s["n"] for s in slides if any(count_emoji(t) for t in slide_texts(s))]
    if emoji_slides:
        errors.append(f"No emoji on slides (slide {', '.join(map(str, emoji_slides))}).")
    caption = plan.get("caption", "") or ""
    if count_emoji(caption) > MAX_CAPTION_EMOJI:
        warnings.append(f"The caption has {count_emoji(caption)} emoji; the spec allows at most {MAX_CAPTION_EMOJI}.")
    everything = " ".join([caption] + [t for s in slides for t in slide_texts(s)] + list(plan.get("hooks") or []))
    if PRICE.search(everything):
        warnings.append(f"Price wording found (\"{PRICE.search(everything).group(0)}\"). The spec says never mention price.")
    if BODY.search(everything):
        warnings.append(f"Body/size wording found (\"{BODY.search(everything).group(0)}\"). Avoid it.")
    hooks = plan.get("hooks") or [""]
    hook = hooks[plan.get("hook_choice", 0)] if 0 <= plan.get("hook_choice", 0) < len(hooks) else hooks[0]
    if hook and sentences(hook) > 2:
        warnings.append("The hook has more than 2 sentences.")
    if caption and not re.search(r"link in bio|save this", caption, re.I):
        warnings.append("The caption has no CTA (\"Save this…\" / \"…link in bio\").")
    return {"errors": errors, "warnings": warnings}
