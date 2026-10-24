# Codex にプラグインとして入れる

AI Deck Factory を Codex（CLI と、ChatGPT のデスクトップアプリの Codex）のプラグインとして、1 つのワークスペースだけで効くように入れる手順。2026-10-20 に Codex CLI 0.162.1 で確かめた。Claude Code で使う手順は [claude-code-plugin.md](claude-code-plugin.md)、pi は [pi.md](pi.md)。

Codex は Claude Code の形をそのまま読む。マーケットプレイスは `.claude-plugin/marketplace.json`、プラグインは `.claude-plugin/plugin.json`、hook は `hooks/hooks.json`（`${CLAUDE_PLUGIN_ROOT}` も Codex が埋める）。Codex のための別のファイルは置いていない。

## 入れる

ワークスペースにするフォルダで回す。

```sh
cd <ワークスペース>
codex plugin marketplace add mats16/ai-deck-factory   # 手元の checkout なら ~/Projects/ai-deck-factory
codex plugin add ai-deck-factory@ai-deck-factory
```

`~/.codex/config.toml` に次が書き込まれる。Codex には入れる範囲（scope）がなく、このままでは、どのフォルダの会話にもスキルが出る。

```toml
[marketplaces.ai-deck-factory]
source_type = "git"
source = "https://github.com/mats16/ai-deck-factory.git"

[plugins."ai-deck-factory@ai-deck-factory"]
enabled = true
```

ワークスペースだけで効かせるには、ユーザーの設定で切り、ワークスペースの `.codex/config.toml` で入れる。

```sh
python3 -c 'import os,pathlib; p=pathlib.Path(os.environ.get("CODEX_HOME","~/.codex")).expanduser()/"config.toml"; k="[plugins.\"ai-deck-factory@ai-deck-factory\"]\nenabled = true"; s=p.read_text(); assert k in s, "見つからない"; p.write_text(s.replace(k, k[:-4]+"false"))'
mkdir -p .codex && { grep -qs 'ai-deck-factory@ai-deck-factory' .codex/config.toml || printf '\n[plugins."ai-deck-factory@ai-deck-factory"]\nenabled = true\n' >> .codex/config.toml; }
```

- ワークスペースの `.codex/config.toml` は、そのフォルダを信頼したときだけ読まれる。初めて Codex を開くと聞かれ、決めたことは `~/.codex/config.toml` の `[projects."<ワークスペース>"] trust_level = "trusted"` に残る。信頼しないと、スキルも hook も出ない。
- 会話が読むのは、入れたときの写し（`~/.codex/plugins/cache/ai-deck-factory/ai-deck-factory/local/`）。手元のパスで足しても写す（Claude Code と違い、checkout をそのまま読まない）。

## hook を信頼する

プラグインの hook（`rules/` と顧客の `memory.md` を続けて出すもの）は、信頼するまで動かない。対話の Codex で `/hooks` を開き、`ai-deck-factory` の 2 つ（PostToolUse・UserPromptSubmit）を信頼する。

- 信頼は hook の中身のハッシュに付く。`hooks/hooks.json` が変わった版を取ると、信頼し直すまで止まる（起動のときに `/hooks` を開くよう知らせが出る）。
- `codex exec`（dreaming の `run.sh codex`、レビューの子）は聞けない。先に対話の Codex で信頼しておく。
- Codex はファイルをシェル（`cat`・`sed` など）で読むので、PostToolUse は `Bash` で効く。`$ai-deck-factory:slides-build` のように呼んだスキルは、道具を使わずに SKILL.md が入るので、UserPromptSubmit がプロンプトから拾って `rules/<スキル>/SKILL.md` を出す。

## そのフォルダだけで効いているかを確かめる

```sh
# 会話に出るスキル（モデルは呼ばない）: ワークスペースでは 12、ほかのフォルダでは 0
for d in <ワークスペース> /tmp; do
  (cd $d && codex debug prompt-input ok 2>/dev/null) | grep -oE 'ai-deck-factory:[a-z-]+: ' | sort -u | wc -l
done

# hook と信頼: PostToolUse・UserPromptSubmit が trusted で出る
cd <ワークスペース> && (printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"t","version":"0"}}}' '{"jsonrpc":"2.0","method":"initialized"}' '{"jsonrpc":"2.0","id":2,"method":"hooks/list","params":{}}'; sleep 5) \
  | codex app-server 2>/dev/null \
  | python3 -c "import json,sys; r=next(e for e in map(json.loads, sys.stdin) if e.get('id')==2); [print(h['eventName'], h['trustStatus']) for d in r['result']['data'] for h in d['hooks'] if h.get('pluginId')=='ai-deck-factory@ai-deck-factory']"
```

2026-10-20 に検証用のワークスペースで確かめた結果:

| フォルダ | 出たスキル | hook |
|---|---|---|
| ワークスペース（信頼した） | `ai-deck-factory:` の 15 個 | `sed -n 1,3p ../skills/slides-build/visual.md` のあとと、`$ai-deck-factory:factory-doctor` で呼んだときに、`rules/` の目印が差し込まれた |
| ワークスペースのサブフォルダ | 15 個（親の `.codex/config.toml` も読まれる） | |
| `/tmp` | 0 | |

## ワークスペースを作る

同じフォルダで Codex を開き、スキルを呼ぶ（`$` を打つと選べる）。

```
$ai-deck-factory:factory-init
$ai-deck-factory:factory-doctor
```

doctor の要修正が 0 になれば使える。

## 直したプラグインを届ける

写しを読むので、取り直すまで変わらない。

```sh
codex plugin marketplace upgrade ai-deck-factory   # GitHub から入れたとき。手元のパスなら要らない
codex plugin add ai-deck-factory@ai-deck-factory   # 写し直す
```

`codex plugin add` は、ユーザーの設定の `enabled` を `true` に戻す。上の「入れる」の `python3 -c …` をもう一度回して切る。

## 外す

```sh
codex plugin remove ai-deck-factory@ai-deck-factory
codex plugin marketplace remove ai-deck-factory
```

ワークスペースの `.codex/config.toml` の `[plugins."ai-deck-factory@ai-deck-factory"]` も消す。ワークスペースのファイル（`factory.toml`・`AGENTS.md`・`rules/`・`.factory/`）は残る。
