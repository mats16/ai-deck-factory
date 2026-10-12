# 情報源と調べ方（2026-10-06 時点。8 は 2026-10-09）

各回の調査で、よかったもの・外れ・アクセスのコツを足していく。詳しい根拠は `log/` の各報告の最後の節。

## 目次

1. 共通のアクセスのコツ
2. 日本語圏: 資料の中身
3. 日本語圏: 見た目・和文の組み方
4. 日本語圏: AI でスライドを作る実践
5. 英語圏: スキルと指示の仕組み
6. 英語圏: AI スライド生成の研究と実践
7. 社内とプラグイン
8. ドキュメント（Google Docs・ビジネス文書）

## 1. 共通のアクセスのコツ

| 相手 | 取れるか・取り方 |
|---|---|
| note・Zenn・Qiita・はてなブログ | WebFetch で本文が読める。有料の note は無料部分だけ |
| Speaker Deck | WebFetch でスライドの文字の要約が取れる。細部は落ちる |
| X（Twitter） | 取れない。話題になった投稿は、note やブログの引用から探すほうが早い |
| GitHub | `raw.githubusercontent.com` の生ファイルのほうが、github.com の表示ページより欠けにくい |
| arxiv | `/abs/` で要旨、`/html/` で本文（表の数値が取れる）。数値は必ず `/html/` で突き合わせる |
| 長いページ（W3C jlreq、Claude Code の docs の一部） | WebFetch の要約が浅い。`curl` で保存し、タグを除いて `grep` する |
| PDF | WebFetch で取れないことがある。`curl` + `pdftotext -layout` |
| Shift_JIS のページ（CUD の配色セット） | `iconv -f SHIFT_JIS` |
| リダイレクト | 手で追う（例: developers.openai.com → learn.chatgpt.com） |
| web_search | ときどき「Connection closed」で落ちる。再試行で通る |

## 2. 日本語圏: 資料の中身

- **よかった:** GitHub の carnot-tech/consulting-pptx-skill（`references/slide-rules.md` と `content-review-prompt.md`。約 110 の規約と、別のエージェントによるレビューの観点。今回いちばん使えた）。ゆるコンサの「パワポの極意」シリーズ（note.com/humble_mole134）。Zenn の rakko_inc（maya honey）、taka_tech1988、firefly。CARTA TECH BLOG、LayerX のテックブログ、ブロッコリーのブログ（登壇の審査側の見方）。Speaker Deck の pauli、takanorip、narihara、hypermkt、goemon。Ballista（constep.jp）のコンサル出身者のコラム。presen.ofsji.org の書評。
- **効いた検索語:** 「タイトルだけ 読める 資料」「メッセージライン 1スライド1メッセージ」「経営層 技術 説明 Zenn」「プロポーザル 採択 審査」「スライド 規約 ルールファイル」
- **外れ:** 「ガバニングメッセージ 縦の論理 横の論理」（定義は出るが一次に当たらない。bcg-jp.com は 503）、「AIっぽい日本語 直し方」「上司レビュー チェックリスト」（要約だけで出典がない）、Claude でのスライド作成の「2026 年版」SEO 記事
- **未読:** 書籍そのもの（山口周、高田貴久、照屋華子、内田和成、清水久三子）。今回は書評・要約記事経由の二次情報。サイボウズ・メルカリ・LayerX の社内の資料ガイドラインの本体は見つからなかった

## 3. 日本語圏: 見た目・和文の組み方

