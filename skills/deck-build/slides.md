# スライド（Google Slides）の作り方: Slides API で直接組む

[slides-001] スライドは pptx を作らず、Slides API で Google Slides を直接組む。LibreOffice は使わない。pptxgenjs は、手元の画像を貼るときの中継にだけ使う（6）。pptx の方式に戻すときは ワークスペースの `Archive/pptx_pipeline_20261007/README.md`。色・配置・文字サイズなどの見た目は `../deck-practices/visual.md`。

## 目次

1. コマンド
2. pages.py の書き方
3. テンプレートとテーマ
4. 図形と文字の組み方
5. Slides API の落とし穴
6. 画像・ロゴ・アイコン
7. 2026-10-07 より前の pptx のデッキ

## 1. コマンド

```sh
K=<deck-build のフォルダ>/scripts   # deck-build の SKILL.md のあるフォルダ。ほかのスキルからは、そのスキルのフォルダの ../deck-build/scripts
cd <フォルダ>/build
python3 $K/slides.py new <Drive のフォルダの URL> <YYYYMMDD_の名前> [--theme visual|company]   # 初めて組むとき。出た URL を構成案に書く
python3 $K/slides.py build <URL> [--force]          # 2 回目から。同じ URL に組み直す（画面で直されていたら止まる。下）
python3 $K/gslides.py check <URL> [--talk]          # lint・テキスト・全ページの画像（/tmp/slides_<ID の頭 8 字>/）・画像で測る箱の下の余白
python3 $K/gslides.py check <URL> --pages 3,5       # 直したページだけ、画像を取り直す（ページの数が変わったときは、自動で全ページ）
uv run -q $K/sheet.py /tmp/<名前>.png /tmp/slides_<ID>/p-0{2,3,4}.png   # 何枚かを 1 枚に並べて見る
```

- 置き場所（Drive のフォルダ）と名前は `SKILL.md` の「Drive に置く」。ローカルに pptx は作らない。
- 部品を分けて組む・試すための一時のデッキは、名前に `tmp` を入れる（`gslides.py check` が lint の記録に数えない。確かめたらゴミ箱へ）。
- [slides-002] **組み直すと、Google Slides の画面で直したところは消え、コメントは付け先を失う。** 直すのは pages.py と構成案。`build` は、前に組んだあとに画面で直されている（組んだときの版を Drive の appProperties に残して比べる）か、未解決のコメントがあると止まる。止まったら、直しとコメントへの対応を pages.py に入れてから `--force` で組み直す（`../deck-practices/SKILL.md` の「作業の始め方」の 6 の「直すのは pages.py と構成案」）。画面で直していないのに止まることがある（Slides の revisionId が、内容を変えずに変わる）。止まったら、Drive の `files.get` の `modifiedTime` と `revisions` を見て、前に組んだ時刻より後に直されていないことを確かめてから `--force` にする。
- 12 枚で、組むのに 15〜25 秒（batchUpdate は 1,300 件ほど）、`check` に約 10 秒かかる（2026-10-07）。
- **組むときの警告**（手で改行した行が枠に収まらない、自動で折り返した最終行が 2 字以下、見出しを縮めた、リードが 2 行、表のセルが折り返す）は、標準エラーに出て、最後の行に件数が出る。見込みなので、画像で確かめてから直すか残すかを決める（前の deck.js と同じ）。
- slides.py は素の `python3`（標準ライブラリ）で動く。手元の画像と、react-icons の名前（`Tb…`）のアイコンを貼るときだけ、グローバルの node（pptxgenjs・react-icons・sharp）を使う（6。URL の画像と Iconify のアイコンには要らない）。
- [slides-003] 素の `python3` には Pillow・python-pptx・markitdown がなく、ImageMagick もない。ライブラリの要るものは uv で動かし、道具は `scripts/` に置く（`sheet.py` と同じ）。画像の切り取りは `sips -c <高さ> <幅> --cropOffset <上> <左> <入力> --out <出力>`（px）。
- スクリプトの分担: `slides.py`（部品と組み立て。版面・色の定義もここ）、`template.py`（テンプレートの作り直し）、`gslides.py`（確かめると流用）、`lint.py`（ルールの数え上げ）、`box_pad.py`（画像で箱の下端と文字の間と、淡色のパネルの上寄せの文字の上下の空きを測る。Pillow が要るので uv で動き、`gslides.py check` が呼ぶ）、`gapi.py`（Google の API の呼び出し。認証、429 の取り直し、エラーの本文、アップロード）。API の呼び方を直すときは `gapi.py` だけを直す。人ごとに変わる値（テンプレートの URL と置き場所、既定のテーマ、quota project）はコードに書かず、ワークスペース（資料のフォルダの上。例: `~/Documents`）の直下の `factory.toml` に置く（`gapi.factory()` が読む。3）。

## 2. pages.py の書き方

pages.py には `NAME`（資料名。社内向けは `｜Internal Only`、秘密扱いは `｜Confidential` を末尾に書く）と `make(d)` だけを書く。資料名はフッターに表示せず、秘密区分だけを著作権表示の末尾に残す。部品は `slides.py` の `Deck` のメソッドを使う。

```python
from slides import NAVY, SUB, RED_TEXT, TEXT, RULE, X, W, INSET   # 色の役割と本文の左端・幅
NAME = "〇〇様_ご説明資料"
def make(d):
    s = d.cover("タイトル", "〇〇様｜2026-10-07", "副題")
    d.note(s, "表紙のノート。")
    s = d.page("見出し（短い名詞句）", "リード（このページで言えること）", kicker="キッカー（要るページだけ）")
    d.text(s, X, 1.78, W, 1.0, ["本文。", ("強調", {"bold": True}), "。"], spacing=125)
    d.source(s, ["出典: ", ("ブログの名前", {"link": "https://…"})])
    d.note(s, "話すこと。")
```

