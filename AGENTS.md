# AI Deck Factory を直すときの決まり

このリポジトリは、AI Deck Factory のプラグイン（Claude Code・Codex）とパッケージ（pi）の元。中身・入れ方・ワークスペースの作りは [README.md](README.md)、設定のガイドは `docs/`。

**`sandbox/` の下で開いた会話には、このファイルは効かない。** そこは利用者として動作を見る検証用のワークスペースで、このファイルは親のフォルダから読まれているだけ。`sandbox/` の `AGENTS.md`（factory-init の雛形）に従い、プラグインの利用者として振る舞う。

## 直すときの決まり

- **Claude Code・Codex・pi で同じソースを使う。** `skills/` はどれも読む。Codex は Claude Code の形（`.claude-plugin/`・`hooks/hooks.json`）をそのまま読むので、Codex のための別のファイルは置かない。`rules/` を続けて出す仕組みは、`hooks/rules_overlay.py` を Claude Code と Codex（`hooks/hooks.json`）と pi（`extensions/rules.ts`）から呼んでいる。どれか 1 つだけに効く直しにしない。
- **スクリプトは標準ライブラリだけで書く。** Pillow などが要るものだけ、先頭の `# /// script` に依存を書いて `uv run` で回す。Python は 3.11 以上で動かす（README の「入れ方」）。
- **直したスクリプトは `--selftest` を通す。** 回し方は下の「sandbox で確かめる」の 2。見た目に効く部品（`slides.py`・`template.py`・`docs.py`）を直したら、テンプレートの見本を組み直して画像で見る（`slides-build/themes.md`・`docs-build/templates.md`）。JSON のページの形と部品を直したら、sandbox で `python3 ../tests/render/run.py --judge` を回し、`skills/slides-build/samples/json/` の見本を全部組んで、全ページの画像をページごとの見るところ（`tests/render/expect.json`）と比べる（形にキーを足したら見本にも足す。selftest が見る。見本のページを足したら見るところも足す）。部品や書き方の説明を直したら、`docs/fixtures/` の依頼文を会話を持たない子に渡し、説明だけで正しい部品を選べるかを見る（[docs/development.md](docs/development.md) の「依頼文で試す」）。
- **`SKILL.md` の本文は 5,000 トークン以内にする。** 場面でしか要らない節（ある場合だけの手順、失敗したとき、別の呼び出しで使う手順）は、`SKILL.md` の表から 1 段で指すファイルに出す。ほかのファイルからしか辿れないファイルは作らない（入れ子の先は一部だけ読まれやすい）。Claude Code はコンパクションのあと、呼んだスキルの先頭 5,000 トークンだけを付け直す。分けたら `factory-migrate/scripts/migrate.py` の `SPLIT` に足す（README の「決めたこと」の 2026-10-24）。
- **ほかのスキルのファイルとスクリプトのメッセージから、`SKILL.md` から分けたファイルを開かせるときは、「`../<スキル>/SKILL.md` を開いてから、その `<ファイル>`」と書く。** hook は開いたパスと同じ `rules/<スキル>/<ファイル>` しか出さないので、分けたファイルを直に開くと、前から `rules/<スキル>/SKILL.md` に書いてあるワークスペースの上書きが出ない。決まりの出典として番号で指すだけのところ（「`dreaming/run.md` の 5 で見る」）とスクリプトのコメントは、そのままでよい。
- **スキルを足す・外す・名前を変えるときは、数と名前の出てくるところをそろえる。** README の表、`docs/` の「15 個」、`deck-practices` などから指しているパス。
- **PR の本文は `.github/pull_request_template.md` の節で書く。** 回したコマンドと結果はそのまま貼り、「レビューで見てほしいところ」にファイル:行と確信のない判断を書く。レビューする人も AI も、そこから読む。
- **ユーザーが決めたことは、README の「決めたこと」に日付とユーザーの発言（原文）で残す。** 後回しにしたものは「残っている課題」に書く。
- **日本語と英語は、下の「言葉の使い分け」に従う。** 日本語で書くところは、平易な和文で、言い切りの「〜する」。漢語やカタカナ語より、やさしい言い方を選ぶ（「検証」より「確かめる」、「ルール」より「決まり」）。例外: `/deck-review` を回す単位は「ラウンド」（README の「決めたこと」の 2026-10-19）。

## 言葉の使い分け

AI が読む指示は英語、人が読むものと日本語に結びつく決まりは日本語にする（README の「決めたこと」の 2026-10-20）。

- **英語で書く:** `skills/` の md（`SKILL.md` の `description` と見出し、子への依頼文 `prompt_*.md` を含む）のうち、手順、工程の順、子の頼み方、ファイルとフォルダの扱い、コマンドとスクリプトの説明、確かめ方、意味が一意に定まる決まり（位置・大きさ・間・色とコントラスト・部品と JSON のキー・揃え方・矢印・表・画像・API の落とし穴・Drive の置き場所）。`description` は 1000 字以内にする。
- **日本語のまま書く:**
  - 日本語の表記の決まり（文体、表記、用語と訳語、和欧間のスペース、約物、改行と折り返しの位置、全角の字数の目安）。
  - 資料作りのニュアンスが絡む決まり（主張や見出しの言い方、顧客への言葉の調子、聞き手がどう受け取るか、話の運び、何を言う・言わないか）。
  - 例、ユーザーの発言、そのまま書き写す文字列（`構成案.md` などのファイル名、構成案に書く節の名前〔「書き方の決め」など〕、lint の札〔`要修正`・`要確認`〕、台帳の値、スクリプトや人が読む表の列の名前、「要判断」の印）。
  - 利用者や Issue に出す出力の型（dreaming の報告、Issue の本文、profile.md の骨組み、doc.md の例）。
  - 人が読むもの: README.md、`docs/`、このファイル、`docs/fixtures/` の依頼文、`skills/factory-init/templates/`（ワークスペースの人が直す）、PR・Issue・commit の本文。スクリプトのメッセージとコメントも、今は日本語のまま（README の「残っている課題」）。
