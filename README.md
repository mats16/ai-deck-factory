# AI Deck Factory

日本語のスライド（Google Slides）とドキュメント（Google Docs）を Slides API・Docs API で直接組み、lint・Google が描いたページの画像・別の目のレビューで確かめて渡す仕組み。会話の記録から、決まりに戻し忘れた指示を拾って決まりを育てていく（dreaming）。

同じソースを、Claude Code のプラグインと pi のパッケージの両方から入れられる。

## 中身

| スキル | すること |
|---|---|
| `factory-init` | ワークスペースを作る（AGENTS.md・CLAUDE.md・factory.toml・references_index.md・rules/ の雛形と資料のフォルダ。あるファイルは上書きしない） |
| `factory-doctor` | 前提を確かめる（Python・uv、ワークスペース、スキルの重なり、Google の認証、テンプレートと Drive のフォルダ、gh） |
| `factory-kaizen` | プラグインの改善を、過去の資料で前後を比べてから PR にする（理由・背景・検証の結果・見た目なら画像） |
| `deck-practices` | 資料を作る・直すときに最初に読む。作業の始め方、構成案と言葉、見た目の決まり、決まりの層と修正の指示の戻し方 |
| `deck-template` | 会社のテンプレートから、AI Deck Factory のテンプレート（テーマ）を作る。日本語のテンプレートがある・英語しかない・ない、の 3 つ。書体・大きさ・大枠の色を残し、和文の書体とコントラストを合わせる（`template.py audit`・`check`） |
| `deck-build` | Google Slides を組む（`slides.py`）・確かめる（`gslides.py check`・`lint.py`）。Drive への置き方。スクリプトはドキュメントと共有。使い回す画像は `assets/` |
| `doc-build` | Google Docs を `build/doc.md` から組む・確かめる（`docs.py`）。テンプレートはワークスペースの `rules/doc-build/templates/` |
| `deck-review` | 返す前の全体のレビュー。会話を渡さない新しいサブエージェント（メインと同じモデル）に頼む |
| `deck-research` | ベストプラクティスの調べ直し。調べた記録（`state.md`・`log/`）はワークスペースの `Research/deck_research/` |
| `dreaming` | 会話の記録から、決まりを定期的に整理する |

```
INSTALL.md                        会話で入れるときに、エージェントが読む手順（README の「会話で入れる」）
.claude-plugin/plugin.json        Claude Code のプラグイン
.claude-plugin/marketplace.json   このリポジトリをそのままマーケットプレイスにする
package.json                      pi のパッケージ（pi.skills: ./skills）
skills/                           上の 10 個（Claude Code と pi で共通）
hooks/hooks.json                  Claude Code の hook（プラグインのファイルを読んだら rules/ を、顧客の資料を読んだら memory.md を続けて出す）
hooks/rules_overlay.py            その中身（Claude Code と pi で共有）
extensions/rules.ts               pi の拡張（同じことを pi の read・bash で）
docs/                             設定のガイド（claude-code-plugin.md: Claude Code に入れる範囲と確かめ方。pi.md: pi に入れる範囲と確かめ方。development.md: 開発しながら動作を見る）
```

## 会話で入れる

Claude Code か pi を開き、次を貼る（どのフォルダで開いた会話でもよい）。

```text
AI Deck Factory を入れて、ワークスペースを作ってください。
手順は https://raw.githubusercontent.com/mats16/ai-deck-factory/main/INSTALL.md にあります。WebFetch ではなく curl で読み、そのとおりに進めてください。
```

エージェントが [INSTALL.md](INSTALL.md) に従い、ワークスペースにするフォルダとプラグインに直しを出すかを聞き、Python・uv を見て、そのフォルダだけにプラグインを入れる。続けて、入れた `factory-init` と `factory-doctor` の手順で `factory.toml`（Google の認証、テーマ、Drive の置き場所、材料を集める道具）を一緒に埋め、要修正が 0 になるまで進める。自分で回すのは、ブラウザが開く Google のログインだけ。終わったら、ワークスペースの直下で会話を開き直す。

## 入れ方

