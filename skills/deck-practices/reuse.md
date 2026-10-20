# Reusing internal materials

[reuse-001] Read this when you use pages from internal decks. The four stages are a flow that worked. Try them from the top, in order. First check "Checks at every stage".

The scripts are in `../deck-build/scripts/`. `gslides.py` does not write to the source deck (`keep` makes a copy and then changes it). `gapi.py` takes care of authentication (the environment variable `GOOGLE_OAUTH_ACCESS_TOKEN`, or the gcloud ADC file; it also adds the quota project header). On 401 or 403, check with factory-doctor.

```sh
G=<deck-build folder>/scripts   # ../deck-build/scripts from this skill's folder
python3 $G/gslides.py pages  <URL>                                  # list of page numbers and the first text on each
python3 $G/gslides.py thumb  <URL> <page> /tmp/<src>_p<N>.png        # 1600 × 900 image drawn by Google
python3 $G/gslides.py export <URL> /tmp/<src>.pptx                   # export as pptx (to extract the original images); also prints the name and last updated date
python3 $G/gslides.py keep   <URL> <AI Deck Factory folder> <YYYYMMDD_資料名_差し替え用> <page ...>   # copy, and keep only the pages you use
python3 $G/gslides.py jp     <copy URL> /tmp/<translations>.json     # insert translations ([["英語", "日本語"], …]) and set the font to Noto Sans JP
```

The page elements (type, position, size, text) can be read directly with the Slides API `presentations.get` (the JSON that `gslides.py check` writes to `/tmp/slides_<first 8 chars of the ID>/`; used in Stage 3). Do not keep copies; manage URLs in `references.md` (materials.md "Ledger"). Exported pptx files and images are working files in `/tmp`; delete them when you are done.

## Contents

1. Search
2. Checks at every stage
3. Four stages
4. What to write in the outline
5. Checks at the finish

## 1. Search

- Before searching, look at `references_index.md` at the top of the working folder (the overall index of materials used before) and `references.md` in the material's folder. If you have seen a material before, reread it from that URL and page (if the source's last updated date is newer than the date you checked it, also check whether the content has changed).
- Search with the internal cross search, and check the contents in file storage, chat, and the wiki ([materials.md](materials.md) "Internal materials"). Add every material you looked at to `references.md`, including ones you decided not to use. To read the contents of Google Slides, having the internal search tool summarize it fails less often than WebFetch （社内 6）. To choose pages, look with `gslides.py pages` and `thumb`.
- [reuse-002] **For pages that depict the product's main feature (architecture and so on), search for a good-looking figure before drawing your own.** Look at internal decks other than the product pitch and Field Kit, figures in the docs, and figures in the official blog and product pages, and use them in Stages 1–3. Do not settle for a self-made box diagram that only gets the meaning across.
- **Search for a Japanese version first.** Pages of global decks have often been put into Japanese by Japan SMEs (for example, the list of Japanese materials in the internal wiki). If a Japanese version exists, use it instead of translating (SIEM example).
- When the same figure appears in several decks, choose the newest version of the product team's source deck (Pitch Deck, Field Kit, and so on). If there is a list of official internal decks, write it in the workspace's `rules/deck-practices/reuse.md`.

## 2. Checks at every stage

