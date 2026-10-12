# rules/

このワークスペースだけの決まりと点検。プラグインより優先する（`deck-practices/rules.md` の「決まりの層」）。

## 決まり: `rules/<スキル>/<ファイル>`

プラグインのスキルのファイルと同じパスに置く（例: `rules/deck-practices/visual.md` は `deck-practices/visual.md` への足しと上書き）。プラグインのファイルを開くと、hook がこちらを続けて出す。

- 各ファイルの冒頭に、どのファイルへの足しかを書く。上書きするときは「プラグインの〇〇の節より優先」と書く。
- 修正の指示を戻したら、日付とユーザーの言葉（原文）を添える。

## 点検: `rules/deck-build/checks.py`

lint（`gslides.py check`・`docs.py check`）が毎回読み込む。`slides(p, r)` はスライドの JSON（presentations.get）、`doc(doc, r)` はドキュメントの JSON（documents.get）を受け取り、指摘を `r.hits["<規則の名前>"].append("<場所>: <中身>")` で足す。`HARD` に入れた名前は要修正（exit 1）、ほかは要確認。

```python
import lint  # プラグインの lint の部品（flatten・paras・ptext）が使える

HARD = {"社名の旧表記"}

def slides(p, r):
    for i, s in enumerate(p.get("slides", []), 1):
        for e, _ in lint.flatten(s.get("pageElements", [])):
            text = "".join(lint.ptext(x) for x in lint.paras(e.get("shape", {}).get("text")))
            if "旧社名" in text:
                r.hits["社名の旧表記"].append(f"p{i}: 「{text[:20]}」")
```

## 大元に上げる

ほかの人にも効くと分かったものは、dreaming が「プラグインに上げる」提案にし、`factory-kaizen` で PR を出す。マージされたら、ここの写しは消す。
