"""Slide baseline, Claude prompts and JSON schemas (copy rules: doc/BRAND_CONTENT_SPEC.md)."""
from __future__ import annotations

import json

from .jobs import as_list, joined
from .paths import Project, list_images
from .spec import BRAND_TAGS, CAROUSEL_TYPES, MAX_SLIDES, MIN_SLIDES, VOICES, with_brand_tags
from .styles import JewelryType

LAYOUTS = ["hook", "statement", "overlay-top", "overlay-bottom", "panel", "checklist", "guide", "list", "cta",
           "framed"]
SOURCES = ["generate", "library", "common", "input", "none"]
EVENTS = ["Birthday", "Christmas", "Mother's Day", "Graduation", "First day of school",
          "Last day of school", "Valentine's Day", "Confirmation", "Communion", "Bat Mitzvah",
          "Wedding", "Baptism", "Anniversary", "Pregnancy / new baby", "Retirement",
          "Thank you / appreciation", "Encouragement", "Sympathy / memorial", "Just because"]
AGE_GROUPS = ["child", "teen", "adult", "any"]
RELATIONS = ["mom", "dad", "grandma", "grandpa", "aunt", "uncle", "godmother", "godfather", "sister", "brother",
             "friend", "best friend", "daughter", "son", "granddaughter", "grandson", "niece", "nephew",
             "goddaughter", "godson", "wife", "husband", "mother-in-law", "daughter-in-law", "bride", "groom",
             "mother of the bride", "mother of the groom", "teacher", "coworker"]
TEXT_HEAVY = ("quality", "info", "text", "length", "choice", "option", "comparison", "chain", "lengths")

SPEC_RULES = """BRAND RULES (Be Wished content spec — follow strictly)
Positioning: "A meaningful gift that already comes with the words you wanted to say." We sell emotion +
personalization + ready-to-gift convenience, not "a necklace with a box". Mood: luxurious, elegant, timeless,
personalized. Brand lines you may use: More than jewelry · Wear what matters.
Style:
- SHORT. People don't like reading much. One idea per slide, max ~20 words per slide.
- Positive framing, not negative. Soften certainty ("She might not remember the toast. She will keep this.").
- Tone: luxurious, quality, emotional, unique, light and pleasant.
- Core words: quality, personalized, ready-to-gift, heartfelt, keepsake. Supporting: elevated, timeless,
  effortless, cherished, curated, intentional.
- Include the symbolic anchor that links the jewelry to the emotion (given below).
- NEVER mention price (no "expensive", "affordable", "cost"). No body/size wording. No fabricated customer
  stories or testimonials. Only the approved product facts below.
- Loss / illness / sympathy: gentle and comforting, never celebratory, no medical claims.
- No emoji on slides. Caption: at most 2 emoji (💛 after the hook line, 🔖 next to "Save this").
Hooks — alternate two types: [statement] short dramatic ("You have one morning to say eighteen years.") and
[question] direct ("What do you give the woman who is about to become your daughter?"). Approved patterns:
giver memory ("This made her cry… I gave it to my daughter just before the ceremony."), quote ("We both love the
same man."), objection ("For the woman who says 'I don't need anything.'"), buyer's struggle ("When you want to say
something meaningful, but don't know how."), symbolic ("A pearl takes years to become one of a kind. So does she.").
Max 2 sentences.
Copy logic: Hook → Problem (short, sharp) → Solution (the jewelry + poem card with her name and the giver's own
closing line + Sterling Silver or 14K Gold Filled + ready to gift) → CTA.
CTAs (alternate selling / inviting): Save this for your next gift idea · Shop through the link in bio ·
Which message would you choose? · Make her feel like family. Link in bio · Send love in a box.
Approved slide copy examples: "Because it carries her name, she knows it was made just for her." ·
"So the words are already written for you." · "Add her name — and your own closing line." ·
"We write the poem. You add her name." · "The poem is written. The last line is yours." ·
"Give her something she will *feel*."
"""

CAPTION_TEMPLATE = """Caption template:
<hook line> 💛
<blank line>
<2–3 very short paragraphs, ~55 characters per line: problem → what the gift is → the personalization>
<blank line>
<product facts: Sterling Silver or 14K Gold Filled, ready to gift>
<blank line>
Save this for your next gift idea 🔖
Shop through the link in bio.
(No hashtags inside the caption.)"""

