# Content: the outline and writing one page

Read this before writing the outline. §0 covers what is the same for every material (the user's iron rule and six principles; a detailed version of 「いい資料の考え方」 in AGENTS.md). §1 onward covers what differs by material type, in forms you can check while making the material. It also applies to documents (Google Docs). The look of documents is in visual_doc.md.

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

[content-001] **Every type**
- 聞き手は、顧客もクラウドベンダー（AWS や Google Cloud の SA など）も、自社の製品の個々の機能はほとんど知らない前提で書く。機能の名前と提供段階を出しただけで通じるとは考えない。
- [content-002] When you talk about a feature the audience does not know, spend 1–2 pages on how it works and what it looks like once they start using it (what they build, where it appears, how it looks; the steps). Put speed, billing, constraints, and where to use it after that. Stop at 1–2 pages. When introducing a product family together, stop at the overall mechanism and a map of the products, and skip the per-product step pages or move them to the Appendix. Do not drift from the chapter's claim. Before going into per-service topics (comparison, choosing between them, constraints), put one entry page that lets a first-time viewer understand what the service is (what it does, what it connects to, the steps to start). Example: in an internal study-session material, Lakehouse Federation (architecture diagram and 3-step procedure → why it tends to get slow and expensive → use it as the entry point, and move repeated queries to ingestion). Do not build the entry page from text cards only; show it with a figure of what it connects to and icons of the product and the things it connects to (the more beginner-oriented, the more approachability comes first). Do not put comparisons or constraints such as 「〜の互換はない」 on the entry page; move them to the comparison pages. How to write it when the recommendation in a customer-facing proposal is a product is in "Customer-facing proposals and explanations" below.
- [content-043] For technical research reports that people without the background also read (analyses of formulas, thresholds, probabilities, and so on; internal ones too), add explanatory pages at the head of the chapter without changing the main flow or the existing pages. Their contents: a diagram of the mechanism (what comes before what), the input and output for one real data item mapped to the terms, how to read the metrics (logit and so on), how to read the figures (state clearly that they are schematic), and a before/after comparison on an example. Separate them with a section divider. Rewriting the main part in simpler terms breaks the line of reading for people who know the background.
- [content-045] For features and mechanisms the audience sees for the first time, do not explain with text and tables only; add a path diagram or a mechanism diagram (more pages are fine). Turn comparison tables and text-heavy pages into figures too (stacked layers, flow, positions on a line between two ends, two figures of the same shape side by side for mapping), and move the text to the notes. Pages that list bullets in numbered steps (vertical or horizontal step cards) do not count as figures here. For checking mechanisms and flowing mechanisms, draw the things (inputs, intermediate tables, outputs) as boxes, write on the arrows who checks between which, and draw the unchecked gaps with dotted lines too. "Why it is needed" problem pages (scenes and pain points) also must not end as a row of text cards: make them a table that marks with circles which clues (what you need to trace the cause) correspond to which scene, or a figure of an example with aligned timestamps, and add icons and the impact (an example with a source) to each scene. When talking about an implementation example, add one concrete example (how to write a policy, a setting value, and so on). When specialist terms the audience will not understand are needed (such as networking terms in a material for sales), replace them with an analogy, and add before the steps a path diagram that lays out what connects and what does not. Text rules alone did not produce figures, and figures were often requested afterwards (checked by review aspect 1).
- [content-046] In materials that explain how tools, skills, or mechanisms work inside, make at least half of the main pages figures (boxes and arrows for things and actors, branches, time flow, before/after contrast). At the outline stage, decide the figure type for each page before writing. Keep tables and numbered cards only for pages used as lookup lists (tables of arguments and tools, how to read reports). Put first one overall figure of the actors (who holds what and checks what), and draw later figures with the same box names and colors. After a page that explains a procedure or a decision rule (steps, conditions), put one running example (if fictional, write 「模式」), and draw how the input changes at each step, using the same step numbers and box colors as the explanation page. Keep the source of the example as md in the material's folder.
- [content-047] Pages that show how easy a tool or product is (it can be built with an agent, and so on) show real screens from actually having it build something, with measurements (number of instructions, time, cost, code written by people); do not use mock screens. For a demo, start the tool the audience uses, with the same setup as the audience (a folder with the skills installed, and so on) (if you have it read things afterwards, the screens do not reflect the setup). Write separately what the person asked for and what the tool decided.
- [content-048] In materials that explain an article, talk, or release, put a 「取り上げる発表」 page right after the cover (before the question page), showing what the material is based on (medium, author, date, title, a one-line summary, link) and what the material adds (explanation and guesses not in the source). Write the main points of the original in the notes. When proper nouns in the source article (companies, products, teams, earlier products) are new to the audience and matter to the storyline (who built it, what it replaces), do not settle for a footnote: explain on one page or one step of a figure what it is, when, and how it relates. Do not only show the name and write 「同じチーム」 or 「置き換え先」.
- [content-003] Materials that guide through setup or getting started first show on one page what the tool (the official CLI and so on) does automatically and what it does not, and then go into the steps you set up yourself. In an overall setup diagram or list, draw what is created automatically and what you set up yourself (step numbers) so they can be told apart by column names or step-number tags. Do not make a figure where you cannot tell which is which.
- [content-044] Materials that guide people who only use AI tools (agents, material-making tools, and so on), such as sales, include one page on the recommended models and when to use which. State firmly which to choose (normally, when in a hurry, when keeping costs down), and write time, cost, and quality as numbers together with the measurement conditions (topic, page count, number of runs, list price or not). Write the weaknesses of the cheaper models (quality scores, errors) on the same page. Also write how to switch (the action in the conversation, which tools support it). Replace firm wording such as 「圧倒的に」 with numeric ratios. People who only use the tools do not have their own criteria for choosing a model.
- [content-049] In a usage guide for a tool you can start just by pasting (it installs when you give a prompt to an agent, and so on), put on the first page right after the cover that prompt (one for first-timers and one for people who already have it installed) and 「これを貼れば始まる。読むのはそのあと」. Do not start from the explanation of the mechanism or steps (some people read the guide in order and never reached the part to paste).
- [content-050] On guide pages for people who only use the tool, make the body of each page short tags and words (1–2 lines per box), show the explanation with figures (paths, before/after contrast, position diagrams, icons and short tags), and move the text to the notes. Do not end with a page of explanatory text in numbered steps or a page of three text-heavy cards. Things to paste, such as prompts, and tables used as lookup lists may stay, but keep the cells short.
- [content-051] When updating a material that explains a tool or mechanism, first go through the changes from the version you checked before (the commit or release written in the outline) to the current version (`git log`, release notes, 「決めたこと」 in the README), and fix every page where a changed implementation appears (how to write it, file formats, commands, counts, what is asked at install time), including pages you were not told about. Update the checked version in the outline and in the dates of the source lines.
- [content-004] When you add a chapter for a different audience to one material (example: a 「迷ったらこれ」 chapter for sales at the start of an analysis for yourself), write it so that reading only that chapter is enough. Replace the other chapters' terms and ways of stating numbers (「2 pt」「勝率」「段」 and so on) with words that audience understands. For the evidence, do not write 「2 章を参照」; point directly to the pages with the supporting numbers (example: 「p.7（長い作業）・p.8（1 回で答える作業）」). Check that the chapter's recommendation does not contradict the other chapters' recommendations, down to the scope of 「〜だけ」 in the headings. Check the audience's tool settings (default values, how to change them) in that audience's tool before writing them, and write 「確かめていない」 for anything not checked. Show which chapter is for whom with the cover subtitle and the section dividers.
- **Explanation and evidence in materials meant to be read:** For materials sent by email or chat and read on their own, limit the main part to short claims, figures, and the evidence needed for the decision. Put detailed explanation, conditions, and sources in the Appendix, and point to them from the main part. Check it by asking whether the recipient could explain it to their own manager without the speaker notes. Notes are the voiceover script (§5); do not put evidence needed for the decision only in the notes. Even when you cut text, keep the explanation needed to read the meaning of the figures and the conclusion （中身 1-10）.

**Customer-facing proposals and explanations** (proposals, PoC plans, explanations to IT departments or executives)
- 聞き手の問い: 自分たちは何をすべきか、何を決めればよいか。
- 答えは先に出す。冒頭の 1〜2 枚で、問いと答えの要約を見せる（SCQA: 状況 → 何が問題か → 問い → 答え）。役員向けほど先に出す。
- 営業色は抜くが、推奨は 1 つに絞って言う。次の一歩は、小さく始められて途中でやめられる形にする（範囲、期間、続けるかを決める基準）。
- [content-005] 推奨が製品のときは、名前と提供ステージだけで終わらせない。まず公式の位置づけ（製品を一言で何と呼ぶか。例: Lakewatch は「レイクハウスネイティブで、AI エージェントネイティブな SIEM」）を、製品を説明するページの見出しかリードに出し、その言葉の意味を本文で説明する。言い方は日本語の製品ページとプレスリリースにそろえる。そのうえで、その製品が何をするか（機能の全体像）と、聞き手の環境（データの置き場所、今の取り込み、運用の形）でどう動くかを、1〜3 枚で、本文だけで読めるように書く。向かないところも同じページに書く。材料は、製品の社内資料（materials.md の「社内の資料」の Japan SME の一覧など）を先に調べて構成と言い方を借り、事実は公開の docs で書く。
- Include only public information and the customer's own information. Do not include internal matters (「社外秘と顧客の情報」 in AGENTS.md).
- [content-006] 顧客が依頼のときに伝えてきた、検討中のプロジェクト・チーム・領域（例:「横断 DX」「全社システム再構築」と、その中のテーマ）は、聞き手の問いの中心として使う。目線合わせのページにその名前のまま載せ、使いどころ・比べ方・次の一歩のページで、それぞれのテーマに当てはめる。製品の一般論だけで組まない。
- 顧客の IT 本部や調達向けは、営業色を抜いて、レイクハウスやオープンテーブルフォーマットの考え方の説明に寄せる。重なるところは重なると言う。検証の提案や利用料の話は Appendix か口頭に回す。
- 役員向けは、冒頭の 1 枚に、推奨、決めてほしいこと、費用、効果、期限を置く。技術の話は、何が変わるか・いくらかかるか・だから何か に置き換える。費用やリスクと、できるようになることの両方を書く（中身 1-9）。
- 初めての提案の前は、調べた範囲の課題の仮説を 1 枚にして見せ、違っていたら教えてほしいと頼む。提案書より前に置く（中身 1-14）。2 の表の「相手に確かめる問い」の形の 1 つ。
- [content-007] 話を聞くための資料（ヒアリング）は、聞くだけの構成でもよい。聞き手の関心の領域の業界の潮流を、特定の製品に寄せずにまとめて冒頭に手土産として置く案は、構成案を確かめるときにユーザーに出してよい（必須ではない。0 の 4・5）。
- [content-008] When summarizing industry trends, do not stop at a table that lists specs or products; include a landscape map that shows on one page where each camp stands (example: the open spec and OSS side, and each vendor's managed-product side). With layers or kinds as rows and camps as columns, you can read where the camps connect and where they split.
- 提案の型の「Why change → Why now → Why <自社>」は、ここと同じ向き。ただし Why now は、期限・規制・サポート終了などの事実があるときだけ使い、なければ不安をあおらないほうを取る（社内 3）。
- [content-042] **顧客と認識を合わせるための資料（定例の資料、スケジュール、進捗の一覧、宿題のまとめなど）に載せるのは、顧客と合意したことと、顧客が言った・持ち帰ったことだけにする。** チャートだけでなく、本文・表・赤字の宿題も同じ。こちらが紹介・提案しただけの機能や案（プレビューの新機能、使い方の案など）は、ノートか社内メモに置く。未定でも、こちらの期待値として進みを追いたいものは載せてよいが、合意した予定と見分けられる形（構想・継続のバー、「時期未定」「<自社> から提案中」など）にする。前の版から写した行も、回ごとにこの目で見直す（紹介しただけのものが混ざると、合意の記録として使えなくなる）。提案資料など、こちらの考えや狙いを伝える資料には当てない。どちらかは資料の用途で決める。見出しの決め方は content-017。レビューの観点 3 で見る。
- [content-052] 製品・機能（とくに監視・運用・ガバナンスなど、それ自体が目的にならない機能）を顧客に紹介する資料は、機能の説明に入る前に「なぜそれが要るのか」の章を冒頭に置く。聞き手の運用で起きること（困る場面と、その影響）から入り、機能はその答えとして出す（0 の 1・3）。顧客向けの資料には、社内向けの「顧客にどう案内するか」の問いを入れない。
- [content-053] 聞き手が内製（自社で作る）を検討しているときは、内製を否定せず、層ごとに「自社で持つ・製品の機能を借りる・組み合わせる」を並べ、どちらにも未成熟なところを書き、決め方（同じ問いで並べて、質・立ち上げの時間・保つ手間を比べる）を次の一歩に入れる（0 の 5）。聞き手と別の組織の人の意向は、名前も意向も資料とノートに入れず、社内メモに書く。
- [content-054] For periodic updates to the customer (weekly or monthly summaries of product updates), split chapters by service or product with section dividers, and put a table of contents of the chapter's pages on each divider. Do not split by the weight of our assessment (needs action, worth trying, wait and see). Even a single item gets its own chapter if the service differs (this takes priority over visual-012's "merge a chapter with only one page after its divider into the one before or after"; lint's single-page chapters may stay for this reason).
- [content-055] 顧客向けのスライドに、こちらの評価や勧めの強さのラベル（「試す価値あり」「知っておく」「おすすめ」など）を書かない。キッカーや札にも置かない。キッカーは事実（提供ステージ・製品・日付）だけにする。聞き手にどう効くかは、項目ごとの本文（「〜なら、〜できる」）で言う。
- [content-056] 自社のアカウントチーム（営業・海外のチームなど）から「会議で確かめてほしい」と頼まれたことは、表紙の次に「最初に確かめたいこと」の 1 枚にして、冒頭で聞く。確かめる理由が聞き手にも分かっているなら（前回の会議で伺いきれなかったなど）、リードとノートで率直に言う。頼んだ人の名前と社内のやり取りはページに書かない。英語を話すチームも見るなら、そのページは英語を併記する。
- [content-057] 顧客に共有する議事録のアクションアイテムには、議事録を作る・送ること自体を入れない（送るのはユーザー）。将来の検討課題（PoC の範囲の外で時間をかける話など）は外し、本文に「将来の検討課題で、長い時間軸で考える」と書く。載せるなら、時間軸が長いことを項目に書く。相談・依頼の宛先（自社のアカウントチーム、グループ会社など）は会議の言葉で確かめ、取り違えない。

**Internal** (study sessions, enablement, account status summaries)
- 聞き手の問い: 顧客に何を言えばよいか、どこでつまずくか、自分は何を頼まれているか。
- 状況整理は、結論と依頼（決めてほしいこと、手伝ってほしいこと）を先に出す。勉強会は、冒頭で持ち帰れること（顧客への言い方、判断の基準、デモの手順など）を言い、あとは聞き手が知っていることから新しいことへ積み上げる。
- 営業色はそもそも要らない。弱いところ、競合に負けるところ、まだ解けていないことも率直に書く。
- Internal information may be used. Because pages may be reused for customers, write 「Internal Only」 on confidential pages.
- [content-009] ユーザー以外に共有する資料では、ユーザーが個人で使っている道具（T3 Code など）の名前を出さない。読み手が使う道具（pi・Claude Code・Codex など）の言葉で書き、要るときは「Codex 向けのサードパーティのツール」のように一般化する。ただし、SA の勉強会のような比較的くだけた会の資料では、実例として出してよい（実例があるほうが分かりやすい）。
- [content-010] When recommending a protection such as isolation or a sandbox, write the scope the protection contains and what stays outside it (components running in the same process, credentials, network). Read the builder's threat model (SECURITY.md and so on) first, and show the protections split the same way the builder splits them.
- [content-011] In materials that introduce a customer case internally (All hands, Meetup, and so on, where people who do not know the customer also listen), put one page before the main topic on the customer's service (what the company or business does) and how it uses our products (consumption amount and the position within the customer; example: the company-wide platform is another vendor's product, and our product came in through a business unit). In materials about why product usage grew, also put, before the reasons, one page on what the product is used for (per app or use: what it does, what is placed on the product, the share of consumption). Checked by review aspect 1.
- [content-012] アカウントワークの振り返りでは、SA の定常業務（定例での進捗確認など）や、まだ手を打てていない課題を「工夫」に入れない。顧客が実際につまずいたこと（ハマりどころ）も、解消したもので、資料の主題に関係するものだけを載せる。
- [content-013] For technical research on OSS or tools, do not stop at reading documents and code; run what can be run locally and check the material's claims. Before running, tell the user what you will run and where (do not wait for approval). Install it in a throwaway folder under /tmp, and run it with version upgrades and outbound sending blocked. When a risky operation is needed (passing credentials, sending outside, incurring charges, changing local settings or shared things), confirm first. For what you could not run, write the scope in the material as 「動かして確かめていない」.
- [content-014] When researching to improve our own mechanisms (harness, skills, settings, and so on), do not just list the approaches you found; apply them to the actual current usage and check the fit. Apply them to local data and history (log formats and so on), the current settings, the tools in use, and so on. Decide how far to apply them by choosing what bears on the request's question.
- [content-058] 依頼の見立て（「〜の不具合がある気がする」など）を確かめる調査で、見立てが外れて別の原因が分かったら、資料は見立ての検証の報告にせず、分かった事実（本当の不具合・仕組み）を主題にして書く。題・要旨・章立てに外れた見立てを据えず、見立てが外れたことは「経緯」に 1 段落で書く。社内に共有する不具合の資料は、症状・条件・再現・影響・回避策・報告先の順にし、読んだ人がすぐ当てはめられるようにする。
- [content-059] 社内の道具の「〜すると困る」「使わない」は、ふだんそう使っている人の経験と合うかを確かめてから書く。仕組みの上の欠点だけで言い切らず、ほかの道具が補っていないか、実際に困るのはどんな場面かまで書き、「動くが、〜が変わる」の形にする。聞き手が知りたい用語は、関わる仕組みのページで 1 枚にする。

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

[content-015] **Materials for talks such as LTs, when the content is new to the audience**
- One message per page. State it firmly in the lead (the heading on assertion pages), and show the body as a figure, or as large numbers and short words. The body is at most 5 lines (125 characters) （中身 1-13）. `gslides.py check <URL> --talk` reports pages over the limit as `要確認`.
- Do not put file names, paths, commands, or step details on the page; move them to the Appendix. Before the name of the mechanism, show what happens from the audience's point of view (what you ask for and what comes out).
- [content-016] Only on pages where the user asked for a technical deep dive may file names and script names appear. Those pages also show their role with a kicker (「深掘り: …」), and still keep one message per page and the character limit.
- Do not apply this to materials meant to be read (circulated or sent by email). Those follow "Explanation and evidence in materials meant to be read" in §1.

## 3. Order of work

[content-039] At the top of the outline, write four things: the material type (customer-facing, internal, community-facing), the audience (department and role, technical level), the audience's questions (with sources), and what the audience can do or decide after reading or listening. Even if you can write them, confirm them with the user before starting to make the material (`SKILL.md` "How to start" step 5). For materials that introduce a mechanism or an effort (a mechanism we built ourselves, an LT on a team's effort, and so on), also ask for the builder's intent (what they wanted to build), where they put effort, and what they want next (whom they want to spread it to). Building from a description of the finished thing makes the theme and the landing drift apart.