手で入れるときの手順。Python 3.11 以上と `uv` が要る。Google の認証は下の「Google の認証」。

**Claude Code**

```sh
claude plugin marketplace add https://github.com/mats16/ai-deck-factory.git   # 手元の checkout なら ~/Projects/ai-deck-factory
claude plugin install ai-deck-factory@ai-deck-factory
claude plugin update ai-deck-factory@ai-deck-factory               # GitHub から入れたとき、直して commit・push したあと
```

マーケットプレイスが GitHub を指していれば、会話は `~/.claude/plugins/cache/` に写した版を読む。`plugin.json` に版を書いていないので commit の SHA が版になり、push してから `update` で届く。手元のパスで足したなら、会話は checkout をそのまま読むので、保存すれば次の会話から効く（commit も `update` も要らない）。手元で直しながら試すときは `claude --plugin-dir ~/Projects/ai-deck-factory`（worktree と検証用のワークスペースで試す手順は [docs/development.md](docs/development.md)）。スキルは `/ai-deck-factory:factory-init` のように呼ぶ。資料のフォルダだけで効かせる（`--scope project`）入れ方と、効いている範囲の確かめ方は [docs/claude-code-plugin.md](docs/claude-code-plugin.md)。

**pi**

```sh
pi install ~/Projects/ai-deck-factory                                # 手元の checkout をそのまま読む（写さない）
pi install git:github.com/mats16/ai-deck-factory        # git から
```

スキルは `/skill:factory-init` のように呼ぶ。資料のフォルダだけで効かせる（`-l`）入れ方と、project trust、効いている範囲の確かめ方は [docs/pi.md](docs/pi.md)。

入れたら、ワークスペースにするフォルダで `factory-init`、続けて `factory-doctor` を呼ぶ。

## ワークスペース

資料を置くフォルダ（例: `~/Documents`）。スクリプトは、今いるフォルダから上へたどって最初に見つかった `factory.toml` のフォルダをワークスペースとして扱う。`factory-init` が置くもの:

- `factory.toml`: 人ごとに変わる値（認証、テンプレート、テーマ〔`[slides.themes.<名前>]`: テンプレートの `url` と使い分けの `description`。エージェントが `slides.py themes` の一覧から資料ごとに選ぶ〕と社名、Drive の置き場所、材料を集める道具〔`[sources]`: 社内の検索・チャット・会議の記録・wiki など〕、プラグインの元のリポジトリ）。テンプレートは `deck-build/scripts/template.py visual --from-base`（`company` も）で作ると URL が書き込まれる。
- `AGENTS.md`（と `@AGENTS.md` を読む `CLAUDE.md`）: どの会話でも要る決まり。
- `rules/<スキル>/<ファイル>`: 資料を作る場面だけで要る、このワークスペースの決まり。
- `Customers/<顧客>/memory.md`: その顧客の好みと、資料をまたいで効く相手のこと（顧客の memory）。その顧客の資料の `構成案*.md` などを開くと、hook が続けて出す。
- `Customers/`・`Internal/`・`Research/`、`references_index.md`: 資料と台帳。`Research/deck_research/` は `deck-research` の調べ直しの記録（`state.md`・`log/`。代表の 3 枚の選び方の記録も）。
- `.factory/`: スクリプトが書く記録。`ledger.jsonl`（決まりの台帳。修正の指示、決まりの ID ごとの出典と再発、dreaming の提案・適用・却下とプラグインへの提案の PR、判断待ちと答え、deck-review の指摘の結果。`deck-practices/scripts/ledger.py` が読み書きする）、`lint_runs.jsonl`（`lint.py --stats` が読む）、`dreaming/last_run`・`dreaming/log/`・`dreaming/backup/`。

自分だけの画像は `assets/` に置く。`slides.asset()` はここを先に探し、なければ `deck-build/assets/` を使う。

## 決まりの層と育て方

ワークスペースは、やり取りの積み重ねで決まりと点検を育てていく 1 つのプロダクト。大元（プラグイン）を直すべきものだけを PR にする。

