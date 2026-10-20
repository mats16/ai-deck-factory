# AI Deck Factory を直すときの決まり

このリポジトリは、AI Deck Factory のプラグイン（Claude Code・Codex）とパッケージ（pi）の元。中身・入れ方・ワークスペースの作りは [README.md](README.md)、設定のガイドは `docs/`。

**`sandbox/` の下で開いた会話には、このファイルは効かない。** そこは利用者として動作を見る検証用のワークスペースで、このファイルは親のフォルダから読まれているだけ。`sandbox/` の `AGENTS.md`（factory-init の雛形）に従い、プラグインの利用者として振る舞う。

## 直すときの決まり

- **Claude Code・Codex・pi で同じソースを使う。** `skills/` はどれも読む。Codex は Claude Code の形（`.claude-plugin/`・`hooks/hooks.json`）をそのまま読むので、Codex のための別のファイルは置かない。`rules/` を続けて出す仕組みは、`hooks/rules_overlay.py` を Claude Code と Codex（`hooks/hooks.json`）と pi（`extensions/rules.ts`）から呼んでいる。どれか 1 つだけに効く直しにしない。
- **スクリプトは標準ライブラリだけで書く。** Pillow などが要るものだけ、先頭の `# /// script` に依存を書いて `uv run` で回す。Python は 3.11 以上で動かす（README の「入れ方」）。
- **直したスクリプトは `--selftest` を通す。** 回し方は下の「sandbox で確かめる」の 2。見た目に効く部品（`slides.py`・`template.py`・`docs.py`）を直したら、テンプレートの見本を組み直して画像で見る（`deck-build/slides.md`・`doc-build/SKILL.md`）。JSON のページの形と部品を直したら、sandbox で `python3 ../tests/render/run.py --judge` を回し、`skills/deck-build/samples/json/` の見本を全部組んで、全ページの画像をページごとの見るところ（`tests/render/expect.json`）と比べる（形にキーを足したら見本にも足す。selftest が見る。見本のページを足したら見るところも足す）。部品や書き方の説明を直したら、`docs/fixtures/` の依頼文を会話を持たない子に渡し、説明だけで正しい部品を選べるかを見る（[docs/development.md](docs/development.md) の「依頼文で試す」）。
- **スキルを足す・外す・名前を変えるときは、数と名前の出てくるところをそろえる。** README の表、`docs/` の「12 個」、`deck-practices` などから指しているパス。
- **PR の本文は `.github/pull_request_template.md` の節で書く。** 回したコマンドと結果はそのまま貼り、「レビューで見てほしいところ」にファイル:行と確信のない判断を書く。レビューする人も AI も、そこから読む。
- **ユーザーが決めたことは、README の「決めたこと」に日付とユーザーの発言（原文）で残す。** 後回しにしたものは「残っている課題」に書く。
- **文体は今のファイルに合わせる。** 平易な和文で、言い切りの「〜する」。漢語やカタカナ語より、やさしい言い方を選ぶ（「検証」より「確かめる」、「ルール」より「決まり」）。例外: `/deck-review` を回す単位は「ラウンド」（README の「決めたこと」の 2026-10-19）。

## 公開のリポジトリ

`origin`（GitHub の `mats16/ai-deck-factory`）は公開している。

- 顧客の名前、資料の名前・URL・本文、社内だけの情報を、commit・PR・Issue に入れない。例には「顧客向けの資料」「（顧客）」「資料 1」を使う。
- 元の checkout（`~/Projects/ai-deck-factory`）は `main` のままにする。ほかのワークスペースに手元のパスで入れたプラグインはここを読むので、直すのは worktree でする。

## sandbox で確かめる

worktree の直下に検証用のワークスペース `sandbox/` を置き、worktree のプラグインを入れずに渡して確かめる。`sandbox/` は `.gitignore` で無視しているので commit に入らず、worktree を消せば一緒に消える。詳しいこと（本番の決まりで試す、本番のワークスペースで worktree の版を試す、残るもの）は [docs/development.md](docs/development.md)。

1. **作る。** worktree の直下で回す。

   ```sh
   python3 skills/factory-init/scripts/init.py sandbox
   cd sandbox
   python3 ../skills/factory-doctor/scripts/doctor.py --local   # Google の API は見ない
   ```

   雛形の `factory.toml` のままでは、Google に組む作業はできない（doctor の要修正が残る）。組んで確かめるときは、本番のワークスペースの `factory.toml` を写し、`[drive]` を検証用の Drive のフォルダに替える（本番のものを書き換えないため）。テンプレートを試すときは `[slides.templates]` も検証用に複製したものにする（docs/development.md の「作る」）。`sandbox/` で `git init` はしない。