- Decide in this order: the action you want the audience to take → what state the audience is in at that time → the audience's expectations and knowledge → the claim and the 3–4 points that support it → the skeleton (page numbers, headings, summaries) → figures and tables. **Do not start from figures and tables** （中身 1-7）.
- Put the claim and points down first as hypotheses, and write in the outline whether each has support. Fix weakly supported points or write 「仮説」 for them （中身 1-7）.
- 構成案の「聞き手」の欄に、聞き手の型を書く。結果を見るか過程を見るか、自分で決めるかほかの人の意見で決まるか。過程を見て自分で決める人には、最小限の中身と、見方を揺さぶるデータ。ほかの人の意見で決まる人には、事例とほかの判断者の根拠（中身 1-8、書評経由）。
- Decide whether to make a material to be read or a material to be shown by how it will be used. Materials sent by email or circulated internally are written so that they can be read and decided on alone. If prose is enough, make it a document (Google Docs) （中身 1-10）.

## 4. Headings

- [content-041] **本文のページの見出しは、短い名詞句にする。言い切りの文にするのは、判断を頼むページと数字の結論のページの 2〜3 枚だけ。** 名詞句は、そのページだけの話が分かる形にする（「問い合わせの一次回答の推移」。「現状」「課題」「まとめ」のような、どの資料にも付く項目名にしない）。主語は聞き手の業務・データ・判断にする（AGENTS.md）。名詞句の見出しのページでは、言えること（だから何か）をリードか本文か結論バンドで言う。言い切りのページは、構成案の型の欄に「言い切り」と書く（SKILL.md の 5）。全ページを主張の文にすると、どのページも同じ強さで言い切って要の主張が埋もれ、見出しが長くなる。主張の文の見出し（中身 1-1）は、聞き手に判断を頼むところと数字で言えるところに絞る。文末と句点は 6 の「文体」。
- [content-017] **定例のたびに使う資料（スケジュール、進捗の一覧など）は、ページの見出しを回ごとに変えない。** 「プロジェクトスケジュール 1/2　ML とデータ基盤」のように、資料の名前と範囲で決め、その回の要点（何が増えたか、次の一歩）はスピーカーノートで話す。毎回同じ見出しなので、画面で同じページを探しやすい。
- 見出しとリード（言い切りのページは見出し）で、次の 3 つの問いのどれかに答える。本当か（事実と数字）、だから何か（意味）、どうするか（打ち手）（中身 1-2）。
- 1 行に収める（visual.md の 1）。本文幅・24pt で全角 35 字ほどまで。目安は 25〜35 字。lint が「2 行の見込み」を出したら、削るか言い換える（中身 1-2）。
- 図表のタイトル（何のデータか。例: 地域別の売上の推移）と、そこから言えること（リードか、言い切りの見出し）を分ける（中身 1-3）。
- [content-018] 見出しの範囲と数の言葉（「だけ」「すべて」「N つ」「割れている」など）は、そのページの表・図の行や項目と突き合わせる。表に例外の行がある、数が合わない、片方の側の例しかない、なら見出しの範囲を絞る（例:「type のほかはすべて省いてよい」→「ふつうの概念では、type のほかは省いてよい」）。
- 結論バンドは、要るページにだけ置く（visual.md の 1）。置くときは見出しやリードの言い換えにしない。見出しかリードが「何が言えるか」なら、結論バンドは「だから何をするか」か、決めてほしいことにする（中身 2 節）。
- [content-019] 表紙の副題・説明・図は、本編を改訂したら合わせて直す。表紙に出す製品名は、聞き手のいまの環境と会話に出ているものだけにする（例: 聞き手が使っていない他社の製品を表紙に出さない）。本編の比較には、公平さのために入れてよい。