| 部品 | すること |
|---|---|
| `d.cover(title, kicker, sub)` | 表紙。2 行のタイトルは、文節の切れ目に `\n` を入れる |
| `d.divider(num, title, sub)` | 章の扉 |
| `d.page(title, lead, kicker)` | 本文のページ（キッカー・タイトル・リード）。ページの ID を返す。見出しが 1 行に収まらなければ 18pt まで縮めて警告する（見出しを短くするのが先） |
| `d.slide(bg, foot)` | 型のないページ。`foot=False` でフッターとページ番号を置かない（全面に画像を貼るページ。reuse.md の段階 1） |
| `d.text(s, x, y, w, h, parts, size, color, bold, align, valign, spacing, fill, line, bullets, kind, radius, edge, pad, gap, dash, weight)` | 文字の枠。`parts` は文字列か `(文字列, {"bold", "size", "color", "link"})` の並び。`\n` で段落を分け、`\v` は段落の中の改行。塗りがある枠は半径 0.1 in の角丸が既定。`spacing` は行間（%）。`edge=True` で文字の端を `(x, y)`・幅 `w` にそろえる（塗りのない文字。4）。塗りか枠線のある左寄せ・右寄せの文字は、箱の端と文字の間を 1 字分（枠でいちばん小さい文字の大きさ。lint と同じ測り方）空ける（`pad` で変える。4）。`gap` は段落の間の空き（pt）。基準の 2 倍以上の大きさの段落（大きな数字）は、行間を 100% にする（4） |
| `d.label(s, v, x, y, w, h, fill, color, size, bold, align, radius, pad)` | 札（日付・工程の名前など、塗りの箱と短い言葉の 1 つの図形）。既定は PANEL の地に濃紺の太字、中央寄せ。左寄せにすると、箱の端と文字の間を 1 字分空ける |
| `d.box(s, x, y, w, h, fill, line, kind, radius, dash, weight)` | 箱。塗りがあれば半径 0.1 in の角丸、枠線だけなら四角が既定。`kind="RECTANGLE"` で四角を明示。塗りか枠線のどちらか一方（visual.md の 4）。`dash=True` で枠線を点線に、`weight` で枠線の太さ（pt。省くと、赤（`RED`）の線は 2（`EMPH_PT`。強調の囲み）、ほかは 0.75）。強調の囲みは `d.box(…, line=RED, kind="ROUND_RECTANGLE")`、点線なら `dash=True` を足す（5、visual.md の 4） |
| `d.code(s, x, y, w, h, lines, hot, size)` | 濃紺のコードの箱。`lines` は 1 行ずつの文字列で、英数字は等幅（`MONO`）。`hot` の行（0 始まり）は濃紺の上の赤の太字。2026-10-09、3 つ目の資料で要ったので pages.py の `code_box` から移した |
| `d.card(s, x, y, w, h, head, body=…, items=…, fill, line, step, bullets)` | 見出しと本文のカード（4）。`h` に `None` を渡すと、中身から高さを決める（`card_h`）。下端（in）を返す。`head` などを省くと、白い地に罫線の箱だけ（中身を自分で組むカード。`h` を渡す）。`items` は既定で 1 つの文字の枠に流す（項目の間が中身の行数によらずそろう）。`step` を渡したときだけ決まった間隔で置く（左右のカードで項目の上端をそろえるときだけ使う） |
| `d.num(s, n, cx, cy, size, fill)` | 正円の番号。`(cx, cy)` は円の中心。`size` は `"S"`（0.3 in・11pt、図の中の印）・`"M"`（0.36 in・14pt、カードと手順。既定）・`"L"`（0.48 in・18pt、大きな段）。大きさは `slides.py` の `NUM`（4、visual.md の 4） |
| `d.table(s, x, y, widths, rows, size, row_h, header, first_col, zebra, align)` | 表。見出しの行は濃紺に白の太字、1 列目は濃紺の太字、1 行おきに PANEL、横の罫線は RULE（前の deck.js と同じ）。`align` は列ごとの `"l"`・`"c"`・`"r"`。下端の見込み（in）を返す（行は文字に合わせて伸び、JSON の行の高さは最小の値のままなので、下に置く要素はこの値で位置を決める） |
| `d.arrow(s, x1, y1, x2, y2, color, head, dash, weight)` | 線と矢印。`dash=True` で点線（「できるが手間」など）、`weight` で太さ（pt、既定 1.25） |
| `d.image(s, src, x, y, w, h, alt)` / `d.icon(s, name, x, y, size, color)` | 画像とアイコン（6）。ロゴには `alt` に名前。SVG の URL は `png(url)`、直下の `assets/` の画像は `asset("gcp/bigquery.png")` で渡す |
| `d.band(s, head, sub)` | 結論バンド。下端を 6.60 に固め、中身に合わせて上へ伸ばす。上端を返す |
| `d.source(s, parts)` / `d.note(s, text)` | 出典の行（頭に「出典: 」がなければ足す）／スピーカーノート |
| `cols(n, gap, x0, w)` | 幅を n 列に分けた (左端, 幅) の並び |

