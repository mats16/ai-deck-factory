# Editing rules (routing corrections and verifying rules)

Open this when you receive a correction from the user and when you add or change a rule. How to record a correction and routing it on the spot are needed in every conversation, so they are in 「修正の指示」 in AGENTS.md. This file covers where to route it and how to verify it. Misses are picked up every day by the periodic cleanup (`../dreaming/`) from the conversation logs, which proposes rule changes with a recommendation (they go in when the user replies; among cleanups of overlaps and stale text, those that only delete a whole rule are applied first and then reported).

## Rule layers

[deck-rules-001] Rules come in two layers, and the workspace takes precedence. For customer-facing materials, the customer's memory ("Customer memory" below) sits on top. Treat the workspace as one product whose rules and checks grow through accumulated exchanges, and file as Issues only what should be fixed upstream (the plugin) (the owner fixes it from the Issue).

| Layer | Location | Content | Who changes it |
|---|---|---|---|
| Workspace | `AGENTS.md` (what every conversation needs), `rules/<skill>/<file>` (what only material-making needs; adds to or overrides the plugin file at the same path), `rules/slides-build/checks.py` and `rules/docs-build/checks.py` (checks added to the slide and document lint) | That person's or organization's rules and checks; what grows from corrections | The making conversation routes them on the spot. dreaming proposes with a recommendation (`ledger.py propose`; `apply` on the user's reply; among cleanups of overlaps and stale text, those that only delete a whole rule are applied with `propose --auto` and then reported). The history is kept in the rule ledger (`.factory/ledger.jsonl`). If the workspace is under git, also commit |
| Plugin | `skills/` (this folder, etc.; the installed location is read-only) | Rules, checks, scripts, and templates that are the same for everyone | Verify on past materials with the `factory-kaizen` skill, then file an Issue (the owner does the same). The owner fixes it from the Issue, and it arrives via `update` |

- **Do not rewrite the plugin's installed location (`~/.claude/plugins/cache/…` etc.).** Reinstalling erases the changes.
- **There is a mechanism so that `rules/` is not forgotten.** When you open a plugin file (Claude Code: Read, Bash, Skill; pi: read, bash), the plugin hook (`hooks/rules_overlay.py`) then shows the `rules/` file at the same path. In environments where it does not appear (a host without hooks), open `rules/` yourself.
- **Grow checks in the workspace too.** Rules a machine can check go first into `rules/slides-build/checks.py` (slides) or `rules/docs-build/checks.py` (documents) (lint loads them every time; how to write them: `rules/README.md`). Once it is clear that they help other people too, file an Issue to move them into the plugin's lint (`slides-build/scripts/lint.py`, `docs-build/scripts/doc_lint.py`, or `deck-practices/scripts/textlint.py` for rules shared by both).
- **Promoting to the plugin.** Workspace rules and checks that help other people too (not that person's taste or a customer's circumstances) become a 「プラグインに上げる」 proposal from dreaming. Apply it with the `factory-kaizen` skill (clone the original repository, fix it, compare before and after on past materials, and file an Issue with the reason, the background, the verification results, images if it is visual, and the diff of the proposed change). When the owner's fix arrives, delete the copy in the workspace's `rules/`.
- The results of re-researching `deck-research/` (`sources.md` and the fixes to the skills that reflect it) are plugin knowledge, so file them as Issues with `factory-kaizen`. The logs and `state.md` stay in the workspace's `Research/deck_research/`.

## Customer memory

[deck-rules-005] Preferences per customer are kept not as rules but as memory in `Customers/<customer>/memory.md`. Rules (`AGENTS.md`, `rules/`) take the form 「〜のときは〜する」, apply to every material, and are verified by lint or review. Memory is what applies across materials about that customer's audience (honorifics, the tone of the language, the audience's position and interests, past decisions and rejected proposals); use it as a premise when making a material and check against it in review. Who the customer is (business, organization, products in use and their setup, engineers' preferences) goes not in memory but in the customer's `profile.md`, with sources and dates (the `customer-profile` skill). When unsure, separate by the form of the sentence. 「〜である」 (a fact: 「エンジニアは Terraform で全部管理している」) goes in the profile; 「〜にする・しない」 (an instruction: 「Terraform のコード例を入れる」) goes in memory. For an instruction decided from a fact, write the fact in the profile and the instruction in memory.

- **Format:** one item per line, with `[ws-memory-<number>]` at the head of the line (`ledger.py next ws-memory`). As with rules, the date and the original wording go in the ledger (`ledger.py add --to ws-memory-<number>`; recurrences are counted too). It is read every time, so keep it short.
- **When it appears:** when you open that customer's `構成案*.md`, `社内メモ_*.md`, or `references.md`, the plugin hook then shows it (Claude Code, Codex, pi). In environments where it does not appear, open it yourself. It takes precedence over the workspace rules and the plugin.
- **What not to put in:** personal names, spend amounts, internal-only assessments. Write them in `社内メモ_*.md` so they do not slip into customer-facing materials. Things only for that material (the wording on this page) get `--to 戻さない`.
- **Going stale:** it stops holding when the person in charge or the organization changes. If it conflicts with the user's newer words, update it to the newer one (the earlier date: `ledger.py why <ID>`). If you cannot tell which one is current, ask.
- **Generalizing:** if preferences with the same gist are in the memory of two or more companies, move them into `rules/` as a rule independent of the customer (dreaming's 4c). Do not promote directly from memory to the plugin.

## Routing corrections

Record findings in the workspace's rule ledger (`.factory/ledger.jsonl`) with [scripts/ledger.py](scripts/ledger.py). Do not create a 「修正の指示」 section in the outline. In the rule text, write only the ID and a short reason; link the date, the user's words, which material, and whether the user decided it to the ledger by the ID (`ledger.py why <ID>` shows them). The ledger contains customer information, so do not copy it outside `.factory/` (Issues, PRs, chat).

```sh
L=<deck-practices folder>/scripts/ledger.py
python3 $L add --deck <material folder> --quote "<the user's words (verbatim where possible)>" --fix "<what was fixed>" --to <destination> --check <lint・レビュー・なし> [--decided] [--plan <AI・人>]
python3 $L list --deck <material folder>     # findings for that material. With --open, only those whose destination is 「未」
python3 $L route <c-ID> <destination>        # the destination was decided or changed
python3 $L next <prefix>                     # the ID for a new rule
```

- `--to` is one of: a rule ID (`ws-slides-visual-<number>`; customer memory: `ws-memory-<number>`), a file, `戻さない`, or `未`.
- `--decided` marks what the user clearly decided (chose from proposals, or stated 「〜にする」 outright). dreaming puts statements that conflict with it on hold for a decision and does not overturn it. Plugin rules are defaults and may be overridden in the workspace.
- `--plan` marks a structure miss. Attach it to findings after the plan review (SKILL.md §5) that changed the audience, the question, the claim, or the order and were not raised in that review (for ① AI, not among the findings received at the end of the outline; for ② human, not in what the user said when shown the outline; in both cases, excluding those in the list of questions for the user). The value is the plan review chosen for that material (`AI` or `人`). The outline review does not check against rules, so as not to constrain the maker's ideas, so only its misses are counted here (the weekly table and the last line of `ledger.py rules`; dreaming's 5). If a finding turns out to be a miss after it was added, mark it with `ledger.py plan <c-ID> <AI・人>`. Remove a wrong mark with `plan <c-ID> なし`.
- **Rule IDs:** one per item, with `[<area>-<topic>-<3 digits>]` at the head of the line (e.g. `- [ws-slides-visual-<number>] 収まらない表は 2 枚に分ける（文字を小さくすると読めなくなる）。`). The ID says what the rule is about, not where it is written, because the ledger links each rule's corrections, recurrences, and review results by ID, and a changed ID cuts that history. The area is `deck` (common to slides and documents), `slides`, `docs`, `vids`, or `factory`; the topic comes from the list printed by `ledger.py topics` (`TOPICS` in `scripts/ledger.py`), with a language suffix only where a topic is split by language (`vids-voice-ja`). To find where a rule is written, run `ledger.py where <ID>`.
  - **Never change an ID once given.** Keep it when the rule moves to another file or skill, when files are split or renamed, and when its scope grows (a slides rule that now also applies to documents keeps its `slides-` ID; say so in the text).
  - **Splitting and merging:** when one rule becomes two, the original keeps the ID and the new one gets the next number (`ledger.py next <prefix>`). When two become one, keep one ID and route the other's corrections to it (`ledger.py route`).
  - **Do not reuse numbers,** even of deleted rules (`ledger.py next` counts the ledger too).
  - **A new topic** is added to `TOPICS` before use; `ledger.py next` refuses prefixes not in it, and the selftest fails on plugin IDs outside it (so typos and drifting topics are caught). Do not name a topic after a skill or a file (`slides-build`, `pages`), so an ID is not read as a location.
  - **How a rule is checked is not part of the ID** (rules move from review to lint over time). Say it in the rule text (「lint が〜」), and have the lint check name the rule ID it enforces.
  - **The workspace** uses `ws-` and the same topics (`ws-slides-visual`), plus `ws-agents` (the workspace `AGENTS.md`) and `ws-memory` (a customer's `memory.md`). Items written by hand without an ID get only an ID from dreaming when they become a destination. When referring to a rule from other text, write `slides-visual-012` without brackets (a bracketed ID is read as the place where that rule is written; `ledger.py`).

- **Merge them and put them in the form of rules.** Merge items with the same gist and rewrite them as rules of the form 「〜のときは〜する」. Fixes only to this material's content (the wording on this page, replacing a number) get `--to 戻さない`.
- **Destination:** route to the workspace ("Rule layers" above). Rules that every conversation needs (handling confidential information, folders, research, the gist of 「いい資料の考え方」) go in AGENTS.md. Do not add to AGENTS.md what only material-making needs (Codex truncates AGENTS.md at 32 KiB, and Claude Code reads all of it every time; dreaming's 4h). How to make things goes in `rules/<skill>/<file>` at the same path as the plugin file in the list below (e.g. for visuals, `rules/slides-build/visual.md`; if it does not exist, create it and write 「`slides-build/visual.md` に足す・上書きする」 at the top). When you want to change a plugin rule, also write it in `rules/`, adding the ID of the rule it overrides in the form `- [ws-slides-visual-<number>] 〜は〜にする（slides-visual-012 より優先。<短い理由>）。` (dreaming uses `ledger.py candidates` to see the number of overrides and stale overrides of rules removed from the plugin). When overriding a section without an ID, write 「プラグインの〇〇の節より優先」.
  - Workflow steps and what to keep: [SKILL.md](SKILL.md)
  - Structure, wording, 「文体」, and how to write sources: [content.md](content.md); what changes by material type: [content_customer.md](content_customer.md), [content_internal.md](content_internal.md), [content_explain.md](content_explain.md)
  - Visuals: [visual.md](../slides-build/visual.md) in slides-build (decks), [visual.md](../docs-build/visual.md) in docs-build (documents)
  - Reuse: [reuse.md](../slides-build/reuse.md)
  - Sources and the ledger: [materials.md](materials.md)
  - Building with the Slides API: the files listed in `../slides-build/SKILL.md` (`pages.md`, `diagrams.md`, `commands.md`, `themes.md`, `images.md`, `api.md`, `legacy.md`)
  - Building with the Docs API, and checking and delivering documents: `../docs-build/SKILL.md`
  - Checking and delivery: `../slides-build/SKILL.md` and `../deck-review/SKILL.md` (the review aspects are in the request texts `prompt_slides.md` and `prompt_doc.md`)
  - How to edit these rules: this file
  - Per-customer preferences: the customer's `memory.md` ("Customer memory" above)
  - About the customer (business, setup, engineers' preferences): the customer's `profile.md` (`../customer-profile/SKILL.md`)

  Also decide how to verify it ("Verifying rules" below).
- **Ask before routing:** items that conflict with the current rules, and items where you cannot tell whether they are just for this material or should become a rule. Set `--to 未` and ask in the report.
- **Record and report.** After routing, set the destination to the rule ID with `ledger.py route`. At the end of the report, write which correction was routed to which rule (`ledger.py list --deck <material folder>`).

## Verifying rules

[deck-rules-002] Rules are followed when making a material and verified with the same rules at the finish. Decide how to verify a rule before adding more considerations. When adding a rule, also decide which of the following verifies it.

| Method | What it looks at | How to write it |
|---|---|---|
| lint | Things countable in JSON (font size, font, character count, position, page order). Positions that JSON cannot estimate (line wrapping, page breaks, padding inside boxes) are measured on the images Google renders (`box_pad.py`, `doc_layout.py`) | Say in the rule text that lint checks it (「lint が〜」 in a Japanese rule, "lint flags …" in an English rule) and add the check to the workspace's `rules/slides-build/checks.py` (when promoting upstream, move it to `lint.py` and `--selftest`). Add it the first time; do not wait for a recurrence |
| Review | What AI judges from images, text, the outline, and the rule text (the storyline, the impression of the wording, the meaning of diagrams, how margins and density look) | No tag (rules that do not say lint checks them are checked in review). Check which of aspects 1–5 in the deck-review request texts (decks: `prompt_slides.md`; documents: `prompt_doc.md`) covers it; if none does, add it to an aspect |
| Principle | 「いい資料の考え方」 in AGENTS.md (details in content.md §0) | Do not make it a condition. Use it as the basis for review questions |

- [deck-rules-003] **Do not force what cannot be counted into lint.** It leads to writing just to pass lint (「禁句をほかの空疎な語に置き換えるだけにしない」 in content.md §6). Do not remove the places where AI judges by looking at images and the rule text.
- [deck-rules-004] **Do not force a good-or-bad binary.** For a lint `要確認`, either fix it or state why it stays. In review, things the rules do not decide, things that can be read either way, and things whose fix would change the point become 「聞く」, and are returned to the user with the reason for hesitating and proposals ("What to fix" in deck-review).
- **Fix or remove conditions with many false hits.** Rules whose `要確認` always end as 「残した」 (`lint.py --stats`), and conditions that missed something the user fixed after the check passed, are reviewed in dreaming's 5.
- **Count how well rules work.** The rule ledger counts, per rule, findings raised even though a rule exists (recurrences) and the results of rows in the deck-review findings table with the rule column filled in (「直した・残した（誤り）・聞く」) (`ledger.py rules`, `why <ID>`). A rule with continuing recurrences and 「直した」 is not being followed when making, so push it down into a check or a making step. A rule with continuing 「残した（誤り）」 needs rewording. A rule that produces no findings may simply be followed, so do not remove it for that reason alone. The next move per rule (push down, rewrite, add a condition, promote, delete the copy, revisit the override) is printed by `ledger.py candidates`.