## 5. Content of one page

- 事実を並べたページには、「だから何か」を 1 文足す。課題や懸念を出したら、対応を同じページか次のページに置く（中身 1-4）。
- 「十分」「限定的」「大幅に」のような評価語は、そのページに裏づけがあるときだけ使う（中身 1-3）。
- [content-020] 時代や業界の流れを主張にするとき（例: AI エージェントの時代は〜）は、Web で中立の出典（調査会社、他社の発表）を確かめ、言える範囲に直してから書く。予測を現在形で言い切らず、反対の見方（失敗の予測など）はノートに添える。出典は自社だけにしない。予測は、予測と分かる形で 1 枚にまとめてよい（注意の予測も並べる。話すときに飛ばせるので、枚数が増えてよい）。
- [content-021] 相手のデータや環境を確かめていないうちに「できる」「作れる」と答えるときは、何次第か（どのデータが取れているか、意味の分からない ID など）を、見出しかリードと、冒頭の要約の文に書く。条件を後ろのページや前提の列にだけ置かない。レビューの観点 2（見出しの範囲）で見る。
- [content-022] 「〜から逆算して選ぶ」と推奨するときは、要素（意味・権限・ガバナンスなど、要る機能）で逆算し、使う道具やエージェントは入れ替わる前提にする。流行りの道具が出るたびに製品を乗り換える話に読めないようにする。道具が替わっても効く強み（公開仕様の形式など）は、その前提とつなげて書く。
- [content-023] 比べるときは、相手（他社の製品・OSS・今の仕組み）が勝つ軸も入れる。相手の道具や機能（例: AWS の Agent Skills）は、ないと決めつけず、確かめてから書く。相手にも同じ道具があるなら、それを書いたうえで、違いはその先（例: 関連するリソースが多く、IaC を介して組む）で書く。自社の数値には測った条件を注記する。相手にしかない機能（例: ブラウザの操作）は、結論で「相手も比べる」とぼかさず、「その部分は相手を使う」と勧める。成熟度の差（GA の部品の多さなど）は、表のステージで比べられるようにして「比べる」でよい。0 の 5「公平に書く」の具体（中身 2 節）。
- [content-060] 接続・認証・API の出し方などで推奨の方式を描くときは、選べるほかの方式（トークンとパスワードなど）を、違い（期限・管理・使える機能）と使い分けとあわせて 1 枚で書き、推奨の理由（安全の面など）も書く。推奨の方式だけを描くと、聞き手がほかの選択肢を知らないままになる（0 の 5・6）。
- 数字は、起点と比べる先を書く（「前年比」「9 月時点」「割引後」）。数字が概算なら概算と書く（中身 1-9）。
- [content-024] 出典の中で値が食い違うとき（docs のページの間、事例のページの見出しの数字と本文）は、強いほうの値だけを見出しや大きな数字にしない。どの出典とも食い違わない安全な側で言い切るか（数百ミリ秒と数秒なら「数秒以内」）、本文の値で書き、見出し・大きな数字・表・ノートと、ほかのページの同じ数字を同じ言い方にそろえる。食い違いは構成案の出典の表に書き、資料には書かない。外に出す資料（顧客・パートナー向け）に「docs のページで違う」「docs にない」「実測する」のような、出典の揺れや確かめていないことを見せる言い方を書かない。言える範囲を言い切り、言えないことは言わない。
- [content-025] When writing prices, context window sizes, or performance of LLM models, check them against each vendor's latest generation (example: as of 2026-10, GPT is the 6 series and Claude is the 5.5 series). Check the latest generation in the local model list (`~/.pi/agent/models.json` or the internal gateway's endpoints) and each vendor's official price list; when you write values of an earlier generation, write them so it is clear they are the earlier generation. Prices in internal guides (Confluence and so on) can be old, so recheck them against the official tables. In tables and trials that compare models, do not drop each vendor's latest flagship models (as of 2026-10, GPT-6.1 Sol, Claude Opus 5.5 and Sonnet 5.5) from the comparison. Do not let only a cheap model (Luna, Haiku, and so on) represent that vendor.
- [content-026] Pages that measure or test with models (token counts, response seconds, summary quality, and so on) measure with the model the user mainly uses. Add other models as comparisons. Ask which one is the main model during the check before making the material, and write it in the outline's assumptions.
- [content-027] For a product's available regions, processing location, and release stage, read the legend of the symbols in the docs tables (⥂, ‡, and so on) and the original footnotes, and write within that scope. Do not rephrase by adding conditions or consequences, such as turning 「cross-Geo の設定が要る」 into 「国外で処理される」. Write conditional statements (「when you disable cross-Geo processing」) together with their conditions.
- [content-028] When proposing an overseas region for a feature not available in Tokyo, do not choose by proximity. Propose a region where every feature you use is available in the docs' per-region availability table (usually US), and cite the table you checked as the source.
- Decks over 10 pages show the current position on an overall map at the head of each chapter. Pick up every point marked 「後で話す」 later in the material （中身 1-5）.
- 終わりは要約で締めず、次の一歩の 1 枚にする。顧客向けなら、決めてほしいこと、小さく始める範囲・期間、続けるかを決める基準（中身 2 節）。
- The main part is about 5–9 pages. Put answers to expected questions in the Appendix （中身 1-6）.
- [content-029] Pages the speaker decided to "cover orally" are not deleted; make them pages shown while talking. Keep only the heading and the main points (about 3 steps), and move what is said to the notes.
- [content-030] Do not put the same table in both the main part and the Appendix. Limit the main part to figures and decisions, put detailed lists in the Appendix, and point to them from the main part. The same goes for lists of commands, APIs, and setting items: put only the flow (a 3-step procedure and so on) and one example in the main part, move the list to the Appendix, and point to it from the main part.
- [content-031] When you add topics, periods, or targets and show the same comparison again, also add the figures from the earlier part (bar charts and so on) in the same form. Do not settle for a table only.
- [content-032] In materials that compare several topics, parts, or periods, write what each topic is (subject, audience, length, conditions) on the page where the topic's name first appears (the conclusion or the comparison method), and put a section divider for each topic. Also put a divider before summaries that span topics (what cannot be said, next steps). Do not call them only by numbers such as 「1 題目」「2 題目」.
- [content-061] In materials asked to examine two or more axes (time and cost, and so on), cover every axis with the same depth. For time, put not only the total per step but also a breakdown of step × kind of time (model, waiting for child agents, building, waiting for people) and a single timeline band (visual.md visual-045). Leaning toward the details of one axis makes the overall breakdown unreadable.
- **Speaker notes:** The notes are the Google Vids voiceover script, because a video is made from the same deck with the same notes (`../vids-beta/SKILL.md`). While writing pages, write only draft notes in `speakerNotes`: the points to say on that page (the facts, caveats, and what you moved off the slide; content-020, content-029) in short sentences, without bridges to other pages, an opening or a closing, or audio tags. After building the whole deck, the parent rewrites them into the script for the whole deck at once by `../slides-speaker-notes/SKILL.md` (deck-practices-021 in SKILL.md), because notes written page by page have no story across scenes. Do not put supplements for readers (sources, URLs, detailed conditions) in the notes, because the voice reads them; put them in the source line, the body, or the Appendix (§1, "Explanation and evidence in materials meant to be read").

