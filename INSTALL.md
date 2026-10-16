# AI Deck Factory を会話で入れる（エージェントが読む手順）

README の「会話で入れる」のプロンプトを貼られたエージェントが従う手順。プラグインを入れ、ワークスペースを作り、factory-doctor で確かめるまでを、1 つの会話で進める。手で入れる手順は README の「入れ方」。

このファイルは curl で読む（`curl -fsSL https://raw.githubusercontent.com/mats16/ai-deck-factory/main/INSTALL.md`）。WebFetch のように要約して返す道具では、コマンドと手順が欠ける。

## 決まり

- **この会話には、まだスキルがない。** 入れたスキルは次の会話から読み込まれる。この会話では `/ai-deck-factory:factory-init` や `/skill:factory-init` を呼ばずに、入れた場所の `SKILL.md` を開いて従う（4）。
- **ワークスペースだけに入れる。** `~/.claude/settings.json`・`~/.pi/agent/settings.json` は変えない。ほかのフォルダの会話にはスキルが出ない。
- **ユーザーが決めることは聞いてから進める。** 場所、ツールを入れるか、`factory.toml` の値。ブラウザが開くログイン（`gcloud auth application-default login`）は、ユーザーに回してもらう。
- **あるファイルは上書きしない。** factory-init の `init.py` も上書きしない。
- 手順の `<ワークスペース>` と `<プラグイン>` は、1 と 3 で決まったパスに置き換える。スクリプトは今いるフォルダから `factory.toml` を探すので、ワークスペースのコマンドは `cd <ワークスペース> &&` を付けて回す。

## 1. 聞く

自分が Claude Code か pi かは聞かない（自分で分かる）。次の 3 つを 1 回でまとめて聞く（Claude Code なら AskUserQuestion）。

1. **ワークスペースにするフォルダ。** 資料（`Customers/`・`Internal/`・`Research/`）と `factory.toml` を置く。候補に、今の会話のフォルダと `~/Documents` を出す。なければ作る。すでに `factory.toml` か `AGENTS.md` があれば、足りないものだけ置くことを伝える。
2. **全社の共有テーマのフォルダ。** 会社でスライドのテーマ（テンプレート）を配っていれば、その Google Drive のフォルダの URL。なければ「ない」。プロンプトに URL が書いてあれば聞かずに使う。4 で `factory.toml` の `[drive] shared_themes` に書く。
3. **定期の整理（dreaming）を回すか。** 会話の記録から、決まりに戻し忘れた指示を毎日拾うもの。選ぶのは「毎日 5:00 に回す（推奨）」「時刻を変える」「回さない」。どのスケジューラーに登録するかは聞かない（5 で、今の環境から決める）。

## 2. 前提を見る

```sh
python3 --version   # 3.11 以上
uv --version
git --version
```

足りないものは、入れ方を示し、ユーザーが良いと言ったら入れる。

