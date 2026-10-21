---
name: vids-beta
description: Beta, for the period until Google Vids has a public editing API. Make a Google Vids video from a built Google Slides deck, or update a video made this way, through Vids' internal editor calls run in a Chrome reached by Chrome DevTools. Use only when the user explicitly asks to make a video from slides or to update such a video 「スライドから動画を作って」「Vids にして」「動画も更新して」「声を替えて」; do not use it or suggest it on your own, for example after writing speaker notes. Every page becomes a scene read by a Conversational voice (Elio by default; audio tags work). Covers setup, `scripts/vids.py create`, `update` (only the scenes whose notes changed; `--rebuild` after page changes), `check`, `voices`, `download`, and the pitfalls of the internal calls.
---

# Videos from slides (Google Vids, beta)

**Beta.** Vids has no public API for editing. This skill writes a video through the same internal calls the Vids editor makes, from a tab of a Chrome that is signed in to the target Google account. The empty Vids, the MP4, and the record on the file go through the public Drive API, and the notes through the Slides API (`../deck-build/scripts/gapi.py`, the same authentication as building slides). The internal calls are listed in [internal_api.md](internal_api.md). They can change without notice, so this skill is a stopgap: when Google publishes an editing API, a skill on that API replaces this one. When a step fails with an error from 「Vids の内部 API」, see "When it fails".

Make the video from the deck itself, and do not copy the Slides into a separate deck for the video, because two decks with the same pages drift apart at every fix and `update` follows only the deck recorded on the Vids. The script of each scene is the page's speaker notes as they are, and every deck's notes are written as that script (`../slides-speaker-notes/SKILL.md`).

## Setup

- **A Chrome DevTools (MCP) that can reach the target Google account.** `vids.py` connects to that Chrome's remote debugging port, opens a background tab on `docs.google.com/videos`, runs `scripts/vids_client.js` there, and closes the tab. The Cookie and tokens stay inside that tab; the script returns only IDs, counts, and lengths. Use the Chrome that the Chrome DevTools MCP of this conversation drives, if it is signed in to the account that owns the deck. If it is not running, start it the way that MCP's setup says.
- The address is `--browser <URL>`, else the environment variable `VIDS_BROWSER`, else `browser` under `[vids]` in factory.toml, else `http://127.0.0.1:9222`.
- Run with `uv run` (it installs `websockets`). `--selftest` also needs `node`.
- The public OAuth token (gcloud ADC) does not work for Vids' editing calls (403, checked 2026-10-21), which is why a signed-in Chrome is needed.

## Steps

Run anywhere under the workspace (factory.toml is found from the current folder upward).

```sh
V=<vids-beta folder>/scripts/vids.py
uv run $V create <Slides URL> [--voice Elio] [--name 名前] [--no-music]
uv run $V update <Vids URL or the Slides URL> [--voice 名前] [--rebuild [--no-music]]
uv run $V check <Vids URL> [<Slides URL>]
uv run $V voices
uv run $V download <Vids URL> <out.mp4>
```

1. **Check the notes.** Run `lint` of slides-speaker-notes on the deck's notes. If they are not a script yet (a deck built before the default, or notes holding sources and supplements for readers), rewrite them in the same deck by the steps of slides-speaker-notes, and move what readers need from the notes to the source line, the body, or the Appendix of that deck (in the page JSON, then build and lint by `../deck-build/SKILL.md`). Ask the user before moving anything to the pages. `vids.py` stops if a page's notes are longer than 2,500 characters (Vids' limit per scene). A page with empty notes becomes a scene without voice.
2. **Close the Vids in every browser tab** before `create` (on `--rebuild`), `update`, and `check`, because saving fails with HTTP 550 while the same Vids is open in an editor tab. `vids.py` stops if it sees such a tab in the Chrome it connects to; tabs in other browsers it cannot see.
3. **`create`.** It makes the Vids in the folder of the Slides, with the name `<Slides の名前>_動画` unless `--name` is given. It turns every page into a scene, puts each page's notes as the scene's script, makes the voiceover of every scene with the chosen voice, adds the background music that Vids picks (`--no-music` to leave it out), and deletes the empty scene that a new Vids starts with. Then it reads the Vids back and stops with 「要修正」 unless the scene count, every scene's script, and every voiceover match the notes and every voiceover has the chosen voice (`check` does the same with the recorded voice). It records the Slides ID and the voice on the Vids file (Drive `appProperties`: `vidsSlides`, `vidsVoice`), so `update` needs only the Vids URL. A 4-page deck took about 90 seconds, and a 38-page deck about 10 minutes (22 minutes of voiceover); keep the command in the foreground or in a background job that waits that long.
4. **`update` after the notes change** (for example after `speaker_notes.py push`). Pass the Vids URL, or the Slides URL to find the Vids made from it by `create` (it stops if there are none or several). It compares each scene's script and voiceover with the current notes and the recorded voice (the voice is read from the label of each voiceover, such as 「… - Elio」), and replaces the script and the voiceover of the scenes that differ, keeping the other scenes, the music, and edits on screen to the scenes. `--voice` records the new voice first and then replaces every scene, so if it stops partway, `update` without `--voice` finishes the rest. It stops if the number of pages differs from the number of scenes.
5. **`update --rebuild` after pages change** (layout, text on the page, pages added, removed, or reordered). It builds all scenes again from the slides in the same Vids (same URL and sharing), then deletes the old scenes with their voiceovers and music. Edits made on screen in Vids are lost; say so before running it.
6. **Deliver.** Give the Vids URL, the scene count, the voice, and the total length of the voiceovers that `create` prints. Give an MP4 only when asked (`download`; it waits for Vids to render, up to 10 minutes).

## Voices

`voices` lists the 30 Conversational voices (the display name in Vids, the name of the Gemini voice, and the description on screen). `--voice` takes either name. The default is Elio, the default of the Vids editor. Only Elio and Nyla have been used to make a whole video (2026-10-21); if another voice fails, tell the user which one.

- The Classic voices (Narrator, Educator, and so on) are not supported. They are the only voices offered when making a video from slides on screen, and they read audio tags aloud (`../slides-speaker-notes/SKILL.md`, slides-speaker-notes-004).
- The voice shown in Vids' voiceover panel is the user's last choice, not a setting of the video. If the user later presses 「Update voiceover」 on screen, Vids uses the voice in the panel, so tell them to choose the same voice there first.

## When it fails

- **HTTP 550 on `save`.** The save was refused and nothing was written. It happens after many saves in a short time (to the same Vids, for example `update` right after `--rebuild`, and also to other Vids of the same account), and then lasts several minutes. The client waits and resends up to three times (a few minutes in all). If it still fails, check that no tab has the Vids open, wait about 10 minutes, and run the same command again: a failed `create` moves its Vids to the trash, and `update` starts from what is saved. When `create` or `update` had to wait, it prints 「保存が 550 で断られ、待って送り直した」.
- **`Chrome につながらない` / `Vids を開けない`.** The Chrome is not running with remote debugging, or is not signed in to the target account.
- **`下書きの応答にシーンのコマンドがない`, `音声の応答に一時ファイルがない`, or an error from `genai`.** Vids changed its internal calls, or the account cannot use Gemini in Vids. Do not guess new formats from the error; report it to the user with the message, and record what changed in [internal_api.md](internal_api.md) after checking it in the editor.
- **`--rebuild` stopped partway.** The new scenes may have been saved while some old scenes are still there, so `update` stops on the scene count. Run `update --rebuild` again: it treats every scene there as old and deletes them after building.
- After any failure, run `check` before telling the user the video is ready.
