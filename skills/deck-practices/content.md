# Content: the outline and writing one page

Read this before writing the outline. §0 covers what is the same for every material (the user's iron rule and six principles; a detailed version of 「いい資料の考え方」 in AGENTS.md). §1 onward covers what differs by material type, in forms you can check while making the material. It also applies to documents (Google Docs). The look of documents is in `../docs-build/visual.md`.

## Contents

0. Same for every material
1. What changes by material type
2. Vary the depth of alignment by situation
3. Order of work
4. Headings
5. Content of one page
6. Wording
7. Checks for the outline and the finish
8. References

## 0. Same for every material

鉄則は「営業色を出さずに、お客様の目線で情報を整理するところから入る。課題や問題意識について目線をそろえることは、提案の中身より重要」。これを、作りながら確かめられる形に直したのがこの節。顧客向けの提案だけでなく、社内向けの資料にも、顧客も来るコミュニティ向けの技術資料にも当てはめる。AGENTS.md の「いい資料の考え方」は、この節の要点（どの会話でも見えるように、そちらにも置いてある）。

1. **主役は聞き手。** 聞き手の状況と問いから始め、自社や機能の紹介から始めない。見出しの主語は、聞き手の業務・データ・判断・つまずきにする。製品は、問いに答える手段としてあとで出す。
2. **問いを先にそろえる。** 中身に入る前に、なぜこの話なのか、何が問題なのかを聞き手と共有する。問いは聞き手が実際に持っているものを拾い、出典を控える（顧客なら会議の記録と社内のチャット、社内ならチャットに来る質問、コミュニティなら GitHub の Issue やよくある質問、自分たちで試した経験）。こちらの見立てには「仮説」と書く。聞き手が言っていないことを、言ったように書かない。
3. **課題は影響まで書く。煽らない。** 「何に困っているか」だけでなく、それで何が起きるか（時間、コスト、リスク、逃す機会）まで書く。変える価値があるかどうかは、影響を見て決まる。数字は出典のあるものだけを使う。「このままでは〜」「乗り遅れる」のように不安をあおる言い方はしない。決めかねている相手には逆効果になる。
4. **聞き手の見方をなぞるだけにしない。** 聞き手の目線に立つことは、聞き手の言い分を繰り返すことではない。聞き手がまだ持っていない見方（論点の整理、比べ方、見落としやすいリスク）を足すのが SA の仕事。ただし、その見方が特定の製品でしか答えられない形になってはいけない。
5. **公平に書く。** 他社の製品や OSS、今の仕組みでできることは、できると書く。重なるところは重なると言う。自社の製品の向かないところや、プレビューのところも書く。問いと課題を整理したページは、結論が自社の製品にならなかったとしても聞き手の役に立つ内容にする。売るための前振りに見えたら逆効果。
6. **見解ははっきり言う。** 選択肢を並べて終わらせない。推奨か使い分け（「〜なら A、〜なら B」）を、理由と一緒に書く。比べる軸と選択肢は絞る（情報を増やすより、判断を整理する手伝いのほうが役に立つ）。

## 1. What changes by material type

[deck-content-001] **Every type**
- 聞き手は、顧客もクラウドベンダー（AWS や Google Cloud の SA など）も、自社の製品の個々の機能はほとんど知らない前提で書く。機能の名前と提供段階を出しただけで通じるとは考えない。
- [deck-content-002] When you talk about a feature the audience does not know, spend 1–2 pages on how it works and what it looks like once they start using it (what they build, where it appears, how it looks; the steps). Put speed, billing, constraints, and where to use it after that. Stop at 1–2 pages. When introducing a product family together, stop at the overall mechanism and a map of the products, and skip the per-product step pages or move them to the Appendix. Do not drift from the chapter's claim. Before going into per-service topics (comparison, choosing between them, constraints), put one entry page that lets a first-time viewer understand what the service is (what it does, what it connects to, the steps to start). Example: in an internal study-session material, Lakehouse Federation (architecture diagram and 3-step procedure → why it tends to get slow and expensive → use it as the entry point, and move repeated queries to ingestion). Do not build the entry page from text cards only; show it with a figure of what it connects to and icons of the product and the things it connects to (the more beginner-oriented, the more approachability comes first). Do not put comparisons or constraints such as 「〜の互換はない」 on the entry page; move them to the comparison pages. How to write it when the recommendation in a customer-facing proposal is a product is deck-content-005 in [content_customer.md](content_customer.md).
- [deck-content-045] For features and mechanisms the audience sees for the first time, do not explain with text and tables only; add a path diagram or a mechanism diagram (more pages are fine). Turn comparison tables and text-heavy pages into figures too (stacked layers, flow, positions on a line between two ends, two figures of the same shape side by side for mapping), and move the text to `authorNotes`. Pages that list bullets in numbered steps (vertical or horizontal step cards) do not count as figures here. For checking mechanisms and flowing mechanisms, draw the things (inputs, intermediate tables, outputs) as boxes, write on the arrows who checks between which, and draw the unchecked gaps with dotted lines too. "Why it is needed" problem pages (scenes and pain points) also must not end as a row of text cards: make them a table that marks with circles which clues (what you need to trace the cause) correspond to which scene, or a figure of an example with aligned timestamps, and add icons and the impact (an example with a source) to each scene. When talking about an implementation example, add one concrete example (how to write a policy, a setting value, and so on). When specialist terms the audience will not understand are needed (such as networking terms in a material for sales), replace them with an analogy, and add before the steps a path diagram that lays out what connects and what does not. Text rules alone did not produce figures, and figures were often requested afterwards (checked by review aspect 1).
- [deck-content-004] When you add a chapter for a different audience to one material (example: a 「迷ったらこれ」 chapter for sales at the start of an analysis for yourself), write it so that reading only that chapter is enough. Replace the other chapters' terms and ways of stating numbers (「2 pt」「勝率」「段」 and so on) with words that audience understands. For the evidence, do not write 「2 章を参照」; point directly to the pages with the supporting numbers (example: 「p.7（長い作業）・p.8（1 回で答える作業）」). Check that the chapter's recommendation does not contradict the other chapters' recommendations, down to the scope of 「〜だけ」 in the headings. Check the audience's tool settings (default values, how to change them) in that audience's tool before writing them, and write 「確かめていない」 for anything not checked. Show which chapter is for whom with the cover subtitle and the section dividers.
- [deck-content-009] ユーザー以外に共有する資料では、ユーザーが個人で使っている道具（T3 Code など）の名前を出さない。読み手が使う道具（pi・Claude Code・Codex など）の言葉で書き、要るときは「Codex 向けのサードパーティのツール」のように一般化する。ただし、SA の勉強会のような比較的くだけた会の資料では、実例として出してよい（実例があるほうが分かりやすい）。
- **Explanation and evidence in materials meant to be read:** For materials sent by email or chat and read on their own, limit the main part to short claims, figures, and the evidence needed for the decision. Put detailed explanation, conditions, and sources in the Appendix, and point to them from the main part. Check it by asking whether the recipient could explain it to their own manager without the speaker talking. Do not leave evidence needed for the decision only in `authorNotes`. Even when you cut text, keep the explanation needed to read the meaning of the figures and the conclusion （中身 1-10）.

Then open the files for this material (read only those that apply; the rules in them are part of §1):

| Material | File |
|---|---|
| Customer-facing proposals and explanations (proposals, PoC plans, explanations to IT departments or executives) | [content_customer.md](content_customer.md) |
| Internal (study sessions, enablement, account status summaries) | [content_internal.md](content_internal.md) |
| Explains a tool or a mechanism, reports research or an investigation (including industry trends), recommends a protection such as isolation or a sandbox, explains an article, a talk, or a release, or guides setup or usage (any audience, including community-facing) | [content_explain.md](content_explain.md), in addition to the audience's file |
| Community-facing technical materials | below (no audience file) |

**Community-facing technical materials** (meetups, OSS study sessions, talks that customers also attend)
- 聞き手の問い: 自分の課題にどう効くか、本当に動くか、何が難しいか。
- 冒頭で、何の話か、何を持ち帰れるかを言う。そのあとは「問題 → なぜ難しいか → 試したこと（失敗も）→ 分かったこと → 使い分け」と話を進めてよく、結論は最後でよい。コード、デモ、測った数字で見せる。
- 営業色はいちばん強く抜く。製品は実装の 1 つとして、OSS やほかの選択肢と並べる。会社と製品の紹介は、自己紹介か最後の 1 枚まで。購入や問い合わせには誘導しない。多くのカンファレンスは CFP で製品の宣伝を禁じているので、イベントの登壇の決まりを先に読む。
- Use only public information. For customer cases, confirm the customer's consent and the scope that may be made public. Do not show roadmaps.
- 聞き手が明日取る行動から逆算する。話さないことを先に決める。苦労と回避策を入れ、成功談だけにしない。冒頭で、聞き手の技術水準も言う。1 枚の文字は 5 行以内（中身 1-13）。

## 2. Vary the depth of alignment by situation

| 場面 | 目線合わせ |
|---|---|
| 初めて扱うテーマ、聞き手の問いがまだはっきりしない | 厚くする。前半を、聞き手の状況・課題・問いの整理にあてる。顧客向けなら、相手に確かめる問いを入れる |
| 前回までに課題を合意できている、聞き手が前提をよく知っている | 合意したことや前提を 1 枚（ドキュメントなら 1 段落）で振り返り、すぐ本題に入る |
| RFP、質問票、技術的な問い合わせへの回答 | 入れない。聞かれたことに直接答える |
| 時間が短い（役員への説明、LT） | 問いは 1 枚で見せ、答えは 1 つに絞る。詳細は Appendix に回す |

[deck-content-015] **Materials for talks such as LTs, when the content is new to the audience**
- One message per page. State it firmly in the lead (the heading on assertion pages), and show the body as a figure, or as large numbers and short words. The body is at most 5 lines (125 characters) （中身 1-13）. `gslides.py check <URL> --talk` reports pages over the limit as `要確認`.
- Do not put file names, paths, commands, or step details on the page; move them to the Appendix. Before the name of the mechanism, show what happens from the audience's point of view (what you ask for and what comes out).
- [deck-content-016] Only on pages where the user asked for a technical deep dive may file names and script names appear. Those pages also show their role with a kicker (「深掘り: …」), and still keep one message per page and the character limit.
- Do not apply this to materials meant to be read (circulated or sent by email). Those follow "Explanation and evidence in materials meant to be read" in §1.

## 3. Order of work

[deck-content-039] At the top of the outline, write four things: the material type (customer-facing, internal, community-facing), the audience (department and role, technical level), the audience's questions (with sources), and what the audience can do or decide after reading or listening. Even if you can write them, confirm them with the user before starting to make the material (step 5 in [start.md](start.md)). For materials that introduce a mechanism or an effort (a mechanism we built ourselves, an LT on a team's effort, and so on), also ask for the builder's intent (what they wanted to build), where they put effort, and what they want next (whom they want to spread it to). Building from a description of the finished thing makes the theme and the landing drift apart.

