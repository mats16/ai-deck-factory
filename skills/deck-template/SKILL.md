---
name: deck-template
description: 会社のスライドのテンプレート（Google Slides）から、AI Deck Factory のテンプレート（テーマ）を作る・整える。日本語のテンプレートがある、英語のテンプレートしかない（外資系の日本支社など）、テンプレートがない（新しく作る）の 3 つに分け、書体・文字の大きさ・大枠の色を残したまま、和文の描ける書体とコントラストの基準に合わせる。template.py の audit・check・--from-base を使う。「会社のテンプレートを使いたい」「テンプレートを作って」「テンプレートを整えて」と頼まれたときに使う。
---

# 会社のテンプレートから AI Deck Factory のテンプレートを作る

AI Deck Factory のテンプレートは、`slides.py new` が複製する Google Slides。テンプレートが決めるのは、テーマの色（マスターの配色の 12 の枠）、書体（マスターのプレースホルダーの書体。`slides.py build` がデッキの文字をこの書体にする）、ページの大きさ、ページ番号の位置だけ。字の大きさと配置は pages.py が書く（`../deck-practices/visual.md` の 1）。

- **元の会社のテンプレートは変えない。** 複製から、いちばん多くのページが使うマスターと、ページ番号の枠を持つ Blank のレイアウトだけを残し、ほかのレイアウト、見本のページ、マスターのロゴや著作権の行を消す（`template.py` の `pick`・`strip`）。人が画面で使う会社のテンプレートは、そのまま使い続ける。
- **会社の値はワークスペースの `factory.toml` に書く。** `[slides.themes.<名前>]`（作ったテンプレートの `url`、使い分けの `description`、元のテンプレートの `base`、書体、役割ごとの色）と `[brand]`（表紙の社名と著作権表示）。プラグインの `slides.py` の `THEMES` には足さない（visual・company は Databricks のテーマ）。
- コマンドは `K=<deck-build のフォルダ>/scripts`（このスキルのフォルダの `../deck-build/scripts`）で書く。

## 決まりの在りか

テンプレートを整えるときに合わせる決まり。値を変えるときは正本を直す（ワークスペースで変えるなら `rules/` の同じパス）。

| 決まり | 正本 | 測るもの |
|---|---|---|
| 色の役割（11 の枠と固定の 6 色）と、組ごとのコントラスト（18pt 未満は 4.5:1、18pt 以上か 14pt 以上の太字は 3:1） | `../deck-practices/visual.md` の 1（表と注）・3 | `template.py check`（役割の組 `PAIRS`）、`gslides.py check` の「コントラストが基準に届かない色の組」 |
| 書体（Noto Sans JP、コードだけ Cascadia Mono。Google Fonts にない書体は描けない） | `visual.md` の 2、`../deck-build/SKILL.md` の「納品物」、下の「書体」 | lint の「書体が … でない」（テンプレートの書体と比べる） |
| 文字の大きさ（11pt 以上。著作権表示とページ番号だけ 9pt）と版面（13.33 × 7.5 in、左右の余白 0.6 in、要素の上端） | `visual.md` の 1 | lint、`slides.py` の定数 |
| visual・company のテーマの値 | `../deck-build/scripts/slides.py` の `THEMES` | `template.py check visual` |
| テンプレートの作り方と、テンプレートが決めるもの | `../deck-build/slides.md` の 3 と、このファイル | `template.py` |
| 調べた経緯（文字の大きさの下限、コントラスト、色の数） | ワークスペースの `Research/deck_research/log/20261006_jp_visual.md` の 1-1・1-5・1-6、`Research/deck_research/state.md` の「採用したもの」 | |

## 流れ

1. **聞く。** 下の 3 つのどれか、元のテンプレートの URL、表紙の社名（日本法人の名前）、著作権表示、ブランドの色の決まり（ブランドガイドがあれば）、テーマの名前（英小文字。例: `acme`）。
2. **読む。** `python3 $K/template.py audit <元の URL>`。ページの大きさ、マスター（使っている枚数）の配色とコントラスト、レイアウトとプレースホルダー、書体（和文が描けるか）、プレースホルダーの文字の大きさ、和文の有無を出す（変えない）。
   - ページが 13.33 × 7.5 in でなければ、`slides.py` は組めない（位置を in で固定している）。元を複製し、複製の画面の「ファイル → ページ設定 → カスタム」で 13.33 × 7.5 インチにして、マスターとレイアウトが崩れていないかを画面で見てから、その URL で読み直す。
   - `slides.py` が使えるのは、プレースホルダーがページ番号の枠だけのレイアウト（audit の「slides.py が使える Blank」）。なければ `--from-base` が止まる。複製の画面のテーマビルダーで、Blank のレイアウトを作るか、Blank のレイアウトにスライド番号のプレースホルダーを足す。
