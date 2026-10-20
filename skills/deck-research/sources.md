# Sources and how to research (as of 2026-10-06; section 8 as of 2026-10-09)

Add what worked, what missed, and access tips after each research run. The detailed evidence is in the last section of each report in `log/`.

## Contents

1. Common access tips
2. Japanese-language: material content
3. Japanese-language: look and Japanese typesetting
4. Japanese-language: practice of making slides with AI
5. English-language: mechanisms of skills and instructions
6. English-language: research and practice of AI slide generation
7. Internal and plugins
8. Documents (Google Docs, business documents)

## 1. Common access tips

| Target | Whether it can be fetched, and how |
|---|---|
| note, Zenn, Qiita, Hatena Blog | WebFetch reads the body. Paid note articles: only the free part |
| Speaker Deck | WebFetch gets a summary of the slide text. Details are lost |
| X (Twitter) | Cannot be fetched. For posts that got attention, searching for quotes in note or blogs is faster |
| GitHub | Raw files on `raw.githubusercontent.com` lose less than github.com display pages |
| arxiv | `/abs/` for the abstract, `/html/` for the body (table numbers can be taken). Always cross-check numbers against `/html/` |
| Long pages (W3C jlreq, some Claude Code docs pages) | WebFetch summaries are shallow. Save with `curl`, strip tags, and `grep` |
| PDF | WebFetch sometimes cannot fetch it. `curl` + `pdftotext -layout` |
| Shift_JIS pages (the CUD color sets) | `iconv -f SHIFT_JIS` |
| Redirects | Follow by hand (e.g. developers.openai.com → learn.chatgpt.com) |
| web_search | Sometimes fails with "Connection closed". Retrying works |

## 2. Japanese-language: material content

- **Good:** GitHub carnot-tech/consulting-pptx-skill (`references/slide-rules.md` and `content-review-prompt.md`: about 110 conventions and the viewpoints for review by a separate agent; the most useful this time). ゆるコンサ's 「パワポの極意」 series (note.com/humble_mole134). Zenn: rakko_inc (maya honey), taka_tech1988, firefly. CARTA TECH BLOG, LayerX's tech blog, ブロッコリー's blog (the reviewer side's view of talk selection). Speaker Deck: pauli, takanorip, narihara, hypermkt, goemon. Columns by former consultants at Ballista (constep.jp). Book reviews on presen.ofsji.org.
- **Search terms that worked:** 「タイトルだけ 読める 資料」「メッセージライン 1スライド1メッセージ」「経営層 技術 説明 Zenn」「プロポーザル 採択 審査」「スライド 規約 ルールファイル」
- **Misses:** 「ガバニングメッセージ 縦の論理 横の論理」 (definitions appear but no primary source; bcg-jp.com returns 503), 「AIっぽい日本語 直し方」「上司レビュー チェックリスト」 (summaries only, no sources), 「2026 年版」 SEO articles on making slides with Claude
- **Not read:** the books themselves (山口周, 高田貴久, 照屋華子, 内田和成, 清水久三子). This time, secondary information via reviews and summary articles. The actual internal material guidelines of サイボウズ, メルカリ, and LayerX were not found

## 3. Japanese-language: look and Japanese typesetting

