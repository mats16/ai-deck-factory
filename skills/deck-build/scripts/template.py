#!/usr/bin/env python3
"""AI Deck Factory のテンプレートを作る・合わせ直す（../slides.md の 3。会社のテンプレートから作る流れは ../../deck-template/SKILL.md）。
テーマは slides.py の THEMES（visual・company）と、factory.toml の [slides.themes.<名前>]（会社のテンプレート。役割の名前で色を書く）。
usage:
  template.py audit <Google Slides の URL>  元にするテンプレートを読み、ページの大きさ・マスターの配色とコントラスト・レイアウト・書体と大きさ・和文の有無を出す（変えない）
  template.py check <テーマ>                テーマの色を役割の組（PAIRS）で測り、届かない色には色相と彩度を保って明るさだけを変えた案を出す（届かない組があれば exit 1）
  template.py <テーマ>                      配色・書体・ページ番号・見本のページをテーマに合わせ直す（ID は変わらない）
  template.py <テーマ> --from-base          元のテンプレート（テーマの base、なければ factory.toml の base_template）を [drive] factory の下の Themes に複製して作り直し、URL を [slides.themes.<テーマ>] の url に書き込む
  template.py --selftest                    見本のページを、API を呼ばずに組めるかを確かめる
すでに作ったデッキは変わらない（複製した時点の写し）。"""
import colorsys, os, re, sys, time, tomllib, urllib.parse
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gapi import DRIVE, SLIDES, batch, factory, factory_path, file_id, find_factory, folder_id, request, run, trash
from lint import JA, cells, contrast, flatten, lum, paras
from slides import (BG, BLANK, CARD, DECOR, EMU, FONT, GA, INSET, NAVY, NAVY_BLOCK, OSS, PAD, PANEL, PREVIEW, RED, RED_ON_NAVY,
                    RED_SOFT, RED_TEXT, RULE, SLOTS, STAGE_TEXT, SUB, TEXT, THEMES, WHITE, W, X, Y_BODY, Y_FOOT, build, cols, make_deck, pt, rgb)
from slides import JP_FONTS, is_blank, need_brand, placeholders

THEMES_DIR = "Themes"  # テンプレートを作る Drive のフォルダ。[drive] factory の下（なければ作る）。使うテンプレートは [slides.themes.<名前>] の url で 1 つずつ指す
FOLDER = "application/vnd.google-apps.folder"
NAMES = {"visual": "テンプレート（visual: このフォルダの色）", "company": "テンプレート（company: 会社の色をコントラストだけ調整）"}
ROLES = [(NAVY, "NAVY", "扉の地・見出し・結論バンド"), (BG, "BG", "本文スライドの地"), (RED_ON_NAVY, "RED_ON_NAVY", "濃紺の上の赤（扉の小見出し）"),
         (PANEL, "PANEL", "パネル・表の 1 行おきの地"), (NAVY_BLOCK, "NAVY_BLOCK", "扉の中のブロック"), (GA, "GA", "GA の札の塗り"),
         (RED_TEXT, "RED_TEXT", "18pt 未満の赤の文字"), (PREVIEW, "PREVIEW", "Beta・Preview の札の塗り"), (SUB, "SUB", "補助の文字・フッター"),
         (OSS, "OSS", "OSS の札の塗り"), (RED, "RED", "赤のアクセント（塗り、18pt 以上）")]
FIXED = [(TEXT, "TEXT", "本文の文字", WHITE, None), (CARD, "CARD・WHITE", "カードと扉の文字", TEXT, RULE), (RULE, "RULE", "罫線と扉の補足", TEXT, None),
         (RED_SOFT, "RED_SOFT", "小さな赤の札の地", RED_TEXT, None), (STAGE_TEXT, "STAGE_TEXT", "札の文字", WHITE, None), (DECOR, "DECOR", "章番号。部品が使う", WHITE, None)]  # テーマに入れない色（色, 名前, 用途, 載せる文字, 罫線）
ON = {NAVY: WHITE, NAVY_BLOCK: WHITE, RED_TEXT: WHITE, SUB: WHITE, OSS: WHITE, BG: TEXT, PANEL: TEXT}  # 枠に載せる文字の色。ほかは札の文字の色
ROLE = {name: slot for slot, name, _ in ROLES}  # factory.toml の [slides.themes.<名前>] に書く役割の名前 → テーマの枠
# 役割の組（文字, 地, 基準, どこで使うか）。visual.md の 1・3 の組み合わせ。18pt 未満は 4.5:1、18pt 以上か 14pt 以上の太字は 3:1。visual・company はすべて届く
PAIRS = [(WHITE, NAVY, 4.5, "結論バンドの白"), (RULE, NAVY, 4.5, "濃紺の上の補足・フッター"), (RED_ON_NAVY, NAVY, 4.5, "表紙の小見出し"),
         (NAVY, BG, 4.5, "見出し・カードの見出し"), (NAVY, PANEL, 4.5, "パネルの見出し"), (NAVY, CARD, 4.5, "白いカードの見出し"),
         (TEXT, BG, 4.5, "本文"), (TEXT, PANEL, 4.5, "パネルの本文"), (SUB, BG, 4.5, "出典・フッター"), (SUB, PANEL, 4.5, "パネルの補足"),
         (SUB, CARD, 4.5, "カードの補足"), (RED_TEXT, BG, 4.5, "キッカー"), (RED_TEXT, PANEL, 4.5, "パネルの赤の文字"), (RED_TEXT, CARD, 4.5, "カードの赤の文字"),
         (RED_TEXT, RED_SOFT, 4.5, "淡い赤の札"), (RED, BG, 3.0, "18pt 以上の赤の文字"), (WHITE, RED, 3.0, "赤の塗りの 14pt 以上の太字"),
         (WHITE, NAVY_BLOCK, 4.5, "扉の中のブロックの白"), (RULE, NAVY_BLOCK, 4.5, "扉の中のブロックの補足"), (STAGE_TEXT, GA, 4.5, "GA の札"),
         (STAGE_TEXT, PREVIEW, 4.5, "Beta・Preview の札"), (WHITE, OSS, 4.5, "OSS の札")]
