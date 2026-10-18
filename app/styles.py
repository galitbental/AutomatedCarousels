"""Jewelry type table (data/styles.json) and style-folder status."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .jsonio import read_json, write_json
from .paths import Project, list_images

# Default table. Written to data/styles.json on first run; the file is the source of truth after that.
DEFAULT_TYPES: list[dict] = [
    {"name": "Floating pearl necklace", "families": ["WP", "PP", "DP"], "folder": "FloatingPearlNecklace",
     "options": "Pearl colors: classic white, blush peach, grey",
     "catalog": ["pearl", "pp", "wp", "dp", "pearlnecklace", "rpp", "wpc", "sb_wp6", "sb_wp6b", "sb_pp6"],
     "anchor": "A pearl forms slowly, inside the shell, and no two are alike. A pearl takes years to become one of a kind. So does she."},
    {"name": "Interlocking circles necklace", "families": ["IC"], "folder": "InterlockingCircelsNecklace",
     "options": "Two linked circles: two lives forever connected; metal options",
     "catalog": ["ic", "roseic", "r_ic"],
     "anchor": "Two circles that hold: a bond with no beginning and no end. Thankful our circles crossed."},
    {"name": "Silver pendant necklace with engraved picture", "exact": ["COM043"],
     "folder": "PictureEngravedNecklace", "options": "Her own photo engraved on the pendant",
     "catalog": ["com043"],
     "anchor": "Her picture, engraved: a moment kept close to her heart."},
    {"name": "Engraved pendant necklace", "families": ["COM"], "folder": "EngravedPendantNecklace",
     "options": "Engraving options: name, initial, birth flower, verse, or your own words",
     "catalog": ["com"],
     "anchor": "Engraved, not printed. So it is still there on the low days."},
    {"name": "Small and large circles necklace", "families": ["CC"], "folder": "SmallLargeCirclesNecklace",
     "options": "Two circles, small and large; metal options",
     "catalog": ["cc", "circles"],
     "anchor": "Two circles, one bond: always connected."},
    {"name": "Drop birthstone necklace", "families": ["SD", "D"], "folder": "DropBirthstoneNecklace",
     "birthstone": True, "options": "12 birthstone colors (highlight the recipient's month)",
     "catalog": ["drop", "dropstone", "d", "sd"],
     "anchor": "Her month, her color: made only for her."},
    {"name": "Gemstone necklace", "families": ["TUR", "ONY", "AME", "EME", "LAB"], "folder": "GemstoneNecklace",
     "options": "Gemstone choices",
     "catalog": ["gemstone", "gemstones", "tur", "ony", "onyx", "ame", "eme", "lab", "sb_ony"],
     "anchor": "A stone chosen for its meaning, worn close to the heart."},
    {"name": "Heart locket necklace", "families": ["SHL", "SHLE", "LHL", "LHLE"], "folder": "HeartLocketNecklace",
     "options": "A photo inside the locket; engraving",
     "catalog": ["heart", "locket", "shl", "lhl"],
     "anchor": "A heart locket keeps her people close."},
    {"name": "Satellite pearl necklace", "families": ["SatP"], "folder": "SatellitePearlNecklace",
     "options": "Delicate satellite chain with pearls",
     "catalog": ["satp", "sat", "satellite"],
     "anchor": "Small moments spaced along one continuous line."},
    {"name": "Satellite CZ diamond necklace", "families": ["SZ"], "folder": "SatelliteCZNecklace",
     "options": "Satellite chain with CZ diamond",
     "catalog": ["sz", "s_sz", "cz", "wpc_cz"],
     "anchor": "A small sparkle for every moment along the way."},
    {"name": "Satellite and birthstone necklace", "families": ["S"], "folder": "SatelliteBirthstoneNecklace",
     "birthstone": True, "options": "12 birthstone colors (highlight the recipient's month)",
     "catalog": ["s", "sat", "satellite"],
     "anchor": "Her month, her color: small moments along one continuous line."},
    {"name": "Birthstone and circle necklace", "exact": [str(i) for i in range(1, 13)],
     "folder": "BirthstoneCircleNecklace", "birthstone": True,
     "options": "12 birthstone colors (highlight the recipient's month)",
     "catalog": ["circlestone", "1"],
     "anchor": "Her month, her color, in a circle that never ends."},
    {"name": "Cuban link necklace", "special": "Cub", "folder": "CubanLinkNecklace", "men": True,
     "options": "Chain lengths 18, 20, 22, 24 inch",
     "catalog": ["cuban", "cub"],
     "anchor": "Strong links, like the bond between you."},
    {"name": "Triangle pendant necklace", "special": "CubTE", "families": ["TRI"],
     "folder": "TrianglePendantNecklace", "men": True, "options": "Engraving styles on the triangle pendant",
     "catalog": ["triangle", "tri"],
     "anchor": "Engraved, not printed: words he can carry."},
    {"name": "Baroque pearl necklace", "families": ["RI"], "folder": "BaroquePearlNecklace",
     "options": "Unique baroque pearl shapes",
     "catalog": ["ri", "rice", "raw", "ri_ss"],
     "anchor": "No two baroque pearls are alike. Neither is she."},
    {"name": "Lava stone necklace", "families": ["LV"], "folder": "LavaStoneNecklace", "options": "Lava stone",
     "catalog": ["lava", "lv"],
     "anchor": "Formed by fire, made to last."},
    {"name": "Small circle pearl necklace", "families": ["SCP"], "folder": "SmallCirclePearlNecklace",
     "options": "Small circle with pearl",
     "catalog": ["scp"],
     "anchor": "A pearl in a circle: one of a kind, always held."},
    {"name": "Diamond tennis bracelet", "exact": ["BR3", "BR4"], "folder": "TennisBracelet",
     "kind": "bracelet", "options": "Sparkling tennis bracelet",
     "catalog": ["tennis", "br3", "br4"],
     "anchor": "An unbroken line of light."},
    {"name": "2 hearts bracelet", "exact": ["BR"], "folder": "TwoHeartsBracelet", "kind": "bracelet",
     "options": "Two linked hearts",
     "catalog": ["br", "hearts"],
     "anchor": "Two hearts, linked."},
    {"name": "Star pendant necklace", "families": ["ST", "STE"], "folder": "StarPendantNecklace",
     "options": "Star pendant designs",
     "catalog": ["star", "st", "ste"],
     "anchor": "Like the stars: you don't always see them, but they're always there."},
    {"name": "Cross pendant necklace", "families": ["CR"], "folder": "CrossPendantNecklace",
     "options": "Cross pendant",
     "catalog": ["cross", "cr"],
     "anchor": "Faith she can hold on to."},
    {"name": "Circle pearl necklace", "families": ["CP"], "folder": "CirclePearlNecklace",
     "options": "Circle with pearl",
     "catalog": ["cp"],
     "anchor": "A pearl held in a circle that never ends."},
    {"name": "Mustard seed necklace", "families": ["MUS"], "folder": "MustardSeedNecklace",
     "options": "Mustard seed of faith",
     "catalog": ["mus", "mustard"],
     "anchor": "Faith as small as a mustard seed can move mountains."},
    {"name": "Men's/boys bracelet", "exact": ["BRM", "BRME"], "folder": "MensBracelet", "men": True,
     "kind": "bracelet", "options": "Men's bracelet styles",
     "catalog": ["brm", "brme"],
     "anchor": "Strength he can wear every day."},
]

BIRTH_MONTHS = {
    1: ("January", "deep red"), 2: ("February", "purple"), 3: ("March", "light blue"),
    4: ("April", "clear"), 5: ("May", "green"), 6: ("June", "light purple"),
    7: ("July", "red"), 8: ("August", "light green"), 9: ("September", "blue"),
    10: ("October", "pink"), 11: ("November", "golden yellow"), 12: ("December", "blue"),
}


@dataclass
class JewelryType:
    name: str
    folder: str
    families: list[str] = field(default_factory=list)
    exact: list[str] = field(default_factory=list)
    special: str | None = None
    men: bool = False
    birthstone: bool = False
    kind: str = "necklace"
    options: str = ""
    catalog: list[str] = field(default_factory=list)  # variant names used in the poem-card catalog
    anchor: str = ""  # symbolic anchor sentence (brand spec 2.3)

    @classmethod
    def from_dict(cls, d: dict) -> "JewelryType":
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in keys})


class StyleTable:
    """Lookup tables built from the type list."""

    def __init__(self, types: list[dict]):
        self.types = [JewelryType.from_dict(t) for t in types]
        self.exact: dict[str, JewelryType] = {}
        self.families: dict[str, JewelryType] = {}
        self.special: dict[str, JewelryType] = {}
        for t in self.types:
            for c in t.exact:
                self.exact[c] = t
            for f in t.families:
                self.families[f] = t
            if t.special:
                self.special[t.special] = t

    def by_name(self, name: str) -> JewelryType | None:
        return next((t for t in self.types if t.name == name), None)

    def by_folder(self, folder: str) -> JewelryType | None:
        return next((t for t in self.types if t.folder == folder), None)


def styles_path(project: Project) -> Path:
    return project.data / "styles.json"


def load_table(project: Project) -> StyleTable:
    path = styles_path(project)
    data = read_json(path)
    if data is None:
        data = {"types": DEFAULT_TYPES}
        write_json(path, data)
    defaults = {t["name"]: t for t in DEFAULT_TYPES}
    changed = False
    for t in data["types"]:  # older files: add fields introduced later, keep the user's edits
        for key in ("catalog", "anchor"):
            if key not in t and key in defaults.get(t["name"], {}):
                t[key] = defaults[t["name"]][key]
                changed = True
    if changed:
        write_json(path, data)
    return StyleTable(data["types"])


def folder_status(project: Project, jtype: JewelryType) -> tuple[str, list[Path]]:
    """('ready'|'no_folder'|'empty', photos) for a jewelry type's RealProductPhotos folder."""
    folder = project.photos / jtype.folder
    if not folder.is_dir():
        return "no_folder", []
    photos = list_images(folder)
    return ("ready" if photos else "empty"), photos