- Decide in this order: the action you want the audience to take → what state the audience is in at that time → the audience's expectations and knowledge → the claim and the 3–4 points that support it → the skeleton (page numbers, headings, summaries) → figures and tables. **Do not start from figures and tables** （中身 1-7）.
- Put the claim and points down first as hypotheses, and write in the outline whether each has support. Fix weakly supported points or write 「仮説」 for them （中身 1-7）.
- 構成案の「聞き手」の欄に、聞き手の型を書く。結果を見るか過程を見るか、自分で決めるかほかの人の意見で決まるか。過程を見て自分で決める人には、最小限の中身と、見方を揺さぶるデータ。ほかの人の意見で決まる人には、事例とほかの判断者の根拠（中身 1-8、書評経由）。
- Decide whether to make a material to be read or a material to be shown by how it will be used. Materials sent by email or circulated internally are written so that they can be read and decided on alone. If prose is enough, make it a document (Google Docs) （中身 1-10）.

## 4. Headings

- [deck-content-041] **本文のページの見出しは、短い名詞句にする。言い切りの文にするのは、判断を頼むページと数字の結論のページの 2〜3 枚だけ。** 名詞句は、そのページだけの話が分かる形にする（「問い合わせの一次回答の推移」。「現状」「課題」「まとめ」のような、どの資料にも付く項目名にしない）。主語は聞き手の業務・データ・判断にする（AGENTS.md）。名詞句の見出しのページでは、言えること（だから何か）をリードか本文か結論バンドで言う。言い切りのページは、構成案の型の欄に「言い切り」と書く（SKILL.md の 5）。全ページを主張の文にすると、どのページも同じ強さで言い切って要の主張が埋もれ、見出しが長くなる。主張の文の見出し（中身 1-1）は、聞き手に判断を頼むところと数字で言えるところに絞る。文末と句点は 6 の「文体」。
- [deck-content-017] **定例のたびに使う資料（スケジュール、進捗の一覧など）は、ページの見出しを回ごとに変えない。** 「プロジェクトスケジュール 1/2　ML とデータ基盤」のように、資料の名前と範囲で決め、その回の要点（何が増えたか、次の一歩）は口頭で話す。毎回同じ見出しなので、画面で同じページを探しやすい。
- 見出しとリード（言い切りのページは見出し）で、次の 3 つの問いのどれかに答える。本当か（事実と数字）、だから何か（意味）、どうするか（打ち手）（中身 1-2）。
- 1 行に収める（`../slides-build/visual.md` の 1）。本文幅・24pt で全角 35 字ほどまで。目安は 25〜35 字。lint が「2 行の見込み」を出したら、削るか言い換える（中身 1-2）。
- 図表のタイトル（何のデータか。例: 地域別の売上の推移）と、そこから言えること（リードか、言い切りの見出し）を分ける（中身 1-3）。
- [deck-content-018] 見出しの範囲と数の言葉（「だけ」「すべて」「N つ」「割れている」など）は、そのページの表・図の行や項目と突き合わせる。表に例外の行がある、数が合わない、片方の側の例しかない、なら見出しの範囲を絞る（例:「type のほかはすべて省いてよい」→「ふつうの概念では、type のほかは省いてよい」）。
- 結論バンドは、要るページにだけ置く（`../slides-build/visual.md` の 1）。置くときは見出しやリードの言い換えにしない。見出しかリードが「何が言えるか」なら、結論バンドは「だから何をするか」か、決めてほしいことにする（中身 2 節）。
- [deck-content-019] 表紙の副題・説明・図は、本編を改訂したら合わせて直す。表紙に出す製品名は、聞き手のいまの環境と会話に出ているものだけにする（例: 聞き手が使っていない他社の製品を表紙に出さない）。本編の比較には、公平さのために入れてよい。

