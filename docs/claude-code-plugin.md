# Claude Code にプラグインとして入れる

AI Deck Factory を Claude Code のプラグインとして入れ、ワークスペースを作るまでの手順。pi で使う手順は [pi.md](pi.md)。

## 入れる範囲（scope）を決める

| scope | 書き込まれる場所 | 効く範囲 |
|---|---|---|
| `user`（既定） | `~/.claude/settings.json` | どのフォルダの会話でも |
| `project` | `<フォルダ>/.claude/settings.json` | そのフォルダ（プロジェクト）の会話だけ。git に入れれば、同じリポジトリを使う人にも効く |
| `local` | `<フォルダ>/.claude/settings.local.json` | そのフォルダで、自分だけ |

資料のフォルダだけで使うなら `project` にする。ほかのフォルダの会話にスキルが出てこない。

## 入れる（project）

ワークスペースにするフォルダで回す。

```sh
cd <ワークスペース>
claude plugin marketplace add https://github.com/mats16/ai-deck-factory.git --scope project   # 手元の checkout なら ~/Projects/ai-deck-factory
claude plugin install ai-deck-factory@ai-deck-factory --scope project
```

`<ワークスペース>/.claude/settings.json` に次が書き込まれる。

```json
{
  "extraKnownMarketplaces": {
    "ai-deck-factory": { "source": { "source": "directory", "path": "/Users/<you>/Projects/ai-deck-factory" } }
  },
  "enabledPlugins": { "ai-deck-factory@ai-deck-factory": true }
}
```

- `~/.claude/settings.json` は変わらない。
- `~/.claude/plugins/` の `known_marketplaces.json`（マーケットプレイスの一覧）と `installed_plugins.json`（`scope: project` と `projectPath` が付く）には行が足される。どちらも記録だけで、ほかのフォルダでプラグインが有効になるわけではない。
- マーケットプレイスを手元のパスで足すと、会話はその checkout からプラグインを読む（起動したときの `plugins` の `path` が checkout を指す）。`install`・`update` は `~/.claude/plugins/cache/` に commit ごとの写しを作り、`installed_plugins.json` の `installPath` もそこを指すが、会話は読まない。commit していない変更も次の会話から効き、checkout を動かすとプラグインは読まれなくなる（写しには戻らない）。GitHub を指していれば、会話は写しを読む（2026-10-12 に Claude Code 2.1.295 で確かめた）。

## そのフォルダだけで効いているかを確かめる

```sh
# 一覧: ワークスペースでは enabled が true、ほかのフォルダでは false
for d in <ワークスペース> /tmp; do
  (cd $d && claude plugin list --json) | python3 -c "import json,sys; [print(p['id'], p['scope'], p['enabled']) for p in json.load(sys.stdin) if 'deck' in p['id']]"
done

# 会話に読み込まれるスキル: ワークスペースでは ai-deck-factory:* の 12 個、ほかのフォルダでは 0
cd <ワークスペース> && claude -p ok --model haiku --max-turns 1 --output-format stream-json --verbose \
  | python3 -c "import json,sys; e=next(e for e in map(json.loads, sys.stdin) if e.get('subtype')=='init'); print(sorted(s for s in e['skills'] if s.startswith('ai-deck-factory:')))"
```

2026-10-12 に `~/adf-plugin-test` で確かめた結果:

| フォルダ | `plugin list` の enabled | 読み込まれたスキル |
|---|---|---|
| `~/adf-plugin-test`（入れたフォルダ） | true | `ai-deck-factory:` の 12 個（customer-profile、deck-build、deck-comments、deck-practices、deck-research、deck-review、deck-template、doc-build、dreaming、factory-doctor、factory-init、factory-kaizen） |
| `~/Documents` | false | `.agents/skills` の 6 つ（`ai-deck-factory:` が付かない。プラグインのものではない） |
| `/tmp` | false | なし |
| `~/adf-plugin-test/Internal`（入れたフォルダのサブフォルダ） | false | なし |

プロジェクトは、Claude Code を開いたフォルダそのもの（git の根元や親のフォルダの `.claude/settings.json` は見ない）。サブフォルダで開くとプラグインは読み込まれず、スキルも hook も効かない。ワークスペースの直下で開き、資料のフォルダへはそこから移る。`.agents/skills`・`.claude/skills` に置いたスキルは親のフォルダからも読まれるので、`~/Documents/Internal/<資料>/build` で開いても使える。ここが前の入れ方との違い。

## ワークスペースを作る

同じフォルダで Claude Code を開き、スキルを呼ぶ。

```
/ai-deck-factory:factory-init
/ai-deck-factory:factory-doctor
```

doctor の要修正が 0 になれば使える。ワークスペースの `rules/<スキル>/<ファイル>` は、プラグインの同じファイルを Read で開くと hook が続けて出す（2026-10-12 に `rules/deck-practices/visual.md` で確かめた。サブフォルダで開いた会話では出ない）。スキルは `ai-deck-factory:` を付けた名前で呼ぶ（`/ai-deck-factory:deck-build` など）。

## 注意

- **同じ名前のスキルを二重に入れない。** ワークスペースの `.agents/skills/` や `.claude/skills/` に deck-build などがあると、プラグインのスキルと両方が読み込まれる（`deck-build` と `ai-deck-factory:deck-build`）。doctor が「スキルの重なり」として要確認に出すので、どちらかを外す。
- **直したプラグインを届ける。** 手元のパスで足したなら、保存して会話を開き直すだけでよい。GitHub から入れたなら、`plugin.json` に版を書いていないので commit の SHA が版になる。push してから `claude plugin update ai-deck-factory@ai-deck-factory --scope project` で届け、会話を開き直す。
- **手元で直しながら試す。** 入れずに `claude --plugin-dir ~/Projects/ai-deck-factory` で開いてもよい。その会話だけで効き、入れてあるものより優先される。worktree で直して検証用のワークスペースで試す手順は [development.md](development.md)。

## 外す

```sh
cd <ワークスペース>
claude plugin uninstall ai-deck-factory@ai-deck-factory --scope project
claude plugin marketplace remove ai-deck-factory --scope project
```
