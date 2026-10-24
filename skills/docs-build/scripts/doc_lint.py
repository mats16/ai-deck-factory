#!/usr/bin/env python3
"""usage: doc_lint.py <doc.json>   Google Docs（Docs API の documents.get の JSON。docs.py check が書き出して呼ぶ）
       python3 doc_lint.py --selftest で自己確認（要確認の残り方は ../../deck-practices/scripts/textlint.py --stats）
ドキュメントの決まりのうち、機械で見られるものを数える（2026-10-09）。本文の表記の決まり・出典の照合・記録はスライドと同じ textlint.py。標準ライブラリだけで動く。
要修正（HARD）が 1 つでもあれば exit 1。要確認（WARN）は 1 件ずつ見て、直すか、残す理由を言えるようにする。
ルールの出典は ../visual.md と ../../deck-practices/content.md。docx を読んでいた部分は Archive/docx_pipeline_20261010/。"""
import itertools, json, os, re, sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deck-practices", "scripts"))  # スライドと共有する部品
import gapi, textlint  # noqa: E402
from brand import FONT, MONO_DEFAULT  # noqa: E402
from textlint import (HARD, HEAD_PERIOD, HEAD_POLITE, FONT_NG, JA, MONO_NG, NO_LINK, NOT_IN_FACTS, NUM, POLITE_END, WARN, facts_hit, load_facts,  # noqa: E402
                      not_in_facts, workspace_checks)  # load_facts は docs.py が doc_lint から引く

DOC_MIN_PT = 9  # ドキュメントの文字の下限。図表の題・出典・表の中・フッターが 9pt（docs-build/visual.md の 1）
SENTENCE_MAX, PARA_SENT_MAX, LINE_MAX = 100, 8, 40  # 一文の字数（textlint の sentence-length の既定）、1 段落の文の数（3〜8 文。木下・倉島・サイボウズ）、
# 1 行の字数（jlreq・デジタル庁）。docs-build/visual.md の 1・3
BOLD_PER_1000 = 3  # 本文 1,000 字あたりの太字の数（Qiita の 2019〜22 年の平均は 1.26、2026 年は 3.83。docs-build/visual.md の 3）
DESU = re.compile(r"(です|ます|でした|ました|ません|でしょう|ください)$")
DEARU = re.compile(r"(だ|である|だった|であった|する|した|しない|ない|なかった|ある|あった|いる|いた|できる|なる|なった)$")
A4_NG, UTM_NG = "用紙が A4 でない", "追跡の印の付いたリンク"
DOC_ONLY = ("文体の混在", "一文が長い", "段落の文が多い", "1 行の字数が多い", "見出しの段の飛び", "見出しの段が深い", "子が 1 つだけの見出し", "見出しの重複",
            "見出しの中の太字", "中身のない見出し", "太字の段落を見出しにしている", "題が「について」で終わる", "冒頭に要旨がない",
            "末尾の「まとめ」", "空の段落の連続", "表の題がない", "図の題がない", "数字に出典のリンクがない", "太字が多い", "太字とコロンで始まる箇条書き",
            "コロンで終わる文", "1 項目だけの箇条書き", "箇条書きの句点の混在", "本文の幅を超える図")


def gdoc_text(p):  # 段落の文字（段落の中の改行 \v は改行にする）
    return "".join(x.get("textRun", {}).get("content", "") for x in p.get("elements", [])).replace("\v", "\n")


def gdoc_paras(doc):
    """本文の段落を順に: (番号, 段落, 表の番号か None, 表の前の段落か)。表の中の段落も、その表の位置に入れる。"""
    out, n, t = [], 0, 0
    content = doc["body"]["content"]
    for i, e in enumerate(content):
        if "paragraph" in e:
            n += 1
            out.append((n, e["paragraph"], None, i + 1 < len(content) and "table" in content[i + 1]))
        elif "table" in e:
            t += 1
            for row in e["table"]["tableRows"]:
                for c in row["tableCells"]:
                    for x in c["content"]:
                        if "paragraph" in x:
                            n += 1
                            out.append((n, x["paragraph"], t, False))
    return out


