# Automated Instagram Carousels — Design

Status: draft for review · 2026-10-17
Brand: **Be Wished** — handmade & personalized jewelry gifts with poem cards.

---

## 1. Goal

Turn a single product photo (poem card + jewelry in its box) into a finished, on-brand
7-slide Instagram carousel plus caption and hashtags — with the user confirming the
facts and approving the plan before anything is generated.

The agent is **Claude Code** running in this project, using:
- its own vision to read poem cards and check generated images,
- **Claude in Chrome** to drive **ChatGPT** for image generation,
- local HTML/CSS → PNG rendering for all slide text.

---

## 2. Folder layout

```
AutomatedCarousels/
├─ doc/                         All documents (this file, style facts, prompt templates)
│  ├─ DESIGN.md
│  └─ facts/<Style>.md          Approved product facts per style (see §8)
├─ DataFromUser/                INPUT queue. One photo = one carousel. Filename = SKU.
├─ RealProductPhotos/           USER material. Read-only. Reference only.
│  ├─ Common/                   Be Wished box, bag, logo, style examples
│  └─ <Style>/                  Product photos + store infographics per style
├─ StyleLibrary/                AGENT-generated, approved, reusable, text-free images
│  ├─ _Common/                  Packaging / CTA backgrounds
│  └─ <Style>/                  Options, worn close-ups, quality mood shots
├─ Carousels/                   OUTPUT. One folder per finished carousel
│  └─ <YYYY-MM-DD>_<SKU>_<event>/
├─ data/                        Ledgers (hooks, hashtags, library usage)
└─ templates/                   HTML/CSS slide layouts (built later)
```

---

## 3. Input

- `DataFromUser/` contains **only** main product photos: poem card + jewelry in the box.
- **Filename (without extension) = SKU.** Example: `GodDaughter1_G_IC.jpg`.
- Processed **one at a time**. Each photo becomes one carousel.
- The input photo is **deleted only after its final carousel is approved and saved**. No archive.

---

## 4. SKU parsing

Delimiter `_`. Fields: `<PoemName>_<Metal>_<TypeCode>[_ignored…]`

### 4.1 Algorithm
1. Strip the file extension and split on `_`.
2. **If field 2 is `Cub`** → Cuban link necklace (field 3 = length: 18/20/22/24).
   **If field 2 is `CubTE`** → Triangle pendant necklace (field 3 = `TRI###` engraving style).
3. Otherwise the type code is **field 3**:
   1. Try an **exact match** on the full code (catches `COM043`, `BR3`, `BR4`, `1`–`12`).
   2. Remove a `-P1` / `-P2` suffix, then remove trailing digits → **family**; match the family **exactly** (case-sensitive).
   3. No match → stop and ask the user.
4. Field 2 (metal) is **not used for copy**. Anything like `S(18)` is ignored. The metal
   seen in the photo is used only to keep generated images visually consistent.
5. Field 1 (poem name, e.g. `Daughter10`, `AugustBday2`, `Fatherloss6`) is a **hint** for
   recipient / occasion / tone. The poem card itself is the primary source (§5).

Prefixes overlap (`S` / `SD` / `SHL` / `SatP` / `SZ`, `BR` / `BR3` / `BRM`, `CP` / `SCP`,
`ST` / `STE`), so matching is never by prefix.

### 4.2 Type table

