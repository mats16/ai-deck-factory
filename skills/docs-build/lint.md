# lint and the image measurements for documents

Open when you read the output of `docs.py check`, or when deciding whether a `要確認` may stay.

## lint (Docs rules)

The content and sources of the rules are in `visual.md` and `content.md`. They are `lint_gdoc` in `scripts/doc_lint.py`; the text rules shared with slides are in `../deck-practices/scripts/textlint.py`.

- **List of headings and first sentences of paragraphs:** Lays out the headings by level and lists the first sentence of each paragraph. Check that the story holds with headings alone, and that reading the first sentences in order gives a summary (visual.md §3). It also prints the **body character count** and **characters per line**.
- **`要修正` (exit 1):** emoji, long dashes, leftover placeholders, replacement tags, fonts other than the theme's font (default Noto Sans JP) (monospace fonts for code pass), Japanese in the monospace font, text under 9pt, paper that is not A4, links with tracking markers (`utm_source=`), Japanese periods (「。」) in headings (including mid-sentence ones), and headings and titles that end in 「〜ください」「〜します」 (visual.md §2).
- **`要確認`:** the same text rules as for slides (empty phrases, fear-mongering, missing spaces between Japanese and Latin text, spaces around punctuation marks, leftover 「要確認」 or TBD, confidentiality labels, and so on), source lines without links, and numbers not in the 「出典の表」 (`出典の表にない数字`, deck-lint-026; when `docs.py check` runs with the document's folder). Document-only ones (values and sources in visual.md):
  - Sentences: mixed writing style (「です・ます」 and 「だ・である」 at sentence ends in body paragraphs. Reports the less frequent one), sentences over 100 characters, paragraphs of 9 or more sentences, a page area with more than 40 characters per line
  - Headings: skipped levels, level 4 or deeper, only one child, duplicates, bold inside headings, headings with no content, bold paragraphs used instead of headings, titles ending in 「について」, a first chapter that is not a summary, a trailing 「まとめ」
  - Tables and figures: missing table or figure titles, figures wider than the body, sections (per H1 and H2) whose numbers have no source link
  - Habits typical of AI-made documents (Docs 1-15): too much bold (more than 3 places per 1,000 body characters), bullets that start with bold and a colon, sentences that end in a colon, lists with only one item, mixed use of periods across bullets, runs of empty paragraphs
- Slide-only rules (「です・ます」, 8 body lines, conclusion band, notes, section dividers) are not checked.
- [docs-lint-005] **Do not report what the template or theme decides** (it would appear every time and people would learn to skip it): 「冒頭に要旨がない」 for documents written from a template and for template samples (doc.md header has `template:` or `source:`) (the template decides the section order), 「1 行の字数が多い」 for themes on paper other than A4 (`page` in `themes/docs/<name>.json`), and 「図の題がない」 for a figure directly followed by a page break (the cover logo).
- **Log:** Written to the same `.factory/lint_runs.jsonl` as for slides, and counted with `textlint.py --stats` (in `../deck-practices/scripts/`) (step 5 of `dreaming/run.md`). Documents whose names contain tmp, 「作業用」, or 「テンプレート」 are not logged.

## What is measured on images (doc_layout.py)

The JSON does not tell where pages break or where lines wrap. These are measured on the Google-rendered PDF and reported as 「要確認（画像で測った）」.

- **Heading at the end of a page:** Headings use the "keep with next" style, so if this appears, the formatting has come off.
- **Punctuation at the start of a line:** Google Docs pushes it to the next line together with the preceding character, so it usually does not appear. If it does, suspect the font or the paragraph formatting.
- **Last lines of only 1–2 characters:** Only short paragraphs (up to 80 characters) such as headings, figure and table titles, and table cells are checked. Do not fix the last line of body paragraphs (visual.md §5).
- **Overflow into the margins:** Anything drawn in the left or right margin (30 mm). Tables with fixed widths, large figures, the left line.
- **Pages with empty space at the bottom:** Pages where the bottom 30% or more of the body area is empty (except the last page and pages whose next page starts with H1). Suspect a table or figure pushed to the next page.
