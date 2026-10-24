# Splitting the fixes among page owners (slides only)

Open at step 5 of a round when you consider giving the fixes to children ("Fix" in [fix.md](fix.md)).

[deck-review-011] **You may split the fixes among children that own pages (slides only).** The time between rounds (the parent verifies, fixes, and rebuilds) is longer than the child's review (in 23 pi records, the median child review was 4.9–6.9 minutes and the time between rounds 11.7 minutes; `Internal/deck_speed_202610/社内メモ_計測の結果.md`). The parent decides whether and how to split.
- Give a child only the rows verified in step 4 and marked 「直す」 under "What to fix" in `fix.md`. The unit is the page file (`p<number>.json`; slides-pages-031 in `../slides-build/pages.md`; for pages.py decks, the page function 〔slides-legacy-030〕). Rows that hit the same file or function go to the same child. 2–4 pages per child.
- The parent keeps: 「聞く」 rows, fixes that touch a claim, number, or order, and cross-page fixes (inconsistent notation, numbers across pages, the order in `deck.json`; for pages.py decks, shared functions and constants and the order in `make`). For the part of a cross-page fix that falls on an owner's page, the parent decides the fix and adds it to that child's rows. The parent does not write an owner's files or functions until the child returns (it would conflict with the child's fix).
- Rounds not to split: rounds with fewer than 4 pages to fix, and rounds where every page's fix takes a few lines (a period, a word swap, an empty cell). Also do not split pages.py decks whose pages are not split into functions (written the old way with all pages in `make`), because the child's functions would not be called from `make`. A child takes 2–4 minutes each, so it does not pay off (one trial on 12 pages on 2026-10-14; the threshold is a guess). Do not split documents (`build/doc.md` is a single file, and fixing any section moves the page breaks).
- Ask the same way as in `../deck-practices/agents.md` (a new child, the same model as the main agent), with the prompt below ("Prompt"). The child edits its page files in place (for pages.py decks, it writes the fixed functions to `build/fix_<owner>.py` and does not write pages.py) and does not build. Fixes that conflict with the outline or the corrections, and fixes that touch anything outside its pages, are returned without deciding. While waiting, the parent puts its own share into files outside the owners' (pages.py for pages.py decks).
- When the children return, re-sort the returned rows in the step 4 table (「直す」, 「聞く」), bring `slides.py lint <URL>` to zero `要修正`, then build only once (`slides.py build`). If a child does not return, or `lint` stops on a JSON error, the parent fixes that child's rows (do not re-ask and wait). For pages.py decks, merge in `build/` with `slides.py merge fix_<owner>.py …`, check that the function names that come out match the owners, add the names the child wrote on the docstring's 「import:」 line to pages.py's imports, then build (if merge stops on a syntax error, the parent fixes it too). Delete each child's `fix_<owner>.py` right after merging (if it stays under the same name into the next round, the previous round's function gets merged in place of a child that finished without writing). Delete `pages.py.bak*` when delivering in step 7.

## Prompt

[deck-review-015] The prompt that gives the rows the parent marked 「直す」 to the children that own pages, between rounds of `/deck-review` (deck-review-011 above). Slides only (the parent fixes documents). Fill in the `<>` once per owner and ask them at the same time. Use a different child from the review child (do not have review children fix; they do not know what was agreed while building, so they conflict with claims, numbers, order, and corrections).

- `<your rows>` are the rows of the step 4 table rewritten as `p<ページ> | <ページのファイル> | <何が起きているか> | <直し方>`. The parent decides and writes the fix (also when adding a cross-page fix to a child's rows, write the fix the parent decided).
- Assign owners by page file (`build/p<number>.json`; slides-pages-031 in `../slides-build/pages.md`). The child edits its files in place. For pages.py decks, ask with the prompt in "When the deck uses pages.py" below.

```text
You fix slides. Fix only the rows under "Your rows", editing your page files (<your files, e.g. <build>/p05.json, <build>/p06.json>) in place. Do not write other page files, deck.json, or the outline. Do not build (do not run slides.py build or new, or gslides.py).

## What to read
- Rules: <workspace>/AGENTS.md, and slides-build/visual.md, slides-build/pages.md, and slides-build/diagrams.md under <workspace>/rules/ (if present; they take priority over the plugin files of the same name)
- Rules: <slides-build folder>/visual.md and <slides-build folder>/pages.md (writing JSON pages), and <slides-build folder>/diagrams.md if your rows touch a frame diagram, arrows, a Gantt chart, a bar chart, or a gridded diagram (a comparison table or a matrix)
- Outline: <outline path> (the agreed claims, numbers, and order)
- Corrections: the output of `python3 <deck-practices folder>/scripts/ledger.py list --deck <material folder>` (the corrections received from the user on this material; run it in <workspace>)
- Images of your pages: <p-05.png etc.> in <image folder> (drawn by Google before the fix)

## Your rows
<your rows>

## How to fix
- Fix only your files.
- Do not shrink text to fit (consider rephrasing, then a diagram). Use the JSON components (slides-pages-034).
- Return the following rows without fixing them: ones that conflict with the outline's claims, numbers, or order or with the corrections, ones that change a heading or what the page says, ones that add or split pages, ones that cannot be fixed without touching anything outside your files (other pages, deck.json), and ones whose fix conflicts with a rule. Do not decide them yourself.
- After writing, run `python3 <slides-build folder>/scripts/slides.py lint <your file>` in <build> for each file, and confirm that it does not stop on a JSON error and that `要修正` is 0 (this lints locally without building; errors and findings come out with their location).

## How to reply
In your reply, write one line each in the following form. Write nothing else.
直した: p<ページ> | <ファイル> | <直したこと>
返す: p<ページ> | <ファイル> | <行> | <返す理由>（なければ「返す: なし」）
```

## When the deck uses pages.py

For decks made earlier with pages.py, assign owners by page function (slides-legacy-030 in `../slides-build/legacy.md`), and make the second field of `<your rows>` the function name. Give `<owner>` a short name such as `a` or `b`, and have the child write to `<build>/fix_<owner>.py` (the parent merges with `slides.py merge`).

```text
You fix slides. Fix only the rows under "Your rows", and write the fixed page functions to <build>/fix_<owner>.py. Do not write pages.py, the outline, or any other file. Do not build (do not run slides.py or gslides.py).

## What to read
- Rules: <workspace>/AGENTS.md, and slides-build/visual.md, slides-build/pages.md, and slides-build/diagrams.md under <workspace>/rules/ (if present; they take priority over the plugin files of the same name)
- Rules: <slides-build folder>/visual.md, and "Writing pages.py" and "Laying out shapes and text" in <slides-build folder>/legacy.md
- Outline: <outline path> (the agreed claims, numbers, and order)
- Corrections: the output of `python3 <deck-practices folder>/scripts/ledger.py list --deck <material folder>` (the corrections received from the user on this material; run it in <workspace>)
- Current pages.py: <build>/pages.py (read only; use the shared functions, constants, and imports found here)
- Images of your pages: <p-05.png etc.> in <image folder> (drawn by Google before the fix)

## Your rows
<your rows>

## How to fix
- Write only your functions, whole, from def to the last line. Do not write functions you do not fix. Do not write imports, constants, or make. For slides.py names (such as `card_h`) that are not in pages.py's imports, use them as they are and list them on the docstring's 「import:」 line (the parent adds them to the imports).
- Do not shrink text to fit (consider rephrasing, then a diagram). Use components that exist in slides.py and the shared functions in pages.py.
- Return the following rows without fixing them: ones that conflict with the outline's claims, numbers, or order or with the corrections, ones that change a heading or what the page says, ones that add or split pages, ones that cannot be fixed without touching anything outside your functions (shared functions, constants, other pages), and ones whose fix conflicts with a rule. Do not decide them yourself.
- After writing, check only for syntax errors with `python3 -c "import ast; ast.parse(open('<build>/fix_<owner>.py').read())"`.

## How to reply
At the top of <build>/fix_<owner>.py, write a docstring in the following form.
"""
直した: p<ページ> | <関数> | <直したこと>（1 行ずつ）
返す: p<ページ> | <関数> | <行> | <返す理由>（1 行ずつ。なければ「なし」）
import: <pages.py の import に足す slides.py の名前>（なければ「なし」）
"""
In your reply, write only the counts of fixed rows and returned rows, and the file path.
```
