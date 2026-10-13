# AI Deck Factory を会話で入れる（エージェントが読む手順）

README の「会話で入れる」のプロンプトを貼られたエージェントが従う手順。プラグインを入れ、ワークスペースを作り、factory-doctor で確かめるまでを、1 つの会話で進める。手で入れる手順は README の「入れ方」。

このファイルは curl で読む（`curl -fsSL https://raw.githubusercontent.com/mats16/ai-deck-factory/main/INSTALL.md`）。WebFetch のように要約して返す道具では、コマンドと手順が欠ける。

## 決まり

- **この会話には、まだスキルがない。** 入れたスキルは次の会話から読み込まれる。この会話では `/ai-deck-factory:factory-init` や `/skill:factory-init` を呼ばずに、入れた場所の `SKILL.md` を開いて従う（4）。
- **ワークスペースだけに入れる。** `~/.claude/settings.json`・`~/.pi/agent/settings.json` は変えない。ほかのフォルダの会話にはスキルが出ない。
- **ユーザーが決めることは聞いてから進める。** 場所、プラグインに Issue を出すか、ツールを入れるか、`factory.toml` の値。ブラウザが開くログイン（`gcloud auth application-default login`）は、ユーザーに回してもらう。
- **あるファイルは上書きしない。** factory-init の `init.py` も上書きしない。
- 手順の `<ワークスペース>` と `<プラグイン>` は、1 と 3 で決まったパスに置き換える。スクリプトは今いるフォルダから `factory.toml` を探すので、ワークスペースのコマンドは `cd <ワークスペース> &&` を付けて回す。

## 1. 聞く

自分が Claude Code か pi かは聞かない（自分で分かる）。次の 2 つを 1 回でまとめて聞く（Claude Code なら AskUserQuestion）。

1. **ワークスペースにするフォルダ。** 資料（`Customers/`・`Internal/`・`Research/`）と `factory.toml` を置く。候補に、今の会話のフォルダと `~/Documents` を出す。なければ作る。すでに `factory.toml` か `AGENTS.md` があれば、足りないものだけ置くことを伝える。
2. **プラグインに直しを出すか（factory-kaizen）。** 使うだけなら「出さない」。出すなら、このリポジトリの checkout（持ち主でなければ `gh repo fork mats16/ai-deck-factory --clone` で作った fork）のパス。

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

1 の 2 で checkout を渡されたら、GitHub の代わりにそのパスから入れる（会話は checkout をそのまま読む。README の「入れ方」）。

**Claude Code**

```sh
cd <ワークスペース>
claude plugin marketplace list --json | python3 -c "import json,sys; [print(m) for m in json.load(sys.stdin) if m['name']=='ai-deck-factory']"   # もうあるか
claude plugin marketplace add https://github.com/mats16/ai-deck-factory.git --scope project   # checkout なら URL の代わりにそのパス
claude plugin install ai-deck-factory@ai-deck-factory --scope project
claude plugin list --json | python3 -c "import json,sys; [print(p.get('readFromFolder') or p['installPath']) for p in json.load(sys.stdin) if p['id']=='ai-deck-factory@ai-deck-factory' and p['enabled']]"
```

- 1 つめで `ai-deck-factory` が出たら、`add` は飛ばす（名前は 1 つしか持てない。足すと前のものとぶつかる）。出た入れ元（`path`・`url`・`repo`）が、ここで入れるもの（GitHub か、1 の 2 の checkout）と違うときは、そのことと、ほかのワークスペースもその入れ元を読んでいることを伝え、そのまま使うかをユーザーに聞く。入れ元を勝手に替えない。
- 最後に出たパスが `<プラグイン>`。手元のパスから入れたなら checkout（`readFromFolder`）、GitHub から入れたなら写し（`installPath`）。

**pi**

```sh
cd <ワークスペース>
pi install -l git:github.com/mats16/ai-deck-factory   # checkout なら git:… の代わりにそのパス
```

`<プラグイン>` は `<ワークスペース>/.pi/git/github.com/mats16/ai-deck-factory`（checkout から入れたなら、そのパス）。

どちらも `<プラグイン>/skills/factory-init/SKILL.md` があることを確かめる。

## 4. ワークスペースを作る

1. `<プラグイン>/skills/factory-init/SKILL.md` を開き、その手順に従う。「このスキルのフォルダ」は `<プラグイン>/skills/factory-init`、ほかのスキルのフォルダは `<プラグイン>/skills/<スキル>`。手順の 1（場所）と 2（元のリポジトリ）は、ここの 1 で聞いたので飛ばす。
2. factory-init の最後の「確かめる」は、`<プラグイン>/skills/factory-doctor/SKILL.md` を開いて従う。要修正が 0 になるまで直す。Google のログインのように、ユーザーが回すものが残ったら、回してもらってから doctor をもう一度回す。

## 5. 終える

次をまとめて返す。

- 置いたもの（init.py の「置いた」「残した」）と、`factory.toml` で埋めた値・空のままの値。
- doctor の結果。残った要確認と、ユーザーが回すもの。
- 次からの開き方。**ワークスペースの直下で開く**（サブフォルダで開くと、プラグインのスキルも hook も読み込まれない）。
  - Claude Code: `cd <ワークスペース> && claude`。スキルは `/ai-deck-factory:deck-build` のように呼ぶ。
  - pi: `cd <ワークスペース> && pi`。初めては `/trust` で信頼を保存する（保存しないと、パッケージのスキルが出ない。dreaming の定期の回も読めない）。スキルは `/skill:deck-build` のように呼ぶ。
- 最初の資料は「〇〇向けの提案のスライドを作って」のように頼めばよい（スキル `deck-practices` から始まる）。

## うまくいかないとき

- **同じ名前のスキルがある。** ワークスペースの `.agents/skills/`・`.claude/skills/` に deck-build などがあると、二重に読まれる（pi ではプラグインのものが負ける）。doctor の「スキルの重なり」に出るので、どちらを使うかをユーザーに聞く。
- **入れる範囲、確かめ方、外し方。** Claude Code は `<プラグイン>/docs/claude-code-plugin.md`、pi は `<プラグイン>/docs/pi.md`。
