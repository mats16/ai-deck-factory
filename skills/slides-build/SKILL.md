---
name: slides-build
description: Build Japanese slides directly in Google Slides with the Slides API (slides.py and the page JSON), then check and finish them (slides.py lint without building, gslides.py check on Google-rendered images, the three layers of checks). SKILL.md has the build-and-check loop and a table of which file to open for each task (writing pages, diagrams, the steps of a new deck, themes, images, reuse, older decks). Documents are docs-build. Always use before you start writing slides and before you deliver them.
---

# Build and finish Japanese slides

Slides are built directly in Google Slides with the Slides API (switched from pptx on 2026-10-07). To go back to the pptx method, see the workspace's `Archive/pptx_pipeline_20261007/README.md`. Documents (Google Docs) are in `../docs-build/`. The parts shared with documents (`gapi.py` for the Google APIs, `textlint.py` for the shared text rules and the run log, `brand.py` for fonts, colors, and the copyright notice, `sheet.py` for contact sheets) are in `../deck-practices/scripts/`; the scripts here import them.

| What you make | Read before you start writing |
|---|---|
| Writing or fixing pages | [pages.md](pages.md) (the page JSON) and [visual.md](visual.md) (this folder's visual rules for slides) |
| Pages with a free-form diagram, arrows, a Gantt chart, a bar chart, or a gridded diagram | [diagrams.md](diagrams.md) (`frame`, `arrow`, `gantt`, `bars`, and the build warnings for positions), in addition to the two above |
| Building, build warnings, command options | [commands.md](commands.md) |
| Steps 6–8 of a new deck (three representative pages, remaining pages, building the whole) | [workflow.md](workflow.md) |
| Choosing, copying, or changing a theme | [themes.md](themes.md) |
| Images, logos, icons | [images.md](images.md) |
| Reading `gslides.py check` and lint output | [lint.md](lint.md) |
| Changing `slides.py`, raw requests, unexpected build failures | [api.md](api.md) |
| Decks built with `pages.py`, or pptx from before 2026-10-07 | [legacy.md](legacy.md) |
| Placing the deck on Drive (location, name, renaming) | `../deck-practices/drive.md` |
| Documents | `../docs-build/SKILL.md` (Google Docs) |
| Splitting the remaining pages among child agents | [prompt_pages.md](prompt_pages.md) (the request to the child agents. Whether to split is slides-flow-016 in step 7 of [workflow.md](workflow.md)) |
| Reusing internal materials | [reuse.md](reuse.md) (use `scripts/gslides.py` to get the page list and images of a Google Slides deck, and `keep` and `jp` to make replacement pages) |

```sh
K=<slides-build folder>/scripts   # the folder that holds slides-build's SKILL.md. From other skills, ../slides-build/scripts relative to that skill's folder
cd <folder>/build
# Slides
python3 $K/slides.py new <Drive folder URL> <YYYYMMDD_name>   # first build. Tell the user the printed URL right away (deck-drive-003 in `../deck-practices/drive.md`). --theme <theme> (a name from slides.py themes) for company colors
python3 $K/slides.py lint <URL>                                     # after every edit, lint locally without building (pages changed since the last run. "Three layers of checks" below)
python3 $K/slides.py build <URL>                                    # build at checkpoints (rebuilds only changed pages. The URL does not change. Stops if someone edited in the UI. commands.md)
python3 $K/gslides.py check <URL>                                   # after building. Images and lint of changed pages. Add --talk at the end for talks such as LTs. --all for images of every page
```

## Three layers of checks

[slides-flow-005] Split checks into 3 layers, like test layers. Building and taking images are slow, and there is a limit of 60 images per minute, so do not build after every edit; check locally whatever the local lint can catch. Build only at checkpoints, and check things that span pages once per checkpoint. Which steps are checkpoints is in "Overall flow" of `../deck-practices/SKILL.md`.

| Layer | When | With | What it checks |
|---|---|---|---|
| unit | After every edit | `slides.py lint <URL>` (no build. 2–7 seconds for 53 pages) | Lint on JSON that turns the build requests into the presentations.get shape locally, and build warnings (positions of `frame` diagrams: an arrow line passes over a component, arrowheads gather at one point, components partly overlap. slides-pages-038 in diagrams.md). By default, pages changed since the last run and pages that still had `要修正` (all pages if the deck or the lint rules changed. `--pages 3,5`, `--all`). Deck-wide rules (number of covers, section dividers, conclusion bands, and so on) and the workspace check always look at all pages |
| e2e | When you build at a checkpoint | `slides.py build` → `gslides.py check` | Builds only changed pages, takes images of those pages, and measures the padding inside boxes on the images (box_pad). Writes the changed pages, images, and findings to `changed.json` |
| whole | Once per checkpoint (before `/deck-review`, and so on) | `gslides.py check --all`, the contact sheet (`sheet.py`), `deck.md` | Things that span pages: size and position of components of the same type, inconsistent naming, the flow of headings |

- **unit:** Findings marked 「（見積もり）」 (a heading or lead on 2 lines, the number of body lines, a line break inside a phrase, overlapping text that overflows its frame, empty space) and build warnings (the table in `commands.md`) use the same character-width estimate as the build, so confirm them on the images. Everything else is fixed by the JSON and produces the same findings as the lint after building. The padding in boxes measured on images, and the line breaks and image frames that Google renders, cannot be known locally. Child agents that write pages may also run it on their own files (`slides.py lint pages_<owner>.json <URL>`. No build).
- **Checkpoints:** when you build the three representative pages, when you build the whole deck for the first time (also once here when you merge the child agents' pages), and when you finish a batch of fixes (such as the fixes from one review round). Do not build between checkpoints. Bring the unit `要修正` to 0 before you build.
- **The parent agent takes the images in one place.** Do not let child agents run `gslides.py check`. Page images are limited to 60 per person per minute (the same per-minute quota counts your conversation, child agents, and other conversations together). Over the limit you get 429 and stop until the quota frees up. `gslides.py` counts the images this machine took in the last minute and waits before the limit.
- **Checking changed pages (e2e):** If 1–3 pages changed, the parent agent opens the images in `changed.json` itself without starting child agents. If 4 or more changed, you may split them into groups of a few pages (by chapter, or pages of the same type) and show them to child agents. Do not make one child agent per page (each child agent costs startup and skill loading, and the model API has rate limits). Give the child agent the `changed.json` entries for its pages (the `image`, and the `lint` and `box_pad` findings), `deck.md` (the full text. Without knowing abbreviations and numbers from earlier pages, it gives off-target findings), the outline, and `visual.md`. How to start them and how they reply is the same as the page owners in "How to ask" of `../deck-review/SKILL.md` (starting a child: `../deck-practices/agents.md`). Child agents do not build and do not take images. Have them return suspicions that span pages marked 「全体へ」, and check those in the whole layer.
  - **When you build the whole deck for the first time and go straight into `/deck-review`,** do not open the changed pages one by one at full size. The first round's review child agents (the page owners, if split by page) look at full-size images ("How to ask" in `../deck-review/SKILL.md`). The parent agent checks the following 3 things and fixes them before entering `/deck-review`. Open at full size only the pages caught by 1 and 3 (you may crop with `sips -c`). This is because full-size images stay in the parent agent's context until summarized ("Basis" below).
    1. Build warnings, and the `要修正` and `要確認` from `gslides.py check --all` (including padding measured on images)
    2. For decks split among child agents, inconsistencies between child agents found by searching `build/*.json` (`h` and `size` of components of the same type, character counts of cards, the 「デッキで共通」 lines and names from the 「書き方の決め」 section)
    3. On the contact sheet of all pages (`sheet.py`), size and position of components of the same type, density, and color
- **box_pad:** Do not let child agents measure it. Measure it by laying out the pages that `gslides.py check` took.

Basis: 20% of the time spent making materials went to building and checking, and the median number of builds per deck was 24 (2026-10-15. The workspace's `Internal/deck_speed_20261015/`). We confirmed on 5 past decks (234 findings in total) that the local lint gives the same findings as after building (2026-10-15). A full-size image costs about 1,500 tokens (opening 16 of 25 pages costs about 25,000; 2 contact sheets about 3,000. An estimate).

## Reading the results

- **What each check and lint rule does** is in [lint.md](lint.md). Open it when a finding is unclear.
- **Images:** After building, open the images of the changed pages (`changed.json`), look at them, and fix (the e2e in "Three layers of checks" above. When you build the whole deck for the first time and go straight into `/deck-review`, the review child agents look at full size. slides-flow-005 above). Look for overflow (text is not clipped even when it leaves its frame), overlaps, collisions with the source line or footer, punctuation at the start of a line, last lines of only 1–2 characters, and line breaks inside a word or phrase. Judge the finish by these Google-rendered images.
- **Text:** Read `deck.md` for missing content or wrong order.
- **lint:** Bring `要修正` to 0. Check each `要確認` one by one, and either fix it or be able to say why it stays (example: 「顧客の発言の引用に です・ます が残るのはよい。案内・依頼・注意書きのページ（問い合わせ先、お願い、「ご相談ください」、免責・価格の注記）の です・ます も残してよい。それ以外の説明の文は常体か体言止めに直す。」 content.md §6).
- **Before delivering:** Review a newly made material as a whole with `/deck-review` (`../deck-review/SKILL.md`) before returning it to the user. It looks with a separate subagent's eyes and with the contact sheet of all pages. For fixes after delivery, run only the scope decided by deck-flow-017 in `../deck-practices/revise.md`.
- When checking is done, you may delete `/tmp/slides_<ID>/`. Do not keep it in the material's folder.

## Deliverables

- **Deliver slides as Google Slides and documents as Google Docs (`../docs-build/`). Do not make PDFs.** Materials that were HTML turned into PDF before delivery (such as customer-facing materials) are kept. Slides before 2026-10-07 are pptx (how to fix them is legacy.md); documents before 2026-10-09 are docx (convert them to Google Docs to fix them. `../docs-build/SKILL.md` §5).
- **Fonts:** Slides and documents (Google Docs) use Noto Sans JP from Google Fonts (for slides, a theme made from a company template uses that template's font; the lint compares against the font of the template's master. `../slides-template/fonts.md`. Documents stay Noto Sans JP). Only the alphanumerics in code boxes and commands use the monospace Cascadia Mono (`MONO` in `slides.py`. `visual.md` §2. 2026-10-09).
- **Text size:** Slide text is 11pt or larger (including the cover, section dividers, and source lines. Only the confidentiality label on the same line as the copyright footer and the page number at the bottom right are 9pt. 2026-10-08; page number 2026-10-13). Supporting text inside a filled shape (such as Gantt bars) may go down to 9pt, 2pt below the body (slides-visual-037). The lint stops on font and size (it does not read page numbers, so the template and `slides.py` set them to 9pt). Google Slides cannot set a language, so check punctuation at the start of lines on the images (api.md).
- **Names and revisions:** The material name is `<counterpart>_<content>_<date>`. The name on Drive is in `../deck-practices/drive.md`. Overwrite revisions in the same file (for slides, the same URL); keep the previous version as `_v2` only when there is a reason. Do not make `.bak` files (except the `pages.py.bak*` that `slides.py merge` leaves in `build/`. Delete them when you deliver in step 7 of `/deck-review`).
- Do not edit decks built with `slides.py` in the UI. Edit the page JSON (pages.py for older materials) and rebuild (UI edits are lost. If someone edited in the UI, `slides.py build` stops. commands.md). For documents, see `../docs-build/SKILL.md` §4.
- Files that start with `~$` are PowerPoint or Word lock files. They are created while a file is open, so do not touch them.