- **よかった:** 伝わるデザイン（tsutawarudesign.com。トップは概念だけで、下位ページ yomiyasuku1〜6・miyasuku1〜5・universal1〜3 が本体。WebFetch は「数値なし」と返すので `curl` で読む）。W3C jlreq（772KB。行間は "It is common that the line gap"、和欧間は "quarter em spacing" の節）。デジタル庁デザインシステム（design.digital.go.jp/dads/。typography・color・spacing が数値つき）。サイボウズ 小林大輔の Speaker Deck（アクセシビリティ。資料のルールとして最も直接的）。森重湧太の Speaker Deck（howtodesignslides）。広島大 天野由貴『スライド作成入門』（PDF）。吉村伸一の note、デザインとAI の note、Zenn の kazzzz。JTF スタイルガイド、SmartHR Design System（表記の規則）
- **効いた検索語:** 「スライド 1行の文字数 日本語 目安 根拠 調査」「PowerPoint 日本語 行間 倍数 固定値 フォント」「AIっぽいスライド 元凶 note」「和文と英数字の間 半角スペース スタイルガイド 比較」「BudouX 日本語 改行」
- **外れ:** 「けっきょく、よはく。 ルール」「ノンデザイナーズ・デザインブック 日本」「プレゼン資料のデザイン図鑑 要点」（本の一次に当たらない）、「freee／サイボウズ デザインシステム スライド」（Web・UI 向けで、スライドの数値がない）
- **測り方（pptx の方式のとき。2026-10-07 からは Google Slides のサムネイルで見る）:** この Mac で pptxgenjs → LibreOffice（`SAL_USE_VCLPLUGIN=osx`）→ PDF → `pdftotext -bbox-layout` で、行送りや折り返しを実測できる。字幅は Pillow の `ImageFont.getlength` で測れる（Noto Sans CJK JP: 全角 1.0 em、英数字 0.55〜0.60 em、スペース 0.223 em）

## 4. 日本語圏: AI でスライドを作る実践

- **よかった:** Zenn の kazzzz（Claude Code のスライドスキルの設計と品質ゲート）、ncukondo（生成 AI でパワポを作る方法の一覧）、wfukatsu（slide-forge）、spacemarket（社内テンプレートから外れない作り方）、megrou（公式スキルが動かないときの確認）。Qiita の fumiya20020409（「書いたルールは守られない」）、ntaka329（Slidev のネイティブ pptx の限界）。note の shin_yoshimura（AI っぽさの消し方）。はてなの susisu（モデル別の比較）、yuk-11、mosfet。企業ブログ（JBS、DevelopersIO、NEXTSCAPE）は失敗談が具体的
- **効いた検索語:** 「AIっぽさ 直し方 スライド」「画像化 サブエージェント レビュー pptx」「LibreOffice PowerPoint 別物」「pptxgenjs 日本語」「Claude Code スライド Zenn」
- **外れ:** 「Claude Code スライド 禁則」「禁則処理 pptx」（禁則まで扱う記事がない）。イルシル・Genspark などの比較記事（公式情報の整理で、実測が薄い）。LayerX・CyberAgent の記事（手順まで書いていない）
- **次に追う:** Zenn の `claude-code` × `pptx` のトピック、mosfet の続報、Claude Design の和文書体の対応、PowerPoint の実機での `p:kinsoku` の効果

## 5. 英語圏: スキルと指示の仕組み

- **docs:** まず https://code.claude.com/docs/llms.txt で全ページの索引を取る。よく使うのは memory（CLAUDE.md・AGENTS.md・rules・コンパクション）、skills、best-practices、features-overview、sub-agents、hooks-guide、context-window、scheduled-tasks、routines、env-vars。スキルの書き方の正本は https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- **Anthropic のブログ:** anthropic.com/engineering/ の equipping-agents-for-the-real-world-with-agent-skills、effective-context-engineering-for-ai-agents、writing-tools-for-agents、effective-harnesses-for-long-running-agents、multi-agent-research-system、demystifying-evals-for-ai-agents。claude.com/blog の steering-claude-code-skills-hooks-rules-subagents-and-more
- **リポジトリ:** anthropics/skills（skill-creator の SKILL.md、pptx・frontend-design のスキル、issue と PR）、anthropics/claude-code（CHANGELOG.md）、obra/superpowers（writing-skills）、ai-evals-course/evals-skills
- **人と実践:** Simon Willison、HumanLayer（writing-a-good-claude-md）、Hamel Husain、Scott Spence（スキルの発火率の実験）、Vercel（agents-md-outperforms-skills-in-our-agent-evals）、Hacker News
- **他のツール:** agents.md、learn.chatgpt.com の Codex の AGENTS.md（読み込みは既定 32 KiB まで）、cursor.com/docs/context/rules、GitHub Copilot の repository instructions
- **効いた検索語:** 「Claude Code skills not triggering description forced eval」「AGENTS.md outperforms skills」「superpowers writing-skills description trap」「Claude Code scheduled tasks routines /loop」「CLAUDE.md 守られない 原因」
- **docs を読むコツ:** 数値や決まりは "Quote verbatim" と頼む。長いページは結果がファイルに保存されるので、`grep` で該当の行を取る

