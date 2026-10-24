---
name: factory-kaizen
description: Improve the factory (the plugin, upstream). Takes the rules, checks, and script fixes that grew in a workspace and help other people too, verifies them on past materials with the changed and previous versions, and files an Issue on the plugin repository with the reason, verification results, images, and the diff of the proposed change. The owner creates the PR. Use when applying dreaming's 「プラグインに上げる」 proposals, or when asked 「工場を改善して」, 「プラグインに Issue を出して」, or 「大元を直して」.
---

# Improve the factory (file an Issue upstream)

Treat the workspace as one product whose rules (AGENTS.md, `rules/`) and checks (`rules/slides-build/checks.py`, `rules/docs-build/checks.py`) grow from accumulated corrections and exchanges. Of these, file only the ones that help other people too (not one person's taste or one customer's circumstances) as an Issue upstream (the plugin). What goes where is in "Rule layers" of `../deck-practices/rules.md`.

The plugin owner reads the Issue, decides whether to take it, and rewrites it to fit the rest of the code as a PR. So the Issue must contain enough material for the owner to decide without seeing the workspace (what happened, counts, verification results, images, the diff of the proposed change, open questions). The proposed change only needs to work in a verifiable form. Cleaning up, shrinking, and running reviews (simplify, review-loop, etc.) are the owner's job, so do not do them here.

Prerequisites: `gh` is logged in. Run in the workspace. `start` clones the upstream repository (`repository` in `.claude-plugin/plugin.json`) into `.factory/kaizen/<name>/repo`, so no local checkout or fork is needed.

```sh
P="python3 <this skill's folder>/scripts/kaizen.py"
$P start <name>                                   # clone into .factory/kaizen/<name>/repo (branch kaizen/<name>)
$P lint <name> <material URL ...>                 # run lint with the previous and changed versions on current materials and compare
$P rebuild <name> <material folder ...> [--pages 2,5]   # build temporarily from the source of truth with both versions and lay changed pages' images side by side (the temporary materials go to the trash)
$P open <name> --title <title> --body <body.md>   # Issue on the upstream repository. From the second time, rewrites the same Issue
$P clean <name>                                   # after the Issue is closed (deletes the clone too)
```

## Steps