- 色は役割の名前で渡す（`NAVY`・`SUB`・`RED_TEXT` など。一覧は `slides.py` の冒頭と visual.md の 1）。位置も `slides.py` の名前（`X`・`W`・`Y_BODY`・`BAND_BOTTOM` など）を使い、数字を写さない。役割の名前はテーマの色を指すので、テンプレートを替えると色が変わる。テーマに入れない色（`TEXT`・`RULE`・`CARD`・`RED_SOFT`・`STAGE_TEXT`・`PUBLIC_PREVIEW`）も名前で書く。`TEXT`・`RULE`・`RED_SOFT`・`STAGE_TEXT`・`DECOR` はテーマで値が替わり、組むときに `paint` とアイコンが置き換える（既定の 6 桁で書いた同じ値も置き換わる）。提供ステージの札の塗りは `STAGE_FILL[<GA・Public Preview・Beta・Private Preview・OSS>]` で引く。
- ページへのリンク（`{"link": 12}`）は、組むときにそのページの ID で付く。画面でページを足したり並べ替えたりしても、同じページを指す。
- `d.text` の行間（`spacing`）を省くと、2 行以上の見込みなら 125、1 行なら 100 になる（visual.md の 2）。表のセルは 2 行以上なら 120。
- フッター（左下の著作権表示）は表紙・扉を含む全ページに自動で入る。文言は `factory.toml` の `[brand] copyright`（デッキのテーマの `copyright` があればそれ。`slides.py` の `COPYRIGHT`）、文字は 9pt（`COPYRIGHT_PT`）、明るい地は `SUB`、濃紺の地は `RULE`。資料名は表示せず、`NAME` 末尾の `Internal Only`・`Confidential` だけを残す。初公表年は現在年へ自動更新しない。`foot=False` の流用ページには重ねない。ページ番号は表紙以外の右下に著作権表示と同じ 9pt で入り、テンプレートの枠なので、画面でページを並べ替えても合う。
- [slides-004] **部品は slides.py にあるものを使う。前の資料から写さない**。1 つの資料でだけ要る部品は pages.py に関数で書き、2 つ目の資料で要ったら slides.py に移す。
- slides.py の部品を足したり直したりしたら、`python3 $K/slides.py --selftest` と `python3 $K/template.py --selftest` を通し、テンプレートの見本を組み直して見る（`python3 $K/template.py visual`。そのあと `gslides.py check <テンプレートの URL>`）。company は使っていないので、組み直さなくてよい（下の 3）。部品を変えると、それを使う資料を組み直したときに見た目も変わる。

## 3. テンプレートとテーマ

テンプレートは `template.py <テーマ> --from-base` が `[drive] factory`（個人の資料の根元）の下の「Themes」フォルダに作る（なければ作る。フォルダの ID や URL は持たない）。使うテンプレートは、ワークスペースの `factory.toml` の `[slides.themes.<名前>]` の `url` で 1 つずつ指し、元にしたテンプレートは `base`。スクリプトはここを読む（この持ち主の visual・company は、前に作った「Templates」フォルダにある）。Databricks の 2026 年版の社内テンプレートを複製し、次を変えたもの（`template.py`）。

- マスター「Databricks Theme」と、レイアウト「Content E - Blank」だけを残した（見本のページ 98 枚、ほかのレイアウト 38 個、マスター「Simple Light」を消した）。
- マスターの著作権の行（©2021）とロゴ、Blank の全面の四角（ページの地を覆ってしまう）を消した。フッターは slides.py が書く。
- マスターの配色（12 の色）をテーマの色にした。プレースホルダーの書体を Noto Sans JP にした。
- ページ番号の枠を著作権表示と同じ 9pt（`COPYRIGHT_PT`）・行間 100・補助の色（SUB）にし、右端を本文の右端（12.73 in）、上端を著作権表示の文字（7.18 in）にそろえた（この枠は内側の余白が 0）。大きさと上端が同じなので、左右の文字の高さがそろう。
- 見本のページ（表紙、章の扉、色の早見表、部品の 2 枚）を slides.py で組んだ。部品の見本は決まり（visual.md）どおりの使い方にし、部品を直したらここで崩れを見る（2026-10-08、`Research/slides_template_review_20261008.md`）。`new` で複製すると、見本のページは消え、pages.py のページになる。

組み込みのテーマは 2 つ。役割と色の対応は visual.md の 1。ほかの会社のテンプレートから作るテーマ（factory.toml の `[slides.themes]`。会社の書体と色）は `../deck-template/SKILL.md`。