## 6. 英語圏: AI スライド生成の研究と実践

- **arxiv の検索語:** "slide generation"、"presentation generation agent"、"PPTEval"、"SlidesBench"、"paper-to-slide"、"slide editing agent"、"VLM judge slide aesthetics"。web_search では「論文名 + arxiv」「システム名 + human agreement correlation」が効いた
- **研究グループ:** Hao Zheng ら（PPTAgent・DeepPresenter、icip-cas/PPTAgent）、Jiaxin Ge（AutoPresent）、Kyudan Jung・Jaegul Choo（Talk to Your Slides）、Yunqiao Yang ら（SlidesGen-Bench）、Nojun Kwak（ACE）、Rehg（ArcDeck）
- **追う論文:** SlidesGen-Bench の GitHub（計算で測る指標の実装を流用できるかもしれない）、DeepPresenter の本文（画像を見て直す手順）、SeaSlides の 3 段のフィードバック
- **公式と実践:** anthropics/skills の pptx（issue #531、PR #330）と frontend-design、Vercel の Gamma の事例、Beautiful.ai のヘルプ、Ethan Mollick の実演（Valence の記録）
- **未読:** Tufte、Duarte『Resonate』、Garr Reynolds の本文。Reddit と X の議論。TSBench・PPTC・DocPres・PreGenie の本文

## 7. 社内とプラグイン

社内の情報。顧客向けの資料に引かない。会社ごとの情報源（チャットのチャンネル、検索の語、見る文書、社内のプラグイン）は、ワークスペースの `rules/deck-research/sources.md` に書く。

- **プラグイン:** `~/.claude/plugins/installed_plugins.json` で入っている版の場所が分かる。

## 8. ドキュメント（Google Docs・ビジネス文書。2026-10-09）

- **よかった:** 文化審議会『公用文作成の考え方』（2022。PDF を `curl` → `pdftotext -layout` で grep）、JIS Z 8301:2019（kikakurui.com の写し）、JAGAT の小林敏「日本語組版とつきあう」（要素ごとの行間）、デジタル庁デザインシステムの typography と調達概要書の PDF、サイボウズ 仲田尚央のテクニカルライティングの Speaker Deck（`curl` で文字起こしが取れる）、textlint の各 preset の README と実装。Docs API・Drive API のリファレンス（`curl` してタグを除き、要求の名前を並べると、ない要求が分かる）、Docs API の release notes（RSS https://developers.google.com/feeds/docs-release-notes.xml ）、anthropics/skills の doc-coauthoring、Wikipedia「Signs of AI writing」（`action=raw`）、tanaikech.github.io。
- **いちばん効いたのは実験:** tmp の文書を組み、PDF に書き出して `pdffonts`・`pdftotext -bbox-layout`・画像で見て、ゴミ箱に入れる（1 回数十秒）。docs と実際の違い（表のセル、用紙、書体、行送り）はこれでしか分からない。
- **効いた検索語:** 「公用文作成の考え方 建議 50～60字 見出し 箇条書き」「表の番号と表題は表の上 図の題は図の下 JIS Z 8301」「デジタル庁 調達 提案書作成要領 文字サイズ ページ番号 目次」「JAGAT 横組み 行長 字詰め 行間」「Google Docs API comments anchored unanchored」「textlint-rule-preset-ai-writing」「Signs of AI writing WikiProject AI Cleanup」
- **外れ:** 「PoC 計画書 書き方 テンプレート」（要約が雛形を作る）、「Google ドキュメント 禁則処理 両端揃え 和欧間」「batchUpdate maximum number of requests」（公式の情報がない。実測する）、OSS の md2gdoc の類（画像と和文の書体を扱わない）、Vale と LanguageTool の日本語。