## 5. Content of one page

- 事実を並べたページには、「だから何か」を 1 文足す。課題や懸念を出したら、対応を同じページか次のページに置く（中身 1-4）。
- 「十分」「限定的」「大幅に」のような評価語は、そのページに裏づけがあるときだけ使う（中身 1-3）。
- [deck-content-020] 時代や業界の流れを主張にするとき（例: AI エージェントの時代は〜）は、Web で中立の出典（調査会社、他社の発表）を確かめ、言える範囲に直してから書く。予測を現在形で言い切らず、反対の見方（失敗の予測など）は `authorNotes` に残す。出典は自社だけにしない。予測は、予測と分かる形で 1 枚にまとめてよい（注意の予測も並べる。話すときに飛ばせるので、枚数が増えてよい）。
- [deck-content-021] 相手のデータや環境を確かめていないうちに「できる」「作れる」と答えるときは、何次第か（どのデータが取れているか、意味の分からない ID など）を、見出しかリードと、冒頭の要約の文に書く。条件を後ろのページや前提の列にだけ置かない。レビューの観点 2（見出しの範囲）で見る。
- [deck-content-022] 「〜から逆算して選ぶ」と推奨するときは、要素（意味・権限・ガバナンスなど、要る機能）で逆算し、使う道具やエージェントは入れ替わる前提にする。流行りの道具が出るたびに製品を乗り換える話に読めないようにする。道具が替わっても効く強み（公開仕様の形式など）は、その前提とつなげて書く。
- [deck-content-023] 比べるときは、相手（他社の製品・OSS・今の仕組み）が勝つ軸も入れる。相手の道具や機能（例: AWS の Agent Skills）は、ないと決めつけず、確かめてから書く。相手にも同じ道具があるなら、それを書いたうえで、違いはその先（例: 関連するリソースが多く、IaC を介して組む）で書く。自社の数値には測った条件を注記する。相手にしかない機能（例: ブラウザの操作）は、結論で「相手も比べる」とぼかさず、「その部分は相手を使う」と勧める。成熟度の差（GA の部品の多さなど）は、表のステージで比べられるようにして「比べる」でよい。0 の 5「公平に書く」の具体（中身 2 節）。
- [deck-content-060] 接続・認証・API の出し方などで推奨の方式を描くときは、選べるほかの方式（トークンとパスワードなど）を、違い（期限・管理・使える機能）と使い分けとあわせて 1 枚で書き、推奨の理由（安全の面など）も書く。推奨の方式だけを描くと、聞き手がほかの選択肢を知らないままになる（0 の 5・6）。
- 数字は、起点と比べる先を書く（「前年比」「9 月時点」「割引後」）。数字が概算なら概算と書く（中身 1-9）。
- [deck-content-024] 出典の中で値が食い違うとき（docs のページの間、事例のページの見出しの数字と本文）は、強いほうの値だけを見出しや大きな数字にしない。どの出典とも食い違わない安全な側で言い切るか（数百ミリ秒と数秒なら「数秒以内」）、本文の値で書き、見出し・大きな数字・表と、ほかのページの同じ数字を同じ言い方にそろえる。食い違いは構成案の出典の表に書き、資料には書かない。外に出す資料（顧客・パートナー向け）に「docs のページで違う」「docs にない」「実測する」のような、出典の揺れや確かめていないことを見せる言い方を書かない。言える範囲を言い切り、言えないことは言わない。
- [deck-content-025] When writing prices, context window sizes, or performance of LLM models, check them against each vendor's latest generation (example: as of 2026-10, GPT is the 6 series and Claude is the 5.5 series). Check the latest generation in the local model list (`~/.pi/agent/models.json` or the internal gateway's endpoints) and each vendor's official price list; when you write values of an earlier generation, write them so it is clear they are the earlier generation. Prices in internal guides (Confluence and so on) can be old, so recheck them against the official tables. In tables and trials that compare models, do not drop each vendor's latest flagship models (as of 2026-10, GPT-6.1 Sol, Claude Opus 5.5 and Sonnet 5.5) from the comparison. Do not let only a cheap model (Luna, Haiku, and so on) represent that vendor.
- [deck-content-026] Pages that measure or test with models (token counts, response seconds, summary quality, and so on) measure with the model the user mainly uses. Add other models as comparisons. Ask which one is the main model during the check before making the material, and write it in the outline's assumptions.
- [deck-content-027] For a product's available regions, processing location, and release stage, read the legend of the symbols in the docs tables (⥂, ‡, and so on) and the original footnotes, and write within that scope. Do not rephrase by adding conditions or consequences, such as turning 「cross-Geo の設定が要る」 into 「国外で処理される」. Write conditional statements (「when you disable cross-Geo processing」) together with their conditions.
- [deck-content-028] When proposing an overseas region for a feature not available in Tokyo, do not choose by proximity. Propose a region where every feature you use is available in the docs' per-region availability table (usually US), and cite the table you checked as the source.
- Decks over 10 pages show the current position on an overall map at the head of each chapter. Pick up every point marked 「後で話す」 later in the material （中身 1-5）.
- 終わりは要約で締めず、次の一歩の 1 枚にする。顧客向けなら、決めてほしいこと、小さく始める範囲・期間、続けるかを決める基準（中身 2 節）。
- The main part is about 5–9 pages. Put answers to expected questions in the Appendix （中身 1-6）.
- [deck-content-029] Pages the speaker decided to "cover orally" are not deleted; make them pages shown while talking. Keep only the heading and the main points (about 3 steps), and move what is said to `authorNotes`.
- [deck-content-030] Do not put the same table in both the main part and the Appendix. Limit the main part to figures and decisions, put detailed lists in the Appendix, and point to them from the main part. The same goes for lists of commands, APIs, and setting items: put only the flow (a 3-step procedure and so on) and one example in the main part, move the list to the Appendix, and point to it from the main part.
- [deck-content-031] When you add topics, periods, or targets and show the same comparison again, also add the figures from the earlier part (bar charts and so on) in the same form. Do not settle for a table only.
- [deck-content-032] In materials that compare several topics, parts, or periods, write what each topic is (subject, audience, length, conditions) on the page where the topic's name first appears (the conclusion or the comparison method), and put a section divider for each topic. Also put a divider before summaries that span topics (what cannot be said, next steps). Do not call them only by numbers such as 「1 題目」「2 題目」.
- [deck-content-061] In materials asked to examine two or more axes (time and cost, and so on), cover every axis with the same depth. For time, put not only the total per step but also a breakdown of step × kind of time (model, waiting for child agents, building, waiting for people) and a single timeline band (`../slides-build/visual.md` slides-visual-045). Leaning toward the details of one axis makes the overall breakdown unreadable.
- **Speaker notes:** Do not write `speakerNotes` unless the user asks for them.

