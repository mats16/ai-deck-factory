#!/usr/bin/env python3
"""AI Deck Factory のテンプレートを作る・合わせ直す（../slides.md の 3。会社のテンプレートから作る流れは ../../deck-template/SKILL.md）。
テーマは slides.py の THEMES（visual・company）と、factory.toml の [slides.themes.<名前>]（会社のテンプレート。役割の名前で色を書く）。
usage:
  template.py audit <Google Slides の URL>  元にするテンプレートを読み、ページの大きさ・マスターの配色とコントラスト・レイアウト・書体と大きさ・和文の有無を出す（変えない）
  template.py check <テーマ>                テーマの色を役割の組（PAIRS）で測り、届かない色には色相と彩度を保って明るさだけを変えた案を出す（届かない組があれば exit 1）
  template.py <テーマ>                      配色・書体・ページ番号・見本のページをテーマに合わせ直す（ID は変わらない）
  template.py <テーマ> --from-base          元のテンプレート（テーマの base、なければ factory.toml の base_template、なければ白紙の BLANK_PPTX）を [drive] factory の下の Themes に複製して作り直し、
                                            URL を [slides.themes.<テーマ>] の url に書き込む
作ったテンプレートには、Drive の説明に description を、プロパティにテーマの名前と組むときに引く値を書く（slides.py の PROP）。ほかの人は url を書くだけで、同じ値で組める。
全社の共有テーマのフォルダ（[drive] shared_themes）に置くと、slides.py themes がほかの人に候補として出す。
  template.py --selftest                    見本のページを、API を呼ばずに組めるかを確かめる
すでに作ったデッキは変わらない（複製した時点の写し）。"""
import colorsys, os, re, sys, time, tomllib, urllib.parse, zipfile
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gapi import DRIVE, GSLIDES, PPTX, SLIDES, batch, factory, factory_path, file_id, find_factory, folder_id, request, run, trash, upload
from lint import JA, cells, contrast, flatten, lum, paras, solid
from slides import (BG, BLANK, CARD, COPYRIGHT_PT, DECOR, EMU, FONT, GA, HEAD, INSET, NAVY, NAVY_BLOCK, ON_RED, OSS, PAD, PANEL, PREVIEW, RED, RED_ON_NAVY,
                    RED_SOFT, RED_TEXT, RULE, SLOTS, STAGE_TEXT, SUB, SUB_ON_NAVY, TEXT, THEMES, WHITE, W, X, Y_BODY, Y_FOOT, build, cols, make_deck, number_style, rgb)
from slides import FIXED as FIXED_DEFAULT, JP_FONTS, LAYOUT_MARK, NAMED, PROP, PUBLISHED, THEME_MARK, THEME_PROP, VARIANTS, is_blank, need_brand, placeholders, theme_fixed, theme_font, use_layouts, use_theme

BLANK_PPTX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "blank.pptx")  # base がないときの元。中身は ../assets/README.md
THEMES_DIR = "Themes"  # テンプレートを作る Drive のフォルダ。[drive] factory の下（なければ作る）。使うテンプレートは [slides.themes.<名前>] の url で 1 つずつ指す
FOLDER = "application/vnd.google-apps.folder"
NAMES = {"visual": "テンプレート（visual: このフォルダの色）", "company": "テンプレート（company: 会社の色をコントラストだけ調整）"}
ROLES = [(NAVY, "NAVY", "表紙・扉の地・結論バンド・表の見出しの行"), (BG, "BG", "本文スライドの地"), (RED_ON_NAVY, "RED_ON_NAVY", "濃紺の上の赤（扉の小見出し）"),
         (PANEL, "PANEL", "パネル・表の 1 行おきの地"), (NAVY_BLOCK, "NAVY_BLOCK", "扉の中のブロック"), (GA, "GA", "GA の札の塗り"),
         (RED_TEXT, "RED_TEXT", "18pt 未満の赤の文字"), (PREVIEW, "PREVIEW", "Beta・Preview の札の塗り"), (SUB, "SUB", "補助の文字・フッター"),
         (OSS, "OSS", "OSS の札の塗り"), (RED, "RED", "赤のアクセント（塗り、18pt 以上）")]
FIXED = [(TEXT, "TEXT", "本文の文字", WHITE, None), (HEAD, "HEAD", "本文のページの見出し", WHITE, None), (CARD, "CARD", "カードと表のセルの地", TEXT, RULE),
         (WHITE, "WHITE", "濃紺の上の文字", TEXT, RULE), (RULE, "RULE", "罫線・カードの枠線", TEXT, None), (SUB_ON_NAVY, "SUB_ON_NAVY", "濃紺の上の補足・フッター", TEXT, None),
         (ON_RED, "ON_RED", "RED の塗りの上の文字", TEXT, RULE), (RED_SOFT, "RED_SOFT", "小さな赤の札の地", RED_TEXT, None), (STAGE_TEXT, "STAGE_TEXT", "札の文字", WHITE, None),
         (DECOR, "DECOR", "章番号。部品が使う", WHITE, None)]  # テーマに入れない色（既定の値か NAMED の名前, 名前, 用途, 載せる文字, 枠線）
