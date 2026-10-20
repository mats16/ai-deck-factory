# 開発しながら動作を見る

プラグインを直す人のための手順。直すのは元のリポジトリの worktree でし、その worktree の下に検証用のワークスペース `sandbox/` を置いて、資料を作って確かめる。`sandbox/` はリポジトリの `.gitignore` で無視しているので commit に入らず、worktree を消せば一緒に消える。worktree ごとに分かれるので、いくつかのブランチを並べて試せる。2026-10-12 に Claude Code と pi 1.0.0 で、Codex は 2026-10-20 に Codex CLI 0.162.1 で確かめた。利用者の入れ方は [claude-code-plugin.md](claude-code-plugin.md)・[codex-plugin.md](codex-plugin.md)・[pi.md](pi.md)。

元の checkout（`~/Projects/ai-deck-factory`）は `main` のままにしておく。ほかのワークスペースにこの checkout のパスで入れたプラグインはここを読むので、利用者と同じものが動く（GitHub や git の URL で入れたものは、checkout とは別の版を読む）。

## 作る

```sh
cd <worktree>
mkdir sandbox && cd sandbox
cp ~/Documents/factory.toml .         # 本番のワークスペースから写す。なければ factory-init
cp -R ~/Documents/rules ~/Documents/AGENTS.md ~/Documents/CLAUDE.md .   # 本番の決まりで試すときだけ
```

写した `factory.toml` は、Google の側で本番のものを書き換えないように替える。

- `[drive]` は、検証用の Drive のフォルダにする（下の「消す」）。
- テンプレートを試すときは、`[slides.templates]` を空にし、`template.py <テーマ> --from-base [<元の URL>]` で検証用の `[drive] factory` の下に作る（URL が書き込まれる）。`template.py <テーマ>` は `[slides.templates]` のテンプレートをその場で書き換えるので、本番の URL を残さない。本番のテーマで試すなら、本番の `themes/slides/` も写す（`template.py` は表紙・扉の幅と地の明るさをそこに書き込む）。
- `sandbox/` で `git init` はしない（factory-init が聞いてくる）。入れ子のリポジトリになり、worktree の `git clean` で消えなくなる。
- `factory-kaizen` だけは、この worktree を試さない。`kaizen.py start` は GitHub の `main` を `sandbox/.factory/kaizen/<名前>/repo` に clone する。

## Claude Code

`sandbox/` で、入れずに `--plugin-dir` で渡して開く。

```sh
claude --plugin-dir ..
```

- 起動したときの `plugins` の `path` が worktree を指し、`ai-deck-factory:` のスキルが 12 個読まれる。
- `claude plugin marketplace add .. --scope project` で入れてはいけない。マーケットプレイスの名前（`ai-deck-factory`）は `~/.claude/plugins/known_marketplaces.json` に 1 つしか持てず、本番のワークスペースで足したものとぶつかる。外すと、ほかで足したものの記録も消える。
- そこから起こす `claude -p` の子（dreaming の `run.sh claude` など）には、プラグインが入っていない。子まで確かめるときは pi で試す。
- worktree が点で始まるフォルダの下（T3 Code の `~/.t3/worktrees` など）にあると、`claude -p` で回した会話は、sandbox の中のファイルを「sensitive file」として書けない（`--permission-mode acceptEdits` でも止まる）。`claude -p` で資料まで作って確かめるときは、sandbox を `/tmp/<名前>/` に写し、そこで `claude --plugin-dir <worktree>` を回す。終わったら消す。

## Codex

`sandbox/` で、`CODEX_HOME` を分けて worktree を入れる。

```sh
export CODEX_HOME=/tmp/adf-codex-$(basename "$(dirname "$PWD")") && mkdir -p $CODEX_HOME
codex plugin marketplace add .. && codex plugin add ai-deck-factory@ai-deck-factory
codex debug prompt-input ok | grep -oE 'ai-deck-factory:[a-z-]+: ' | sort -u
```

- `CODEX_HOME` は worktree の外に置く。Codex は worktree（マーケットプレイスの根元）を丸ごと写すので、中に置くと自分を写し続けて止まる（`File name too long`）。
- ふだんの `~/.codex` で `codex plugin marketplace add ..` しない。マーケットプレイスの名前（`ai-deck-factory`）は 1 つしか持てず、本番のワークスペースで足したものとぶつかる。
- 会話は `$CODEX_HOME/plugins/cache/ai-deck-factory/ai-deck-factory/local/` の写しを読む。手元のパスで足しても写すので、直したら `codex plugin add ai-deck-factory@ai-deck-factory` を回し直す。
- 分けた `CODEX_HOME` にはログインがない。会話を回すなら、`~/.codex/auth.json`（ChatGPT のログイン）か、`~/.codex/config.toml` の `model_provider`・`[model_providers.<名前>]` を写す。会話の記録も `$CODEX_HOME/sessions/` に残るので、dreaming の `sessions.py`（`~/.codex/sessions/` を読む）には出ない。
- hook は信頼するまで動かない。対話の Codex の `/hooks` で信頼するか、`codex exec --dangerously-bypass-hook-trust` で回す。`sed -n 1,3p ../skills/deck-practices/visual.md` を回させたあとと、`$ai-deck-factory:factory-doctor` で呼んだときに、`sandbox/rules/` の目印が差し込まれることを確かめた。

## pi

`sandbox/` で、worktree をパッケージとして入れる。

```sh
pi install -l ..
```