2. **selftest を回す。** `sandbox/` で回す（`template.py` は `factory.toml` を探す）。Python は最低の版の 3.11 にそろえる。

   ```sh
   for f in ../hooks/*.py ../skills/*/scripts/*.py ../tests/*/*.py; do
     grep -q -e --selftest "$f" && echo "$f: $(uv run -q --python 3.11 "$f" --selftest 2>&1 | tail -1)"
   done
   ```

   すべて `selftest ok` になる。PR と `main` への push では、GitHub Actions（`.github/workflows/selftest.yml`）が Ubuntu で sandbox を作り、2 を回す。

3. **Claude Code で開く。** `sandbox/` で、入れずに `--plugin-dir` で渡す。

   ```sh
   claude --plugin-dir ..
   ```

   読まれたスキルが worktree のものかは、次で確かめる（worktree のパスと、`ai-deck-factory:` の 12 個が出る）。

   ```sh
   claude --plugin-dir .. -p ok --model haiku --max-turns 1 --output-format stream-json --verbose 2>/dev/null \
     | python3 -c "import json,sys; e=next(e for e in map(json.loads, sys.stdin) if e.get('subtype')=='init'); print([p['path'] for p in e['plugins'] if p['name']=='ai-deck-factory']); print(sorted(s for s in e['skills'] if s.startswith('ai-deck-factory:')))"
   ```

   - `claude plugin marketplace add ..` で入れない。マーケットプレイスの名前は 1 つしか持てず、本番のワークスペースで足したものとぶつかる。
   - そこから起こす `claude -p` の子（dreaming の `run.sh claude` など）にはプラグインが入っていない。子まで確かめるときは pi で試す。

4. **pi で開く。** `sandbox/` で、worktree をパッケージとして入れる。

   ```sh
   pi install -l ..
   pi                                     # 初めては /trust で信頼を保存する（pi -p の子は聞けない）
   (echo '{"type":"get_commands"}'; sleep 8) | pi --mode rpc --no-session 2>/dev/null \
     | python3 -c "import json,os,sys; r=os.path.realpath('..'); e=next(e for e in map(json.loads, sys.stdin) if e.get('command')=='get_commands'); print(sorted(c['name'] for c in e['data']['commands'] if c.get('sourceInfo',{}).get('path','').startswith(r)))"
   ```

   worktree から読まれた 12 個のスキルが出る。足りないときは、同じ名前のスキルがほかにあって負けている（パッケージのものはいちばん優先が低い）か、trust を保存していない（[docs/pi.md](docs/pi.md)）。

5. **Codex で開く。** `sandbox/` で、本番とぶつからないように `CODEX_HOME` を分けて worktree を入れる。Codex は写しを読むので、直したら `codex plugin add` を回し直す。

   ```sh
   export CODEX_HOME=/tmp/adf-codex-$(basename "$(dirname "$PWD")") && mkdir -p $CODEX_HOME   # 会話を回すなら、~/.codex の auth.json か config.toml のモデルの設定を写す
   codex plugin marketplace add .. && codex plugin add ai-deck-factory@ai-deck-factory
   codex debug prompt-input ok | grep -oE 'ai-deck-factory:[a-z-]+: ' | sort -u   # 12 個が出る（モデルは呼ばない）
   ```

   hook は、対話の Codex の `/hooks` で信頼するまで動かない（`codex exec` で試すだけなら `--dangerously-bypass-hook-trust`）。詳しいことは [docs/development.md](docs/development.md) の「Codex」。

6. **`rules/` が続けて出るかを見る。** `sandbox/rules/deck-practices/visual.md` に目印の 1 行を書き、会話で `../skills/deck-practices/visual.md` を開かせる。目印が続けて差し込まれれば、hook（Claude Code・Codex）と拡張（pi）が効いている。`$ai-deck-factory:<スキル>`（Codex）・`/ai-deck-factory:<スキル>`（Claude Code）で呼んだときは、`rules/<スキル>/SKILL.md` が出る（UserPromptSubmit）。hook だけなら、会話を開かずに確かめられる。

   ```sh
   mkdir -p rules/deck-practices && echo "目印" > rules/deck-practices/visual.md
   echo "{\"cwd\":\"$PWD\",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$PWD/../skills/deck-practices/visual.md\"}}" \
     | python3 ../hooks/rules_overlay.py claude
   ```

7. **直したところを、資料を作って確かめる。** `sandbox/` の会話で、直したスキルを使う場面（`/ai-deck-factory:deck-build`、Codex なら `$ai-deck-factory:deck-build`、pi なら `/skill:deck-build` など）を通し、lint と Google が描いたページの画像で見る。`factory-kaizen` だけは、この worktree ではなく GitHub の `main` を clone するので、ここでは試せない。

8. **消す。** 手順 1 から `sandbox/` の中にいるので、worktree の直下に戻ってから消す（worktree ごと消すなら要らない）。

   ```sh
   cd .. && rm -rf sandbox
   ```

   Google Drive に組んだものは、検証用のフォルダごと消す。Codex で試したなら `/tmp/adf-codex-<worktree の名前>` も消す。
