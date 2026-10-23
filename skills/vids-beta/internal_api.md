# Calls that vids_client.js makes

The calls the Vids editor makes, as observed in the editor's own traffic (build `editors.videos-frontend_20261014`, checked 2026-10-21; the avatar calls on 2026-10-22). None is a published API; the numbers below are positions in arrays and can change with any release. `scripts/vids_client.js` holds the exact request bodies. This file says what each call is for and what to watch for. How the browser authenticates the calls is not described here; the client uses the tab's own session and never returns it.

## Calls

| Call | Purpose | What goes in and out |
|---|---|---|
| `GET docs.google.com/videos/d/<id>/edit` | Open the document | The page has the parameters for the calls below (`info_params`) and the document model (`modelChunk`: a list of commands and the revision). Each run makes its own session ID (16 hex digits). |
| `POST appsgenaiserver-pa.clients6.google.com/v1/genai/streamGenerate`, `[0][0] = 33` | Draft of the video from slides | In: the Vids ID, the Slides ID, the page objectIds, each page's script, a voice preset, the music settings. Out: the commands that build the scenes (a JSON string inside the response, starting `[["[[4,`) and the assets (images, background music). The script is not rewritten when it is given (the call `[0][0] = 144`, which writes a script, is not used). |
| `POST …/genai/generate`, `[0][0] = 254` | Voiceover of one scene with a Conversational voice | In: the script and the Gemini voice name (`Achird` for Elio; the avatar panel sends it in lower case). Out: a temporary audio file (`[<key>, "bard_storage", null, "lookup_temp_data"]`). The avatar panel's Preview is this same call. |
| `POST …/genai/streamGenerate`, `[0][0] = 124` | AI avatar video of one scene (checked 2026-10-22) | In: the Vids ID, the audio key from `254`, the avatar ID (`["actor50", null, 1]`), and `[1, null, [[null, "1", 1187]]]` (meaning unknown; kept as the editor sent it). Out: an operation name (`agency_session_id/…`) and the month's avatar quota (`["50", null, "46", …, ["<reset time>"], 0]`: limit, left). |
| `GET appsgenaiserver-pa.clients6.google.com/v1/operations/<name>?$alt=protojson` | Progress of the avatar video | Polled every few seconds. When done (`[2] = 1`) it has the video (`[<key>, "bard_storage", "temp_data", "lookup_temp_data", "…video.mp4…", 1280, 720, ["<sec>", <nanos>]]`). A 3-second script took about a minute. |
| `POST docs.google.com/videos/u/0/d/<id>/copyimages` | Copy the images of the slides into the Vids | Form `photo_info`: the Slides blob → a new blob. |
| `POST …/insertmedia` | Bring a media file into the Vids | Form `insertable_media_type`: `CONTRIB_SERVICE_AUDIO` (the voiceover from `generate`), `CONTRIB_SERVICE_VIDEO` (the avatar video from the operation), `LMS_AUDIO` (music from the draft), `BLOBSTORE_AUDIO` (Classic voices; not used). Out: `ni` (the media ID) and `sb` (bytes; the voiceover is a 24 kHz 16-bit mono WAV, so milliseconds = (sb − 44) / 48). |
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
| `[60, <id>, [<keys to remove>], [key, value, …]]` | Change keys of an audio element (checked 2026-10-23 by trimming the music on screen). Trimming the end sends `122` = 1 and `123` = the end in the source, in ms; trimming the start sends `120` = 1, `121` = the start in the source, and `173` = the same value, the clip's start in its scene (`184`). `176` stays the length of the source. The music plays from `121` to `123`, or to the end of the video. On a new music element `118` is the volume (20), `175` = 1800 and `204` = −6 are not known (perhaps a fade in ms and ducking in dB). |
| `[18, [<scene>], [], [16, <ms>]]` | Set the length of a scene. |
| `[3, <id>, <type>, <transform>, [key, value, …], <scene>]` | Add an element to a scene. The edit page's model holds every element in this form. The transform is `[scaleX, shearY, shearX, scaleY, x, y]` in EMU; the page is 365760 × 205740 (960 × 540 × 381). An avatar is a video (`157`, natural size from keys `8`, `9`) with `202` = 2 (1 for a voiceover), `177` = 3, `194` the MD5 of its script, `176` length in ms, and `58` the media. Masked with the ellipse it becomes type `8`, whose base is 120000 × 120000 EMU; then `87`/`88` are the video's height and width, and `79`, `80`, `84`, `85` the crop (horizontal scale, vertical scale, left and top offsets as fractions of the frame; a centered square from 16:9 is `79` = 16/9, `84` = −7/18). A border set on screen is `19` (color, `"#BD2B26"`; `[null, 3]` is none), `22` (weight in EMU, 3048 for 8 px), and `18` = 1. |
| `[35, <id>, <position>, [0, 20, …, 7, <ms>], <scene>]` | Put an element in the scene's timing (start 0, length ms). |
| `[36, <position>, <scene>]` and `[0, [<id>]]` | Take an element out of the timing, and delete it (Delete on screen). |
| `[5, [<id>], [<keys to remove>], [key, value, …]]`, `[6, <id>, <transform>]`, `[19, [<id>], <type>]` | Change keys, move or resize, change type (the mask). |