LAYOUT_GUIDE = """Slide layouts (1080x1350):
- hook: cover photo, headline (the hook) + optional eyebrow (tiny uppercase label) — slide 1.
- statement: pure black slide, gold rule + headline (*gold* accent words) + optional subtext or quote. source "none".
- overlay-top / overlay-bottom: text on the photo (only when that part of the photo is dark and empty).
- panel: photo on top, black panel below with headline + gold subtext (+ optional small grey note).
- checklist: like panel, with a gold check icon before the headline (a question, e.g. "Personalized name?").
- guide: like panel, with eyebrow ("GRATITUDE + LOVE"), title ("For Mom"), gold subtext, grey note.
- list: photo on top, numbered items below.
- cta: closing slide, headline + subtext + gold button (button text uppercase, e.g. "SHOP THROUGH THE LINK IN BIO").
- framed: the input photo framed on a dark background.
Optional on photo layouts: "script" = 2–3 words in elegant handwriting over the photo (e.g. "Forever connected").
Image sources: generate (ChatGPT, per carousel), library (reusable style image, slot options/quality),
common (packaging/CTA image, slot cta), input (the product photo itself), none (black slide, no image)."""


def pronouns(intake: dict) -> dict:
    if intake.get("gender") == "male":
        return {"sub": "he", "obj": "him", "pos": "his"}
    return {"sub": "she", "obj": "her", "pos": "her"}


def style_refs(project: Project, jtype: JewelryType, n: int = 3) -> list[str]:
    """Up to n style photos, preferring on-model photos over text-heavy infographics."""
    photos = list_images(project.photos / jtype.folder)
    clean = [p for p in photos if not any(w in p.stem.lower() for w in TEXT_HEAVY)]
    ordered = clean + [p for p in photos if p not in clean]
    return [project.rel(p) for p in ordered[:n]]


def common_ref(project: Project, name: str) -> list[str]:
    p = project.common / name
    return [project.rel(p)] if p.exists() else []


def available_references(project: Project, jtype: JewelryType) -> list[str]:
    return ([project.rel(p) for p in list_images(project.photos / jtype.folder)]
            + [project.rel(p) for p in list_images(project.common)])


def _slide(n, purpose, layout, source, prompt, refs, headline="", subtext="", items=None, button="",
           slot=None, text_pos=None, eyebrow="", note="", quote="", script="") -> dict:
    return {"n": n, "purpose": purpose, "layout": layout, "source": source, "slot": slot,
            "prompt": prompt, "references": refs, "headline": headline, "subtext": subtext,
            "items": items or [], "button": button, "eyebrow": eyebrow, "note": note, "quote": quote,
            "script": script, "text_pos": text_pos or ("bottom" if layout in ("overlay-bottom", "hook") else "top"),
            "shade": 0.55}


NAME_LIKE = {"mom", "mum", "mommy", "mama", "dad", "daddy", "papa", "grandma", "grandpa", "nana", "granny",
             "grandmother", "grandfather", "mother", "father"}


def giver_phrase(intake: dict) -> str:
    """'Grandma' / 'her aunt': reads naturally in 'A necklace from ___'."""
    givers = as_list(intake.get("from"))
    g = givers[0] if givers else ""
    if not g:
        return "someone who loves " + pronouns(intake)["obj"]
    if g.lower() in NAME_LIKE:
        return g[:1].upper() + g[1:]
    return f"{pronouns(intake)['pos']} {g}"


