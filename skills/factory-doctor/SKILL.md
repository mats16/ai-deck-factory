---
name: factory-doctor
description: AI Deck Factory を動かす前提を確かめる。Python・uv、ワークスペース（factory.toml・AGENTS.md）、スキルの重なり、Google の認証（環境変数のトークンか認証情報の JSON）、テンプレートと Drive のフォルダに届くか、材料を集める MCP を見て、直し方を出す。factory-init のあと、新しい環境、401・403、「factory.toml が見つからない」が出たとき、「環境を確かめて」「doctor して」と頼まれたときに使う。
---

# 前提を確かめる

```sh
cd <ワークスペース>
python3 <このスキルのフォルダ>/scripts/doctor.py          # 手元と Google の API
python3 <このスキルのフォルダ>/scripts/doctor.py --local  # 手元だけ（API を呼ばない）
```

1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。

## 見るもの

| 項目 | 要修正・要確認のとき |
|---|---|
| Python 3.11 以上、uv | 入れる。uv がないと、画像での測り（`box_pad.py`・`doc_layout.py`・`sheet.py`）と、lint の文節の点検（BudouX）が動かない |
| `factory.toml`・`AGENTS.md`（`CLAUDE.md`・`references_index.md`） | factory-init で置く |
| `factory.source` | 使わなくなった（factory-kaizen が自分で clone する）。ユーザーに伝えて消す |
| スキルの重なり | ワークスペースの `.agents/skills/`・`.claude/skills/` に同じ名前のスキルがある。プラグインと二重に読まれるので、どちらを使うかをユーザーに聞く（ワークスペースのものを外すのはユーザーが決める） |
| `google.quota_project`、`slides.templates`、`drive.*` | factory-init の 3 のとおり埋める |
| `slides.themes`（前の版の書き方） | テーマの表を、ワークスペースの `themes/slides/<名前>.json`（`kind: Theme`。色は `colors` の下に同じ名前で書き、`url` は書かない）に移し、`url` を `[slides.templates]` の「<名前> = "<url>"」に移して、表を消す。テンプレートのある名前は `slides.py theme <url>` でも写せる（2026-10-16 より前のテンプレートは、テーマに入れない色・`copyright`・`mono`・`description` が抜けるので、表から写す）。移す前に、表のコメントに残した経緯をどこに残すかをユーザーに聞く（JSON にはコメントを書けない） |
| `themes/slides/<名前>.json`、テーマのファイル、`slides.default_theme` | 書けない値は、出た場所を直して `slides.py lint <ファイル>` で確かめる。テンプレートだけでファイルのないテーマは `slides.py theme <URL>` で写す |
| テーマの説明 | `description` がないテーマは、エージェントが資料ごとに選べない。何のテーマで、どの資料・聞き手に使うかを書く（`deck-build/slides.md` の 3） |
| `review.*`、AGENTS.md の方針のレビュー・返したあとの直し | `review.*` は雛形の範囲の値（`"ai"`・`"human"`、1〜3）に直す。AGENTS.md に前の雛形の「人がレビューするかも選んでもらう」か「ユーザーに返す前に、スキル `deck-review` で全体をレビューする」が残っていれば、ユーザーに見せてから雛形の今の文（`[review] plan_reviewer` に従う。新しく作った資料は `deck-review`、返したあとは `deck-practices` の「返したあとの依頼」）に替える（ワークスペースの決まりなので、黙って直さない） |
| Google の認証 | 出たコマンド（`gcloud auth application-default login --scopes=…`）をユーザーに回してもらう。トークンの取り方は `factory.toml` の `[google]` のコメント |
| テンプレート・Drive のフォルダ | 開けないものは、URL の誤りか、共有されていない。持ち主に共有を頼むか、URL を直す |

## スクリプトの外で見るもの

材料を集める道具（`deck-practices/materials.md`）が使えるかは、スクリプトからは見えない。`factory.toml` の `[sources]` に書いた道具（MCP のサーバーかスキルの名前）が自分の道具の一覧にあるかを見て、ないものを「要確認」として一緒に返す。`[sources]` が空なら、どの道具を使うかをユーザーに聞いて書く。なくても資料は組めるが、材料の集め方が手作業になる。

## 返し方

要修正と要確認を、直し方と一緒に返す。ユーザーが回すもの（ログインのコマンド、共有の依頼）と、こちらで直せるもの（`factory.toml` の値）を分ける。直したら、もう一度回す。
