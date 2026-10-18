# Carousel Studio — Software Requirements Specification (SRS)

Version 1.1 · 2026-10-18 · Status: implemented
Related: [DESIGN.md](DESIGN.md) (product design and business rules) · [BRAND_CONTENT_SPEC.md](BRAND_CONTENT_SPEC.md) (copy & visual rules)

## Change log v1.1 (supersedes the matching requirements below)

| ID | Change |
|---|---|
| FR-INT-2 (new primary) | On job creation the poem card is looked up in the catalog folder (Settings `catalog_dir`, default `V:\Amazon\Catalog\AllCatalog\_ALL_SKU_POEM_CARDS`): (1) poem name = first field of `<Poem>[_<Variant>]_MainImage/_PoemText` (case-insensitive); (2) if several, the variant must fit the SKU (exact type code > jewelry-type alias > generic card); (3) if still several, the card images are compared with the input photo. The parsed Header/Body/Closing/From/To fill the form; events, age group, gender and tone are inferred from the poem name and header (body only adds options). Other candidates are shown and can be chosen. Claude card reading remains as a fallback. An unreachable catalog never blocks a job. |
| FR-INT-3/4 | From, To, Event and Age group are **multi-select** (chips + custom values). The "Confirmed" boxes are removed. Approval requires at least one From, To and Event. |
| FR-FAC-2 | After intake approval, if the style has no facts yet, Claude drafts them from the style's photos automatically; the UI shows the progress and the user edits and approves. |
| FR-PLN-1 | Plans follow `BRAND_CONTENT_SPEC.md`: speaker voice (giver / founder / brand, rotated against the previous carousel), carousel type (story, because, objection, checklist, guide, educational), symbolic anchor per jewelry type, hook patterns, caption template. 7–10 slides. New slide fields: eyebrow, quote, note, script. New image source `none` (black slide). |
| FR-PLN-8 | Spec checks (`app/spec.py`): errors for slide count outside 7–10 and emoji on slides; warnings (confirm to continue) for price or body wording, more than 2 caption emoji, hooks over 2 sentences, missing CTA, same voice as the previous carousel. Brand tags `#bewished #bewishedgifts #morethanjewelry` are always appended last. |
| FR-SLD-1 | Rendering uses Playfair Display (headlines/body), Great Vibes (script overlay), the brand palette, a "›" swipe arrow on all but the last slide, and the layouts hook, statement, overlay-top/bottom, panel, checklist, guide, list, cta, framed. |
| FR-IMG-2 | Reference images are converted to upload-sized copies (max 2048 px, JPEG) before ChatGPT upload. |
| FR-LED | New ledger `data/posts.json` (sku, date, voice, carousel type, hook). |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for **Carousel Studio**. It is a local desktop
application that turns Be Wished product photos (a poem card plus jewelry in its box) into
finished 7-slide Instagram carousels with caption and hashtags. The user reviews, edits
and approves every stage in the UI.

### 1.2 Scope
In scope:
- An input queue, SKU parsing and style detection.
- Poem-card reading, intake confirmation, product facts, carousel planning, image
  generation (ChatGPT driven through Claude in Chrome, or manual), slide rendering,
  final approval, saving the output and cleaning up the input.
- Ledgers of hooks, hashtags and style-library usage.

Out of scope:
- Publishing to Instagram, scheduling, analytics.
- Multi-user use, cloud hosting, authentication.

### 1.3 Definitions

| Term | Meaning |
|---|---|
| **Input photo** | An image in `DataFromUser/`. The file name (without extension) is the SKU. |
| **SKU** | `<PoemName>_<Metal>_<TypeCode>[_…]`, see DESIGN §4. |
| **Style** | Jewelry type, mapped to a folder in `RealProductPhotos/`. |
| **Job** | One carousel in progress, created from one input photo. |
| **Stage** | One of: Intake, Facts, Plan, Images, Slides, Final. |
| **Approve** | Explicit user action that locks a stage and unlocks the next. |
| **Library** | `StyleLibrary/`: approved reusable text-free images per style and slot. |
| **Ledger** | JSON history files in `data/` (hooks, hashtags, library usage). |
| **Claude CLI** | `claude` executable (Claude Code), called headless with `-p`. |
| **Claude in Chrome** | Chrome extension that lets a Claude session control the browser (`--chrome`). |