3. **役割に色を当てる。** audit の配色から、`visual.md` の 1 の表の役割に会社の色を当てる。役割の名前は Databricks の色から付けたが、意味は役割（RED は会社の強調の色なら青でもよい）。

   | 役割 | 当てる色の目安 |
   |---|---|
   | `NAVY` | 表紙・扉の地と見出し。会社のいちばん濃い主色（DARK1 か ACCENT1 にあることが多い） |
   | `BG`・`PANEL` | 本文の地と、パネル・表の 1 行おきの地。会社の LIGHT1・LIGHT2（白、ごく淡い灰色） |
   | `RED` | 強調の色（図形の塗り、番号の丸、18pt 以上の文字） |
   | `RED_TEXT`・`RED_ON_NAVY` | `RED` と同じ色相で、18pt 未満の文字用と、`NAVY` の上の文字用。`RED` をそのまま書き、`check` の直す案で明るさを合わせる |
   | `NAVY_BLOCK` | 扉の中のブロック。`NAVY` を少し明るくした色 |
   | `SUB` | 補助の文字とフッター。会社の灰色 |
   | `GA`・`PREVIEW`・`OSS` | 提供ステージの札。意味で決まる色なので、ふつうは書かない（visual の値） |

   `GA`・`PREVIEW`・`OSS` のほかは全部書く。書かない役割は visual（Databricks）の値になり、会社の色の中で浮く（2026-10-12 に試したとき、青の `NAVY` の扉に visual の `NAVY_BLOCK` の灰色が残った）。1 枚に使う色は 4 色まで（`visual.md` の 3）なので、会社の配色をすべて使おうとしない。
4. **書体を決める。** 下の「書体」。
5. **`factory.toml` に書く。**
   ```toml
   [brand]  # 表紙の左下と、全ページの左下の著作権表示（ドキュメントのフッターも）。copyright は要る（factory-doctor が見る）
   company = "アクメ・ジャパン株式会社"
   copyright = "© 2026 Acme, Inc. All rights reserved."  # lint が 9pt を通すのは「© <年> <社名> All rights reserved.」の形だけ（factory-doctor が確かめる）

   [slides.themes.acme]  # 会社のテンプレートのテーマ。色は役割の名前（visual.md の 1）、# は付けない
   description = "アクメの会社の色のテーマ。顧客に出す提案・説明と社外の登壇に使う。社内の勉強会には使わない（visual）"  # 何のテーマで、どの資料・聞き手に使うか、使わない場面（../deck-build/slides.md の 3）
   base = "https://docs.google.com/presentation/d/<元のテンプレート>/edit"
   font = "Noto Sans JP"
   NAVY = "002B5C"
   ...
   ```
6. **測る。** `python3 $K/template.py check acme`。役割の組ごとの比と、届かない組の直す案（色相と彩度を保ち、明るさだけを変えた色）を出す。直す案は会社のブランドの色を変えるので、前と後の色をユーザーに見せて決めてもらう（黙って写さない）。直す案を使わないなら、当てる色を替える。NG が 0 になるまで繰り返す。
7. **作る。** `python3 $K/template.py acme --from-base`。元を `[drive] factory` の下の Themes フォルダ（なければ作る）に複製し、マスターと Blank だけを残し、配色・書体・ページ番号を合わせ、見本のページ（表紙、章の扉、色の早見表、部品の 2 枚）を組む。URL は `[slides.themes.acme]` の `url` に書き込まれる（手で写さない）。
8. **確かめる。** `python3 $K/gslides.py check <テンプレートの URL>`。要修正は 0、コントラストの一覧に出るのは見本の飾り（章番号）だけにする。全ページの画像を開き、書体が描けているか（明朝や別のゴシックになっていないか）、社名と著作権表示、会社の資料と並べて色に違和感がないかを見る。URL をユーザーに渡して見てもらう。
9. **使い始める。** 既定にするなら `[slides] default_theme` を書き換える。デッキごとに選ぶなら `slides.py new <フォルダ> <名前> --theme acme`。

## 3 つの場合の違い

### A. 日本語のテンプレートがある

- **書体:** audit の「和文」が「和文あり（Google Fonts）」なら、その書体を `font` に書いて残す。メイリオ・游ゴシック・ヒラギノなど Google Fonts にない書体は、Google Slides で描けないか、別の書体になる。下の表で近い書体に替え、替える前と後をユーザーに伝える。
- **文字の大きさ:** マスターとレイアウトのプレースホルダーの大きさは変えない。`slides.py` が組むページの文字の大きさは、`visual.md` の 1 に従う（タイトル 24pt、本文 11pt 以上など）。
- **色:** 会社の配色を役割に当て、届かない色だけ明るさを変える。

### B. 英語のテンプレートしかない（外資系の日本支社など）

Databricks の社内テンプレート（DM Sans、英語だけ）がこの場合で、visual・company のテーマはここから作った（`../deck-build/slides.md` の 3）。