## 6. Wording

- **文体:** 書くところで分ける。和欧間のスペースと製品名の書き方は AGENTS.md の「書き方」。
  - 見出し: 表紙の題・章の扉・図表のタイトル・カードや表の項目名と、本文のページの見出し（4）は、短い名詞句（体言止め）。言い切りにする 2〜3 枚の見出しと、名詞句の見出しのページのリードは、主語と述語のある常体の文で言い切る（「問い合わせの一次回答が 3 割減っている」「夜間の集計を新しい基盤に移す」）。言えることを体言止めにすると、誰がするのか、予測なのか意志なのかが消える。「だ」「である」で終える必要はない。見出しに句点を付けず、「〜ください」「〜します」で終えない。頼みごとはリードか本文で言う（lint が「見出しの句点」「見出しが「ください・します」で終わる」を要修正、「言い切りの見出しが多い」を要確認に出す）。
  - 箇条書きと図のラベル: 体言止めでよい。ひとまとまり（1 つの箱の箇条書き、1 つの図のラベル、見出しの並び）の中では、文末（体言止め・常体・敬体）と句点の有無をそろえる（lint が「箇条書きの句点の混在」）。名詞だけで終えない（下の「箇条書きを名詞だけで終えない」）。
  - 本文: 敬体か常体のどちらかにそろえる。スライドは常体か体言止めにする。スライドの です・ます は、案内・依頼・注意書きのページ（問い合わせ先、アンケートのお願い、「ご相談ください」、免責・価格の注記）では残してよい（lint の「スライドに です・ます」は、それ以外のページに出たものを直す）。
  - 顧客向けのドキュメントは です・ます調。スピーカーノートは話し言葉（です・ます）。社内メモは だ・である調でよい。