1. **Decide what to file.** Combine into one: what to change and why (the findings and the number of materials and customers shown by `ledger.py why <rule ID>` in the rule ledger, recurrences and review results, figures from `.factory/lint_runs.jsonl` or dreaming's records). Do not write original quotes or material names in the Issue (after `start` in step 2, write them only in `verify/detail.md`); write counts in the Issue. If the workspace `rules/` has a copy, frame it as moving that copy upstream. Do not file preferences from a customer's `memory.md` (`ws-memory`) directly (if two or more customers share one, dreaming first moves it into `rules/`; "Customer memory" in `../deck-practices/rules.md`). Give a moved rule a new ID with the plugin's prefix (the next number after the largest one with the same prefix in `.factory/kaizen/<name>/repo`; no `ws-`). In the rule text write only the ID and a short reason, not dates or original quotes ("Routing corrections" in `../deck-practices/rules.md`).
2. **Run `start`, write the proposed change inside `.factory/kaizen/<name>/repo`, and commit.** Do not edit the plugin's install location. The branch is not pushed (the diff goes into the Issue), so commit granularity and messages are free.
3. **Verify on past materials.** Choose by what changed.
   - Rules and checks (`lint.py`, `doc_lint.py`, `textlint.py`, things moved from `checks.py`): run `lint` on both materials the rule should fire on and materials it must not fire on. Candidates are the materials in `.factory/lint_runs.jsonl` (materials where that rule's finding appeared) and 「作った」 in `references_index.md`.
   - Layout and appearance (`slides.py`, `docs.py`, `template.py`, `slides-build/visual.md`, `docs-build/visual.md`, templates, images): run `rebuild` on materials that have pages that should change. Before/after images are required (`open` stops without them).
   - Changes whose appearance does not differ before and after (for example a lint-only change that also edits text in `visual.md`): `rebuild` reports 「変わったページ: なし」 and makes no images. Place images of pages where the changed rule applies (for example built samples) in `verify/img/` by hand, and write in the 「過去資料での検証」 section of the body that the appearance does not change. Images without a `rebuild` marker (`<!-- img:<file name> -->` in `verify/pr.md`) are collected by `open` under 「ほかの画像」 at the end of the verification record (to show them elsewhere, add a marker to `verify/pr.md`).
   - Text-only edits (rewording a procedure, etc.): if no verification is needed, write `検証しない理由:` in the 「過去資料での検証」 section of the body.
   - Read the results, and in `.factory/kaizen/<name>/verify/detail.md` (which contains material names and finding text) check that added findings are not false positives and that removed findings really should go away. If the results are not what you expected, go back to step 2.
4. **Write the body.** Write it in `.factory/kaizen/<name>/body.md` using the template below. Every section is required (`open` stops otherwise).
5. **Confirm with the user before `open`.** People outside the repository also read the Issue. Show these two and file only after the user approves.
   - The body
   - The images to include (`verify/img/` and changed png files; a png's content does not show in a diff, so `open` includes the changed version as an image). As a rule, do not include images from customer-facing materials (`Customers/`), because they show the customer's name, numbers, and confidential information. Re-verify with internal materials or materials with only public content.
   `open` checks that the sections are complete, that verification exists, and that appearance changes have images. It then puts the images on the `pr-assets` branch (of your fork if you cannot write to the upstream repository; if there is no fork, `open` creates one on GitHub), appends the verification record (materials only as numbers like 「資料 1」; no names, URLs, or text), the previous version's commit, and the diff of the proposed change (`git diff origin/main...HEAD`, based on main of the upstream repository cloned by `start`) to the body, and creates the Issue. If the diff is so long that the body exceeds the limit, leave out the diff and write only its line count (file it in parts).
6. **Report back.** Return the Issue URL. If it came from a dreaming proposal to the plugin (P-ID), record it in the rule ledger with `ledger.py sent <P-ID> --issue <URL>` (if the proposed change uses an ID different from the proposal, also add `--rule <that ID>`) (so dreaming does not propose the same thing again). Follow the Issue with `gh issue view <URL> --json state,stateReason`. If it is closed without being taken (`NOT_PLANNED`), run `ledger.py reject <P-ID> --reason <reason>`. If it is closed as fixed (`COMPLETED`), tell the user it arrives with `claude plugin update ai-deck-factory@ai-deck-factory` (for pi, depends on how it was installed), and run `clean`. Once it arrives, dreaming proposes deleting the copy in the workspace `rules/` through 「写しを消す」 of `ledger.py candidates` (it checks whether the filed text is in the installed plugin; if the owner changed the text or ID, it does not appear, so dreaming removes it through the overlap check in its step 4e). The source findings are already linked to the new ID by `sent`. If findings that were not used as sources remain on the copy (`ledger.py why <ws-ID>`), relink each finding with `ledger.py route <c-ID> <plugin ID>`.

## Body template

```markdown
## 変えること
<何がどう変わるか。1〜3 行>

## 理由
<なぜ大元で変えるべきか。ほかの人にも効く理由>

## 背景
<きっかけ。ユーザーの発言（原文）、起きたこと、数字（lint の残り方、dreaming の記録）。顧客の名前は書かない>

## 過去資料での検証
<何で確かめたか、結果をどう読んだか（増えた指摘・消えた指摘が正しいか）。下に factory-kaizen が表と画像を足す>

## 影響
<既存の資料・ワークスペースの rules/ への影響。ほかの人の資料で指摘が増えるか。なければ「なし」>

## 迷ったところ
<確信のない判断・前提（しきい値を何本の資料で決めたか、など）と、とらなかった案。なければ「なし」>
```

## Notes

- Do not put customer names, internal URLs, or personal names in the Issue body or images (same as 「社外秘と顧客の情報」 in AGENTS.md). `open` stops if the title, body, branch name, changed file names, or included diff (including removed lines and context lines) contain a customer name from the workspace's `Customers/`, a material folder name under `Customers/<customer>/` or `Internal/` (one containing a 4-digit year; by rule `<内容>_<日付>`), or a word in `[factory] private` of `factory.toml`. Write folder names without dates, and Japanese company and product names, in `[factory] private`. Write the source parentheses of a rule like 「顧客向けの資料の p.3」 or 「ユーザー「（顧客）は〜」」.
- Temporary materials built for verification are created in `drive.factory` and moved to the trash afterward (kept only with `--keep`). They are not recorded in the lint log (`.factory/lint_runs.jsonl`).