**どのテーマで組むかは資料ごとに選ぶ**（`../deck-practices/SKILL.md` の「作業の始め方」の 5）。テーマは `factory.toml` の `[slides.themes.<名前>]` で管理する（探し方は Agent Skills にならった。名前と説明の一覧から説明で選ぶ）。
```toml
[slides.themes.default]   # 表の名前がテーマの名前（英数字と - _。default でもよい。既定にするのは [slides] default_theme）
url = "https://docs.google.com/presentation/d/<テンプレート>/edit"   # このテーマのテンプレート。template.py <名前> --from-base が書き込む
description = "アクメの会社の色のテーマ。顧客に出す提案・説明と社外の登壇に使う。社内の勉強会には使わない（visual）"
# 会社のテンプレートから作るときだけ: base（元のテンプレート）、font、役割ごとの色（../deck-template/SKILL.md）
# どのテーマにも書ける: mono（コードの等幅）、テーマに入れない色（TEXT・RULE・RED_SOFT・STAGE_TEXT・DECOR）、copyright（[brand] の代わり）
```
- **テンプレートのあるテーマが 2 つ以上あるのに `--theme` なしで `new` すると、一覧を出して止まる**（選び忘れを防ぐため。kaizen の検証の仮の資料は止めない）。
- **`description` は選ぶ手がかりのすべて。** エージェントは `slides.py themes`（名前・既定か・テンプレートがあるか・`description` の一覧）だけを見て選ぶ。何のテーマか、どの資料・聞き手に使うか、使わない場面（ほかのどれにするか）を 1〜3 文で書く。資料の種類や聞き手の言葉（「顧客向けの提案」「社内の勉強会」）を入れると選びやすい。
- 組み込みのテーマ（visual・company）は、コードに既定の説明がある。`[slides.themes.visual]` には `url`・`description`・`base`（元にするテンプレート）と、`mono`・テーマに入れない色・`copyright` だけを書ける（`description` を書けば既定の説明より優先する）。
- **デッキは自分のテーマの名前を持つ。** `template.py` が、テンプレートのマスターのページ番号の枠の代替テキストに `ai-deck-factory theme=<名前>` を書き、複製したデッキにも残る。`slides.py build`（`new` はテンプレート）はそれを読み、`mono`・テーマに入れない色・`copyright` を `factory.toml` から引いて組む。名前のないデッキ（合わせ直す前のテンプレートから作ったもの）と、`factory.toml` にそのテーマがないデッキは、既定の値で組む。

| テーマ | 色 |
|---|---|
| [slides-005] `visual`（既定） | このフォルダの色（visual.md の 1）。2025 年版の公式パレットから、コントラストを確かめて選んだもの |
| [slides-006] `company` | 会社の規定の色を念のため残しているテーマで、見本が古くても組み直さない。2026 年版の Databricks Theme の色のまま。役割のコントラストに届かない ACCENT5 だけを暗くした（`618794` → `50707B`。補助の文字が Oat Medium の上で 3.32:1 → 4.54:1） |

- **テンプレートが決めるのは、テーマの色、ページの大きさ（13.33 × 7.5 in）、ページ番号の位置だけ。** 字の大きさと配置は pages.py が文字ごとに書き、ページ番号の大きさと行間は slides.py が組むたびに書く（文字ごとに書いた値がテンプレートより優先される）。
- **作ったデッキは、複製した時点のテンプレートの写し。** テンプレートを直しても、作ったデッキは変わらない。デッキのテーマを替えるときは `new` で作り直す（URL が変わる）。
- 色を変えるときは、`slides.py` の `THEMES`（会社のテーマは factory.toml の `[slides.themes]`）を直して `template.py <テーマ>` を回す（配色・書体・見本を合わせ直す。ID は変わらない）。コントラストは `gslides.py check <テンプレートの URL>` で見る。
- 会社のテンプレートが新しくなったら、`factory.toml` の `[slides.themes.<テーマ>]` の `base` を新しい URL にして `template.py <テーマ> --from-base` で作り直す。作ったテンプレートの URL は `template.py` が `factory.toml` の `[slides.themes.<テーマ>]` の `url` に書き込む（手で写さない）。前のテンプレートは消すか、名前に「旧」を付ける。
- [slides-007] **`factory.toml`**（ワークスペースの直下。factory-init が置き、factory-doctor が確かめる）: 人ごとに変わる値だけを置く（テンプレートの URL と置き場所、既定のテーマ、quota project、Drive の置き場所の根元）。見た目の決まり（色・余白・版面）は置かない。スクリプトは今いるフォルダ、次にスクリプトのフォルダから上へたどって探し、なければ止まる。ほかの人がスクリプトを使うときは、`factory.toml` を写して自分の値にし、`template.py visual --from-base`・`template.py company --from-base` で自分のテンプレートを作る（書き方は `factory.toml` の冒頭のコメント）。
- テンプレートは誰とも共有していない。共有するときも、自動では共有せず、`anyone` にしない。

## 4. 図形と文字の組み方

位置は座標の計算で合わせず、図形と文字の枠の機能（`align`・`valign`）でそろえる。文字が増えても崩れにくく、画面で直しやすい。

- **図形と、その中の文字は 1 つにする。** 番号、札、矢印の中の言葉は `d.text(…, fill=RED, color=WHITE, align="CENTER", valign="MIDDLE")` にする。角丸の背景と文字は `finish` が編集可能な 1 グループにまとめる。正円は `kind="ELLIPSE"`。塗りのない文字は従来どおり透明の四角。
  - [slides-008] **正円の番号は `d.num` で組み、大きさは S・M・L から選ぶ**（円の大きさと文字の大きさには釣り合いがあるので、直径と文字の大きさを資料ごとに決めない。見本はテンプレートの部品のページ）。`d.num` は `d.text(…, kind="ELLIPSE")` を使う。 Google は正円の文字を、内接する四角のさらに 0.1 in 内側に置くので、0.3〜0.36 in の円では文字の場所が 14pt の数字より狭く、数字が右上にずれる（0.3 in で右 3.5 pt・上 2 pt、0.36 in で右 1.5 pt。「10」は 2 行に折り返す）。書体を替えても直らない（7 つの書体で、右に 1.2〜2.7 pt ずれた）。`d.text` は、円を塗りだけにし、円と同じ大きさの透明の枠を重ねて、1 グループにする（ずれは 0.6 pt 以内）。四角の枠なら、文字の場所（枠から内側の余白を除いたところ）が数字より狭くても、はみ出しを上下・左右に均等に振って中央に置く。ただし 2 字以上は幅が足りないと折り返す（「10」は文字の場所 0.20 in で折り返し、0.22 in で 1 行）ので、2 字以上のときだけ横を数字の幅まで広げる。行間は 100% にする。はじめは枠を余白の分（0.1 in）だけ円より大きくしていたが、選んだときの枠が大きすぎた。`d.box` と `_shape` で正円を置き、そこに文字を入れない。
