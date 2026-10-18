"""Approved product facts per style (doc/facts/<Style>.md)."""
from __future__ import annotations

from pathlib import Path

from .jsonio import write_text
from .paths import Project

MARKER = "<!-- approved: yes -->"
COMMON = "_Common"

COMMON_DRAFT = """# Be Wished: facts for all styles

## Brand
- Handmade & personalized jewelry gifts, each with a personalized poem card.
- Tagline on packaging: "More than jewelry".

## Materials & quality (from store infographics)
- Solid 14K gold-filled or 925 sterling silver. Not just plated.
- Will not rub off; will not tarnish or turn skin green.
- Durable and keeps its shine.
- Hypoallergenic and nickel free.
- Metal colors: yellow gold, rose gold, silver.

## Packaging
- Arrives in the black Be Wished gift box with gold logo, inside a white organza bag.
- Boxed, bagged and ready to gift.

## Personalization
- Poem card personalized with the recipient's name.
- The giver can add their own closing words / signature line.
"""


def facts_path(project: Project, style: str) -> Path:
    return project.facts / f"{style}.md"


def read_facts(project: Project, style: str) -> dict:
    path = facts_path(project, style)
    if not path.exists():
        if style == COMMON:
            return {"text": COMMON_DRAFT, "approved": False, "exists": False}
        return {"text": "", "approved": False, "exists": False}
    raw = path.read_text(encoding="utf-8")
    approved = raw.startswith(MARKER)
    text = raw[len(MARKER):].lstrip("\n") if approved else raw
    return {"text": text, "approved": approved, "exists": True}


def write_facts(project: Project, style: str, text: str, approved: bool) -> dict:
    text = text.strip() + "\n"
    write_text(facts_path(project, style), (MARKER + "\n" + text) if approved else text)
    return read_facts(project, style)


def is_approved(project: Project, style: str) -> bool:
    return read_facts(project, style)["approved"]