def baseline_slides(project: Project, job: dict, jtype: JewelryType) -> list[dict]:
    """Recipient-story baseline (spec §5), 7 slides, pre-filled with generic premium copy."""
    it = job["intake"]
    pr = pronouns(it)
    giver = (as_list(it.get("from")) or ["the giver"])[0]
    to = (as_list(it.get("to")) or ["the recipient"])[0]
    age = (as_list(it.get("age_group")) or ["adult"])[0]
    item = jtype.name.lower()
    inp = job["input_file"]
    gentle = it.get("tone") == "gentle"
    mood = ("quiet, comforting embrace, soft window light, peaceful and tender, eyes gently closed"
            if gentle else "joyful embrace, genuine happy smiles, warm and loving")
    refs_style = style_refs(project, jtype)
    return [
        _slide(1, "Hook: cover", "hook", "generate",
               f"Luxury still life: the poem card with the {item} exactly as in the first reference photo, "
               f"displayed in the open BLACK Be Wished gift box, with the black Be Wished lid with gold logo "
               f"leaning beside it, on a dark marble table with candles, baby's breath and gold ribbon. "
               f"Keep the lower third of the frame dark and calm for a headline.",
               [inp] + common_ref(project, "Box2.png") + common_ref(project, "BoxExample1.png"),
               headline=f"A {jtype.kind} from {giver_phrase(it)} is never just a {jtype.kind}"),
        _slide(2, "Problem", "statement", "none", "", [],
               headline=f"Finding the right words for {pr['obj']} is *the hard part*.",
               subtext="You know what you feel.\nSaying it is another thing."),
        _slide(3, "Emotion: giver + recipient", "panel", "generate",
               f"Portrait of a {giver} and {pr['pos']} {to} ({age}), {mood}. The {to} is wearing the {item} "
               f"from the reference photo, clearly visible. Dark warm background with gold bokeh and candles.",
               [inp] + refs_style[:1] + common_ref(project, "BoxExample1.png"),
               headline="You want it to say *exactly* what is in your heart."),
        _slide(4, "Personalization", "panel", "generate",
               f"Close-up of a woman's hands gently holding the open gift box with the poem card and the "
               f"{item} exactly as in the first reference photo, soft cream knit sweater, soft neutral "
               f"background. The box may be grey (no lid visible).",
               [inp] + common_ref(project, "BoxExample3.png"),
               headline="So the words are *already written* for you.",
               subtext=f"Add {pr['pos']} name and your own closing line."),
        _slide(5, "Style options", "panel", "library",
               f"Elegant product display of the {item} options: {jtype.options}. Dark velvet jewelry "
               f"stands on black marble, warm gold bokeh, baby's breath.", refs_style, slot="options",
               headline=f"One of a kind, *just for {pr['obj']}*.", subtext=jtype.options),
        _slide(6, "Quality", "panel", "library",
               f"Three versions of the {item} (rose gold, yellow gold, silver) side by side on a dark velvet "
               f"jewelry display, dark warm background with soft gold bokeh.", refs_style, slot="quality",
               headline="Sterling Silver or 14K Gold Filled.", subtext="*Handmade. Ready to gift.*"),
        _slide(7, "Trust & CTA", "cta", "common",
               "Be Wished black gift box in a white organza bag on dark marble, gold bokeh, "
               "Be Wished gold logo above. Leave the lower third calm for text.",
               common_ref(project, "Box.png") + common_ref(project, "Box2.png"), slot="cta",
               headline="Ready to gift the moment it arrives.",
               button="SHOP THROUGH THE LINK IN BIO"),
    ]


def default_image_prompt(jtype: JewelryType, slide: dict) -> str:
    """Starting prompt when a black slide is switched to an image slide (the user edits it)."""
    calm = "upper" if slide.get("text_pos") == "top" else "lower"
    return (f"Luxury still life for the slide '{slide.get('purpose', '')}': the poem card with the "
            f"{jtype.name.lower()} exactly as in the first reference photo, in the open BLACK Be Wished gift box "
            f"on a dark marble table with candles, baby's breath and gold ribbon. "
            f"Keep the {calm} third of the frame dark and calm for the text.")

# ---------------------------------------------------------------- card reading (fallback when no catalog card)
CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "card_headline": {"type": "string"},
        "card_text": {"type": "string"},
        "signature": {"type": "string"},
        "placeholder_name": {"type": "string"},
        "to": {"type": "array", "items": {"type": "string"}},
        "from": {"type": "array", "items": {"type": "string"}},
        "giver_name": {"type": "string"},
        "event_stated": {"type": "string"},
        "suggested_events": {"type": "array", "items": {"type": "string"}},
        "tone": {"type": "string", "enum": ["joyful", "gentle"]},
        "gender": {"type": "string", "enum": ["female", "male"]},
        "age_group": {"type": "array", "items": {"type": "string", "enum": AGE_GROUPS}},
        "notes": {"type": "string"},
    },
    "required": ["card_headline", "card_text", "signature", "placeholder_name", "to", "from", "giver_name",
                 "event_stated", "suggested_events", "tone", "gender", "age_group", "notes"],
}