- **書体:** 欧文の書体（DM Sans・Arial・Montserrat など）には和文の字がない。Google Slides は和文を別のゴシックで描き、どの書体になるかは選べない。和文のある Google Fonts の書体から、欧文の書体の印象に近いものを選ぶ（下の表）。英数字もその書体で描かれる。
- **社名と著作権表示:** 表紙の社名は日本法人の名前（例: アクメ・ジャパン株式会社）。著作権表示は本社の英語の表記のままでよい。
- **行間:** 英語のテンプレートは行間が詰まっている（タイトル 90% など）。`slides.py` は文字ごとに行間を書くので、テンプレートの行間は使わない。和文の行間は `visual.md` の 2。
- 英語の見本のページとレイアウトは、作ったテンプレートには残らない。

### C. テンプレートがない（新しく作る）

- **元:** Google Slides で新しいプレゼンを作り、「ファイル → ページ設定 → カスタム」で 13.33 × 7.5 インチにする（API ではページの大きさを決められない）。名前に「元」と付けて Themes フォルダに置き、その URL を `base` に書く。audit で「slides.py が使える Blank」があるかを見る。
- **色:** 会社のロゴ・Web サイト・ブランドガイドから、主色（`NAVY`）と強調の色（`RED`）を決め、ほかの役割をそこから作る（3 の表）。決まった色がなければ、2〜3 の組の案を `check` で測ってから見せる。visual の色は Databricks のブランドの色なので、ほかの会社のテーマにはそのまま使わない。
- **書体:** Noto Sans JP（既定。字幅の見積もりがこの書体で測ってある）。

## 書体

Google Slides で描けるのは Google Fonts の書体だけ。描けると確かめた和文の書体は `slides.py` の `JP_FONTS`（2026-10-07 に、テンプレートを複製した試しのデッキで同じ文を書体ごとに描いて見た）。

| 元の書体の印象 | 和文のある Google Fonts の候補 |
|---|---|
| ふつうのゴシック（Arial、Helvetica、Roboto、DM Sans、Inter、メイリオ、游ゴシック、ヒラギノ角ゴ） | Noto Sans JP（既定）、IBM Plex Sans JP（IBM Plex を使う会社）、BIZ UDPGothic（読みやすさを優先する会社） |
| 幾何学的なゴシック（Montserrat、Poppins、Futura） | Zen Kaku Gothic New、M PLUS 2、LINE Seed JP |
| 丸ゴシック | M PLUS Rounded 1c、Zen Maru Gothic |
| 明朝・セリフ（Times、Georgia、Garamond） | Noto Serif JP、Shippori Mincho、Zen Old Mincho、BIZ UDPMincho |

- `Noto Sans CJK JP`・`Hiragino Sans`・`Yu Gothic` は、API が受け付けても、描くと明朝と欧文のセリフ体になる（`template.py` の `NO_RENDER`）。`Meiryo` はゴシックで描かれたが、メイリオそのものかは見分けきれていない（使わない）。
- `BIZ UDGothic`・`Kosugi Maru` は英数字が等幅で、字の間が広く見える。
- 描けたかどうかは API の値では分からない（指定した名前をそのまま返す）。見本のページの画像で見る。
- `slides.py` の字幅の見積もり（`em_width`）は Noto Sans JP で測ってある。ほかの書体では英数字の幅が違い、折り返しの見込みがずれることがある。組むときの警告と画像で見る。
- コードの等幅の書体（Cascadia Mono）は、どのテーマでも替えない（`visual.md` の 2）。

## できないこと

- 13.33 × 7.5 in 以外のページには組めない（上の 2）。
- 書体が効くのはスライドだけ。ドキュメント（Google Docs）は Noto Sans JP のまま（`[brand]` の著作権表示はフッターに効く）。
- `font` に書けるのは `JP_FONTS` の書体だけ（`template.py` が止める）。ほかの和文の Google Fonts を使うなら、試しのデッキで描けるかを画像で確かめてから `slides.py` の `JP_FONTS` に足す。
- 会社のテンプレートの文字の大きさ・行間・レイアウトは、`slides.py` が組むページには効かない（`visual.md` の 1 の型で組む）。会社の大きさで組みたいときは、`slides.py` の部品を直す（`factory-kaizen`）。
- 人が画面で使う会社のテンプレート（全部のレイアウト）を、日本語用に整えることはしない。
- テーマに入れない色（`TEXT`・`RULE`・`RED_SOFT`・`STAGE_TEXT`・`DECOR`）は、どのテーマでも同じ灰色と淡い赤。章の扉の章番号（`DECOR`、飾り）は、会社の `NAVY` と合わないことがある。
- マスターのロゴは消える。ロゴを置くなら pages.py で画像として置く（`../deck-build/slides.md` の 6）。

## 直すとき

- 色や書体を変えたら、`factory.toml` を直して `check` を回し、`template.py <名前>` で合わせ直す（ID は変わらない）。作ったデッキは変わらない（複製した時点の写し）。
- 会社のテンプレートが新しくなったら、`base` を新しい URL にして `--from-base` で作り直す。前のテンプレートは消すか、名前に「旧」を付ける。