NO_RENDER = {"Noto Sans CJK JP", "Hiragino Sans", "Yu Gothic"}  # API は受け付けるが、描くと明朝と欧文のセリフ体になる（Google Fonts にない）
PAGE = (13.333, 7.5)  # slides.py の版面（in）。違う大きさのテンプレートには組めない


def page_ok(size):
    """presentations の pageSize が PAGE か。"""
    return all(abs(size[k]["magnitude"] / EMU - v) < 0.02 for k, v in zip(("width", "height"), PAGE))


def themes():
    """factory.toml の [slides.themes]（会社のテンプレートのテーマ）。"""
    return factory().get("slides", {}).get("themes", {}) if find_factory() else {}


def colors(theme):
    """テーマの 12 の枠の色。factory.toml のテーマは役割の名前で書き、書かない役割は visual の値にする。"""
    if theme in THEMES:
        if bad := set(themes().get(theme, {})) - {"url", "description", "base"}:  # 色は組み込みのまま、font だけが効いてしまう
            sys.exit(f"[slides.themes.{theme}] は組み込みのテーマ（slides.py の THEMES）。url・description・base のほか（{', '.join(sorted(bad))}）は書けない。会社の色なら別の名前のテーマにする")
        return THEMES[theme]
    if (t := themes().get(theme)) is None:
        sys.exit(f"テーマ {theme} がない（slides.py の THEMES にも、factory.toml の [slides.themes] にもない）")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", theme):  # [slides.themes.<名前>] の表の名前に、引用符なしで書き込む（set_url）
        sys.exit(f"テーマの名前 {theme!r} は英数字と - _ だけにする")
    if bad := set(t) - set(ROLE) - {"base", "font", "url", "description"}:
        sys.exit(f"[slides.themes.{theme}] に知らない名前: {', '.join(sorted(bad))}（色は役割の名前 {', '.join(ROLE)} で書く）")
    if bad := [k for k, v in t.items() if k in ROLE and not re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(v))]:
        sys.exit(f"[slides.themes.{theme}] の {', '.join(bad)} が 6 桁の 16 進の色でない（例: NAVY = \"002B5C\"）")
    if t.get("font", FONT) not in JP_FONTS:  # ほかの書体は、和文が別の書体になるか、描けない。deck_font も FONT に戻す
        sys.exit(f"[slides.themes.{theme}] の font {t['font']!r} は、和文を描けると確かめた書体（slides.py の JP_FONTS）にない。deck-template の SKILL.md の「書体」から選ぶ")
    return {**THEMES["visual"], **{ROLE[k]: v.lstrip("#").upper() for k, v in t.items() if k in ROLE}}


def shift(c, other, need):
    """c の色相と彩度を保ち、明るさだけを変えて、other とのコントラストを need に届かせた色（6 桁）。暗くする・明るくするの両方を試し、
    届くほうのうち明るさの変化の小さいものを返す（濃紺の上の赤のように、地と近い色はどちらにも動かせる）。どちらも届かなければ、比の高いほう。"""
    h, l0, s = colorsys.rgb_to_hls(*(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)))

    def walk(step):
        l, x = l0, c
        while contrast(x, other) < need and (l > 0 if step < 0 else l < 1):
            l = min(1.0, max(0.0, l + step))
            x = "".join(f"{round(v * 255):02X}" for v in colorsys.hls_to_rgb(h, l, s))
        return x, abs(l - l0)

    def rank(cand):
        x, moved = cand
        return (0, moved) if contrast(x, other) >= need else (1, -contrast(x, other))

    return min((walk(-0.005), walk(0.005)), key=rank)[0]


