# Calls that vids_client.js makes

The calls the Vids editor makes, as observed in the editor's own traffic (build `editors.videos-frontend_20261014`, checked 2026-10-21). None is a published API; the numbers below are positions in arrays and can change with any release. `scripts/vids_client.js` holds the exact request bodies. This file says what each call is for and what to watch for. How the browser authenticates the calls is not described here; the client uses the tab's own session and never returns it.

## Calls

| Call | Purpose | What goes in and out |
|---|---|---|
| `GET docs.google.com/videos/d/<id>/edit` | Open the document | The page has the parameters for the calls below (`info_params`) and the document model (`modelChunk`: a list of commands and the revision). Each run makes its own session ID (16 hex digits). |
| `POST appsgenaiserver-pa.clients6.google.com/v1/genai/streamGenerate`, `[0][0] = 33` | Draft of the video from slides | In: the Vids ID, the Slides ID, the page objectIds, each page's script, a voice preset, the music settings. Out: the commands that build the scenes (a JSON string inside the response, starting `[["[[4,`) and the assets (images, background music). The script is not rewritten when it is given (the call `[0][0] = 144`, which writes a script, is not used). |
| `POST …/genai/generate`, `[0][0] = 254` | Voiceover of one scene with a Conversational voice | In: the script and the Gemini voice name (`Achird` for Elio). Out: a temporary audio file (`[<key>, "bard_storage", null, "lookup_temp_data"]`). |
| `POST docs.google.com/videos/u/0/d/<id>/copyimages` | Copy the images of the slides into the Vids | Form `photo_info`: the Slides blob → a new blob. |
| `POST …/insertmedia` | Bring a media file into the Vids | Form `insertable_media_type`: `CONTRIB_SERVICE_AUDIO` (the voiceover from `generate`), `LMS_AUDIO` (music from the draft), `BLOBSTORE_AUDIO` (Classic voices; not used). Out: `ni` (the media ID) and `sb` (bytes; the voiceover is a 24 kHz 16-bit mono WAV, so milliseconds = (sb − 44) / 48). |
| `POST …/save` | Apply commands to the document | Form: `rev` (the revision the commands are based on), `bundles` (`[{commands, sid, reqId}]`), and `blobIdMap` (`PLACEHOLDER_<sid>_<n>` → media ID) when commands refer to new media. The response gives the new revision. |
| `POST …/prefs` | The user's preferences | Choosing a voice in the voiceover panel saves only `flix-previous_voiceover_voice` here. It is not part of the video. Not used. |

## Commands in `save`

| Command | Meaning |
|---|---|
| `[20]` | Sent first in the first save after a draft (as the editor does). |
| `[4, [ … ]]` | A group of commands applied together. |
| `[12, <scene>, …, 0]` | A scene (in the model; the draft's commands create them). |
| `[13, <position>, 0, null, <scene>]` | Delete a scene (the position is its index in the current order). |
| `[15, "<scene>:notes_text", null, <index>, <text>]` | Insert text into the scene's script. |
| `[16, "<scene>:notes_text", null, <start>, <end>]` | Delete the script's text from start to end (end not included). |
| `[58, <id>, [key, value, …]]` | Add an audio element. Keys: `177` kind (3 voiceover, 2 music), `184` the scene it belongs to, `176` length in ms, `194` the MD5 (Base64) of the script it was made from (a different value shows "Voiceover outdated"), `181` the label on the timeline, `58` the media (a placeholder in `blobIdMap`). |
| `[59, <id>]` | Delete an audio element. |
| `[18, [<scene>], [], [16, <ms>]]` | Set the length of a scene. |

## Pitfalls (2026-10-21)

- A save is sometimes refused with HTTP 550 (`[["er",…,550,…,13],["di",<40–63>]]`). Nothing is written. It happened most on a Vids that had been saved dozens of times in the last hour: there every save, even inserting one character, was refused for several minutes, while the same save on another Vids went through; after about 5 minutes without saves it went through again. Later, after about an hour of heavy testing, the first save of new Vids was refused too, and went through again 10 minutes later. Waiting the `di` value and resending, three times, was not enough. The revision in the edit page was not behind (checked right after saves). The client still resends after `di` + 5 seconds, up to three times.
- A save is always refused while the same Vids is open in an editor tab.
- `[20]` in the same save as text commands (`15`, `16`) was refused three times out of three, and the same text commands alone went through (this may have been the refusals above, which were not known then). Send text commands in their own save, without `[20]`.
- The empty first scene of a new Vids cannot be deleted in the same save that adds the new scenes. A scene that has audio cannot be deleted until its audio is deleted (`[59]`).
- Use the draft's voice preset `docs-preset-voice-achird`. With `docs-preset-voice-achernar` (Nyla) the next save failed three times out of three (this may also have been the refusals above). The preset does not decide the voice of the video, because the client replaces every voiceover.
- Once, setting Drive `appProperties` on the empty Vids in `files.create` was followed by a failed first save (not tried again). Set them after building.
- The draft request has a fixed Drive ID next to the voice preset. It is not one of the user's files (the Drive API returns 404); it is kept as the editor sent it.