- [reuse-003] **Can it go outside the company** (customer-facing, community-facing)? Do not use pages with an Internal Only, Confidential, or 「社外秘」 label, a roadmap, the names or logos of customers that are not public, or numbers without public backing. If only the numbers can be re-sourced from a public source, use Stage 3 or 4 (in the SIEM example, numbers without backing were not used). For internal materials you may use them, but write 「Internal Only」 on that page (AGENTS.md). A video shared internally (demo, product introduction) may be shown to the customer if the same video is published in a public place such as YouTube or the company's own site. Use the public URL as the source, and write the internal Drive URL only in the outline and the internal memo. If you cannot find a public copy, do not show it.
- [reuse-004] **Is it current?** Look at the source deck's last updated date. Check the release stage (GA, Preview, and so on) against the current state in the docs. Do not use screenshots of old screens. Also do not use screens with trial names (test and so on) or hand-drawn marks baked in; if the content is a structure (such as a catalog tree), redraw it with shapes. That needs no re-shooting and is easy to fix.
- **聞き手に合うか。** 社内のピッチ資料は営業色が強いことが多い。主語が自社の売り込みのページは、顧客の IT 部門などにはそのまま使わない（段階 3 か 4 で、聞き手の問いから書き直す）。AGENTS.md の「いい資料の考え方」に合わせる。
- **Is the message the same?** Check that the heading and the claim (the assertion or the lead) of that page in the outline say the same thing as the source page. If not, that stage cannot be used.
- [reuse-005] **製品のメッセージの柱にそろえる。** まとめや提案の要素の並べ方は、社内と公開の製品のメッセージの柱にそろえる（柱の例はワークスペースの `rules/deck-practices/reuse.md`）。訳語は公開の日本語版に合わせ、柱は「<自社> の整理」と出典を付けて引く。社内の資料にある強い言い方（業界唯一、ロックインなし、知能はもう十分）は使わず、「乗り換え」のように聞き手のいまの基盤を否定して聞こえる言い方は「足す・替える」にする。

## 3. Four stages

### Stage 1: Use the page as is (change only the font and language)

**When to use:** the whole page meets everything in §2, and only the font and language (translation) need to change. If you use only the figure, use Stage 2.

