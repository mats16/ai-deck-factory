---
name: docs-build
description: Write Japanese documents (proposals, research reports, explanatory materials, PoC plans) in markdown (build/doc.md), build them in Google Docs with docs.py, and check and fix them with docs.py check (lint, page images, matching against the template). When delivering as Word, export from Google Docs. Always use before you start writing a document and before you deliver it.
---

# Build and finish Japanese documents in Google Docs

[docs-write-001] Documents are built directly in Google Docs with the Docs API (history in `Research/gdocs_pipeline_20261009.md`). The source of truth for the content is the material's `build/doc.md` (markdown); docs.py builds it with named styles and a theme, and rebuilds it to the same URL (moved from doc.py on 2026-10-10. §1 below). The visual rules are in [visual.md](visual.md), and how to write the content is in `../deck-practices/content.md` (same as slides). Slides are in `../slides-build/`. Where to place the document on Drive is `../deck-practices/drive.md`.

| What you make | Read before you start writing |
|---|---|
| Google Docs (default) | This file and [visual.md](visual.md) (the visual rules for documents) |
| A document written from a workspace template (`rules/docs-build/templates/<name>/doc.md`), or making or fixing a template | [templates.md](templates.md), in addition to the two above |
| Writing a document theme file (`themes/docs/<name>.json`) | [themes.md](themes.md) |
| Reading `docs.py check` and lint output | [lint.md](lint.md) |
| Changing `docs.py`, or a build that fails or looks wrong in an unexpected way (Docs API pitfalls) | [api.md](api.md); after editing `docs.py`, `doc_lint.py`, or `doc_layout.py`, also the bullet 「When you edit docs.py, doc_lint.py, or doc_layout.py」 in [templates.md](templates.md) (selftests and rebuilding the template samples) |

```sh
K=<docs-build folder>/scripts   # the folder that holds this file. From other skills, ../docs-build/scripts relative to that skill's folder. docs.py imports the parts shared with slides (gapi.py, textlint.py, brand.py, sheet.py) from ../deck-practices/scripts
cd <folder>/build
python3 $K/docs.py init <template name>                      # when the workspace has a template and you start from it (copies doc.md. templates.md)
python3 $K/docs.py new <Drive folder URL> <YYYYMMDD_name>   # first build. Write the printed URL in the outline and tell the user right away (deck-drive-003 in ../deck-practices/drive.md)
python3 $K/docs.py build <URL>                                    # rebuild after edits (the URL does not change. Stops if someone edited in the UI)
python3 $K/docs.py check <URL>                                    # check (§2 below. exit 1 if there is 要修正)
python3 $K/docs.py export <URL> /tmp/<material name>.docx                 # only when the counterpart asks for Word ([lint.md](lint.md))
```

## 1. Writing doc.md and the check loop

### 1.1 Workflow

[docs-write-002] First settle the content in markdown, then build it with the template through the API, and repeat checking and fixing. As with slide page JSON, **edit doc.md (content) and docs.py's themes and components (appearance); do not edit the built document by hand**. Do not upload markdown and then edit the resulting document to bring it closer to the template (the edits live only in the document and are lost when you upload again).

1. Create doc.md with `docs.py init <template>` (if there is no template, start writing in the format of §1.2 below).
2. Write the content. Write the content agreed in the outline into doc.md without waiting for the user (deck-flow-006 in `../deck-practices/SKILL.md`). If the user says they want to settle the content in doc.md, you may do so (what readers see is the built Google Docs).
3. Build with `docs.py new` (first time) or `docs.py build`, and check with `docs.py check`.
4. Bring `要修正` to 0, check each `要確認` one by one, and open and look at the images ([lint.md](lint.md)). Put fixes into doc.md or docs.py, and go back to 3.
5. Before returning a newly made document, run `/deck-review` (`../deck-review/SKILL.md`). Put the findings into doc.md as well and rebuild. For fixes after delivery, run only the scope decided by deck-flow-017 in `../deck-practices/revise.md`.

### 1.2 doc.md format

Write the material's information in the header (between `---` lines) and markdown in the body. Do not write formatting. Font, size, color, and spacing are decided by docs.py's named styles (`STYLES`) and the theme, and are reapplied on every build (changing `STYLES` affects every material you rebuild). The text notation is the same as for slides (the "Text markup" item in `../slides-build/pages.md`. The size notation `{32:…}` is slides only).

````markdown
---
name: Acme様_Lakebase導入の検討｜Internal Only   # only the trailing confidentiality label (Internal Only, Confidential) appears in the footer
theme: acme                                      # the workspace's themes/docs/acme.json. If omitted, the default (A4, 10.5pt, navy headings)
template: proposal                               # when written from a template (check matches against it)
title: Lakebase の導入の検討について              # title and subtitle (subtitle:) of a material without a cover
---

# 1. 要旨