- When making the material in English, use sentence case for headings and write the notes in English too.
- [content-033] **Sources:** Attach a source to every number (on slides, the source line at the bottom of the page; in documents, a footnote or parentheses in the body). Give every blog, talk, doc, or study cited as a source a link to the original page, so that it can be reached from the page that cites it. Do not put links only in the source list in the Appendix (lint reports source lines without links). For customer-facing materials, attach only public URLs, and do not cite meetings with the customer as sources (「社外秘と顧客の情報」 in AGENTS.md).
- [content-064] **Facts on pages come from the 「出典の表」.** Put on pages only numbers, availability statements, statements about the customer's environment, and proper nouns that are rows of the 「出典の表」 (columns and kinds: "Ledger" in materials.md). When you need a new one while writing, add the row with its source first, then write the page; do not settle the value on the page and backfill the table. Write a computed value as a `計算` row with the rows it uses and the formula, because computed values were the numbers most often missing from the table. Product facts (`提供・数字・名前`) need a `公式` source or local data: mark them 「済」 only after opening one, and treat a chat, a meeting, an article, or something said in the conversation as a lead, not a source. Write `見立て` rows on the page so that they read as `見立て` or `仮説`. lint reports numbers that are not in the table (`出典の表にない数字`).
- [content-063] プレビューやベータの機能は、提供ステージ（Private Preview・Public Preview・Beta）を書く。「本番向けではない」「本番では使えない」と添えない。どこまで使えるかの判断は聞き手に任せる（本文もノートも、ほかのページも同じ）。スライドのラベルの付け方と、控えるページは visual.md の 1。
- 1 つの資料で 1 つのものには 1 つの言葉を使う。最後に表記ゆれを全文で探す。略語は初出で正式名を書く（中身 1-11）。
- [content-034] 道具・エージェントは、聞き手がふだん使っている製品の名前で書く（Claude Code、Codex CLI など）。ACP のアダプターや登録簿の表示名（Claude Agent、Codex など）は、アダプターそのものや登録簿の一覧を指すときだけ使い、そのページで製品の名前との対応を一度書く。レビューの観点 4 で見る。
- [content-062] 道具の画面に出る設定の値（reasoning effort の Low・Medium・High など）は、画面の表記のまま書く。「浅め・ふつう・深め」のような訳語に置き換えない（画面で探せず、意味が通らない）。項目の名前は和訳してよいが、初出に英語の名前を添える（例: 考える深さ〔reasoning effort〕）。
- [content-035] 資料の主題の言葉（タイトルに入れた言葉。例: オープンテーブルフォーマット）は、それを説明するページの見出しか図にそのまま出す。言い換え（テーブル形式・公開仕様）だけにしない。
- 箇条書きを名詞だけで終えない。「強化」ではなく、誰が何をどう変えるかを書く。同じ階層の箇条書きは文末をそろえる（中身 1-11）。体言止めそのものはよい（この節の「文体」）。
- 「実現」「加速」「最適化」「効率化」「強化」「変革」で文を終えない。対象と変化を書く（例:「業務の効率化を実現」ではなく「問い合わせの一次回答を AI に任せ、担当者は個別の対応に回る」）。言い換えられないなら、その項目は要らない。禁句をほかの空疎な語に置き換えるだけにしない（AI 実践 1-6）。lint が候補を出す。
- 「社内」「外部」「既存」のような相対語は、誰から見てかを書く（中身 1-11）。
- 口に出して言える日本語にする。会社名や製品名を入れ替えてもそのまま通る文は、中身がない（見た目 1-9）。
- [content-036] **字を詰めるために語を略さない。** 「〜の組の点」「Grok Build の点は」のように、何の数か・何と何の組み合わせかを略した名詞句にしない。数字は何を測った値か（「端末の作業を解けた割合」）、組み合わせは「〜と〜を組み合わせた成績」と書き、ノートと同じ言い方で口に出して通じるかで確かめる。短くするなら、文を分けるか、要らない語を消す。レビューの観点 4 で見る。
- Do not fill in facts that are not in the materials (internal operations, product behavior, numbers). Write 「要確認」 for what you do not know, and resolve it before delivery （AI 実践 1-7）.
- [content-037] **Compute numbers from the source data.** Compute totals, averages, ratios, and multiples from the original values (tables, JSON, records); do not add or divide rounded values. Even when a table shows rounded values, compute with the values before rounding (computing with rounded values makes the totals drift).
- [content-038] **When you add a comparison target midway, search all pages again for assertion words.** Search the headings, body, tables, panels, and notes for 「最も」「だけ」「すべて」「どれも」「N 本・N 社・N つ」 and for abbreviated names (such as 「Sonnet」 once there are two of the same model or product), and check that they still hold with the added target (after adding, overstatement and mixed-up names are common).