| Code / family | Jewelry type | Notes |
|---|---|---|
| `WP`, `PP`, `DP` | Floating pearl necklace | |
| `IC` | Interlocking circles necklace | |
| `COM043` | Silver pendant necklace with engraved picture | exact match |
| `COM` (any other number) | Engraved pendant necklace | e.g. `COM033` |
| `CC` | Small and large circles necklace | |
| `SD1`–`SD12`, `D1`–`D12` | Drop birthstone necklace | number = birth month |
| `TUR`, `ONY`, `AME`, `EME`, `LAB` | Gemstone necklace | |
| `SHL`, `SHLE1`, `LHL`, `LHLE1` (± `-P1`/`-P2`) | Heart locket necklace | |
| `SatP` | Satellite pearl necklace | |
| `SZ` | Satellite CZ diamond necklace | |
| `S1`–`S12` | Satellite and birthstone necklace | number = birth month |
| `1`–`12` (digits only) | Birthstone and circle necklace | number = birth month |
| field 2 = `Cub` | Cuban link necklace (men/boys) | field 3 = length |
| field 2 = `CubTE`, or `TRI` | Triangle pendant necklace (men/boys) | |
| `RI` | Baroque pearl necklace | |
| `LV` | Lava stone necklace | |
| `SCP` | Small circle pearl necklace | |
| `BR3`, `BR4` | Diamond tennis bracelet | exact match |
| `BR` | 2 hearts bracelet | exact match |
| `ST`, `STE` | Star pendant necklace | e.g. `STE001` |
| `CR` | Cross pendant necklace | |
| `CP` | Circle pearl necklace | |
| `MUS` | Mustard seed necklace | |
| `BRM`, `BRME` | Men's/boys bracelet | |

Worked examples:

| SKU | Result |
|---|---|
| `Daughter10_S_WP` | Floating pearl |
| `BonusSon1_Cub_18` | Cuban link, 18" |
| `Confirmation5_CubTE_TRI019` | Triangle pendant |
| `AugustBday2_G_D8` | Drop birthstone, August |
| `Fatherloss6_S(18)_ONY` | Gemstone (onyx), memorial tone |
| `School9_R_STE001` | Star pendant |

### 4.3 Style → folder mapping

Folder names don't need to match type names exactly. The mapping lives in one table,
kept in `data/styles.json` when built:

| Jewelry type | RealProductPhotos folder |
|---|---|
| Drop birthstone necklace | `DropBirthstoneNecklace` |
| Engraved pendant necklace | `EngravedPendantNecklace` |
| Floating pearl necklace | `FloatingPearlNecklace` |
| Gemstone necklace | `GemstoneNecklace` |
| Interlocking circles necklace | `InterlockingCircelsNecklace` |
| *(all others)* | *not yet created* |

**If a style has no folder, or the folder is empty → stop and ask the user to add photos.**

---

## 5. Intake & confirmation (approval point 1)

The agent reads the poem card in the photo (headline, name, poem, signature line) and
proposes values. **It always asks the user to confirm from, to and event, even when it is
confident.**

```
SKU:       GodDaughter1_G_IC
Style:     Interlocking circles necklace → RealProductPhotos\InterlockingCircelsNecklace
Metal:     Gold (from photo)
From:      Aunt / Godmother   (card: "Aunt Morgan")                 ← confirm
To:        Goddaughter        age group: child / teen / adult?       ← confirm
Event:     not stated. Suggest: Baptism · Christmas · Birthday · Just because   ← choose
Tone:      Joyful
Card text: [transcribed poem, used for copy and for image QA]
```

Rules:
- **Events** are open-ended. The baseline list (birthday, Christmas, Mother's Day,
  graduation, first/last day of school, Valentine's Day, confirmation, communion,
  bat mitzvah, just because) is extended by whatever the card says (e.g. wedding).
- **Placeholder names** on cards ("Emma", "Olivia") are sample names, not real people.
- **Tone:**
  - **Joyful** (default): warm, happy atmosphere.
  - **Gentle** for loss, sympathy and memorial poems (e.g. `Fatherloss`): soft light,
    quiet embrace, "carry them with you" messaging. Never "happy" imagery.
- **Recipient gender** comes from the card/poem name. Men/boys styles and male recipients
  switch copy to him/his and use a more masculine visual mood (still black & gold).

Nothing is planned until the user confirms the intake.

---

## 6. Storyline & slide baseline

Three-step storyline: **Emotion → Personalization → Trust & CTA**.
The 7 slides below are a **baseline**. The agent may adapt them per style and event and
explain any change in the plan.