def fix(T):
    """T（12 の枠）を PAIRS で測り、届かない組の色を shift で直す。直すのは、文字がテーマの枠ならその文字の色、文字が固定の色なら地の色。
    戻りは（直した T、[(どこ, 枠, 前, 後, 前の比, 後の比)]）。"""
    T, out = dict(T), []
    for _ in range(3):  # 1 つの枠を直すと、ほかの組の比が変わることがある
        for fg, gr, need, use in PAIRS:
            if (r := contrast(T.get(fg, fg), T.get(gr, gr))) >= need:
                continue
            slot, other = (fg, T.get(gr, gr)) if fg in T else (gr, fg)
            old, T[slot] = T[slot], shift(T[slot], other, need)
            if T[slot] != old:  # 動かせなかった枠は、check が「届かない」に出す
                out.append((use, slot, old, T[slot], r, contrast(T.get(fg, fg), T.get(gr, gr))))
    return T, out


def check(theme):
    """テーマの役割の組のコントラストと、届かない色の直す案を出す。すべて届けば True。"""
    T = colors(theme)
    F, out = fix(T)
    name = {**{c: n for c, n, *_ in FIXED}, **{slot: n for n, slot in ROLE.items()}}
    print(f"テーマ {theme} の役割の組（文字 / 地、比 / 基準）")
    for fg, gr, need, use in PAIRS:
        r = contrast(T.get(fg, fg), T.get(gr, gr))
        print(f"  {'OK' if r >= need else 'NG'}  {use}: {name.get(fg, fg)} {T.get(fg, fg)} / {name.get(gr, gr)} {T.get(gr, gr)}  {r:.2f}:1 / {need:g}:1")
    if out:
        print(f"\n直す案（色相と彩度を保ち、明るさだけを変えた。ユーザーに見せてから factory.toml の [slides.themes.{theme}] に写す）:")
        for slot in dict.fromkeys(o[1] for o in out):
            old, new = next(o[2] for o in out if o[1] == slot), F[slot]
            print(f'  {name[slot]} = "{new}"  # {old} から{"暗く" if lum(new) < lum(old) else "明るく"}した（{"、".join(dict.fromkeys(o[0] for o in out if o[1] == slot))}）')
    for fg, gr, need, use in PAIRS:  # 明るさだけでは届かない組（白か黒まで動かしても届かない、ほかの組と同じ枠を取り合うなど）。当てる色を替える
        if (r := contrast(F.get(fg, fg), F.get(gr, gr))) < need:
            print(f"  直す案でも届かない: {use}（{r:.2f}:1 / {need:g}:1）。役割に当てる色を替える")
    return all(contrast(T.get(fg, fg), T.get(gr, gr)) >= need for fg, gr, need, _ in PAIRS)


def runs(page, empty=False):
    """ページ（マスター・レイアウト・スライド）の (要素, 文字, 書式) を、グループと表の中までたどって返す。empty なら空の連なりも（マスターのプレースホルダーは改行だけ）。"""
    for e, _ in flatten(page.get("pageElements", [])):
        for text, _ in cells(e):
            for _, rs in paras(text):
                for t, st in rs:
                    if empty or t.strip():
                        yield e, t, st


def audit(url):
    """元にするテンプレートを読み、テーマを決める材料を Markdown で出す（変えない）。"""
    p = request("GET", f"{SLIDES}/{file_id(url)}")
    w, h = (p["pageSize"][k]["magnitude"] / EMU for k in ("width", "height"))
    out = [f"# {p.get('title', '')}", "", f"- ページの大きさ: {w:.2f} × {h:.2f} in" + ("" if page_ok(p["pageSize"]) else
           f"。slides.py は {PAGE[0]:.2f} × {PAGE[1]} in でしか組めない。複製を画面の「ファイル → ページ設定 → カスタム」で {PAGE[0]:.2f} × {PAGE[1]} インチにし、その URL で audit し直す")]
    used = Counter(s.get("slideProperties", {}).get("masterObjectId") for s in p.get("slides", []))
    out.append(f"- ページ: {len(p.get('slides', []))} 枚。マスター {len(p['masters'])} 個、レイアウト {len(p['layouts'])} 個")
    for m in p["masters"]:
        sch = {c["type"]: "".join(f"{round(c['color'].get(k, 0) * 255):02X}" for k in ("red", "green", "blue"))
               for c in m.get("pageProperties", {}).get("colorScheme", {}).get("colors", [])}
        out += ["", f"## マスター「{m['masterProperties']['displayName']}」（{used[m['objectId']]} 枚が使う）", "",
                "| 枠 | 色 | 白の上 | LIGHT1 の上 | DARK1 の上 |", "|---|---|---|---|---|"]
        for k in SLOTS:
            c = sch.get(k)
            if c:
                out.append(f"| {k} | `{c}` | " + " | ".join(f"{contrast(c, g):.2f}" for g in ("FFFFFF", sch.get("LIGHT1", "FFFFFF"), sch.get("DARK1", "000000"))) + " |")
        out += ["", "| レイアウト | プレースホルダー |", "|---|---|"]  # slides.py が使えるのは、ページ番号の枠だけのもの（is_blank）
        for l in (l for l in p["layouts"] if l["layoutProperties"].get("masterObjectId") == m["objectId"]):
            ph = placeholders(l)
            out.append(f"| {l['layoutProperties']['displayName']} | {', '.join(ph) or 'なし'}" + ("（slides.py が使える Blank）" if is_blank(l) else "") + " |")
    fonts, sizes, ja, latin = Counter(), {}, 0, 0
    for pg in p["masters"] + p["layouts"]:
        for e, t, st in runs(pg, empty=True):
            ph = e.get("shape", {}).get("placeholder", {}).get("type")
            if st.get("fontFamily"):
                fonts[st["fontFamily"]] += 1
            if ph and (sz := st.get("fontSize", {}).get("magnitude")):
                sizes.setdefault(ph, set()).add(sz)
    for s in p.get("slides", []):
        for e, t, st in runs(s):
            fonts[st.get("fontFamily", "（継承）")] += 1
            if re.search(f"[{JA}]", t):
                ja += 1
            else:
                latin += 1
    kind = lambda f: "和文あり（Google Fonts）" if f in JP_FONTS else "描けない（別の書体になる）" if f in NO_RENDER else "和文がない欧文の書体か、確かめていない書体"
    out += ["", "## 書体", "", "| 書体 | 使っている文字の連なり | 和文 |", "|---|---|---|"]
    out += [f"| {f} | {n} | {kind(f) if f != '（継承）' else ''} |" for f, n in fonts.most_common()]
    out += ["", "## プレースホルダーの文字の大きさ（マスターとレイアウト）", ""] + [f"- {k}: {', '.join(f'{v:g}pt' for v in sorted(vs))}" for k, vs in sorted(sizes.items())]
    out += ["", "## 和文の有無", "", f"- ページの文字の連なり: 和文を含む {ja}、含まない {latin}" + ("。英語だけのテンプレート（deck-template の B）" if latin and not ja else "")]
    print("\n".join(out))


