"""Build a self-contained project folder for tests and demo mode.

python -m tests.make_demo <folder>   -> demo project (copies the real sample photos when present)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REAL_ROOT = Path(__file__).resolve().parent.parent


def _img(path: Path, color, label: str, size=(800, 800)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", size, color)
    d = ImageDraw.Draw(im)
    d.rectangle([60, 60, size[0] - 60, size[1] - 60], outline=(230, 200, 140), width=6)
    d.ellipse([size[0] // 2 - 60, size[1] // 2 - 60, size[0] // 2 + 60, size[1] // 2 + 60], outline=(230, 200, 140), width=8)
    d.text((80, 80), label, fill=(255, 255, 255))
    im.save(path)


def build_synthetic(root: Path) -> Path:
    """Small deterministic project: 4 inputs (2 ready, 1 unknown code, 1 empty style folder)."""
    inputs = root / "DataFromUser"
    photos = root / "RealProductPhotos"
    for sku, color in [("GodDaughter1_G_IC", (40, 30, 30)), ("Sister25_G_D6", (30, 30, 50)),
                       ("Mystery1_G_XYZ", (50, 50, 50)), ("Niece11_S_COM033", (30, 50, 30))]:
        _img(inputs / f"{sku}.jpg", color, sku)
    _img(photos / "InterlockingCircelsNecklace" / "Model20Gold.jpg", (90, 70, 60), "IC model")
    _img(photos / "InterlockingCircelsNecklace" / "QualityInfoA+General.jpg", (60, 60, 60), "IC info")
    _img(photos / "DropBirthstoneNecklace" / "Model7.jpg", (70, 60, 90), "Drop model")
    (photos / "EngravedPendantNecklace").mkdir(parents=True, exist_ok=True)
    for name, color in [("Box.png", (15, 12, 10)), ("Box2.png", (230, 230, 230)), ("BoxExample1.png", (40, 25, 15)),
                        ("BoxExample2.png", (45, 28, 18)), ("BoxExample3.png", (200, 190, 180)),
                        ("GOlden Logo2.jpg", (0, 0, 0))]:
        _img(photos / "Common" / name, color, name, size=(900, 1125))
    return root


def build_catalog(folder: Path) -> Path:
    """Small poem-card catalog in both text formats the real one uses."""
    folder.mkdir(parents=True, exist_ok=True)
    cards = {
        "GodDaughter1_IC": ("Header: To my beloved Goddaughter\n\nBody: You are a treasure with a heart that is kind "
                            "and true.\n\nClosing: None\n\nFrom: Aunt/Godmother\n\nTo: Goddaughter\n\nRelationCircle: 1\n",
                            (40, 30, 30)),
        "GodDaughter1": ("Header: To my beloved Goddaughter\n\nBody: Generic version.\n\nClosing: None\n\n"
                         "From: Mother\n\nTo: Goddaughter\n", (200, 200, 200)),
        "Sister25_Drop": ("**Header:** My Sister My Friend\n\n**Body:**\n\nSisters are a little bit of childhood that can "
                          "never be lost.\n\n**Closing:** Love You Always and Forever!\n\n**From:**\n* Sister\n\n"
                          "**To:**\n* Sister\n", (30, 30, 50)),
        "Sister25_COM009": ("Header: Sister engraved\n\nBody: x\n\nFrom: Sister\n\nTo: Sister\n", (90, 10, 10)),
    }
    for key, (text, color) in cards.items():
        (folder / f"{key}_PoemText.txt").write_text(text, encoding="utf-8")
        _img(folder / f"{key}_MainImage.jpg", color, key)
    _img(folder / "GodDaughter1_ICEXPLAIN.jpg", (0, 0, 0), "explain")  # ignored by the matcher
    return folder


def sync_photos(src: Path, dst: Path) -> int:
    """Copy reference photos that are new or changed in the real project into the demo copy."""
    if not src.is_dir() or not dst.is_dir():
        return 0
    copied = 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        target = dst / p.relative_to(src)
        if not target.exists() or target.stat().st_mtime < p.stat().st_mtime:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            copied += 1
    return copied


def build_demo(root: Path) -> Path:
    """Demo project: real sample photos when available, synthetic otherwise. Never touches the real project."""
    root.mkdir(parents=True, exist_ok=True)
    if (root / "DataFromUser").exists() and any((root / "DataFromUser").iterdir()):
        sync_photos(REAL_ROOT / "RealProductPhotos", root / "RealProductPhotos")
        return root  # keep an existing demo (resume), with any reference photos added since
    real_inputs = REAL_ROOT / "DataFromUser"
    real_photos = REAL_ROOT / "RealProductPhotos"
    if real_photos.is_dir() and any(real_photos.iterdir()):
        shutil.copytree(real_photos, root / "RealProductPhotos", dirs_exist_ok=True)
        (root / "DataFromUser").mkdir(exist_ok=True)
        for p in real_inputs.iterdir() if real_inputs.is_dir() else []:
            if p.is_file():
                shutil.copy2(p, root / "DataFromUser" / p.name)
    else:
        build_synthetic(root)
    facts = REAL_ROOT / "doc" / "facts"
    if facts.is_dir():
        shutil.copytree(facts, root / "doc" / "facts", dirs_exist_ok=True)
    return root


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else REAL_ROOT / "_demo")
    if target.resolve() == REAL_ROOT.resolve():
        sys.exit("Refusing to build a demo inside the real project root.")
    build_demo(target)
    print(f"Demo project ready: {target}")
