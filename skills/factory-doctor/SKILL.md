---
name: factory-doctor
description: Check the prerequisites for running AI Deck Factory. Looks at Python and uv, the workspace (factory.toml, AGENTS.md), overlapping skills, Google authentication (a token in an environment variable or a credentials JSON), whether templates and Drive folders are reachable, and the MCP servers for gathering material, and prints how to fix each problem. Use after factory-init, in a new environment, on 401 or 403, when 「factory.toml が見つからない」 appears, or when asked 「環境を確かめて」 or 「doctor して」.
---

# Check the prerequisites

```sh
cd <workspace>
python3 <this skill's folder>/scripts/doctor.py          # local and Google APIs
python3 <this skill's folder>/scripts/doctor.py --local  # local only (does not call APIs)
```

Prints one item per line as 「OK」, 「要修正」, or 「要確認」. Exits 1 if there is at least one `要修正`.

## What it checks

| Item | What to do on `要修正` or `要確認` |
|---|---|
| Python 3.11 or later, uv | Install them. Without uv, the image measurements (`box_pad.py`, `doc_layout.py`, `sheet.py`) and lint's phrase-break check (BudouX) do not run |
| `factory.toml`, `AGENTS.md` (`CLAUDE.md`, `references_index.md`) | Place them with factory-init |
| `factory.source` | No longer used (factory-kaizen clones by itself). Tell the user and remove it |
| Overlapping skills | The workspace's `.agents/skills/` or `.claude/skills/` has a skill with the same name. It is loaded twice along with the plugin's, so ask the user which one to use (the user decides whether to remove the workspace's copy) |
| `google.quota_project`, `slides.templates`, `drive.*` | Fill them in as in factory-init step 3 |
| `slides.themes` (the format of an earlier version) | Move the theme table to the workspace's `themes/slides/<name>.json` (`kind: theme`; write the colors under `colors` with the same names, and do not write `url`), move `url` to 「<名前> = "<url>"」 in `[slides.templates]`, and delete the table. Names that have a template can also be copied with `slides.py theme <url>` (templates from before 2026-10-16 lack the colors not stored in the theme, `copyright`, `mono`, and `description`, so copy those from the table). Before moving, ask the user where to keep the history left in the table's comments (JSON cannot hold comments) |
| `themes/slides/<name>.json`, theme files, `slides.default_theme` | For invalid values, fix the reported location and check with `slides.py lint <file>`. For a theme that has a template but no file, copy it with `slides.py theme <URL>` |
| Theme descriptions | A theme without `description` cannot be chosen per material by the agent. Write what the theme is and which materials and audience it is for (`deck-build/slides.md` §3) |
| `review.*`, the plan review and post-delivery fixes in AGENTS.md | Fix `review.*` to values within the template's range (`"ai"`, `"human"`, 1 to 3). If AGENTS.md still contains the earlier template's 「人がレビューするかも選んでもらう」 or 「ユーザーに返す前に、スキル `deck-review` で全体をレビューする」, show it to the user and then replace it with the current template text (follow `[review] plan_reviewer`; newly created materials use `deck-review`, and after delivery use `deck-practices`'s "Requests after delivery") (it is a workspace rule, so do not change it silently) |
| Google authentication | Have the user run the printed command (`gcloud auth application-default login --scopes=…`). How to get a token is in the comments of `[google]` in `factory.toml` |
| Templates and Drive folders | Anything that cannot be opened has a wrong URL or is not shared. Ask the owner to share it, or fix the URL |

## What to check outside the script

The script cannot see whether the tools for gathering material (`deck-practices/materials.md`) are available. Check whether each tool written in `[sources]` of `factory.toml` (an MCP server or skill name) is in your own tool list, and return the missing ones together as `要確認`. If `[sources]` is empty, ask the user which tools to use and write them. Materials can be built without them, but gathering material becomes manual.

## How to reply

Return the `要修正` and `要確認` items together with how to fix them. Separate what the user runs (login commands, share requests) from what you can fix (values in `factory.toml`). After fixing, run it again.