def specimen(theme):
    """テンプレートの見本のページ。テーマの色と部品を一通り、決まり（visual.md）どおりの使い方で置く（色の確かめと、部品を直したときの確かめに使う）。"""
    T = colors(theme)
    docs = "https://developers.google.com/workspace/slides"  # 出典の行の見本のリンク。どの会社のテンプレートにも入るので、会社に結びつかない公開のページ

    def make(d):
        s = d.cover(f"テーマ「{theme}」の見本", f"社内｜{time.strftime('%Y-%m-%d')}", "AI Deck Factory のテンプレート")
        d.note(s, "表紙です。小見出しは相手と日付、タイトルは白、副題と小見出しは濃紺の上の赤、社名は罫線の色です。表紙にはページ番号を置きません。")

        s = d.divider("01", "色と部品", "テーマの色の役割と、本文ページの部品")
        d.card(s, X, 5.0, 2.4, 0.85, None, body=[("扉の中のブロック\n", {"bold": True, "color": WHITE}), ("白と罫線の色だけを載せる", {"color": RULE})],
               fill=NAVY_BLOCK, line=None)
        d.note(s, "章の扉です。章番号は飾りの色で、コントラストの基準の外です。扉の中のブロックには、白と罫線の色だけを載せます。濃紺の上の赤は、ブロックの上ではコントラストが届きません。")

        s = d.page("色は役割の名前で選び、値はテーマが決める", "濃い色の枠には白か札の文字、淡い色の枠には本文の色を載せる。", kicker="早見表")
        cw, ch, gap = (W - 3 * 0.2) / 4, 1.0, 0.2
        for i, (slot, name, use) in enumerate(ROLES):
            x, y = X + (i % 4) * (cw + gap), Y_BODY + (i // 4) * (ch + 0.15)
            d.box(s, x, y, cw, ch, slot, RULE if slot == BG else None)  # BG は地と同じ色なので、見本だけ罫線を付ける
            d.text(s, x + PAD, y + PAD, cw - 2 * PAD, ch - 2 * PAD, [(f"{name}（{slot}）\n", {"bold": True}), f"{T[slot]}\n", use],
                   color=ON.get(slot) or max((STAGE_TEXT, WHITE), key=lambda c: contrast(c, T[slot])), spacing=115)
        d.text(s, X + 3 * (cw + gap) + PAD, Y_BODY + 2 * (ch + 0.15) + PAD, cw - 2 * PAD, ch - 2 * PAD,
               [("テーマに入れない色（下の段）\n", {"bold": True}), "pages.py に 6 桁で書く\nテーマを替えても変わらない"], spacing=115)
        for (x, w), (hexc, name, use, fg, line) in zip(cols(6, 0.2), FIXED):
            y = Y_BODY + 3 * ch + 2 * 0.15 + 0.2
            d.box(s, x, y, w, ch, hexc, line)
            d.text(s, x + PAD, y + PAD, w - 2 * PAD, ch - 2 * PAD, [(f"{name}\n", {"bold": True}), f"{hexc}\n", use], color=fg, spacing=115)
        d.source(s, ["出典: visual.md の 1（色の決まり）。ページの大きさとマスターは ", ("元のテンプレート", {"link": base(theme)})])
        d.note(s, f"テーマ「{theme}」の 11 の枠と、テーマに入れない 6 つの色です。キッカーは、このページのように役割を示すときだけ置きます。"
                  "BG は地と同じ色なので、見本だけ罫線を付けています。値は pages.py に書く形（# を付けない 6 桁）です。DECOR は slides.py の章の扉が使い、pages.py には書きません。")

        s = d.page("部品は役割の色で塗り、大きさと間隔は既定に従う", "カード、パネル、数字、札、正円の番号、表、矢印、結論バンド、出典の行の見本。")
        hw = (W - 0.3) / 2
        d.card(s, X, Y_BODY, hw, 1.5, "カードの見出し（12pt 太字）", body=["本文は 11pt。", ("強調は太字", {"bold": True}), "。\n",
                                                                  ("赤の文字", {"color": RED_TEXT, "bold": True}), "は 18pt 未満でも読める色。\n",
                                                                  ("リンク", {"link": docs}), "は周りの色のまま下線を付ける。"])
        d.text(s, X - INSET, 3.4, hw + 2 * INSET, 0.65, [("32", {"size": 32, "bold": True, "color": NAVY}), ("%", {"size": 16, "bold": True, "color": NAVY}),
                                                        ("  数字 32pt・単位 16pt。赤にするなら RED", {"color": SUB})])
        d.card(s, X, 4.18, hw, 0.8, None, body=[("パネル\n", {"bold": True}), "塗りだけで囲み、枠線は付けない。"], fill=PANEL, line=None)
        for i, (label, fill, fg) in enumerate([("GA", GA, STAGE_TEXT), ("Beta", PREVIEW, STAGE_TEXT), ("OSS", OSS, WHITE)]):
            d.text(s, X + i * 0.95, 5.13, 0.8, 0.4, label, color=fg, bold=True, align="CENTER", valign="MIDDLE", fill=fill)
        d.text(s, X + 3.2, 5.13, 0.8, 0.4, "推奨", color=RED_TEXT, bold=True, align="CENTER", valign="MIDDLE", fill=RED_SOFT)  # 提供ステージの札と離す（赤と緑を並べない）
        for n, (size, cx) in enumerate((("S", 4.35), ("M", 4.85), ("L", 5.45)), 1):  # 正円の番号の 3 つの大きさ（slides.py の NUM）。札と中心をそろえる
            d.num(s, n, X + cx, 5.33, size)
        rx = X + hw + 0.3
        tb = d.table(s, rx, Y_BODY, [1.6, hw - 1.6], [["役割", "使うところ"], ["NAVY", "見出し、扉、結論バンド、表の見出しの行"], ["SUB", "出典、フッター、補足"],
                                                 ["RED_TEXT", "キッカー、18pt 未満の強調"], ["RED", "番号の丸、図形の塗り、太い線"]], row_h=0.4)
        d.box(s, rx, Y_BODY, 1.6, tb - Y_BODY, line=RED, kind="ROUND_RECTANGLE")  # 表の 1 列の強調。赤の線は既定で 2pt（2026-10-08、ユーザー）
        for bx, label in ((rx, "箱 A"), (rx + hw - 2.4, "箱 B")):
            d.text(s, bx, 4.18, 2.4, 0.8, label, align="CENTER", valign="MIDDLE", fill=CARD, line=RULE)
        d.arrow(s, rx + 2.48, 4.58, rx + hw - 2.48, 4.58)
        d.band(s, "結論バンド: 言いたいことを 1 文（13pt 太字）", "補足は 11pt の罫線の色。下端は 6.60 in に固定。")
        d.source(s, ["出典: ", ("Google Slides API のドキュメント", {"link": docs}), "（URL へのリンクの例）、", ("p.3 の早見表", {"link": 3}), "（ページへのリンクの例）"])
        d.note(s, "部品の見本です。カード、パネル、大きな数字、札、正円の番号（小・中・大の 3 つ）、表と 1 列の強調の囲み（赤の 2pt）、矢印、結論バンド、出典の行を置いています。"
                  "結論バンドは、だから何をするかを言うページにだけ置きます。")

        s = d.page("並べ方は中身で選び、まとまりは塗りのない囲みで示す", "見出しと説明の組は items、短い並びは bullets にし、白いカードだけ薄い罫線を付ける。")
        d.card(s, X, Y_BODY, hw, 4.2, "項目のカード（items）", items=[
            ("items", "見出しと説明の組を、step の間隔で並べる"), ("step", "既定は 0.95 in。説明が 2 行になるなら広げる"),
            ("縦の並び", "見出しと説明は 1 つの枠に入れ、改行で分ける"), ("横の並び", "横に並ぶカードは y・h・valign をそろえる")])
        d.card(s, rx, Y_BODY, hw, 1.5, "箇条書き（bullets）", body="短い項目を並べるときに使う\n1 つの枠の本文は 8 行まで\n字下げは文字の大きさの 1.3 倍", bullets=True)
        y0 = 3.48
        d.box(s, rx, y0, hw, 1.55, line=SUB, kind="ROUND_RECTANGLE")  # 塗りのない角丸は辺と弧を線でつなぐ。継ぎ目の段をここで見る（slides.md の 5）
        d.text(s, rx + PAD, y0 + 0.1, hw - 2 * PAD, 0.34, "塗りのない角丸の囲み（まとまりを示す）", size=12, color=NAVY, bold=True)
        for (x, w), label in zip(cols(2, 0.24, rx + 0.2, hw - 0.4), ("部品 A", "部品 B")):
            d.text(s, x, y0 + 0.55, w, 0.8, label, align="CENTER", valign="MIDDLE", fill=PANEL)
        y1 = 5.2  # 強調の赤い点線の囲み。中のカードと同じ半径（Google 標準の角丸にしない）で、線は赤の既定の 2pt（2026-10-08、ユーザー）
        d.box(s, rx, y1, hw, 1.3, line=RED, kind="ROUND_RECTANGLE", dash=True)
        d.card(s, rx + 0.12, y1 + 0.12, hw - 0.24, 1.06, "強調の点線の囲み（dash=True。赤の線は 2pt）", body="重なる範囲や、見てほしいところを囲む。角は中のカードと同じ丸み")
        d.note(s, "項目のカード、箇条書き、塗りのない角丸の囲み、強調の点線の囲みの見本です。塗りのない角丸の囲みは辺と弧を線でつないで描くので、"
                  "部品を直したら、継ぎ目に段が出ていないかと、点線の囲みの角が中のカードと同じ丸みになっているかを、ここで見ます。")

    return make_deck(make, f"AI Deck Factory｜テーマ「{theme}」の見本")


def base(theme):
    """元にするテンプレートの URL。テーマの base、なければ factory.toml の [slides] base_template（2026-10-12 までの書き方。組み込みのテーマにも base を書ける）。"""
    return themes().get(theme, {}).get("base") or factory().get("slides", {}).get("base_template", "")


def pick(p):
    """残すマスター（いちばん多くのページが使うもの。同じなら先のもの）と、slides.py が使うレイアウトを選ぶ。レイアウトは、そのマスターの、
    プレースホルダーがページ番号の枠だけのもの（slides.py の is_blank）。名前が BLANK のもの、型が BLANK のものの順に先にする。"""
    used = Counter(s.get("slideProperties", {}).get("masterObjectId") for s in p.get("slides", []))
    master = max(p["masters"], key=lambda m: used[m["objectId"]])
    ls = [l for l in p["layouts"] if l["layoutProperties"].get("masterObjectId") == master["objectId"]]
    cands = sorted(filter(is_blank, ls), key=lambda l: (l["layoutProperties"]["displayName"] != BLANK, l["layoutProperties"].get("name") != "BLANK"))
    if not cands:
        sys.exit(f"マスター「{master['masterProperties']['displayName']}」に、プレースホルダーがページ番号の枠だけのレイアウトがない。元のテンプレートを複製し、"
                 "画面のテーマビルダーで Blank のレイアウトを作るか、Blank のレイアウトにスライド番号のプレースホルダーを足して、その URL を base にする")
    return master, cands[0]


def strip(pid, p, master, blank):
    """元のテンプレートの複製から、残すマスターとレイアウト（pick）のほかを消す。"""
    # 見本のページを消す前に 1 枚作っておく。ページが 0 枚になると、使われていないマスターごと消える
    batch(pid, [{"createSlide": {"objectId": "keep_slide", "slideLayoutReference": {"layoutId": blank["objectId"]}}}]
          + [{"deleteObject": {"objectId": s["objectId"]}} for s in p["slides"]])
    dels = [l["objectId"] for l in p["layouts"] if l is not blank] + [m["objectId"] for m in p["masters"] if m is not master]
    # マスターの著作権の行とロゴ、Blank の全面の四角（ページの地を覆う）など、プレースホルダーでないもの。フッターは slides.py が書く
    dels += [e["objectId"] for pg in (master, blank) for e in pg.get("pageElements", []) if "placeholder" not in e.get("shape", {})]
    batch(pid, [{"deleteObject": {"objectId": o}} for o in dels])


def styles(theme, master, blank):
    """配色、プレースホルダーの書体、ページ番号の枠（11pt・SUB。右端を本文の右端に、上端を著作権表示の文字にそろえる。この枠は内側の余白が 0）。"""
    reqs = [{"updatePageProperties": {"objectId": master["objectId"], "pageProperties": {"colorScheme": {"colors": [
        {"type": k, "color": rgb(colors(theme)[k])} for k in SLOTS]}}, "fields": "colorScheme.colors"}}]
    font = themes().get(theme, {}).get("font", FONT)
    for e in (e for pg in (master, blank) for e in pg.get("pageElements", [])):
        ph = e.get("shape", {}).get("placeholder", {}).get("type")
        if not ph:
            continue
        reqs.append({"updateTextStyle": {"objectId": e["objectId"], "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}})
        if ph == "SLIDE_NUMBER":
            size = e["size"]
            reqs += [{"updatePageElementTransform": {"objectId": e["objectId"], "applyMode": "ABSOLUTE", "transform": {
                         "scaleX": 1.0 * EMU / size["width"]["magnitude"], "scaleY": 0.28 * EMU / size["height"]["magnitude"],
                         "translateX": round((X + W - 1.0) * EMU), "translateY": round((Y_FOOT + INSET) * EMU), "unit": "EMU"}}},
                     {"updateShapeProperties": {"objectId": e["objectId"], "shapeProperties": {"contentAlignment": "TOP"}, "fields": "contentAlignment"}},
                     {"updateTextStyle": {"objectId": e["objectId"], "textRange": {"type": "ALL"},
                                          "style": {"fontSize": pt(11), "foregroundColor": {"opaqueColor": {"themeColor": SUB}}}, "fields": "fontSize,foregroundColor"}}]
    return reqs


def themes_folder():
    """[drive] factory の下の Themes フォルダの ID。なければ作る（フォルダの ID や URL は factory.toml に持たない）。"""
    if not (root := factory().get("drive", {}).get("factory")):
        sys.exit(f"factory.toml の [drive] factory（個人の資料の根元）がない。テンプレートはその下の {THEMES_DIR} に作る")
    parent = folder_id(root)
    q = urllib.parse.quote(f"name = '{THEMES_DIR}' and '{parent}' in parents and mimeType = '{FOLDER}' and trashed = false")
    found = request("GET", f"{DRIVE}/files?q={q}&fields=files(id)&supportsAllDrives=true&includeItemsFromAllDrives=true")["files"]
    if found:
        return found[0]["id"]
    return request("POST", f"{DRIVE}/files?supportsAllDrives=true&fields=id", {"name": THEMES_DIR, "mimeType": FOLDER, "parents": [parent]})["id"]


def template(theme, from_base=False):
    """テンプレートを作る（from_base）か、合わせ直す。Drive に複製する・テンプレートを書き換える前に、要るものを全部確かめる
    （テーマの色、[brand] copyright、作るときは factory.toml に url を書けるか）。作るときは、組んだあとに url を factory.toml に書く。
    複製したあとで止まったら（url を書けなかったときも）、複製をゴミ箱に移す。"""
    colors(theme)  # 知らないテーマ・書けない値なら止まる
    need_brand()  # 見本のページ（build）に著作権表示を書く
    if from_base:
        record(theme)  # factory.toml に url を書けるか（書けないのに複製を残さない）
    src = file_id(base(theme))
    if from_base:
        if not src:
            sys.exit(f"元のテンプレートがない。factory.toml の [slides.themes.{theme}] の base に URL を書く")
        if not page_ok(request("GET", f"{SLIDES}/{src}?fields=pageSize")["pageSize"]):
            sys.exit(f"元のテンプレートのページが {PAGE[0]:.2f} × {PAGE[1]} in でない。template.py audit {base(theme)} の指示どおりに直す")
        pid = request("POST", f"{DRIVE}/files/{src}/copy?supportsAllDrives=true&fields=id",
                      {"name": NAMES.get(theme, f"テンプレート（{theme}）"), "parents": [themes_folder()]})["id"]
    elif url := themes().get(theme, {}).get("url"):
        pid = file_id(url)
    else:
        sys.exit(f"factory.toml の [slides.themes.{theme}] に url がない。template.py {theme} --from-base で作る")
    try:
        p = request("GET", f"{SLIDES}/{pid}")
        master, blank = pick(p)
        if from_base:
            strip(pid, p, master, blank)
        batch(pid, styles(theme, master, blank))
        build(pid, specimen(theme), force=True)  # 直前に配色を変えているので、版の確かめはしない
        if from_base:
            record(theme, pid)  # 書けずに止まったときも、下で複製を片付ける
    except BaseException:
        if from_base:  # 作りかけの複製を残さない（factory.toml にも書いていない）
            trash(pid)
            print(f"作れなかったので、複製 {pid} をゴミ箱に移した", file=sys.stderr)
        raise
    return pid


def set_url(text, theme, url):
    """factory.toml の文字列の [slides.themes.<theme>] の url の行を url にする（なければ表の頭に足し、表もなければファイルの最後に足す）。コメントと並びはそのまま。"""
    text = text if text.endswith("\n") else text + "\n"  # 見出しがファイルの最後の行でも見つける
    m = re.search(rf"^\[slides\.themes\.{re.escape(theme)}\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.S | re.M)
    if not m:
        return text.rstrip("\n") + f'\n\n[slides.themes.{theme}]\nurl = "{url}"\n'
    body = m.group(1)
    line = re.compile(r'^url\s*=\s*"[^"]*"', re.M)
    body = line.sub(f'url = "{url}"', body, count=1) if line.search(body) else f'url = "{url}"\n' + body
    return text[:m.start(1)] + body + text[m.end(1):]


def record(theme, pid=None):
    """作ったテンプレートの URL を factory.toml に書く。書いたあとの TOML が読めて、url が入っていることを確かめてから書く（壊さない）。
    pid が None なら、書けるかだけを確かめる（--from-base で複製する前に呼ぶ。書けないのに Drive に複製を残さない）。"""
    p, url = factory_path(), f"https://docs.google.com/presentation/d/{pid or 'CHECK'}/edit"
    text = set_url(p.read_text(), theme, url)
    try:
        ok = tomllib.loads(text)["slides"]["themes"][theme]["url"] == url
    except (tomllib.TOMLDecodeError, KeyError):
        ok = False
    if not ok:
        sys.exit(f"factory.toml の [slides.themes.{theme}] に url を書けない（見出しの書き方が違うかもしれない。[slides.themes.{theme}] の形にする）"
                 + (f"。作ったテンプレートは {url}。手で url = \"{url}\" を書く" if pid else "。テンプレートはまだ作っていない"))
    if pid:
        p.write_text(text)


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        for theme in [*THEMES, *themes()]:
            d = specimen(theme)
            assert len(d.slides) == 5 and not d.images and all(s in d.notes for s in d.slides)
        assert all(not fix(T)[1] for T in THEMES.values())  # 組み込みのテーマは、役割の組がすべて届く
        F, out = fix({**THEMES["company"], SUB: "618794"})  # 2026 年版の Databricks Theme の ACCENT5。Oat Medium の上で 3.32:1
        assert {o[1] for o in out} == {SUB} and F[SUB] == "51707C"  # 同じ青緑のまま暗くする（手で選んだ company の 50707B とほぼ同じ）
        assert contrast(shift("FFFFFF", "FFFFFF", 4.5), "FFFFFF") >= 4.5  # 同じ色からでも離す
        assert contrast(shift("4A5A70", "5A6E8C", 4.5), "5A6E8C") >= 4.5  # 暗くしても届かない色は明るくする
        F, out = fix({**THEMES["visual"], NAVY: "1F6FB2", RED_ON_NAVY: "B22222"})  # 中くらいの青の NAVY に、RED をそのまま写した RED_ON_NAVY
        assert contrast(F[RED_ON_NAVY], F[NAVY]) >= 4.5 and lum(F[RED_ON_NAVY]) > lum("B22222") and len({o[1] for o in out}) == len(out)
        sn = {"shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}
        lay = lambda i, m, *els, name="": {"objectId": i, "layoutProperties": {"masterObjectId": m, "displayName": i, "name": name}, "pageElements": list(els)}
        p = {"masters": [{"objectId": "a"}, {"objectId": "b"}], "slides": [{"slideProperties": {"masterObjectId": "b"}}],
             "layouts": [lay("a1", "a", sn), lay(BLANK, "b", sn, {"shape": {"placeholder": {"type": "TITLE"}}}), lay("b1", "b", sn), lay("b2", "b", sn, name="BLANK")]}
        assert [x["objectId"] for x in pick(p)] == ["b", "b2"]  # ページが使うマスターの、ページ番号の枠だけのレイアウト（名前が BLANK でも枠が多ければ使わない。型が BLANK を先に）
        assert page_ok({"width": {"magnitude": 12192000}, "height": {"magnitude": 6858000}}) and not page_ok({"width": {"magnitude": 9144000}, "height": {"magnitude": 5143500}})
        md = "# 設定\n[slides.themes.visual]  # 注\nurl = \"a\"  # 書き込む\ndescription = \"d\"\n\n[slides.themes.acme]\nNAVY = \"002B5C\"\n\n[drive]\nx = 1\n"
        assert set_url(md, "visual", "b") == md.replace('"a"', '"b"')  # url の行を書き換え、ほかは変えない
        assert '[slides.themes.acme]\nurl = "c"\nNAVY' in set_url(md, "acme", "c")  # url のない表は、表の頭に足す
        assert set_url(md, "company", "c").endswith('x = 1\n\n[slides.themes.company]\nurl = "c"\n')  # 表がなければ最後に足す
        assert tomllib.loads(set_url("[slides.themes.acme]", "acme", "c"))["slides"]["themes"]["acme"] == {"url": "c"}  # 見出しがファイルの最後の行（改行なし）でも
        quoted = md.replace("[slides.themes.acme]", '[slides.themes."acme"]')  # 引用符付きの見出しは見つけられず、同じ表を足す。record が書く前に止める
        try:
            tomllib.loads(set_url(quoted, "acme", "c"))
            raise AssertionError("同じ表が 2 つあっても読めてしまった")
        except tomllib.TOMLDecodeError:
            pass
        assert tomllib.loads(set_url(set_url(md, "acme", "c"), "company", "e"))["slides"]["themes"]["acme"] == {"url": "c", "NAVY": "002B5C"}
        return print("selftest ok")
    if a[:1] in (["audit"], ["check"]) and len(a) != 2:
        sys.exit(__doc__)
    if a[:1] == ["audit"]:
        return audit(a[1])
    if a[:1] == ["check"]:
        return sys.exit(0 if check(a[1]) else 1)
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    pid = template(a[0], "--from-base" in a)  # 要るものの確かめは template() の頭、url を書くのは template() の中
    print(f"テンプレート {a[0]}: {pid}" + (f"  （{factory_path()} の [slides.themes.{a[0]}] の url に書いた）" if "--from-base" in a else ""))


if __name__ == "__main__":
    run(main)
