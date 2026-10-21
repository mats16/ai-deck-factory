# Request to child agents that write pages (slides)

The request you give when you split the remaining pages among child agents after the three representative pages (deck-practices-016 in "How to start" §7 of `../deck-practices/SKILL.md`). Fill in the `<>` and send one request per owner. How to start them (a fresh context, the same model as the main agent, in Claude Code side by side in one message, in T3 Code a separate delegated task per owner) is the same as "How to ask" in `../deck-review/SKILL.md`. Unlike reviews, pass the page JSON of the three representative pages as examples. The child agents also write pages in JSON (slides-034 in `slides.md`). Do not pass the conversation. Write everything decided in the conversation into the outline before you ask.

```text
You are in charge of writing pages of a material. Write each of your pages as one JSON file per page. The parent agent builds only once, so do not run slides.py new or build, or gslides.py check.

## Your pages
- Pages: <p12〜p19 (the # numbers in the outline's table)>
- Files to write: <material folder>/build/p<outline number>.json (one file per page. Example: p06.json), and <material folder>/build/pages_<owner>.json that lists them in the outline's order (`{"apiVersion": "slides/v1", "kind": "deck", "name": "<owner>", "pages": ["p06.json", …]}`). Put `"apiVersion": "slides/v1", "kind": "page"` at the top of every page file. Do not rewrite any other file (not deck.json, not the three representative pages, not the other owners' files)

## What to read (open only these. Do not go looking for others)
- Outline: <path to 構成案> (read the whole thing: the rows for your pages, the 「書き方の決め」 section, and the sources table)
- Examples: the page files of the three representative pages (<material folder>/build/<p05.json and so on>)
- Workspace rules: <workspace>/AGENTS.md, and the files under deck-practices and deck-build in <workspace>/rules/ (if any)
- Corrections received for this material: python3 <deck-practices folder>/scripts/ledger.py list --deck <material folder>
- Facts: the rows of the outline's 「出典の表」. Put on your pages only facts that are rows there (numbers, availability, the customer's environment, proper nouns). Open <material folder>/references.md only to check a row's source
- How to write: slides-034, slides-035, and slides-038 in §2 of <deck-build folder>/slides.md (writing JSON pages, raw, build warnings), the samples that cover the usual ways of writing in <deck-build folder>/samples/json/ (open the page of the same type), <deck-practices folder>/visual.md and §4–6 of content.md, and for the notes, "How to write" and "Audio tags" in <slides-speaker-notes folder>/SKILL.md and its language file (ja.md or en.md). `python3 <deck-build folder>/scripts/slides.py schema --brief` prints a quick reference of the types, keys, and color names you can write (`schema` for everything)

## How to write
- Write layout with row, stack, and grid, and write coordinates only inside a frame. Emphasize text with **bold** and ***red bold***, change the size of part of the text with {32:48}, link to another page with [name](#<page file name>), connect arrows by component id, and put the name of a line in the arrow's label (slides-034 in slides.md). In frame diagrams, bring the build warnings (a line passes over a component, arrowheads gather at one point, components partly overlap) to 0. Write in raw only what the shape keys cannot express, and mention it in your reply (slides-035).
- Write pages of the same type as an example so they look the same as the example (components, text sizes, layout, colors). If something cannot be written with the JSON components (cannot be built even when placed by position inside a frame), write the page as far as you can and put it under 「親に返すこと」 in your reply.
- Write local images as a path from the JSON file (such as img/ under build/) or as asset:<path>.
- Do not copy placeholder words from the outline's examples (such as 「〇〇」 and 「TODO」) as they are; replace them with content (if you copy them, the lint stops with the `要修正` 「置き換え忘れ」. If the outline does not determine the content, put it under 「親に返すこと」).
- Follow the 「書き方の決め」 section line by line. For numbers and wording that span pages, use what is in the outline and the 「書き方の決め」 section.
- Write a source line (on pages with numbers) and notes on every page. The notes are the voiceover script for Google Vids (content.md §5).
- If a page needs a fact that is not a row of the 「出典の表」, do not add it to the outline or guess it; write the page without it and put it under 「親に返すこと」. lint reports numbers that are not in the table as `出典の表にない数字`; bring them to 0 or return them.
- When done, run <deck-build folder>/scripts/slides.py lint pages_<owner>.json <deck URL> in <material folder>/build (it lints locally without building. A few seconds. JSON errors stop with their location) and bring `要修正` to 0. The (p06.json.body[1]) after a finding is the location of the component to fix. Check each `要確認` and build warning one by one, and either fix it or write why it stays. For findings marked 「（見積もり）」, the parent agent builds and confirms them on images, so if you cannot fix them, just write the reason.

## What not to decide yourself
Do not change the outline's claims, numbers, or order. Do not add, delete, or split pages. If any of these applies — it conflicts with the outline, the rules do not decide it, the outline has no source for a number, or it does not fit in its frame without cutting — write that page as the outline says and put it under 「親に返すこと」 in your reply.

## Reply
- The path of the pages_<owner>.json you wrote and the number of pages
- The lint result (the `要確認` and warnings you left, with reasons)
- 「親に返すこと」: `p<page> | <what cannot be decided> | <proposal>` (「なし」 if none)
- Pages you could not write with the JSON components (「なし」 if none)
```