ON = {NAVY: WHITE, NAVY_BLOCK: WHITE, RED_TEXT: WHITE, SUB: WHITE, OSS: WHITE, BG: TEXT, PANEL: TEXT}  # 枠に載せる文字の色（届かなければ、札の文字か白の届くほう）。ほかは札の文字の色
ROLE = {name: slot for slot, name, _ in ROLES}  # factory.toml の [slides.themes.<名前>] に書く役割の名前 → テーマの枠
# 役割の組（文字, 地, 基準, どこで使うか）。visual.md の 1・3 の組み合わせ。18pt 未満は 4.5:1、18pt 以上か 14pt 以上の太字は 3:1。visual・company はすべて届く。
# NAMED の役割（HEAD・CARD・SUB_ON_NAVY・ON_RED）は、テーマが書いていなければ既定の色で測る（alias）。本文の地が暗いテーマも同じ組で測る
PAIRS = [(WHITE, NAVY, 4.5, "結論バンドの白"), (SUB_ON_NAVY, NAVY, 4.5, "濃紺の上の補足・フッター"), (RED_ON_NAVY, NAVY, 4.5, "表紙の小見出し"),
         (HEAD, BG, 4.5, "見出し"), (HEAD, PANEL, 4.5, "パネルの見出し"), (HEAD, CARD, 4.5, "カードの見出し・表の 1 列目"),
         (TEXT, BG, 4.5, "本文"), (TEXT, PANEL, 4.5, "パネルの本文"), (TEXT, CARD, 4.5, "カードの本文"), (SUB, BG, 4.5, "出典・フッター"), (SUB, PANEL, 4.5, "パネルの補足"),
         (SUB, CARD, 4.5, "カードの補足"), (RED_TEXT, BG, 4.5, "キッカー"), (RED_TEXT, PANEL, 4.5, "パネルの赤の文字"), (RED_TEXT, CARD, 4.5, "カードの赤の文字"),
         (RED_TEXT, RED_SOFT, 4.5, "淡い赤の札"), (RED, BG, 3.0, "18pt 以上の赤の文字"), (ON_RED, RED, 3.0, "赤の塗りの 14pt 以上の太字（番号の丸）"),
         (WHITE, NAVY_BLOCK, 4.5, "扉の中のブロックの白"), (SUB_ON_NAVY, NAVY_BLOCK, 4.5, "扉の中のブロックの補足"), (STAGE_TEXT, GA, 4.5, "GA の札"),
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
        if bad := set(themes().get(theme, {})) - {"url", "description", "base", "copyright", "mono", "cover", "section", *FIXED_DEFAULT, *NAMED}:  # 役割の色は組み込みのまま、font だけが効いてしまう
            sys.exit(f"[slides.themes.{theme}] は組み込みのテーマ（slides.py の THEMES）。url・description・base・copyright・mono・cover・section と固定の色（{', '.join([*FIXED_DEFAULT, *NAMED])}）のほか"
                     f"（{', '.join(sorted(bad))}）は書けない。会社の色なら別の名前のテーマにする")
        return THEMES[theme]
    if (t := themes().get(theme)) is None:
        sys.exit(f"テーマ {theme} がない（slides.py の THEMES にも、factory.toml の [slides.themes] にもない）")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", theme):  # [slides.themes.<名前>] の表の名前に、引用符なしで書き込む（set_url）
        sys.exit(f"テーマの名前 {theme!r} は英数字と - _ だけにする")
    if bad := set(t) - set(ROLE) - set(FIXED_DEFAULT) - set(NAMED) - {"base", "font", "mono", "url", "description", "copyright", "cover", "section"}:
        sys.exit(f"[slides.themes.{theme}] に知らない名前: {', '.join(sorted(bad))}（色は役割の名前 {', '.join(ROLE)} と固定の色の名前 {', '.join([*FIXED_DEFAULT, *NAMED])} で書く）")
    if bad := [k for k, v in t.items() if k in {*ROLE, *FIXED_DEFAULT, *NAMED} and not re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(v))]:
        sys.exit(f"[slides.themes.{theme}] の {', '.join(bad)} が 6 桁の 16 進の色でない（例: NAVY = \"002B5C\"）")
    theme_font(t)
    return {**THEMES["visual"], **{ROLE[k]: v.lstrip("#").upper() for k, v in t.items() if k in ROLE}}


def palette(theme):
    """colors に、テーマの固定の色（既定の値 → テーマの値）と、テーマが書いた NAMED の色（名前 → 値）を足したもの。PAIRS と FIXED の色は tone で引く。"""
    fx = theme_fixed(themes().get(theme, {}))
    return {**colors(theme), **{FIXED_DEFAULT[k]: v for k, v in fx.items() if k in FIXED_DEFAULT}, **{k: v for k, v in fx.items() if k in NAMED}}


def alias(T, c):
    """T が書いていない NAMED の役割は、その既定の色（NAVY の枠、白、RULE の値）。ほかはそのまま。"""
    return c if c in T else NAMED.get(c, c)


def tone(T, c):
    """役割・固定の色 c の 6 桁。"""
    return T.get(alias(T, c), alias(T, c))


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
    """T（palette）を PAIRS で測り、届かない組の色を shift で直す。直すのは、文字がテーマの枠かテーマが書いた NAMED ならその文字の色、
    文字が固定の色なら地の色。戻りは（直した T、[(どこ, 枠, 前, 後, 前の比, 後の比)]）。"""
    T, out = dict(T), []
    for _ in range(3):  # 1 つの枠を直すと、ほかの組の比が変わることがある
        for fg, gr, need, use in PAIRS:
            fg, gr = alias(T, fg), alias(T, gr)
            if (r := contrast(T.get(fg, fg), T.get(gr, gr))) >= need:
                continue
            slot, other = (fg, T.get(gr, gr)) if fg in SLOTS or fg in NAMED else (gr, T.get(fg, fg))
            if slot not in T:  # 文字も地も固定の色（TEXT / 書いていない CARD など）は動かさない。check が「届かない」に出す
                continue
            old, T[slot] = T[slot], shift(T[slot], other, need)
            if T[slot] != old:  # 動かせなかった枠は、check が「届かない」に出す
                out.append((use, slot, old, T[slot], r, contrast(T.get(fg, fg), T.get(gr, gr))))
    return T, out


