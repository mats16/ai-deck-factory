---
name: deck-review
description: Full review of a material (Google Slides or Google Docs) before returning it to the user. Uses lint, a contact sheet of all pages, and a separate subagent's eyes, verifies the findings, fixes and rebuilds what may be fixed, and asks about anything that changes a claim, number, or order. `/deck-review <URL>`. Use when asked 「レビューして」「見直して」「渡す前に確認して」, and always before returning a newly made material to the user. Checks during building are slides-build and docs-build. For fixes after delivery, run only the scope decided in deck-practices/revise.md.
---

# Full review before delivery

[deck-review-001] While building, run lint with slides-build's `gslides.py check` for slides and docs-build's `docs.py check` for documents, and open the images of the changed pages yourself and fix them (`../slides-build/SKILL.md` "Reading the results", `../docs-build/SKILL.md` §3). This skill is the review of the whole material that runs after that, before returning it to the user. The steps and the files below are the same for every format; only the review prompt is split per format. A separate pair of eyes finds the cross-page defects that page-by-page checks miss (story, runs of the same pattern, uneven whitespace and density, the number of decorations) and the defects the maker overlooks (研究 1-3、AI 実践 1-4、中身 1-12; the abbreviations are in the table in `../deck-practices/SKILL.md`). For fixes after delivery, how far to run (one round on the changed pages only, the whole material, or not at all) is decided by deck-flow-017 in `../deck-practices/revise.md`.

`/deck-review <Google Slides or Google Docs URL> [--talk]`. If the URL is omitted, use the URL written in the outline of the working folder. The URL decides the format (`/presentation/` is slides, `/document/` is a document). `--talk` is for materials that are spoken, such as LTs (slides only). Steps 1–6 below (check again, ask, verify findings, fix, rebuild and check) count as one round; run up to the round limit.

## Files to open at each step

Open the file for the step you are on; do not read ahead.

| Step | File |
|---|---|
| 1 Check, 6 Check again and end the round, 7 Deliver | this file |
| 2–3 Write the review prompt and ask (every round) | [ask.md](ask.md), and the prompt for the format: [prompt_slides.md](prompt_slides.md) (slides) or [prompt_doc.md](prompt_doc.md) (documents) |
| 3 Pass 2 of the source check (round 1 only; deck-flow-019 in `../deck-practices/start.md`) | [prompt_sources.md](prompt_sources.md) |
| 4–5 Verify, sort, and fix the findings (every round) | [fix.md](fix.md) |
| 5 Split the fixes among page owners (slides only, when `fix.md` says so) | [prompt_fix.md](prompt_fix.md) |
| Starting and waiting for any child | `../deck-practices/agents.md` |

## Steps

```sh
K=<slides-build folder>/scripts   # The folder that holds slides-build's SKILL.md. From another skill, ../slides-build/scripts relative to that skill's folder
J=<docs-build folder>/scripts    # ../docs-build/scripts relative to this skill's folder
C=<deck-practices folder>/scripts # ../deck-practices/scripts (shared by slides and documents)
python3 $K/gslides.py check <URL> --all [--talk] # Slides. Images of all pages (the checkpoint for cross-page review)
D=/tmp/slides_<first 8 chars of ID>              # Output of check (deck.json from presentations.get [not build/deck.json], deck.md, p-NN.png)
python3 $J/docs.py check <URL>                    # Document (Google Docs)
D=/tmp/docs_<first 8 chars of ID>                # Output of check (doc.json, text.md, p-N.png)
uv run -q $C/sheet.py $D/sheet.png $(ls $D/p-*.png | sort -V) --cols 4 --width 400 --per 16   # Contact sheet (16 pages each: sheet-1.png …; sheet.png if 16 pages or fewer)
```

1. **Check all pages again.** For slides, run `gslides.py check --all` and the contact sheet; for documents, run `docs.py check` and the contact sheet. If you just built the whole material and ran `check --all` (step 8 in `../slides-build/workflow.md`) and have not rebuilt since, reuse that output (`$D`) and contact sheet; do not run them again. If lint `要修正` items remain, fix them first.
2. **Confirm the audience** from the outline and write it into the review prompt ([ask.md](ask.md)).
3. **Ask** the review children with the per-format prompt ([ask.md](ask.md)). In round 1, also start pass 2 of the source check.
4. **Verify the findings** one by one before fixing ([fix.md](fix.md)).
5. **Fix** what may be fixed and set aside what to ask ([fix.md](fix.md)).
6. **Check the fixed pages again.** While putting in fixes, use `slides.py lint <URL>` (no build) to bring `要修正` to zero; after all of the round's fixes are in, build only once, run `gslides.py check <URL>` (takes images of the fixed pages only and writes `$D/changed.json`; for documents, `docs.py check <URL>` on all pages, because page breaks move), rebuild the contact sheet, and go back to step 3 with the fixed pages and the contact sheet ("From round 2" in [ask.md](ask.md)). Steps 1–6 count as one round; stop at the number of rounds in `[review] deck_review_max_rounds` in `factory.toml` (1–3; 3 if not set). If a fix increases defects, revert that fix, because the more rounds you run, the more likely a fix's side effects create new defects ("Basis" below).
   [deck-review-006] **How to end.** You may stop mid-run only when there are zero findings to fix. If even one finding was fixed, ask for the next round (except when the last round has ended). Fixes made in the last round need not be sent to a child again, but check them yourself with `gslides.py check` (`docs.py check` for documents) and the images of the fixed pages before delivering. Findings not fully fixed in the last round (also when the count does not drop, and when the limit is 1 round) go in the table as 「残した（<number of rounds> ラウンドで打ち切り）」 when you deliver (so you do not end without checking after a fix, or deliver while hiding that the count did not drop).
   [deck-review-013] **Before asking for the next round, write out and summarize the round.** Append the round's table ("Finding format" in [fix.md](fix.md)), the 「直したこと」 to add to the next round's prompt, and the questions for the user to `$D/review.md` (the same file as the table delivered in step 7). If you can call a context-summarizing tool, call it after that (deck-flow-005 and 015 in `../deck-practices/SKILL.md`). In the continuation instructions, write which round you are about to ask for, the URL, `$D`, and the files to reread (`$D/review.md`, the outline, this file, [ask.md](ask.md), [fix.md](fix.md), `../deck-practices/agents.md`, the review prompt, and [prompt_fix.md](prompt_fix.md) if you split the fixes). If you cannot call it, just append and ask for the next round. This step averages 68 calls per run, and 8 of 11 automatic summaries at 400k ran here (2026-10-14; the same record as deck-flow-005).
7. **Deliver.** Return the Drive URL, the findings table ("Finding format" in [fix.md](fix.md)), and the list of questions for the user to the user. Write the delivered table (all rounds) to `$D/review.md` (do not rewrite the earlier rounds' rows appended in deck-review-013; add the last round's table. For findings carried over to the next round, write the page and 「何が起きているか」 with the previous round's wording; the ledger uses these two and the rule to identify the same finding), and import it into the rule ledger with `python3 <deck-practices folder>/scripts/ledger.py review --deck <material folder> --table $D/review.md` (dreaming counts results per rule. The same row is not counted twice, and the same row across rounds takes the later round's result). After checking, you may delete `$D`. For pages.py decks, also delete the `build/pages.py.bak*` left by `slides.py merge`.

Basis: the round limit and reverting when things get worse follow research on draw-look-fix loops (ACE: two thirds finish in one pass, limit of 3 passes, roll back when worse) (研究 1-3・1-4).
