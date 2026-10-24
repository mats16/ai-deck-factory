# AI avatars

Open from `SKILL.md` only when the user names scenes for an AI avatar (step 1 of "Steps" in `SKILL.md`), or when adjusting avatars made earlier.

`avatars` lists the 30 avatars that speak with a Conversational voice (name, ID, style on screen, and voice). `--avatar` takes the name, the ID, or a voice (the avatar that speaks with it: `--avatar Elio` is Oliver). Each of the 30 voices has exactly one avatar, and the pages without an avatar are read in the avatar's voice, so the voice stays the same across scenes. With both `--voice` and `--avatar`, `vids.py` stops unless the avatar speaks with that voice and names the one that does. To add avatars to a video made with voice only, pass its voice (`update --avatar Elio --layout …`). Only Oliver has been used to make a video (2026-10-22); if another avatar fails, tell the user which one.

- The Classic avatars (Olivia, James, and so on) are not supported. They are the only ones offered when making a video from slides on screen, and they cannot use a Conversational voice. `vids.py` passes the avatar ID directly, after building the scenes, which is how the other avatars can be used.
- Each scene's avatar is its own generated video: the scene's notes are read by the avatar's voice, and the face moves with it. Avatar generations are limited per user and month by the Workspace edition (Business Starter 10, Standard and Plus 25 in Google's help; 50 on the account tested, 2026-10-22), and reset on the 1st; voiceovers are not counted on business and education editions. More needs a higher edition or the AI Expanded Access add-on, which the user's admin decides. A new video uses one per scene with an avatar, `update` one per scene whose notes changed, and moving uses none. `vids.py` makes one avatar first, and if the rest do not fit, places that one and stops.
- The avatar sits in a circle cut from the center of its 16:9 video, on top of the page. Realistic avatars bring their room as background. Avoid avatars on pages where nothing can be hidden (`none` in the JSON).

## Adjusting avatars in the editor (Chrome DevTools)

`vids.py` makes, replaces, deletes, and places avatars; use it for those, because it counts generations and saves the same way every time. Its placement only picks a corner and a size from the slides' images. Fine adjustments are better done on screen in the Vids editor through the Chrome DevTools (MCP), where the scene is seen as it plays: the face off center in the circle, a crop or a size that needs a nudge, a border or shadow, or an overlap that shows only in Vids.

- Do it after `create` or `update` has finished. Open the Vids in a tab of the Chrome that `vids.py` uses, look at each avatar scene (a screenshot of the canvas), and fix only what is wrong: drag the avatar or its corner handles, use 「Crop video」 and 「Mask video」 in the toolbar, or 「Format options」 (size, position, drop shadow). Take a screenshot again after each fix.
- Close the tab when done, before any `vids.py` command, because saves fail while the editor is open.
- `vids.py` keeps those edits: `update` replaces an avatar in its current place and keeps its shape, crop, border, and shadow, changing only the video. `update --layout` moves avatars back to the JSON, so after editing on screen, do not pass `--layout` unless the JSON is meant to win (update the JSON or leave it out). A new video by `create` (step 7) starts without those edits.
- If an editor control or its behavior differs from this description, describe what you see to the user instead of guessing.