- **大きな枠に文字のかたまりがいくつも入るときは、枠を別にしてよい。** 見出しと本文のカードは `d.card`（箱の上に一回り小さい文字の枠を重ねる。文字の枠の内側の余白は 0.1 in で変えられないので、枠と文字の間をここで空ける）。本文を 1 つの枠に入れるなら `body`、(見出し, 説明) の項目を間隔をそろえて並べるなら `items`。番号・ラベルなどが入る複雑な枠も、枠を `d.box` で置き、その上に `PAD`（0.08 in）だけ内側に文字の枠を置く。[slides-028] `d.card` の高さは、`h` に `None` を渡して中身から決める（`card_h` が、英数字の語を行をまたがずに送って行数を見込む）。隣の列やページの下端に合わせて伸ばさない（代表の 3 枚の記録で、中身より大きい箱がほぼすべてのデッキに出た）。列の高さをそろえるときは、並ぶカードの `card_h(w, head, body=…)` の最大を渡す。大きさの違う文字（大きな数字）が混ざるカードと `d.box` は、高さを呼ぶ側が決める。中の文字の枠は箱からはみ出しても切れず、そのまま描かれるので、項目や行を足したら箱の高さも直す（`items` の `step` は項目ごとに同じ間隔なので、行の多い項目が最後に来るとはみ出しやすい）。最終行と下端の間は `gslides.py check` の「要確認（画像で測った）」で見る（visual.md の 4。2026-10-09）。
- [slides-009] **格子のある図（ガント、比べる表、マトリクス）は、格子を表（`d.table`）で作る。** 四角と線を並べて組まない。表で表しにくいもの（月をまたぐバー、今日の線、ラベル）だけを、表の上に図形で置く。表なら、開いた人が行を足したり文言を直したりしやすい（lint が、上端と長さの同じ縦線が 3 本以上あると要確認に出す）。表の行は文字に合わせて伸びる（`row_h` は最小の高さ）。上に図形を置く表は、セルの文字を 1 行にして、画像で位置を確かめる。
  - [slides-010] 顧客の定例のスケジュール（1 枚のガント）は、本文を 11pt、1 か月の列を 1.0 in にし、バーの文字は 9pt（visual-037。バーは塗りと文字を 1 つの図形にする。札を付けるバーも、塗りの四角に別の文字の枠を重ねると lint が 11pt 未満の要修正にする）、言葉は 1 行 5 字・2 行までにして改行の位置を `\n` で決める。表の下に余った高さ（表の下端はフッターの上まで）は行に等しく配り（1 行に足すのは、行が間延びしない程度まで。11pt の本文なら 0.4 in ほど）、バーは行の上下の中央に置く。上だけ詰まって下が空くと、ページの重心が上に寄る。次の回は、新しいフォルダ（AGENTS.md の「フォルダの置き方」）に pages.py で作り直し、`slides.py new` で新しい URL にする。
  - `d.table` はセルごとの罫線の濃淡（月の間を薄く、項目の境目を濃く）を持たない。要るときは部品を足す（`updateTableBorderProperties` の `tableRange` をセルの範囲にする）。
- **グラフ**は、図形で描くか、Google Sheets のグラフを貼る（`createSheetsChart`。Sheets の数字を直すとグラフも直せる）。どちらも部品はまだないので、初めて要ったときに slides.py に足す。凡例・目盛り・色の決まりは visual.md の 5。
- **横に並べる文字は、`y`・`h`・`valign` をそろえる。** 横に並ぶカード、番号と見出し、ラベルと本文などは、枠の上端と高さを同じにし、`valign` も同じにする。1 行ずつ並べるもの（番号と見出しなど）は `MIDDLE` で中心をそろえる。文字の量が違うカードは `TOP` にして見出しの高さをそろえる。
- **縦に重ねる文字は、1 つの文字の枠に入れて改行で分ける。** 見出しと本文、ラベルと補足のように上下に並ぶものは、`parts` に `("見出し\n", {"bold": True})` と本文を並べる。`y` をずらした別々の枠にしない。
- **出典の行は、名前ごとにリンクを付けた run にする。** `("Mandiant M-Trends 2026", {"link": url})` のように、ブログ・講演・docs の名前にリンクを付け、つなぎの「、」や括弧は文字列のままにする。Appendix の出典のページへは `{"link": <ページ番号>}`。URL は pages.py の冒頭に 1 か所に置き、出典の行と Appendix の一覧で同じものを使う。lint は、リンクのない出典の行を要確認に出す（2026-10-06）。
- [slides-011] **文字の左端をほかの要素の端とそろえるときは、`d.text(…, edge=True)` にする**（枠を `INSET`（0.1 in）だけ外に出す。`page`・`source`・`cover` はそうしてある）。pages.py に、枠を外に出す関数（前の `t()`）を置かない（資料ごとに同じ関数を持たないため）。
- [slides-012] **塗りの箱に左寄せ・右寄せで置く文字は、`d.text`・`d.label` に塗りを渡せば、箱の端と文字の間が 1 字分になる**（visual.md の 4）。文字の枠の内側の余白は 0.1 in で変えられず、11pt でも 1 字に足りないので、文字の枠を内に縮めて図形と 1 グループにする。`d.box` の上に文字を重ねるときは、文字の端を箱の端から 1 字分以上離す。lint が、塗りの箱の端と文字の間が 1 字分（その枠でいちばん小さい文字の大きさ）より狭い文字を要確認に出す。
- [slides-013] **大きな数字と説明を 1 つの枠に入れるときは、行間を数字に合わせて調整しない。** `d.text` が、基準（`size`）の 2 倍以上の大きさの段落だけ行間を 100% にする（行間 125% のままだと、Google の行送りは pptx より広く、数字と説明が離れて見えた）。