- **決まり（箇条 1 つ）ごとに、言いたいことの中心で決める。** 迷ったら日本語のままにする。1 つの文の中で混ぜない。英語の文に入れる日本語の例・値・節の名前は、「」か `` ` `` で囲む（「AGENTS.md の「修正の指示」」ではなく「「修正の指示」 in AGENTS.md」）。囲まなくてよいのは、出典の札（（見た目 1-7）など）と固有名詞（人名・書名・社名・書体名）だけ。
- **言葉を替えても、決まりの ID（`[slides-visual-027]` など）と節の番号は変えない。** ほかのファイルの節は英語の見出しで指し（`deck-practices/SKILL.md` の "Working practices"）、番号は `§4` と書く。日本語のまま残るファイル（README・`docs/`・ワークスペースの `AGENTS.md`）の節は、日本語の見出しのまま指す。日本語のファイル（雛形・スクリプトのメッセージ）から英語にしたファイルの節を指すときも、英語の見出しで指す（README の「決めたこと」の過去の記録は直さない）。
- **子への依頼文に、答えの言葉（「日本語で答える」など）を書かない。** なくてもモデルが選ぶ。要るのは、決まりの文・ユーザーの発言・出典を写すときに、元の言葉のまま写す指示のほう。
- **英語は、平易な命令形の短い文にし、理由（because …）を残す。** 用語は今のスキルにそろえる（構成案 → the outline、子 → child agent、指摘 → finding、修正の指示 → correction、扉 → section divider、一覧の画像 → contact sheet、レビューの観点 → aspect など）。

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

   読まれたスキルが worktree のものかは、次で確かめる（worktree のパスと、`ai-deck-factory:` の 15 個が出る）。

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

   worktree から読まれた 15 個のスキルが出る。足りないときは、同じ名前のスキルがほかにあって負けている（パッケージのものはいちばん優先が低い）か、trust を保存していない（[docs/pi.md](docs/pi.md)）。

5. **Codex で開く。** `sandbox/` で、本番とぶつからないように `CODEX_HOME` を分けて worktree を入れる。Codex は写しを読むので、直したら `codex plugin add` を回し直す。

   ```sh
   export CODEX_HOME=/tmp/adf-codex-$(basename "$(dirname "$PWD")") && mkdir -p $CODEX_HOME   # 会話を回すなら、~/.codex の auth.json か config.toml のモデルの設定を写す
   codex plugin marketplace add .. && codex plugin add ai-deck-factory@ai-deck-factory
   codex debug prompt-input ok | grep -oE 'ai-deck-factory:[a-z-]+: ' | sort -u   # 15 個が出る（モデルは呼ばない）
   ```

   hook は、対話の Codex の `/hooks` で信頼するまで動かない（`codex exec` で試すだけなら `--dangerously-bypass-hook-trust`）。詳しいことは [docs/development.md](docs/development.md) の「Codex」。

6. **`rules/` が続けて出るかを見る。** `sandbox/rules/slides-build/visual.md` に目印の 1 行を書き、会話で `../skills/slides-build/visual.md` を開かせる。目印が続けて差し込まれれば、hook（Claude Code・Codex）と拡張（pi）が効いている。`$ai-deck-factory:<スキル>`（Codex）・`/ai-deck-factory:<スキル>`（Claude Code）で呼んだときは、`rules/<スキル>/SKILL.md` が出る（UserPromptSubmit）。hook だけなら、会話を開かずに確かめられる。

   ```sh
   mkdir -p rules/slides-build && echo "目印" > rules/slides-build/visual.md
   echo "{\"cwd\":\"$PWD\",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$PWD/../skills/slides-build/visual.md\"}}" \
     | python3 ../hooks/rules_overlay.py claude
   ```

7. **直したところを、資料を作って確かめる。** `sandbox/` の会話で、直したスキルを使う場面（`/ai-deck-factory:slides-build`、Codex なら `$ai-deck-factory:slides-build`、pi なら `/skill:slides-build` など）を通し、lint と Google が描いたページの画像で見る。`factory-kaizen` だけは、この worktree ではなく GitHub の `main` を clone するので、ここでは試せない。

8. **消す。** 手順 1 から `sandbox/` の中にいるので、worktree の直下に戻ってから消す（worktree ごと消すなら要らない）。

   ```sh
   cd .. && rm -rf sandbox
   ```

   Google Drive に組んだものは、検証用のフォルダごと消す。Codex で試したなら `/tmp/adf-codex-<worktree の名前>` も消す。
