# Docs API pitfalls

Open when you change `docs.py`, write raw requests, or a build fails in an unexpected way.

## Docs API pitfalls

Things we tried and confirmed on 2026-10-09 (for Docs, the workspace's `Research/deck_research/log/20261009_en_gdocs_generation.md`).

- **Named styles:** Put `namedStyleType` in the `fields` of `updateNamedStyle` (without it, 400 「Named style type is required」). No template document is needed.
- **Indentation:** The position of the first line is `indentFirstLine` (position from the left edge), and `indentStart` applies from line 2. A one-line paragraph does not move with `indentStart` alone. Set both.
- **Left line (`borderLeft`):** It is drawn to the left of the text's left edge by `padding` plus the line width. Unless you indent by that amount, it overflows into the margin (`d.quote` indents 11pt and puts the line at the body's left edge).
- **Inherited formatting:** Inserted text and paragraphs inherit the formatting of where they were inserted. docs.py reapplies paragraph and text formatting per paragraph (`P_FIELDS`, `T_FIELDS`. Fields not written fall back to the named style).
- **Tables:** `insertTable` inserts one newline before the table. docs.py makes that paragraph the table title. Get cell positions from the JSON after insertion, and fill from the last cell backward (so earlier cell positions do not shift).
- **A line break within a paragraph is `\v`.** The code background does not break between lines.
- **Shading (`shading`) has no inner padding.** Add a border of the same color as the shading and get padding from its `padding`. The border sticks out by the indentation, so put padding plus line width into `indentStart`, `indentFirstLine`, and `indentEnd` to align with the body edges (`d.code`).
- **Text positions are in UTF-16 units** (`u16` in `slides.py`).
- **Line spacing:** Line pitch is "1.88 × font size × line spacing %" (Noto Sans JP. Measured in the PDF by building an 11-line paragraph at 70, 85, and 100%). At 120% it became 2.3 times and looked loose.
- **Punctuation at the start of a line:** Text has no language field (`TextStyle` has no `language`), but Google Docs pushes it to the next line together with the preceding character.
- **Bullet symbols and numbers are rendered in Arial.** There is no request to change list formatting.
- **Page numbers and tables of contents cannot be inserted with the API.** If page numbers are needed, insert them in the UI with 「挿入 > ページ番号」. docs.py does not touch existing footers, so they survive rebuilds (the first `build` after inserting stops as a UI edit, so use `--force`). For a table of contents, the outline on the left of Google Docs is often enough.
- **UI edits are detected by a fingerprint of the body.** `revisionId` is officially documented as "valid for only 24 hours and may change for internal reasons", so it stops even without edits. docs.py stores a fingerprint of the body right after building (the body of `documents.get`) in appProperties and compares against it. The build time (`modifiedTime`) cannot be compared, because the write that stores the fingerprint itself advances it. Formatting-only edits also change the fingerprint, so it stops.
- **Comments:** If you delete everything and rebuild, comments lose their anchors and remain unresolved (Docs 1-1). `docs.py build` stops if there are unresolved comments, printing the text they were attached to and their content.
- **Two numbered lists in a row may continue the numbering** (`createParagraphBullets` joins the immediately preceding list of the same type. Docs 1-9). Put a normal paragraph between them.
- **Tabs:** docs.py builds and checks only the first tab. Documents split into tabs are not handled.
- **Images:** Only PNG, JPG, and GIF can be read by URL. Turn SVG URLs into PNG with `png()`. Local images are pasted via a temporary URL (30 minutes) made by `carry`, which then deletes the temporary file.