| 層 | 置き場所 | 中身 | 誰が変えるか |
|---|---|---|---|
| 顧客の memory（その顧客の資料で、いちばん優先） | `Customers/<顧客>/memory.md` | その顧客の好みと、資料をまたいで効く相手のこと | 作る会話がその場で書く。dreaming は提案する。2 社以上で同じ趣旨なら `rules/` に寄せる |
| ワークスペース（優先） | `AGENTS.md`、`rules/<スキル>/<ファイル>`、`rules/deck-build/checks.py` | その人・その組織の決まりと点検、修正の指示で育つもの | 作る会話がその場で戻す。dreaming は提案し、「適用」で当てる。経緯は決まりの台帳（`.factory/ledger.jsonl`）に残す（git は前提にしない） |
| プラグイン | `skills/`（入った場所は読むだけ） | 誰が使っても同じ決まり、点検、スクリプト、テンプレート | `factory-kaizen` で PR。マージされたら `update` で届く |

- **決まりの本文と経緯を分ける。** 決まりは 1 項目ごとに ID（プラグインは `[visual-<番号>]`、ワークスペースは `[ws-visual-<番号>]`）と短い理由だけを書く。日付・ユーザーの言葉・どの資料か・ユーザーが決めたかは、ワークスペースの決まりの台帳に ID でつなぐ（`ledger.py why <ID>`）。資料・顧客の数から、ワークスペースに寄せるか、プラグインに上げるかを決める。
- **`rules/` と memory は読み忘れない。** プラグインのファイルを開くと（Claude Code は Read・Bash・Skill、pi は read・bash）、hook が同じパスの `rules/` のファイルを続けて出す。顧客の資料の `構成案*.md`・`社内メモ_*.md`・`references.md` を開くと、その顧客の `memory.md` を続けて出す。
- **次の一手は台帳が出す。** `ledger.py candidates` が、決まりごとの数から、下ろす（点検か作る手順へ）・書き直す・条件を足す・上げる・写しを消す・上書きを見直すを出す。境目（2 本以上の資料、2 社以上の顧客）はスクリプトが持ち、dreaming は趣旨と提案の文を考える。
- **点検もワークスペースで育てる。** `rules/deck-build/checks.py` の `slides(p, r)`・`doc(doc, r)` を、lint（`gslides.py check`・`docs.py check`）が毎回呼ぶ。`HARD` に入れた名前は要修正。書き方は `factory-init/templates/rules/README.md`。
- **大元に上げる。** ほかの人にも効くものは、dreaming が「プラグインに上げる」提案にし、`factory-kaizen` で出す。
  1. 元のリポジトリの worktree で直す。
  2. 過去の資料で確かめる。lint は前の版と変えた版をかけ比べ、見た目は正本から両方の版で仮に組み直してページの画像を並べる。
  3. 理由・背景・検証の結果・画像を入れた PR を作る。PR には資料の名前・URL・本文を出さず、「資料 1」の番号と規則ごとの数の変化、ユーザーが選んだ画像だけを載せる。
  4. マージされたら、`rules/` の写しを消す。
- `deck-research` の調べ直しの結果も、`factory-kaizen` で PR にする（PR に入れるのはスキルの直しと `sources.md`。調べた記録はワークスペースに残す）。

## Google の認証

API を直接呼ぶ（MCP は使わない）。トークンは `deck-build/scripts/gapi.py` が次の順に取る。gcloud も、ほかの Google のスキルも、動かすときには要らない。

1. 環境変数 `GOOGLE_OAUTH_ACCESS_TOKEN`（ほかの仕組みで取ったトークンを渡すとき）
2. `authorized_user` の認証情報の JSON（`GOOGLE_APPLICATION_CREDENTIALS`、なければ gcloud の ADC のファイル）の refresh_token。作るのは `gcloud auth application-default login --scopes=…`（`factory-doctor` がコマンドを出す）

gcloud の既定の OAuth クライアントで作った認証情報は、`google.quota_project` がないと 403 になる。

## 決めたこと