## 5. Slides API の落とし穴

2026-10-07 に確かめた。

- **`presentations.create` は `pageSize` を無視して 10 × 5.625 in になる。** 必ずテンプレートを複製して作る（`slides.py new`）。
- **ページが 0 枚になると、使われていないマスターがレイアウトごと消える。** 前のページを消すのは、新しいページを作ったあと（`build` はそうしている）。
- **和文の言語（`ja-JP`）は付けられない**（文字の書式に項目がない）。禁則は Google Slides の組みに任せ、画像で行頭の句読点を見る。
- [slides-014] **文字の枠の内側の余白は 0.1 in で、変えられない。Google 標準の角丸の半径も直接は決められない。** 共通部品は、四角と正円を合成して一定半径の角丸を作る。枠線つきの塗りの箱（白いカードなど）は、線を引かずに、線の色の角丸の上へ線の太さ（0.75 pt）だけ内側に縮めた塗りの角丸を重ねて枠を作る。円の輪郭と辺の線をつなぐと、Google の描画で継ぎ目に 1〜2 px の段が出た。塗りのない角丸の囲み（`d.box(…, line=…, kind="ROUND_RECTANGLE")`）は、内側を塗れないので、辺を線、角を Google の円弧（`ARC`。既定で右上の 1/4 円）を反転して 4 隅に置いて描く。円弧を短い線 8 本でつないでいたときは、角張りと継ぎ目の段が出た。円弧にしても、線と図形の輪郭で Google の描き方が違うので、置く位置によっては角に 1 px の段が残る（反転を回転に替えても、辺を図形の輪郭にしても消えなかった。2026-10-08、テンプレートの見本 p.5 で測った）。`box`・塗り付き `text`・`card` の既定は半径 0.1 in。短辺が 0.2 in 未満なら半径を短辺の半分まで抑える。明示の `kind="ROUND_RECTANGLE"` もこの半径になる。Google 規定の形状が必要な小さな線画などに限り `radius=None` を使う。`kind="RECTANGLE"` は四角のまま。共通部品を変えても保存済みの資料は変わらず、次に `slides.py build` で組み直したときに反映される。別セッションは次の生成時に修正済みツールを読み直す。
- [slides-015] **点線は `dash=True` で付ける。角丸の点線も半径 0.1 in のまま描く。** 塗りのない角丸は辺の線 4 本と角の円弧 4 つで組むので、その 8 つに点線と太さを付ける。塗りと点線の枠の両方があるときは、塗りの角丸の上に点線の輪郭を重ねる（塗りの角丸を縁取る作り方では点線にできない）。Google 標準の角丸（`radius=None`）に点線を付けると、半径が短い辺の約 1/6 になり、中のカードと曲率が合わない。強調の赤い囲みは、点線でも実線でも線を 2pt にする（強調のための線なので、細くしない）。`d.box`・`d.text` は、赤の線の `weight` を省くと 2pt にする。2pt でも、線と円弧の継ぎ目に 1 px の淡い点が残る（4 倍に拡大すると見える。等倍ではほぼ分からない）。見本はテンプレートの部品のページ（4 枚目は表の 1 列の実線、5 枚目は点線）。
- **箇条書きの黒丸は、最初の行の字下げより、文字の大きさの半分ほど左に描かれる**（11pt で 6 pt、14pt で 7.2 pt。2026-10-08 に測った）。字下げが 0 だと、黒丸が枠の文字の左端からはみ出す。`d.text(…, bullets=True)` は最初の行を文字の大きさの半分だけ字下げして、黒丸の左端を本文の左端にそろえる。
- 文字の位置は UTF-16 の単位で数える（絵文字などは 2）。`slides.py` の `u16`。
- スピーカーノートの枠の ID は、ページを作ったあとでないと分からない。`build` は 2 回目の batchUpdate で書く。
- [slides-016] 文字は枠からはみ出しても切れない。lint は 8 行を超える本文だけを見るので、はみ出しは画像で見る。手で改行した行が枠に収まるかは、組むときに `em_width` の見込みで警告する。見込みは 1 字の差まで当たらないので、枠の幅の 98% を超える行は画像で確かめる。
- リンクを付けると、色を書かない限りテーマのリンクの色（赤）になる。`d.text` は周りの色を書く。
- 表のセルの内側の余白は、API で変えられない。
- **書体の名前は、ないものでも API が受け付けて、黙って別の書体で描く。** `Noto Sans CJK JP`（docx の書体）・`Hiragino Sans`・`Yu Gothic` は明朝と欧文のセリフ体になった。Google Fonts の和文の書体（BIZ UDPGothic、M PLUS 2、IBM Plex Sans JP など）は描ける（`Research/google_slides_jp_fonts_20261007.md`）。lint はテンプレートの書体（既定は Noto Sans JP）でない書体を要修正で止める（コードの等幅の書体〔既定は Cascadia Mono、テーマの `mono`〕は、英数字だけなら通し、和文が入ると止める）。
- [slides-017] **等幅の書体は、Google Fonts の版にリガチャがあると Google Slides がそれを描き、API では止められない。** JetBrains Mono の `->` が矢印 1 字になった。コードはリガチャのない Cascadia Mono（`MONO`。テーマの `mono` で替えられるが、リガチャのある `LIGATURE_MONO` は止める）にし、`mono=True`・`mono_cols` で付ける。`mono_reqs` は行頭の字下げの空白も等幅にする（空白が Noto Sans JP のままだと、4 字の字下げが 1.5 字ほどに縮む）。字の幅は `MONO_EM`（0.586 em。Cascadia Mono の値で、テーマの `mono` でも替えない）で見積もる（`Research/monospace_font_google_slides_20261009.md`）。
- [slides-018] **確認は、PDF に書き出さずにサムネイル（`pages.getThumbnail`）に一本化した**。12 枚で約 5 秒（6 本並列）で、PDF に書き出して画像にするのと同じ速さだった。Google Slides の画面と同じ描画で、ページごとに取り直せ、Drive の書き出しの 10 MB の上限もなく、poppler も要らない。サムネイルは重い読み込みの枠（1 分あたりの上限）に数えられるので、`gslides.py` は 429 が返ると待って取り直す。サムネイルの URL は 30 分で切れる。
- Drive の `files.export` は 10 MB で止まる（403「This file is too large to be exported.」）。pptx が要るときは `gslides.py export`（`exportLinks` から書き出す。65 枚の社内テンプレートの 14.6 MB も書き出せた）。
- **書き出した pptx は、和文でも言語が `en` になる**（`../deck-research/sources.md`）。顧客に pptx で渡すように頼まれたら、書き出したあとに ワークスペースの `Archive/pptx_pipeline_20261007/skills/office-jp/scripts/fixjp.py --all` で書体と言語をそろえる（言語がないと、PowerPoint で行頭に句読点が来る）。渡す前にユーザーに聞く。