結論は「***分析と同じ基盤で管理したい表から移す***」です。
費用は[公式の価格表](https://www.databricks.com/product/pricing/lakebase)で見積もりました。

表: いまと移したあとの比較 {widths: 40 65 65}
| 項目 | いま | 移したあと |
|---|---|---|
| 写しの遅れ | 最大 24 時間 | 数秒 |

出典: [Lakebase の docs](https://docs.databricks.com/aws/ja/oltp/)

![BigQuery](gcp/bigquery.png){width=120}

図: 写しの流れ
```mermaid
flowchart LR
  A[(基幹の DB)] -->|数秒| B[Lakebase] --> C[分析]
```
````

| Syntax | What is built |
|---|---|
| Header `name`, `theme`, `template`, `omit` | Material name, theme, template to match against, and sections of the template to leave out (`  - <section name>` under `omit:`) |
| Header `cover:` (a list of `  - <line>`) and `cover_left` | A cover page. Places the title lines large in the center, puts the left-hand words (such as the company name) and our own logo (`[brand] logo` in `factory.toml`; not placed if absent) side by side below, and breaks the page. Only when the template has a cover |
| Header `title`, `subtitle` | Title and subtitle (date, addressee, and so on) at the top of page 1. No cover page is made (visual.md §2) |
| `#`, `##`, `###` | Headings (H1–H3). Write numbers as text (「1. 要旨」). Go in order from H1 and do not skip levels |
| Paragraph | Separate with blank lines. You may break lines after 「。」 (they are joined when built; a space is inserted only between alphanumerics). `**bold**`, `***red bold***` (only for the key phrase of a conclusion. visual.md §3), `[text](URL)`, `` `code` ``, `<br>` (line break within a paragraph). Links and code can go inside bold and red (`***[text](URL)***`). Escape literal symbols with `\`, such as `\*` |
| Paragraph starting with `出典: …` | Source line (below tables and figures. 9pt, supporting color). Add a link (content.md §6) |
| `- `, `1. ` | Bullet lists (numbered). Items indented 2 or more spaces are level 2. Keep an introductory paragraph on the same page as the list or table that follows |
| `表: <title> {widths: 30 80 40}` with a `\|` table right below | Table. Row 1 is the header row (repeated at the top of the next page when the table crosses pages). The title appears above the table as 「表 N　…」. `widths` are ratios of column widths; the table spans from the left to the right edge of the body. Line breaks in a cell are `<br>`, a vertical bar is `\\|` |
| `![<title>](<image>){width=150}` | Figure. The image is a path inside `assets/` (`"gcp/bigquery.png"`), a path from build/, or a URL. Width is in mm (write it for a body width of 150 mm; if the theme widens the body, it scales by that ratio). The title appears below the figure as 「図 N　…」 |
| `図: <title> {width: 120}` with ```` ```mermaid ```` right below | A mermaid diagram ([syntax](https://mermaid.js.org/intro/)). docs.py draws it as PNG with the local mermaid-cli and places it as a figure (docs-write-009 below). The `図:` line can be omitted (no title). A `図:` line not followed by ```` ```mermaid ```` stays a body paragraph. Width is in mm, as for `![…]`; if omitted, it is the width at which the diagram text is the same size as the body (the body width if that exceeds it). Usually omit it |
| `> …` | Quote (customer voice, notes to the template's writer). Draws a line on the left and uses the supporting color |
| ```` ``` ```` | Code and commands. Alphanumerics in the monospace font (default Cascadia Mono), Japanese in the body font (default Noto Sans JP) |
| `\newpage` | Page break (before an appendix, and so on) |
| `<!-- … -->` | Notes that are not built (the material it was based on, reasons for changes) |

- docs.py numbers figures and tables in order of appearance. When the body refers to them, as in 「表 1 のとおり」, check the number in the text after building.
- Check each build warning (the number of column widths does not match the columns, a figure is wider than the body, the line after `表:` is not a table) one by one.
- **Theme:** The default is A4, 10.5pt body, navy headings (visual.md §1). When the workspace has document themes (`docs.py themes` prints names and descriptions), choose one per material (step 5 in `../deck-practices/start.md`) and write `theme: <name>` in the header (a doc.md written from a template keeps the template's theme; check reports a different one as `要修正`). `docs.py new` stops and prints the list if themes exist and `theme:` is missing (write `theme: standard` to keep the default). To write a theme file or read its keys, open [themes.md](themes.md) (docs-write-010).
- How to choose images and where they come from (`assets/README.md`, Iconify, each company's icons) is the same as for slides (`../slides-build/images.md`). To draw a figure in Google Slides and paste it, turn it into an image with `gslides.py thumb` and then place it with `![…](…)`.
- [docs-write-009] **mermaid:** Write diagrams that boxes and arrows are enough for (flows, sequences, states, and so on) as ```` ```mermaid ```` in doc.md (the content stays in doc.md, rebuilding after an edit changes the diagram too, and GitHub shows it as is). Architecture diagrams that need icons or logos are drawn in Google Slides and pasted. docs.py draws locally with mermaid-cli (`@mermaid-js/mermaid-cli` with a pinned version via `npx`. `MERMAID_CLI` in `docs.py`. The first run takes a few minutes. Needs Node.js). Do not use a local `mmdc` of unknown version (rendering changes between versions and no longer matches the PNG fingerprint). Do not give diagram content to outside services (such as mermaid.ink) (`../slides-build/assets/README.md`). Colors come from the theme's `colors` (box background `PANEL`, border `HEAD`, lines `SUB`, text `TEXT`), the font is the theme's body font, and text is drawn at the same size as the body. The font is whatever is installed locally (if it is not installed, another Gothic font is used, so check on the images). The PNG is placed at `build/mermaid/<fingerprint>.png` and not redrawn if the content, colors, font, and mermaid-cli version are the same (each build deletes unused PNGs). The local fonts and the Chrome that mermaid-cli fetches are not part of the fingerprint, so to redraw after replacing them, delete `build/mermaid/` and rebuild. If shrinking to the body width makes the diagram text smaller than 9pt, a build warning appears (for wide diagrams use `flowchart TB` or split the diagram). Syntax errors stop with the mermaid-cli output.

### 1.3 Templates

If the workspace has a template for this kind of document (`rules/docs-build/templates/<name>/doc.md`), start from it with `docs.py init <name>`. How to write from a template, what check matches against it, and how to make or fix one: [templates.md](templates.md).

## 2. What docs.py check does

It writes the document's JSON, text (`text.md`), PDF, and page images to `/tmp/docs_<first 8 chars of the ID>/`, runs the lint and the layout measurements, and matches the build against doc.md, the template, and the original document. Exit 1 if there is `要修正`. The steps and what each match finds: "What docs.py check does" in [lint.md](lint.md).

## 3. Reading the results

- **Images:** After building, open and look at the images of all pages yourself, and fix. Look at table column widths and wrapping, figure sizes, whether a figure and its title or a table and its title are split across pages, spacing between paragraphs, and headings left at the end of a page. Judge the finish by these Google-rendered images.
- **Text:** Read `text.md` for missing content or wrong order.
- **lint:** Bring `要修正` to 0. Check each `要確認` one by one, and either fix it or be able to say why it stays (example: 「顧客の発言の引用に だ・である が残るのはよい」).
- **Before delivering:** Review a newly made document as a whole with `/deck-review <Google Docs URL>` (`../deck-review/SKILL.md`) before returning it to the user. For fixes after delivery, run only the scope decided by deck-flow-017 in `../deck-practices/revise.md`.
- When checking is done, you may delete `/tmp/docs_<ID>/`. Do not keep it in the material's folder.

## 4. Deliverables and Drive

- **Deliver as a Google Docs URL. Do not make PDFs.** Only when the counterpart asks for Word, export to docx with `docs.py export` and give that (the Google Docs on Drive is the source of truth. Do not edit the exported docx).
- [docs-write-006] **Location, name, renaming, and sharing are the same as for slides** (`../deck-practices/drive.md`). Customer-facing ones go in the customer's folder under the shared drive's `10_Customers` (「Google Drive の置き場所」 in `references_index.md`); ones not tied to a customer (internal) go in a topic folder under `drive.docs` in `factory.toml` (Docs inside AI Deck Factory), separate from the Slides folder for slides. The name is `YYYYMMDD_<material name>`. Add the materials you made to 「Google Drive の置き場所」 in `references_index.md`, and write the URL in the outline and the report.
- **Do not edit in the UI; edit doc.md and rebuild.** Rebuilding erases edits made in the UI. If someone edited in the UI, or there are unresolved comments, `docs.py build` stops. Put the edits and the responses to comments into doc.md, then rebuild with `--force`.
- [docs-write-007] **Stop rebuilding a material once people start editing it in the UI.** When it reaches the stage where you edit it together with the customer or colleagues in the UI, edit in the UI from then on (same as slides whose `build/` was deleted). Write 「<日付> から画面で直す」 in the outline.
- Do not delete `build/doc.md` until there is no prospect of rebuilding ("What to keep" in `../deck-practices/deliver.md`).

## 5. docx

[docs-write-008] Do not make new documents as docx. Existing docx files (3 in `Customers/`) and docx received from Word are uploaded to Drive and converted to Google Docs before editing. The tools for editing docx as docx (docx-js, `check.sh`, rendering images with LibreOffice) were removed (the backup is in the workspace's `Archive/docx_pipeline_20261010/`). Documents with a company template, such as PoC plans, follow its chapter structure (templates are in the workspace's `rules/docs-build/templates/`). Examples before 2026-10-09 are customer-facing materials (docx).
