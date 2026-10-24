---
name: factory-migrate
description: Move a workspace made with an earlier version of AI Deck Factory to the current one. On 2026-10-24 the skills were renamed by what they make (deck- common, slides-, docs-, vids-), the plugin files were split by the situation they are read in, and the rule IDs were renamed to say what each rule is about. This moves the workspace's rules/ files to the new paths, rewrites rule IDs and paths in rules/, AGENTS.md, customers' memory.md, and the rule ledger (.factory/ledger.jsonl), after a backup, and then has you split overrides whose plugin file was split. Use when factory-doctor reports 「前の版のワークスペース」, after updating the plugin, or when asked 「移行して」「migrate して」.
---

# Move a workspace to the current version

Run in the workspace (the folder with `factory.toml`). `migrate.py` changes only the workspace's own files (`rules/`, `AGENTS.md`, `Customers/*/memory.md`, `.factory/ledger.jsonl`) and takes a backup first, because these hold the user's rules and their history.

```sh
M=<this skill's folder>/scripts/migrate.py
python3 $M check                 # what would move and change. Changes nothing
python3 $M apply                 # backup to .factory/migrate/<time>/, then move and rewrite
python3 $M rename-id <old> <new> # rename one workspace rule ID everywhere (rules/, AGENTS.md, memory.md, the ledger); only for a mistyped or colliding ID
```

## Steps

1. **Check.** Run `check` and show the user the list in one message (what moves, which files are rewritten). Do not wait for approval: the backup makes it reversible.
2. **Apply.** Run `apply` and relay its lines as they are (「控え」「移した」「写した」「書き換えた」「移していない」「要判断」).
   - 「移していない」: the new path already has a file. Open both, merge the old one's rules into the new one (keep the IDs), and delete the old one.
   - 「写した」 `checks.py`: slides lint reads `slides(p, r)` from `rules/slides-build/checks.py`, and document lint reads `doc(doc, r)` from `rules/docs-build/checks.py`. Delete the function each file does not use.
3. **Split the overrides of split files (「要判断」).** The plugin split some files (the list after 「要判断」 says into which). A workspace override (`rules/<skill>/<file>`) is shown only when its plugin file at the same path is opened, so a rule that adds to a section that moved would no longer be shown in the right place.
   - For each `ws-` rule listed under the line, `migrate.py` names the plugin file of the rules it refers to. Open that plugin file and check that the rule adds to or overrides that section. If it names nothing, decide from the content.
   - Move the rule line (with its ID) to `rules/<skill>/<that file>`. A rule may stay where it is when its plugin section is still in that file.
   - Keep the rule's ID when you move it: IDs name what a rule is about, not its file (`deck-practices/rules.md` "Rule IDs").
4. **Check again.** Run `check` (it should print 「移すものはない（今の版）」) and `factory-doctor` (`python3 <factory-doctor folder>/scripts/doctor.py --local`).
5. **Report.** In one message: what moved, the rules you split and where they went, and the backup folder. Tell the user that deleting the backup is their call.

## Notes

- `apply` and `check` can be run any number of times. Files already in the current form are not changed.
- It does not touch the material folders (`Customers/<customer>/<material>/`, `Internal/`, `Research/`), because they are records of past work. Old IDs and paths in an outline or memo stay as they were; look them up in `scripts/ids_20261024.json` when needed.
- In the ledger, the fields that hold people's own words (`quote`, `a`, `reason`) are not rewritten, so the user's words stay as said; old IDs or names in them stay too.
- The ID map is `scripts/ids_20261024.json` (`ids`: old → new plugin ID; `prefixes`: old → new prefix, used for `ws-` IDs and for plugin IDs no longer in the plugin). From now on IDs do not change (`deck-practices/rules.md` "Rule IDs"); if a future version must rename some, it adds another dated map, and `migrate.py` applies the maps in date order.
- To undo, copy the backup folder's contents back over the workspace.