### 1.4 References
- `doc/DESIGN.md`: business rules (SKU table, image rules, copy rules).
- `Functionality.txt`: original requirements from the user.
- Example carousel: `V:\_Private\GalitHillel\SchoolOfBusiness\Instagram\COIN\Granddaughter`.

---

## 2. Overall description

### 2.1 Product perspective
A standalone local web application shown in a desktop window:

```
CarouselStudio.bat
  └─ Python 3 (project venv)  ── Flask server on 127.0.0.1:8765
        ├─ REST API + static single-page UI (HTML/CSS/JS)
        ├─ Job store (JSON files on disk)
        ├─ Claude CLI adapter ── claude -p (vision, copy, QA)
        │                     └─ claude -p --chrome ── Claude in Chrome ── chatgpt.com
        ├─ Downloads watcher (Windows Downloads folder)
        └─ Renderer ── Playwright → installed Google Chrome (headless) → PNG
  └─ Chrome in app mode (--app=http://127.0.0.1:8765) = the application window
```

### 2.2 User
A single user: the shop owner. They are comfortable with Windows and not a programmer.
They may run the app locally or watch it through remote control, so every action and its
result must be visible in the UI.

### 2.3 Operating environment
- Windows 10/11, Python ≥ 3.11 (3.14 installed), Google Chrome (installed).
- Claude Code CLI installed and logged in. The Claude in Chrome extension is installed and
  connected for automated image generation.
- A ChatGPT account with image generation, logged in within that Chrome profile.

### 2.4 Constraints
- No cloud services other than the Claude CLI and ChatGPT (through the browser).
- All documents in `doc/`, all ledgers and settings in `data/`.
- `RealProductPhotos/` is **read-only** for the application.
- Only files inside the project root may be read or written by the server.

### 2.5 Assumptions
- Input photo file names are valid SKUs.
- ChatGPT's UI may change. The automated path is therefore best-effort and always has a
  manual fallback (FR-IMG-6…8).

---

## 3. Functional requirements

Priority: **M** = must, **S** = should.

### 3.1 Application shell (APP)

| ID | Requirement | P |
|---|---|---|
| FR-APP-1 | `CarouselStudio.bat` creates the venv and installs dependencies if missing, starts the server, and opens the UI in a Chrome app window (falls back to Edge, then the default browser). | M |
| FR-APP-2 | The console window shows the server log. Closing it stops the application. | M |
| FR-APP-3 | If the port is already serving Carousel Studio, the batch file only opens the window. | S |
| FR-APP-4 | The UI has a persistent **activity log** panel showing every operation with timestamp, including Claude/ChatGPT task progress and errors. | M |
| FR-APP-5 | Long operations run as background tasks. The UI shows a spinner, elapsed time and status, and stays responsive. A task can be cancelled. | M |
| FR-APP-6 | A **Settings** screen edits `data/settings.json`: Claude command, model, image backend (`claude_chrome` / `manual`), Downloads folder, ChatGPT URL, generation timeout, QA on/off, max auto-retries, image style suffix. | M |
| FR-APP-7 | A **System check** reports: Python OK, Chrome found, Claude CLI found and version, folders present, style folders and their photo counts. | S |

### 3.2 Input queue (Q)