- **Good:** 伝わるデザイン (tsutawarudesign.com; the top page is concepts only, and the lower pages yomiyasuku1–6, miyasuku1–5, universal1–3 are the substance; WebFetch returns "no numbers", so read with `curl`). W3C jlreq (772KB; line spacing is in the section "It is common that the line gap", Japanese–Latin spacing in "quarter em spacing"). デジタル庁デザインシステム (design.digital.go.jp/dads/; typography, color, and spacing with numbers). サイボウズ 小林大輔's Speaker Deck (accessibility; the most direct as rules for materials). 森重湧太's Speaker Deck (howtodesignslides). 広島大 天野由貴『スライド作成入門』 (PDF). 吉村伸一's note, デザインとAI's note, Zenn's kazzzz. JTF スタイルガイド, SmartHR Design System (notation rules)
- **Search terms that worked:** 「スライド 1行の文字数 日本語 目安 根拠 調査」「PowerPoint 日本語 行間 倍数 固定値 フォント」「AIっぽいスライド 元凶 note」「和文と英数字の間 半角スペース スタイルガイド 比較」「BudouX 日本語 改行」
- **Misses:** 「けっきょく、よはく。 ルール」「ノンデザイナーズ・デザインブック 日本」「プレゼン資料のデザイン図鑑 要点」 (no primary source for the books), 「freee／サイボウズ デザインシステム スライド」 (for web and UI; no numbers for slides)
- **How to measure (for the pptx method; from 2026-10-07, look at Google Slides thumbnails):** on this Mac, pptxgenjs → LibreOffice (`SAL_USE_VCLPLUGIN=osx`) → PDF → `pdftotext -bbox-layout` measures line pitch and wrapping. Character widths can be measured with Pillow's `ImageFont.getlength` (Noto Sans CJK JP: full-width 1.0 em, alphanumerics 0.55–0.60 em, space 0.223 em)

## 4. Japanese-language: practice of making slides with AI

