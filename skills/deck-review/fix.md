# Verifying, sorting, and fixing the findings (steps 4–5)

Open when the review children's findings return (every round; steps 4–5 of `SKILL.md`). Rebuilding and checking the fixes is step 6 of `SKILL.md`.

## Verify the findings

Review children also report defects that do not occur. Fixing without verifying changes places that need no change and creates new defects. Before fixing, check one by one whether each finding really occurs.

- Check visual findings (overflow, misalignment, overlap) on the full-size image (`$D/p-NN.png`; crop details with `sips -c`) or by the coordinates in the JSON in `$D` (`deck.json`, `doc.json`). If it does not occur, mark it 「残した（誤り）」 (that count is used to fix rules and aspects that miss often; `../deck-practices/rules.md`).
- Put lint `要確認` items into the same table, one per row. For each verified finding, write the matching rule in the 「決まり」 column ("Finding format" below).
- Before putting in a finding, check that it does not stray from the one sentence that page wants to say. Put ones that stray into 「聞く」.

## What to fix

[deck-review-007] Review findings mix things that a fix settles and things whose fix changes what the material says. Fixing the latter silently changes the claims, numbers, and order agreed with the user without the user knowing (deck-flow-010 in "Working practices" of `../deck-practices/SKILL.md`: "Do not silently change confirmed claims, numbers, or order."). So sort each finding into one of the two before fixing. When unsure, ask.

| Category | Examples | What to do |
|---|---|---|
| 直す | lint `要修正`, 「和欧間のスペース」, 「約物」, overflow, overlap, collision with the footer, misaligned arrows, boxes larger than their content, inconsistent notation, first use of abbreviations, line-break positions that do not change the wording, changing a page's form when the claim and the facts stay the same (deck-review-010) | Fix it and write 「直した」 in the table. Do not shrink text to fit (consider rephrasing, a diagram, then splitting the page, in that order; for a split, build it split and then ask; deck-flow-010 in `../deck-practices/SKILL.md`). Shrinking a box so the bottom of the page becomes empty is fine (adding content is a question) |
| 聞く | Changing a heading, claim, number, or order; adding, deleting, or splitting pages; adding another example or path for fairness; removing a conclusion band or kicker; preferences in phrasing; items the reviewer rated 「聞く」 (not decided by the rules, or readable either way) | Do not fix. Write 「聞く」 and a proposed fix in the table and return it to the user |

## Finding format

One finding per row. The reviewer returns up to 「直し方の案」; you (the maker) write 「結果」 and 「決まり」. Compare the counts per round to see whether fixes increased them.

`p<ページ> | <出所: lint・一覧・画像・テキスト・読み手テスト・照合> | <観点 1〜5> | <直す／見直す／聞く> | <何が起きているか> | <直し方の案> | <結果: 直した・残した（理由）・残した（誤り）・聞く> | <決まり>`

- **決まり:** the ID of the rule the finding falls under (`slides-visual-012`, `ws-slides-visual-003`; customer memory is `ws-memory-001`; separate several with `,`). Attach to each ID, in 「」, a phrase copied verbatim, in the rule's own language, from that rule's text (the text after `[ID]`) (`slides-visual-013「単語や文節の途中で折り返さない」`; do not put `|` or 「」 in the phrase). `ledger.py review` reports and skips only that ID when the phrase is not in that ID's rule text or the ID's rule is not found (this stops mislabeled IDs; IDs without a phrase are imported and their count is reported). For lint findings, use `lint:<rule name>` (the name inside `[ ]` in the lint output). If no rule applies, `-`. Do not make the reviewer look these up (so it looks with eyes that do not know how the material was made; deck-agents-008). You look them up in `rules/`, the customer's `memory.md`, and the skill rules when verifying the findings. If unsure, use `-` and do not guess (this becomes the count of whether a rule worked or missed).

## Fix

- [deck-review-005] **Fix.** Follow "What to fix" above. Fix the page JSON (pages.py for older decks; `build/doc.md` for documents) and the outline, and rebuild with `slides.py build <URL>` (`docs.py build <URL>` for documents).
- **Splitting the fixes among page owners (slides only).** When several pages need fixes, open [prompt_fix.md](prompt_fix.md) before fixing them yourself: it holds when to split and when not to, what the parent keeps, how to merge what returns (deck-review-011), and the prompt.
