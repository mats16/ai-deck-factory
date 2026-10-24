# Request to the child agent that checks facts against sources

The request you give the source-check child agent (deck-flow-019 in step 5 of `../deck-practices/start.md`). It opens the sources of the rows in the 「出典の表」 and checks the values against the source text, because the maker's 「済」 is self-attested, and errors whose source was a chat, a meeting, or the maker's own reading passed every review so far (only a proofread that reopened the URLs caught them). Start it in the background and do not wait for it (deck-agents-013); it never blocks writing or building. Fill in the `<>`. How to start it (a new child agent without the conversation, the same model as the main agent) is `../deck-practices/agents.md`.

- **Pass 1 (rows):** after the 「出典の表」 is written in step 5. Delete the "Pages" section of the request.
- **Pass 2 (rows and pages):** after building the whole in step 8, together with round 1 of `/deck-review`. Keep the "Pages" section and pass the text that `gslides.py check` wrote (`$D/deck.md`; for documents `$D/text.md`). Rows marked 「照合済」 in pass 1 are not listed again.
- For a content/structure fix after delivery that adds or changes rows, run pass 2 on the changed pages only.
- When a child returns items under 「見ていない」, start another child on them with the same request and the sentence in "Limit".

```text
You check the facts of a material against their sources. Open each source yourself and compare the value with the source text. Do not trust the `確認` column: 「済」 only means the maker says they looked. Do not edit the material, the outline, or references.md (except when writing the findings file).

## What to read
- Rows to check: run `python3 <deck-practices folder>/scripts/refs.py check <material folder>` and take the section 「照合していない行」. It lists the rows in order of risk (`提供` → `計算` → `数字` → `顧客` → `名前`) with the source's ID, kind, date checked, and URL. Check them in that order.
- The outline's 「出典の表」 (<outline path>) and <material folder>/references.md, for the full rows and for `使い道`.
- Rules: "Sources" and deck-content-024, 025, 027, and 064 in <deck-practices folder>/content.md (what counts as a source, conflicting values, model generations, availability tables).

## How to open sources
- Public pages: fetch the page itself (WebFetch, or `curl -sL`). A search result snippet is not the source. Read the tables and footnotes (legends such as ‡ in availability tables).
- GitHub: `gh api repos/<owner>/<repo>`, `gh api repos/<owner>/<repo>/contents/<path>`, or raw.githubusercontent.com (README, package.json, Cargo.toml, and so on).
- Google Slides and Docs: the file-storage tool in <workspace>/factory.toml `[sources]`, or `python3 <slides-build folder>/scripts/gslides.py export <URL> /tmp/<name>.pptx` and the slide XML text; for Docs `python3 <docs-build folder>/scripts/docs.py export <URL> /tmp/<name>.pdf` and `pdftotext`. Do not run `gslides.py check` (it takes page images and shares the parent's rate limit).
- Meetings and chat: the `meetings` and `chat` tools in `[sources]`. Read the part the `出典` cell points to (time, message).
- Local data (kind `データ`): open the file and recompute. For `計算` rows, recompute from the original values of the rows it cites, not from rounded values (deck-content-037).

## How to judge each row
- `合う`: the source says the same value or statement, within the same scope and conditions.
- `違う`: the source says something else. Quote the source's words and give the correct value.
- `言い過ぎ`: true only under a condition the row dropped (region, plan, release stage, date, "up to"), or a generalization of one example.
- `確かめられない`: you could not open the source, or it does not mention the claim. Say which.
- For rows marked `（出典が弱い）` (a product fact whose only source is an article, a meeting, a chat, or something the user said): look for a primary source (the vendor's docs, the repository, the price list). If you find one, judge against it and give its URL. If there is none, judge `確かめられない` and say that only the weak source supports it.
- Judge product facts against the primary source (the project's own README and code, the vendor's docs) even when the row cites a list or a summary (an awesome list, a search result, a blog). A list that names the project is not evidence of how it is built (in a trial, a row checked only against an awesome list passed though the app's own README said otherwise).
- For values that change over time (stars, prices, model generations, release stages), judge against the source as of today and write today's date.

## Pages (pass 2 only)
- Text: <deck.md or text.md path> (below `### Notes:` are the speaker notes).
- Find statements on the pages that are not rows of the 「出典の表」 but need a source: availability and negations (「できない」「対応していない」「GA」「東京リージョンで使える」), limits and prices, the customer's environment and what the customer said, numbers, and the headings of pages that conclude (`言い切り`). Check them the same way and report them with the ID 「表にない」.
- Also report rows of kind `見立て` whose page states them as an established fact (without 「見立て」「仮説」 or a similar marker).
- Do not check wording, layout, or the story. The review child agents cover those.

## Limit
Check up to 30 rows and statements, in the order above. In pass 2, spend at most 15 on rows, so that the page statements get checked too (rows were checked in pass 1; in a trial where a 30-row table took the whole limit, 9 of 11 errors on the pages went unchecked). List the rest under 「見ていない」 by ID (for statements, the page and the words), so that the parent can start another child on them. <If this child takes over an earlier child's 「見ていない」, write: 「Check only these: <the list>.」 Otherwise delete this sentence.>

## How to reply
One line per row or statement: `<F-ID か 行<番号> か 表にない> | <ページ（分かれば）> | <合う／違う／言い過ぎ／確かめられない> | <表かページの言い方> | <出典の言い方（引用）> | <見た出典の URL と場所> | <直し方の案>`.
Then 「見ていない」: the IDs you did not reach (「なし」 if none).
Write all of the above to <findings file>, and in your reply write only the counts (per judgment) and that path.
```