def check(theme):
    """テーマの役割の組のコントラストと、届かない色の直す案を出す。すべて届けば True。"""
    T = palette(theme)
    F, out = fix(T)
    name = {**{c: n for c, n, *_ in FIXED}, **{slot: n for n, slot in ROLE.items()}}
    print(f"テーマ {theme} の役割の組（文字 / 地、比 / 基準）")
    for fg, gr, need, use in PAIRS:
        r = contrast(tone(T, fg), tone(T, gr))
        print(f"  {'OK' if r >= need else 'NG'}  {use}: {name.get(fg, fg)} {tone(T, fg)} / {name.get(gr, gr)} {tone(T, gr)}  {r:.2f}:1 / {need:g}:1")
    if out:
        print(f"\n直す案（色相と彩度を保ち、明るさだけを変えた。ユーザーに見せてから factory.toml の [slides.themes.{theme}] に写す）:")
        for slot in dict.fromkeys(o[1] for o in out):
            old, new = next(o[2] for o in out if o[1] == slot), F[slot]
            print(f'  {name[slot]} = "{new}"  # {old} から{"暗く" if lum(new) < lum(old) else "明るく"}した（{"、".join(dict.fromkeys(o[0] for o in out if o[1] == slot))}）')
    for fg, gr, need, use in PAIRS:  # 明るさだけでは届かない組（白か黒まで動かしても届かない、ほかの組と同じ枠を取り合うなど）。当てる色を替える
        if (r := contrast(tone(F, fg), tone(F, gr))) < need:
            print(f"  直す案でも届かない: {use}（{r:.2f}:1 / {need:g}:1）。役割に当てる色を替える")
    return all(contrast(tone(T, fg), tone(T, gr)) >= need for fg, gr, need, _ in PAIRS)


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
    T = palette(theme)
    use_theme(themes().get(theme, {}))  # 固定の色と著作権表示はテーマの値（slides.py build がデッキのテーマから読むのと同じ）
    docs = "https://developers.google.com/workspace/slides"  # 出典の行の見本のリンク。どの会社のテンプレートにも入るので、会社に結びつかない公開のページ

    def on(fill, want=None):  # 色の箱に載せる文字の色。want が届かなければ（本文の地が暗いテーマの淡い色の箱など）、札の文字か白の届くほう
        ratio = lambda c: contrast(tone(T, c), tone(T, fill))
        return want if want and ratio(want) >= 4.5 else max((STAGE_TEXT, WHITE), key=ratio)

    def make(d):
        s = d.cover(f"テーマ「{theme}」の見本", f"社内｜{time.strftime('%Y-%m-%d')}", "AI Deck Factory のテンプレート")
        d.note(s, "表紙です。小見出しは相手と日付、タイトルは白、副題と小見出しは濃紺の上の赤、社名は濃紺の上の補足の色（SUB_ON_NAVY）です。表紙にはページ番号を置きません。")

        s = d.divider("01", "色と部品", "テーマの色の役割と、本文ページの部品")
        d.card(s, X, 5.0, 2.4, 0.85, None, body=[("扉の中のブロック\n", {"bold": True, "color": WHITE}), ("白と SUB_ON_NAVY だけを載せる", {"color": SUB_ON_NAVY})],
               fill=NAVY_BLOCK, line=None)
        d.note(s, "章の扉です。章番号は飾りの色で、コントラストの基準の外です。扉の中のブロックには、白と濃紺の上の補足の色（SUB_ON_NAVY）だけを載せます。濃紺の上の赤は、ブロックの上ではコントラストが届きません。")

        s = d.page("色は役割の名前で選び、値はテーマが決める", "濃い色の枠には白か札の文字、淡い色の枠には本文の色を載せる。", kicker="早見表")
        cw, ch, gap = (W - 3 * 0.2) / 4, 1.0, 0.2
        for i, (slot, name, use) in enumerate(ROLES):
            x, y = X + (i % 4) * (cw + gap), Y_BODY + (i // 4) * (ch + 0.15)
            d.box(s, x, y, cw, ch, slot, RULE if slot == BG else None)  # BG は地と同じ色なので、見本だけ罫線を付ける
            d.text(s, x + PAD, y + PAD, cw - 2 * PAD, ch - 2 * PAD, [(f"{name}（{slot}）\n", {"bold": True}), f"{T[slot]}\n", use],
                   color=on(slot, ON.get(slot)), spacing=115)
        d.text(s, X + 3 * (cw + gap) + PAD, Y_BODY + 2 * (ch + 0.15) + PAD, cw - 2 * PAD, ch - 2 * PAD,
               [("テーマに入れない色（次のページ）\n", {"bold": True}), "pages.py に名前で書く\n値は factory.toml で変えられる"], spacing=115)
        origin = ("元のテンプレート", {"link": base(theme)}) if base(theme) else "白紙の pptx（deck-build/assets/blank.pptx）"  # 空の URL のリンクは API が断る
        d.source(s, ["出典: visual.md の 1（色の決まり）。ページの大きさとマスターは ", origin])
        d.note(s, f"テーマ「{theme}」の 11 の枠です。キッカーは、このページのように役割を示すときだけ置きます。"
                  "BG は地と同じ色なので、見本だけ罫線を付けています。値は factory.toml に書く形（# を付けない 6 桁）です。")

        s = d.page("テーマに入れない色は名前で書き、値は factory.toml で替える", "書かなければ既定の値。本文の地が暗いテーマは、HEAD・CARD・SUB_ON_NAVY・ON_RED も書く。", kicker="早見表")
        cw, ch = (W - 4 * 0.2) / 5, 1.1  # 3 行の下を、カードの決まり（box_pad の 0.28 in）より空ける
        for i, (c, name, use, fg, line) in enumerate(FIXED):
            x, y = X + (i % 5) * (cw + 0.2), Y_BODY + (i // 5) * (ch + 0.15)
            d.box(s, x, y, cw, ch, c, line)
            d.text(s, x + PAD, y + PAD, cw - 2 * PAD, ch - 2 * PAD, [(f"{name}\n", {"bold": True}), f"{tone(T, c)}\n", use], color=on(c, fg), spacing=115)
        d.source(s, ["出典: visual.md の 1（色の決まり）、deck-template の SKILL.md（暗い本文のテーマ）。ページの大きさとマスターは ", origin])
        d.note(s, f"テーマ「{theme}」の、テーマに入れない {len(FIXED)} の色です。HEAD・CARD・SUB_ON_NAVY・ON_RED は、書かなければ NAVY・白・RULE・白と同じ色です。"
                  "DECOR は slides.py の章の扉が使い、pages.py には書きません。")

        s = d.page("部品は役割の色で塗り、大きさと間隔は既定に従う", "カード、パネル、数字、札、正円の番号、表、矢印、結論バンド、出典の行の見本。")
        hw = (W - 0.3) / 2
        d.card(s, X, Y_BODY, hw, 1.5, "カードの見出し（12pt 太字）", body=["本文は 11pt。", ("強調は太字", {"bold": True}), "。\n",
                                                                  ("赤の文字", {"color": RED_TEXT, "bold": True}), "は 18pt 未満でも読める色。\n",
                                                                  ("リンク", {"link": docs}), "は周りの色のまま下線を付ける。"])
        d.text(s, X - INSET, 3.4, hw + 2 * INSET, 0.65, [("32", {"size": 32, "bold": True, "color": HEAD}), ("%", {"size": 16, "bold": True, "color": HEAD}),
                                                        ("  数字 32pt・単位 16pt。赤にするなら RED", {"color": SUB})])
        d.card(s, X, 4.18, hw, 0.8, None, body=[("パネル\n", {"bold": True}), "塗りだけで囲み、枠線は付けない。"], fill=PANEL, line=None)
        for i, (label, fill, fg) in enumerate([("GA", GA, STAGE_TEXT), ("Beta", PREVIEW, STAGE_TEXT), ("OSS", OSS, WHITE)]):
            d.text(s, X + i * 0.95, 5.13, 0.8, 0.4, label, color=fg, bold=True, align="CENTER", valign="MIDDLE", fill=fill)
        d.text(s, X + 3.2, 5.13, 0.8, 0.4, "推奨", color=RED_TEXT, bold=True, align="CENTER", valign="MIDDLE", fill=RED_SOFT)  # 提供ステージの札と離す（赤と緑を並べない）
        for n, (size, cx) in enumerate((("S", 4.35), ("M", 4.85), ("L", 5.45)), 1):  # 正円の番号の 3 つの大きさ（slides.py の NUM）。札と中心をそろえる
            d.num(s, n, X + cx, 5.33, size)
        rx = X + hw + 0.3
        tb = d.table(s, rx, Y_BODY, [1.6, hw - 1.6], [["役割", "使うところ"], ["NAVY", "扉、結論バンド、表の見出しの行"], ["HEAD", "見出し、表の 1 列目"], ["SUB", "出典、フッター、補足"],
                                                 ["RED_TEXT", "キッカー、18pt 未満の強調"], ["RED", "番号の丸、図形の塗り、太い線"]], row_h=0.36)  # 6 行で、下の箱（4.18 in）の上に収める
        d.box(s, rx, Y_BODY, 1.6, tb - Y_BODY, line=RED, kind="ROUND_RECTANGLE")  # 表の 1 列の強調。赤の線は既定で 2pt（2026-10-08、ユーザー）
        for bx, label in ((rx, "箱 A"), (rx + hw - 2.4, "箱 B")):
            d.text(s, bx, 4.18, 2.4, 0.8, label, align="CENTER", valign="MIDDLE", fill=CARD, line=RULE)
        d.arrow(s, rx + 2.48, 4.58, rx + hw - 2.48, 4.58)
        d.band(s, "結論バンド: 言いたいことを 1 文（13pt 太字）", "補足は 11pt の SUB_ON_NAVY。下端は 6.60 in に固定。")
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
        d.text(s, rx + PAD, y0 + 0.1, hw - 2 * PAD, 0.34, "塗りのない角丸の囲み（まとまりを示す）", size=12, color=HEAD, bold=True)
        for (x, w), label in zip(cols(2, 0.24, rx + 0.2, hw - 0.4), ("部品 A", "部品 B")):
            d.text(s, x, y0 + 0.55, w, 0.8, label, align="CENTER", valign="MIDDLE", fill=PANEL)
        y1 = 5.2  # 強調の赤い点線の囲み。中のカードと同じ半径（Google 標準の角丸にしない）で、線は赤の既定の 2pt（2026-10-08、ユーザー）
        d.box(s, rx, y1, hw, 1.3, line=RED, kind="ROUND_RECTANGLE", dash=True)
        d.card(s, rx + 0.12, y1 + 0.12, hw - 0.24, 1.06, "強調の点線の囲み（dash=True。赤の線は 2pt）", body="重なる範囲や、見てほしいところを囲む。角は中のカードと同じ丸み")
        d.note(s, "項目のカード、箇条書き、塗りのない角丸の囲み、強調の点線の囲みの見本です。塗りのない角丸の囲みは辺と弧を線でつないで描くので、"
                  "部品を直したら、継ぎ目に段が出ていないかと、点線の囲みの角が中のカードと同じ丸みになっているかを、ここで見ます。")

    def make_all(d):
        make(d)
        for kind, vs in VARIANTS.items():  # 表紙・扉のパターン（会社のテンプレートから残したもの）を 1 枚ずつ。pages.py の variant の番号はここで選ぶ
            for i, (_, t) in sorted(vs.items())[1:]:  # 1 は make の表紙・扉
                if kind == "cover":
                    s = d.cover(f"表紙のパターン {i}", f"d.cover(…, variant={i})", f"地: {t}", variant=i)
                else:
                    s = d.divider(f"{i:02d}", f"扉のパターン {i}", f"d.divider(…, variant={i})。地: {t}", variant=i)
                d.note(s, f"{'表紙' if kind == 'cover' else '章の扉'}のパターン {i} です（地の明るさ {t}）。会社のテンプレートの図形と写真を残し、文字の色は地に合わせます。")

    return make_deck(make_all, f"AI Deck Factory｜テーマ「{theme}」の見本")


def base(theme):
    """元にするテンプレートの URL。テーマの base、なければ factory.toml の [slides] base_template（2026-10-12 までの書き方。組み込みのテーマにも base を書ける）。
    どちらもなければ ""（--from-base は BLANK_PPTX から作る）。"""
    return themes().get(theme, {}).get("base") or factory().get("slides", {}).get("base_template", "")


def pick(p, names=None):
    """残すマスター（いちばん多くのページが使うもの。同じなら先のもの）と、slides.py が使うレイアウトを選ぶ。レイアウトは、そのマスターの、
    プレースホルダーがページ番号の枠だけのもの（slides.py の is_blank）。名前が BLANK のもの、型が BLANK のものの順に先にする。
    names（{"cover"・"section": レイアウトの名前の並び}。テーマの cover・section）があれば、その表紙・扉のパターンも選ぶ（{種類: [レイアウト, …]}。
    並びの順がパターンの番号。同じ名前のレイアウトが 2 つあれば両方）。"""
    used = Counter(s.get("slideProperties", {}).get("masterObjectId") for s in p.get("slides", []))
    master = max(p["masters"], key=lambda m: used[m["objectId"]])
    ls = [l for l in p["layouts"] if l["layoutProperties"].get("masterObjectId") == master["objectId"]]
    names = {k: [v] if isinstance(v, str) else v for k, v in (names or {}).items()}
    if bad := [k for k, v in names.items() if not isinstance(v, list) or not all(isinstance(n, str) for n in v)]:
        sys.exit(f"テーマの {'・'.join(bad)} は、レイアウトの名前の文字列か、その並びで書く（例: cover = [\"Title Slide 1\", \"Title Slide 2\"]）")
    if both := set(names.get("cover", [])) & set(names.get("section", [])):  # 目印はレイアウトに 1 つなので、両方に書くと後のものだけが残る
        sys.exit(f"レイアウト「{'」「'.join(sorted(both))}」が、テーマの cover と section の両方にある。どちらか一方に書く")
    if bad := [n for v in names.values() for n in v if not any(l["layoutProperties"]["displayName"] == n for l in ls)]:
        sys.exit(f"マスター「{master['masterProperties']['displayName']}」に、テーマの cover・section のレイアウト「{'」「'.join(bad)}」がない"
                 "（名前は template.py audit の表のとおりに書く。合わせ直しなら --from-base で作り直す）")
    extras = {k: [l for n in dict.fromkeys(v) for l in ls if l["layoutProperties"]["displayName"] == n] for k, v in names.items()}
    kept = [l for v in extras.values() for l in v]
    if stale := [l["layoutProperties"]["displayName"] for l in ls if l not in kept and any(LAYOUT_MARK.search(e.get("description", "")) for e in l.get("pageElements", []))]:
        # 前に表紙・扉として残し、テーマの cover・section から外したパターン。目印が残ると slides.py が使い続け、Blank に選ぶこともある
        sys.exit(f"テーマの cover・section にない表紙・扉のパターン「{'」「'.join(stale)}」が、テンプレートに残っている。パターンを減らすときは --from-base で作り直す")
    if bad := [l["layoutProperties"]["displayName"] for l in kept if "SLIDE_NUMBER" not in placeholders(l)]:  # 目印はページ番号の枠に書き、slides.py の createSlide もこの枠を対応づける
        sys.exit(f"テーマの cover・section のレイアウト「{'」「'.join(dict.fromkeys(bad))}」に、ページ番号の枠がない。元のテンプレートを複製し、"
                 "画面のテーマビルダーでそのレイアウトにスライド番号のプレースホルダーを足して、その URL を base にする")
    cands = sorted((l for l in ls if is_blank(l) and l not in kept),
                   key=lambda l: (l["layoutProperties"]["displayName"] != BLANK, l["layoutProperties"].get("name") != "BLANK"))
    if not cands:
        sys.exit(f"マスター「{master['masterProperties']['displayName']}」に、プレースホルダーがページ番号の枠だけのレイアウトがない。元のテンプレートを複製し、"
                 "画面のテーマビルダーで Blank のレイアウトを作るか、Blank のレイアウトにスライド番号のプレースホルダーを足して、その URL を base にする")
    return master, cands[0], extras


def decor(layout):
    """表紙・扉のレイアウトに残す置き物（図形・画像・ロゴ・線）。プレースホルダーと、文字の入った枠（著作権の行など。slides.py が書く）は残さない。"""
    def text(e):
        return "".join(t.get("textRun", {}).get("content", "") for t in e.get("shape", {}).get("text", {}).get("textElements", [])).strip()
    return [e for e in layout.get("pageElements", []) if "placeholder" not in e.get("shape", {}) and not text(e)]


def align_decor(layout):
    """表紙・扉の置き物のうち、元のタイトルの枠と左端がそろっていたもの（ロゴ、短い線など）を、slides.py の文字の左端 X に寄せる要求。
    元の余白（例: 0.83 in）のままだと、0.6 in の余白で組む文字と左端がずれる（2026-10-13）。ページの右端まで届くもの（帯、全面の写真や四角）は
    寄せない（右端に地が見える）。"""
    lefts = [e.get("transform", {}).get("translateX", 0) / EMU for e in layout.get("pageElements", [])  # API の JSON は 0 の値を省く
             if e.get("shape", {}).get("placeholder", {}).get("type") in ("TITLE", "CENTERED_TITLE")]
    def right(e):
        t = e.get("transform", {})
        return (t.get("translateX", 0) + e.get("size", {}).get("width", {}).get("magnitude", 0) * t.get("scaleX", 1)) / EMU
    return [{"updatePageElementTransform": {"objectId": e["objectId"], "applyMode": "RELATIVE", "transform": {
                "scaleX": 1, "scaleY": 1, "translateX": round((X - lefts[0]) * EMU), "translateY": 0, "unit": "EMU"}}}
            for e in decor(layout) if lefts and abs(e.get("transform", {}).get("translateX", 0) / EMU - lefts[0]) < 0.05 and abs(lefts[0] - X) >= 0.05
            and right(e) < 2 * X + W - 0.05]


def text_w(layout):
    """表紙・扉の文字の幅（in）。元のタイトルの枠の右端まで（会社のテンプレートが図形・写真に重ねないように決めた幅）。枠がなければ
    （合わせ直しで、strip が消したあと）、前に書いた目印の幅。どちらもなければ None（本文の幅のまま）。"""
    for e in layout.get("pageElements", []):
        if e.get("shape", {}).get("placeholder", {}).get("type") in ("TITLE", "CENTERED_TITLE"):
            t = e["transform"]
            return round((t.get("translateX", 0) + e["size"]["width"]["magnitude"] * t.get("scaleX", 0)) / EMU - (X - INSET), 2)
    return next((float(m.group(3)) for e in layout.get("pageElements", []) if (m := LAYOUT_MARK.search(e.get("description", ""))) and m.group(3)), None)


def bg_tone(theme, master, layout):
    """表紙・扉のパターンの地の明るさ（slides.py の TONES）。地は、レイアウトの置き物のうちページ全面を覆う塗りの四角（上にあるもの）、
    なければレイアウトの塗り、なければマスターの塗り（テーマの色はこのテーマの値で引く）。白の文字が 4.5:1 に届けば dark、3:1 なら accent
    （大きな文字だけ白）、届かなければ light。ponytail: 全面の写真や絵の明るさは見ない（塗りだけ）。"""
    scheme = colors(theme)
    def full(e):  # ページ全面（13.33 × 7.5 in）を覆う図形か
        t, s = e.get("transform", {}), e.get("size", {})
        return (t.get("translateX", 0) <= 0 and t.get("translateY", 0) <= 0 and s.get("width", {}).get("magnitude", 0) * t.get("scaleX", 1) / EMU >= 2 * X + W - 0.05
                and s.get("height", {}).get("magnitude", 0) * t.get("scaleY", 1) / EMU >= 7.45)
    rects = [solid(e.get("shape", {}).get("shapeProperties", {}).get("shapeBackgroundFill"), scheme) for e in decor(layout) if full(e)]
    page = lambda pg: solid(pg.get("pageProperties", {}).get("pageBackgroundFill"), scheme)
    r = contrast(WHITE, next((c for c in reversed(rects) if c), None) or page(layout) or page(master) or "FFFFFF")
    return "dark" if r >= 4.5 else "accent" if r >= 3 else "light"


def strip(pid, p, master, blank, extras=None):
    """元のテンプレートの複製から、残すマスターとレイアウト（pick）のほかを消す。表紙・扉のレイアウト（extras）は、置き物（decor）だけを残す。"""
    extras = extras or {}
    # 見本のページを消す前に 1 枚作っておく。ページが 0 枚になると、使われていないマスターごと消える。
    # 足す位置の前のページのマスターのレイアウトしか使えないので、残すマスターのページの直後に足す（末尾が別のマスターだと 400。2026-10-13）
    at = next((i + 1 for i, s in enumerate(p["slides"]) if s.get("slideProperties", {}).get("masterObjectId") == master["objectId"]), None)
    batch(pid, [{"createSlide": {"objectId": "keep_slide", "slideLayoutReference": {"layoutId": blank["objectId"]},
                                 **({"insertionIndex": at} if at is not None else {})}}]
          + [{"deleteObject": {"objectId": s["objectId"]}} for s in p["slides"]])
    # ページを消すと、そのページだけが使っていたマスターとレイアウトを Google が消すことがある。読み直して、残っているものだけを消す（2026-10-13）
    now = request("GET", f"{SLIDES}/{pid}?fields=masters.objectId,layouts.objectId,slides(objectId,pageElements.shape.placeholder.type)")
    slide = next(s for s in now["slides"] if s["objectId"] == "keep_slide")
    if not any(e.get("shape", {}).get("placeholder", {}).get("type") == "SLIDE_NUMBER" for e in slide.get("pageElements", [])):
        # 元のファイルの「スライド番号」の設定がオフだと、API で足したページにページ番号の枠ができない。API では変えられない（2026-10-13）
        sys.exit("元のテンプレートは、足したページにページ番号の枠ができない（ファイルの「スライド番号」の設定がオフ）。元を複製し、複製の画面の"
                 "「挿入 → スライド番号」で「オン」にして「すべてに適用」を押し、その URL を base にする")
    kept = [l for v in extras.values() for l in v]
    keep = {blank["objectId"], *(l["objectId"] for l in kept)}
    dels = ([l["objectId"] for l in now["layouts"] if l["objectId"] not in keep]
            + [m["objectId"] for m in now["masters"] if m["objectId"] != master["objectId"]])
    # マスターの著作権の行とロゴ、Blank の全面の四角（ページの地を覆う）など、プレースホルダーでないもの。フッターは slides.py が書く
    dels += [e["objectId"] for pg in (master, blank) for e in pg.get("pageElements", []) if "placeholder" not in e.get("shape", {})]
    for l in kept:  # 置き物とページ番号の枠（2 つあれば先の 1 つ。slides.py の placeholderIdMappings が 1 つに決まるように）のほかを消す
        nums = [e for e in l.get("pageElements", []) if placeholders({"pageElements": [e]}) == ["SLIDE_NUMBER"]]
        dels += [e["objectId"] for e in l.get("pageElements", []) if e not in decor(l) and e not in nums[:1]]
    batch(pid, [{"deleteObject": {"objectId": o}} for o in dels])


def styles(theme, master, blank, extras=None):
    """配色、プレースホルダーの書体、ページ番号の枠（文字は slides.py の number_style。右端を本文の右端に、上端を著作権表示の文字にそろえる。
    この枠は内側の余白が 0）。ページ番号の枠の代替テキストにテーマの名前を書く（slides.py build がデッキのテーマを知り、固定の色・著作権表示・等幅を
    factory.toml から引く。THEME_MARK）。"""
    reqs = [{"updatePageProperties": {"objectId": master["objectId"], "pageProperties": {"colorScheme": {"colors": [
        {"type": k, "color": rgb(colors(theme)[k])} for k in SLOTS]}}, "fields": "colorScheme.colors"}}]
    font = themes().get(theme, {}).get("font", FONT)
    kept = [l for v in (extras or {}).values() for l in v]
    first = lambda l: next(e for e in l["pageElements"] if placeholders({"pageElements": [e]}) == ["SLIDE_NUMBER"])  # 2 つ目は strip が消した
    mark = {first(l)["objectId"]: f"ai-deck-factory layout={k}:{i}" + (f" w={w}" if (w := text_w(l)) else "") + f" tone={bg_tone(theme, master, l)}"
            for k, v in (extras or {}).items() for i, l in enumerate(v, 1)}  # slides.py の LAYOUT_MARK
    reqs += [r for l in kept for r in align_decor(l)]
    for pg, e in ((pg, e) for pg in (master, blank, *kept) for e in pg.get("pageElements", [])):
        ph = e.get("shape", {}).get("placeholder", {}).get("type")
        if not ph or (pg not in (master, blank) and e["objectId"] not in mark):  # 表紙・扉のほかの枠は strip が消した
            continue
        reqs.append({"updateTextStyle": {"objectId": e["objectId"], "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}})
        if ph == "SLIDE_NUMBER":
            size = e["size"]
            reqs += [{"updatePageElementAltText": {"objectId": e["objectId"], "description": mark.get(e["objectId"], f"ai-deck-factory theme={theme}")}},
                     {"updatePageElementTransform": {"objectId": e["objectId"], "applyMode": "ABSOLUTE", "transform": {
                         "scaleX": 1.0 * EMU / size["width"]["magnitude"], "scaleY": 0.28 * EMU / size["height"]["magnitude"],
                         "translateX": round((X + W - 1.0) * EMU), "translateY": round((Y_FOOT + INSET) * EMU), "unit": "EMU"}}},
                     {"updateShapeProperties": {"objectId": e["objectId"], "shapeProperties": {"contentAlignment": "TOP"}, "fields": "contentAlignment"}},
                     *number_style(e["objectId"])]
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


def props(theme):
    """テンプレートの Drive のプロパティ（公開）。テーマの名前と、factory.toml のテーマの表のうち PUBLISHED の値。Drive の上限（名前と値で 124 バイト）を超える値は
    書かずに知らせる（社名の長い copyright など。url だけを書いた人は、その値を自分の factory.toml の値か既定の値で組む）。"""
    t = themes().get(theme, {})
    p = {THEME_PROP: theme, **{PROP + k: str(t[k]) for k in PUBLISHED if k in t}}
    if long := [k for k, v in p.items() if len((k + v).encode()) > 124]:
        print(f"[slides.themes.{theme}] の {', '.join(k[len(PROP):] for k in long)} は長すぎて、テンプレートの Drive のプロパティに書けない（名前と値で 124 バイトまで）。"
              "url だけを書いた人は、自分の factory.toml の値か既定の値で組む", file=sys.stderr)
    return {k: v for k, v in p.items() if k not in long}


def publish(pid, theme):
    """テンプレートの Drive のプロパティ（props）と説明（[slides.themes.<theme>] の description）を書く。前に書いたプロパティで、今の表にないものは消す。"""
    old = request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=properties").get("properties") or {}
    request("PATCH", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=id", {"description": themes().get(theme, {}).get("description", ""),
                                                                              "properties": {**{k: None for k in old if k.startswith(PROP)}, **props(theme)}})


def template(theme, from_base=False):
    """テンプレートを作る（from_base）か、合わせ直す。Drive に複製する・テンプレートを書き換える前に、要るものを全部確かめる
    （テーマの色、[brand] copyright、作るときは factory.toml に url を書けるか）。作るときは、組んだあとに url を factory.toml に書く。
    複製したあとで止まったら（url を書けなかったときも）、複製をゴミ箱に移す。"""
    palette(theme)  # 知らないテーマ・書けない値なら止まる
    use_theme(themes().get(theme, {}))
    need_brand()  # 見本のページ（build）に著作権表示（テーマの copyright があればそれ）を書く
    if from_base:
        record(theme)  # factory.toml に url を書けるか（書けないのに複製を残さない）
    src = file_id(base(theme))
    if from_base:
        name = NAMES.get(theme, f"テンプレート（{theme}）")
        if not src:  # Google Slides に変換して上げる（変換しないと Office のファイルのままで、Slides API が使えない）
            with open(BLANK_PPTX, "rb") as f:
                pid = upload(f.read(), PPTX, name, themes_folder(), convert=GSLIDES)["id"]
        elif not page_ok(request("GET", f"{SLIDES}/{src}?fields=pageSize")["pageSize"]):
            sys.exit(f"元のテンプレートのページが {PAGE[0]:.2f} × {PAGE[1]} in でない。template.py audit {base(theme)} の指示どおりに直す")
        else:
            pid = request("POST", f"{DRIVE}/files/{src}/copy?supportsAllDrives=true&fields=id", {"name": name, "parents": [themes_folder()]})["id"]
    elif url := themes().get(theme, {}).get("url"):
        pid = file_id(url)
    else:
        sys.exit(f"factory.toml の [slides.themes.{theme}] に url がない。template.py {theme} --from-base で作る")
    try:
        p = request("GET", f"{SLIDES}/{pid}")
        t = themes().get(theme, {})
        master, blank, extras = pick(p, {k: t[k] for k in ("cover", "section") if t.get(k)})
        if from_base:
            strip(pid, p, master, blank, extras)
        batch(pid, styles(theme, master, blank, extras))
        use_layouts(request("GET", f"{SLIDES}/{pid}?fields=layouts(objectId,pageElements(description))"))  # 見本の表紙・扉を、置き物に重ならない幅で組む
        build(pid, specimen(theme), force=True)  # 直前に配色を変えているので、版の確かめはしない
        publish(pid, theme)
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
            assert len(d.slides) == 6 and not d.images and all(s in d.notes for s in d.slides)
        assert all(not fix(T)[1] for T in THEMES.values())  # 組み込みのテーマは、役割の組がすべて届く
        F, out = fix({**THEMES["company"], SUB: "618794"})  # 公式のテンプレートの ACCENT5。Oat Medium の上で 3.32:1
        assert {o[1] for o in out} == {SUB} and F[SUB] == "506F7A"  # 同じ青緑のまま暗くする（company の SUB はこの案）
        assert contrast(shift("FFFFFF", "FFFFFF", 4.5), "FFFFFF") >= 4.5  # 同じ色からでも離す
        assert contrast(shift("4A5A70", "5A6E8C", 4.5), "5A6E8C") >= 4.5  # 暗くしても届かない色は明るくする
        F, out = fix({**THEMES["visual"], NAVY: "1F6FB2", RED_ON_NAVY: "B22222"})  # 中くらいの青の NAVY に、RED をそのまま写した RED_ON_NAVY
        assert contrast(F[RED_ON_NAVY], F[NAVY]) >= 4.5 and lum(F[RED_ON_NAVY]) > lum("B22222") and len({o[1] for o in out}) == len(out)
        F, out = fix({**palette("visual"), TEXT: "8A8A8A"})  # テーマの固定の色でも測る。直すのは役割の枠（地）のほう
        assert out and all(o[1] in SLOTS for o in out) and F[TEXT] == "8A8A8A" and contrast("8A8A8A", F[BG]) >= 4.5
        assert palette("visual")[TEXT] == TEXT and set(palette("visual")) == set(SLOTS) | set(FIXED_DEFAULT.values())  # 書いていなければ既定の値
        T = palette("visual")  # 書いていない NAMED は既定の色で測る（前の PAIRS と同じ組）
        assert [tone(T, c) for c in (HEAD, CARD, SUB_ON_NAVY, ON_RED)] == [T[NAVY], WHITE, RULE, WHITE] and alias(T, HEAD) == NAVY
        F, out = fix({**T, NAVY: "6A7F87"})  # 書いていない HEAD が届かなければ、前と同じく NAVY の枠を直す
        assert {o[1] for o in out} >= {NAVY} and not {o[1] for o in out} & set(NAMED)
        dark = {**T, BG: "000000", NAVY: "1A1A1A", PANEL: "1A1A1A", NAVY_BLOCK: "2E3033", SUB: "A8A8AF", RED: "FF6308", RED_TEXT: "FF6308", RED_ON_NAVY: "FF6308",
                TEXT: "D8D8E1", RULE: "2E3033", RED_SOFT: "3A1D0A", STAGE_TEXT: "000000", HEAD: "F0F0FA", CARD: "0A0A0A", SUB_ON_NAVY: "C0C0C8", ON_RED: "000000"}
        assert not fix(dark)[1]  # 本文の地が暗いテーマ（RULE は暗い枠線、濃紺の上の補足は SUB_ON_NAVY で分ける）は、役割の組がすべて届く
        F, out = fix({**dark, ON_RED: "FFFFFF"})  # 書いた ON_RED が届かなければ、RED でなく ON_RED を直す（オレンジに白は 2.98:1）
        assert [o[1] for o in out] == [ON_RED] and contrast(F[ON_RED], "FF6308") >= 3
        sn = {"shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}
        master = {"objectId": "m", "pageElements": [{"objectId": "n", "size": {"width": {"magnitude": EMU}, "height": {"magnitude": EMU}}, **sn}]}
        alt = [r["updatePageElementAltText"] for r in styles("visual", master, {"pageElements": []}) if "updatePageElementAltText" in r]
        assert alt == [{"objectId": "n", "description": "ai-deck-factory theme=visual"}] and THEME_MARK.search(alt[0]["description"]).group(1) == "visual"  # slides.py build が読む
        lay = lambda i, m, *els, name="": {"objectId": i, "layoutProperties": {"masterObjectId": m, "displayName": i, "name": name}, "pageElements": list(els)}
        p = {"masters": [{"objectId": "a"}, {"objectId": "b"}], "slides": [{"slideProperties": {"masterObjectId": "b"}}],
             "layouts": [lay("a1", "a", sn), lay(BLANK, "b", sn, {"shape": {"placeholder": {"type": "TITLE"}}}), lay("b1", "b", sn), lay("b2", "b", sn, name="BLANK")]}
        assert [x["objectId"] for x in pick(p)[:2]] == ["b", "b2"]  # ページが使うマスターの、ページ番号の枠だけのレイアウト（名前が BLANK でも枠が多ければ使わない。型が BLANK を先に）
        assert pick(p, {"cover": "b2"})[1:] == (p["layouts"][2], {"cover": [p["layouts"][3]]})  # 表紙に残すレイアウトは Blank に選ばない
        try:  # ページ番号の枠のない表紙は、書き換える前に止める
            pick({**p, "layouts": [*p["layouts"], lay("c0", "b", {"shape": {"placeholder": {"type": "TITLE"}}})]}, {"cover": "c0"})
            raise AssertionError
        except SystemExit as e:
            assert "c0" in str(e) and "ページ番号の枠がない" in str(e)
        marked = lay("c1", "b", {**sn, "description": "ai-deck-factory layout=cover:1 tone=dark"})
        for names, want in (({"cover": 1}, "文字列"), ({"cover": "b2", "section": ["b2"]}, "両方"), ({}, "c1")):  # 型の違う値、cover と section の重なり、外したパターンの目印
            try:
                pick({**p, "layouts": [*p["layouts"], marked]}, names)
                raise AssertionError(names)
            except SystemExit as e:
                assert want in str(e), (names, str(e))
        assert pick({**p, "layouts": [*p["layouts"], marked]}, {"cover": ["c1"]})[2] == {"cover": [marked]}  # 合わせ直し（目印のあるパターンを同じに書く）は通る
        box = lambda x, y, w, h, **k: {"objectId": f"e{x}{y}", "transform": {"translateX": x * EMU, "translateY": y * EMU, "scaleX": 1, "scaleY": 1},
                                       "size": {"width": {"magnitude": w * EMU}, "height": {"magnitude": h * EMU}}, **k}
        copy = box(0.8, 7.0, 4, 0.2, shape={"text": {"textElements": [{"textRun": {"content": "© 2026"}}]}})
        head = {**box(0.83, 1.3, 6.75, 2.6), "objectId": "t", "shape": {"placeholder": {"type": "CENTERED_TITLE"}}}
        bg = lambda c: {"pageProperties": {"pageBackgroundFill": {"solidFill": {"color": c}}}}
        cov = {**lay("c", "b", {**sn, **box(12, 7, 1, 0.3)}, head, box(0, 0, 13.33, 7.5), box(10.6, 3.15, 1.9, 1.7), copy), **bg({"themeColor": "DARK2"})}
        assert copy not in decor(cov) and head not in decor(cov) and len(decor(cov)) == 2 and text_w(cov) == 7.08  # 元のタイトルの枠の右端まで
        assert text_w(lay("c3", "b", {"description": "ai-deck-factory layout=cover:1 w=7.08 tone=dark"})) == 7.08  # 合わせ直し（枠はもうない）は前の目印の幅
        white = {"objectId": "m", **bg({"rgbColor": {"red": 1, "green": 1, "blue": 1}})}
        assert [bg_tone("company", white, x) for x in (cov, lay("w", "b"), {**lay("n", "b"), **bg({"themeColor": "DARK1"})})] == ["accent", "light", "dark"]
        navy_rect = box(0, 0, 13.33, 7.5, shape={"shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": {"themeColor": "DARK1"}}}}})
        assert bg_tone("company", white, lay("r", "b", navy_rect)) == "dark"  # 地を全面の四角で描いたレイアウトは、四角の色で見る
        assert bg_tone("company", white, {**lay("r2", "b", navy_rect, box(0, 0, 13.33, 7.5, shape={"shapeProperties": {"shapeBackgroundFill": {
            "solidFill": {"color": {"rgbColor": {"red": 1, "green": 1, "blue": 1}}}}}})), **bg({"themeColor": "DARK1"})}) == "light"  # 上の四角が先
        alt = [r["updatePageElementAltText"]["description"] for r in styles("company", {**master, **white}, {"pageElements": []}, {"cover": [lay("w", "b", {**sn, **box(12.1, 7, 1, 0.3)}), cov]})
               if "updatePageElementAltText" in r]
        assert alt == ["ai-deck-factory theme=company", "ai-deck-factory layout=cover:1 tone=light", "ai-deck-factory layout=cover:2 w=7.08 tone=accent"]
        logo, shapes, band = box(0.83, 0.67, 2.8, 0.44), box(10.6, 3.15, 1.9, 1.7), box(0.83, 5.2, 12.5, 2.3)
        moved = align_decor(lay("c2", "b", head, logo, shapes, band))  # 元のタイトルと左端がそろうロゴだけを、文字の左端に寄せる（右端まで届く帯は寄せない）
        t0 = {**head, **box(0, 1.3, 6, 2.6), "objectId": "t0"}
        t0["transform"] = {k: v for k, v in t0["transform"].items() if k != "translateX"}  # API は 0 の translateX を省く
        assert not align_decor(lay("c4", "b", t0, box(0, 0, 13.33, 7.5)))  # 左端 0 のタイトルでも止まらず、全面の四角は動かさない
        assert [r["updatePageElementTransform"]["objectId"] for r in moved] == [logo["objectId"]] and moved[0]["updatePageElementTransform"]["transform"]["translateX"] == round((X - 0.83) * EMU)
        num = {**sn, "objectId": "n", "size": {"width": {"magnitude": EMU}, "height": {"magnitude": EMU}}}
        st = [r["updateTextStyle"]["style"] for r in styles("visual", {"objectId": "b"}, {"pageElements": [num]}) if "fontSize" in r.get("updateTextStyle", {}).get("style", {})]
        assert [s["fontSize"]["magnitude"] for s in st] == [COPYRIGHT_PT]  # ページ番号は著作権表示と同じ大きさ（高さをそろえる）
        th = themes  # Drive のプロパティ: 組むときに引く値だけ（url・元・説明・マスターにある役割の色は書かない）。124 バイトを超える値は書かない
        globals()["themes"] = lambda: {"acme": {"TEXT": "111111", "copyright": "© 2026 Acme, Inc. All rights reserved.", "url": "u", "base": "b", "NAVY": "002B5C", "description": "d"},
                                       "long": {"copyright": "©" * 60}}
        assert props("acme") == {THEME_PROP: "acme", f"{PROP}TEXT": "111111", f"{PROP}copyright": "© 2026 Acme, Inc. All rights reserved."}
        assert props("long") == {THEME_PROP: "long"}  # 124 バイトを超える値は書かない（止めない）
        globals()["themes"] = th
        with zipfile.ZipFile(BLANK_PPTX) as z:  # 白紙の pptx: 版面の大きさ、Blank だけ、スライド番号オン、ページ番号の枠のパディング 0（../assets/README.md）
            x = {n: z.read(n).decode() for n in z.namelist() if n.endswith(".xml")}
        nums = [m for n, v in x.items() if n.startswith(("ppt/slideMasters/", "ppt/slideLayouts/", "ppt/slides/"))
                for m in re.findall(r'<p:ph type="sldNum".*?<a:bodyPr[^>]*>', v, re.S)]
        assert '<p:sldSz cx="12188952" cy="6858000"' in x["ppt/presentation.xml"] and '<p:hf hdr="0" ftr="0" dt="0"/>' in x["ppt/slideMasters/slideMaster1.xml"]
        assert [n for n in x if n.startswith("ppt/slideLayouts/")] == ["ppt/slideLayouts/slideLayout7.xml"] and 'type="blank"' in x["ppt/slideLayouts/slideLayout7.xml"]
        assert len(nums) == 3 and all(all(f'{k}="0"' in m for k in ("lIns", "tIns", "rIns", "bIns")) for m in nums)
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