| ID | Requirement | P |
|---|---|---|
| FR-Q-1 | List all images (`.jpg .jpeg .png .webp`) in `DataFromUser/` with thumbnail, SKU, detected style and status. | M |
| FR-Q-2 | Status is one of: *Ready*, *Unknown type code*, *Style folder missing*, *Style folder empty*, *In progress* (job exists), *Done*. | M |
| FR-Q-3 | **Start** creates a job for a Ready photo (or opens the existing job). Non-ready photos show the reason and cannot be started. | M |
| FR-Q-4 | A **Refresh** button rescans the folder. The queue also refreshes after every finalize. | M |
| FR-Q-5 | In-progress jobs are listed separately and can be resumed after restarting the app. | M |
| FR-Q-6 | A job can be **discarded**. This deletes its work folder only, never the input photo. | M |

### 3.3 SKU parsing & style mapping (SKU)

| ID | Requirement | P |
|---|---|---|
| FR-SKU-1 | Parse according to DESIGN §4.1: `Cub`/`CubTE` in field 2; otherwise field 3 with exact match first, then strip `-P<n>`, then strip trailing digits for the family; case-sensitive. | M |
| FR-SKU-2 | Output: poem name, poem base (letters only), poem number, metal raw, metal (Gold / Rose Gold / Silver / unknown from the first letter G/R/S), type code, family, jewelry type, style key, birth month (1–12) where applicable, chain length (Cub), men/boys flag. | M |
| FR-SKU-3 | The type table (DESIGN §4.2) and the style → folder map are data (`data/styles.json`) and can be edited without code changes. | M |
| FR-SKU-4 | Unknown codes and fewer than 3 fields produce a clear error and never a guess. | M |

### 3.4 Stage 1: Intake (INT)

| ID | Requirement | P |
|---|---|---|
| FR-INT-1 | Show the input photo large (zoomable) next to the SKU parse table. | M |
| FR-INT-2 | **Read card with Claude** runs a vision task that returns: card headline, recipient term, placeholder name, poem text, signature line, giver (relation and name if present), event if stated, suggested events (≥ 3), suggested tone, recipient gender, suggested age group, confidence notes. | M |
| FR-INT-3 | Editable fields: From (relation), giver name, To (relation), recipient gender, age group (child / teen / adult / any), event (dropdown with the baseline list + free text), tone (joyful / gentle), card text, notes. | M |
| FR-INT-4 | Values suggested by Claude are visibly marked as *suggested*. **From, To and Event must be confirmed by the user even if suggested** (Approve is disabled until each one has been explicitly confirmed). | M |
| FR-INT-5 | Loss/memorial/sympathy detection (poem name or card text) pre-selects the *gentle* tone and shows a notice. | M |
| FR-INT-6 | Approve saves the intake to `job.json`. | M |

### 3.5 Stage 2: Facts (FAC)

| ID | Requirement | P |
|---|---|---|
| FR-FAC-1 | Show `doc/facts/<StyleFolder>.md` and `doc/facts/_Common.md` in editors, next to a thumbnail strip of the style's reference photos. | M |
| FR-FAC-2 | **Draft with Claude** reads the style's photos/infographics and writes a facts draft containing only facts visible in the material (materials, colors, lengths, options, care claims, customization options). | M |
| FR-FAC-3 | An approved facts file carries the marker `<!-- approved: yes -->` on its first line. If both files are already approved, the stage is shown as approved automatically, and the user can still edit and re-approve. | M |
| FR-FAC-4 | Plan generation is blocked until both facts files are approved. | M |

### 3.6 Stage 3: Plan (PLN)

