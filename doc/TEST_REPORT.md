# Carousel Studio: test report

## Update 2026-10-18 (v1.3: black/image toggle, reference picker, bell, launcher)
- Default suite: **165 passed, 0 failed**. New: API tests for the black/image toggle (Plan and Images stage, restore,
  refused once images are approved), reference picker (photo added while the app runs and in a subfolder appears, order
  kept, duplicates and paths outside the project refused, thumbnails), version ping / shutdown / no-cache headers;
  `test_launcher.py` (code version, an outdated server is replaced, a busy one is kept, demo photo sync). UI test now
  toggles slide 2 both ways, picks a newly added photo after Refresh, checks the bell rings exactly once after
  "Generate all missing", and toggles a slide on the Images stage.
- Defects found and fixed: (1) the demo batch file reopened a window on a server started from older code, so the demo
  showed the old UI; (2) a finished task could be reported twice by overlapping polls; (3) the demo's fake hashtag pool
  contained a brand tag, so the plan test failed about 1 run in 10.

## Update 2026-10-18 (v1.2: UI redesign from the Stitch project "Carousel Studio")
- New UI: Be Wished dark design system (Playfair Display + Plus Jakarta Sans, bundled), slim stepper with hints,
  storyboard strip + live preview (real slide template served at `/api/jobs/<sku>/preview/<n>`), hook cards,
  brand-spec status panel, compact chip rows with "+ more".
- Default suite: **157 passed, 0 failed**. UI test rewritten for the storyboard flow; new API test for the live preview
  and font routes.

## Update 2026-10-18 (v1.1: catalog intake, multi-select, brand spec)
- Default suite: **156 passed, 0 failed** (about 1 minute). New: `test_catalog_spec.py` (catalog parsing in both
  file formats, the 3 matching steps incl. image comparison and ambiguity, offline catalog, spec lint rules, brand tags).
  API and UI tests now cover catalog prefill, choosing another card, multi-select chips, automatic facts drafting,
  black statement slides, voice/type rotation and spec warnings. Rendering baselines were regenerated after the
  visual redesign (checked against the published carousels).
- Real catalog check: all 5 photos in `DataFromUser` matched the right card (Niece11 → COM033 out of 3 variants,
  GodDaughter1 → IC card out of 2). Index of 4,175 files: 0.7 s.
- Live: **ChatGPT image generation via Claude in Chrome passed end to end** (upload 3 references → generate →
  download → QA OK → rendered slide; ~7 min, ~$1.15). See `doc/live_test_slide_1.png`. A defect found and fixed:
  references over 10 MB are now resized before upload. Live Claude planning passed with no spec warnings.

## Original report (2026-10-17)

Date: 2026-10-17 · Result: **129 passed, 0 failed** (default suite, about 2 minutes) · Live smoke: 1 passed, 1 blocked (see below)

Run with `RunTests.bat`. Regression baselines are regenerated deliberately with `set UPDATE_GOLDEN=1`.

## Coverage by test file

| File | Tests | Covers (SRS) |
|---|---|---|
| `test_sku.py` | 47 | Every type code in the table, all DESIGN examples, exact matching where prefixes overlap (`S`/`SD`/`SHL`, `BR`/`BR3`, `CP`/`SCP`), error cases, editable `styles.json`, folder status, **golden** parse table (FR-SKU-*) |
| `test_ledgers.py` | 7 | Tag normalization, 3–30 range, exact-duplicate error (order-insensitive), overlap warning, hook history, library usage (FR-LED-*) |
| `test_facts_jobs_library.py` | 8 | Facts approval marker, job stage machine (approve / reopen / stale / locked), job store and path safety, per-slide dirty tracking, library variants + least-recently-used pick + seeding (FR-FAC, FR-NAV, FR-LIB) |
| `test_llm_imagegen.py` | 14 | Claude CLI adapter with a simulated process: structured output, JSON fallback, exit code, `is_error`, timeout, cancel, Chrome flags, missing CLI, prompt via stdin. Downloads pickup (old/partial files ignored, waits for the file). Version storage, reference confinement. ChatGPT backend success / limit / failure / no download (FR-IMG, §4.2) |
| `test_prompts_caption.py` | 7 | 7-slide baseline, gentle tone, male pronouns, plan sanitizing (bad layouts, bad references, slot fixing, hook → slide 1), plan prompt contents, Chrome/QA/card prompts, **golden** caption file, `plan.md` (FR-PLN, FR-FIN) |
| `test_render.py` | 13 | Markup escaping and gold accents, **golden HTML** for all 7 layouts, **pixel regression** for all layouts (1080×1350), partial render, cleanup of deleted slides, long-text fitting, missing image error (FR-SLD-*) |
| `test_api.py` | 30 | Every endpoint. Queue statuses, start blocking, `/file` path confinement, open-in-Explorer, settings, system check, log/tasks, intake confirmation gating, Claude failure reporting, loss→gentle tone, facts auto-approve, plan generation and partial regeneration, plan validation, warnings needing confirmation, duplicate hashtag block, slide reorder keeping images, library/common autofill, all image operations, QA auto-retry with prompt fix, cancel, render dirty tracking, **full end-to-end pipeline**, finalize failure deleting nothing, destination collision, discard keeping the input, no hashtag reuse across carousels |
| `test_ui.py` | 3 | **Real UI in headless Chrome**: the complete 6-stage flow by clicking (including refused approvals), library/settings/system views, the log drawer, discard. Fails on any JavaScript error |
| `test_live.py` (opt-in) | 2 | Real Claude: card reading → facts → plan. Real ChatGPT through Claude in Chrome: one image + QA + render |

## Live smoke results (2026-10-17)
- **Claude pipeline: passed.** Card read correctly (to = goddaughter, from = aunt / Morgan). Facts were drafted from
  11 photos with "verify" notes. The plan had 7 slides, 3 hooks, a caption, and 13 hashtags (the target was 13).
  Cost about $0.50 and 1¾ minutes.
- **ChatGPT image: blocked.** The Claude in Chrome agent opened chatgpt.com and correctly reported *"ChatGPT is not
  logged in"*. I confirmed this by opening the page myself: the Chrome profile connected to the extension is logged out.
  The app showed the error and offers the manual path. **Action for you:** log in to chatgpt.com in that Chrome profile,
  then run `RunTests.bat -m live` (or generate one image in the app).

## Defects found by the tests and fixed
1. Jinja macro names shadowed the headline/subtext variables, so text rendered as `<Macro …>` (found by visual check, now covered by golden HTML/PNG).
2. POST requests without a JSON body returned HTTP 415 (API tests).
3. The collapsed activity-log bar covered the Approve button (UI test).
4. The slide "up to date" badge did not change while editing, so approval could be attempted mid-render (UI test).
5. Reference thumbnails on the Images stage rendered at full size (screenshot review).
6. Plan hooks copied the baseline placeholder ungrammatically ("A gift from aunt…") (live test). The baseline now reads "…from her aunt…" and the prompt asks for fresh hooks.
