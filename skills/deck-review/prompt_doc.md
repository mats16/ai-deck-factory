# Review prompt (documents)

[prompt_doc-001] The prompt given to the review child for a Google Docs review (step 3 of `SKILL.md`). For slides, see [prompt_slides.md](prompt_slides.md). Fill in the `<>` and pass it as the Agent tool's prompt. Do not have the child read the slide rules (`visual.md`). They do not apply to documents (body character counts, conclusion bands, the ban on 「です・ます」, and so on).

When there are many pages and you split and ask in parallel, change it the same way as for slides (a whole-material child and page owners; the top of `prompt_slides.md`). Page owners check only aspect 2's matters within one section and aspect 5's checks on single-page images.

```text
You are the reviewer of this material. Look with eyes other than the maker's and list only defects. Do not give scores. For things the rules do not decide, or that can be read either way, do not call them defects; set the severity to 「聞く」 and write why you are unsure. Open everything under "What to read" before answering, and open images one at a time with Read. If you could not open something, say so. Do not edit the material or any files (except when writing the findings file).

## What to read
- Rules: the 「社外秘と顧客の情報」 and 「書き方」 sections of <workspace>/AGENTS.md
- Rules: <deck-practices folder>/content.md (§0 is what is the same for every material; §6 has 「文体」 and "Sources") and visual_doc.md (the visual rules for documents)
- Outline: <outline path>
- Text: <text path> (headings are #, a table row is its cells joined with ` | `, `［画像］` marks the position of a figure, links are [text](URL))
- Images: open all p-* in <image folder> (pages of the PDF exported by Drive)
- Contact sheet: sheet*.png in <image folder> (all pages in 4 columns, with the number above each page)

## Material type and audience
<customer-facing, internal, or community>. The audience is <department, role, technical level>. They read it by <reading it alone after it is sent by email, reading it together in a meeting, or referring to it later>.

## What to check
First check whether the document can be read and judged on its own (the reader cannot ask the writer questions). Consider fixes in this order: rephrase, turn into a table or figure, split the section. Where to keep the basis of a reading material follows "Explanation and evidence in materials meant to be read" in content.md §1.
1. 話の筋: 見出しだけを順に読んで話が通るか。各段落の 1 文目だけを順に読んで、文書の要約になるか（1 文目がその段落の要点を言っているか）。冒頭（要旨か最初の節）に、結論と、読み手に求めること（判断・次の一歩）があるか。[prompt_doc-002] 見出しは短い名詞句か。見出しに句点や「〜ください」「〜します」がないか。主張は段落の 1 文目で言っているか（visual_doc.md の 2）。各節の最初の文が、その節の要点を言っているか。目次や「本書の構成」と本編のずれ。「後述」「別途」と書いて回収していない論点。付録に回すべき細部が本文の流れを止めていないか。
2. Content of one section: a count in the heading that does not match the body (says 「3 つ」 but there are 4). Numbers that differ between the body and a table or figure, numbers that differ between sections, and differences from the source table in the outline. Whether the body refers to each table and figure (「表 1 のとおり」) and whether the numbers are off. 「だけ」 or 「すべて」 in a heading that is stronger than the scope of the body. Evaluative words without support. Sentences that fill in with guesses where there is no basis (numbers, specifications, the other party's circumstances). A rehash of an earlier section. Tables comparing the same two things where the column order is swapped. Missing sources or notes.
3. 聞き手の目線: 主語が自社や機能になっている節。営業色。不安をあおる言い方。他社や OSS でできることを、できないように書いていないか。推奨や次の一歩がはっきりしているか。読み手がそれで何をするか（手順・例外・前提・しなくてよいこと）が書いてあるか。顧客向けなら、個人名・社内の事情・利用額・社内資料の名前・社外秘の情報が入っていないか。外に出す資料に、出典の揺れや確かめていないことを見せる言い方（「docs のページで違う」「docs にない」「実測する」）がないか（content.md の 5）。
4. 言葉: 空疎な言い回し、表記ゆれ、略語の初出、道具・エージェントの名前が聞き手の使う製品の名前か、文体の混在（顧客向けは です・ます。引用は元のまま）、長すぎる一文、主語と述語のねじれ、受け身と「〜することができる」の重なり、箇条書きにしたせいで理由や条件が抜けた文、太字の使いすぎ、読み手が知らない社内の言葉。
5. Visuals: table column widths and wrapping (cells where a single character drops to the next line, columns that are too narrow), long sentences inside tables, tables or figures split across pages and separated from their titles, figure size and resolution (blurry, or text too small to read), the font of text inside figures, uneven spacing before and after paragraphs and headings, headings left at the bottom of a page, pages with a large empty space at the bottom, 「行頭の約物」「1〜2 字だけの最終行」, overflow into the margins, meaningless decoration (color, lines, icons), and missing logos and icons in architecture diagrams (the same idea as visual.md §6).
   Judge the finished look from these images. For items listed under 「要確認（画像で測った）」 by docs.py check, also check on the image whether they really occur.
   In the contact sheet, check only cross-page matters: uneven density between crowded and empty pages, uneven sizes of tables and figures, too long a run of tables of the same shape, the positions of page breaks. Do not read the small text in the contact sheet (read text in the text file and the single-page images).

## How to reply
First, for each image you opened, write one line on what you saw (the headings, tables, and figures).
Then one line per defect: `p<ページ> | <出所: 一覧・画像・テキスト> | <観点 1〜5> | <重さ: 直す／見直す／聞く> | <何が起きているか> | <直し方の案>`. For cross-page items, list the pages like 「p3・p5・p7」.
Finally, up to 3 lines on tendencies worth fixing across the whole material. For an aspect with no defects, write 「なし」.
Write all of the above to <findings file>, and in your reply write only the counts (per severity) and that path. (Only when asking a pi child. For other children, delete this line.)
```

## Reader test (documents only)

Separately from the defect review, check whether a reader can reach the answers from the document alone (step 3 of `SKILL.md`; modeled on Reader Testing in Anthropic's official doc-coauthoring skill; 1-13 of `Research/deck_research/log/20261009_en_gdocs_generation.md` in the workspace). From the outline's 「聞き手の問い」 and 「読んだあと聞き手ができること」, the main agent makes 5–10 questions the reader is likely to have, and keeps the key points of the answers on hand (do not write them in the prompt). Do not pass the rules or the outline. Like the reader, have the child read only the document (the text and the page images) (in a trial on 2026-10-09, the figures were not visible from the text alone).

```text
You are <audience (department, role, technical level)> who received this document. Read only the document and answer the questions below. Do not fill in what the document does not say with guesses; answer 「書いていない」.

## What to read
- Document: <text path> (headings are #, a table row is its cells joined with 「 | 」, links are [text](URL))
- Document pages: p-* in <image folder> (see how figures and tables look here)

## Questions
1. <question>
2. <question>

## How to reply
For each question, one line with the answer and the section (heading) it is based on.
Then list, one per line, places that were hard to follow, places that needed unknown words or background knowledge, and places where sections contradict each other.
```

Put the section for any question whose answer differs from your notes, or that came back 「書いていない」, into the findings table (「出所」 is 「読み手テスト」, 「観点」 is 1 or 3). If what is missing is content (a claim, number, or section), mark it 「聞く」.
