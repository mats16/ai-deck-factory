# Steps 10–11: delivering and cleaning up

Steps 10–11 of "Overall flow" in [SKILL.md](SKILL.md), for decks and documents, and what to keep afterwards.

## 10. Deliver

[deck-flow-020] **Before the report, check the ledger.** Run `refs.py check <material folder> --fetch`. Reread the sources it lists as stale or updated after the date checked, fix what changed (rows and pages), and run `refs.py seen`. Resolve the rows still `未`: open the source, or take the fact off the pages and ask. Also run it when a request after delivery changes the facts of a material checked more than 14 days ago. Stale sources caused wrong model generations, prices, and descriptions of our own tools in past corrections.

[deck-flow-022] **When the request also asks for speaker notes or a video, go on to them right after the deck is finished, without stopping.** Run in this order: finish the deck (9 and deck-flow-020, which can still change pages) → write the notes for the whole deck by `../vids-voice/SKILL.md` → make the video by `../vids-build/SKILL.md`, only if a video was asked for → deliver everything in one report. Keep the order, because the notes are written from the finished pages and the video reads the notes. A request for a video alone also runs the notes first. Do not report or wait for the user between the steps. If a step would ask the user (such as moving content from the notes to the pages in step 2 of vids-build), skip that part and put the question in the final report. Do not ask about the video: it uses a Conversational voice unless the request names a voice or avatar scenes (step 1 of vids-build).

Put the final report in one message. Include:

- The Drive URLs (the material and anything else you made)
- The `/deck-review` findings table and the count per round (step 7 of `../deck-review/SKILL.md`)
- The list of questions for the user: the items set to 「聞く」 along the way (plan-review findings that change the audience, the question, or the claim; proposals that change claims, numbers, or order; proposals to add, delete, or split pages; things the rules do not decide; what child agents returned). Pages split because they did not fit are also asked about here (deck-flow-010)
- The key points of the three-representative-pages log (up to 3 lines; slides-flow-009)
- Which correction was routed to which rule (「修正の指示」 in AGENTS.md)
- What the source check changed, and the rows still 「照合中」 or `確かめられない` (deck-flow-019)
- If notes or a video were asked for: what step 7 of `../vids-voice/SKILL.md` lists, and the Vids URL (deck-flow-022)

If `[feedback.google_comments] watch_hours` in `factory.toml` is greater than 0, start watching comments after delivery (deck-comments-004 in `../deck-comments/SKILL.md`). If it is 0 or unset, do not watch.

## 11. Clean up

Check that no findings for this material remain with the destination 「未」 (`ledger.py list --deck <material folder> --open`; so that if a correction drops out of a conversation summary, it can be picked up again from the ledger), and that 「あと」 in the three-representative-pages log is filled in ([rules.md](rules.md)). Add the materials you used to `references_index.md`. Do not leave PDFs or images used for checking in the folder ("What to keep" below).

## What to keep

- Keep the deliverables (Google Slides and Google Docs on Drive, html and csv, pptx from before 2026-10-07, docx from before 2026-10-09, PDFs made from HTML and handed over) and the documents (`構成案*.md`, `社内メモ_*.md`, `references.md`, research notes).
- Delete generator scripts, images and PDFs used for checking, `__pycache__`, `.venv`, and old versions of the outline once the material is no longer in use.
- Keep `build/` only for materials likely to be edited again. List the current `build/` folders with `find Customers Internal -maxdepth 3 -type d -name build`. Do not decide to delete one just because it exists; check each material's work status and whether it will be edited. Google Slides materials cannot be rebuilt without `build/deck.json` and the page JSON (older materials: `build/pages.py`), and Google Docs materials without `build/doc.md`, so do not delete them until there is no prospect of editing. Materials whose `build/` was deleted, and documents that started being edited in the UI, are edited in the UI and not rebuilt from then on. Edit docx and pptx from before 2026-10-07 by the official skill's editing procedure (unzip → rewrite the XML → zip).
