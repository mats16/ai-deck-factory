# English scripts

The rules for an English voiceover script. Use them with "How to write" and "Audio tags" in [SKILL.md](SKILL.md), and run `speaker_notes.py lint <script.json> --lang en`.

These rules have not been tried on a real deck or with Vids' English voices yet. The first time you use them, tell the user so, and write what you learn (misread words, tags that did not work) to the workspace's `rules/vids-voice/en.md`.

- [vids-voice-en-001] Write as you would say it to the audience: plain words, second person, contractions are fine. Aim for 40–120 words per scene (20–40 for a section divider), and about half the length of reading every slide aloud. The word counts are converted from the Japanese guide (100–300 characters) at a speaking rate of about 150 words a minute; adjust them after hearing the first video.
- [vids-voice-en-002] Write names the way they are said, because the voice reads the text as it is. Spell out symbols and units that a voice may misread (write "versus", not "vs."; write "per month", not "/mo"). Do not use slashes, hashes, asterisks, vertical bars, parentheses, or URLs. Split a sentence that cannot be said in one breath.
- [vids-voice-en-003] Point at other scenes with "earlier" and "next", not "slide 5". On a table or a dense page, say "pause the video to read the table".
- [vids-voice-en-004] On a section divider, lead into the next part as you would say it ("Next, let's look at …", "Now let's turn to …"). Choose the words to fit the content and the previous scene, and do not repeat one pattern, because the viewer should hear someone leading them into the next part, which keeps the story moving.
- [vids-voice-en-005] Put a tag after the period that ends a sentence. Put `[short pause]` before a turn in the talk (before "so", "but", "next", "second").