## 6. Wording

- **文体:** 書くところで分ける。和欧間のスペースと製品名の書き方は AGENTS.md の「書き方」。
  - 見出し: 表紙の題・章の扉・図表のタイトル・カードや表の項目名と、本文のページの見出し（4）は、短い名詞句（体言止め）。言い切りにする 2〜3 枚の見出しと、名詞句の見出しのページのリードは、主語と述語のある常体の文で言い切る（「問い合わせの一次回答が 3 割減っている」「夜間の集計を新しい基盤に移す」）。言えることを体言止めにすると、誰がするのか、予測なのか意志なのかが消える。「だ」「である」で終える必要はない。見出しに句点を付けず、「〜ください」「〜します」で終えない。頼みごとはリードか本文で言う（lint が「見出しの句点」「見出しが「ください・します」で終わる」を要修正、「言い切りの見出しが多い」を要確認に出す）。
  - 箇条書きと図のラベル: 体言止めでよい。ひとまとまり（1 つの箱の箇条書き、1 つの図のラベル、見出しの並び）の中では、文末（体言止め・常体・敬体）と句点の有無をそろえる（lint が「箇条書きの句点の混在」）。名詞だけで終えない（下の「箇条書きを名詞だけで終えない」）。
  - 本文: 敬体か常体のどちらかにそろえる。スライドは常体か体言止めにする。スライドの です・ます は、案内・依頼・注意書きのページ（問い合わせ先、アンケートのお願い、「ご相談ください」、免責・価格の注記）では残してよい（lint の「スライドに です・ます」は、それ以外のページに出たものを直す）。
  - 顧客向けのドキュメントは です・ます調。社内メモは だ・である調でよい。
