# Registering the scheduled cleanup

Every scheduler gets only the one line in `prompt.txt`. The steps are in SKILL.md and run.md, readable from Claude Code, Codex, and pi with the AI Deck Factory plugin installed. Set the working folder to the workspace (the folder with `factory.toml`). When switching schedulers, stop the old one before registering the new one (even if they overlap, step 0 of run.md stops a second run within 12 hours). When installing through a conversation (step 5 of `../../INSTALL.md`), the agent uses a scheduler among its own tools; if it has none, ask the user to set up option 5 by hand. A scheduler not listed below also works if it meets the conditions in step 5 of INSTALL.md.

A run fixes only safe things such as the index; rule changes become proposals (top of SKILL.md). Proposals are applied when the user replies 「適用」 in the thread or conversation that ran it. With setups that leave no conversation, such as launchd, look at the workspace's `.factory/dreaming/log/<YYYYMMDD>.md` and ask in another conversation, e.g. 「dreaming の P0001 を適用して」 (proposal contents and status are in the rule ledger; `ledger.py pending`).

The default time is 5:00 every day (materials are sometimes made at night, so run in the early morning once the previous day's conversations are complete. On 2026-10-07 the user changed it from 18:00). If there is nothing to do, it finishes immediately. Replace 5:00 in the examples below with the chosen time.

| | When it runs | Runs missed while asleep | Where to reply to proposals | Claude Code memory |
|---|---|---|---|---|
| 1. T3 Code (the author uses this) | While T3 Code is running | Unconfirmed | A thread dedicated to the cleanup | Readable |
| 2. Claude Code Desktop | While the app is open and the Mac is awake | Only the last run within 7 days, on wake | The Scheduled conversation in the sidebar | Readable |
| 3. Codex app | While the app is running | Unconfirmed | A new chat per run | Readable (written only when applying) |
| 4. Omnigent | While the connected PC is online | Not run | A new conversation per run | Unconfirmed |
| 5. launchd + CLI | While logged in | Run once on wake, combined | Ask in another conversation | Readable |

## 1. T3 Code

**Create a thread dedicated to the cleanup, and register `schedule_task` from that thread with `bindToCurrentThread: true`** (each run's result appears in that thread. Reply 「適用」 to proposals there too).

- The mode that creates a new thread per run (`bindToCurrentThread: false`) does not work. A new thread tries to prepare a git worktree and, in this folder that is not under git, stops with "Workspace preparation failed … Failed to resolve the VCS driver". Setting the project default to `local` did not change this (confirmed 2026-10-06 on T3 Code 0.0.46-nightly).
- Create the thread with `t3_thread_launch` directly in the working folder (`workspaceStrategy: {"type":"root"}`). If the workspace is not a T3 Code project yet, first look for it with `t3_project_list`, and create it with `t3_project_create` if missing. Use the provider normally used for making materials (the author uses Claude; switched from Codex on 2026-10-06). Set `runtimeMode` to `auto` (approval is left to the agent, so it does not stall with no one around).
- `t3_thread_launch` stops with "capability_denied" unless the calling thread is full-access (default) (2026-10-07, it stopped when called from an auto thread). Make the calling thread full-access before creating.
- `schedule_task` contents: `prompt` is the one line in `prompt.txt`, `schedule` is `{"type":"fixed_time","timeOfDay":"05:00"}`, `clientRequestId` is `dreaming-daily` (it becomes the end of the ID).
- When registering from another thread (such as the thread doing the install through conversation), use the `message` of `t3_thread_launch` to ask the new thread: 「この中身で `schedule_task` を `bindToCurrentThread: true` で登録し、ID と次に回る時刻を返して」. Wait with `t3_thread_wait`, and check that `boundThreadId` in `list_scheduled_tasks` is that thread.
- The author's registration (recreated 2026-10-07): the ID is `scheduled-task:command:mcp:91ea5ee6-38a0-49ff-ba0e-6afcd3cc5921:schedule-task:dreaming-daily`. It is bound to the dedicated cleanup thread 「dreaming（指示とスキルの定期の整理）」 (`mcp:d9cb28f9-831a-4767-a164-1da9b0b63a53`).
- To move it to another thread, call `update_scheduled_task` with `bindToCurrentThread: true` from the destination thread. The ID does not change (confirmed 2026-10-07). If the thread is deleted, the task stays bound to the deleted thread, so move it the same way.
- Check and stop: `list_scheduled_tasks` (`boundThreadId` is the bound thread), `update_scheduled_task` (`enabled: false`), `delete_scheduled_task`. To run now, `run_scheduled_task_now`.
- Claude's `auto` safety checks can stop operations (2026-10-06, while writing these steps, an operation writing instructions that run unattended was stopped as "Create Unsafe Agents"). Skip stopped operations and note them in the report ("Rules for running" in run.md).
- It was first registered with Codex `gpt-6.1-sol`, which ran the first cleanup (`log/20261006.md`) and applied its proposals.

## 2. Claude Code Desktop

Inside a Desktop conversation, you can just ask for it (values as below). To create it by hand: Code tab, **Routines** → **New routine** → **Local** (Desktop 1.1.5368 or later). Do not use the CLI `/loop` (it stops when the conversation closes) or cloud routines (they cannot read local files).

- Name: `dreaming`. Instructions: the one line in `prompt.txt`. Permission mode: Auto (Accept edits if Auto is unavailable). Working folder: the workspace (the author's is `~/Documents`). Do not use a worktree (it is not under git).
- Schedule: Daily, 5:00
- After creating it, run it once with **Run now**, and choose "always allow" for the permission prompts that appear. They are not asked again.
- The prompt is stored at `~/.claude/scheduled-tasks/dreaming/SKILL.md`. Time, folder, and model are kept on the app side.
- Source: https://code.claude.com/docs/en/desktop-scheduled-tasks (checked 2026-10-06)

## 3. Codex app

Ask in a Codex conversation opened on this folder.

```text
毎日 5:00 に、このプロジェクトで新しいチャットを開いて、次を実行する scheduled task を作ってください: <prompt.txt の 1 行>
```

- The RRULE is `FREQ=DAILY;BYHOUR=5;BYMINUTE=0`. In a folder not under git, it runs directly in that folder.
- It runs in the default sandbox without human confirmation. `workspace-write` has no web access (the resurvey in step 7 of run.md becomes a report only).
- The definition is stored at `~/.codex/automations/<id>/automation.toml` (the format is not public, so do not write it by hand).
- Source: https://learn.chatgpt.com/docs/automations?surface=app (checked 2026-10-06)

## 4. Omnigent

Create it with the `sys_scheduled_task_create` tool (every agent has it. In the Web UI it is Automations).

- `name` is `dreaming`, `prompt` is the one line in `prompt.txt`, `rrule` is `FREQ=DAILY;BYHOUR=5;BYMINUTE=0`. `timezone` is the local IANA time zone (`Asia/Tokyo`, etc.). The default is UTC, so always set it.
- `agent_id` is the agent of the current conversation (`sys_agent_list`). `execution_target` is `connected_host` (`managed_sandbox` cannot read the workspace). Set `host_id` to this PC and `workspace` to the absolute path of the workspace (`workspace` is rejected without `host_id`. Without it, it runs in the home folder).
- `permission_mode` is `auto` for a Claude Code agent (`claude-native`). Other harnesses cannot set it, so check whether the agent's default runs without human confirmation.
- Missed runs are not retried, and failed runs are not repeated (it waits for the next run). To run now, use the Web UI or `POST /v1/scheduled-tasks/{id}/run`. Check and stop: `sys_scheduled_task_list`, `sys_scheduled_task_update` (`state: paused`), `sys_scheduled_task_delete`.
- Unconfirmed: whether `scripts/sessions.py` can read the logs of conversations Omnigent starts (it reads those of Claude Code, Codex, and pi). After registering, tell the user this.
- Sources: https://omnigent.ai/docs/build/scheduled-tasks and https://github.com/omnigent-ai/omnigent/blob/main/docs/AUTOMATIONS.md (checked 2026-10-15)

## 5. launchd + CLI (running without an app)

In the workspace, run `scripts/run.sh claude` (`claude -p --permission-mode auto`), `scripts/run.sh codex` (`codex exec -s workspace-write`), or `scripts/run.sh pi` (`pi -p`). If the pi package was installed only in the workspace (`pi install -l`), first save the workspace trust with `/trust` in an interactive pi (`-p` cannot ask for trust, and without saved trust the package is not loaded. `../../docs/pi.md`). Point `<run.sh>` at a path that does not change between versions (Claude Code's plugin cache changes per version). For Claude Code, use the `installLocation` of `ai-deck-factory` in `claude plugin marketplace list --json` (`~/.claude/plugins/marketplaces/ai-deck-factory` if installed from GitHub, or that checkout if installed from a local path); for pi with `pi install -l`, `<workspace>/.pi/git/github.com/mats16/ai-deck-factory`. Under that, `skills/dreaming/scripts/run.sh`. Put the plist at `~/Library/LaunchAgents/local.dreaming.plist`. Write paths starting from `/Users/...` (plist does not expand `~`).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.dreaming</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string>
    <string><run.sh></string>
    <string>claude</string>
  </array>
  <key>WorkingDirectory</key><string><workspace></string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/dreaming.log</string>
  <key>StandardErrorPath</key><string>/tmp/dreaming.log</string>
</dict></plist>
```

- Install: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.dreaming.plist`. Stop: `launchctl bootout gui/$(id -u)/local.dreaming`. Run now: `launchctl kickstart gui/$(id -u)/local.dreaming`.
- With cron (Linux, etc.), add one line via `crontab -e`: `0 5 * * * cd <workspace> && /bin/sh <run.sh> claude >> /tmp/dreaming.log 2>&1`.
- Unconfirmed: macOS access permissions when launchd reads `~/Documents` and similar folders. After installing, run `kickstart` once and look at `/tmp/dreaming.log`.
