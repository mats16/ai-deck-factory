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
| Python 3.11 以上、uv | 入れる。uv がないと、画像での測り（`box_pad.py`・`doc_layout.py`・`sheet.py`）が動かない |
| `factory.toml`・`AGENTS.md`（`CLAUDE.md`・`references_index.md`） | factory-init で置く |
| `factory.source` | git の checkout を指しているか。違えばパスを直すか、消す |
| スキルの重なり | ワークスペースの `.agents/skills/`・`.claude/skills/` に同じ名前のスキルがある。プラグインと二重に読まれるので、どちらを使うかをユーザーに聞く（ワークスペースのものを外すのはユーザーが決める） |
| `google.quota_project`、`slides.themes` の `url`、`drive.*` | factory-init の 4 のとおり埋める。`slides.templates`（前の版の書き方）が要修正なら、URL を `[slides.themes.<名前>]` の `url` に移す |
| テーマの説明 | `description` がないテーマは、エージェントが資料ごとに選べない。何のテーマで、どの資料・聞き手に使うかを書く（`deck-build/slides.md` の 3） |
| Google の認証 | 出たコマンド（`gcloud auth application-default login --scopes=…`）をユーザーに回してもらう。トークンの取り方は `factory.toml` の `[google]` のコメント |
| テンプレート・Drive のフォルダ | 開けないものは、URL の誤りか、共有されていない。持ち主に共有を頼むか、URL を直す |

## スクリプトの外で見るもの

材料を集める道具（`deck-practices/materials.md`）が使えるかは、スクリプトからは見えない。`factory.toml` の `[sources]` に書いた道具（MCP のサーバーかスキルの名前）が自分の道具の一覧にあるかを見て、ないものを「要確認」として一緒に返す。`[sources]` が空なら、どの道具を使うかをユーザーに聞いて書く。なくても資料は組めるが、材料の集め方が手作業になる。

## 返し方

要修正と要確認を、直し方と一緒に返す。ユーザーが回すもの（ログインのコマンド、共有の依頼）と、こちらで直せるもの（`factory.toml` の値）を分ける。直したら、もう一度回す。
