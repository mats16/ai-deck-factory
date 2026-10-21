---
name: slides-speaker-notes
description: Write the speaker notes of a built Google Slides deck as the script for Google Vids' AI voiceover (when Vids makes a video from slides, each page becomes a scene and its notes become the scene's voiceover). Use when asked to write or rewrite notes for a video 「字幕」「ナレーション」「読み上げ」「Vids」「動画にする」, or to fix audio tags in them. Covers the story across scenes, what to leave out of the voice, writing for speech, the audio tags Vids reads, the per-scene limit, one review by a child agent, and replacing only the notes without rebuilding pages (`scripts/speaker_notes.py pull`, `lint`, `push`). Rules that depend on the language (tone, length, readings, symbols) are in ja.md and en.md. The slides themselves are not changed.
---

# Speaker notes for Google Vids

When Google Vids makes a video from slides, each page becomes a scene and its speaker notes become the scene's voiceover script. This skill rewrites the notes of a built deck as that script. Run the request through the normal flow in `../deck-practices/SKILL.md` (read the history, route corrections to the ledger); this file covers only the notes.

## Steps

Run in the material's `build/` folder. The URL is in the outline.

```sh
N=<slides-speaker-notes folder>/scripts/speaker_notes.py
K=<deck-build folder>/scripts                  # ../deck-build/scripts from this skill's folder
python3 $K/gslides.py check <URL> --all        # deck.md (text and current notes of each page) and page images in /tmp/slides_<first 8 chars of ID>/
python3 $N pull <URL> > notes_vids.json        # current notes as {"1": "…", …}; pages whose notes differ from `speakerNotes` in the page JSON go to stderr
python3 $N lint notes_vids.json --lang ja      # run after every edit (--lang en for English decks)
python3 $N push <URL> notes_vids.json          # replace the notes only
```

1. **Read the story first.** Open the outline (`構成案*.md`: audience, question, what the audience can do after reading, the order of headings), `deck.md`, and the contact sheet (`uv run -q $K/sheet.py`, as in `../deck-review/SKILL.md`). Decide the one point the whole video should leave before writing any scene.
2. **Take the current notes** with `pull`. If stderr lists pages whose notes differ from the page JSON, the notes were edited on screen; ask which is right before rewriting them.
3. **Write the script** into `notes_vids.json`, one key per page (page numbers from 1), by "How to write" and "Audio tags" below and the language file. Write the whole deck before reviewing, because the bridges between scenes depend on their neighbors.
4. **Bring `lint` to zero `要修正`.** Look at every `要確認` and fix it, or keep it when it is intended (an example phrase that names a page number is fine).
5. **Ask one child agent to review once** with [prompt_review.md](prompt_review.md) (a new child without the conversation, the same model as the main agent; "How to ask" in `../deck-review/SKILL.md`). Verify each finding against `deck.md` before fixing, then run `lint` again. Do not ask for a second round; the script has no layout, so the parent can check its own fixes.
6. **Push.** `push` does not run `lint` (so a backup of the earlier notes longer than Vids' limit can be pushed back); run `lint` first. It writes only the speaker notes, so on-screen edits and comments on the slides stay. See "What push does".
7. **Deliver.** Give the URL, the scene count and total characters (from `lint`), the point the video leaves and where the story turns, what you left out of the voice, and the backup file.

## How to write

Before writing, open the file for the deck's language: [ja.md](ja.md) for Japanese (the default, 「日本語で作る」 in the workspace's AGENTS.md) or [en.md](en.md) for English. It holds what depends on the language: the tone, the length of a scene, words to rewrite for the voice, symbols, how to point at other scenes, and where tags go. The workspace adds to or overrides it in `rules/slides-speaker-notes/<ja|en>.md` (the hook shows it after the file). Run `lint` with the same language (`--lang ja|en`).