def theme_pages():
    """ドキュメントのテーマのファイル（ワークスペースの themes/docs/<名前>.json）の用紙（pt の幅・高さ）。会社のテンプレートに合わせた版面なので、
    A4 でなくても、1 行の字数が多くても通す。読めないファイルは飛ばす（形の誤りは docs.py と factory-doctor が止める）。"""
    out = []
    for f in sorted(p.parent.joinpath("themes", "docs").glob("*.json")) if (p := gapi.locate()) else []:
        try:
            page = json.loads(f.read_text()).get("page")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(page, list) and len(page) == 2 and all(isinstance(x, (int, float)) for x in page):
            out.append(tuple(x * 72 / 25.4 for x in page))
    return out


def lint_gdoc(doc, r, template=False, font=FONT, mono=MONO_DEFAULT, facts=None):
    """template=True はテンプレートから書いた文書（docs.py の doc.md の template:）。節の順はテンプレートが決めるので、冒頭の要旨を見ない。"""
    ns = {s["namedStyleType"]: s for s in doc.get("namedStyles", {}).get("styles", [])}
    base = ns.get("NORMAL_TEXT", {}).get("textStyle", {})

    def eff(p, st, key):  # 文字の書式の実際の値。run → 段落の名前付きスタイル → 本文のスタイル の順に見る
        named = ns.get(p["paragraphStyle"].get("namedStyleType", "NORMAL_TEXT"), {}).get("textStyle", {})
        return st.get(key) or named.get(key) or base.get(key) or {}

    runs_of = lambda p: [x["textRun"] for x in p.get("elements", []) if "textRun" in x and x["textRun"]["content"].strip()]
    links_of = lambda p: [x.get("textStyle", {}).get("link", {}).get("url", "") for x in runs_of(p) if "link" in x.get("textStyle", {})]
    ds = doc["documentStyle"]
    pw, ph = (ds["pageSize"][k]["magnitude"] for k in ("width", "height"))
    width = pw - sum(ds.get(f"margin{s}", {}).get("magnitude", 72) for s in ("Left", "Right"))
    a4 = abs(pw - 595.28) <= 1 and abs(ph - 841.89) <= 1
    themed = not a4 and any(abs(pw - w) <= 1 and abs(ph - h) <= 1 for w, h in theme_pages())  # 会社のテンプレートに合わせた、A4 でないテーマの用紙（docs.py の theme）。A4 は例外にしない
    if not a4 and not themed:
        r.hits[A4_NG].append(f"用紙 {pw:.0f} × {ph:.0f}pt（A4 は 595 × 842。テーマの用紙は themes/docs/<名前>.json の page）。docs.py build で入れ直す")
    per_line = width / base.get("fontSize", {}).get("magnitude", 11)
    if per_line > LINE_MAX + 1 and not themed:  # [docs-lint-019] テーマの版面は会社のテンプレートに合わせたもので、1 行の字数が多くなることがある
        r.hits["1 行の字数が多い"].append(f"本文の 1 行が約 {per_line:.0f} 字（{LINE_MAX} 字まで）。余白か本文の大きさを docs.py の値に戻す")
    images = {k: v["inlineObjectProperties"]["embeddedObject"] for k, v in doc.get("inlineObjects", {}).items()}
    paras = gdoc_paras(doc)
    heads, body, bold_spans, empty, firsts, lists = [], 0, 0, 0, [], defaultdict(list)
    desu, dearu = [], []
    sec, sec_num, sec_link = "（冒頭）", [], False

    def close():
        if sec_num and not sec_link:
            r.hits["数字に出典のリンクがない"].append(f"{sec}: 「{sec_num[0]}」ほか。数字の出典を、その節の本文か表の下の出典の行にリンクで書く（content.md の 6）")
    for k, (n, p, tab, before_table) in enumerate(paras):
        text, style = gdoc_text(p).rstrip("\n"), p["paragraphStyle"].get("namedStyleType", "NORMAL_TEXT")
        where = f"段落 {n}" + (f"（表 {tab}）" if tab else "")
        rs = runs_of(p)
        for x in rs:
            st, t = x.get("textStyle", {}), x["content"].strip()
            f = eff(p, st, "weightedFontFamily").get("fontFamily", "")
            size = eff(p, st, "fontSize").get("magnitude", 11)
            if f == mono and re.search(f"[{JA}]", t):
                r.hits[MONO_NG].append(f"{where}: 「{t[:20]}」")
            elif f not in (font, mono):
                r.hits[FONT_NG].append(f"{where}: {f or '（既定）'}「{t[:20]}」")
            if size < DOC_MIN_PT:
                r.hits[f"{DOC_MIN_PT}pt 未満の文字"].append(f"{where}: {size:g}pt「{t[:20]}」")
            if st.get("bold") and style == "NORMAL_TEXT" and not tab:
                bold_spans += 1
            if st.get("bold") and style.startswith("HEADING_"):
                r.hits["見出しの中の太字"].append(f"{where}: 「{t[:20]}」。見出しは名前付きスタイルの太さだけにする")
        for u in links_of(p):
            if "utm_source=" in u:
                r.hits[UTM_NG].append(f"{where}: {u[:80]}。検索の道具が足した印なので消す")
        for x in p.get("elements", []):
            if "inlineObjectElement" in x:
                o = images.get(x["inlineObjectElement"]["inlineObjectId"], {})
                w = o.get("size", {}).get("width", {}).get("magnitude", 0)
                if w > width + 1:
                    r.hits["本文の幅を超える図"].append(f"{where}: 幅 {w:.0f}pt（本文 {width:.0f}pt）")
                nxt = gdoc_text(paras[k + 1][1]).strip() if k + 1 < len(paras) else ""
                cover = k + 1 < len(paras) and any("pageBreak" in y for y in paras[k + 1][1].get("elements", []))  # 表紙のロゴ（docs.py の cover。すぐ後ろが改ページ）
                if not re.match(r"図 ?\d+", nxt) and not cover:
                    r.hits["図の題がない"].append(f"{where}: 次の段落「{nxt[:20]}」。図の下に「図 N　…」を置く（d.image の caption）")
        if before_table and not re.match(r"表 ?\d+", text):
            r.hits["表の題がない"].append(f"{where}: 表の上に「表 N　…」を置く（d.table の caption）")
        if not text.strip():
            empty = empty + 1 if not before_table and not any("inlineObjectElement" in x for x in p.get("elements", [])) and not tab else 0
            if empty == 2:
                r.hits["空の段落の連続"].append(f"{where}: 空きは段落の書式で取る（空の段落を重ねない）")
            continue
        empty = 0
        r.scan(where, text, {**HARD, **WARN})
        if re.match(r"(出典|Sources?)[：:]", text, re.I) and not links_of(p):
            r.hits[NO_LINK].append(f"{where}: 「{text[:24]}」")
        sec_link |= bool(links_of(p))
        if facts is not None and not re.match(r"(出典|Sources?|図|表) ?[：:\d]", text) and (miss := not_in_facts([text], facts)):  # 見出しの数字も（数字で結論を言う見出し）
            r.hits[NOT_IN_FACTS].append(facts_hit(where, miss, facts))
        if style == "TITLE" and text.rstrip("。").endswith("について"):
            r.hits["題が「について」で終わる"].append(f"{where}: 「{text[:30]}」。主題と文書の性格（提案・報告・計画）を入れる（docs-build/visual.md の 2）")
        if (style == "TITLE" or style.startswith("HEADING_")) and POLITE_END.search(text):
            r.hits[HEAD_POLITE].append(f"{where}: 「{text[:24]}」。頼みごとは段落で言う")
        if style.startswith("HEADING_"):
            lv = int(style[-1])
            if lv > 3:
                r.hits["見出しの段が深い"].append(f"{where}: H{lv}「{text[:24]}」。3 段までにし、4 段目は箇条書きか表にする")
            if heads and lv > heads[-1][0] + 1:
                r.hits["見出しの段の飛び"].append(f"{where}: 「{text[:24]}」（H{heads[-1][0]} の次が H{lv}）")
            elif not heads and lv > 1:
                r.hits["見出しの段の飛び"].append(f"{where}: 最初の見出しが H{lv}「{text[:24]}」")
            if heads and heads[-1][2] and heads[-1][0] >= lv:
                r.hits["中身のない見出し"].append(f"{heads[-1][2]}: 「{heads[-1][1][:24]}」のあとに本文がない")
            if "。" in text:
                r.hits[HEAD_PERIOD].append(f"{where}: 「{text[:24]}」")
            heads.append([lv, text, where])
            firsts.append("  " * (lv - 1) + f"H{lv} {text}")
            if lv <= 2:
                close()
                sec, sec_num, sec_link = f"「{text[:20]}」", [], False
            continue
        if heads and heads[-1][2]:
            heads[-1][2] = None  # 本文が来た
        m = NUM.search(text)
        if m and not re.match(r"(図|表) ?\d+", text):
            sec_num.append(m.group())
        if "bullet" in p and not tab:
            lists[p["bullet"].get("listId")].append((where, text, rs))
        quote_or_code = "borderLeft" in p["paragraphStyle"] or "shading" in p["paragraphStyle"]  # 引用（d.quote）とコード（d.code）は本文に数えない
        if style != "NORMAL_TEXT" or tab or quote_or_code or re.match(r"(出典|Sources?|図|表) ?[：:\d]", text):
            continue
        nxt = paras[k + 1] if k + 1 < len(paras) else None
        if ("bullet" not in p and rs and all(x.get("textStyle", {}).get("bold") for x in rs) and len(text) < 40 and nxt
                and gdoc_text(nxt[1]).strip() and nxt[1]["paragraphStyle"].get("namedStyleType", "NORMAL_TEXT") == "NORMAL_TEXT"):
            r.hits["太字の段落を見出しにしている"].append(f"{where}: 「{text[:24]}」。見出しのスタイル（d.h2・d.h3）にする（アウトラインに出ない）")
        if re.search(r"[:：]$", text) and "bullet" not in p:
            r.hits["コロンで終わる文"].append(f"{where}: 「…{text[-16:]}」。文で言い切ってから箇条書きや表に続ける")
        body += len(text)
        sents = [x.strip() for x in re.findall(r"[^。！？\n]+[。！？]?", text) if x.strip()]
        if "bullet" not in p:
            firsts.append("  " * (heads[-1][0] if heads else 0) + "・" + (sents[0] if sents else text)[:60])
            if len(sents) > PARA_SENT_MAX:
                r.hits["段落の文が多い"].append(f"{where}: {len(sents)} 文「{text[:16]}…」。話題が 2 つ混ざっていないか")
        for sent in sents:
            core = re.sub(r"[。！？」』）\s]+$", "", sent)
            if len(sent) > SENTENCE_MAX:
                r.hits["一文が長い"].append(f"{where}: {len(sent)} 字「{sent[:16]}…」")
            if "bullet" not in p and sent.endswith("。"):
                (desu if DESU.search(core) else dearu if DEARU.search(core) else []).append(f"{where}: 「…{core[-14:]}。」")
    close()
    if heads and heads[-1][2]:
        r.hits["中身のない見出し"].append(f"{heads[-1][2]}: 「{heads[-1][1][:24]}」のあとに本文がない")
    strip = lambda t: re.sub(r"^(第?\d+(\.\d+)*[.章節]?|[0-9０-９]+[.．])\s*", "", t)
    h1 = [strip(t) for lv, t, _ in heads if lv == 1]
    if h1 and not template and not re.match(r"(要旨|概要|結論|サマリー|エグゼクティブサマリー)", h1[0]):
        r.hits["冒頭に要旨がない"].append(f"最初の章「{h1[0][:20]}」。結論と読み手に求めることを最初の章で言う（docs-build/visual.md の 2）")
    if heads and re.match(r"(まとめ|おわりに)$", strip(heads[-1][1])):
        r.hits["末尾の「まとめ」"].append(f"{heads[-1][2] or '最後の見出し'}: 「{heads[-1][1]}」。結論は冒頭の要旨で言い、繰り返しの章を作らない")
    seen = Counter(strip(t) for _, t, _ in heads)
    r.hits["見出しの重複"] += [f"「{t[:24]}」が {c} 回" for t, c in seen.items() if c > 1]
    for i, (lv, t, w) in enumerate(heads):  # 子が 1 つだけの見出し（2.1 だけで 2.2 がない）
        kids = [x for x in itertools.takewhile(lambda x: x[0] > lv, heads[i + 1:]) if x[0] == lv + 1]
        if len(kids) == 1:
            r.hits["子が 1 つだけの見出し"].append(f"「{t[:20]}」の下に「{kids[0][1][:20]}」だけ。子をなくすか 2 つ以上にする")
    for items in lists.values():
        if len(items) == 1:
            r.hits["1 項目だけの箇条書き"].append(f"{items[0][0]}: 「{items[0][1][:24]}」。文にする")
        if len({x[1].endswith("。") for x in items}) > 1:
            r.hits["箇条書きの句点の混在"].append(f"{items[0][0]} から {len(items)} 項目。文なら全部に「。」、語なら全部なし")
        for where, text, rs in items:
            if rs and rs[0].get("textStyle", {}).get("bold") and re.match(r"\s*[:：]", text[len(rs[0]["content"]):] or "") or \
                    (rs and rs[0].get("textStyle", {}).get("bold") and rs[0]["content"].rstrip().endswith((":", "："))):
                r.hits["太字とコロンで始まる箇条書き"].append(f"{where}: 「{text[:20]}」。項目の頭のラベルをやめ、文で書くか表にする")
    if desu and dearu:
        few, many = sorted((desu, dearu), key=len)
        kind = "です・ます" if few is desu else "だ・である"
        r.hits["文体の混在"] += [f"{x}（{kind}。本文は {len(many)} 文が逆の文体）" for x in few]
    if body and bold_spans * 1000 / body > BOLD_PER_1000:
        r.hits["太字が多い"].append(f"本文 {body} 字に {bold_spans} か所（1,000 字に {bold_spans * 1000 / body:.1f}。{BOLD_PER_1000} まで）。結論の語句だけにする")
    print("== 見出しと段落の 1 文目。見出しだけで話が通るか、1 文目を順に読んで要約になるか ==")
    print("\n".join(firsts) or "（見出しも本文もない）")
    print(f"\n== 本文の字数: {body} 字（見出し・表・図表の題・出典・引用を除く）、1 行 約 {per_line:.0f} 字 ==")
    hard = r.show(list(HARD) + [f"{DOC_MIN_PT}pt 未満の文字", FONT_NG, MONO_NG, A4_NG, UTM_NG, HEAD_PERIOD, HEAD_POLITE], "要修正")
    r.show(list(WARN) + [NOT_IN_FACTS, NO_LINK] + list(DOC_ONLY), "要確認")
    hard += workspace_checks("doc", doc, r)
    return hard
