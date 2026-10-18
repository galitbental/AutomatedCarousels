"""Caption file and human-readable plan.md."""
from __future__ import annotations

from .jobs import joined
from .ledgers import parse_hashtags


def caption_file_text(plan: dict) -> str:
    """Same format as the example carousel's 'POST CAPTION and HASHTAGS.txt'."""
    tags = " ".join(parse_hashtags(plan.get("hashtags", [])))
    return f"POST CAPTION and HASHTAGS\n{plan.get('caption', '').strip()}\n{tags}\n"


def chosen_hook(plan: dict) -> str:
    hooks = plan.get("hooks") or [""]
    i = plan.get("hook_choice", 0)
    return hooks[i] if 0 <= i < len(hooks) else hooks[0]


def plan_markdown(job: dict) -> str:
    it, info, plan = job["intake"], job["sku_info"], job["plan"]
    lines = [
        f"# Carousel {job['sku']}", "",
        "## Intake",
        f"- Jewelry: {info['jewelry_type']} ({info['metal']})",
        f"- From: {joined(it['from'])}" + (f" ({it['giver_name']})" if it.get("giver_name") else ""),
        f"- To: {joined(it['to'])} ({it['gender']}, {joined(it['age_group'])})",
        f"- Event: {joined(it['event'])}",
        f"- Tone: {it['tone']}",
        f"- Voice: {plan.get('voice', '')} · Carousel type: {plan.get('carousel_type', '')}",
        f"- Card: {it.get('card_headline', '')}",
        "",
        "## Hook",
        f"**{chosen_hook(plan)}**",
        "",
        "Options: " + " | ".join(h for h in plan.get("hooks", []) if h),
        "",
        "## Slides",
    ]
    for s in plan.get("slides", []):
        img = job["images"].get(str(s["n"]), {})
        versions = img.get("versions") or []
        cur = versions[img.get("current", 0)] if versions else {}
        lines += [
            f"### Slide {s['n']}: {s['purpose']}",
            f"- Layout: {s['layout']} · Source: {s['source']}" + (f" ({s['slot']})" if s.get("slot") else ""),
            f"- Headline: {s.get('headline', '')}",
            f"- Subtext: {s.get('subtext', '')}".replace("\n", " / "),
        ]
        if s.get("items"):
            lines.append("- Items: " + "; ".join(s["items"]))
        if s.get("button"):
            lines.append(f"- Button: {s['button']}")
        lines.append(f"- Image: {cur.get('file', '')} ({cur.get('origin', '')})")
        if cur.get("prompt"):
            lines += ["- Prompt:", "", "  " + cur["prompt"].replace("\n", "\n  ")]
        lines.append("")
    lines += ["## Caption", "", plan.get("caption", ""), "",
              "## Hashtags", "", " ".join(parse_hashtags(plan.get("hashtags", []))), ""]
    return "\n".join(lines)