- `.pi/settings.json` に `../..`（`.pi/` からの相対のパス）で入り、worktree の 12 個のスキルと `extensions/rules.ts` が読まれる。`pi -p` の子（dreaming の `run.sh pi`、レビューを頼むとき）も同じものを読む（`sandbox/` で `pi -p` を起こし、deck-build の `SKILL.md` が worktree のパスで出ることと、`../skills/deck-practices/visual.md` を read すると `sandbox/rules/deck-practices/visual.md` が続けて差し込まれることを確かめた）。
- trust は、`sandbox/` で対話の pi を開いて `/trust` で保存する（`pi -p` の子は聞けないので、先に済ませる）。親のフォルダの決定も子に効く。ホームを信頼してあれば、`--approve` なしの `pi -p`・`--mode rpc` でも読まれた。worktree を置くフォルダ（T3 Code なら `~/.t3/worktrees`）ごと信頼すると、聞かれなくなる代わりに、あとからそこに置くほかのリポジトリの拡張も黙って読まれる（[pi.md](pi.md) の「project trust」）。
- 同じ名前のスキルがほかにあると、パッケージのものは負ける（[pi.md](pi.md) の「同じ名前のスキルがあるとき」）。`get_commands` の `sourceInfo.path` が worktree を指しているかを確かめる。

## 見本を組んで画像で見る

JSON のページの形と部品を直したら、`sandbox/` で `tests/render/run.py` を回す。見本（`skills/deck-build/samples/json/` の全ページと、部品 1 つの `component.json`）を `[drive] internal` に一時のデッキとして組み、lint（手元と組んだあと）と全ページの画像を取って、ページごとの見るところ（`tests/render/expect.json`）と並べた `sandbox/.factory/render/report.md` を書く。デッキは画像を取ったらゴミ箱に移す（`--keep` で残す）。

```sh
python3 ../tests/render/run.py            # report.md を書く。画像は自分で開いて見る
python3 ../tests/render/run.py --judge    # 続けて claude -p に画像を見させ、ページごとの OK・NG を judge.md に書く
```

lint の要修正か、`--judge` の NG があれば、終わりの状態が 1 になる。`--judge` の見立ては LLM なので、NG のページは画像を開いて確かめる。見本のページを足したら、`expect.json` にも見るところを足す（`--selftest` が見る）。

## 依頼文で試す

JSON のページの形やスキルの説明を直したら、会話を持たない子に [fixtures/](fixtures/) の依頼文を渡して書かせ、各ファイルの「見るところ」で確かめる（pom の dev-fixtures にならった。2026-10-16）。説明だけで正しい部品を選べるかは、selftest では分からない。

```sh
rsync -a --exclude sandbox --exclude .git <worktree>/ /tmp/adf-plugin/   # 点で始まるフォルダの下だと、claude -p の子はプラグインも読めない（上の Claude Code の節）
cp -R sandbox /tmp/adf-fixture && cd /tmp/adf-fixture
claude --plugin-dir /tmp/adf-plugin -p "$(sed -n '/^```text$/,/^```$/p' /tmp/adf-plugin/docs/fixtures/02-gantt.md | sed '1d;$d')" \
  --permission-mode acceptEdits --allowedTools "Bash(python3:*)" "Bash(uv run:*)" "Bash(ls:*)" "Bash(mkdir:*)"
```

書いたファイルと lint の結果を見て、迷った書き方は形か説明を直す。依頼文は見本（`skills/deck-build/samples/json/`）と違う中身にする（同じだと、見本を写しただけか分からない）。終わったら `/tmp/adf-plugin` と `/tmp/adf-fixture` を消す。

## 本番のワークスペースで worktree の版を試す

本番のワークスペースの決まりや資料のまま試すときは、そのワークスペースの直下で、起動オプションで worktree を渡す。入れてあるものは変えない。

```sh
cd ~/Documents
claude --plugin-dir <worktree>
pi -ns --skill <worktree>/skills -ne -e <worktree>/extensions/rules.ts
```

- Claude Code は、入れてあるものと重ねても、読まれるのは `--plugin-dir` の版だけ（二重にならない）。
- pi は、`--skill` だけを足すと入れてあるパッケージのほうが勝つ。`-ns`（スキルを探さない）・`-ne`（拡張を探さない）を付けると、渡したものだけが読まれる。ほかのスキル（`~/.agents/skills` など）と拡張も止まる。
- Codex には、入れずに渡す起動オプションがない。本番のワークスペースで試すなら、上の「Codex」と同じく `CODEX_HOME` を分けて入れる。
- どちらも、子のプロセスには伝わらない。子は入れてある版（checkout のパスで入れたなら `~/Projects/ai-deck-factory`）を読む。

## 消す

worktree を消せば `sandbox/` も消える。worktree を残して作り直すときは `rm -rf sandbox`。worktree の中で `git clean -fdx` を回すと、`sandbox/` もほかの無視したファイル（`node_modules/` など）も消える。

残るもの:

- Google Drive に組んだスライドとドキュメント。`[drive]` に替えた検証用のフォルダごと消す。
- Codex で試したときの `CODEX_HOME`（`/tmp/adf-codex-<worktree の名前>`）。`rm -rf` で消す。
- Claude Code のメモリと会話の記録（`~/.claude/projects/<sandbox のパスの / . _ を - にしたもの>/`）と、pi の会話の記録（`~/.pi/agent/sessions/--<sandbox のパスの / を - にしたもの>--/`）。害はないが、たまに消す。