def card_prompt(job: dict) -> str:
    info = job["sku_info"]
    return f"""You help the jewelry gift shop "Be Wished" prepare an Instagram carousel.
Use the Read tool to look at the product photo: {job['input_file']}
It shows a personalized poem card with a piece of jewelry in a gift box.
SKU: {info['sku']} | jewelry type: {info['jewelry_type']} | poem name hint: {info['poem_words']}

Return:
- card_headline: the card's heading exactly (e.g. "To my beloved Goddaughter").
- card_text: the full poem text exactly as printed, line breaks as on the card.
- signature: the closing/signature line(s) exactly (e.g. "Aunt Morgan - December 2025").
- placeholder_name: the sample recipient name printed on the card (e.g. Emma); it is a placeholder, not a real person.
- to: possible recipient relations in lowercase (e.g. ["goddaughter"]).
- from: possible giver relations in lowercase, deduced from the signature/poem (e.g. "Aunt Morgan" -> ["aunt"]).
- giver_name: a name in the signature if any (e.g. "Morgan"), else empty.
- event_stated: the occasion only if the card states it (e.g. "wedding"), else empty.
- suggested_events: 4 likely occasions for this relationship and poem, most likely first.
- tone: "gentle" for loss, memorial or sympathy poems, else "joyful".
- gender: recipient gender. age_group: likely recipient age groups (child, teen, adult, any).
- notes: anything uncertain the user should check (short)."""


# ---------------------------------------------------------------- facts
FACTS_SCHEMA = {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]}


def facts_prompt(jtype: JewelryType, files: list[str]) -> str:
    listing = "\n".join(f"- {f}" for f in files)
    return f"""You prepare a product facts sheet for the jewelry shop "Be Wished", jewelry type: {jtype.name}.
Use the Read tool to look at EVERY image below (product photos and store infographics):
{listing}

Write a concise markdown facts sheet with these sections (omit a section if nothing is shown):
# {jtype.name}: facts
## Product
## Materials & metals
## Options & customization
## Sizes & lengths
## Quality claims
## Do not claim
Rules: include ONLY facts that are visible/stated in the images. Never invent claims. Never include prices.
Mark anything ambiguous with "(verify)". Fix obvious typos from infographics. Use short bullet points.
Return the markdown in the "markdown" field."""


# ---------------------------------------------------------------- plan
_SLIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose": {"type": "string"},
        "layout": {"type": "string", "enum": LAYOUTS},
        "source": {"type": "string", "enum": SOURCES},
        "slot": {"type": "string"},
        "prompt": {"type": "string"},
        "references": {"type": "array", "items": {"type": "string"}},
        "eyebrow": {"type": "string"},
        "headline": {"type": "string"},
        "subtext": {"type": "string"},
        "quote": {"type": "string"},
        "note": {"type": "string"},
        "script": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "button": {"type": "string"},
    },
    "required": ["purpose", "layout", "source", "prompt", "references", "headline", "subtext", "items", "button"],
}
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "voice": {"type": "string", "enum": list(VOICES)},
        "carousel_type": {"type": "string", "enum": list(CAROUSEL_TYPES)},
        "hooks": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "slides": {"type": "array", "items": _SLIDE_SCHEMA, "minItems": MIN_SLIDES, "maxItems": MAX_SLIDES},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["voice", "carousel_type", "hooks", "slides", "caption", "hashtags"],
}