## 6. 画像・ロゴ・アイコン

- [slides-019] **画像とアイコンは、URL か手元のパスを `d.image`・`d.icon` に渡すだけでよい。** 貼り方（下の一時の pptx）は `slides.py build` の中で済むので、pages.py で気にしない。「pptx を介さず」の依頼でも、このまま使う（デッキそのものは pptx を介さない）。意味のあるアイコンを省かない。単純な線画は `d.box`・`d.arrow(..., head=False)` で編集できる図形として組んでもよいが、正式な製品ロゴや複雑な画像を独自の図形で代用しない。
- [slides-020] **どこから取るかは、URL のまま貼れるものを先にする**。出どころと URL の形は `assets/README.md`（このスキルの中の素材の台帳。足したら台帳にも書く。自分だけの画像はワークスペースの `assets/` に置く。`asset()` はそこを先に探す）。次の順に探す。
  1. 公開の PNG・JPG・GIF の URL を、そのまま `d.image` に渡す（AWS・Azure の構成図のアイコンは mingrammer/diagrams、写真は Unsplash など）。
  2. アイコンと製品のロゴは `d.icon(s, "tabler:database", x, y, 0.4)`（Iconify）。
  3. [slides-021] ファイルでしか配られないもの（Google Cloud の今のアイコン、自社の製品のアイコン）は、ワークスペースの直下の `assets/` に置き、`asset("gcp/bigquery.png")` で渡す。資料のフォルダに写さない（資料をまたいで使い回すため）。
  4. その資料だけの画像（画面の写し、流用元のデッキの図）は `build/assets/`。