| # | Purpose | Image | Source | Text |
|---|---|---|---|---|
| 1 | **Hook** | Poem card + jewelry in the **black Be Wished box with lid**, luxe scene | Generated per carousel | Chosen hook headline |
| 2 | Emotion: the want | Giver + recipient, happy (or gentle); recipient **wearing the jewelry** | Generated per carousel | "You want it to be more than just a gift…" |
| 3 | Emotion: the promise | Giver + recipient with the card in the black box + lid (style of `BoxExample1/2`) | Generated per carousel | Personal, the right words, a keepsake |
| 4 | Personalization | Hands holding the **open** box with the card (grey box OK, style of `BoxExample3`) | Generated per carousel | "Make it truly hers/his:" numbered options from facts |
| 5 | Style options | Style-specific options shot (see below) | StyleLibrary | Options headline |
| 6 | Quality | Metal trio / craftsmanship mood | StyleLibrary | Materials from facts |
| 7 | CTA | Packaging + logo (`Common/Box.png` or library variants) | Common / StyleLibrary | "Arrives ready to gift." + **SHOP THE LINK IN BIO** |

Slide 5 per style (examples):

| Style | Slide 5 subject |
|---|---|
| Engraved pendant | Engraving options grid (name, initial, birth flower, verse, own words) |
| Floating pearl | Pearl colors: white / blush peach / grey |
| Drop birthstone, Satellite & birthstone, Birthstone & circle | 12-month birthstone colors (highlight the SKU's month) |
| Interlocking circles | Symbolism of two linked circles + metal options |
| Heart locket | Photo inside the locket |
| Men/boys styles | Lengths / engraving styles |

---

## 7. Image rules

1. **No text in generated images.** All headlines, lists and CTAs are rendered locally.
   Allowed text: the poem card itself and the Be Wished logo on the box.
2. **Box color:**
   - Whenever the **lid or the whole box** is visible, it is the **black Be Wished box with
     the gold logo** (reference `Common/Box2.png`, `BoxExample1/2.png`).
   - When **only the open box** is shown (hands close-up, or the input photo), grey is fine.
3. **Card fidelity:** in every image showing the card, the agent compares the card text
   with the transcription from intake. Garbled or changed text → regenerate. After the retry
   limit, fall back to using the input photo as-is, framed on a dark branded background.
4. **Jewelry fidelity:** the jewelry must match the input photo and style references
   (shape, metal color, stone/pearl color). The agent checks every image.
5. **Visual identity:** dark, warm, candlelit luxury: black/marble surfaces, gold bokeh,
   baby's breath, gold ribbon (see `Common/BoxExample1/2.png`). 4:5 portrait (1080×1350).
6. Store **infographics** in `RealProductPhotos/<Style>` are **never published as-is**.
   They are reference and a fact source only, unless a photo is exactly right for a slide.

---

## 8. Product facts (no invented claims)

- Per style, the agent reads the infographics and photos once and writes
  `doc/facts/<Style>.md`: materials, colors, lengths, options, care claims.
- The user **approves** each facts file once.
- All slide copy and captions use **only** approved facts.
- Shared facts (e.g. `Quality Comparison.jpg`: solid 14K gold-filled, hypoallergenic,
  nickel-free) go in `doc/facts/_Common.md`.

---

## 9. Style library & rotation

- `StyleLibrary/<Style>/` holds **generated, text-free, user-approved** images for the
  reusable slides (5, 6, 7). They are based on that style's real product photos.
- The **first carousel** of a style generates its library images. The user approves them
  (approval point 3), then they are saved.
- **Rotation:** 2–3 variants per slot are built up over time. `data/library_usage.json`
  records which variant each carousel used, and the least recently used variant is
  preferred, so the feed doesn't repeat the same slide 6 every time.

---

## 10. Image generation via ChatGPT (Claude in Chrome)

Preconditions: the user is logged in to ChatGPT in the Chrome profile connected to the
Claude in Chrome extension.

Per carousel:
1. Open a **new ChatGPT chat** (one chat per carousel, for consistent style).
2. Upload references: the input photo, style photos, and `Common` box/scene examples.
3. Paste the slide's prompt from the approved plan (prompt templates in
   `doc/prompts.md`, written during build).
