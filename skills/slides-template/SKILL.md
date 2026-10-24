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
- **When invoked without saying what to do** (just `/ai-deck-factory:slides-template`), start from "Choosing the default theme" below and add the option 「新しく作る（会社のテンプレートから）」. If that is chosen, go to "Flow".

## Where the rules live

The rules a template must meet when you adjust it. To change a value, edit the source of truth (to change it in the workspace, use the same path under `rules/`).

| Rule | Source of truth | What measures it |
|---|---|---|
| Color roles (11 slots and 6 fixed colors) and the contrast of each pair (4.5:1 for non-bold text under 18pt and bold text under 11pt; 3:1 for text 18pt and above and bold text 11pt and above) | `../slides-build/visual.md` §1 (table and notes) and §3 | `slides.py lint <theme file>` (the role pairs `PAIRS` in `template.py`), 「コントラストが基準に届かない色の組」 in `gslides.py check` |
| Font (default Noto Sans JP, Cascadia Mono for code only; the theme can change it; fonts not in Google Fonts cannot render) | `../slides-build/visual.md` §2, "Deliverables" in `../slides-build/SKILL.md`, "Fonts" below | lint's 「書体が … でない」 (compared with the template's font) |
| Text size (11pt or more; only the copyright notice and page number at 9pt) and page area (13.33 × 7.5 in, 0.6 in left and right margins, top edges of elements) | `../slides-build/visual.md` §1 | lint, constants in `slides.py` |
| Values of the visual and company themes | `../slides-build/themes/visual.json`, `company.json` | `slides.py lint ../slides-build/themes/visual.json` |
| How to create a template, and what the template decides | `../slides-build/themes.md` and this file | `template.py` |
| Research history (minimum text size, contrast, number of colors) | 1-1, 1-5, and 1-6 of the workspace's `Research/deck_research/log/20261006_jp_visual.md`, and 「採用したもの」 in `Research/deck_research/state.md` | |

## Choosing the default theme