- 2026-10-11: setup は前の検討の `/deck-init`・`/deck-doctor` の案を、今の作りに合わせて入れる。名前は `factory-init`・`factory-doctor`（ユーザー「名前は `factory-init` `factory-doctor` のほうがいい気がします」）。
- 2026-10-11: プラグインの決まりとワークスペースの決まりがぶつかったら、ワークスペースの AGENTS.md を優先する。hooks（rules・corrections・guard・review_gate）は後回し（ユーザー「AGENTS.md 優先です。なお、hooks は後回しで良いです」）。
- 2026-10-11: Google Slides・Docs は MCP に切り替えず、API を直接呼ぶ。認証情報を渡せば単独で動く形にする。Unity Gateway の Google Drive MCP には `google_file_create`・`google_file_edit`・`google_slides_add_slide` などがある（ユーザー「ツール的には認証情報渡したら単独で動作するコードのほうが使い勝手がいい気がしました」）。`factory.toml` の `auth_command`（トークンを出すコマンド）はいったん入れたが、Databricks の社員は ADC で足りるので廃止した（ADC で足りる）。ほかの取り方は環境変数 `GOOGLE_OAUTH_ACCESS_TOKEN` で渡す（ユーザー「auth_command も廃止で良いです」）。

- 2026-10-11: `rules/` の開き忘れは、hook で防ぐ（ユーザー「開き忘れても止まらない …こちらも対応してください」）。ワークスペースは 1 つのプロダクトとして育て、大元は PR で直す。PR には理由・背景、見た目なら画像、過去の資料での検証の結果を入れる（ユーザー「基本的にセットアップ対象のフォルダ配下を1プロダクトのように育てていく方針で、やり取りの蓄積からルール・チェックすべき項目を改善、大元を改善すべき場合は PR 作成のようなコンセプトでおねがします」「PR には理由・背景情報の他、デザインに関するものであればスクリーンショットを含めるようにしてください。また、ローカルで変更して過去資料で検証した結果も提出する流れが望ましいです」）。

- 2026-10-12: PR を作るスキルの名前を `factory-pr` から `factory-kaizen` にした（ユーザー「factory-pr ではなく、工場を改修・発展のようなニュアンスの方がいいかな」。候補から factory-kaizen を選んだ）。

- 2026-10-12: 継続改善の仕組みを、Devin の Dreaming（Agent Memory Repo）・Hermes Agent・Letta・Codex の memories・GitHub Copilot Memory・ACE と比べて直す。修正の指示は構成案の節をやめ、ワークスペースの決まりの台帳（`.factory/ledger.jsonl`）に置き換える（ユーザー「1 は問題ありません」）。ワークスペースの git は前提にしない。dreaming の提案と適用・却下・戻すことも台帳で持つ（ユーザー「ワークスペースの git は前提としたくないです。その前提で再考してください。」）。プラグインの本文の日付と原文は台帳へ移し、ID と短い理由だけを残す。コンパクションの前に指摘を拾う hook は後回しのままにし、dreaming が取りこぼしを数えてから決める（推奨を説明したあと、ユーザー「ではその方針で進めてください。」）。
- 2026-10-12: 決まりが効いたかの手ごたえを、決まりの台帳で数える。プラグインに上げる提案と判断待ちも台帳に入れ（却下と答えを覚え、出し直さない）、決まりがあるのに言われた指摘を「再発」として数え、deck-review の指摘の表に「決まり」の列を足して結果（直した・残した（誤り）・聞く）を取り込む。`.factory/review_runs.jsonl` は作らず、台帳 1 つにまとめる。指摘の出ない決まりは、守られているのかもしれないので、それだけで外さない（案を説明したあと、ユーザー「1, 2, 5 を対応しようと思いますがどうですか？」「ではその方針で 5 まで含めて実装して」）。

- 2026-10-12: Claude Code・pi に貼るだけで初期設定が終わるプロンプトを README に置く。フォルダ・ツールの指定もその会話でする。エージェントが読む手順は `INSTALL.md`（oh-my-openagent の貼り付けのプロンプトと、Cline の `llms-install.md` を参考にした）（ユーザー「Claude や Pi にコピペするだけで初期設定が完了するプロンプトを README に追加してください。フォルダやツール指定もそのチャット内で行い、完了できるように、コピペした後に読み込むスキル等も整備してください。」）。