HARD_NAMES = textlint.HARD_NAMES | {f"{DOC_MIN_PT}pt 未満の文字", A4_NG, UTM_NG}


class Report(textlint.Report):
    hard = HARD_NAMES


def selftest():
    globals()["theme_pages"] = lambda: []  # 回す場所の factory.toml のテーマ（用紙）に左右されない
    globals()["workspace_checks"] = lambda *a: 0  # 回す場所のワークスペースの checks.py にも左右されない
    import contextlib, io
    # Google Docs: わざと欠陥を入れた文書で、規則がそれぞれ拾うか
    def gp(text, style="NORMAL_TEXT", bullet=None, **st):
        p = {"elements": [{"textRun": {"content": text + "\n", "textStyle": st}}], "paragraphStyle": {"namedStyleType": style}}
        return {"paragraph": {**p, **({"bullet": {"listId": bullet}} if bullet else {})}}
    cell = {"content": [gp("a")]}
    gdoc = {"documentId": "x", "documentStyle": {"pageSize": {"width": {"magnitude": 595.28}, "height": {"magnitude": 841.89}},
                                                 "marginLeft": {"magnitude": 85}, "marginRight": {"magnitude": 85}},
            "namedStyles": {"styles": [{"namedStyleType": "NORMAL_TEXT", "textStyle": {"weightedFontFamily": {"fontFamily": FONT}, "fontSize": {"magnitude": 10.5}}}]},
            "inlineObjects": {"i": {"inlineObjectProperties": {"embeddedObject": {"size": {"width": {"magnitude": 600}}}}}},
            "body": {"content": [gp("Lakebase の検討について", "TITLE"), gp("1. 背景", "HEADING_1"), gp("1.1 細目", "HEADING_2"), gp("細かい", "HEADING_4"),
                                 gp("本文です。"), gp("本文である。"), gp("本文です。"), gp("2. 空の章", "HEADING_1"), gp("3. 次", "HEADING_1"),
                                 gp("売上は 30% 増えました。"), gp(""), gp(""), gp("小さい字です。", fontSize={"magnitude": 8}),
                                 gp("Arial の字です。", weightedFontFamily={"fontFamily": "Arial"}),
                                 {"paragraph": {"elements": [{"inlineObjectElement": {"inlineObjectId": "i"}}], "paragraphStyle": {}}}, gp("説明です。"),
                                 gp("見出しもどき", bold=True), gp("続きの本文です。"), gp("次のとおりです："), gp("ひとつ", bullet="L1"),
                                 {"paragraph": {"elements": [{"textRun": {"content": "ラベル：", "textStyle": {"bold": True}}},
                                                             {"textRun": {"content": "説明です。\n", "textStyle": {}}}],
                                                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "bullet": {"listId": "L2"}}}, gp("二つ目", bullet="L2"),
                                 gp("題のない表"), {"table": {"tableRows": [{"tableCells": [cell]}]}},
                                 gp("4. 空の章", "HEADING_1"), gp("出典", link={"url": "https://a.b/?utm_source=openai"}), gp("おわりです。"), gp("まとめ", "HEADING_1"), gp("以上です。")]}}
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    for k in ("見出しの段の飛び", "見出しの段が深い", "子が 1 つだけの見出し", "中身のない見出し", "文体の混在", "数字に出典のリンクがない", "空の段落の連続",
              "9pt 未満の文字", FONT_NG, "表の題がない", "図の題がない", "本文の幅を超える図", "題が「について」で終わる", "冒頭に要旨がない",
              "末尾の「まとめ」", "見出しの重複", "太字の段落を見出しにしている", "コロンで終わる文", "1 項目だけの箇条書き", "箇条書きの句点の混在",
              "太字とコロンで始まる箇条書き", "追跡の印の付いたリンク"):
        assert g.hits[k], k
    assert len(g.hits["文体の混在"]) == 1 and not g.hits["用紙が A4 でない"] and not g.hits["1 行の字数が多い"]
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc({**gdoc, "body": {"content": [gp("要旨", "HEADING_1"), gp("本文です。"), gp("移行の順をご確認ください", "HEADING_1"), gp("本文です。"),
                                                gp("移行は夜間にする。", "HEADING_1"), gp("本文です。")]}}, g := Report())
    assert g.hits[HEAD_POLITE] and g.hits[HEAD_PERIOD] and not any("要旨" in h for h in g.hits[HEAD_POLITE] + g.hits[HEAD_PERIOD])
    gdoc["documentStyle"]["pageSize"]["height"]["magnitude"] = 792  # レター
    gdoc["documentStyle"]["marginLeft"]["magnitude"] = 40  # 1 行 49 字
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    assert g.hits["用紙が A4 でない"] and g.hits["1 行の字数が多い"]  # 幅 595・高さ 792 は A4 でも Letter でもない
    gdoc["documentStyle"]["pageSize"]["width"]["magnitude"] = 612
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    assert g.hits["用紙が A4 でない"]  # Letter（612 × 792）も、テーマに書いていなければ A4 でない
    globals()["theme_pages"] = lambda: [(612, 792)]  # themes/docs/ に Letter のテーマがあるとき
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    globals()["theme_pages"] = lambda: []
    assert not g.hits["用紙が A4 でない"] and not g.hits["1 行の字数が多い"]  # テーマの用紙と版面なので通す
    globals()["theme_pages"] = lambda: [(595.28, 841.89)]  # A4 の用紙をテーマに書いても、A4 の文書の「1 行の字数が多い」は止めない
    gdoc["documentStyle"]["pageSize"]["width"]["magnitude"], gdoc["documentStyle"]["pageSize"]["height"]["magnitude"] = 595.28, 841.89
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    globals()["theme_pages"] = lambda: []
    assert g.hits["1 行の字数が多い"] and not g.hits["用紙が A4 でない"]
    gdoc["documentStyle"]["pageSize"]["width"]["magnitude"], gdoc["documentStyle"]["pageSize"]["height"]["magnitude"] = 612, 792  # あとの試しは Letter のまま
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report(), template=True)
    assert not g.hits["冒頭に要旨がない"]  # テンプレートから書いた文書は、節の順をテンプレートが決める
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report(), font="Arial", mono="IBM Plex Mono")  # テーマの書体（docs.py check が渡す）と比べる
    assert g.hits[FONT_NG] and not any("Arial" in x for x in g.hits[FONT_NG]) and all(FONT in x for x in g.hits[FONT_NG])  # 既定の書体の段落を出し、テーマの書体の段落は通す
    br = {"paragraph": {"elements": [{"pageBreak": {}}, {"textRun": {"content": "\n"}}], "paragraphStyle": {}}}
    body = gdoc["body"]["content"]
    i = next(k for k, e in enumerate(body) if "inlineObjectElement" in str(e))
    gdoc["body"]["content"] = body[:i + 1] + [br] + body[i + 1:]
    with contextlib.redirect_stdout(io.StringIO()):
        lint_gdoc(gdoc, g := Report())
    assert not g.hits["図の題がない"]  # すぐ後ろが改ページの図は表紙のロゴ（docs.py の cover）
    with contextlib.redirect_stdout(io.StringIO()):  # ドキュメントの段落も同じ照合。出典の行は数えない
        lint_gdoc({**gdoc, "body": {"content": [gp("要旨", "HEADING_1"), gp("一次回答が 40% 減った。"), gp("売上が 99% 増加", "HEADING_2"), gp("残りは 15% だった。"), gp("出典: 社内の集計（2026 年 9 月、12%）")]}}, g := Report(), facts="| F1 | 40% |")
    assert [h.split(": ", 1)[1] for h in g.hits[NOT_IN_FACTS]] == ["「99%」。先に出典の表へ足すか、表の値にする", "「15%」。先に出典の表へ足すか、表の値にする"], g.hits[NOT_IN_FACTS]
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if len(a) != 1 or a[0].startswith("-"):
        sys.exit(__doc__)
    sys.exit(1 if lint_gdoc(json.load(open(a[0], encoding="utf-8")), Report()) else 0)
