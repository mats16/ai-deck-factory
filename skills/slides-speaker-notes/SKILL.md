---
name: slides-speaker-notes
description: Write the speaker notes of a built Google Slides deck as the script for Google Vids' AI voiceover (when Vids makes a video from slides, each page becomes a scene and its notes become the scene's voiceover). Use when asked to write or rewrite notes for a video 「字幕」「ナレーション」「読み上げ」「Vids」「動画にする」, or to fix audio tags in them. Covers the story across scenes, what to leave out of the voice, writing for speech, the audio tags Vids reads, the per-scene limit, one review by a child agent, and replacing only the notes without rebuilding pages (`scripts/speaker_notes.py pull`, `lint`, `push`). The slides themselves are not changed. Presenter notes written while making a deck follow the normal flow in deck-practices, not this skill.
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
python3 $N lint notes_vids.json                # run after every edit
python3 $N push <URL> notes_vids.json          # replace the notes only
```

1. **Read the story first.** Open the outline (`構成案*.md`: audience, question, what the audience can do after reading, the order of headings), `deck.md`, and the contact sheet (`uv run -q $K/sheet.py`, as in `../deck-review/SKILL.md`). Decide the one point the whole video should leave before writing any scene.
2. **Take the current notes** with `pull`. If stderr lists pages whose notes differ from the page JSON, the notes were edited on screen; ask which is right before rewriting them.
3. **Write the script** into `notes_vids.json`, one key per page (page numbers from 1), by "How to write" and "Audio tags" below. Write the whole deck before reviewing, because the bridges between scenes depend on their neighbors.
4. **Bring `lint` to zero `要修正`.** Look at every `要確認` and fix it, or keep it when it is intended (an example phrase that contains 「5 ページ」 is fine).
5. **Ask one child agent to review once** with [prompt_review.md](prompt_review.md) (a new child without the conversation, the same model as the main agent; "How to ask" in `../deck-review/SKILL.md`). Verify each finding against `deck.md` before fixing, then run `lint` again. Do not ask for a second round; the script has no layout, so the parent can check its own fixes.
6. **Push.** `push` refuses while `要修正` remains. It writes only the speaker notes, so on-screen edits and comments on the slides stay. See "What push does".
7. **Deliver.** Give the URL, the scene count and total characters (from `lint`), the point the video leaves and where the story turns, what you left out of the voice, and the backup file.

## How to write

- [slides-speaker-notes-001] スライドを読み上げない。動画全体の筋を優先する。冒頭で、この動画を通して見てほしい点を先に言う。各シーンの頭に、前のシーンからのつなぎの一言を入れ、章の切り替わりでは、ここから何の話かを言う。最後にその点に戻り、次の一歩を呼びかけて終える。
- [slides-speaker-notes-002] 細部は声では飛ばしてよい（ファイル名、パス、コマンド、表のセルの値）。表や細かいページでは「動画を止めて見てください」と言う。動画にページ番号はないので、「〇ページ」とページを指さない（前後のシーンは「さきほどの」「このあと」で指す）。
- [slides-speaker-notes-003] 縮めても、事実は元のノートとスライドから変えない。割合や件数は、何のうちの数かを残す。同じ数の言葉（「10 本」など）が別のまとまりを指すときは、どのまとまりかを言う。断り書き（「モデルで差が出た」など）を落とさず、言い過ぎにしない。
- [slides-speaker-notes-004] 文体は「です・ます」。1 シーンの目安は 100〜300 字（扉は 50〜100 字）、全体は発表者向けのノートの半分ほどにする。
- [slides-speaker-notes-005] 読み誤りそうな語は、読みで書く（pi は「パイ」、$32 は「32 ドル」、ハイフンでつないだ名前は空白で区切る〔deck-review は「deck review」〕）。voiceover は文字をそのまま読むので、記号（/ ~ # $ 括弧 「」）を使わない。言い切れない長い文は 2 つに分ける。

## Audio tags

- [slides-speaker-notes-006] **Tags take effect only with Vids' Conversational voices** (the Gemini voices, such as Nyla and Elio). The voices offered when making a video from slides (Narrator, Educator, Teacher, and so on) read the tags aloud as text (the user checked this on 2026-10-21). Write the tags anyway; the steps to change the voice are in "In Vids".
- [slides-speaker-notes-007] **Use only these tags.** Pauses: `[short pause]` before a turn in the talk (before 「だから」「ただ」「そこで」「2 つ目」), `[medium pause]` between paragraphs (1–2 per scene), `[long pause]` only at the boundary between the halves of the video. Emotion, at most one per scene: `[enthusiasm]` for the opening and the closing, `[curiosity]` for a question to the audience, `[determination]` for a recommendation or a conclusion. Put a tag after 「。」, and never put two tags in a row. Most scenes need only pauses.
- To use another tag, first confirm its exact name in Vids (type `[` in a Voiceover script; the menu lists Pace, Pauses, Emotion, Style, and Sounds), because a name Vids does not know is read aloud. `lint` reports names outside the list above as `要確認`.
- One scene holds at most 2,500 characters (Vids' limit; `lint` reports it as `要修正`).

## What push does

- The first time, it saves the current notes to `notes_presenter_<date>.json` in `build/`. If any `notes_presenter_*.json` exists, it saves nothing, so the file keeps the presenter's notes. To present with the deck again, `push` that file.
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
