---
name: slides-template
description: Create or adjust an AI Deck Factory template (theme) from a company's slide template (Google Slides), in three cases (a Japanese template, only an English one, or none), keeping the fonts, text sizes, and overall colors while meeting the standards for Japanese fonts and contrast. Also switches the default theme ([slides] default_theme). Use when asked 「会社のテンプレートを使いたい」「テンプレートを作って」「テンプレートを整えて」「既定のテンプレートを変えたい」, and when invoked without saying what to do.
---

# Create an AI Deck Factory template from a company template

An AI Deck Factory template is the Google Slides file that `slides.py new` copies. The template decides only these: the theme colors (the 12 slots of the master's color scheme), the font (the font of the master's placeholders; `slides.py build` sets the deck's text in this font), the page size, the position of the page number, and the decorations of the cover and section dividers (the shapes and logos of the company's layouts; the theme's `cover` and `section`). Text sizes and placement are written by the pages (deck.json or pages.py) (`../slides-build/visual.md` §1).

- **Do not change the original company template.** From a copy, keep only the master that the most pages use and the Blank layout that has the page-number placeholder; delete the other layouts, the sample pages, and the master's logo and copyright line (`pick` and `strip` in `template.py`). People keep using the company template on screen as it is.
- [slides-theme-001] **Keep every cover and section-divider layout pattern (with shapes, logos, or photos) that the company template provides.** List the layout names in the theme's `cover` and `section` (as in the audit table. The order is the pattern number; if the same name appears twice, list both. Each layout needs a page-number placeholder: the marker is written into this placeholder, so add one in the theme builder if it is missing. Do not list the same layout in both cover and section. To reduce the patterns, recreate with --from-base), and `template.py` deletes only each layout's text boxes and copyright line, keeping the shapes, images, and logos. Logos and lines that were aligned with the left edge of the original title box are moved to the text's left edge (0.6 in). The marker holds the number, the text width (up to the right edge of the original title box; do not overlap shapes or photos), and the background brightness (`dark`, `accent`, `light`: white text reaches 4.5:1, reaches only 3:1, reaches neither). When a JSON `cover` or `divider` page has `"variant": n`, `slides.py` keeps that layout's background and artwork and sets the text in colors that match the background brightness (`TONES`). The sample pages build every pattern once each, so when making a material, pick the number by looking at the samples. Dividers with different backgrounds may be used for different chapters. Cover pattern 1 is the first cover in the original samples (2026-10-13, ユーザー「テンプレートを作る際に、元の図形が入ったタイトルスライドなどを、維持して欲しいです」「表紙、中表紙は何パターンか用意されている元のものを維持してください」「セクション区切りで異なる背景の区切りページを使い分けることはよくします」).
- **Write the company's values in the workspace.** The theme file `themes/slides/<name>.json` (the `description` for choosing between themes, the font, colors per role, colors not in the theme, the per-theme copyright notice, the cover and divider patterns) and `[brand]` in `factory.toml` (the company name on the cover and the copyright notice). `template.py` writes the URL of the created template to `[slides.templates]` in `factory.toml`. Do not write the original template's URL anywhere; pass it to `--from-base` when creating. Do not add to the plugin's built-in themes (`../slides-build/themes/`) (visual and company are Databricks themes).
- Commands are written with `K=<slides-build folder>/scripts` (`../slides-build/scripts` from this skill's folder).
- **When invoked without saying what to do** (just `/ai-deck-factory:slides-template`), start from "Choosing the default theme" below and add the option 「新しく作る（会社のテンプレートから）」. If that is chosen, go to [create.md](create.md).

## What to open

| Situation | Open |
|---|---|
| Switching the default theme | "Choosing the default theme" below |
| Creating a template from a company template (the three cases) | [create.md](create.md) |
| A theme with a dark body background (`BG`), in any case | [dark.md](dark.md), in addition |
| Choosing or changing the font | [fonts.md](fonts.md) |
| Adjusting an existing template | "Where the rules live" and "When editing" below |

## Where the rules live

The rules a template must meet when you adjust it. To change a value, edit the source of truth (to change it in the workspace, use the same path under `rules/`).

| Rule | Source of truth | What measures it |
|---|---|---|
| Color roles (11 slots and 6 fixed colors) and the contrast of each pair (4.5:1 for non-bold text under 18pt and bold text under 11pt; 3:1 for text 18pt and above and bold text 11pt and above) | `../slides-build/visual.md` §1 (table and notes) and §3 | `slides.py lint <theme file>` (the role pairs `PAIRS` in `template.py`), 「コントラストが基準に届かない色の組」 in `gslides.py check` |
| Font (default Noto Sans JP, Cascadia Mono for code only; the theme can change it; fonts not in Google Fonts cannot render) | `../slides-build/visual.md` §2, "Deliverables" in `../slides-build/SKILL.md`, [fonts.md](fonts.md) | lint's 「書体が … でない」 (compared with the template's font) |
| Text size (11pt or more; only the copyright notice and page number at 9pt) and page area (13.33 × 7.5 in, 0.6 in left and right margins, top edges of elements) | `../slides-build/visual.md` §1 | lint, constants in `slides.py` |
| Values of the visual and company themes | `../slides-build/themes/visual.json`, `company.json` | `slides.py lint ../slides-build/themes/visual.json` |
| How to create a template, and what the template decides | `../slides-build/themes.md` and this file | `template.py` |
| Research history (minimum text size, contrast, number of colors) | 1-1, 1-5, and 1-6 of the workspace's `Research/deck_research/log/20261006_jp_visual.md`, and 「採用したもの」 in `Research/deck_research/state.md` | |

## Choosing the default theme

Switch `[slides] default_theme` (the theme to build with when the material's `description` does not decide it) by choosing from the existing templates. factory-init also uses this (including when it is installed through conversation).

1. Run `python3 $K/slides.py themes`. You can choose themes marked 「テンプレートあり」 and templates shown as 「（共有。…）」 or 「（個人。…）」 (those in `[drive] shared_themes` or in the Themes folder under `[drive] factory` that `[slides.templates]` in `factory.toml` does not point to). Themes marked 「テンプレートなし」 cannot be chosen (to create one, use [create.md](create.md) or `template.py <name> --from-base`).
2. Ask with a choice question (AskUserQuestion in Claude Code). Give each option its name and `description`, and mark the current default with 「（今の既定）」. There can be at most 4 options (the 「新しく作る」 option, when invoked without saying what to do, counts as one), so if there are more, show the list, offer the current default and those whose `description` seems to fit, and let the user name any other. If only one can be chosen, choose it without asking and go to 3.
3. Rewrite `[slides] default_theme` in `factory.toml` to the chosen name. If a shared or personal one was chosen, also run `slides.py theme <the URL shown>` (it copies the theme file and writes it to `[slides.templates]`, as the last line of `slides.py themes` says).
4. Run `slides.py themes` again and show that the chosen theme now has 「（既定）」.

## Limitations

- Pages other than 13.33 × 7.5 in cannot be built (step 2 of the flow in [create.md](create.md)).
- The font in the theme file applies only to slides. The font of documents (Google Docs) is `font` and `mono` in the document theme file of the same form (`themes/docs/<name>.json`) (docs-write-010 in `../docs-build/themes.md`). The copyright notice in the document footer stays `[brand]`.
- Only the `JP_FONTS` fonts and DM Sans can be written in `font` (`slides.py lint` and `template.py` reject others). To use another Latin font, measure its alphanumeric widths and add it to `FONT_EM` in `../deck-practices/scripts/brand.py` (check in rendered images which version Google Slides renders). To use another Japanese Google Font, check in a trial deck's images that it renders, then add it to `JP_FONTS` in `../deck-practices/scripts/brand.py`.
- The company template's text sizes, line spacing, and layouts do not apply to the pages `slides.py` builds (they are built in the style of `../slides-build/visual.md` §1). To build at the company's sizes, change the `slides.py` components (`factory-kaizen`).
- Do not adapt for Japanese the company template that people use on screen (with all its layouts).
- Colors not in the theme (`TEXT`, `RULE`, `RED_SOFT`, `STAGE_TEXT`, `DECOR`) and roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`) have no slot left in the master's color scheme (all 12 slots are used). When they are written in the theme file, `template.py` writes them into the alt text (the theme marker) of the master's page-number placeholder, and `slides.py build` builds with the theme file's values. If not written, every theme gets the same grays and light red. The chapter number on section dividers (`DECOR`, a decoration) may not match the company's `NAVY`, so write it if it does not.
- The master's logo is deleted. To place a logo, put it on the page as an image (JSON `image` or `icon`; `../slides-build/images.md`). Logos on the cover and divider layouts can be kept with `cover` and `section` (slides-theme-001).

## When editing

- After changing colors or fonts, edit the theme file, run `slides.py lint <file>`, and re-sync with `template.py <name>` (the ID does not change). For decks already made, rebuilding with `slides.py build` aligns the master's color scheme, font, and marker with the theme file's values (`../slides-build/themes.md`). If you changed role colors, look at the images of the rebuilt decks too, not only the template's samples.
- If you changed the template's colors or fonts in the on-screen theme builder, bring them back into the theme file with `slides.py theme <template URL> --force` (if you build without doing so, they revert to the theme file's values).
- If the template has no theme name (one not yet re-synced with `template.py`) or has another theme's name, `slides.py new` stops.
- When the company template is updated, pass the new URL to `--from-base` and recreate. Delete the old template or add 「旧」 to its name. If it is in the shared theme folder, remove it from the folder (otherwise two themes with the same name appear). Recreating changes the URL, so have users write the new URL too (re-syncing [without `--from-base`] keeps the URL, so it reaches them as is).
