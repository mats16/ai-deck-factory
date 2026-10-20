# Visual rules for documents (Google Docs)

Visual rules for building proposals, research reports, explanatory materials, and PoC plans in Google Docs (created on 2026-10-09). The slide rules ([visual.md](visual.md)) do not apply (§6 below). For how to write the content, see [content.md](content.md) (same as for slides); for how to build, see `../doc-build/SKILL.md`. The values are in the page area constants and `STYLES` of `docs.py` and are applied on every build, so do not write formatting in doc.md.

How each rule is checked (the "Verifying rules" section of [rules.md](rules.md)): "lint" (「lint が」) means `lint_gdoc` in `lint.py`, and "measured on images" (「画像で測る」) means `doc_layout.py` (`docs.py check` runs both. check also compares doc.md, the built document, and the template; `../doc-build/SKILL.md` §2). Rules with no tag are checked in review (the aspects in `../deck-review/prompt_doc.md`). The abbreviations in parentheses are reports in the workspace's `Research/deck_research/log/`: 「文書」 is `20261009_jp_doc_content_visual.md`, and 「Docs」 is `20261009_en_gdocs_generation.md`.

## 1. Page area, fonts, and line spacing

- **A4 portrait, 25 mm top and bottom, 30 mm left and right. Up to 40 full-width characters per line** (body 10.5pt on a 150 mm body width; the same as Word's Japanese default). lint checks the paper (`要修正` if not A4) and the characters per line (文書 1-12。jlreq・デジタル庁).
- **The font is Noto Sans JP** (Regular and Bold). Only code alphanumerics use Cascadia Mono. A company's document theme can change these (`font` and `mono` in doc-build-010 of `../doc-build/SKILL.md`). lint checks the fonts. For long documents read on paper, ask per material whether to use a Mincho font (文書 1-16).
- **Sizes:** body 10.5pt; H1 15pt, H2 12.5pt, H3 11pt (bold, navy); title 20pt; subtitle 11pt; table contents, figure and table captions, source lines, and footer 9pt; code 9.5pt. lint stops text under 9pt. The size, color, space above and below, and line spacing of the title, headings, and body can be changed in the `styles` of a company's document theme (doc-build-010 of `../doc-build/SKILL.md`).
- **Line spacing:** the line advance is "1.88 × the character size × the line spacing %" (Noto Sans JP; measured on PDF on 2026-10-09; differs from the % in Slides). Body 100% (a line gap of 0.88 characters), table contents, figure and table captions, and source lines 80% (a half-character gap, 「二分」), headings 75%, code 85% (文書 1-13。小林敏「行間の選択」).
- **Separate paragraphs with space after the paragraph (6pt), and do not indent.** Do not use empty paragraphs for spacing (lint: 「空の段落の連続」). Left-align. Do not use justified alignment until we have measured that it does not widen the spaces between Japanese and Latin text (文書 1-14・1-17).
- **The background is white. Colors are fixed by role:** headings and the table header row are navy `1B3139`, body `303F47`, supporting text (figure and table captions, source lines, quotes, footer) `5A6F77`, rules `DCE0E2`, code background `EEEDE9`, and links use Google Docs' default blue. [visual_doc-003] Use red only for the conclusion phrases in `***赤の太字***` (`CC2B17`), never for fills or lines. Because it is bold, the emphasis survives black-and-white printing (文書 1-10・2).
- **The footer** holds the copyright notice and the confidentiality label (the end of `NAME`; same as slides). Page numbers and a table of contents cannot be inserted through the API (`../doc-build/SKILL.md` §7). When a proposal or plan to be submitted needs page numbers, insert them in the UI.

## 2. Structure and headings

- **Do not make a cover page.** Put the title and subtitle (date and recipient) at the top of page 1 (`d.title`). Ask per material whether a proposal to be submitted needs a cover.
- **題には主題と文書の性格（提案・報告・計画・回答）を入れ、1 行に収める。** 「〜について」で終えない（lint が。文書 1-3。公用文作成の考え方）。
- **Make the first chapter the summary, and state the conclusion and what you ask of the reader (a decision, the next step) in its first paragraph.** Move details to later sections or an appendix (lint: 「冒頭に要旨がない」. Whether the summary alone is enough to decide is checked in review. 文書 1-1). Do not repeat the conclusion in a 「まとめ」 at the end (lint. Docs 1-15).
- **Before writing, write the page limit in the outline.** Compare it with the page count from `docs.py check`, and if it is over, cut the least needed parts first (文書 1-2).
- **Headings go at most three levels deep (H1 chapter, H2 section, H3 subsection).** Do not skip levels, do not give a level only one child (「2.1」 with no 「2.2」), do not use the same heading twice, do not end with a period, and do not use bold paragraphs instead of headings (they do not appear in the outline on the left). lint checks all of these (文書 1-4).
- [visual_doc-002] **見出し（H1〜H3）は短い名詞句にする**（「要旨」「背景」「いまの構成」、RFP の評価項目）。主張は段落の 1 文目で言う。見出しに句点を付けず、「〜ください」「〜します」で終えない（lint が出す。スライドの content.md の 4 と同じ考え方。文書 2）。
- Number headings in the heading text (「1. 要旨」, 「2.1 いまの構成」).

## 3. Paragraphs and sentences

- **One topic per paragraph. State the paragraph's point in the first sentence.** Check that reading only the first sentences in order gives a summary (the equivalent of "read only the headings in order" for slides). lint lists the headings and first sentences, and you read that list in review. A paragraph is 3–8 sentences; lint reports paragraphs of 9 or more (文書 1-5。木下是雄).
- **一文は 100 字まで**（lint が）。50〜60 字を超えたら、読みにくくないかを見る（文書 1-6）。
- **文体は、顧客向けなら です・ます、社内メモは だ・である**（content.md の 6）。本文の中で混ぜない（lint が「文体の混在」。引用と箇条書きは数えない）。
- **Use bullet lists for three or more parallel items.** Write reasons, conditions, and cause and effect as paragraphs. Do not make a bullet list with only one item (lint). In a list of sentences, every item ends with 「。」; in a list of words, none does (lint: 「句点の混在」). Do not start items with a bold label and a colon (lint) (文書 1-7、Docs 1-15).
- **Bold only conclusion phrases. At most three places per 1,000 characters of body text** (red bold counts too; lint. Docs 1-15. Documents written by AI tend to have more bold). Among those, keep red bold for the phrase you most want to get across (such as the conclusion of the summary). Do not put bold inside headings (lint).
- **文をコロンで終えて、箇条書きや表に続けない**（「次のとおりです：」）。文で言い切る（lint が。Docs 1-15）。
- 事実の文は名詞と動詞で書き、主観の修飾語（「大幅に」「非常に」）とぼかし言葉を 1 つずつ吟味する（文書 1-8）。
- So that the reader can act alone, also write the procedures, exceptions, and what they do not need to do. Do not fill gaps that have no basis with guesses (文書 1-9、Docs 1-14).

## 4. Tables and figures

- **Put 「表 N　題」 above the table and 「図 N　題」 below the figure** (the caption of `d.table` and `d.image`; docs.py numbers them in sequence). Do not combine them with chapter numbers. lint reports tables and figures without a caption (文書 1-10。JIS Z 8301).
- [visual_doc-001] **The first row of a table is the header row** (white bold on navy; the theme can change it via `TABLE_HEAD` and `TABLE_HEAD_TEXT` in `colors`; it repeats on the next page when the table spans pages). **Stretch tables from the left edge to the right edge of the body, keeping the left and right margins** (docs.py fits the column width ratios to the body width). Do not put a table inside a table. Keep text in cells short, and write long comparisons as paragraphs.
- **Write sources as links in the source line below tables and figures (`d.src`).** lint reports sections with numbers (H1, H2) that have no source link (content.md §6).
- **Figures are at most the body width** (lint. Spilling into the margins is measured on images). The approach to logos, icons, and architecture diagrams is the same as for slides (visual.md §6). Whether the text in a figure is large enough to read and whether the figure is blurry is checked in review. Draw mermaid diagrams with text the same size as the body; if shrinking to the body width brings it under 9pt, the build gives a warning (doc-build-009 of `../doc-build/SKILL.md`).
- Keep enclosures (quotes, code) few (文書 1-10).

## 5. What is measured on images

In JSON, page breaks and line wrapping are unknown. Measure them on the PDF that Google exports (`doc_layout.py`; `../doc-build/SKILL.md` §4).

- **A heading left at the end of a page.** The heading styles include 「次の段落と分離しない」 (keep with next) to prevent this, so if it appears, the formatting has come off.
- **Pages with 30% or more empty at the bottom** (except the last page and pages whose next page starts with H1). This happens easily with tables or figures pushed to the next page. Split the table, shrink the figure, or change the order.
- **Spilling into the left or right margins** (tables with fixed widths, large figures, left lines).
- **行頭の約物。** Google Docs は前の字ごと次の行に追い出すので、ふつうは出ない（Docs 1-10）。
- **1〜2 字だけの最終行。** 見出し・図表の題・表のセルなど短い段落だけを見る。本文の段落の最終行は直さなくてよい（行が長い文書は改行の頻度が低い。文書 2）。

## 6. Slide rules that do not apply to documents

| Slide rule (visual.md, content.md) | In documents |
|---|---|
| 1 行 15〜25 字、最終行は 3 字以上、文節で折る、1 つの箱は 8 行まで | 1 行は 40 字まで。本文の段落の改行の位置は直さない。行数の上限はない |
| Text is 11pt or larger | Body 10.5pt. Figure and table captions, source lines, table contents, and the footer may be 9pt |
| Line spacing 125–135% (Slides) | The Docs % computes line advance differently. Use the values in §1 above |
| Body background is Oat Light; the cover has a navy background | The background is white. Do not make a cover page |
| 見出しは短い名詞句、言い切りは 2〜3 枚。見出しとリードを順に読む | 見出しは名詞句。段落の 1 文目を順に読む |
| スライドの本文は常体か体言止め、です・ます は lint が出す（案内・依頼・注意書きのページは残してよい） | 顧客向けは です・ます。混在を lint が出す |
| Kicker, conclusion band, light bands, speaker notes | None. The summary paragraph replaces them |