- 2026-10-13: 継続改善の仕組みを直す。会話の抜き出しに触った資料のフォルダを出し、指摘を誰が書いたか（作る会話・dreaming・取り込み）を台帳に残して週ごとの取りこぼしを出し、決まりごとの次の一手（上げた決まりの写しを消す、上書きを ID で書いて見直す、も含む）を `ledger.py candidates` が出す。顧客の `CLAUDE.md` は `memory.md` にし、hook が Claude Code と pi で続けて出す（ユーザー「1・2・3（4 と 5 を含む）と 6 を a で進めてください。」）。顧客ごとのものは決まりではなく好みとして memory に持つ（ユーザー「6 は顧客ごとのスライドのルールというより、嗜好に近い気がするので、いわゆる memory として持ったほうがいい気もしています。」）。

## 入れていないもの

`databricks-updates`（毎朝のアップデートのまとめ）と `pi-compaction-report`（pi の運用レポート）は、使う人のチャット・フォルダ・セッションに結びついた個人の定期の作業なので入れていない。

## 残っている課題

- **hooks の残り（後回し）:** 前の検討の corrections・guard・review_gate。corrections（コンパクションの前に指摘を拾う）は、dreaming の報告の「取りこぼし」の数が続けて多ければ入れる（Claude Code と pi の両方に要る。pi にきっかけがあるかは確かめていない）。入れたのは `rules/` と顧客の memory を続けて出すものだけ。pi の `/skill:<名前>`（読むツールを通らない）では出ない。
- **継続改善の残り:** コンパクションの前に拾う hook は、`ledger.py rules` の週ごとの取りこぼしの割合を見てから決める。顧客の memory の古さ（担当が変わった）は、食い違う発言が出たときに直すだけで、日付から外すことはしていない。ワークスペースの決まりの上書きは、ワークスペースの中でしか数えていない（ほかの人のワークスペースの上書きは、プラグインに上げる提案で届いたものだけ見える）。
- **スキルの中の経緯:** 2026-10-12 に、スキルの本文の持ち主の決めたこと（「ユーザーが決めた」と日付、ユーザーの言葉）を、決まりの ID に置き換えた。移した経緯は、持ち主のワークスペースの決まりの台帳に入れる（`git show <この直しの前>:skills/...` からも見られる）。測った日・調べた日・その日より前のファイルを指す日付は、意味が変わるので残した。PR に顧客の名前が入らないかは、`kaizen.py open` が見て止める（`Customers/` の顧客と資料のフォルダの名前、`[factory] private` の語）。
- **外部に出すとき:** 2026-10-12 に会社ごとの値をワークスペースに分けた。材料を集める道具は `factory.toml` の `[sources]`、社名・著作権表示・表紙のロゴは `[brand]`（`copyright` がないか仮の値なら組めない。factory-doctor が要修正）、テーマは `[slides.themes.<名前>]`・`[docs.themes.<名前>]`（`url`・`description`・`base`）、会社の素材はワークスペースの `assets/`、ドキュメントのテンプレートは `rules/doc-build/templates/`、会社の道具の使い方は `rules/`。プラグインに残る会社の前提は、組み込みのテーマ visual・company の色（Databricks のブランドの色）だけ。
- **Documents を移す:** 顧客フォルダの `CLAUDE.md` は `memory.md` に名前を変える（factory-doctor が「顧客の memory」で出す）。`~/Documents` は今も自分の `.agents/skills/` で動いている（factory-doctor が「スキルの重なり」を出す）。移すときは、Documents の AGENTS.md の表を雛形の形（スキルの名前で指す。`rules/` も開く）にし、`.agents/skills/` の中核の 6 つを外し、`.agents/skills/dreaming/log/` を `.factory/dreaming/log/` に、`.agents/skills/deck-build/log/lint_runs.jsonl` を `.factory/lint_runs.jsonl` に移す。`deck-research` の記録は 2026-10-12 に `Research/deck_research/` へ移した。旧い場所の `.agents/skills/deck-research/log` は、移したときに進んでいた会話のための symlink なので、`.agents/skills/` と一緒に消す。

## ライセンス

MIT（[LICENSE](LICENSE)）。