## Pitfalls (2026-10-21, avatars 2026-10-22)

- A save is sometimes refused with HTTP 550 (`[["er",…,550,…,13],["di",<40–63>]]`). Nothing is written. It happened most on a Vids that had been saved dozens of times in the last hour: there every save, even inserting one character, was refused for several minutes, while the same save on another Vids went through; after about 5 minutes without saves it went through again. Later, after about an hour of heavy testing, the first save of new Vids was refused too, and went through again 10 minutes later. Waiting the `di` value and resending, three times, was not enough. The revision in the edit page was not behind (checked right after saves). The client still resends after `di` + 5 seconds, up to three times.
- A save is always refused while the same Vids is open in an editor tab.
- The tab that runs the client can be lost partway (it moves to another page, for example a sign-in page, or is closed; CDP answers `Inspected target navigated or closed`). Everything not yet saved is lost with it: a 38-page `create` lost its tab twice in a row on 2026-10-23. The server takes one piece at a time (the draft, one voiceover, one media file, one save), and the client builds the video, as the editor does. So the client saves the scenes first and then the voiceovers as they are made, and a new tab goes on from the document.
- `[20]` in the same save as text commands (`15`, `16`) was refused three times out of three, and the same text commands alone went through (this may have been the refusals above, which were not known then). Send text commands in their own save, without `[20]`.
- The empty first scene of a new Vids cannot be deleted in the same save that adds the new scenes. A scene that has audio cannot be deleted until its audio is deleted (`[59]`).
- Use the draft's voice preset `docs-preset-voice-achird`. With `docs-preset-voice-achernar` (Nyla) the next save failed three times out of three (this may also have been the refusals above). The preset does not decide the voice of the video, because the client replaces every voiceover.
- Once, setting Drive `appProperties` on the empty Vids in `files.create` was followed by a failed first save (not tried again). Set them after building.
- AI avatars (2026-10-22): the editor's JS has the table of avatars (`actor01`–`actor23` Classic with `voicelm` voices, `actor24`–`actor53` with Gemini voices; each has one fixed voice). Making a video from slides on screen offers only the Classic avatars, but `124` takes any ID. The client makes the avatar after the draft, scene by scene, instead of asking the draft for one.
- The avatar quota is per account and month (50 on 2026-10-22, reset on the 1st). `quotaSummary` (`[null, 1, [9]]`) answered `999999` and is not the avatar quota; the client reads the count from the `124` response.
- The draft request has a fixed Drive ID next to the voice preset. It is not one of the user's files (the Drive API returns 404); it is kept as the editor sent it.