def plan_prompt(job: dict, jtype: JewelryType, facts_style: str, facts_common: str, baseline: list[dict],
                used_hooks: list[str], recent_tag_sets: list[list[str]], target_tags: int,
                references: list[str], voice: str = "", carousel_type: str = "",
                recent_posts: list[dict] | None = None) -> str:
    it = job["intake"]
    info = job["sku_info"]
    pr = pronouns(it)
    base = json.dumps([{k: s.get(k) for k in ("purpose", "layout", "source", "slot", "prompt", "references",
                                              "headline", "subtext", "items", "button")} for s in baseline],
                      indent=1, ensure_ascii=False)
    birth = (f"Birth month: {info['birth_month_name']} ({info['birth_color']} stone).\n"
             if info.get("birth_month") else "")
    hooks = "\n".join(f"- {h}" for h in used_hooks[-60:]) or "- (none yet)"
    tags = "\n".join("- " + " ".join(t) for t in recent_tag_sets[-10:]) or "- (none yet)"
    refs = "\n".join(f"- {r}" for r in references)
    recent = recent_posts or []
    last = recent[-1] if recent else {}
    voice_rule = (f"Use the {voice} voice." if voice else
                  "Choose the voice yourself; it MUST differ from the previous carousel's voice"
                  + (f" ({last.get('voice')})." if last.get("voice") else "."))
    type_rule = (f"Carousel type: {carousel_type} — {CAROUSEL_TYPES[carousel_type][1]}." if carousel_type else
                 "Choose the best carousel type for this product and occasion; prefer one not used in the last "
                 "carousels" + (f" ({', '.join(p.get('carousel_type', '') for p in recent[-3:])})." if recent else "."))
    voices = "\n".join(f"- {k}: {v}" for k, v in VOICES.items())
    types = "\n".join(f"- {k}: {name} — {desc}" for k, (name, desc) in CAROUSEL_TYPES.items())
    return f"""You are the copywriter and art director for "Be Wished", a premium handmade & personalized
jewelry gift shop. Plan one Instagram carousel ({MIN_SLIDES} to {MAX_SLIDES} slides, 4:5).

PRODUCT: {info['jewelry_type']} (SKU {info['sku']}), metal in photo: {info['metal']}. {birth}
Symbolic anchor for this jewelry: {jtype.anchor or '(write one that links the jewelry to the emotion)'}
GIFT: from {joined(it.get('from'))}{(' (' + it['giver_name'] + ')') if it.get('giver_name') else ''}
to {joined(it.get('to'))} ({it.get('gender')}, age: {joined(it.get('age_group'))}).
Occasion(s): {joined(it.get('event'))}. Tone: {it.get('tone')}.
Pronouns for the recipient: {pr['sub']}/{pr['obj']}/{pr['pos']}.
Poem card headline: {it.get('card_headline', '')}
Poem card text: {it.get('card_text', '')}
User notes: {it.get('notes', '')}

APPROVED FACTS (the only product claims you may use):
{facts_style}

{facts_common}

{SPEC_RULES}
VOICES:
{voices}
{voice_rule}

CAROUSEL TYPES:
{types}
{type_rule}

{LAYOUT_GUIDE}

BASELINE (recipient-story example; adapt or restructure for the chosen type; keep slides 5–7 sources/slots
when they fit):
{base}

OUTPUT RULES
- voice and carousel_type: the ones you used.
- hooks: 3 NEW hooks for slide 1 in the chosen voice, clearly different from each other (mix statement and
  question types). Do not copy the examples and do not reuse or closely paraphrase these used hooks:
{hooks}
- slide 1 headline = the first hook. Use *asterisks* around 1–4 words to make them gold. Use \\n for line breaks.
- Image prompts (source generate/library/common): photorealistic scene for ChatGPT; never ask for text in the
  image; black Be Wished box with gold logo whenever the lid/closed box is visible; the poem card stays exactly
  as in the input photo; recipient wears the jewelry in emotional scenes; for text-on-photo layouts keep that part
  of the image dark and empty. Statement slides use source "none" and an empty prompt.
- references: choose from this list only (the input photo is {job['input_file']}):
{refs}
- caption: follow the template.
{CAPTION_TEMPLATE}
- hashtags: exactly {target_tags} hashtags in total, English, relevant (recipient, giver, occasion, jewelry type,
  gift ideas), ENDING with the 3 brand tags {' '.join(BRAND_TAGS)}. The set must differ from these recent sets:
{tags}
"""


