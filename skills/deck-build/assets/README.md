# 画像の素材の台帳

スライドとドキュメントに貼る画像・アイコン・ロゴの出どころを、ここにまとめる。貼り方の決まり（どれを先に使うか、`d.image`・`d.icon`・`png()`・`asset()` の使い方）は `../slides.md` の 6。調べた経緯と、試した URL の結果は `Research/google_slides_public_image_urls_20261008.md`。

- [assets-001] **URL のまま貼れるものを先に使う**。Slides API が URL で読めるのは PNG・JPG・GIF だけ。SVG は `png(<SVG の URL>)`（wsrv.nl）で PNG の URL にする。
- [assets-002] **ファイルでしか配られないものだけ、このフォルダに置く**。資料のフォルダの `build/assets/` に写さず、`asset("gcp/bigquery.png")` で指す。その資料だけの画像（画面の写し、流用元のデッキの図）は、今までどおり `build/assets/`。
- 足すときは、名前を英小文字・数字・ハイフンにし（`<製品>.png`）、下の「このフォルダのもの」に 1 行足す（元の URL、取った日、使ってよい範囲、社外に出せるか）。PNG と SVG の両方が配られていれば、両方を置く。
- ロゴとアイコンは各社の商標。構成図や説明に使い、変形しない・色を変えない・自社のものに見せない（各社の条件は下の表）。

## URL で貼れるもの

2026-10-08 に Slides API で貼れることを確かめた形。大きさは px。

| 用途 | URL の形 | 大きさ | 使ってよい範囲 |
|---|---|---|---|
| 線画のアイコン・製品のロゴ（Iconify） | JSON の `{"type": "icon", "name": "<セット>:<名前>"}`（中で `https://api.iconify.design/<セット>/<名前>.svg?color=…` を `png()` に通す）。セット: `tabler`（線画。既定）、`material-symbols`、`simple-icons`（1 色のロゴ）、`logos`（色付きのロゴ。`logos:<名前>` は社名の文字入りのことがあり、マークだけなら `logos:<名前>-icon`（例: `logos:databricks-icon`）。`logos:aws`・`logos:google-cloud`・`logos:microsoft-azure`・`logos:snowflake-icon`・`logos:oracle`・`logos:salesforce`・`logos:tableau-icon`・`logos:microsoft-power-bi`・`logos:aws-redshift` など）。名前は https://icon-sets.iconify.design/ で探す | 512（指定できる） | セットごと（tabler MIT、material-symbols Apache-2.0、simple-icons・logos CC0）。ロゴの商標は別 |
| SVG しかない画像（顧客のロゴなど） | `png("<SVG の URL>", w=1024)` → `https://wsrv.nl/?url=…&output=png&w=1024` | 指定どおり | 元の画像の条件 |
| AWS・Azure・Kubernetes・OSS の構成図のアイコン（mingrammer/diagrams） | `https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/<aws・azure・k8s・onprem・saas など>/<分類>/<名前>.png`。一覧は https://github.com/mingrammer/diagrams/tree/master/resources | 256〜300 | コードは MIT。絵は各社の条件: [AWS](https://aws.amazon.com/architecture/icons/)（構成図・資料・プレゼンに使ってよい）、[Azure](https://learn.microsoft.com/en-us/azure/architecture/icons/)（構成図・研修・文書に使ってよい。変形しない） |
| AWS のアイコン（AWS Labs） | `https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v23.1/dist/<分類>/<名前>.png` | 64 | 絵は CC-BY-ND 2.0。小さいので 0.5 in まで |
| 写真（Unsplash） | `https://images.unsplash.com/photo-<ID>?w=1600&fm=jpg` | 指定どおり | Unsplash License（商用可、クレジットは任意） |
| SVG のロゴ（Wikimedia Commons） | `https://upload.wikimedia.org/wikipedia/commons/thumb/<a>/<ab>/<ファイル>.svg/<幅>px-<ファイル>.svg.png`。幅は 20・40・60・120・250・330・500・960・1280・1920・3840 だけ | 指定どおり | ファイルごと |
| Google の製品のアイコン | `https://www.gstatic.com/images/branding/product/2x/<slides・sheets・drive>_2020q4_48dp.png`、`google_cloud_48dp.png`、`gemini_48dp.png` | 96 | Google のブランドのガイドライン。公式の一覧はなく、変わりうる |
| [assets-003] pi（pi coding agent）のマーク | `png("https://pi.dev/favicon.svg")`。黒 1 色（`#111111`）なので、白いカードの上に置く | 1024 | 記載なし。pi.dev の公式のサイトのマーク。製品の箱のロゴとして使う |
| [assets-004] T3 Code のマーク | `https://raw.githubusercontent.com/pingdotgg/t3code/main/assets/prod/black-universal-1024.png`（黒地の角丸に白の T3） | 1024 | リポジトリは MIT。マークの商標の条件は記載なし。製品の箱のロゴとして使う |
| 絵文字（Fluent Emoji、Microsoft） | `https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/<名前>/3D/<名前>_3d.png` | 256 | MIT |