- When making the material in English, use sentence case for headings.
- [deck-content-033] **Sources:** Attach a source to every number (on slides, the source line at the bottom of the page; in documents, a footnote or parentheses in the body). Give every blog, talk, doc, or study cited as a source a link to the original page, so that it can be reached from the page that cites it. Do not put links only in the source list in the Appendix (lint reports source lines without links). For customer-facing materials, attach only public URLs, and do not cite meetings with the customer as sources (「社外秘と顧客の情報」 in AGENTS.md).
- [deck-content-064] **Facts on pages come from the 「出典の表」.** Put on pages only numbers, availability statements, statements about the customer's environment, and proper nouns that are rows of the 「出典の表」 (columns and kinds: "Ledger" in materials.md). When you need a new one while writing, add the row with its source first, then write the page; do not settle the value on the page and backfill the table. Write a computed value as a `計算` row with the rows it uses and the formula, because computed values were the numbers most often missing from the table. Product facts (`提供・数字・名前`) need a `公式` source or local data: mark them 「済」 only after opening one, and treat a chat, a meeting, an article, or something said in the conversation as a lead, not a source. Write `見立て` rows on the page so that they read as `見立て` or `仮説`. lint reports numbers that are not in the table (`出典の表にない数字`).
- [deck-content-063] プレビューやベータの機能は、提供ステージ（Private Preview・Public Preview・Beta）を書く。「本番向けではない」「本番では使えない」と添えない。どこまで使えるかの判断は聞き手に任せる（本文もノートも、ほかのページも同じ）。スライドのラベルの付け方と、控えるページは `../slides-build/visual.md` の 1。
- 1 つの資料で 1 つのものには 1 つの言葉を使う。最後に表記ゆれを全文で探す。略語は初出で正式名を書く（中身 1-11）。
- [deck-content-034] 道具・エージェントは、聞き手がふだん使っている製品の名前で書く（Claude Code、Codex CLI など）。ACP のアダプターや登録簿の表示名（Claude Agent、Codex など）は、アダプターそのものや登録簿の一覧を指すときだけ使い、そのページで製品の名前との対応を一度書く。レビューの観点 4 で見る。
- [deck-content-062] 道具の画面に出る設定の値（reasoning effort の Low・Medium・High など）は、画面の表記のまま書く。「浅め・ふつう・深め」のような訳語に置き換えない（画面で探せず、意味が通らない）。項目の名前は和訳してよいが、初出に英語の名前を添える（例: 考える深さ〔reasoning effort〕）。
- [deck-content-035] 資料の主題の言葉（タイトルに入れた言葉。例: オープンテーブルフォーマット）は、それを説明するページの見出しか図にそのまま出す。言い換え（テーブル形式・公開仕様）だけにしない。
- 箇条書きを名詞だけで終えない。「強化」ではなく、誰が何をどう変えるかを書く。同じ階層の箇条書きは文末をそろえる（中身 1-11）。体言止めそのものはよい（この節の「文体」）。
- 「実現」「加速」「最適化」「効率化」「強化」「変革」で文を終えない。対象と変化を書く（例:「業務の効率化を実現」ではなく「問い合わせの一次回答を AI に任せ、担当者は個別の対応に回る」）。言い換えられないなら、その項目は要らない。禁句をほかの空疎な語に置き換えるだけにしない（AI 実践 1-6）。lint が候補を出す。
- 「社内」「外部」「既存」のような相対語は、誰から見てかを書く（中身 1-11）。
- 口に出して言える日本語にする。会社名や製品名を入れ替えてもそのまま通る文は、中身がない（見た目 1-9）。
- [deck-content-036] **字を詰めるために語を略さない。** 「〜の組の点」「Grok Build の点は」のように、何の数か・何と何の組み合わせかを略した名詞句にしない。数字は何を測った値か（「端末の作業を解けた割合」）、組み合わせは「〜と〜を組み合わせた成績」と書き、口に出して通じるかで確かめる。短くするなら、文を分けるか、要らない語を消す。レビューの観点 4 で見る。
- Do not fill in facts that are not in the materials (internal operations, product behavior, numbers). Write 「要確認」 for what you do not know, and resolve it before delivery （AI 実践 1-7）.
- [deck-content-037] **Compute numbers from the source data.** Compute totals, averages, ratios, and multiples from the original values (tables, JSON, records); do not add or divide rounded values. Even when a table shows rounded values, compute with the values before rounding (computing with rounded values makes the totals drift).
- [deck-content-038] **When you add a comparison target midway, search all pages again for assertion words.** Search the headings, body, tables, and panels for 「最も」「だけ」「すべて」「どれも」「N 本・N 社・N つ」 and for abbreviated names (such as 「Sonnet」 once there are two of the same model or product), and check that they still hold with the added target (after adding, overstatement and mixed-up names are common).