1. If a Japanese version exists, use that page of the source deck (do not translate). Go to step 5.
2. For an English page, use `gslides.py keep` to make a copy with only that page (the replacement copy) directly under the AI Deck Factory folder (My Drive; the URL is `drive.factory` in `factory.toml`; do not put it in the template's Templates). Name it `<YYYYMMDD_資料名>_差し替え用`. Do not make it in the customer's folder (the copy's version history keeps every page of the source deck, and anyone who can edit can restore them; in the earlier method too, replacement copies were kept only locally).
3. Write the translations as JSON `[["英語の文", "日本語の文"], …]` and insert them with `gslides.py jp` (text formatting stays as is; the font becomes Noto Sans JP). Keep product names as their official English names, and match terms to internal Japanese materials and the Japanese version of the product's official docs (「書き方」 in AGENTS.md). Write replacements at the sentence level (a short word also matches other places).
4. Render it with `gslides.py check <replacement copy URL>` and check that the translated text does not overflow its boxes. Do not change the text size or placement of the source page (when the name contains 「差し替え用」, lint skips the 11pt minimum and the cover).
5. In the main deck, paste that page's image over the full slide. JSON pages cannot do this (components can only go inside the body frame, and page image URLs expire in 30 minutes, so fetch them again with `thumb_url` on every build). So write only this page as a pages.py function (write pages.py without a `deck.json`, and call the JSON pages in order with `d.spec` inside `make`; `../deck-build/slides.md` §2, "Pages the JSON components cannot express"). With `s = d.slide(foot=False)`, make a page with no footer and no page number, then `d.image(s, thumb_url(<URL>, <page>), 0, 0, 13.333, 7.5)` (when you translated, the first page of the replacement copy's URL; when you use the Japanese version as is, the source URL and page). Do not add a tag. Write speaker notes in Japanese. Write the replacement copy's URL in the outline's 「流用元」.
6. [reuse-006] Leave no pages waiting for replacement. People receive it as a Drive URL, and nobody replaces pages (`../deck-build/SKILL.md` "Deliverables"). To fix text, fix the replacement copy and rebuild the main deck (`slides.py build`; it fetches the image again). lint stops with `要修正` if a 「差し替え：」 tag remains.

If you find a typo on the source page, fix it in the replacement copy and note it in the outline.

### Stage 2: Crop figures and similar parts

[reuse-007] **When to use:** the figure (architecture diagram, product screen, chart) fits, but the rest of the page (heading, text, arrangement) does not. Limit this to figures whose text the audience understands as is (product names, or cases where an English figure is fine). Limit it to figures that depict the page's claim (the heading and the body items) as it stands. When the figure depicts only part of the claim (example: a figure of only the login flow on a page about four layers of defense), or the figure's numbers and the body's numbers do not line up, redraw it in Stage 3 or 4 (the figure and the claim do not match, which is confusing).

1. For a figure embedded in the source deck as an image, use the original image file. Export the pptx to `/tmp` with `gslides.py export`, find `media/` with `unzip -p /tmp/<src>.pptx ppt/slides/_rels/slide<N>.xml.rels`, and extract it to `build/assets/` with `unzip -j`. The resolution does not drop.
2. For a figure built from shapes, crop it from the `thumb` image (`/tmp`): `sips -c <height> <width> --cropOffset <top> <left> <input.png> --out <output.png>` (px; top comes first). Cut off the source page's title band, page number, and copyright notice.
3. Put the image in `build/assets/` and paste it with JSON `image` (`{"type": "image", "src": "assets/<name>.png"}`; the path is relative to the page file) (`../deck-build/slides.md` §2, "Images"). Paste it on a page in this folder's style, and write the heading, lead, and source line in Japanese. Do not change the aspect ratio.
4. Do not paste it smaller than on the source page. The `thumb` image is 120 px per inch, so the pasted width (in) must be at least the cropped width (px) ÷ 120. Shrinking makes the text in the figure smaller than the original, and lint cannot detect it. If it does not fit, crop the figure tighter or use Stage 3.

Text inside an image cannot be corrected or translated （AI 実践 1-8）. When an English figure needs a reading guide, add a panel with the Japanese reading next to the figure (AWS SA example). If there are typos, or it needs fixing in Japanese, use Stage 1 or 3.

### Stage 3: Keep the layout and rebuild in this folder's style

**When to use:** the composition (arrangement, flow, comparison) fits, but translation alone is not enough. For example: updating numbers, changing the wording for the audience, removing the sales tone, or making the text in the figure fixable in Japanese.

1. Read the structure of the source page. From the element list of `presentations.get` (the JSON from `gslides.py check`, or the XML of the exported pptx) and the `thumb` image, write out for each element its role (heading, card, arrow, icon, label), arrangement (how many columns and rows, in which order it reads), and groupings （研究 1-5）.
2. Map it to the diagram patterns and the page-pattern functions in visual.md, and rebuild it with this folder's colors, fonts, and margins. Do not copy the coordinates as is (the page area and margins differ). Keep the arrangement, reading order, and groupings.
3. Take icons and logos in this order: those that can be pasted by URL (Iconify and so on), the top-level `assets/`, and images from the source deck (the extraction in Stage 2 step 1) (sources are in `../deck-build/assets/README.md`; how to paste is in `../deck-build/slides.md` §6).

### Stage 4: Take only the intent and make it new

**When to use:** none of Stages 1–3 fits. For example: the audience or the question differs, the page is old, it cannot go outside the company, or the sales tone is too strong.

Borrow only the source page's message, line of argument, and terms and phrasing (messaging). Make it new following content.md and visual.md. Re-source the numbers from public sources.

## 4. What to write in the outline

In 「流用元」 at the end of `構成案.md`, write one row per page.

| 本編のページ | 流用元（資料名・URL・ページ・更新日） | 段階 | したこと | 社外に出せるか（確かめ方） |
|---|---|---|---|---|

- Stage 4 may go in a separate bullet list as 「考え方を借りたもの」 (SIEM example).
- In customer-facing materials, write the names and URLs of internal materials only in the outline and the internal memo. Do not write them in the slide's source line or notes (write a public source or the company's own name).
- When finished, add the materials you used to `references_index.md`. As the point of view, note in a few words which stage you used and why (examples: 「日本語版があり段階 1 で差し替え」「英語の図を段階 2 で画像に。読み方のパネルを足した」).
- If more than half of the main deck's pages would come from one internal deck via Stage 1, ask the user before rebuilding. Copying that deck in Google Slides and editing it can be faster.

## 5. Checks at the finish

- lint's 「差し替えの仮ページ」 (leftover tags) is 0. The Stage 1 rows in the outline's 「流用元」 match the pages where images were pasted.
- For customer-facing materials, lint's 「社外秘の表示」 is 0.
- Stage 2 images have no leftover source title band, page number, copyright notice, or typos.
- In Stage 1 replacement copies, the translated text does not overflow its boxes.
- Stage 3 and 4 pages go through the same lint and review (`../deck-review/SKILL.md`) as the other pages.