4. Wait for generation, then download the image.
5. Pick up the file from the Windows **Downloads** folder (newest file after the request
   time) and move it into the carousel's `raw/` folder.
   *(The extension usually cannot open `chrome://downloads`, so the folder is read
   directly.)*
6. QA with vision (§7). On failure, regenerate with a corrected prompt, up to a retry
   limit, then ask the user.
7. If ChatGPT reports a usage limit, pause and tell the user.

---

## 11. Copy rules

**Hooks**
- Premium style (e.g. "A necklace from grandma is never just a necklace").
- The agent proposes the **top 3** hooks in the plan. The user picks one or edits it.
- `data/hooks.json` stores every used hook. Exact repeats are not proposed.

**Slides:** short, premium, a serif headline with gold accent words, matching the example
carousel. Uses only approved facts. Pronouns follow the recipient.

**Caption** (`POST CAPTION and HASHTAGS.txt`): mirrors the slide story (hook → want →
personalization → materials → packaging → "Shop through the link in bio"), then hashtags.

**Hashtags**
- **3 to 30**, and the count varies from carousel to carousel.
- All relevant to the style, recipient, giver, event and brand.
- `data/hashtags.json` stores every published set.
- **Hard rule:** no two carousels ever have the exact same set.
- **Soft rule (proposed):** at most about 70% overlap with any previous set.

---

## 12. Rendering

- One HTML/CSS template per layout:
  - text over the image (top or bottom),
  - image with a lower dark text panel,
  - numbered list panel,
  - CTA with a button.
- Brand tokens: near-black background, gold accent (~`#D9C08A`), white serif headlines,
  gold rule, sans-serif secondary text, 1080×1350.
- Rendered to PNG by headless Chromium. The text-free source images stay in `raw/`, so
  any slide can be re-rendered with edited text without regenerating the image.

---

## 13. Plan (approval point 2)

Before generating anything, the agent writes `plan.md` in the carousel folder:
- the confirmed intake,
- 3 hook options,
- per slide: purpose, layout, image source (generated / library / common) with the
  **ChatGPT prompt**, headline and subtext,
- the caption and hashtag set (with count and overlap check result).

The user approves or edits it. Only then does generation start.

---

## 14. Output & cleanup (approval point 4)

```
Carousels/2026-10-17_GodDaughter1_G_IC_baptism/
├─ bewished_slide_1.png … bewished_slide_7.png
├─ POST CAPTION and HASHTAGS.txt
├─ plan.md            (intake, chosen hook, prompts, sources)
└─ raw/               (text-free source images)
```

1. The agent shows the finished slides. The user approves, or asks for changes to
   individual slides (re-render the text, or regenerate one image).
2. On approval: the folder is finalized, ledgers are updated (hooks, hashtags, library
   usage), and **the input photo is deleted from `DataFromUser/`**.
3. The agent moves on to the next photo in the queue.

---

## 15. End-to-end flow

```
for each photo in DataFromUser/:
  parse SKU → style        (unknown code or missing style folder → ask)
  read poem card           (vision)
  ▶ APPROVAL 1: intake (from / to / event / age / tone)
  ensure doc/facts/<Style>.md exists      (else draft → user approves)
  write plan.md (3 hooks, slides, prompts, caption, hashtags)
  ▶ APPROVAL 2: plan
  if StyleLibrary/<Style> is missing slots → generate → ▶ APPROVAL 3: library images
  generate per-carousel images via ChatGPT → QA → raw/
  render slides → PNG
  ▶ APPROVAL 4: final carousel (iterate per slide)
  save, update ledgers, delete input photo
```

---

## 16. Open items

- `EngravedPendantNecklace/` and `GemstoneNecklace/` are empty. Photos are needed
  before those styles can be processed.
- Facts files (`doc/facts/*.md`) are to be drafted and approved at first use of each style.
- Confirm the ChatGPT account/plan and that the Chrome profile is the one connected to
  the extension.
- Decide on the hashtag soft-overlap threshold (proposed 70%).
- Tooling for rendering (e.g. Node + Playwright vs. Python + Playwright) is decided at
  build time.
