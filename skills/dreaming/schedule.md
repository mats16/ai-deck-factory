# 定期の整理の登録のしかた

どのスケジューラーでも、渡すのは `prompt.txt` の 1 行だけ。手順は SKILL.md にあり、AI Deck Factory のプラグインを入れた Claude Code と pi から読める。作業フォルダはワークスペース（`factory.toml` のあるフォルダ）にする。スケジューラーを替えるときは、前のものを止めてから登録する（重なっても、SKILL.md の 0 で 12 時間以内の 2 回目は止まる）。

回すときに直すのは索引などの危なくないものだけで、決まりの変更は提案になる（SKILL.md の冒頭）。提案は、回したスレッドか会話で「適用」と返すと入る。launchd のように会話の残らない回し方では、ワークスペースの `.factory/dreaming/log/<YYYYMMDD>.md` を見て、別の会話で「dreaming の P1 を適用して」と頼む。

時刻は毎日 5:00（夜にも資料を作ることがあるので、前の日の会話がそろった朝方にする。2026-10-07 にユーザーが 18:00 から変えた）。何もなければすぐ終わる。

| | 動くとき | 寝ていて逃した回 | 提案への返事 | Claude Code のメモリ |
|---|---|---|---|---|
| 1. T3 Code（いま使っている） | T3 Code が動いているとき | 未確認 | 整理専用のスレッド | 読める |
| 2. Claude Code Desktop | アプリが開いていて、Mac が起きているとき | 7 日以内の最後の 1 回だけ、起きたときに回す | サイドバーの Scheduled の会話 | 読める |
| 3. Codex app | アプリが動いているとき | 未確認 | 回ごとの新しいチャット | 読める（書くのは適用のときだけ） |
| 4. launchd + CLI | ログインしているとき | 起きたときに 1 回にまとめて回す | 別の会話で頼む | 読める |

## 1. T3 Code

**整理専用のスレッドを作り、そのスレッドから `schedule_task` を `bindToCurrentThread: true` で登録する**（毎回の結果がそのスレッドに出る。提案への「適用」もそこで返す）。

- 回ごとに新しいスレッドを作る方式（`bindToCurrentThread: false`）は使えない。新しいスレッドは git の worktree を用意しようとして、git で管理していないこのフォルダでは「Workspace preparation failed … Failed to resolve the VCS driver」で止まる。プロジェクトの既定を `local` にしても変わらなかった（2026-10-06、T3 Code 0.0.46-nightly で確かめた）。
- スレッドは `t3_thread_launch` で作業フォルダの直下（`workspaceStrategy: {"type":"root"}`）に作る。提供元は Claude にする（資料を作るのが Claude なので。2026-10-06 にユーザーが Codex から切り替えた）。`runtimeMode` は `auto`（承認をエージェントに任せるので、人がいなくても止まらない）。
- `t3_thread_launch` は、呼ぶスレッドが full-access（default）でないと「capability_denied」で止まる（2026-10-07、auto のスレッドから呼んで止まった）。呼ぶスレッドを full-access にしてから作る。
- `schedule_task` の中身: `prompt` は `prompt.txt` の 1 行、`schedule` は `{"type":"fixed_time","timeOfDay":"05:00"}`、`clientRequestId` は `dreaming-daily`（ID の末尾になる）。
- いまの登録（2026-10-07 に作り直した）: ID は `scheduled-task:command:mcp:91ea5ee6-38a0-49ff-ba0e-6afcd3cc5921:schedule-task:dreaming-daily`。結びついているのは、整理専用のスレッド「dreaming（指示とスキルの定期の整理）」（`mcp:d9cb28f9-831a-4767-a164-1da9b0b63a53`）。
- 別のスレッドに移すときは、移す先のスレッドから `update_scheduled_task` を `bindToCurrentThread: true` で呼ぶ。ID は変わらない（2026-10-07 に確かめた）。スレッドが消えると、タスクは消えたスレッドに結びついたまま残るので、そのときも同じように移す。
- 確かめる・止める: `list_scheduled_tasks`（`boundThreadId` がつながっているスレッド）、`update_scheduled_task`（`enabled: false`）、`delete_scheduled_task`。すぐ回すのは `run_scheduled_task_now`。
- Claude の `auto` は、安全チェックが操作を止めることがある（2026-10-06、この手順を書いたときに、無人で動く指示を書く操作が「Create Unsafe Agents」で止まった）。止まった操作は飛ばして報告に書く（SKILL.md の「回すときの決まり」）。
- 最初は Codex の `gpt-6.1-sol` で登録し、初回の整理（`log/20261006.md`）と提案の適用はそれで回した。

## 2. Claude Code Desktop

Code タブの **Routines** → **New routine** → **Local**（Desktop 1.1.5368 以降）。

- Name: `dreaming`。Instructions: `prompt.txt` の 1 行。権限モードは Auto（なければ Accept edits）。作業フォルダ: `~/Documents`。worktree は使わない（git で管理していない）。
- Schedule: Daily、5:00
- 作ったら **Run now** で 1 回回し、出た権限の確認に「always allow」を選ぶ。次からは聞かれない。
- プロンプトは `~/.claude/scheduled-tasks/dreaming/SKILL.md` に置かれる。時刻・フォルダ・モデルはアプリの側にある。
- 出典: https://code.claude.com/docs/en/desktop-scheduled-tasks（2026-10-06 に確認）

## 3. Codex app

このフォルダを開いた Codex の会話で頼む。

```text
毎日 5:00 に、このプロジェクトで新しいチャットを開いて、次を実行する scheduled task を作ってください: <prompt.txt の 1 行>
```

- RRULE は `FREQ=DAILY;BYHOUR=5;BYMINUTE=0`。git で管理していないフォルダでは、そのフォルダで直接動く。
- 既定のサンドボックスで、人の確認なしに動く。`workspace-write` では web が使えない（SKILL.md の 7 の調べ直しは報告だけになる）。
- 定義は `~/.codex/automations/<id>/automation.toml` に置かれる（形式は公開されていないので、手で書かない）。
- 出典: https://learn.chatgpt.com/docs/automations?surface=app（2026-10-06 に確認）

## 4. launchd + CLI（アプリなしで回すとき）

ワークスペースで `scripts/run.sh claude`（`claude -p --permission-mode auto`）か `scripts/run.sh codex`（`codex exec -s workspace-write`）、`scripts/run.sh pi`（`pi -p`）を回す。pi のパッケージをワークスペースだけに入れた（`pi install -l`）なら、先に対話の pi でワークスペースの trust を `/trust` で保存しておく（`-p` は trust を聞けず、保存していないとパッケージが読まれない。`../../docs/pi.md`）。run.sh はプラグインの元のリポジトリのものを指す（Claude Code のキャッシュのパスは版ごとに変わる）。`~/Library/LaunchAgents/local.dreaming.plist` に置く。`<ユーザー名>` は自分のものにする（plist では `~` が展開されない）。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.dreaming</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string>
    <string>/Users/<ユーザー名>/Projects/ai-deck-factory/skills/dreaming/scripts/run.sh</string>
    <string>claude</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/<ユーザー名>/Documents</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/dreaming.log</string>
  <key>StandardErrorPath</key><string>/tmp/dreaming.log</string>
</dict></plist>
```

- 入れる: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.dreaming.plist`。止める: `launchctl bootout gui/$(id -u)/local.dreaming`。すぐ回す: `launchctl kickstart gui/$(id -u)/local.dreaming`。
- 未確認: launchd から `~/Documents` を読むときの macOS のアクセス許可。入れたら一度 `kickstart` して `/tmp/dreaming.log` を見る。
