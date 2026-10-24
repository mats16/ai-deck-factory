# Create a template from a company template

Open from `SKILL.md` when creating a template. `SKILL.md` has what a template decides, the rules a template must meet ("Where the rules live"), the limitations, and what to do when editing.

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

   Write every role except `GA`, `PREVIEW`, and `OSS` (for themes with a light body background; for dark themes, see [dark.md](dark.md)). Roles not written take visual (Databricks) values and stand out among the company's colors (in a trial on 2026-10-12, visual's gray `NAVY_BLOCK` remained on a divider with a blue `NAVY`). Use at most 4 colors on one page (`../slides-build/visual.md` §3), so do not try to use all of the company's colors.
4. **Decide the font.** See [fonts.md](fonts.md).
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
   - `colors` uses role names and 6-digit hex without `#`. Colors not in the theme (`TEXT`, `RULE`, `RED_SOFT`, `STAGE_TEXT`, `DECOR`) go in the same place. Replace the grays and the light red that do not match the main color (lint measures them). Roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`) default to NAVY, white, RULE, and white if not written. Write them for dark body themes ([dark.md](dark.md)).
   - Defaults if not written: `font` ([fonts.md](fonts.md)), `mono` (the monospace font for code), `copyright` (used instead of `[brand]` only for decks with this theme; same form as `[brand]`; factory-doctor checks it).
   - `cover` and `section` are the cover and chapter-divider patterns that keep shapes and logos (slides-theme-001; the order is the variant number). If not written, covers and dividers are also built on Blank. If you write only the names, `template.py` in step 7 measures the text width (`w`) and background brightness (`tone`) and writes them in.
6. **Measure.** `python3 $K/slides.py lint themes/slides/acme.json` (it does not read Google). It checks the format and the font, and prints the ratio of each role pair and suggested fixes for the pairs that fail (colors that keep the hue and saturation and change only the brightness). A suggested fix changes the company's brand colors, so show the user the colors before and after and let them decide (do not copy it silently). If you do not use a suggested fix, assign a different color. Repeat until NG is 0.
7. **Create.** `python3 $K/template.py acme --from-base <original URL>` (for case C, pass no URL). It copies the original into the Themes folder under `[drive] factory` (creating the folder if missing), keeps only the master and Blank, matches the color scheme, font, and page number, and builds the sample pages (cover, chapter divider, a quick reference of the theme's slots, a quick reference of the colors not in the theme, and 2 pages of components). The URL is written into `[slides.templates]` in `factory.toml` (do not copy it by hand), and the text width and background brightness of the covers and dividers are written into the theme file. Every theme value is written to the master (`slides.py theme <URL>` can restore them to a theme file).
8. **Check.** `python3 $K/gslides.py check <template URL>`. `要修正` must be 0. The only entries allowed in the contrast list are the thin text on the color swatches of the quick references (depending on a swatch's background color, neither white nor the tag text reaches 4.5:1; the default DECOR `6B8089` is 4.14:1 with white; on 2026-10-16 the user kept the current arrangement). Open every page image and check that the font renders (not Mincho or a different Gothic), check the company name and copyright notice, and check that the colors look natural next to the company's materials. Give the URL to the user to look at.
9. **Start using it.** To make it the default, rewrite `[slides] default_theme`. To choose it per deck, use `slides.py new <folder> <name> --theme acme`. To distribute it company-wide, place the template in the company-wide shared theme folder (`[drive] shared_themes`) (the Themes folder itself may serve as the shared theme folder). Templates made with `template.py` before 2026-10-14 have no theme name (`adf.theme`) in their Drive properties, so they do not appear in `slides.py themes` even when placed there. First, the owner re-syncs them with `template.py acme` (this also rebuilds the color scheme, font, and sample pages from the current theme file; they appear under 「共有テーマ」 in factory-doctor). Templates made before 2026-10-16 also have no theme values on the master (colors not in the theme, `copyright`, `mono`, `description`) until re-synced, and copying them drops those values. Other people only need to run `slides.py theme <template URL>` to build with the same values (slides-theme-032 in `../slides-build/themes.md`).

## Differences among the three cases

### A. A Japanese template exists

- **Font:** If audit's 「和文」 shows 「和文あり（Google Fonts）」, write that font in `font` and keep it. Fonts not in Google Fonts, such as メイリオ, 游ゴシック, and ヒラギノ, either cannot be rendered in Google Slides or turn into a different font. Replace them with a similar font from the table in [fonts.md](fonts.md), and tell the user the font before and after.
- **Text size:** Do not change the placeholder sizes of the master and layouts. The text sizes on pages that `slides.py` builds follow `../slides-build/visual.md` §1 (title 24pt, body 11pt or more, and so on).
- **Color:** Assign the company's color scheme to the roles, and change the brightness only of the colors that fail.

### B. Only an English template exists (e.g. the Japan branch of a foreign company)

Databricks's internal template (DM Sans, English only) is this case, and the visual and company themes were made from it (`../slides-build/themes.md`).

- **Font:** Latin fonts (DM Sans, Arial, Montserrat, and so on) have no Japanese glyphs. Google Slides renders Japanese in another Gothic, and you cannot choose which one. Choose a Google Fonts font with Japanese whose impression is close to the Latin font (the table in [fonts.md](fonts.md)). Latin letters and digits are also rendered in that font. Only DM Sans can be written in `font` as is (its alphanumeric widths are measured; Japanese becomes the Gothic that Google chooses). Ask the user whether to match the alphanumerics to the original company look or to unify the Japanese font, and decide. Matching the original works as is only for DM Sans; for another Latin font (Montserrat and so on), say that its alphanumeric widths must be measured and added first ("Limitations" in [SKILL.md](SKILL.md)), or choose the Japanese font.
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