## 7. Checks for the outline and the finish

- [ ] 枚数や時間を削るときは、製品の説明から削り、目線合わせを残している（2 の表で「すぐ本題に入る」場面は除く）
- [ ] 問いと課題を整理したページに、自社の製品の機能の話が入っていない（聞き手の今の環境として名前が出るのはよい）
- [ ] Features the audience does not know have pages on how they work and what they look like once in use (the steps). They do not end at the name and release stage
- [ ] Every problem item has a source or 「仮説」
- [ ] 見解（推奨か使い分け）がはっきりしている。顧客向けなら、推奨が 1 つで、次の一歩が小さい
- [ ] [content-040] The opening conclusion (summary) page answers every one of the audience's questions in the outline
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
- [ ] Wherever the body was fixed, the notes on the same page are fixed to match (counts, scope, names, assertions)
- [ ] If a comparison target was added midway, 「最も」「だけ」「N つ」 still hold with the added target

## 8. References

Checked on 2026-10-05: the Pyramid Principle and SCQA (Barbara Minto); the audience as the hero (Nancy Duarte, *Resonate*); in large deals, questions about the impact of problems work (Neil Rackham, *SPIN Selling*); insight that reframes the customer's view (Dixon and Adamson, *The Challenger Sale*); 40–60% of lost deals come from customers failing to decide, pushing harder on the harm of the status quo backfires in 84% of cases, and stating a clear recommendation and lowering risk works (Dixon and McKenna, *The JOLT Effect*, HBR 2022); buyers who receive information that moves their decision forward are 2.8 times as likely to find buying easy (Gartner's 2018 B2B buying survey); identify the question to solve first (安宅和人『イシューからはじめよ』); community conferences often ban product promotion in their CFP (KubeCon + CloudNativeCon, JJUG CCC, CEDEC).

The 2026-10-06 research (mainly Japanese-language sources) is cited by the short names in parentheses in the body. The short names are mapped in the table in SKILL.md.

2026-10-13 に確認（6 の「文体」）: 本文は敬体と常体を混ぜない、見出しは常体か体言止めで句点を付けない、ひとまとまりの箇条書きでは文末を混ぜない（JTF 日本語標準スタイルガイド 第 4.0 版の 1.1、https://www.jtf.jp/pdf/jtf_style_guide.pdf ）、1 つの文書の中で文末を混ぜないが、箇条書きの部分に違う文末が出るのはよい（文化審議会建議「公用文作成の考え方」の解説 Ⅲ-1、https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf ）、体言止めにすると主語が抜けて責任や因果が曖昧になり、予測か意志かも分からなくなる（杉野幹人『超・箇条書き』、https://diamond.jp/articles/-/338937 、https://diamond.jp/articles/-/382251 ）。