- **Good:** Zenn: kazzzz (design and quality gates of a Claude Code slide skill), ncukondo (a list of ways to make PowerPoint with generative AI), wfukatsu (slide-forge), spacemarket (how to stay within the internal template), megrou (checks when the official skill does not work). Qiita: fumiya20020409 (「書いたルールは守られない」), ntaka329 (the limits of Slidev's native pptx). note: shin_yoshimura (removing the AI feel). Hatena: susisu (comparison by model), yuk-11, mosfet. Company blogs (JBS, DevelopersIO, NEXTSCAPE) have concrete failure stories
- **Search terms that worked:** 「AIっぽさ 直し方 スライド」「画像化 サブエージェント レビュー pptx」「LibreOffice PowerPoint 別物」「pptxgenjs 日本語」「Claude Code スライド Zenn」
- **Misses:** 「Claude Code スライド 禁則」「禁則処理 pptx」 (no articles cover 「禁則」). Comparison articles on イルシル, Genspark, etc. (a summary of official information; little measurement). LayerX and CyberAgent articles (do not go down to the steps)
- **Follow next:** the Zenn `claude-code` × `pptx` topic, mosfet's follow-ups, Claude Design's support for Japanese fonts, the effect of `p:kinsoku` in real PowerPoint

## 5. English-language: mechanisms of skills and instructions

- **docs:** First get the index of all pages from https://code.claude.com/docs/llms.txt. Often used: memory (CLAUDE.md, AGENTS.md, rules, compaction), skills, best-practices, features-overview, sub-agents, hooks-guide, context-window, scheduled-tasks, routines, env-vars. The source of truth for writing skills is https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- **Anthropic blogs:** anthropic.com/engineering/: equipping-agents-for-the-real-world-with-agent-skills, effective-context-engineering-for-ai-agents, writing-tools-for-agents, effective-harnesses-for-long-running-agents, multi-agent-research-system, demystifying-evals-for-ai-agents. claude.com/blog: steering-claude-code-skills-hooks-rules-subagents-and-more
- **Repositories:** anthropics/skills (skill-creator's SKILL.md, the pptx and frontend-design skills, issues and PRs), anthropics/claude-code (CHANGELOG.md), obra/superpowers (writing-skills), ai-evals-course/evals-skills
- **People and practice:** Simon Willison, HumanLayer (writing-a-good-claude-md), Hamel Husain, Scott Spence (experiments on skill trigger rates), Vercel (agents-md-outperforms-skills-in-our-agent-evals), Hacker News
- **Other tools:** agents.md, Codex's AGENTS.md on learn.chatgpt.com (loads up to 32 KiB by default), cursor.com/docs/context/rules, GitHub Copilot repository instructions
- **Search terms that worked:** 「Claude Code skills not triggering description forced eval」「AGENTS.md outperforms skills」「superpowers writing-skills description trap」「Claude Code scheduled tasks routines /loop」「CLAUDE.md 守られない 原因」
- **Tips for reading docs:** For numbers and rules, ask "Quote verbatim". For long pages the result is saved to a file, so take the relevant lines with `grep`

## 6. English-language: research and practice of AI slide generation

- **arxiv search terms:** "slide generation", "presentation generation agent", "PPTEval", "SlidesBench", "paper-to-slide", "slide editing agent", "VLM judge slide aesthetics". In web_search, 「論文名 + arxiv」 and 「システム名 + human agreement correlation」 worked
- **Research groups:** Hao Zheng et al. (PPTAgent, DeepPresenter, icip-cas/PPTAgent), Jiaxin Ge (AutoPresent), Kyudan Jung and Jaegul Choo (Talk to Your Slides), Yunqiao Yang et al. (SlidesGen-Bench), Nojun Kwak (ACE), Rehg (ArcDeck)
- **Papers to follow:** SlidesGen-Bench's GitHub (its implementations of computed metrics may be reusable), DeepPresenter's body (the procedure of fixing by looking at images), SeaSlides' three-stage feedback
- **Official and practice:** anthropics/skills' pptx (issue #531, PR #330) and frontend-design, Vercel's Gamma case, Beautiful.ai's help, Ethan Mollick's demos (Valence's record)
- **Not read:** the bodies of Tufte, Duarte's "Resonate", Garr Reynolds. Discussions on Reddit and X. The bodies of TSBench, PPTC, DocPres, PreGenie

## 7. Internal and plugins

Internal information. Do not cite it in customer-facing materials. Write company-specific sources (chat channels, search terms, documents to read, internal plugins) in the workspace's `rules/deck-research/sources.md`.

- **Plugins:** `~/.claude/plugins/installed_plugins.json` shows where the installed versions are.

## 8. Documents (Google Docs, business documents; 2026-10-09)

- **Good:** 文化審議会『公用文作成の考え方』 (2022; `curl` the PDF → `pdftotext -layout` and grep), JIS Z 8301:2019 (the copy on kikakurui.com), JAGAT 小林敏's 「日本語組版とつきあう」 (line spacing per element), デジタル庁デザインシステム's typography and the procurement overview PDF, サイボウズ 仲田尚央's technical writing Speaker Deck (a transcript can be taken with `curl`), the READMEs and implementations of each textlint preset. The Docs API and Drive API references (`curl`, strip tags, and list the request names to see which requests do not exist), the Docs API release notes (RSS https://developers.google.com/feeds/docs-release-notes.xml ), anthropics/skills' doc-coauthoring, Wikipedia "Signs of AI writing" (`action=raw`), tanaikech.github.io.
- **Experiments worked best:** build a tmp document, export it to PDF, look at it with `pdffonts`, `pdftotext -bbox-layout`, and images, and put it in the trash (tens of seconds per run). Differences between the docs and reality (table cells, paper, fonts, line pitch) can only be found this way.
- **Search terms that worked:** 「公用文作成の考え方 建議 50～60字 見出し 箇条書き」「表の番号と表題は表の上 図の題は図の下 JIS Z 8301」「デジタル庁 調達 提案書作成要領 文字サイズ ページ番号 目次」「JAGAT 横組み 行長 字詰め 行間」「Google Docs API comments anchored unanchored」「textlint-rule-preset-ai-writing」「Signs of AI writing WikiProject AI Cleanup」
- **Misses:** 「PoC 計画書 書き方 テンプレート」 (the summary makes up a template), 「Google ドキュメント 禁則処理 両端揃え 和欧間」「batchUpdate maximum number of requests」 (no official information; measure it), the md2gdoc-type OSS (do not handle images or Japanese fonts), Vale and LanguageTool for Japanese.
