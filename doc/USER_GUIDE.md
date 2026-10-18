# Carousel Studio: user guide

## Start
Double-click **`CarouselStudio.bat`**. The first run sets everything up (about a minute). After that, a
window opens with the queue. Keep the black console window open: closing it stops the app.

Want to look around without any Claude/ChatGPT cost? Use **`CarouselStudio-Demo.bat`**. It works on a
separate copy (`_demo` folder) with placeholder images and canned texts. New reference photos from
`RealProductPhotos` are copied into the demo on each start. If an older version of the app is still running (for
example a window left open), starting the batch file replaces it with the current version automatically, unless it
is busy with a task.

### One-time setup for automatic image generation
1. Open Google Chrome (the profile with the Claude in Chrome extension) and **log in to chatgpt.com**.
2. Make sure Chrome saves downloads to your `Downloads` folder without asking where to save
   (Chrome settings → Downloads → "Ask where to save each file" **off**).
3. Check **System check** in the app: Claude CLI, browser and Downloads folder should all show OK.

## Daily flow
1. Put product photos into `DataFromUser`. The **file name must be the SKU**, e.g. `GodDaughter1_G_IC.jpg`.
2. In **Queue**, click **Refresh**, then **Start carousel** on a photo marked *Ready*.
   *Blocked* photos tell you why (unknown code, or the style folder in `RealProductPhotos` is missing/empty).
3. Work through the six stages. Each one ends with **Approve** (bottom right).

| Stage | What you do |
|---|---|
| **1 Intake** | The form is filled in automatically from the **catalog poem card** (`V:\Amazon\Catalog\AllCatalog\_ALL_SKU_POEM_CARDS`): giver, recipient, event, age group, card headline, text and closing line. **From, To, Event and Age group are multi-select**: click a chip to select or unselect it, or type your own value in "+ add…". If several cards matched, pick the right one under "Other matching cards". No card found? Use **Read card with Claude instead**. Pick the tone: *joyful*, or *gentle* for loss/memorial. |
| **2 Facts** | The first time a style is used, Claude **reads that style's product photos and suggests the facts automatically** (about a minute). Edit them, then approve. Only these facts are used in the copy. |
| **3 Plan** | Optionally choose the **speaker voice** (giver / founder / brand; *Auto* rotates them) and the **carousel type** (story, because, objection, checklist, gift guide, educational). Click **Generate full plan with Claude**. Choose one of the 3 hooks (or edit it), and edit any slide: layout, image source (*none* = black slide), headline, subtext, eyebrow label, quote, small note, script overlay, image prompt, references. A carousel has 7–10 slides. The brand-spec checker warns about price wording, emoji on slides, long hooks, missing CTA, and a voice repeated from the previous carousel. Brand hashtags are always added last. |
| **4 Images** | Click **Generate all missing (ChatGPT)**. Claude opens ChatGPT in your Chrome, uploads the references, generates and downloads each image, then checks it (QA). Per slide you can also regenerate, switch between versions, import your own download, upload a file, use the input photo, or pick a library image. |
| **5 Slides** | Click **Render all slides**. Fix any text in the boxes next to each slide, then **Re-render**. |
| **6 Final** | Review the carousel, caption and hashtags. **Approve & Save** writes `Carousels/<date>_<SKU>_<event>/` and deletes the input photo. |

**Storyboard:** Plan, Images, Slides and Final share a strip of slide thumbnails at the top. Click a slide to open
its editor below. The **live preview** next to the fields is drawn with the real slide template, so it shows exactly
what the final slide will look like, and it updates as you type. The dot under each thumbnail shows its status:
green = ready, amber = missing image or needs render, red = QA issue, outline = black slide (no image needed).

**Black slide or image slide:** after the storyboard is suggested, every slide has a switch
**Black slide | Slide with image** (Plan stage, and on the Images stage until images are approved). Switching to an
image gives the slide a starting ChatGPT prompt and the input photo as a reference; switching back to black and again
to image restores the earlier layout and settings.

**Reference images for ChatGPT:** click **+ Choose references…** under a slide (Plan or Images stage). The picker shows
the input photo, the style's photos (subfolders included), Common, the style library and, folded, other styles.
Click photos to select them; the number is the upload order. **You can add new photos to the folders at any time**:
click **↻ Refresh** in the picker and they appear (marked NEW). **Open style folder** opens it in Explorer.

**Bell:** when **Generate all missing** finishes, the app plays a soft bell (turn it off in Settings → `bell_sound`;
**♪ Test bell** plays it).

You can click any earlier stage to look at it. **Reopen to edit** unlocks it, and later stages are then
marked *re-approve*. Everything is saved automatically, so you can close the app and continue later.

### Without automatic generation (manual ChatGPT)
On the Images stage: **Copy prompt** → **Open ChatGPT** → attach the reference images (**Show
references** opens their folder) → generate → download → **Import latest download**.

## Where things are

| Folder / file | Content |
|---|---|
| `DataFromUser/` | Your input photos (queue) |
| `RealProductPhotos/<Style>/`, `Common/` | Your reference photos (never changed by the app) |
| `StyleLibrary/` | Approved reusable images (Images stage → **Save to library**; manage under **Style library**) |
| `Carousels/<date>_<SKU>_<event>/` | Finished carousels: `bewished_slide_N.png`, `POST CAPTION and HASHTAGS.txt`, `plan.md`, `raw/` |
| `Carousels/_work/` | Carousels in progress |
| `doc/facts/` | Approved product facts per style |
| `data/` | Settings, jewelry type table (`styles.json`), hook/hashtag/library history |

## Adding a new jewelry style
1. Create `RealProductPhotos/<FolderName>/` with product photos. The folder names the app expects are listed
   in **System check** (or edit them in `data/styles.json`).
2. The first carousel of that style asks you to approve its facts and, on the Images stage, to save the
   reusable images to the library.

## Tests
`RunTests.bat` runs the automated tests (about 3 minutes). `RunTests.bat -m live` runs the real Claude/ChatGPT
smoke tests (costs money; needs ChatGPT logged in).