## 7. Checks for the outline and the finish

- [ ] 枚数や時間を削るときは、製品の説明から削り、目線合わせを残している（2 の表で「すぐ本題に入る」場面は除く）
- [ ] 問いと課題を整理したページに、自社の製品の機能の話が入っていない（聞き手の今の環境として名前が出るのはよい）
- [ ] Features the audience does not know have pages on how they work and what they look like once in use (the steps). They do not end at the name and release stage
- [ ] Every problem item has a source or 「仮説」
- [ ] 見解（推奨か使い分け）がはっきりしている。顧客向けなら、推奨が 1 つで、次の一歩が小さい
- [ ] [deck-content-040] The opening conclusion (summary) page answers every one of the audience's questions in the outline
- [ ] 不安をあおる言い方がない。他社や OSS でもできることを、できないように書いていない
- [ ] For community-facing materials: only public information is used, the company and product introduction fits on the last page, and it follows the event's speaker rules
- [ ] 見出しとリードを順に読んで、紙芝居のように話せる。どの資料にも付く項目名だけの見出しが 0、言い切りの見出しは 2〜3 枚
- [ ] 各ページの本文が、言い切り（見出しかリード）の「なぜそう言えるか」に答えている
- [ ] Pages with figures or tables have all of 「見出し」「データの名前」「出典」
- [ ] キッカーと結論バンドが、要るページにだけある。結論バンドが見出しと同じことを言っていない
- [ ] Every number, availability statement, statement about the customer, and proper noun on the pages is a row of the 「出典の表」 (lint `出典の表にない数字` is 0, or you can say why each one stays), and no row is still `未`
- [ ] 評価語に、そのページの裏づけがある
- [ ] 比較に、相手が勝つ軸がある
- [ ] 最後のページが、次の一歩（決めること・範囲・期間・基準）になっている
- [ ] 表記ゆれがない。略語の初出に正式名がある
- [ ] If a comparison target was added midway, 「最も」「だけ」「N つ」 still hold with the added target