| ID | Requirement | P |
|---|---|---|
| FR-PLN-1 | **Generate plan with Claude** produces: 3 premium hooks; 7 slides (purpose, layout, image source, ChatGPT prompt, reference files, headline with `*accent*` markup, subtext, list items, button text); caption; hashtag list (3–30). The inputs are the intake, the approved facts, the slide baseline, previously used hooks and the last hashtag sets. | M |
| FR-PLN-2 | The slide baseline (DESIGN §6) is the default. The user can add, remove or reorder slides (2–10 slides). | S |
| FR-PLN-3 | Hooks: three radio options, each editable, plus a custom option. The chosen hook becomes slide 1's headline (they stay synchronized until the headline is edited separately). | M |
| FR-PLN-4 | Each slide card is fully editable: layout (hook / overlay-top / overlay-bottom / panel / list / cta / framed), image source (generate / library / common / input), prompt, references (add/remove from the project's photos), headline, subtext, items, button. | M |
| FR-PLN-5 | **Regenerate** can be run for the whole plan, the hooks only, the caption only or the hashtags only. | S |
| FR-PLN-6 | The hashtag editor shows the live count, and errors and warnings from the ledger checks (FR-LED-3, FR-LED-4). | M |
| FR-PLN-7 | Hook ledger check: a warning if the chosen hook was already used. | M |
| FR-PLN-8 | Approve is blocked if the hashtag count is outside 3–30, the set duplicates a previous set, or a slide has no headline and no image source. | M |
| FR-PLN-9 | Every generated prompt automatically gets the rules suffix: no added text, the black Be Wished box when the lid is visible, keep the card text exact, keep the jewelry identical, 4:5 portrait, brand mood. | M |

### 3.7 Stage 4: Images (IMG)

| ID | Requirement | P |
|---|---|---|
| FR-IMG-1 | One row per slide: current image thumbnail (large preview on click), source, prompt, references, status, QA result. | M |
| FR-IMG-2 | **Generate (ChatGPT)**: start a background task that calls `claude -p --chrome` with step-by-step instructions: open/continue the job's ChatGPT chat, upload the references, send the prompt, wait, download. Then pick up the downloaded file (FR-IMG-5). | M |
| FR-IMG-3 | One ChatGPT conversation per job. Its URL is stored in the job and reused for later slides. | S |
| FR-IMG-4 | **Generate all missing** runs the slides that need generation one after another. | S |
| FR-IMG-5 | Downloads pickup: the newest image file in the Downloads folder whose modified time is after the task started, waiting until its size is stable. It is moved (renamed) into `raw/slide_<n>_<k>.<ext>`. | M |
| FR-IMG-6 | Manual path: **Copy prompt**, **Open ChatGPT** (opens the URL in the browser), **Show reference files** (opens Explorer with them selected), **Import latest download**, **Upload file…**. | M |
| FR-IMG-7 | Library source: choose a variant from `StyleLibrary/<Style>/<slot>/` (least recently used preselected). If the slot is empty, the image is generated and can be **Saved to library**, which needs approval. | M |
| FR-IMG-8 | Common source: choose an image from `RealProductPhotos/Common` or `StyleLibrary/_Common/cta`. Input source: use the input photo itself. | M |
| FR-IMG-9 | **QA with Claude** (automatic after generation when QA is on) checks: the card text matches the intake card text, the jewelry matches the input photo, the box is black when the lid is visible, there is no extra text, and there are no anatomy/rendering defects. The result is OK, or issues plus a suggested prompt fix. | M |
| FR-IMG-10 | Every image version is kept (`slide_<n>_<k>`). The user can switch between versions. | S |
| FR-IMG-11 | Approve requires every slide to have an image. QA failures produce a warning but do not block. | M |

### 3.8 Stage 5: Slides (SLD)

| ID | Requirement | P |
|---|---|---|
| FR-SLD-1 | **Render** produces `bewished_slide_<n>.png` at 1080×1350 from the HTML templates with brand tokens (DESIGN §12). | M |
| FR-SLD-2 | A gallery shows all slides at phone-like size. Clicking opens full size. Next to each slide: quick editors for headline, subtext, items and button, text position, overlay darkness, and **Re-render this slide**. | M |
| FR-SLD-3 | Text never comes from the image model. `*accent*` words render in gold. The Be Wished logo is placed from `Common/GOlden Logo2.jpg` where a layout requires it. | M |
| FR-SLD-4 | Text fitting: headlines auto-shrink to fit their box and never overflow the canvas. | M |
| FR-SLD-5 | Approve requires a successful render of all slides that is newer than the last edit. | M |

### 3.9 Stage 6: Final (FIN)

| ID | Requirement | P |
|---|---|---|
| FR-FIN-1 | Show the final carousel (swipeable strip), caption and hashtags (editable), and the destination folder name `Carousels/<YYYY-MM-DD>_<SKU>_<event-slug>/`. | M |
| FR-FIN-2 | **Approve & Save**: copy the slides, write `POST CAPTION and HASHTAGS.txt`, `plan.md` (human-readable), `job.json` and `raw/`; verify that all files exist; append to the ledgers; **then** delete the input photo from `DataFromUser/` and delete the work folder. | M |
| FR-FIN-3 | If any step before deletion fails, nothing is deleted and the error is shown. | M |
| FR-FIN-4 | After saving, offer **Open folder** and **Next in queue**. | M |
| FR-FIN-5 | The destination never overwrites an existing folder (a `-2`, `-3` suffix is added). | M |

### 3.10 Stage navigation (NAV)

| ID | Requirement | P |
|---|---|---|
| FR-NAV-1 | A stepper shows the 6 stages with status: locked / open / approved / stale. | M |
| FR-NAV-2 | Approved stages can be reopened. Reopening marks later approved stages **stale** but keeps their data. A stale stage must be approved again. | M |
| FR-NAV-3 | All edits auto-save to `job.json` (debounced) and survive an app restart. | M |

### 3.11 Ledgers (LED)

| ID | Requirement | P |
|---|---|---|
| FR-LED-1 | `data/hooks.json`: list of {hook, sku, date}. | M |
| FR-LED-2 | `data/hashtags.json`: list of {sku, date, tags[]}. Tags are normalized (lowercase, leading `#`, no spaces or duplicates). | M |
| FR-LED-3 | Hard rule: a set equal to any previous set (order-insensitive) is an **error**. | M |
| FR-LED-4 | Soft rule: overlap = \|A∩B\| / min(\|A\|,\|B\|) against each previous set. Above the threshold (default 0.7, set in Settings) is a **warning** naming the closest carousel. | M |
| FR-LED-5 | `data/library_usage.json`: list of {style, slot, variant, sku, date}. Used for least-recently-used preselection. | M |
| FR-LED-6 | Ledgers are written only by Finalize (FR-FIN-2), atomically (temp file + rename). | M |

### 3.12 Style library (LIB)

| ID | Requirement | P |
|---|---|---|
| FR-LIB-1 | Layout: `StyleLibrary/<StyleFolder>/<slot>/<variant>.<ext>` plus `StyleLibrary/<StyleFolder>/library.json` (variant metadata: prompt, source sku, date, approved). Slots: `options`, `quality`. `StyleLibrary/_Common/cta/` holds the packaging/CTA backgrounds. | M |
| FR-LIB-2 | On first run, `RealProductPhotos/Common/Box.png` is seeded as an approved `_Common/cta` variant. | S |
| FR-LIB-3 | A **Library** screen shows all styles, slots and variants with usage counts. Variants can be approved, unapproved or removed. | S |

---

## 4. External interface requirements

### 4.1 User interface
- One window in Chrome app mode, minimum 1280×800, designed for 1500×950.
- Layout: **left sidebar** (Queue / In progress / Library / Settings / System check),
  **main area** (stage stepper + stage content), **bottom drawer** (activity log,
  collapsible).
- Visual style matches the brand: dark background, gold accents, serif headings, readable
  sans-serif body text. Buttons are large with clear verbs (Approve, Generate, Import).
- Every destructive action (Discard job, Approve & Save, which deletes the input photo)
  asks for an in-app confirmation (never a browser `alert`).
- Images open in an in-app lightbox.

### 4.2 Claude CLI interface
- Call: `claude -p <prompt> --output-format json --json-schema <schema> --model <model>
  --allowedTools Read --permission-mode dontAsk --no-session-persistence --add-dir <root>`.
  The working directory is the project root.
- The result is taken from `structured_output`. If it is missing, the first JSON object in
  `result` is parsed. A non-zero exit, `is_error`, or a parse failure is surfaced as a task
  error with stderr shown in the log.
- Image generation: `claude -p <instructions> --chrome --permission-mode
  bypassPermissions --output-format json --json-schema <status schema>`. The schema
  returns `{status: done|failed|limit, chat_url, message}`.
- Default timeouts: 300 s for text/vision tasks, 600 s for image generation (Settings).

### 4.3 File interface

| Path | Owner | Format |
|---|---|---|
| `DataFromUser/*.jpg…` | user | input photos |
| `RealProductPhotos/**` | user | read-only references |
| `StyleLibrary/**` | app | images + `library.json` |
| `Carousels/_work/<SKU>/job.json` | app | job state (§5.1) |
| `Carousels/_work/<SKU>/raw/`, `slides/`, `render/` | app | images, rendered PNG, HTML |
| `Carousels/<date>_<SKU>_<event>/` | app | final output |
| `doc/facts/*.md` | app + user | facts |
| `data/settings.json`, `data/styles.json`, `data/*.json` ledgers | app | JSON |

### 4.4 REST API (internal, for the UI)
`GET /api/queue` · `POST /api/jobs` · `GET|PATCH /api/jobs/<sku>` ·
`POST /api/jobs/<sku>/approve/<stage>` · `POST /api/jobs/<sku>/reopen/<stage>` ·
`POST /api/jobs/<sku>/intake/read` · `GET|PUT /api/facts/<style>` ·
`POST /api/facts/<style>/draft` · `POST /api/jobs/<sku>/plan/generate` ·
`POST /api/jobs/<sku>/images/<n>/generate|import|upload|use` ·
`POST /api/jobs/<sku>/images/<n>/qa` · `POST /api/jobs/<sku>/render[/<n>]` ·
`POST /api/jobs/<sku>/finalize` · `DELETE /api/jobs/<sku>` · `GET /api/tasks/<id>` ·
`POST /api/tasks/<id>/cancel` · `GET /api/log` · `GET|PUT /api/settings` ·
`GET /api/library` · `GET /api/system` · `GET /file?path=` (project-root-confined).

---

## 5. Data requirements

### 5.1 `job.json`
```json
{
  "sku": "GodDaughter1_G_IC",
  "input_file": "DataFromUser/GodDaughter1_G_IC.jpg",
  "created": "2026-10-17T18:00:00",
  "sku_info": { "...": "FR-SKU-2" },
  "stages": { "intake": "approved", "facts": "approved", "plan": "open",
              "images": "locked", "slides": "locked", "final": "locked" },
  "intake": { "from": "", "giver_name": "", "to": "", "gender": "female",
              "age_group": "adult", "event": "", "tone": "joyful",
              "card_text": "", "card_headline": "", "notes": "",
              "suggested": { "...": "claude output" },
              "confirmed": { "from": true, "to": true, "event": false } },
  "plan": { "hooks": ["", "", ""], "hook_choice": 0,
            "slides": [ { "n": 1, "purpose": "", "layout": "hook",
                          "source": "generate", "slot": null, "prompt": "",
                          "references": [], "headline": "", "subtext": "",
                          "items": [], "button": "", "text_pos": "top",
                          "shade": 0.55 } ],
            "caption": "", "hashtags": [] },
  "images": { "1": { "versions": ["raw/slide_1_1.png"], "current": 0,
                     "origin": "chatgpt", "qa": { "ok": true, "issues": [] } } },
  "chat_url": "",
  "render": { "files": [], "rendered_at": "", "edited_at": "" },
  "log": []
}
```

### 5.2 Integrity
- All JSON writes are atomic.
- Paths stored in jobs are relative to the project root.
- File-serving and file-writing endpoints reject paths outside the project root.

---

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Usability | Every stage fits one screen with at most one scroll region. Primary action button is bottom-right. Status always visible. |
| NFR-2 Transparency | Every Claude/ChatGPT call is logged with its purpose, duration and outcome. The full prompt can be viewed. |
| NFR-3 Safety | The input photo is deleted only in FR-FIN-2 after verification. `RealProductPhotos/` is never modified. No deletion outside `Carousels/_work` and the specific input file. |
| NFR-4 Resilience | A crash or restart loses at most the last 2 seconds of edits. Failed tasks never corrupt `job.json`. |
| NFR-5 Performance | UI actions under 200 ms. Rendering 7 slides under 15 s. Claude text tasks typically under 120 s. |
| NFR-6 Portability | No absolute paths in code. The project root is derived from the application location. |
| NFR-7 Maintainability | Business tables in data files. Modules separated (sku, styles, jobs, ledgers, llm, imagegen, render, finalize, server). Type hints and docstrings on public functions. |
| NFR-8 Cost awareness | The default model is `sonnet` for vision and copy tasks. Settings can change it. |

---

## 7. Verification requirements

| ID | Requirement |
|---|---|
| VR-1 Unit tests | `pytest` tests for every module: SKU parsing (every table row and all DESIGN examples), style mapping, ledgers (exact duplicate, overlap, normalization), facts approval marker, job state machine (approve/reopen/stale), library LRU, Downloads pickup, prompt suffix, caption builder, Claude adapter (subprocess mocked: success, `structured_output` missing, error, timeout), finalize (success, failure before delete, name collision). |
| VR-2 Regression tests | Golden files in `tests/golden/`: SKU parse results, caption text, rendered HTML per layout, and **rendered PNGs** compared pixel by pixel within a tolerance. Goldens are regenerated deliberately with `UPDATE_GOLDEN=1` (regenerative baselines), and any unintended change fails the suite. |
| VR-3 API tests | Flask test client covering every endpoint, path-confinement rejection, and stage-gating errors. |
| VR-4 End-to-end | Full pipeline on a temporary project copy with a fake Claude and a fake image backend: queue → intake → facts → plan → images → render → finalize. Verifies the output folder, ledgers and input deletion. |
| VR-5 UI test | Playwright drives the real UI against a temporary project with fakes through all 6 stages and checks the stepper, editors and approval gating. |
| VR-6 Live smoke (opt-in) | `pytest -m live`: real Claude card reading on one photo, and one real ChatGPT image generation through Claude in Chrome. Not part of the default run. |
| VR-7 | `RunTests.bat` runs the default suite and prints a summary. |

---

## 8. Acceptance criteria
1. The user double-clicks `CarouselStudio.bat` and sees the window with the queue of
   `DataFromUser/` photos and the status of each.
2. For a Ready photo, the user can complete all 6 stages in the UI, editing anything,
   without touching files or a terminal.
3. From, To and Event cannot be approved without explicit confirmation.
4. The final folder contains 7 PNG slides at 1080×1350, a caption file, `plan.md` and
   `raw/`. The input photo is gone from `DataFromUser/`.
5. A second carousel cannot be saved with an identical hashtag set.
6. The default test suite passes.

---

## 9. Traceability

| DESIGN section | Requirements |
|---|---|
| §3 Input | FR-Q-*, FR-FIN-2 |
| §4 SKU parsing | FR-SKU-* |
| §5 Intake & confirmation | FR-INT-* |
| §6 Slide baseline | FR-PLN-1/2, FR-SLD-* |
| §7 Image rules | FR-PLN-9, FR-IMG-9, FR-SLD-3 |
| §8 Facts | FR-FAC-* |
| §9 Library & rotation | FR-LIB-*, FR-IMG-7, FR-LED-5 |
| §10 ChatGPT procedure | FR-IMG-2…6 |
| §11 Copy rules | FR-PLN-*, FR-LED-1…4 |
| §12 Rendering | FR-SLD-* |
| §14 Output & cleanup | FR-FIN-* |