- [slides-022] **Slides API が URL で読めるのは PNG・JPG・GIF だけ。** SVG の URL を `d.image` に渡すと止まる。PNG の URL を先に使い、SVG のほうが合うとき（PNG が小さくて大きく置けない、PNG が配られていない、色を変えたい）は、`png(<SVG の URL>, w=1024)`（wsrv.nl が PNG に描いた URL）に切り替える。手元の SVG（`assets/` の `.svg`）は、組むときに PNG にするので、そのまま渡せる。
- `d.image(s, <パスか URL>, x, y, w, h)`。画像は縦横の比を保って枠に収まり、枠の中央に置かれる。左や上にそろえたいときは、枠を画像と同じ比にする。
- [slides-023] **手元の画像（`assets/`・`build/assets/`）は、組むときに Drive を経由して貼る（`slides.py` の `carry`）。** Slides API は、公開された URL の画像しか読めない（Drive の非公開のファイルの URL は「publicly accessible」でないと断られる）。`build` は、画像を pptxgenjs で 1 枚に 1 つずつ入れた pptx を作り、My Drive の直下に Google Slides として上げ、その画像の URL から貼って、上げたファイルを消す（フォルダを指定しないので、スクリプトをほかの人に渡してもそのまま動く）。共有の設定を変えて公開することはしない。Drive には S3 の署名付き URL にあたる仕組みがない（共有の期限は特定の人とグループにしか付けられず、匿名で取りに来る API には効かない）。Google Cloud Storage の署名付き URL でも貼れるが、採らない（速くなるのは画像のある build で約 4 秒だけで、バケットと署名用の SA を持ち続ける手間、ほかの人に渡すと動かないこと、sandbox に画像を置くことに見合わない。`Research/gcs_signed_url_images_20261008.md`）。Drive の `thumbnailLink` は Slides API に断られる。渡した URL は、画像の `sourceUrl` としてデッキに残る。
- ほかの Google Slides のページをそのまま貼るときは、`thumb_url(<URL>, <ページ番号>)` を `d.image` に渡す（`../deck-practices/reuse.md` の段階 1）。
- **顧客のロゴ**は、自社が公開している事例ページか、その会社の公式のプレスキットから取る（使ってよい範囲が確かめやすい）。落とさずに、その URL を `png()` に通して `d.image(s, png("<SVG の URL>"), …, alt="<社名>")` で貼る。Splunk のロゴは Wikimedia Commons の `Splunk_logo.svg` の PNG の URL（幅は台帳の決まった値。splunk.com の画像は直接取れなかった）。
- [slides-024] **アイコンと製品のロゴ**は `d.icon(s, "tabler:database", x, y, 0.4)` のように Iconify の名前で置く（名前は https://icon-sets.iconify.design/ で探す。ないと、組む前に止まる）。`tabler:` は線画で、色は本文色 `303F47` の 1 色（既定）。1 色のロゴは `simple-icons:` で、`color` にブランドの色を渡す（例: `d.icon(s, "simple-icons:postgresql", x, y, 0.4, "4169E1")`）。色付きのロゴは `logos:`（マークだけなら `logos:<名前>-icon`。`color` は効かない）。代替テキストは名前が入る。`color` は 6 桁で渡す。`NAVY`・`SUB` などテーマの色（中身は `DARK1`・`ACCENT5`）は画像の色にできず、透明の画像になって lint も気づかないので、`d.icon` が止める。前の pages.py の react-icons の名前（`TbDatabase`・`SiPostgresql`）も、そのまま組める（組むときに手元で PNG にする）。
- [slides-025] **自社の製品のアイコンがワークスペースの `assets/` にないときは、線画（`tabler:`）で代える前に、社内のアイコン集から探し（探す場所はワークスペースの `rules/deck-build/slides.md`）、見つかったら `assets/` とその台帳に足す。** 白い角丸の地と影の付いた画像は、地と影を外して透過にする。見つからないものだけ線画にし、構成案に書く（レビューの観点 5 の「製品を汎用の線画で代えていないか」で見る）。
- **自社の製品のアイコン**は、ワークスペースの `assets/<会社>/` に置き、`d.image(s, asset("<会社>/<製品>.png"), …, alt="<製品>")` で置く。ほかの会社の製品は `logos:`（Snowflake・Oracle・Salesforce・Tableau・Power BI・Redshift など）。BigQuery など Google Cloud の製品は `logos:` にないか旧い絵柄なので `asset("gcp/<製品>.png")`。
- 似た図は、過去の資料の考え方を借りて作り直す（`references_index.md` で探す）。

## 7. 2026-10-07 より前の pptx のデッキ

- pptxgenjs か python-pptx で作り、pptx を Drive に上げてある。`deck.js` を読み込む build.js（8 本）は、`deck.js` を ワークスペースの `Archive/pptx_pipeline_20261007/skills/office-jp/scripts/` から読み込むように直さないと動かない。部品を写して持っている build.jsは、そのまま動く。直すときは、pptx のまま直すか、Google Slides で作り直すかをユーザーに聞く（pptx のまま直す手順は、その Archive の `README.md`）。
- 2026-10-06 より前のデッキは、文字の下限 11pt と今の色（visual.md）より前に作った。作り直すときは、全体を今の決まりに合わせるかをユーザーに聞く。
- [slides-026] **Google Slides で作り直すとき**: build.js のページの関数を pages.py に移し、中身（見出し・本文・ノート）は変えない。部品は slides.py のものにし、deck.js の部品は写さない（この資料だけの部品は pages.py の関数）。座標はほぼそのまま使えるが、次の 6 つで崩れた。
  - pptxgenjs で `margin: 0` だった塗りのない文字は、Google の枠の内側の余白（5）の分だけずれる。`d.text(…, edge=True)` にする（4）。塗りのある札は `d.label`、番号は `d.num` にする
  - `d.table` の `row_h` は見出しの行にも効く。中身で伸ばす行は `row_h` を小さくして、行を文字に合わせて伸ばす
  - pptxgenjs の `margin`（12pt など）で左に余白を取った、左寄せの塗りの札は、Google では内側の余白が 0.1 in に固定されて 1 字分に足りなかった。`d.label`・`d.text` に塗りを渡せば 1 字分空く（4）
  - 大きな数字と説明を 1 つの枠に入れて行間を 125% にすると、Google の行送りが pptx より広く、数字と説明が離れて見えた。`d.text` が数字の段落だけ行間を 100% にする（4）
  - 線で組んだ格子（ガント）は表に直し、文字の箱だけだった人や製品の箱にはアイコンとロゴを足す（4、visual.md の 6）。足した分だけ文字の幅が狭まり、1〜2 字の最終行が出たので、画像で見て言い回しを詰める
  - URL が新しくなる（pptx の URL には組めない）。前の pptx は Drive に残し、消すかはユーザーに聞く。references_index.md には両方を載せ、どちらがいまの版かを書く
  - [slides-027] build.js の部品（text・box・chip・table など）を、同じ呼び方の部品集として写さない。pages.py に置くのは、その資料で要る小さな関数だけにする（文字の端をそろえるのは `edge=True`、札は `d.label`、番号は `d.num`、白いカードは `d.card` で、pages.py に写さない）。進め方をユーザーに確かめ、10 枚を超えるなら代表の 3 枚（`../deck-practices/SKILL.md` の「作業の始め方」の 6）を自分で確かめてから全体を組む。サブエージェントに分けて移すのも、その後にする（頼まれていないコードを先に作らないため）