## 8. References

Checked on 2026-10-05: the Pyramid Principle and SCQA (Barbara Minto); the audience as the hero (Nancy Duarte, *Resonate*); in large deals, questions about the impact of problems work (Neil Rackham, *SPIN Selling*); insight that reframes the customer's view (Dixon and Adamson, *The Challenger Sale*); 40–60% of lost deals come from customers failing to decide, pushing harder on the harm of the status quo backfires in 84% of cases, and stating a clear recommendation and lowering risk works (Dixon and McKenna, *The JOLT Effect*, HBR 2022); buyers who receive information that moves their decision forward are 2.8 times as likely to find buying easy (Gartner's 2018 B2B buying survey); identify the question to solve first (安宅和人『イシューからはじめよ』); community conferences often ban product promotion in their CFP (KubeCon + CloudNativeCon, JJUG CCC, CEDEC).

The 2026-10-06 research (mainly Japanese-language sources) is cited by the short names in parentheses in the body. The short names are mapped in the table in SKILL.md.

2026-10-13 に確認（6 の「文体」）: 本文は敬体と常体を混ぜない、見出しは常体か体言止めで句点を付けない、ひとまとまりの箇条書きでは文末を混ぜない（JTF 日本語標準スタイルガイド 第 4.0 版の 1.1、https://www.jtf.jp/pdf/jtf_style_guide.pdf ）、1 つの文書の中で文末を混ぜないが、箇条書きの部分に違う文末が出るのはよい（文化審議会建議「公用文作成の考え方」の解説 Ⅲ-1、https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf ）、体言止めにすると主語が抜けて責任や因果が曖昧になり、予測か意志かも分からなくなる（杉野幹人『超・箇条書き』、https://diamond.jp/articles/-/338937 、https://diamond.jp/articles/-/382251 ）。