使わないもの:

- mingrammer/diagrams の `gcp/`（旧い絵柄。Google は 2026 年から使わないよう案内している）と `onprem/analytics/databricks.png`（旧いロゴ）。Google Cloud は、このフォルダのものを使う。
- クレジットの要るもの（Icons8、Twemoji、Noto Emoji のアニメーション版）。ほかで足りる。
- URL から図を作るサービス（mermaid.ink・kroki.io・quickchart.io）。図の中身が第三者に渡るので、顧客の情報を渡さない。スライドの図は表と図形で組む（slides.md の 4）。ドキュメントの mermaid の図は、`docs.py` が手元の mermaid-cli で描く（`../../doc-build/SKILL.md` の doc-build-009）。

## このフォルダのもの

| フォルダ | 中身 | 元 | 取った日 | 使ってよい範囲・社外に出せるか |
|---|---|---|---|---|
| `blank.pptx` | `template.py --from-base` に元の URL を渡さないときに使う白紙（`../slides.md` の 3）。13.33 × 7.5 in（12188952 × 6858000 EMU）、レイアウトは Blank だけ（ページ番号の枠だけ）、マスターに `<p:hf hdr="0" ftr="0" dt="0"/>`（スライド番号を出す設定）、スライド 1 枚にページ番号の枠（ないと Google Slides でスライド番号がオフになり、足したページに枠ができない）、マスター・Blank・スライドのページ番号の枠の `a:bodyPr` の `lIns`・`tIns`・`rIns`・`bIns` が 0（`template.py` は内側の余白を 0 と見込む）。`template.py --selftest` がこの 5 つを見る | python-pptx の既定の pptx から、ほかのレイアウトと日付・フッターの枠を消して作り、作成者・プリンター設定・サムネイルを抜いた。変換したあとのマスターの名前は「Office Theme」 | 2026-10-14 | 社外に出せる（中身は空） |
| `gcp/` | Google Cloud の主な製品のアイコン（4 色、512 px の PNG と SVG）。`bigquery`・`cloud-storage`・`vertex-ai`・`looker`・`gke`・`cloud-run` など 22 個 | [Google Cloud icons](https://cloud.google.com/icons) の Core product icons（https://services.google.com/fh/files/misc/core-products-icons.zip） | 2026-10-08 | 構成図・技術文書に使ってよい。Google の後援に見せない（[Brand Resource Center](https://about.google/brand-resource-center/guidance/)）。社外に出せる |
| `gcp/category/` | 主な製品以外に使う分類のアイコン（2 色）。`data-analytics`・`databases`・`ai-machine-learning`・`storage` など 27 個 | 同じページの Product category icons（https://services.google.com/fh/files/misc/category-icons.zip）。製品とアイコンの対応は https://services.google.com/fh/files/misc/google-cloud-product-icons.pdf | 2026-10-08 | 同上 |