def sanitize_plan(raw: dict, project: Project, baseline: list[dict], target_tags: int | None = None) -> dict:
    """Coerce Claude's plan into the job plan shape; fills gaps from the baseline."""
    from .ledgers import parse_hashtags

    hooks = [h.strip() for h in (raw.get("hooks") or []) if isinstance(h, str) and h.strip()][:3]
    while len(hooks) < 3:
        hooks.append(baseline[0]["headline"] if not hooks else "")
    slides = []
    for i, s in enumerate((raw.get("slides") or baseline)[:MAX_SLIDES]):
        b = baseline[i] if i < len(baseline) else baseline[-1]
        layout = s.get("layout") if s.get("layout") in LAYOUTS else b["layout"]
        source = s.get("source") if s.get("source") in SOURCES else b["source"]
        if layout == "statement":
            source = "none"
        refs = []
        for r in s.get("references") or []:
            try:
                if isinstance(r, str) and project.abs(r).exists() and r not in refs:
                    refs.append(project.abs(r).relative_to(project.root.resolve()).as_posix())
            except ValueError:
                continue
        slide = {
            "n": i + 1, "purpose": s.get("purpose") or b["purpose"], "layout": layout, "source": source,
            "slot": s.get("slot") or (b.get("slot") if source in ("library", "common") else None),
            "prompt": "" if source == "none" else (s.get("prompt") or b["prompt"]),
            "references": [] if source == "none" else (refs or b["references"]),
            "headline": s.get("headline", ""), "subtext": s.get("subtext", ""),
            "eyebrow": s.get("eyebrow", "") or "", "quote": s.get("quote", "") or "", "note": s.get("note", "") or "",
            "script": s.get("script", "") or "",
            "items": [x for x in (s.get("items") or []) if isinstance(x, str) and x.strip()],
            "button": s.get("button", ""),
            "text_pos": "bottom" if layout in ("overlay-bottom", "hook") else "top", "shade": 0.55,
        }
        if source == "library" and slide["slot"] not in ("options", "quality"):
            slide["slot"] = b.get("slot") if b.get("slot") in ("options", "quality") else "options"
        if source == "common" and slide["slot"] != "cta":
            slide["slot"] = "cta"
        if source in ("generate", "input", "none"):
            slide["slot"] = None if source != "generate" else slide["slot"]
        slides.append(slide)
    if hooks[0] and slides:
        slides[0]["headline"] = hooks[0]
    voice = raw.get("voice") if raw.get("voice") in VOICES else ""
    ctype = raw.get("carousel_type") if raw.get("carousel_type") in CAROUSEL_TYPES else ""
    return {"hooks": hooks, "hook_choice": 0, "slides": slides, "caption": raw.get("caption", "").strip(),
            "hashtags": with_brand_tags(parse_hashtags(raw.get("hashtags") or [])), "hashtag_target": target_tags,
            "voice": voice, "carousel_type": ctype}


# ---------------------------------------------------------------- QA
QA_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "issues": {"type": "array", "items": {"type": "string"}},
                   "prompt_fix": {"type": "string"}},
    "required": ["ok", "issues", "prompt_fix"],
}


def qa_prompt(image_rel: str, input_rel: str, card_text: str, slide: dict) -> str:
    return f"""Quality-check a generated marketing image for the jewelry shop "Be Wished".
Use the Read tool to view the generated image: {image_rel}
and the real product photo (ground truth): {input_rel}
Slide purpose: {slide.get('purpose')}. Prompt used: {slide.get('prompt')}
Ground-truth poem card text:
{card_text}

Check:
1. If the poem card is visible, its text must match the ground truth (minor blur is OK; changed or garbled words are not).
2. The jewelry must match the real product (shape, metal color, stones/pearls).
3. If a box lid or closed box is visible, it must be BLACK with the gold Be Wished logo.
4. No added text, captions or watermarks besides the card and the box logo.
5. No anatomy or rendering defects (hands, faces, duplicated objects).
Return ok=true only if all checks pass. issues: short list. prompt_fix: one sentence to add to the prompt to fix the issues (empty if ok)."""


# ---------------------------------------------------------------- ChatGPT via Claude in Chrome
CHROME_SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["done", "failed", "limit"]},
                   "chat_url": {"type": "string"}, "message": {"type": "string"}},
    "required": ["status", "chat_url", "message"],
}


def image_prompt(slide_prompt: str, suffix: str) -> str:
    return f"{slide_prompt.strip()}\n\n{suffix.strip()}"


def chrome_agent_prompt(full_prompt: str, refs_abs: list[str], chat_url: str, chatgpt_url: str) -> str:
    files = "\n".join(f"- {r}" for r in refs_abs) or "- (no reference files)"
    where = (f"Open this existing ChatGPT conversation: {chat_url}" if chat_url
             else f"Open {chatgpt_url} and start a NEW chat")
    return f"""Use the Claude in Chrome browser tools to generate exactly ONE image in ChatGPT and download it.
Work only in a tab you create; never close or change the user's other tabs.

1. Call tabs_context_mcp (createIfEmpty: true), then create a new tab.
2. {where}. If ChatGPT is not logged in, stop and return status "failed" with message "ChatGPT is not logged in".
3. Attach these reference images to the message with the file_upload tool (wait until every upload finishes):
{files}
4. Type the prompt below into the message box exactly as given and send it.
5. Wait for the image to finish generating (usually 1-3 minutes). Check with a screenshot about every 20 seconds.
   If ChatGPT says a usage or rate limit was reached, return status "limit" with its message.
6. When the finished image is shown, download it with ChatGPT's download button (hover or open the image to
   find it). Make sure the download actually started.
7. Return status "done" and the conversation URL from the address bar as chat_url.
Do nothing else.

PROMPT TO SEND:
<<<
{full_prompt}
>>>"""
