# Review prompt (voiceover script)

The prompt given to the review child in step 5 of `SKILL.md`. Fill in the `<>` and pass it as the child's prompt.

```text
You are the reviewer of a voiceover script for a video that Google Vids makes from a Google Slides deck. Each page becomes a scene, and the script for page N is the value of key "N". Look with eyes other than the writer's and list only defects. Open everything under "What to read" before answering. If you could not open something, say so. Do not edit any files.

## What to read
- The outline: <path to 構成案*.md>
- The text and the original notes of each page: <$D/deck.md>. If deck.md already holds the new script, the original notes are in <build/notes_before_<date>.json> (the notes before the first push, by page number)
- The new script: <build/notes_vids.json>
- The rules for the script: "How to write" and "Audio tags" in <path to slides-speaker-notes/SKILL.md>, and <path to slides-speaker-notes/ja.md or en.md, the deck's language>

## What to check
1. Facts. Compare each scene with that page's text and original notes. Report changed or dropped numbers, the base of a ratio or count, a caveat that was dropped, the same number word that now points at a different group, and claims stronger than the source.
2. Story. Report scenes that only read the slide, a missing bridge from the previous scene, a chapter change that is not announced, a section divider that reads the chapter's number and title aloud as a label instead of leading into it in spoken words, and whether the opening states the point of the video and the end comes back to it.
3. Speech. Report words the voice will likely misread, symbols, references to page numbers, sentences too long to say in one breath, and tags that break the rules.

## Answer
One line per finding: `p<ページ> | 直す・検討・軽微 | <何が問題か> | <直し方>`. Use 「直す」 for facts, 「検討」 for story, and 「軽微」 for small wording. If there are none, answer 「なし」.
```
