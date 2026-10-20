# Fix prompt (slide page owners)

[prompt_fix-001] The prompt that gives the rows the parent marked 「直す」 to the children that own pages, between rounds of `/deck-review` (deck-review-011 in `SKILL.md`). Slides only (the parent fixes documents). Fill in the `<>` once per owner and ask them at the same time. Use a different child from the review child (do not have review children fix; they do not know what was agreed while building, so they conflict with claims, numbers, order, and corrections).

- `<your rows>` are the rows of the step 4 table rewritten as `p<ページ> | <ページのファイル> | <何が起きているか> | <直し方>`. The parent decides and writes the fix (also when adding a cross-page fix to a child's rows, write the fix the parent decided).
- Assign owners by page file (`build/p<number>.json`; slides-031 in `../deck-build/slides.md`). The child edits its files in place. For pages.py decks, ask with the prompt in "When the deck uses pages.py" below.

```text
You fix slides. Fix only the rows under "Your rows", editing your page files (<your files, e.g. <build>/p05.json, <build>/p06.json>) in place. Do not write other page files, deck.json, or the outline. Do not build (do not run slides.py build or new, or gslides.py).

## What to read
- Rules: <workspace>/AGENTS.md, and deck-practices/visual.md and deck-build/slides.md under <workspace>/rules/ (if present; they take priority over the plugin files of the same name)
- Rules: <deck-practices folder>/visual.md, and slides-034 (writing JSON pages) and "4. Laying out shapes and text" in <deck-build folder>/slides.md
- Outline: <outline path> (the agreed claims, numbers, and order)
- Corrections: the output of `python3 <deck-practices folder>/scripts/ledger.py list --deck <material folder>` (the corrections received from the user on this material; run it in <workspace>)
- Images of your pages: <p-05.png etc.> in <image folder> (drawn by Google before the fix)

## Your rows
<your rows>

## How to fix
- Fix only your files.
- When you fix the body, also match the same spot in that page's note (counts, ranges, names, assertions).
- Do not shrink text to fit (consider rephrasing, then a diagram). Use the JSON components (slides-034).
- Return the following rows without fixing them: ones that conflict with the outline's claims, numbers, or order or with the corrections, ones that change a heading or what the page says, ones that add or split pages, ones that cannot be fixed without touching anything outside your files (other pages, deck.json), and ones whose fix conflicts with a rule. Do not decide them yourself.
- After writing, run `python3 <deck-build folder>/scripts/slides.py lint <your file>` in <build> for each file, and confirm that it does not stop on a JSON error and that `要修正` is 0 (this lints locally without building; errors and findings come out with their location).

## How to reply
In your reply, write one line each in the following form. Write nothing else.
直した: p<ページ> | <ファイル> | <直したこと>
返す: p<ページ> | <ファイル> | <行> | <返す理由>（なければ「返す: なし」）
```

## When the deck uses pages.py

For decks made earlier with pages.py, assign owners by page function (slides-030 in `../deck-build/slides.md`), and make the second field of `<your rows>` the function name. Give `<owner>` a short name such as `a` or `b`, and have the child write to `<build>/fix_<owner>.py` (the parent merges with `slides.py merge`).

```text
You fix slides. Fix only the rows under "Your rows", and write the fixed page functions to <build>/fix_<owner>.py. Do not write pages.py, the outline, or any other file. Do not build (do not run slides.py or gslides.py).

## What to read
- Rules: <workspace>/AGENTS.md, and deck-practices/visual.md and deck-build/slides.md under <workspace>/rules/ (if present; they take priority over the plugin files of the same name)
- Rules: <deck-practices folder>/visual.md, and "Writing pages.py" in §2 and "4. Laying out shapes and text" in <deck-build folder>/slides.md
- Outline: <outline path> (the agreed claims, numbers, and order)
- Corrections: the output of `python3 <deck-practices folder>/scripts/ledger.py list --deck <material folder>` (the corrections received from the user on this material; run it in <workspace>)
- Current pages.py: <build>/pages.py (read only; use the shared functions, constants, and imports found here)
- Images of your pages: <p-05.png etc.> in <image folder> (drawn by Google before the fix)

## Your rows
<your rows>

## How to fix
- Write only your functions, whole, from def to the last line. Do not write functions you do not fix. Do not write imports, constants, or make. For slides.py names (such as `card_h`) that are not in pages.py's imports, use them as they are and list them on the docstring's 「import:」 line (the parent adds them to the imports).
- When you fix the body, also match the same spot in that page's d.note (counts, ranges, names, assertions).
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
