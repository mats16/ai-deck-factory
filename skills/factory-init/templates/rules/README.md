# rules/

このワークスペースだけの決まりと点検。プラグインより優先する（`deck-practices/rules.md` の「Rule layers」）。

## 決まり: `rules/<スキル>/<ファイル>`

プラグインのスキルのファイルと同じパスに置く（例: `rules/slides-build/visual.md` は `slides-build/visual.md` への足しと上書き）。プラグインのファイルを開くと、hook がこちらを続けて出す。

- 各ファイルの冒頭に、どのファイルへの足しかを書く。プラグインの決まりを上書きするときは、その ID を `- [ws-slides-visual-<番号>] 〜は〜にする（slides-visual-012 より優先。<短い理由>）。` の形で書く（ID のない節なら「プラグインの〇〇の節より優先」）。
- 決まりは 1 項目ごとに ID を付ける（`- [ws-slides-visual-<番号>] 〜のときは〜する（<短い理由>）。`。ID は `ledger.py next ws-slides-visual`）。日付とユーザーの言葉（原文）は本文に書かず、決まりの台帳（`.factory/ledger.jsonl`）に ID でつなぐ（`deck-practices/rules.md` の「Routing corrections」）。

## 点検: `rules/slides-build/checks.py`・`rules/docs-build/checks.py`

lint が毎回読み込む。スライドの lint（`slides.py lint`・`gslides.py check`）は `rules/slides-build/checks.py` の `slides(p, r)` にスライドの JSON（presentations.get）を、ドキュメントの lint（`docs.py check`）は `rules/docs-build/checks.py` の `doc(doc, r)` にドキュメントの JSON（documents.get）を渡す。どちらも指摘を `r.hits["<規則の名前>"].append("<場所>: <中身>")` で足す。`HARD` に入れた名前は要修正（exit 1）、ほかは要確認。

```python
# rules/slides-build/checks.py
import lint  # スライドの lint の部品（flatten・paras・ptext）が使える

HARD = {"社名の旧表記"}

def slides(p, r):
    for i, s in enumerate(p.get("slides", []), 1):
        for e, _ in lint.flatten(s.get("pageElements", [])):
            text = "".join(lint.ptext(x) for x in lint.paras(e.get("shape", {}).get("text")))
            if "旧社名" in text:
                r.hits["社名の旧表記"].append(f"p{i}: 「{text[:20]}」")
```

```python
# rules/docs-build/checks.py
import doc_lint  # ドキュメントの lint の部品（gdoc_paras・gdoc_text）が使える。スライドの lint はここからは読めない

HARD = {"社名の旧表記"}

def doc(doc, r):
    for n, p, _, _ in doc_lint.gdoc_paras(doc):  # 段落の番号、段落、表の番号、表の前の段落か
        if "旧社名" in (text := doc_lint.gdoc_text(p).strip()):
            r.hits["社名の旧表記"].append(f"段落 {n}: 「{text[:20]}」")
```

## 大元に上げる

ほかの人にも効くと分かったものは、dreaming が「プラグインに上げる」提案にし、`factory-kaizen` で Issue を出す。上げた決まりが入っているプラグインに届いたら、ここの写しを消す提案を dreaming が出す（`ledger.py candidates` の「写しを消す」）。

## 顧客の memory: `Customers/<顧客>/memory.md`

顧客ごとの好みは、ここではなく顧客のフォルダに置く（`deck-practices/rules.md` の「Customer memory」）。その顧客の資料を開くと、hook が続けて出す。