- [slides-speaker-notes-001] スライドを読み上げない。動画全体の筋を優先する。冒頭で、この動画を通して見てほしい点を先に言う。各シーンの頭に、前のシーンからのつなぎの一言を入れ、章の切り替わり（扉）では、ここから何の話かを、話しかける言葉でつなぐ（言い方は言語のファイル）。最後にその点に戻り、次の一歩を呼びかけて終える。
- [slides-speaker-notes-002] 細部は声では飛ばしてよい（ファイル名、パス、コマンド、表のセルの値）。表や細かいページでは、動画を止めて見るよう促す。動画にページ番号はないので、ページを番号で指さず、前後のシーンとして指す（言い方は言語のファイル）。
- [slides-speaker-notes-003] 縮めても、事実は元のノートとスライドから変えない。割合や件数は、何のうちの数かを残す。同じ数の言葉が別のまとまりを指すときは、どのまとまりかを言う。断り書きを落とさず、言い過ぎにしない。

## Audio tags

- [slides-speaker-notes-006] **Tags take effect only with Vids' Conversational voices** (the Gemini voices, such as Nyla and Elio). The voices offered when making a video from slides (Narrator, Educator, Teacher, and so on) read the tags aloud as text (the user checked this on 2026-10-21 with a Japanese script). Write the tags anyway; the steps to change the voice are in "In Vids".
- [slides-speaker-notes-007] **Use only these tags.** Pauses: `[short pause]` before a turn in the talk, `[medium pause]` between paragraphs (1–2 per scene), `[long pause]` only at the boundary between the halves of the video. Emotion, at most one per scene: `[enthusiasm]` for the opening and the closing, `[curiosity]` for a question to the audience, `[determination]` for a recommendation or a conclusion. Put a tag after the end of a sentence, and never put two tags in a row. Most scenes need only pauses. The words that start a turn and the sentence end differ by language (the language file).
- To use another tag, first confirm its exact name in Vids (type `[` in a Voiceover script; the menu lists Pace, Pauses, Emotion, Style, and Sounds), because a name Vids does not know is read aloud. `lint` reports names outside the list above as `要確認`.
- One scene holds at most 2,500 characters in any language (Vids' limit; `lint` reports it as `要修正`).

## What push does

- It stops before writing anything unless an `.md` file in the material's folder (the outline holds the URL) contains the deck's ID, because page file names such as `p05.json` repeat across materials, and pushing from another material's `build/` would overwrite that material's page files.
- The first time, it saves the current notes to `notes_before_<date>.json` in `build/`. If any `notes_before_*.json` exists, it saves nothing, so the file keeps the notes from before the first push. To restore them, `push` that file.
- It replaces only the speaker notes of pages whose notes changed (in the deck's font), reads them back, and stops if they differ from the script.
- It rewrites `speakerNotes` in the page file of each slide, keeping the file's layout. It finds the file by the file-name mark in the slide's ID (not by position, so a locally reordered `deck.json` does not send notes to the wrong file). It lists the slides whose file it cannot find (pages.py decks, pages added on screen); rewrite those notes yourself (`d.note` for pages.py).
- If the deck had no on-screen edits, it records the new version, so the next `slides.py build` does not take the push for an on-screen edit. If it had some, it leaves the record as it was, and the next build still stops for them (slides-002 in `../deck-build/slides.md`).
- The page hash includes the notes, so the next `slides.py build` recreates the pages whose notes changed (comments on those pages lose their anchor; `../deck-comments/SKILL.md`).

## In Vids

Do not include these steps when delivering, because not every deck becomes a video. Explain them when the user asks how to make the video or how to change the voice, or reports that tags are read aloud. Steps 3–4 follow the help page and have not been checked on screen; ask the user to report if the names differ.

1. Make the video from the slides. The voices offered here do not read tags.
2. In the video, open Voiceover on the right and choose All scenes at the top.
3. Change the voice to one of the Conversational voices.
4. Regenerate the voiceover of all scenes (Update all voiceovers in the help).

Suggest trying one scene that has tags before regenerating all of them.
