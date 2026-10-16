---
name: factory-init
description: AI Deck Factory のワークスペース（資料と決まりを置くフォルダ）を作る。AGENTS.md・CLAUDE.md・factory.toml・references_index.md・rules/・.gitignore の雛形と Customers/・Internal/・Research/ を置き（あるファイルは上書きしない）、factory.toml の値を一緒に埋め、factory-doctor で確かめる。「ワークスペースを作って」「setup して」「AI Deck Factory を使い始めたい」と頼まれたときに使う。
---

# ワークスペースを作る

ワークスペースは、資料のフォルダと、`factory.toml` を置くフォルダ（例: `~/Documents`）。スクリプトは、今いるフォルダから上へたどって最初に見つかった `factory.toml` のフォルダをワークスペースとして扱う。置くものと、決まりの優先（ワークスペースの AGENTS.md と `rules/` がプラグインより優先）は、置いた `AGENTS.md` に書いてある。

## 手順

会話で入れているとき（リポジトリの `INSTALL.md`）は、1 は済んでいる。プラグインを入れたばかりの会話には、このスキルもほかのスキルも読み込まれていないので、ほかのスキル（deck-build・deck-template・factory-doctor）は、入れた場所の `skills/<スキル>/SKILL.md` を開いて従う。

1. **場所を決める。** 言われていなければ、今いるフォルダでよいかを聞く。すでに `factory.toml` か `AGENTS.md` があるフォルダなら、そのことを伝える（上書きはしない。足りないものだけ置く）。
2. **置く。**
   ```sh
   python3 <このスキルのフォルダ>/scripts/init.py <ワークスペース>
   ```
   出力の「置いた」「残した」をそのまま伝える。
3. **`factory.toml` を埋める。** 1 つずつ聞いて書く。分からないものは空のままにし、doctor の「要確認」に残す。
   - `[user] profile`: 名前・役割・担当の顧客を書いたファイル。
   - `[google]`: トークンの取り方。gcloud を使えるなら、doctor が出す `gcloud auth application-default login --scopes=…` を 1 回だけ回してもらう（ユーザーが自分で回す。ブラウザが開く）。ほかの仕組みでトークンを取るなら、環境変数 `GOOGLE_OAUTH_ACCESS_TOKEN` で渡す。gcloud の既定の OAuth クライアントなら `quota_project` も要る。
   - `[brand]`: `copyright`（全ページの左下の著作権表示。「© <年> <社名> All rights reserved.」の形）は要る。書かないと、スライドもドキュメントもテンプレートも組めない。`company`（表紙の左下の社名）と `logo`（ドキュメントの表紙のロゴ。`assets/` の中のパスか URL）は任意。
   - `[drive] shared_themes`: 全社の共有テーマのフォルダ（管理者が配っているテンプレートの置き場所）の URL。会社で配っていなければ空のまま。書いたら `[drive] factory` と Google の認証のあとで `python3 <deck-build のフォルダ>/scripts/slides.py themes` を回し、「共有。」と出たテーマから使うものを選んでもらい、`python3 <deck-build のフォルダ>/scripts/slides.py theme <出た URL>` を回す（テーマのファイル `themes/slides/<名前>.json` を写し、`[slides.templates]` に URL を書く）。共有のテーマで足りれば、次の `--from-base` は要らない。
   - `[slides.templates]`: `[drive] factory` を埋めたら、`python3 <deck-build のフォルダ>/scripts/template.py visual --from-base`（会社の色なら `company` も）でテンプレートを作る。元にするテンプレートを言われたら、その URL を `--from-base <元の URL>` で渡す（`factory.toml` には持たない。渡さなければ白紙の pptx〔`deck-build/assets/blank.pptx`〕から作る）（`[drive] factory` の下の Themes に作る）。URL は `[slides.templates]` に書き込まれる。visual・company の色と説明はプラグインの組み込みのテーマのファイルにある。会社のテンプレートを使うなら、スキル `deck-template` で作る（`[brand]` と、ワークスペースのテーマのファイル `themes/slides/<名前>.json`。テーマを 2 つ以上使うなら、それぞれに `description`〔どの資料・聞き手に使うか〕を書いてもらう）。
   - `[slides] default_theme`: 上の 2 つでテンプレートがそろったら、既定のテーマを選択式で聞く（`deck-template` の「既定のテーマを選ぶ」）。
   - `[drive]`: 顧客向け・社内向けのスライドとドキュメントの置き場所の根元。
   - `[review]`: 聞かない。雛形の既定（構成のレビューは AI、`/deck-review` は 3 周まで）のままにする。ユーザーが言ったときだけ変える。
   - `[sources]`: 材料を集める道具（社内の検索・チャット・会議の記録・wiki・顧客の台帳・利用額）。自分の道具の一覧にある MCP とスキルから候補を出して聞く。道具ごとの使い方を決まりにするときは `rules/deck-practices/materials.md` に書く。
4. **`AGENTS.md` を合わせる。** 「顧客とフォルダ」の表に担当の顧客を足す。足した顧客の profile を今作るかを聞き、作るならスキル `customer-profile` で作る（`[sources]` を埋めたあと）。置いた雛形の決まりで合わないものは、ユーザーに聞いてから直す（ワークスペースの決まりが優先するので、ここで直したことが効く）。
5. **git にするかを聞く。** 決まりと点検を育てていく履歴を残すなら、ワークスペースで `git init` し、最初の commit をする（置いた `.gitignore` が、決まりと設定だけを入れる）。リモートに上げるかはユーザーが決める。
6. **確かめる。** スキル `factory-doctor` を回し、要修正が 0 になるまで直す。

## 注意

- 雛形は `templates/` にある。ワークスペースで直したものは、雛形に戻さない（雛形は誰でも同じ出発点）。
- すでに `.agents/skills/` か `.claude/skills/` に同じ名前のスキル（deck-build など）があるワークスペースでは、プラグインのものと二重に読まれる。doctor が「要確認」に出すので、どちらを使うかをユーザーに聞く。
