# Gathering materials

Read this when gathering internal materials and customer information (`SKILL.md` "How to start" steps 3 and 4, and 「調べもの」 in AGENTS.md). Handle confidential information as 「社外秘と顧客の情報」 in AGENTS.md says. Record what you read in `references.md` in the material's folder (see "Ledger" below).

- [materials-001] **Do not stall waiting on slow tools.** Two rules for waiting:
  - [materials-002] **One command runs at most 5 minutes.** Set the limit with the tool's `timeout` (the argument of pi's bash or Claude Code's Bash). macOS has no `timeout` command. When a command hits the limit, do not rerun the same command. Narrow the scope (period, path, `git clone --depth 1`, only the needed files through the GitHub API) or postpone it.
  - [materials-003] **Report on a subagent at 20 minutes.** Do not wait with `sleep`. Move ahead with other materials and the skeleton of the outline, and add the result when it arrives (`SKILL.md` "Working practices", deck-practices-013). If there is no result 20 minutes after delegating, tell the user what you are waiting for, since when, and what you are doing meanwhile (do not wait for approval).

## Internal materials (reuse and messaging)

The tools are listed by role in the workspace's `factory.toml` under `[sources]` (`search`, `chat`, `meetings`, `wiki`, `crm`, `usage`). For a role that is not listed, ask the user to paste the material or URL. How to use each tool and where to look in that company are in the workspace's `rules/deck-practices/materials.md`.

- **Internal cross search** (`search`): search here first for materials on the same theme (「<製品名> pitch deck」「<テーマ> 日本語」「<顧客の業種> 事例」 and so on).
- **File storage**: read the contents of the Google Slides and Docs you found (for Google Slides, `../deck-build/scripts/gslides.py` also works).
- **Internal chat** (`chat`): product channels and field channels hold the latest wording, cautions, and constraints that the docs do not mention. When you find a constraint that is not in the docs, write it in customer-facing materials only as far as the docs support. Bug details, answers, and future plans are internal information, so write them in `社内メモ_*.md`.
- **Internal wiki** (`wiki`): enablement materials and guides for the field. If there is a list of Japanese materials, cite the official Japanese pages.
- **How to reuse:** try in this order: use as is → crop figures and similar parts → rebuild in this folder's style while keeping the layout → take only the intent and make it new. How to decide and how to do it are in [reuse.md](reuse.md).

## Customer information

- **Meeting records** (`meetings`): read both meetings with the customer and internal meetings with sales. Read the summary first, and look at the transcript only when you need evidence.
- **Internal chat** (`chat`): search by customer name, and look at the internal account channel and the channel shared with the customer. Day-to-day exchanges that meeting records miss are here.
  - [materials-004] When a colleague pastes comments from another company or the customer (a transcription such as 「いただいた問い合わせの内容もシェアします」), confirm whose words they are before interpreting them. Do not read a transcription as the colleague's own remark, and do not add your own reading such as 「聞き違い」. For words whose meaning you do not know (such as 「ブロック ID」), write that you do not know, and add them to what needs checking.
  - [materials-005] When a link the tools cannot read (such as a separate workspace shared with the customer) is given as background for the request, ask the user to paste its text in your first reply. Until it arrives, do not fix the audience and the questions in the outline. When it arrives, copy the projects, teams, and areas the customer wrote into the top of the outline (if you proceed without reading the text, information about the project under consideration is lost).
- **Customer ledger** (`crm`): deals, owners, and basic customer information.
- **Usage and consumption** (`usage`): note each number with its source (which table, which period, which unit). Usage amounts are internal information, so do not write them in customer-facing materials (「社外秘と顧客の情報」 in AGENTS.md).

## Ledger (references.md)

Manage the URLs of materials you referred to in `references.md` in the material's folder, so that you do not search for the same material again and again. Do not keep copies. When you reread, read from the URL (for Google Slides, `../deck-build/scripts/gslides.py` also works).

- One item per line: the source (material name and URL, meeting ID, chat link), the pages or parts to look at, the source's last updated date, the date you checked it, whether it can go outside the company, and what it is used for (keep items you decided not to use, with the reason).
- Look at `references.md` before searching. If the source's last updated date is newer than the date you checked it, reread it.
- It contains internal URLs and materials that cannot go outside the company, so do not put it in the deliverables (reuse.md §2).
- When the material is finished, add the materials you used to `references_index.md` (the overall index) at the top level.