Switch `[slides] default_theme` (the theme to build with when the material's `description` does not decide it) by choosing from the existing templates. factory-init also uses this (including when it is installed through conversation).

1. Run `python3 $K/slides.py themes`. You can choose themes marked 「テンプレートあり」 and templates shown as 「（共有。…）」 or 「（個人。…）」 (those in `[drive] shared_themes` or in the Themes folder under `[drive] factory` that `[slides.templates]` in `factory.toml` does not point to). Themes marked 「テンプレートなし」 cannot be chosen (to create one, use "Flow" below or `template.py <name> --from-base`).
2. Ask with a choice question (AskUserQuestion in Claude Code). Give each option its name and `description`, and mark the current default with 「（今の既定）」. There can be at most 4 options (the 「新しく作る」 option, when invoked without saying what to do, counts as one), so if there are more, show the list, offer the current default and those whose `description` seems to fit, and let the user name any other. If only one can be chosen, choose it without asking and go to 3.
3. Rewrite `[slides] default_theme` in `factory.toml` to the chosen name. If a shared or personal one was chosen, also run `slides.py theme <the URL shown>` (it copies the theme file and writes it to `[slides.templates]`, as the last line of `slides.py themes` says).
4. Run `slides.py themes` again and show that the chosen theme now has 「（既定）」.

## Flow

1. **Ask.** Which of the three cases below applies, the original template's URL, the company name on the cover (the name of the Japanese entity), the copyright notice, the brand's color rules (if there is a brand guide), and the theme name (lowercase English letters; e.g. `acme`).
2. **Read.** `python3 $K/template.py audit <original URL>`. It reports, without changing anything, the page size, the masters (with the number of pages using each) with their color schemes and contrast, the layouts and placeholders, the fonts (whether they render Japanese), the placeholder text sizes, and whether there is Japanese text.
   - If the page is not 13.33 × 7.5 in, `slides.py` cannot build (positions are fixed in inches). Copy the original, set the copy to 13.33 × 7.5 inches in its 「ファイル → ページ設定 → カスタム」, check on screen that the master and layouts are not broken, and read again with that URL.
   - `slides.py` can use only a layout whose only placeholder is the page number (audit's 「slides.py が使える Blank」). If there is none, `--from-base` stops. In the copy's theme builder, create a Blank layout or add a slide-number placeholder to the Blank layout.
3. **Assign colors to roles.** From the audit's color scheme, assign the company's colors to the roles in the table in `../slides-build/visual.md` §1. The role names come from Databricks colors, but what counts is the role (RED may be blue if that is the company's emphasis color).

   | Role | Color to assign (guide) |
   |---|---|
   | `NAVY` | Background of the cover and section dividers, the conclusion band, table header rows, and code boxes. Also the color of body-page heading text (`HEAD`) unless that is written. The company's darkest main color (often in DARK1 or ACCENT1) |
   | `BG`, `PANEL` | Body background, and the background of panels and of every other table row. The company's LIGHT1 and LIGHT2 (white, a very light gray) |
   | `RED` | Emphasis color (shape fills, number circles, text 18pt and above) |
   | `RED_TEXT`, `RED_ON_NAVY` | Same hue as `RED`, for text under 18pt and for text on `NAVY`. Write `RED` as is and match the brightness with lint's suggested fix |
   | `NAVY_BLOCK` | Blocks inside the section divider. `NAVY` made slightly lighter |
   | `SUB` | Secondary text and the footer. The company's gray |
   | `GA`, `PREVIEW`, `OSS` | Release-stage tags. Their colors are set by meaning, so normally do not write them (visual's values) |

   Write every role except `GA`, `PREVIEW`, and `OSS` (for themes with a light body background; for dark themes, see "Dark body themes" below). Roles not written take visual (Databricks) values and stand out among the company's colors (in a trial on 2026-10-12, visual's gray `NAVY_BLOCK` remained on a divider with a blue `NAVY`). Use at most 4 colors on one page (`../slides-build/visual.md` §3), so do not try to use all of the company's colors.
4. **Decide the font.** See "Fonts" below.
5. **Write.** Write the company name and copyright notice in `[brand]` in `factory.toml`, and the theme in the workspace's `themes/slides/acme.json` (the file name is the theme name; slides-theme-036 in `../slides-build/themes.md`).
   ```toml
   [brand]  # copyright notice at the lower left of the cover and of every page (also the document footer). copyright is required (factory-doctor checks it)
   company = "アクメ・ジャパン株式会社"
   copyright = "© 2026 Acme, Inc. All rights reserved."  # lint passes 9pt only for the form 「© <年> <社名> All rights reserved.」 (factory-doctor checks it)
   ```
   ```json
   {"apiVersion": "slides/v1", "kind": "theme",
    "description": "アクメの会社の色のテーマ。顧客に出す提案・説明と社外の登壇に使う。社内の勉強会には使わない（visual）",
    "font": "Noto Sans JP",
    "colors": {"NAVY": "002B5C", "BG": "FFFFFF", "RED": "E4002B", "…": "…"},
    "cover": ["Title Slide 1", "Title Slide 2"],
    "section": ["Section Break 1", "Section Break 2"]}
   ```
   - `description` says what the theme is, which materials and audiences it is for, and when not to use it (`../slides-build/themes.md`).
   - `colors` uses role names and 6-digit hex without `#`. Colors not in the theme (`TEXT`, `RULE`, `RED_SOFT`, `STAGE_TEXT`, `DECOR`) go in the same place. Replace the grays and the light red that do not match the main color (lint measures them). Roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`) default to NAVY, white, RULE, and white if not written. Write them for dark body themes ("Dark body themes" below).
   - Defaults if not written: `font` ("Fonts" below), `mono` (the monospace font for code), `copyright` (used instead of `[brand]` only for decks with this theme; same form as `[brand]`; factory-doctor checks it).
   - `cover` and `section` are the cover and chapter-divider patterns that keep shapes and logos (slides-theme-001; the order is the variant number). If not written, covers and dividers are also built on Blank. If you write only the names, `template.py` in step 7 measures the text width (`w`) and background brightness (`tone`) and writes them in.
6. **Measure.** `python3 $K/slides.py lint themes/slides/acme.json` (it does not read Google). It checks the format and the font, and prints the ratio of each role pair and suggested fixes for the pairs that fail (colors that keep the hue and saturation and change only the brightness). A suggested fix changes the company's brand colors, so show the user the colors before and after and let them decide (do not copy it silently). If you do not use a suggested fix, assign a different color. Repeat until NG is 0.
7. **Create.** `python3 $K/template.py acme --from-base <original URL>` (for case C, pass no URL). It copies the original into the Themes folder under `[drive] factory` (creating the folder if missing), keeps only the master and Blank, matches the color scheme, font, and page number, and builds the sample pages (cover, chapter divider, a quick reference of the theme's slots, a quick reference of the colors not in the theme, and 2 pages of components). The URL is written into `[slides.templates]` in `factory.toml` (do not copy it by hand), and the text width and background brightness of the covers and dividers are written into the theme file. Every theme value is written to the master (`slides.py theme <URL>` can restore them to a theme file).
8. **Check.** `python3 $K/gslides.py check <template URL>`. `要修正` must be 0. The only entries allowed in the contrast list are the thin text on the color swatches of the quick references (depending on a swatch's background color, neither white nor the tag text reaches 4.5:1; the default DECOR `6B8089` is 4.14:1 with white; on 2026-10-16 the user kept the current arrangement). Open every page image and check that the font renders (not Mincho or a different Gothic), check the company name and copyright notice, and check that the colors look natural next to the company's materials. Give the URL to the user to look at.
9. **Start using it.** To make it the default, rewrite `[slides] default_theme`. To choose it per deck, use `slides.py new <folder> <name> --theme acme`. To distribute it company-wide, place the template in the company-wide shared theme folder (`[drive] shared_themes`) (the Themes folder itself may serve as the shared theme folder). Templates made with `template.py` before 2026-10-14 have no theme name (`adf.theme`) in their Drive properties, so they do not appear in `slides.py themes` even when placed there. First, the owner re-syncs them with `template.py acme` (this also rebuilds the color scheme, font, and sample pages from the current theme file; they appear under 「共有テーマ」 in factory-doctor). Templates made before 2026-10-16 also have no theme values on the master (colors not in the theme, `copyright`, `mono`, `description`) until re-synced, and copying them drops those values. Other people only need to run `slides.py theme <template URL>` to build with the same values (slides-theme-032 in `../slides-build/themes.md`).

## Differences among the three cases

### A. A Japanese template exists

- **Font:** If audit's 「和文」 shows 「和文あり（Google Fonts）」, write that font in `font` and keep it. Fonts not in Google Fonts, such as メイリオ, 游ゴシック, and ヒラギノ, either cannot be rendered in Google Slides or turn into a different font. Replace them with a similar font from the table below, and tell the user the font before and after.
- **Text size:** Do not change the placeholder sizes of the master and layouts. The text sizes on pages that `slides.py` builds follow `../slides-build/visual.md` §1 (title 24pt, body 11pt or more, and so on).
- **Color:** Assign the company's color scheme to the roles, and change the brightness only of the colors that fail.

### B. Only an English template exists (e.g. the Japan branch of a foreign company)

Databricks's internal template (DM Sans, English only) is this case, and the visual and company themes were made from it (`../slides-build/themes.md`).

- **Font:** Latin fonts (DM Sans, Arial, Montserrat, and so on) have no Japanese glyphs. Google Slides renders Japanese in another Gothic, and you cannot choose which one. Choose a Google Fonts font with Japanese whose impression is close to the Latin font (table below). Latin letters and digits are also rendered in that font. Only DM Sans can be written in `font` as is (its alphanumeric widths are measured; Japanese becomes the Gothic that Google chooses). Ask the user whether to match the alphanumerics to the original company look or to unify the Japanese font, and decide.
- **Company name and copyright notice:** The company name on the cover is the Japanese entity's name (e.g. アクメ・ジャパン株式会社). The copyright notice may stay in the head office's English form.
- **Line spacing:** English templates have tight line spacing (title at 90%, and so on). `slides.py` writes the line spacing for each text, so the template's line spacing is not used. Line spacing for Japanese is in `../slides-build/visual.md` §2.
- The English sample pages and layouts are not kept in the created template.

### C. No template exists (make a new one)

- **Base:** Pass no URL to `--from-base`. It uploads a blank pptx (`../slides-build/assets/blank.pptx`: 13.33 × 7.5 in, layout Blank [only the page-number placeholder], slide numbers on, page-number placeholder padding 0), converts it to Google Slides, and builds from it.
- **When you make your own base** (for example, putting the company logo or shapes on the blank): upload `blank.pptx` to Drive, open it, convert it with 「ファイル → Google スライドとして保存」, and add to the converted file (without conversion it stays an Office file and the Slides API cannot be used). To start from a new presentation instead, set the following 3 things, add 「元」 to its name, place it in the Themes folder, audit it with that URL, and then pass it to `--from-base`.
  - Page size: a new presentation is 10 × 5.625 in. Set it to 13.33 × 7.5 inches in 「ファイル → ページ設定 → カスタム」 (the API cannot change it).
  - Slide numbers: turn them on with 「挿入 → スライド番号」. If they are off, added pages get no page-number placeholder and `--from-base` stops.
  - Page-number placeholder padding: a new presentation has 0.34 cm, which shifts the page number about 0.13 in down and 0.1 in left (`template.py` assumes an inner margin of 0). The API can neither read nor change it, so set the page-number placeholders of the master and Blank to 0 in the on-screen theme editor. Unused layouts may be deleted.
- **Color:** From the company's logo, website, or brand guide, decide the main color (`NAVY`) and the emphasis color (`RED`), and derive the other roles from them (the table in step 3). If there are no set colors, measure 2–3 candidate sets with `slides.py lint` before showing them. The visual colors are Databricks brand colors, so do not use them as is for another company's theme.
- **Font:** Noto Sans JP (the default; the character-width estimates are measured with this font).

## Dark body themes

A theme that makes even the body-page background (`BG`) dark (light text on a black background, like the website of a space or AI company). The roles are the same as in a light theme, but the colors assigned are reversed. Roles that a light theme covers with one color are split using the roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`).

| Role | Color to assign (guide) |
|---|---|
| `BG` | Body background. Black or a very dark gray |
| `NAVY` | Background of the cover and dividers, and of the conclusion band, table header rows, and code boxes. If it equals `BG`, the conclusion band cannot be seen, so use a gray one step lighter than `BG` (about `1A1A1A` if `BG` is `000000`). The cover and dividers also take this color |
| `PANEL`, `NAVY_BLOCK` | Panels and the blocks inside the divider. `PANEL` may equal `NAVY`. `NAVY_BLOCK` sits on the divider background (`NAVY`), so make it lighter than `NAVY` |
| `CARD` | Background of cards and table cells. About as dark as `BG` (enclosed by the `RULE` border) |
| `HEAD`, `TEXT`, `SUB` | Headings, body text, and secondary text. From a near-white color, progressively darker grays |
| `RULE` | Card borders and rules. A dark gray (a light one makes the borders stand out) |
| `SUB_ON_NAVY` | Notes on navy, and the footer of the cover and dividers. Because `RULE` is dark, write a light gray separately |
| `RED`, `RED_TEXT`, `RED_ON_NAVY` | Emphasis color. On a dark background, all three can often be the same light color |
| `ON_RED` | Text on a `RED` fill (number circles). If white does not reach the standard on a light emphasis color (white on orange `FF6308` is 2.98:1), black |
| `RED_SOFT`, `STAGE_TEXT`, `DECOR` | Background of small red tags: the emphasis color made very dark. Tag text: black. Chapter number: a gray that reaches 3:1 against the divider background (`NAVY`; also `BG` if there is a divider with a white background) (slides-visual-038) |

- Where to write the colors, how to measure them, and how to create the template are the same as for light themes (steps 5–8 of the flow). `slides.py lint` measures the same role pairs (`HEAD`, `TEXT`, `SUB`, and `RED_TEXT` on the body, panels, and cards; `WHITE` and `SUB_ON_NAVY` on navy; `ON_RED` on `RED`; and so on).
- The difference between the background and the panels or conclusion band is outside the text standard, and lint does not measure it. Dark colors look close to each other (`000000` and `1A1A1A` are 1.2:1), so check in the sample images whether the boundaries between surfaces can be seen.
- lint and `box_pad.py` tell covers and dividers apart not by background color but by whether `slides.py` built the page with a `NAVY` background. They tell cards apart by the theme's `CARD` color. If `PANEL` has the same value as `NAVY`, a panel that spans the full body width down to the bottom of the page (6.60 in) is counted as a conclusion band, and code-like lines inside the panel are required to be monospace.
- Materials whose page JSON (pages.py) writes heading text as `NAVY` and card backgrounds as `WHITE` become unreadable in a dark theme (write `HEAD` and `CARD`; `../slides-build/visual.md` §1). They appear in lint's contrast list.

## Fonts

Google Slides renders only Google Fonts. The Japanese fonts confirmed to render are `JP_FONTS` in `slides.py` (on 2026-10-07, the same text was rendered in each font in a trial deck copied from the template).

| Impression of the original font | Google Fonts candidates with Japanese |
|---|---|
| Ordinary Gothic (Arial, Helvetica, Roboto, DM Sans, Inter, メイリオ, 游ゴシック, ヒラギノ角ゴ) | Noto Sans JP (default), IBM Plex Sans JP (companies that use IBM Plex), BIZ UDPGothic (companies that put readability first) |
| Geometric Gothic (Montserrat, Poppins, Futura) | Zen Kaku Gothic New, M PLUS 2, LINE Seed JP |
| Rounded Gothic | M PLUS Rounded 1c, Zen Maru Gothic |
| Mincho / serif (Times, Georgia, Garamond) | Noto Serif JP, Shippori Mincho, Zen Old Mincho, BIZ UDPMincho |

- `Noto Sans CJK JP`, `Hiragino Sans`, and `Yu Gothic` are accepted by the API but render as Mincho and a Latin serif (`NO_RENDER` in `template.py`). `Meiryo` rendered as a Gothic, but it could not be confirmed to be Meiryo itself (do not use it).
- `BIZ UDGothic` and `Kosugi Maru` have monospaced alphanumerics, so the spacing between letters looks wide.
- Whether a font rendered cannot be told from the API's values (it returns the specified name as is). Check the images of the sample pages.
- The only Latin font that can be written in `font` is DM Sans (`FONT_EM` in `slides.py`). It has no Japanese glyphs, so Google Slides renders Japanese in another Gothic (rendered and checked on 2026-10-15: about 0.92 em per character, a little narrower than the assumed 1 em). `template.py audit` prints 「欧文（和文は別のゴシック。字幅を測ってあり、font に書ける）」.
- The width estimate in `slides.py` (`em_width`) assumes body alphanumerics at the `FONT_EM` width (Noto Sans JP's `ASCII_EM`, DM Sans's `DM_SANS_EM`; for bold, each Bold's `ASCII_BOLD_EM` and `DM_SANS_BOLD_EM`) and code at `MONO_EM` (Cascadia Mono). If another font is written in `font` or `mono`, it still estimates with the Noto Sans JP and Cascadia Mono widths, so the alphanumeric widths differ and the wrap estimates (build-time warnings, `d.card` height, lint's line counts) drift. Check the images of the sample pages and of the built material.
- The default monospace font for code is Cascadia Mono. The theme's `mono` changes it (in the slide and document theme files: `themes/slides/<name>.json` and `themes/docs/<name>.json`). Monospace text carries no Japanese, so it is not limited to `JP_FONTS`, but fonts with ligatures (`LIGATURE_MONO` in `slides.py`: JetBrains Mono, Fira Code, Cascadia Code) are rejected (`../slides-build/visual.md` §2). A name not in Google Fonts is accepted by the API and silently rendered in another font (Arial). After writing it, rebuild the sample pages with `template.py <name>` and check in the `gslides.py check` images that code renders monospaced and that `->` has not turned into a single arrow glyph.
- The list of checked fonts is in 「書体」 of the repository README.

## Limitations

- Pages other than 13.33 × 7.5 in cannot be built (step 2 above).
- The font in the theme file applies only to slides. The font of documents (Google Docs) is `font` and `mono` in the document theme file of the same form (`themes/docs/<name>.json`) (docs-write-010 in `../docs-build/SKILL.md`). The copyright notice in the document footer stays `[brand]`.
- Only the `JP_FONTS` fonts and DM Sans can be written in `font` (`slides.py lint` and `template.py` reject others). To use another Latin font, measure its alphanumeric widths and add it to `FONT_EM` (check in rendered images which version Google Slides renders). To use another Japanese Google Font, check in a trial deck's images that it renders, then add it to `JP_FONTS` in `slides.py`.
- The company template's text sizes, line spacing, and layouts do not apply to the pages `slides.py` builds (they are built in the style of `../slides-build/visual.md` §1). To build at the company's sizes, change the `slides.py` components (`factory-kaizen`).
- Do not adapt for Japanese the company template that people use on screen (with all its layouts).
- Colors not in the theme (`TEXT`, `RULE`, `RED_SOFT`, `STAGE_TEXT`, `DECOR`) and roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`) have no slot left in the master's color scheme (all 12 slots are used). When they are written in the theme file, `template.py` writes them into the alt text (the theme marker) of the master's page-number placeholder, and `slides.py build` builds with the theme file's values. If not written, every theme gets the same grays and light red. The chapter number on section dividers (`DECOR`, a decoration) may not match the company's `NAVY`, so write it if it does not.
- The master's logo is deleted. To place a logo, put it on the page as an image (JSON `image` or `icon`; `../slides-build/images.md`). Logos on the cover and divider layouts can be kept with `cover` and `section` (slides-theme-001).

## When editing

- After changing colors or fonts, edit the theme file, run `slides.py lint <file>`, and re-sync with `template.py <name>` (the ID does not change). For decks already made, rebuilding with `slides.py build` aligns the master's color scheme, font, and marker with the theme file's values (`../slides-build/themes.md`). If you changed role colors, look at the images of the rebuilt decks too, not only the template's samples.
- If you changed the template's colors or fonts in the on-screen theme builder, bring them back into the theme file with `slides.py theme <template URL> --force` (if you build without doing so, they revert to the theme file's values).
- If the template has no theme name (one not yet re-synced with `template.py`) or has another theme's name, `slides.py new` stops.
- When the company template is updated, pass the new URL to `--from-base` and recreate. Delete the old template or add 「旧」 to its name. If it is in the shared theme folder, remove it from the folder (otherwise two themes with the same name appear). Recreating changes the URL, so have users write the new URL too (re-syncing [without `--from-base`] keeps the URL, so it reaches them as is).