- uv: `brew install uv`（macOS）か `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.11 以上: `brew install python@3.12` など。`python3` が古いままなら、このあとの `python3` を `uv run --python 3.11` に替えて回す。

## 3. プラグインを入れる

**Claude Code**

```sh
cd <ワークスペース>
claude plugin marketplace list --json | python3 -c "import json,sys; [print(m) for m in json.load(sys.stdin) if m['name']=='ai-deck-factory']"   # もうあるか
claude plugin marketplace add https://github.com/mats16/ai-deck-factory.git --scope project
claude plugin install ai-deck-factory@ai-deck-factory --scope project
claude plugin list --json | python3 -c "import json,sys; [print(p.get('readFromFolder') or p['installPath']) for p in json.load(sys.stdin) if p['id']=='ai-deck-factory@ai-deck-factory' and p['enabled']]"
```

- 1 つめで `ai-deck-factory` が出たら、`add` は飛ばす（名前は 1 つしか持てない。足すと前のものとぶつかる）。出た入れ元（`path`・`url`・`repo`）が、ここで入れるもの（GitHub）と違うときは、そのことと、ほかのワークスペースもその入れ元を読んでいることを伝え、そのまま使うかをユーザーに聞く。入れ元を勝手に替えない。
- 最後に出たパスが `<プラグイン>`。手元のパスから入れたなら checkout（`readFromFolder`）、GitHub から入れたなら写し（`installPath`）。

**pi**

```sh
cd <ワークスペース>
pi install -l git:github.com/mats16/ai-deck-factory
```

`<プラグイン>` は `<ワークスペース>/.pi/git/github.com/mats16/ai-deck-factory`。

どちらも `<プラグイン>/skills/factory-init/SKILL.md` があることを確かめる。

## 4. ワークスペースを作る

1. `<プラグイン>/skills/factory-init/SKILL.md` を開き、その手順に従う。「このスキルのフォルダ」は `<プラグイン>/skills/factory-init`、ほかのスキルのフォルダは `<プラグイン>/skills/<スキル>`。手順の 1（場所）は、ここの 1 で聞いたので飛ばす。3 の `[drive] shared_themes` は、ここの 1 の 2 で聞いた値を書く。3 の `[slides] default_theme`（既定のテンプレート）は、テンプレートを作り、共有のテーマを `slides.py theme <url>` で写したあとで、`<プラグイン>/skills/deck-template/SKILL.md` の「既定のテーマを選ぶ」に従って選択式で聞く（1 では聞かない。何を選べるかは、そろってから分かる）。
2. factory-init の最後の「確かめる」は、`<プラグイン>/skills/factory-doctor/SKILL.md` を開いて従う。要修正が 0 になるまで直す。Google のログインのように、ユーザーが回すものが残ったら、回してもらってから doctor をもう一度回す。

## 5. 定期の整理を登録する

1 の 3 で「回さない」なら飛ばす。渡すのは `<プラグイン>/skills/dreaming/prompt.txt` の 1 行で、作業フォルダは `<ワークスペース>`、時刻は 1 の 3 で決めたもの。登録のしかたの詳しいことは `<プラグイン>/skills/dreaming/schedule.md`（以下、schedule.md）。pi で回すときは、T3 Code の中でも手で入れるときも、先に対話の pi でワークスペースの trust を `/trust` で保存してもらう（人のいない回は trust を聞けず、保存していないとスキルが読まれない。`<プラグイン>/docs/pi.md`）。

1. **自分の道具にスケジューラーがあれば、それに登録する。** 道具の一覧から、定期の回を作る道具を探す（見えなければ「schedule」「scheduled task」で道具を探す）。使えるのは、次をすべて満たすものだけ。
   - 会話を閉じても、アプリを開き直しても残る。Claude Code の `/loop` のように、会話の中だけで動くものは使わない。
   - この PC で、`<ワークスペース>` を作業フォルダにして回る。クラウドや、回ごとに作るサンドボックス・git の worktree で回るものは使わない（ワークスペースのファイルと会話の記録を読めない）。
   - 人がいなくても、権限の確認で止まらない。

   時刻は手元の時間帯で書く（UTC が既定の道具もある）。2 つ以上あれば、この会話を動かしているアプリのものにする（T3 Code の中なら T3 Code）。よく使うものの値と注意は schedule.md にある（T3 Code の `schedule_task` は 1、Claude Code Desktop は 2、Omnigent の `sys_scheduled_task_create` は 4）。schedule.md にない道具でも、上を満たせば使い、登録した値を 6 で返す。
2. **なければ、手で入れてもらう。** Claude Code の CLI と pi には、会話を閉じても残るスケジューラーがない。launchd（macOS）か cron で `run.sh` を回す設定（schedule.md の 5）を、`<ワークスペース>`・run.sh のパス・時刻・引数（Claude Code なら `claude`、pi なら `pi`）を埋めて示し、入れる・すぐ回す・止めるのコマンドを添える。`~/Library/LaunchAgents/` と crontab は、エージェントが書かない（会話の外で毎日動くものを足すので、ユーザーが中身を見て入れる）。Claude Code Desktop を使っているなら、その Routines で作ってもよいことも添える（schedule.md の 2）。

登録したら、すぐ回して確かめる（道具の「すぐ回す」、launchd は `kickstart`）。権限の確認が出たら、ユーザーに許してもらう（次からは聞かれないようにする）。初めての回は 7 日前からの会話を見る。この回から 12 時間以内の次の回は、重ねないために止まる（dreaming の SKILL.md の 0）ので、6 で伝える。

## 6. 終える

次をまとめて返す。

- 置いたもの（init.py の「置いた」「残した」）と、`factory.toml` で埋めた値・空のままの値。既定のテーマ。
- 定期の整理を登録したスケジューラーと時刻。手で入れてもらうものが残っていれば、その手順。
- doctor の結果。残った要確認と、ユーザーが回すもの。
- 次からの開き方。**ワークスペースの直下で開く**（サブフォルダで開くと、プラグインのスキルも hook も読み込まれない）。
  - Claude Code: `cd <ワークスペース> && claude`。スキルは `/ai-deck-factory:deck-build` のように呼ぶ。
  - pi: `cd <ワークスペース> && pi`。初めては `/trust` で信頼を保存する（保存しないと、パッケージのスキルが出ない。dreaming の定期の回も読めない）。スキルは `/skill:deck-build` のように呼ぶ。
- 最初の資料は「〇〇向けの提案のスライドを作って」のように頼めばよい（スキル `deck-practices` から始まる）。

## うまくいかないとき

- **同じ名前のスキルがある。** ワークスペースの `.agents/skills/`・`.claude/skills/` に deck-build などがあると、二重に読まれる（pi ではプラグインのものが負ける）。doctor の「スキルの重なり」に出るので、どちらを使うかをユーザーに聞く。
- **入れる範囲、確かめ方、外し方。** Claude Code は `<プラグイン>/docs/claude-code-plugin.md`、pi は `<プラグイン>/docs/pi.md`。
