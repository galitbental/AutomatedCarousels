# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is
**Carousel Studio** is a local desktop app that turns Be Wished product photos into Instagram carousels. Be Wished sells
handmade, personalized jewelry gifts with poem cards. Each input photo shows a poem card plus the jewelry in its box.
- Input: `DataFromUser/<SKU>.jpg`. The file name is the SKU.
- Output: `Carousels/<date>_<SKU>_<event>/`, containing 7–10 PNG slides (1080×1350), `POST CAPTION and HASHTAGS.txt`,
  `plan.md` and `raw/`.
- The single user (the shop owner, not a programmer, often watching via remote control) approves every stage in the UI.

## Commands
- Run the app: `CarouselStudio.bat`. It creates `.venv` on first run and runs `python -m app`.
- Run the demo: `CarouselStudio-Demo.bat`. It builds or resumes `_demo/` and runs `--fake --root _demo --port 8766`.
- Run the app by hand: `.venv\Scripts\python.exe -m app [--fake] [--root DIR] [--port N] [--no-window]`.
- Tests: `.venv\Scripts\python.exe -m pytest` (or `RunTests.bat`). This takes about 80 s.
  - `pytest.ini` deselects `live` by default.
  - One test: `.venv\Scripts\python.exe -m pytest tests\test_api.py -k toggle -q`.
  - Live tests make real Claude/ChatGPT calls and cost money: `-m live`.
  - UI tests (`tests/test_ui.py`) drive the real UI in headless installed Chrome (`channel="chrome"`). They fail on any JS error.
  - Regression baselines live in `tests/golden/` (golden HTML/PNG per layout, caption, SKU table). Regenerate them only
    deliberately, with `UPDATE_GOLDEN=1`.
- JS syntax check: `node --check app/web/app.js`.
- There is no build step and no linter.

## Architecture
**Process model.** `app/__main__.py` starts Flask (`app/server.py`) on 127.0.0.1 and opens Chrome in `--app` mode.
- `/api/ping` returns a code hash from `app/version.py`.
- If a server with a different hash is already on the port, the launcher stops it (`/api/shutdown`, or kills the pid)
  and starts fresh. A server that is busy with a task is kept.
- After changing code, a running server must be restarted; relaunching the batch file does that.

**Layers:**
- `server.py` is thin routing.
- `service.py` (`Studio`) holds all business logic and the stage rules.
- `jobs.py` is the job store and the stage state machine.
- External work goes through two injected adapters:
  - `llm.Assistant`: `claude -p` headless, prompt via stdin, `--output-format json --json-schema` → `structured_output`.
  - The image backend: `imagegen.ChatGPTChromeBackend` runs `claude -p --chrome` to drive chatgpt.com, then picks the
    newest file from the Downloads folder.
- `fakes.py` provides `FakeAssistant` / `FakeImageBackend` for `--fake` mode and all tests. Keep the fakes in step when
  prompt or schema output changes.

**Jobs and stages.**
- Each job is JSON under `Carousels/_work/<SKU>/`.
- The stages are intake → facts → plan → images → slides → final. Each has a state:
  - `open`: editable
  - `approved`
  - `stale`: an earlier stage was reopened; editable and needs re-approval
  - `locked`: not reachable yet
- `require_editable(job, stage)` guards every mutation.
- `mark_dirty` timestamps record which slides need re-rendering.
- Long operations run as background tasks (`tasks.py`), polled by the UI. `kind` values are e.g. `gen:all`,
  `gen:<n>`, `plan`, `render`.
- Mutations go through `Studio._mutate(sku, fn)`, which holds a per-SKU lock.

**Domain modules:**
- `sku.py` + `styles.py` + `data/styles.json`: SKU → jewelry type → `RealProductPhotos/<folder>`. Rules are in
  `doc/DESIGN.md` §4. Matching is exact or by family, never by prefix; `Cub`/`CubTE` sit in field 2.
- `catalog.py`: poem-card lookup in the `catalog_dir` setting (a network V: drive). Matching goes by name, then variant
  score, then image similarity. Its suggestions prefill the intake. An unreachable catalog must never block a job.
- `prompts.py`: all LLM prompts and schemas, the 7-slide `baseline_slides`, and `sanitize_plan`. `sanitize_plan` forces
  layout `statement` to source `none`.
- `spec.py`: brand rules from `doc/BRAND_CONTENT_SPEC.md`:
  - voices and carousel types
  - `lint_plan` (errors block approval; warnings need confirmation)
  - brand hashtags always last
- `ledgers.py`: `data/*.json` history (hooks, hashtag sets, library usage, posts). It enforces no identical hashtag set
  and rotation of voice and type.
- `library.py`: `StyleLibrary/<style>/<slot>/` holds reusable approved images, picked least recently used.
- `render.py` + `templates/slide.html`: one Jinja template with all layouts. It is rendered to PNG through a CDP
  screenshot in headless Chrome. `fits()` JS shrinks text to fit. The same HTML serves the UI live preview
  (`/api/jobs/<sku>/preview/<n>`).
- `finalize.py`: writes the output folder, updates the ledgers, then deletes the input photo.

**UI.** `app/web/` holds the files (`index.html`, `app.js`, `app.css`). It's vanilla JS with no framework, using an
`h()` element helper, ported from the Stitch "Carousel Studio" design.
- The Plan, Images, Slides and Final stages share a storyboard strip plus an editor for the selected slide.
- Autosave is `queueSave`/`flushSave` (PATCH `/api/jobs/<sku>`). Call `await flushSave()` before any request that
  re-reads the job.
- Element ids are used heavily by `tests/test_ui.py`. Keep them stable: `#sb-n`, `#sl-n-field`, `#btn-approve`,
  `#kind-seg-n`, `#btn-refs-n`, etc.

**Paths.** `paths.Project` resolves every path. `Project.abs()` refuses paths outside the project root, and the API only
serves files inside it. `--root` points the whole app at another folder (used by the demo and tests:
`tests/make_demo.py`, and `tests/conftest.py` fixtures `proj`/`studio`/`client`/`flask_app` with a synthetic catalog).

## Project rules
- All project documents go in `doc/`:
  - `DESIGN.md`: business rules
  - `SRS.md`: requirements plus change log
  - `BRAND_CONTENT_SPEC.md`: approved copy and visual rules
  - `USER_GUIDE.md`
  - `TEST_REPORT.md`
  - `facts/<Style>.md`: approved product facts; copy may only use these

  Update USER_GUIDE and TEST_REPORT when features change.
- `RealProductPhotos/` is read-only for the app.
- Store infographics there are references only and are never published as-is.
- Input photos are deleted only after the final carousel is approved. No archive.
- Generated images must contain no text. All text is rendered locally.
- The box must be black whenever its lid or the whole box is visible.
- The user is non-technical and expects everything to be visible and approvable in the UI. Ask before saving brand or
  spec decisions.
- Project log: a Stop hook (`.claude/settings.json` → `.claude/hooks/obsidian_log.py`) appends an entry to the Obsidian
  vault at `C:\Work\GalitProjects\FirstProject\InstagramCarousel\Log.md`. When decisions or a version change, also update
  `03 Decisions.md` and `04 Build Status.md` there.
