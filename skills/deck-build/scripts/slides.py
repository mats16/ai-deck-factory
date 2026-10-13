#!/usr/bin/env python3
"""Google Slides を Slides API で直接組む（2026-10-07 に pptx から切り替えた。組み方と落とし穴は ../slides.md）。
資料ごとの build/pages.py に NAME（資料名・秘密区分）と make(d) だけを書き、部品は Deck のメソッドを使う。
usage（資料の build/ で。pages.py は今いるフォルダのもの）:
  slides.py new <Drive のフォルダの URL か ID> <Drive 上の名前> [--theme <テーマ>]   テンプレートを複製して組む（テーマは factory.toml の [slides.themes.<名前>]。その url のテンプレートを複製する）
  slides.py build <URL か ID> [--force]   組み直す（ページをすべて作り直す。URL は変わらない）。前に組んだあとに画面で直されているか、
                                          未解決のコメントがあれば止まる。直しを pages.py に入れてから --force で組み直す
  slides.py themes   テーマの名前・説明・テンプレートがあるか・既定か。資料ごとに選ぶ（../../deck-practices/SKILL.md の「作業の始め方」の 5）
  slides.py --selftest
テンプレートの管理は template.py。色は下の「色の役割」の名前で渡す。役割の名前はテーマの色（マスターの配色）を指すので、テンプレートを替えると色が変わる。
見た目の決まりは ../../deck-practices/visual.md の 1。"""
import atexit, functools, json, math, os, re, shutil, subprocess, sys, tempfile, time, tomllib, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True  # build/ と scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi
from gapi import (DRIVE, GSLIDES, PPTX, SLIDES, batch, delete, factory, factory_path, file_id, folder_id, request, run, slide_ids, thumbnail,
                  trash, upload)

# ---- テンプレート。ID・置き場所・既定のテーマは人ごとに違うので、Documents の直下の factory.toml の [slides] に置く（作り方は template.py） ----
BLANK = "Content E - Blank"  # テンプレートに残した、置き物のないレイアウト。ページ番号の枠だけを持つ

# ---- 版面（visual.md の 1。上端は in） ----
FONT = "Noto Sans JP"  # Google Fonts の名前。Noto Sans CJK JP と字形・文字幅は同じ（Google Fonts にない書体は黙って別の書体になる）
# Google Slides で描けることを確かめた、和文のある Google Fonts（2026-10-07。../../deck-template/SKILL.md の「書体」）。会社のテーマの書体はここから選ぶ
JP_FONTS = {FONT, "Noto Serif JP", "BIZ UDPGothic", "BIZ UDGothic", "BIZ UDPMincho", "M PLUS 1p", "M PLUS 2", "M PLUS Rounded 1c", "Zen Kaku Gothic New",
            "Zen Maru Gothic", "Sawarabi Gothic", "Kosugi Maru", "IBM Plex Sans JP", "LINE Seed JP", "Murecho", "Shippori Mincho", "Zen Old Mincho", "Klee One"}
MONO_DEFAULT = "Cascadia Mono"  # コードの箱・コマンドの等幅の書体の既定（Google Fonts。Windows Terminal の既定でリガチャがない。visual.md の 2）。和文の字形がないので、ASCII の続きにだけ付ける（mono_reqs）
LIGATURE_MONO = {"JetBrains Mono", "Fira Code", "Cascadia Code"}  # Google Fonts の版にリガチャがあり、Google Slides が描く（2026-10-09。visual.md の 2）。テーマの mono に書けない
MONO = MONO_DEFAULT  # 組むデッキの等幅の書体。テーマの mono があればそれ（use_theme）
MONO_EM = 0.586  # Cascadia Mono の英数字の幅（em。hmtx で測った。2026-10-09）。テーマで等幅の書体を替えても、この幅で見込む（ずれる。deck-template の「書体」）
EMU = 914400
INSET = 0.1  # 文字の枠の内側の余白（API で変えられない）。枠をこの分だけ外に出し、文字の端を箱の端にそろえる
PAD = 0.08   # 箱と、その上に重ねる文字の枠の間（INSET と合わせて、枠と文字の間が 1 字分ほどになる）
CORNER_RADIUS = 0.1  # in。元の AI Deck Factory の pptx と同じ、辺の長さによらない丸み
X, W = 0.6, 12.13  # 本文の左端と幅（左右の余白 0.6 in）
Y_KICK, Y_TITLE, Y_LEAD = 0.40, 0.62, 1.20
Y_BODY, Y_BODY_NOLEAD = 1.78, 1.62  # 本文の上端（リードがあるとき、ないとき）
BAND_BOTTOM, Y_SRC, Y_FOOT = 6.60, 6.68, 7.08  # 結論バンドの下端、出典の行、フッター


def _brand():
    """factory.toml の [brand]（社名と著作権表示。../../deck-template/SKILL.md）。import のときに読むので gapi.locate で探し、gapi の覚えた結果を作らない。
    書き方の誤りでは止めない（factory() を呼ぶところと factory-doctor が止める）。"""
    try:
        return tomllib.loads(p.read_text()).get("brand", {}) if (p := gapi.locate()) else {}
    except tomllib.TOMLDecodeError:
        return {}


_BRAND = _brand()
COMPANY = _BRAND.get("company", "")  # 表紙の左下。空なら置かない
PLACEHOLDER_COPYRIGHT = "© 2026 Example, Inc. All rights reserved."  # [brand] copyright を書いていないときの仮の値。これと空のときは組めない（need_brand）
BRAND_COPYRIGHT = _BRAND.get("copyright", PLACEHOLDER_COPYRIGHT)  # 初公表年。既存資料の年を現在年へ自動更新しない
COPYRIGHT = BRAND_COPYRIGHT  # 組むデッキの著作権表示。テーマの copyright があればそれ（use_theme）
LOGO = _BRAND.get("logo")  # ドキュメントの表紙のロゴ（assets/ の中のパスか URL）。なければ置かない
COPYRIGHT_PT = 9  # 著作権表示と、高さをそろえるページ番号だけは 11pt 以上の例外。本文を邪魔しない（2026-10-08、ページ番号は 2026-10-13）
# 結論バンドの内側の余白（in）。枠と文字の間は 1 字分より大きめに取る（見た目 1-8。13pt の 1 字は 0.18 in）。左右は pptx 版と同じ 18pt
BAND_PAD_X, BAND_PAD_Y = 0.25, 0.2
# [slides_py-001] 正円の番号の直径（in）と数字（pt）。M・L は数字の高さが円の 4 割ほど。S は周りの 11pt の文字に合わせて 11pt（赤に白の 14pt の決まりの例外。visual.md の 1）
NUM = {"S": (0.3, 11), "M": (0.36, 14), "L": (0.48, 18)}  # 図の中の印／カードと手順（既定）／大きな段
# [slides_py-002] 赤（RED）の線の太さ（pt）。強調の囲みは実線でも点線でも 2pt（強調のための線なので、細くしない）。ほかの枠線は 0.75pt
EMPH_PT = 2

# ---- 色の役割（visual.md の 1）。テーマの色の枠の名前 ----
NAVY, BG, RED_ON_NAVY, PANEL = "DARK1", "LIGHT1", "DARK2", "LIGHT2"  # 扉の地・見出し・結論バンド／本文の地／濃紺の上の赤／パネル
NAVY_BLOCK, GA, RED_TEXT, PREVIEW = "ACCENT1", "ACCENT2", "ACCENT3", "ACCENT4"  # 扉の中のブロック／GA の札／18pt 未満の赤の文字／Beta・Preview の札
SUB, OSS, RED = "ACCENT5", "ACCENT6", "HYPERLINK"  # 補助の文字とフッター／OSS の札／赤のアクセント（塗りと 18pt 以上の文字）
# テーマに入れない色。WHITE・CARD はどのテーマでも同じ
WHITE = CARD = "FFFFFF"
TEXT, RULE, RED_SOFT, STAGE_TEXT, DECOR = "303F47", "DCE0E2", "FFECE8", "0B2026", "3E5159"  # 本文／罫線と濃紺の上の補足／淡い赤／札の文字／章番号（飾り）
# 上の 5 色は既定の値。factory.toml の [slides.themes.<名前>] に同じ名前で書くと、そのテーマのデッキでは paint とアイコンが置き換える（use_theme）。
# pages.py には名前（か既定の 6 桁）で書く。マスターの配色に枠が残っていない（12 の枠をすべて使う）ので、組むときに置き換える
FIXED = {"TEXT": TEXT, "RULE": RULE, "RED_SOFT": RED_SOFT, "STAGE_TEXT": STAGE_TEXT, "DECOR": DECOR}
THEME_MARK = re.compile(r"ai-deck-factory theme=([A-Za-z0-9_-]+)")  # template.py がマスターのページ番号の枠の代替テキストに書く。Drive の複製でも残る（2026-10-13）
_SWAP = {}  # 組んでいるデッキの、FIXED の既定の値 → テーマの値（use_theme が決める）
# 提供ステージの札の塗り（visual.md の 1）。本番で使える Public Preview は、Beta・Private Preview（本番向けではない）の黄と分け、GA の緑を 4 割にした色（2026-10-09）
PUBLIC_PREVIEW = "99DDC7"
STAGE_FILL = {"GA": GA, "Public Preview": PUBLIC_PREVIEW, "Beta": PREVIEW, "Private Preview": PREVIEW, "OSS": OSS}  # 札の文字は OSS だけ WHITE、ほかは STAGE_TEXT
SLOTS = ("DARK1", "LIGHT1", "DARK2", "LIGHT2", "ACCENT1", "ACCENT2", "ACCENT3", "ACCENT4", "ACCENT5", "ACCENT6", "HYPERLINK", "FOLLOWED_HYPERLINK")
_COMMON = dict(DARK1="1B3139", LIGHT1="F9F7F4", DARK2="FF5F46", LIGHT2="EEEDE9", ACCENT2="00A972", ACCENT4="FFAB00",
               HYPERLINK="FF3621", FOLLOWED_HYPERLINK="954F72")
THEMES = {  # 色を変えたら template.py <テーマ> でテンプレートに入れる
    # このフォルダの色（visual.md の 1。2025 年版の公式パレットから、コントラストを確かめて選んだもの）
    "visual": {**_COMMON, "ACCENT1": "303F47", "ACCENT3": "CC2B17", "ACCENT5": "5A6F77", "ACCENT6": "2272B4"},
    # 2026 年版の「Databricks Theme」の色。役割のコントラストに届かない ACCENT5（618794、Oat Medium の上で 3.32:1）だけを暗くした
    "company": {**_COMMON, "ACCENT1": "1B5162", "ACCENT3": "98102A", "ACCENT5": "50707B", "ACCENT6": "4359FF"},
}
THEME_NOTES = {  # 組み込みのテーマの使い分け（slides.py themes が出す）。factory.toml の [slides.themes.<名前>] の description で書き換えられる
    "visual": "既定の配色。濃紺の扉、淡い Oat の本文面、赤のアクセント。会社の色の指定がない資料（勉強会、技術の説明、提案）",
    "company": "Databricks の 2026 年版の会社の色（Databricks Theme）。Databricks の正式な色にそろえたいとき",
}


# [slides_py-003] 英数字と記号の幅（em）。Noto Sans CJK JP Regular の実測（2026-10-08）。前は英数字を一律 0.57 にしていて、大文字の多い行を
# 2.52 in と見込み、2.56 in の枠に収まるとしたが、実際は 2.57 in で Google が最後の 1 字を折り返した
ASCII_EM = dict(zip(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~", (
    .22, .32, .47, .56, .56, .92, .68, .28, .34, .34, .47, .56, .28, .35, .28, .39, .56, .56, .56, .56, .56, .56, .56, .56, .56, .56, .28, .28, .56, .56,
    .56, .47, .95, .61, .66, .64, .69, .59, .55, .69, .73, .29, .54, .65, .54, .81, .72, .74, .63, .74, .64, .60, .60, .72, .57, .88, .57, .53, .60, .34,
    .39, .34, .56, .56, .61, .56, .62, .51, .62, .55, .33, .56, .61, .28, .28, .55, .28, .93, .61, .61, .62, .62, .39, .47, .38, .61, .52, .80, .50, .52,
    .47, .34, .27, .34, .56)))


def em_width(s, mono=False):
    """文字の幅の見積もり（em）。全角と、矢印・丸数字・× などの記号（U+2100 から上と ×÷±…※†‡）は 1、英数字と記号は ASCII_EM（mono なら MONO_EM）、ほかは 0.57。"""
    return sum(1.0 if ord(c) >= 0x2100 or c in "×÷±…※†‡" else MONO_EM if mono and c in ASCII_EM else ASCII_EM.get(c, 0.57) for c in s)


def wrap_lines(s, avail, size, mono=False):
    """1 段落を幅 avail（in）で折り返したときの (行数, 最終行の幅 em) の見込み。和文は 1 字ずつ、英数字の語はまとめて次の行へ送る。
    ponytail: 行頭の句読点を前の行に戻す禁則は見ない"""
    n, cur, cap = 1, 0.0, max(avail, 0.05) * 72 / size
    for word in re.findall(r"[!-~]+| +|.", s):
        for t in (word if em_width(word, mono) > cap else [word]):  # 1 行より長い語（長い識別子・URL）は、字で折る
            tw = em_width(t, mono)
            if cur + tw > cap + 1e-9 and cur > 0:
                n, cur = n + 1, (0.0 if t.isspace() else tw)
            else:
                cur += tw
    return n, cur


def est_lines(s, avail, size, mono=False):
    """幅 avail（in。文字の枠の内側）に size pt で置いたときの行数の見込み。\n と \v で改行する。英数字の語は行をまたがない
    （1 字ずつ詰めて数えると、英語の多いカードで 1 行少なく見込み、h を省いたカードから文字がはみ出した。2026-10-13）。"""
    return sum(wrap_lines(p, avail, size, mono)[0] for p in re.split(r"[\n\v]", s))


def mono_reqs(oid, s, cell=None):
    """s の中の ASCII の続き（行頭の字下げの空白も含める）を MONO にする updateTextStyle。和文は FONT のまま（MONO に和文の字形がない。lint が見る）。"""
    loc = {"cellLocation": cell} if cell else {}
    return [{"updateTextStyle": {"objectId": oid, **loc, "textRange": {"type": "FIXED_RANGE", "startIndex": u16(s[:m.start()]), "endIndex": u16(s[:m.end()])},
                                 "style": {"fontFamily": MONO}, "fields": "fontFamily"}} for m in re.finditer(r"[ -~]+", s)]


def est_h(s, avail, size, spacing=100):
    """高さの見込み（in）。行送りは文字の大きさの 1.2 倍 × 行間。"""
    return est_lines(s, avail, size) * size * 1.2 * spacing / 100 / 72


def card_h(w, head=None, body=None, items=None, step=None, bullets=False, size=11):
    """[slides_py-012] d.card の高さの見込み（in）。d.card の h を省くと、これで中身から決める。隣の列やページの下端に合わせて伸ばすと、
    中身より大きい箱になる（代表の 3 枚の記録で、ほぼすべてのデッキに出た）。列の高さをそろえるなら、並ぶカードの card_h の最大を渡す。
    ponytail: 本文は size の 1 つの大きさで見積もる。大きさの違う run（大きな数字など）が混ざるなら h を渡す"""
    top = 0.5 if head else 0.1
    if step is not None:
        return top + len(items or []) * step + 0.1
    avail = w - 2 * PAD - 2 * INSET - (size * 1.3 / 72 if bullets else 0)
    parts = [body] if isinstance(body, str) else body or []
    s = "\n\n".join(h2 + "\n" + b for h2, b in items) if items else "".join(p if isinstance(p, str) else p[0] for p in parts)
    return top + (est_h(s, avail, size, 125) + 2 * INSET if s else 0) + 0.15  # 最終行と下端の間を、白いカードの決まり（box_pad の 0.28 in）より広く


def cols(n, gap=0.24, x0=X, w=W):
    """幅 w を n 列に分けた (左端, 幅) の並び。"""
    cw = (w - gap * (n - 1)) / n
    return [(x0 + i * (cw + gap), cw) for i in range(n)]


_ICONS = {}


def render_icon(name, color):
    """react-icons のアイコン（Tb… は Tabler の線画、Si… は Simple Icons の製品のロゴ）を 256 px の PNG にし、パスを返す。"""
    if (name, color) not in _ICONS:
        d = _ICONS.setdefault("dir", tempfile.mkdtemp(prefix="slides_icons_"))
        if len(_ICONS) == 1:
            atexit.register(shutil.rmtree, d, True)
        out = os.path.join(d, f"{name}_{color}.png")
        js = ("const R = require('react'), { renderToStaticMarkup: m } = require('react-dom/server'), [n, c, o] = process.argv.slice(1);"
              "const I = require('react-icons/' + n.slice(0, 2).toLowerCase())[n]; if (!I) throw new Error('アイコンがない: ' + n);"
              "require('sharp')(Buffer.from(m(R.createElement(I, { size: 256, color: '#' + c })))).png().toFile(o);")
        subprocess.run(["node", "-e", js, name, color, out], check=True, env={**os.environ, "NODE_PATH": _npm_root()})
        _ICONS[(name, color)] = out
    return _ICONS[(name, color)]


def _npm_root():
    return subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, check=True).stdout.strip()


def png(url, w=1024):
    """SVG の URL を、Slides API が読める PNG の URL にする（wsrv.nl が幅 w px に描く）。Slides API は SVG の URL を読めない（../slides.md の 6）。"""
    return "https://wsrv.nl/?" + urllib.parse.urlencode({"url": url, "output": "png", "w": w})


@functools.lru_cache(maxsize=None)
def iconify(name, color=TEXT, w=512):
    """Iconify のアイコン（"tabler:database"、"logos:aws"）の PNG の URL。color（6 桁）は 1 色のセットにだけ効く。名前がなければ止める。
    [slides_py-004] 同じアイコンは 1 回だけ確かめる（20 枚で 60 回ほど問い合わせると 429 が返った）。"""
    svg = "https://api.iconify.design/" + name.replace(":", "/", 1) + ".svg"
    try:  # 名前の間違いは、組むときに Slides API の「画像を取れない」としか出ないので、先に確かめる。既定の User-Agent は 403 になる
        urllib.request.urlopen(urllib.request.Request(svg, method="HEAD", headers={"User-Agent": "slides.py"}), timeout=15)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit(f"アイコンがない: {name}。名前は https://icon-sets.iconify.design/ で探す")
        print(f"警告: アイコンの名前を確かめられなかった: {name}（{e.code}）。組むときに Slides API が取れなければ止まる", file=sys.stderr)
    return png(f"{svg}?color=%23{color}", w)


def asset(path):
    """使い回す画像のパス。ワークスペースの assets/ にあればそれを、なければこのスキルの assets/（出どころは assets/README.md）を使う。"""
    dirs = (factory_path().parent / "assets", Path(__file__).resolve().parent.parent / "assets")
    for d in dirs:
        if (d / path).is_file():
            return str(d / path)
    sys.exit(f"assets にない: {path}（{'、'.join(map(str, dirs))} を見た）")


def rgb(h):
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def fixed(c):
    """FIXED の既定の値なら、デッキのテーマの値（6 桁で書いた同じ値も置き換わる。refont と同じ）。ほかはそのまま。"""
    return _SWAP.get(c.upper(), c) if isinstance(c, str) else c


def paint(c):  # 役割の名前ならテーマの色、6 桁ならその色（固定の色はテーマの値）
    return {"themeColor": c} if c in SLOTS else {"rgbColor": rgb(fixed(c))}


def u16(s):  # Slides API の文字位置は UTF-16 の単位
    return len(s.encode("utf-16-le")) // 2


def emu(v):
    return {"magnitude": round(v * EMU), "unit": "EMU"}


def pt(v):
    return {"magnitude": v, "unit": "PT"}


def number_style(oid, color=SUB):
    """ページ番号の枠の文字を、著作権表示と同じ大きさ・行間にする（枠の上端は template.py が著作権表示の文字にそろえる。文字の高さがそろう）。"""
    return [{"updateTextStyle": {"objectId": oid, "textRange": {"type": "ALL"}, "style": {"fontSize": pt(COPYRIGHT_PT), "foregroundColor": {"opaqueColor": paint(color)}},
                                 "fields": "fontSize,foregroundColor"}},
            {"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"}, "style": {"lineSpacing": 100, "spaceAbove": pt(0), "spaceBelow": pt(0)},
                                      "fields": "lineSpacing,spaceAbove,spaceBelow"}}]


def place(sid, x, y, w, h, sx=1, sy=1):
    return {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
            "transform": {"scaleX": sx, "scaleY": sy, "translateX": round(x * EMU), "translateY": round(y * EMU), "unit": "EMU"}}


def run_style(st, color):
    """parts の書式（{"bold", "size", "color", "link"}）を updateTextStyle の style と fields にする。ページへのリンク（int）は finish で付ける。"""
    style, fields = {}, []
    if "bold" in st:
        style["bold"] = st["bold"]; fields.append("bold")
    if "size" in st:
        style["fontSize"] = pt(st["size"]); fields.append("fontSize")
    if isinstance(st.get("link"), str):
        style["link"] = {"url": st["link"]}
    if "link" in st:
        style["underline"] = True; fields += ["link", "underline"]
    if "color" in st or "link" in st:  # 色を書かないと、リンクの文字がテーマのリンクの色になる
        style["foregroundColor"] = {"opaqueColor": paint(st.get("color", color))}; fields.append("foregroundColor")
    return style, ",".join(fields)


def thumb_url(src, page):
    """ほかの Google Slides のページの画像（1600 × 900）の URL。d.image に渡すとページをそのまま貼れる（reuse.md の段階 1）。30 分で切れる。"""
    pid = file_id(src)
    return thumbnail(pid, slide_ids(pid)[int(page) - 1])["contentUrl"]


class Deck:
    """ページを組む要求（batchUpdate）を貯める。Google の API は build まで呼ばない。"""

    def __init__(self, name):
        self.name, self.reqs, self.notes, self.slides, self.images, self.n = name, [], {}, [], [], 0
        self.dark = set()   # 濃紺の地のページ（フッターとページ番号を淡い色にする）
        self.links = []     # ページへのリンク（要求, ページ番号）。すべてのページを作ってから付ける
        self.nofoot = set()  # フッターとページ番号を置かないページ（全面に画像を貼るページなど）
        self.round_groups = []  # 角丸・正円の背景と文字の枠を、文字を書き終わってから 1 つにまとめる
        self.warnings = []   # 組むときの見込みの警告（折り返し、見出しを縮めた、など）
        self.run = f"r{int(time.time()) % 100000}"  # 組み直すときに前の ID とぶつけない

    def oid(self):
        self.n += 1
        return f"{self.run}_{self.n:04d}"

    def warn(self, msg):
        msg = f"[p{len(self.slides)}] {msg}"
        self.warnings.append(msg)
        print("警告:", msg, file=sys.stderr)

    # ---- ページ ----
    def slide(self, bg=BG, foot=True):
        """ページ番号はテンプレートの枠（自動で振られる。表紙では消す）。foot=False のページには、フッターもページ番号も置かない。"""
        sid = self.oid()
        self.slides.append(sid)
        if bg == NAVY:
            self.dark.add(sid)
        if not foot:
            self.nofoot.add(sid)
        self.reqs += [{"createSlide": {"objectId": sid, "slideLayoutReference": {"layoutId": "@LAYOUT"},
                                       "placeholderIdMappings": [{"layoutPlaceholder": {"type": "SLIDE_NUMBER"}, "objectId": sid + "_n"}]}},
                      {"updatePageProperties": {"objectId": sid, "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": paint(bg)}}},
                                                "fields": "pageBackgroundFill"}}]
        return sid

    def note(self, sid, text):
        self.notes[sid] = text

    # ---- 図形と文字 ----
    def _shape(self, sid, x, y, w, h, fill=None, line=None, kind="RECTANGLE", sx=1, sy=1, dash=False, weight=0.75):
        """Google の 1 図形。公開部品 box から、角丸の構成要素にも使う。dash で枠線を点線に、weight（pt）で太さを変える。"""
        e = self.oid()
        outline = {"outlineFill": {"solidFill": {"color": paint(line)}}, "weight": pt(weight), **({"dashStyle": "DASH"} if dash else {})} if line else None
        props = {"shapeBackgroundFill": {"solidFill": {"color": paint(fill)}} if fill else {"propertyState": "NOT_RENDERED"},
                 "outline": outline or {"propertyState": "NOT_RENDERED"}}
        self.reqs += [{"createShape": {"objectId": e, "shapeType": kind, "elementProperties": place(sid, x, y, w, h, sx, sy)}},
                      {"updateShapeProperties": {"objectId": e, "shapeProperties": props, "fields": "shapeBackgroundFill,outline"}}]
        return e

    def box(self, sid, x, y, w, h, fill=None, line=None, kind=None, radius=CORNER_RADIUS, inner=0, dash=False, weight=None):
        """塗りの箱は半径 0.1 in の角丸が既定。輪郭だけの枠は四角。kind='RECTANGLE' で四角を明示できる。
        ROUND_RECTANGLE は四角と円の合成で半径を固定する。radius=None だけが Google 規定の丸み。
        戻りは文字を入れる透明の枠の ID。finish で背景とまとめ、編集可能な 1 グループにする。
        inner（in）は、文字の枠を左右だけ箱の内に縮める幅（枠の内側の余白 0.1 in に足す。text の pad）。
        dash で枠線を点線にし、weight（pt）で枠線の太さを変える。角丸の点線は、辺の線と角の円弧に点線を付けるので、半径は 0.1 in のまま
        [slides_py-005] （Google 標準の角丸に点線を付けると、半径が短い辺の約 1/6 になって中のカードと曲率が合わない）。
        weight を省くと、赤（RED）の線は EMPH_PT（2pt。強調の囲み）、ほかは 0.75pt。"""
        weight = weight or (EMPH_PT if line == RED else 0.75)
        kind = kind or ("ROUND_RECTANGLE" if fill else "RECTANGLE")
        if inner > 0 and (kind != "ROUND_RECTANGLE" or radius is None):  # 1 つの図形では余白を変えられないので、図形と文字の枠を分けて 1 グループにする
            bg = self._shape(sid, x, y, w, h, fill, line, kind, dash=dash, weight=weight)
            e = self._shape(sid, x + inner, y, w - 2 * inner, h)
            self.round_groups.append((bg, e, self.oid()))
            return e
        if kind != "ROUND_RECTANGLE" or radius is None:
            return self._shape(sid, x, y, w, h, fill, line, kind, dash=dash, weight=weight)
        if not math.isfinite(radius) or radius < 0 or w <= 0 or h <= 0:
            raise ValueError("角丸の半径は有限の非負値、幅と高さは正の値にする")
        r = min(radius, w / 2, h / 2)
        if r == 0 or not (fill or line):
            return self._shape(sid, x, y, w, h, fill, line, dash=dash, weight=weight)

        parts = []

        def solid(x0, y0, w0, h0, r0, color):
            """塗りだけの角丸。円を先に置き、十字の 2 つの四角で内側の円弧を覆う。外側の 1/4 円だけが残る。"""
            if r0 <= 1e-8:
                return [self._shape(sid, x0, y0, w0, h0, color)]
            out = [self._shape(sid, cx-r0, cy-r0, 2*r0, 2*r0, color, None, "ELLIPSE")
                   for cx, cy in dict.fromkeys([(x0+r0,y0+r0),(x0+w0-r0,y0+r0),(x0+r0,y0+h0-r0),(x0+w0-r0,y0+h0-r0)])]
            return out + [self._shape(sid,bx,by,bw,bh,color) for bx,by,bw,bh in [(x0+r0,y0,w0-2*r0,h0),(x0,y0+r0,w0,h0-2*r0)] if bw > 1e-8 and bh > 1e-8]

        def edge(x1,y1,x2,y2):
            if math.hypot(x2-x1,y2-y1) < 1e-8:
                return
            parts.append(self.arrow(sid,x1,y1,x2,y2,color=line,head=False,dash=dash,weight=weight))

        def ring():  # 塗りのない角丸の輪郭: 辺は線、角は Google の円弧（ARC。既定で右上の 1/4 円）を反転して 4 隅に置く。
            # 円弧を短い線 8 本でつなぐと、継ぎ目に段が出た（2026-10-08、AI Deck Factory のテンプレートの見本 p.5）
            for points in [(x+r,y,x+w-r,y),(x+r,y+h,x+w-r,y+h),(x,y+r,x,y+h-r),(x+w,y+r,x+w,y+h-r)]:
                edge(*points)
            for cx,cy,sx,sy in [(x+w-r,y+r,1,1),(x+r,y+r,-1,1),(x+w-r,y+h-r,1,-1),(x+r,y+h-r,-1,-1)]:  # 反転すると translate は反対の端になる
                parts.append(self._shape(sid,cx-r*sx,cy-r*sy,2*r,2*r,None,line,"ARC",sx,sy,dash=dash,weight=weight))

        if fill and line and dash:  # 点線は、塗りの角丸を縁取る形では作れないので、塗りの角丸の上に点線の輪郭を重ねる
            parts += solid(x, y, w, h, r, fill)
            ring()
        elif fill:
            # 枠線は線で引かず、線の色の角丸に、線の太さ（_shape と同じ 0.75 pt）だけ内側へ縮めた塗りの角丸を重ねる。
            # [slides_py-006] 円の輪郭と辺の線をつなぐと、Google の描画で継ぎ目に 1〜2 px の段が出た
            lw = weight / 72 if line else 0
            if line:
                parts += solid(x, y, w, h, r, line)
            parts += solid(x+lw, y+lw, w-2*lw, h-2*lw, max(r-lw, 0), fill)
        else:  # 透明な囲みは内側を塗れないので、輪郭を線と円弧で描く
            ring()

        bg = parts[0] if len(parts) == 1 else self.oid()
        if len(parts) > 1:
            self.reqs.append({"groupObjects":{"groupObjectId":bg,"childrenObjectIds":parts}})
        e = self._shape(sid,x+inner,y,w-2*inner,h)
        self.round_groups.append((bg,e,self.oid()))
        return e

    def text(self, sid, x, y, w, h, parts, size=11, color=TEXT, bold=False, align="START", valign="TOP",
             spacing=None, fill=None, line=None, bullets=False, kind=None, fit=True, radius=CORNER_RADIUS, edge=False, pad=None, gap=0,
             dash=False, weight=None, mono=False):
        """parts は文字列か、(文字列, {"bold":…, "color":…, "size":…, "link":…}) の並び。改行は \\n（段落を分ける）、\\v は段落の中の改行。
        link は URL か、ページ番号（int。Appendix の出典のページなど）。リンクの文字は周りの色のまま下線を付ける。
        spacing（行間、%）を省くと、2 行以上の見込みなら 125、1 行なら 100（visual.md の 2）。基準（size）の 2 倍以上の文字の段落
        （大きな数字）は、spacing によらず 100 にする（125 だと、Google の行送りでは数字と説明が離れて見えた。2026-10-08）。
        edge=True で、文字の端を (x, y)・幅 w・高さ h にそろえる（塗りのない文字。枠を INSET だけ外に出す。slides.md の 4）。
        pad（in）は、塗りか枠線のある文字の、左寄せ・右寄せのときの箱の端と文字の間。省くと 1 字分（枠でいちばん小さい文字の大きさ。lint と同じ測り方）。
        枠の内側の余白は 0.1 in で変えられず 1 字分に足りないので、文字の枠を内に縮める（visual.md の 4。lint が見る）。中央寄せには効かない。
        gap（pt）は段落の間の空き（最後の段落には付けない。付けると上下の中央が上にずれる）。
        改行を含む part は、その行が枠に収まるかを見て、収まらない見込みなら警告する（fit=False で見ない）。
        mono=True で、英数字を等幅の MONO にする（コードの箱・コマンドだけの札。visual.md の 2）。"""
        parts = [parts] if isinstance(parts, str) else parts
        full = "".join(p if isinstance(p, str) else p[0] for p in parts)
        weight = weight or (EMPH_PT if line == RED else 0.75)  # box と同じ
        if edge:
            x, y, w, h = x - INSET, y - INSET, w + 2 * INSET, h + 2 * INSET
        if not full:  # 空の文字は API が受け付けない
            return self.box(sid, x, y, w, h, fill, line, kind, radius, dash=dash, weight=weight) if fill or line else None
        smallest = min((p[1].get("size", size) if isinstance(p, tuple) else size for p in parts if (p[0] if isinstance(p, tuple) else p).strip()), default=size)
        inner = max((smallest / 72 if pad is None else pad) - INSET, 0) if (fill or line) and align != "CENTER" and kind != "ELLIPSE" else 0
        # Google は正円の文字を、内接する四角のさらに 0.1 in 内側に置く。0.3〜0.36 in の円では 14pt の数字より狭く、数字が右上にずれる
        # [slides_py-007] （0.3 in で右 3.5 pt・上 2 pt。書体を替えても直らない）。
        # 円は塗りだけにし、円と同じ大きさの透明の枠を重ねて、1 グループにする。四角の枠なら、文字の場所が数字より狭くても、はみ出しを上下・左右に
        # 均等に振って中央に置く。ただし 2 字以上は幅が足りないと折り返す（「10」は文字の場所 0.20 in で折り返し、0.22 in で 1 行）ので、横だけ数字の幅まで広げる
        ring = (x, y, w, h) if kind == "ELLIPSE" else None
        if ring:
            fw = max(w, em_width(full) * size / 72 + 2 * INSET) if len(full) > 1 else w
            x, w, spacing = x - (fw - w) / 2, fw, spacing or 100  # 行の見込みで 125 にしない（1 行で中央に置く）
        avail = w - 2 * INSET - 2 * inner - (size * 1.3 / 72 if bullets else 0)  # 箇条書きは下の indentStart の分だけ狭い（card_h と同じ）
        if fit:
            over = set()
            for p in parts:
                t, sz = (p, size) if isinstance(p, str) else (p[0], p[1].get("size", size))
                for ln in (re.split(r"[\n\v]", t) if re.search(r"[\n\v]", t) else []):
                    if ln and est_lines(ln, avail, sz, mono) > 1:
                        over.add(ln)
                        self.warn(f"手で改行した行が枠に収まらない見込み「{ln}」（{em_width(ln, mono) * sz / 72:.2f} in > {avail:.2f} in）")
            # [slides_py-013] 自動で折り返す行の、最終行の 1〜2 字（代表の 3 枚の記録で、ほぼすべてのデッキに出た）。ponytail: size の 1 つの大きさで見る
            for ln in re.split(r"[\n\v]", full):
                n, last = wrap_lines(ln, avail, size, mono)
                if n > 1 and last <= 2 and ln not in over:
                    self.warn(f"折り返した最終行が 2 字以下の見込み「{ln}」（{n} 行。言い換えか \\v で行を決める）")
        if spacing is None:
            spacing = 125 if est_lines(full.strip("\n"), avail, size, mono) > 1 else 100
        if ring:
            bg = self._shape(sid, *ring, fill, line, kind, dash=dash, weight=weight)  # 円を先に置く（文字の枠より下）
            e = self._shape(sid, x, y, w, h)
            self.round_groups.append((bg, e, self.oid()))
        else:
            e = self.box(sid, x, y, w, h, fill, line, kind, radius, inner, dash, weight)
        self.reqs += [{"updateShapeProperties": {"objectId": e, "shapeProperties": {"contentAlignment": valign}, "fields": "contentAlignment"}},
                      {"insertText": {"objectId": e, "insertionIndex": 0, "text": full}},
                      {"updateTextStyle": {"objectId": e, "textRange": {"type": "ALL"},
                                           "style": {"fontFamily": FONT, "fontSize": pt(size), "bold": bold, "foregroundColor": {"opaqueColor": paint(color)}},
                                           "fields": "fontFamily,fontSize,bold,foregroundColor"}},
                      {"updateParagraphStyle": {"objectId": e, "textRange": {"type": "ALL"},
                                                "style": {"alignment": align, "lineSpacing": spacing, "spaceAbove": pt(0), "spaceBelow": pt(0)},
                                                "fields": "alignment,lineSpacing,spaceAbove,spaceBelow"}}]
        i = 0
        for p in parts:
            s, st = (p, {}) if isinstance(p, str) else p
            if st:
                style, fields = run_style(st, color)
                req = {"updateTextStyle": {"objectId": e, "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + u16(s)},
                                           "style": style, "fields": fields}}
                if isinstance(st.get("link"), int):
                    self.links.append((req, st["link"]))
                else:
                    self.reqs.append(req)
            i += u16(s)
        if mono:
            self.reqs += mono_reqs(e, full)
        start, big, i = 0, 0, 0  # 段落ごとに、いちばん大きい文字を見る
        for s, sz in [(p, size) if isinstance(p, str) else (p[0], p[1].get("size", size)) for p in parts] + [("\n", 0)]:
            for k, piece in enumerate(s.split("\n")):
                if k:  # 段落の終わり
                    if big >= 2 * size and spacing > 100:
                        self.reqs.append({"updateParagraphStyle": {"objectId": e, "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": min(i + 1, u16(full))},
                                                                   "style": {"lineSpacing": 100}, "fields": "lineSpacing"}})
                    i += 1
                    start, big = i, 0
                i += u16(piece)
                big = max(big, sz) if piece else big
        if gap and "\n" in full:
            self.reqs.append({"updateParagraphStyle": {"objectId": e, "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": u16(full[:full.rindex("\n")]) + 1},
                                                       "style": {"spaceBelow": pt(gap)}, "fields": "spaceBelow"}})
        if bullets:  # Google は黒丸を、最初の行の字下げより文字の大きさの半分ほど左に描く（11pt で 6 pt、14pt で 7.2 pt。2026-10-08 に測った）。半分だけ字下げして、黒丸の左端を本文の左端にそろえる
            self.reqs += [{"createParagraphBullets": {"objectId": e, "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
                          {"updateParagraphStyle": {"objectId": e, "textRange": {"type": "ALL"}, "style": {"indentStart": pt(size * 1.3), "indentFirstLine": pt(size / 2)},
                                                    "fields": "indentStart,indentFirstLine"}}]
        return e

    def num(self, sid, n, cx, cy, size="M", fill=RED):
        """正円の番号。(cx, cy) は円の中心（大きさを替えても位置が動かず、横に並べる見出しと中心をそろえやすい）。size は NUM の S・M・L。"""
        dia, pt_ = NUM[size]
        return self.text(sid, cx - dia / 2, cy - dia / 2, dia, dia, str(n), size=pt_, color=WHITE, bold=True, align="CENTER", valign="MIDDLE",
                         fill=fill, kind="ELLIPSE")

    def label(self, sid, v, x, y, w, h, fill=PANEL, color=NAVY, size=11, bold=True, align="CENTER", radius=CORNER_RADIUS, pad=None, mono=False):
        """塗りの箱と、その中の短い言葉（札・日付・工程の名前）。図形と文字を 1 つにする（slides.md の 4）。
        左寄せ（align="START"）なら、箱の端と文字の間を 1 字分空ける（text の pad）。"""
        return self.text(sid, x, y, w, h, v, size=size, color=color, bold=bold, align=align, valign="MIDDLE", fill=fill, radius=radius, pad=pad, mono=mono)

    def code(self, sid, x, y, w, h, lines, hot=(), size=11):
        """濃紺のコードの箱。lines は 1 行ずつの文字列で、英数字は等幅（MONO）。hot の行（0 始まりの番号）は濃紺の上の赤の太字。
        [slides_py-008] 3 つ目の資料で要ったので pages.py から移した（slides.md の 2）。"""
        self.box(sid, x, y, w, h, NAVY)
        parts = [(ln + ("\n" if i < len(lines) - 1 else ""), {"color": RED_ON_NAVY, "bold": True} if i in hot else {}) for i, ln in enumerate(lines)]
        return self.text(sid, x + 0.22, y + 0.14, w - 0.4, h - 0.24, parts, size=size, color=WHITE, spacing=110, edge=True, mono=True)

    def card(self, sid, x, y, w, h=None, head=None, body=None, items=None, fill=CARD, line=RULE, step=None, bullets=False):
        """見出しと本文の箱。箱の上に一回り小さい文字の枠を重ねる（文字の枠の内側の余白は変えられないので、枠と文字の間をここで空ける）。
        head・body・items を省くと、白い地に罫線の箱だけを置く（中身を自分で組むカード。h を渡す）。
        body は 1 つの文字の枠に入れるもの（text の parts と同じ。bullets で箇条書き）。
        items は (見出し, 説明) の並びで、既定では 1 つの文字の枠に空行を挟んで流す（1 行と 2 行の項目が混ざっても間がそろう）。
        [slides_py-009] step（in）を渡すと、前のように項目ごとに決まった間隔で置く（左右のカードで項目の上端をそろえたいときだけ。
        決まった間隔だと、行数の違う項目の間がそろわない）。
        h を省くと中身から決める（card_h）。戻りは箱の下端（in。下に置く要素の位置に使う）。"""
        if h is None:
            if not (head or body or items):
                raise ValueError("中身を自分で組むカードは h を渡す")
            h = card_h(w, head, body, items, step, bullets)
        self.box(sid, x, y, w, h, fill, line)
        if head:
            self.text(sid, x + PAD, y + 0.1, w - 2 * PAD, 0.34, head, size=12, color=NAVY, bold=True)
        top = y + (0.5 if head else 0.1)
        if items and step is None:
            parts = []
            for i, (h2, b) in enumerate(items):
                parts += [(h2 + "\n", {"bold": True}), b + ("\n\n" if i < len(items) - 1 else "")]
            self.text(sid, x + PAD, top, w - 2 * PAD, h - (top - y) - 0.1, parts, spacing=125)
        for i, (h2, b) in enumerate(items if step is not None else []):
            self.text(sid, x + PAD, top + i * step, w - 2 * PAD, step - 0.08, [(h2 + "\n", {"bold": True}), b], spacing=125)
        if body:
            self.text(sid, x + PAD, top, w - 2 * PAD, h - (top - y) - 0.1, body, spacing=125, bullets=bullets)
        return y + h

    def table(self, sid, x, y, widths, rows, size=11, row_h=0.36, header=True, first_col=True, zebra=True, align=None, mono_cols=()):
        """rows は文字列の 2 次元の並び（1 行目が見出し）。セルの中の改行は \\n。縦の罫線なし、横の罫線は RULE（visual.md の 5）。
        見出しの行は濃紺に白の太字、1 列目は濃紺の太字（first_col）、行は 1 行おきに PANEL（zebra）。align は列ごとの "l"・"c"・"r"（金額は右）。
        行は文字に合わせて伸びる（row_h は最小）。戻りは表の下端の見込み（in。下に置く要素の位置に使う）。
        mono_cols の列は、見出しの行を除いて英数字を等幅の MONO にする（コマンドの一覧など。visual.md の 2）。"""
        t, nr, nc = self.oid(), len(rows), len(widths)
        whole = {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nr, "columnSpan": nc}

        def rng(r, c, rs=1, cs=1):
            return {"location": {"rowIndex": r, "columnIndex": c}, "rowSpan": rs, "columnSpan": cs}

        def border(pos, alpha):
            return {"updateTableBorderProperties": {"objectId": t, "tableRange": whole, "borderPosition": pos,
                                                    "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": paint(RULE), "alpha": alpha}}, "weight": pt(0.75)},
                                                    "fields": "tableBorderFill,weight"}}

        def fill(r, color):
            return {"updateTableCellProperties": {"objectId": t, "tableRange": rng(r, 0, 1, nc),
                                                  "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": paint(color)}}},
                                                  "fields": "tableCellBackgroundFill"}}

        self.reqs += [{"createTable": {"objectId": t, "rows": nr, "columns": nc, "elementProperties": place(sid, x, y, sum(widths), row_h * nr)}},
                      border("ALL", 0), border("INNER_HORIZONTAL", 1), border("BOTTOM", 1),
                      {"updateTableCellProperties": {"objectId": t, "tableRange": whole, "tableCellProperties": {"contentAlignment": "MIDDLE"},
                                                     "fields": "contentAlignment"}},
                      {"updateTableRowProperties": {"objectId": t, "rowIndices": list(range(nr)), "tableRowProperties": {"minRowHeight": emu(row_h)}, "fields": "minRowHeight"}}]
        self.reqs += [{"updateTableColumnProperties": {"objectId": t, "columnIndices": [j], "tableColumnProperties": {"columnWidth": emu(w)}, "fields": "columnWidth"}}
                      for j, w in enumerate(widths)]
        self.reqs += [fill(r, NAVY if header and r == 0 else PANEL if zebra and (r - header) % 2 else CARD) for r in range(nr)]
        bottom = y
        for r, row in enumerate(rows):
            head = header and r == 0
            lines = 1
            for c, s in enumerate(row):
                avail, mono = widths[c] - 2 * INSET, c in mono_cols and not head
                for ln in s.split("\n"):
                    if ln and est_lines(ln, avail, size, mono) > 1:
                        self.warn(f"表のセルが折り返す見込み「{ln}」（列の幅 {widths[c]:.2f} in）")
                lines = max(lines, est_lines(s, avail, size, mono))
                if not s:
                    continue
                loc = {"rowIndex": r, "columnIndex": c}
                first = first_col and c == 0 and not head
                self.reqs += [{"insertText": {"objectId": t, "cellLocation": loc, "insertionIndex": 0, "text": s}},
                              {"updateTextStyle": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"},
                                                   "style": {"fontFamily": FONT, "fontSize": pt(size), "bold": head or first,
                                                             "foregroundColor": {"opaqueColor": paint(WHITE if head else NAVY if first else TEXT)}},
                                                   "fields": "fontFamily,fontSize,bold,foregroundColor"}},
                              {"updateParagraphStyle": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"},
                                                        "style": {"lineSpacing": 120 if est_lines(s, avail, size) > 1 else 100, "spaceAbove": pt(0), "spaceBelow": pt(0),
                                                                  "alignment": {"l": "START", "c": "CENTER", "r": "END"}[(align or "l" * nc)[c]]},
                                                        "fields": "lineSpacing,spaceAbove,spaceBelow,alignment"}}]
                if mono:
                    self.reqs += mono_reqs(t, s, loc)
            bottom += max(row_h, 0.16 + lines * size * 1.2 * 1.2 / 72)
        return bottom

    def arrow(self, sid, x1, y1, x2, y2, color=SUB, head=True, dash=False, weight=1.25):
        """細い線。横の矢印は、両側の箱の上下の中央に引く（visual.md の 4。lint が見る）。dash で点線（「できるが手間」などの意味）、weight は太さ（pt）。"""
        e = self.oid()
        props = {"lineFill": {"solidFill": {"color": paint(color)}}, "weight": pt(weight), "endArrow": "FILL_ARROW" if head else "NONE"}
        if dash:
            props["dashStyle"] = "DASH"
        self.reqs += [{"createLine": {"objectId": e, "category": "STRAIGHT", "elementProperties": place(
                          sid, x1, y1, abs(x2 - x1), abs(y2 - y1), 1 if x2 >= x1 else -1, 1 if y2 >= y1 else -1)}},
                      {"updateLineProperties": {"objectId": e, "lineProperties": props, "fields": ",".join(props)}}]
        return e

    def image(self, sid, src, x, y, w, h, alt=None):
        """src は PNG・JPG・GIF の URL（SVG は png() を通す）か、手元の画像のパス（asset() か build/assets/。SVG も可）。
        縦横の比は保ったまま枠に収まり、枠の中央に置かれる。手元の画像は、build のときに carry で Slides API が読める URL にする。
        ロゴには alt に名前を入れる（代替テキスト）。"""
        e = self.oid()
        if src.startswith("http") and re.search(r"\.svg($|[?#])", src, re.I):
            sys.exit(f"Slides API は SVG の URL を読めない: {src}。png(<URL>) で PNG の URL にする（../slides.md の 6）")
        if not src.startswith("http"):
            self.images.append(os.path.abspath(src))
            src = f"@IMG{len(self.images) - 1}"
        self.reqs.append({"createImage": {"objectId": e, "url": src, "elementProperties": place(sid, x, y, w, h)}})
        if alt:
            self.reqs.append({"updatePageElementAltText": {"objectId": e, "title": alt, "description": alt}})
        return e

    def icon(self, sid, name, x, y, size, color=TEXT):
        """アイコンを size（in）の正方形に置く。name は Iconify の名前（"tabler:database"。URL のまま貼る。既定）か、react-icons の名前
        （"TbDatabase"。組むときに手元で PNG にして carry で貼る。前の pages.py のため）。color は 6 桁（1 色のアイコンにだけ効く）。代替テキストは名前。"""
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", str(color)):  # テーマの色（NAVY は "DARK1"）は画像の色にできず、透明の画像になる。lint も気づかない
            sys.exit(f"アイコンの色は 6 桁で渡す: {name} に {color!r}。テーマの色（NAVY・SUB など）は使えないので、TEXT か 6 桁にする")
        color = fixed(color)
        return self.image(sid, iconify(name, color) if ":" in name else render_icon(name, color), x, y, size, size, alt=name)

    # ---- 1 枚の型（visual.md の 1） ----
    def page(self, title, lead=None, kicker=None):
        sid = self.slide()
        if kicker:
            self.text(sid, X - INSET, Y_KICK, W + 2 * INSET, 0.26, kicker, size=11, color=RED_TEXT, bold=True)
        sz = 24  # 1 行に収まらなければ 18pt まで縮め、警告する（言い切りを短くするのが先）
        while em_width(title) * sz / 72 > W and sz > 18:
            sz -= 0.5
        if sz < 24:
            self.warn(f"見出しを {sz:g}pt に縮めた「{title}」")
        self.text(sid, X - INSET, Y_TITLE, W + 2 * INSET, 0.5, title, size=sz, color=NAVY, bold=True)
        if lead:
            if est_lines(lead, W, 12) > 1:
                self.warn(f"リードが 2 行の見込み「{lead}」")
            self.text(sid, X - INSET, Y_LEAD, W + 2 * INSET, 0.34, lead, size=12)
        return sid

    def cover(self, title, kicker, sub=None):
        """表紙: 小見出し（相手と日付）→ タイトル（2 行まで）→ 副題、左下に社名。"""
        s = self.slide(NAVY)
        self.text(s, X - INSET, 2.3, W + 2 * INSET, 0.3, kicker, size=11, color=RED_ON_NAVY, bold=True)
        lines = title.count("\n") + 1  # 2 行にするときは、文節の切れ目に \n を入れる
        self.text(s, X - INSET, 2.7, W + 2 * INSET, 0.62 * lines, title, size=34, color=WHITE, bold=True, spacing=110)
        if sub:
            self.text(s, X - INSET, 2.7 + 0.62 * lines + 0.23, W + 2 * INSET, 0.4, sub, size=13, color=RED_ON_NAVY, bold=True)
        if COMPANY:
            self.text(s, X - INSET, 6.7, W + 2 * INSET, 0.3, COMPANY, size=11, color=RULE)
        return s

    def divider(self, num, title, sub=None):
        """章の扉: 章番号（飾り）→ 章タイトル → 副題。"""
        s = self.slide(NAVY)
        self.text(s, X - INSET, 1.9, W + 2 * INSET, 1.4, num, size=88, color=DECOR, bold=True)
        self.text(s, X - INSET, 3.45, W + 2 * INSET, 0.6, title, size=30, color=WHITE, bold=True)
        if sub:
            self.text(s, X - INSET, 4.2, W + 2 * INSET, 0.4, sub, size=12.5, color=RED_ON_NAVY, bold=True)
        return s

    def band(self, sid, head, sub=None, h=None):
        """結論バンド。下端を BAND_BOTTOM に固め、中身に合わせて上へ伸ばす（h を省いたとき。1 文目と補足が 1 行ずつなら 0.86 in、1 文目だけなら 0.65 in）。
        文字と枠の間は、左右 BAND_PAD_X・上下 BAND_PAD_Y（1 字分より大きめ。見た目 1-8）。箱と文字の枠を分ける。戻りはバンドの上端（in）。"""
        avail = W - 2 * BAND_PAD_X
        if h is None:
            h = 2 * BAND_PAD_Y + est_lines(head, avail, 13) * 0.25 + (est_lines(sub, avail, 11) * 0.21 if sub else 0)
        parts = [(head, {"bold": True, "size": 13})] + ([("\n" + sub, {"size": 11, "color": RULE})] if sub else [])
        self.box(sid, X, BAND_BOTTOM - h, W, h, NAVY)
        self.text(sid, X + BAND_PAD_X - INSET, BAND_BOTTOM - h, W - 2 * (BAND_PAD_X - INSET), h, parts, color=WHITE, valign="MIDDLE", spacing=115, fit=False)
        return BAND_BOTTOM - h

    def source(self, sid, parts):
        """出典の行。頭に「出典: 」がなければ足す（lint は「出典:」の文字で出典の行を見分ける）。名前には元のページへのリンクを付ける。"""
        parts = [parts] if isinstance(parts, str) else list(parts)
        first = parts[0] if isinstance(parts[0], str) else parts[0][0]
        if not re.match(r"(出典|Sources?)[：:]", first):
            parts.insert(0, "出典: ")
        self.text(sid, X - INSET, Y_SRC, W + 2 * INSET, 0.3, parts, size=11, color=SUB, fit=False)

    def finish(self):
        """表紙・扉を含む全ページの左下に著作権表示。資料名は出さず、NAME の秘密区分だけを残す。表紙のページ番号の枠は消す。
        ページ番号は著作権表示と同じ大きさにする。濃紺の地では、著作権表示とページ番号を罫線の色にする（SUB は届かない）。foot=False の流用ページは元の表示を維持する。
        ページへのリンクを、ページの ID で付ける（番号で持つと、画面でページを足したり並べ替えたりしたときにずれる）。"""
        classification = re.search(r"(?:^|[｜|])\s*(Internal Only|Confidential)\s*$", self.name, re.I)
        footer = COPYRIGHT + (f"｜{classification.group(1)}" if classification else "")
        for sid in self.slides:
            if sid in self.nofoot:
                if sid != self.slides[0]:
                    self.reqs.append({"deleteObject": {"objectId": sid + "_n"}})
                continue
            c = RULE if sid in self.dark else SUB
            self.text(sid, X - INSET, Y_FOOT, W - 1.2, 0.28, footer, size=COPYRIGHT_PT, color=c)
            if sid != self.slides[0]:  # 前のテンプレート（ページ番号が 11pt）から作ったデッキも、組み直せばそろう
                self.reqs += number_style(sid + "_n", c)
        for req, n in self.links:
            if not 1 <= n <= len(self.slides):
                raise ValueError(f"リンク先の p.{n} がない（{len(self.slides)} 枚）")
            req["updateTextStyle"]["style"]["link"] = {"pageObjectId": self.slides[n - 1]}
            self.reqs.append(req)
        for bg, e, gid in self.round_groups:
            self.reqs.append({"groupObjects":{"groupObjectId":gid,"childrenObjectIds":[bg,e]}})
        if self.slides:
            self.reqs.append({"deleteObject": {"objectId": self.slides[0] + "_n"}})


def make_deck(make, name):
    d = Deck(name)
    make(d)
    d.finish()
    return d


def carry(paths):
    """手元の画像（PNG・JPG・GIF・SVG）を Slides API が読める URL にする。API は公開された URL の画像しか読めないので、pptxgenjs で 1 枚に
    1 つずつ入れた pptx を Drive で Google Slides に変換し、その画像の URL（30 分で切れる）を取る。SVG は API が貼れないので sharp で PNG にする。
    [slides_py-010] build の中で呼ぶので、pages.py では手元のパスを d.image に渡すだけでよい。戻り: (URL の並び, あとで消す仮のファイルの ID)。"""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "images.pptx")
        js = ("const p = new (require('pptxgenjs'))(); p.layout = 'LAYOUT_WIDE';"
              "(async () => { for (const f of process.argv.slice(2)) {"
              "  const src = /\\.svg$/i.test(f) ? { data: 'image/png;base64,' + (await require('sharp')(f, { density: 600 })"
              "    .resize({ width: 1600, withoutEnlargement: true }).png().toBuffer()).toString('base64') } : { path: f };"
              "  p.addSlide().addImage({ ...src, x: 0, y: 0, w: 1, h: 1 }); }"
              "  await p.writeFile({ fileName: process.argv[1] }); })();")
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["node", "-e", js, out, *paths], check=True, env={**os.environ, "NODE_PATH": root})
        # [slides_py-011] 仮のファイルは My Drive の直下に置く（フォルダの ID を持つと、スクリプトをほかの人に渡したときに動かない）
        fid = upload(open(out, "rb").read(), PPTX, "tmp_images", convert=GSLIDES)["id"]
    try:
        p = request("GET", f"{SLIDES}/{fid}?fields=slides(pageElements(image(contentUrl)))")
        return [s["pageElements"][0]["image"]["contentUrl"] for s in p["slides"]], fid
    except BaseException:
        delete(fid)
        raise


STAMP = "slides_py_revision"  # 組んだときの版（presentations の revisionId）を、Drive のファイルの appProperties に残す


def revision(pid):
    return request("GET", f"{SLIDES}/{pid}?fields=revisionId")["revisionId"]


def need_brand():
    """[brand] copyright（テーマの copyright があればそれ）がなければ止める。仮の著作権表示を全ページに書いた資料を出さないため（lint は形しか見ないので、仮の値も通る）。
    スライド・ドキュメント・テンプレートを組む build が、Slides・Docs に送る前に呼ぶ。"""
    if COPYRIGHT.strip() in ("", PLACEHOLDER_COPYRIGHT):  # 空（copyright = ""）と、前後に空白を付けた仮の値も、書いていないのと同じ（doctor と同じ判定）
        sys.exit("factory.toml の [brand]（テーマごとに変えるなら [slides.themes.<名前>]）に copyright（例: copyright = \"© 2026 Acme, Inc. All rights reserved.\"）を書いてから組む。"
                 "書かないと全ページの左下が仮の表示（Example, Inc.）になる")


def deck_theme(p):
    """presentations の masters・layouts の代替テキストにある、テーマの名前（THEME_MARK）。なければ None（template.py で合わせ直す前のテンプレートから作ったデッキ）。"""
    return next((m.group(1) for pg in p.get("masters", []) + p.get("layouts", []) for e in pg.get("pageElements", [])
                 if (m := THEME_MARK.search(e.get("description", "")))), None)


def theme_table(name):
    """factory.toml の [slides.themes.<name>]。name が None か、そのテーマがなければ {}（今の値で組む）。"""
    return factory().get("slides", {}).get("themes", {}).get(name, {}) if name and gapi.find_factory() else {}


def theme_fixed(t):
    """テーマの表 t の固定の色（名前 → 6 桁）。書いていない色は FIXED の既定。"""
    if bad := [k for k in FIXED if k in t and not re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(t[k]))]:
        sys.exit(f"[slides.themes] の {', '.join(bad)} が 6 桁の 16 進の色でない（例: TEXT = \"37352F\"）")
    return {k: str(t.get(k, v)).lstrip("#").upper() for k, v in FIXED.items()}


def use_theme(t):
    """テーマの表 t（theme_table）の固定の色・著作権表示・等幅の書体で組む。make_deck の前に呼ぶ（pages.py が作る要求に効かせる）。"""
    global COPYRIGHT, MONO
    _SWAP.clear()
    _SWAP.update({FIXED[k]: v for k, v in theme_fixed(t).items() if v != FIXED[k]})
    COPYRIGHT = t.get("copyright", BRAND_COPYRIGHT)
    MONO = theme_mono(t)


def theme_mono(t):
    """テーマの表 t（[slides.themes]・[docs.themes]）の等幅の書体。書いていなければ MONO_DEFAULT。和文を載せないので JP_FONTS には限らない（Google Fonts にない書体は黙って別の書体になる）。"""
    if not isinstance(m := t.get("mono", MONO_DEFAULT), str) or not m.strip():
        sys.exit(f"テーマの mono {m!r} は書体の名前でない（例: mono = \"Cascadia Mono\"）")
    if m.strip() in LIGATURE_MONO:
        sys.exit(f"テーマの mono {m!r} は、Google が描くとリガチャが出る（-> が矢印 1 字になる。visual.md の 2）。リガチャのない書体にする")
    return m.strip()


def deck_mono(p):
    """デッキの等幅の書体（デッキのテーマの mono。lint が比べる）。マスターにコードの枠がないので、deck_font と違いテーマの名前から引く。"""
    return theme_mono(theme_table(deck_theme(p)))


def theme_of(pid):
    """プレゼン（かテンプレート）pid のテーマの名前（deck_theme）。"""
    return deck_theme(request("GET", f"{SLIDES}/{pid}?fields=masters(pageElements(description)),layouts(pageElements(description))"))


def build(pid, deck, force=False):
    """pid のプレゼンのページを、deck のページに置き換える。force=False なら、先に guard で画面での直しとコメントを確かめる。"""
    need_brand()
    if not force:
        gapi.guard(pid, revision(pid), STAMP, "pages.py")
    p = request("GET", f"{SLIDES}/{pid}?fields=slides(objectId),layouts(objectId,layoutProperties(displayName),pageElements(shape(placeholder))),"
                       "masters(pageElements(shape))")
    ls = [l for l in p["layouts"] if is_blank(l)]  # 会社のテンプレートから作ったものは、template.py が残した Blank が 1 つだけ（名前は会社のもの）
    layout = next((l["objectId"] for l in ls if l["layoutProperties"]["displayName"] == BLANK), ls[0]["objectId"] if len(p["layouts"]) == 1 and ls else None)
    if not layout:
        sys.exit(f"レイアウト「{BLANK}」がない。AI Deck Factory のテンプレートから作ったプレゼンではない（slides.py new で作る）")
    font = deck_font(p)
    reqs = json.dumps(refont(deck.reqs, font)).replace('"@LAYOUT"', json.dumps(layout))
    # 新しいページを先に作ってから、前のページを消す。ページが 0 枚になると、使われていないマスターごと消える
    old = [{"deleteObject": {"objectId": s["objectId"]}} for s in p.get("slides", [])]
    carrier = None
    try:
        if deck.images:
            urls, carrier = carry(deck.images)
            reqs = re.sub(r'"@IMG(\d+)"', lambda m: json.dumps(urls[int(m.group(1))]), reqs)
        batch(pid, json.loads(reqs) + old)
    finally:
        if carrier:  # 貼った画像はデッキの中に写し取られているので、仮のファイルは消してよい
            delete(carrier)
    p = request("GET", f"{SLIDES}/{pid}?fields=slides(objectId,slideProperties(notesPage(notesProperties)))")
    spk = {s["objectId"]: s["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"] for s in p["slides"]}
    nreqs = []  # ノートの枠はページを作ったあとでないと ID が分からないので、2 回目に書く
    for sid, t in deck.notes.items():
        if not t:
            continue
        nreqs += [{"insertText": {"objectId": spk[sid], "insertionIndex": 0, "text": t}},
                  {"updateTextStyle": {"objectId": spk[sid], "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}}]
    batch(pid, nreqs)
    gapi.stamp(pid, revision(pid), STAMP)
    missing = [i for i, s in enumerate(deck.slides, 1) if not deck.notes.get(s)]
    print(json.dumps({"presentationId": pid, "url": f"https://docs.google.com/presentation/d/{pid}/edit",
                      "slides": len(deck.slides), "requests": len(deck.reqs) + len(old) + len(nreqs), "pages_without_notes": missing,
                      "warnings": len(deck.warnings)}, ensure_ascii=False))


def placeholders(page):
    """ページ（マスター・レイアウト）のプレースホルダーの型の並び。"""
    return [e["shape"]["placeholder"]["type"] for e in page.get("pageElements", []) if "placeholder" in e.get("shape", {})]


def is_blank(layout):
    """slides.py が組めるレイアウトか。プレースホルダーはページ番号の枠だけ（ほかの枠があると、全ページに空の枠が残る）。"""
    return placeholders(layout) == ["SLIDE_NUMBER"]


def deck_font(p):
    """デッキの書体。テンプレートのマスターのプレースホルダーの書体（template.py が書く。本文の枠を先に見る）のうち、JP_FONTS にあるもの。
    なければ FONT（社内資料の複製など、マスターが欧文の書体のデッキは FONT で組み、lint も FONT と比べる）。pages.py は FONT で組み、build が置き換える。"""
    els = [e for m in p.get("masters", []) for e in m.get("pageElements", []) if "placeholder" in e.get("shape", {})]
    for e in sorted(els, key=lambda e: e["shape"]["placeholder"].get("type") != "BODY"):
        for t in e["shape"].get("text", {}).get("textElements", []):
            if (f := t.get("textRun", {}).get("style", {}).get("fontFamily")) in JP_FONTS:
                return f
    return FONT


def refont(o, font):
    """組む requests の書体 FONT を font にする（fontFamily の値だけ。資料の文に書体の名前があっても変えない）。"""
    if isinstance(o, dict):
        return {k: font if k == "fontFamily" and v == FONT else refont(v, font) for k, v in o.items()}
    return [refont(v, font) for v in o] if isinstance(o, list) else o


def theme_list():
    """(名前, 説明, テンプレートがあるか, 既定か) の並び。組み込みのテーマと、factory.toml の [slides.themes] の名前。"""
    cfg = factory().get("slides", {})
    mine = cfg.get("themes", {})
    return [(n, mine.get(n, {}).get("description") or THEME_NOTES.get(n, ""), bool(mine.get(n, {}).get("url")), n == cfg.get("default_theme", "visual"))
            for n in dict.fromkeys([*THEMES, *mine])]


def cmd_themes():
    """テーマを 1 行ずつ出す。エージェントが、資料の種類と聞き手に合うものを選ぶ。テンプレートのないテーマは選べない（template.py で作る）。"""
    for name, note, has, default in theme_list():
        print(f"{name}{'（既定）' if default else ''}\t{'テンプレートあり' if has else 'テンプレートなし'}\t"
              + (note or f"（説明がない。factory.toml の [slides.themes.{name}] の description に書く）"))


def need_theme(theme):
    """new で、テンプレートのあるテーマが 2 つ以上あるのに --theme がなければ、一覧を出して止める。資料ごとに description でテーマを選ばせる
    （Agent Skills でスキルの一覧が毎回出るのと同じ役目。deck-practices の「作業の始め方」の 5）。factory-kaizen の検証で組む仮の資料は止めない。"""
    if theme is None and len(templates()) >= 2 and not os.environ.get("FACTORY_VERIFY"):
        cmd_themes()
        sys.exit("テーマを選んでから組む。上の description と、資料の種類・聞き手を突き合わせて、slides.py new <フォルダ> <名前> --theme <名前> で渡す"
                 "（description で決まらなければ既定のテーマ）。選んだテーマと理由は構成案の前提に書く")


def templates():
    """テーマごとのテンプレートの ID（factory.toml の [slides.themes.<名前>] の url。URL のまま書いてある）。"""
    return {k: file_id(t["url"]) for k, t in factory().get("slides", {}).get("themes", {}).items() if t.get("url")}


def template_id(theme=None):
    """テーマのテンプレートの ID。theme を省くと factory.toml の default_theme。"""
    theme, T = theme or factory().get("slides", {}).get("default_theme", "visual"), templates()  # 既定は factory-doctor と同じ visual
    if theme not in T:
        sys.exit(f"テーマ {theme} のテンプレートが factory.toml の [slides.themes.{theme}] の url にない（url があるテーマ: {', '.join(T) or 'なし'}）。template.py {theme} --from-base で作る")
    return T[theme]


def new(folder, name, src):
    """テンプレート src（template_id）を Drive のフォルダに複製して、その ID を返す。"""
    if not re.match(r"\d{8}_", name):
        sys.exit("Drive 上の名前は YYYYMMDD_ で始める: " + name)
    return request("POST", f"{DRIVE}/files/{src}/copy?supportsAllDrives=true&fields=id",
                   {"name": name, "parents": [folder_id(folder)]})["id"]


def load_pages():
    """今いるフォルダの pages.py を読む。pages.py の「from slides import …」には、このモジュールをそのまま渡す（2 つ目を読み込まない）。"""
    sys.modules["slides"] = sys.modules[__name__]
    sys.path.insert(0, os.getcwd())
    from pages import NAME, make
    return make, NAME


def selftest():
    assert gapi.find_factory.cache_info().currsize == 0  # import で [brand] を読んでも、gapi の覚えた結果を作らない（あとで今いるフォルダを変える factory-doctor のため）
    assert paint(NAVY) == {"themeColor": "DARK1"} and paint("FFFFFF") == {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
    assert u16("𝄞あ") == 3  # サロゲートペアは 2
    if COPYRIGHT.strip() == PLACEHOLDER_COPYRIGHT:  # factory.toml の [brand] がないところで回したとき
        try:
            need_brand()
            raise AssertionError("仮の著作権表示のまま組める")
        except SystemExit as e:
            assert "[brand]" in str(e)
    ph = lambda t, f: {"shape": {"placeholder": {"type": t}, "text": {"textElements": [{"textRun": {"style": {"fontFamily": f}}}]}}}
    assert deck_font({"masters": [{"pageElements": [ph("TITLE", "BIZ UDPGothic")]}]}) == "BIZ UDPGothic" and deck_font({"masters": [{}]}) == FONT  # 書体はテンプレートのマスターから
    assert deck_font({"masters": [{"pageElements": [ph("TITLE", "DM Sans")]}]}) == FONT  # 欧文の書体のマスター（社内資料の複製）は FONT
    assert deck_font({"masters": [{"pageElements": [ph("TITLE", "Noto Serif JP"), ph("BODY", "BIZ UDPGothic")]}]}) == "BIZ UDPGothic"  # 本文の枠を先に見る
    assert refont([{"style": {"fontFamily": FONT}}, {"insertText": {"text": FONT}}], "X") == [{"style": {"fontFamily": "X"}}, {"insertText": {"text": FONT}}]
    assert is_blank({"pageElements": [{"shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}]}) and not is_blank({"pageElements": [ph("TITLE", FONT)]})
    assert all(set(SLOTS) == set(t) for t in THEMES.values()) and set(THEME_NOTES) == set(THEMES)  # 配色は 12 の枠をすべて決める（API の決まり）。組み込みのテーマには説明がある
    corners = Deck("角丸")
    sid = corners.slide()
    for height in (1, 3):
        start = len(corners.reqs)
        corners.text(sid,1,1,6,height,"角丸の文字",fill=PANEL)
        circles = [r["createShape"]["elementProperties"]["size"] for r in corners.reqs[start:]
                   if r.get("createShape",{}).get("shapeType") == "ELLIPSE"]
        assert len(circles) == 4 and all(abs(c[k]["magnitude"] - .2*EMU) < 1e-6 for c in circles for k in ("width","height"))  # 高さが変わっても半径 0.1 in
    cards = Deck("カード")
    csid = cards.slide()
    texts = lambda f: (lambda n: (f(), sum("insertText" in r for r in cards.reqs[n:]))[1])(len(cards.reqs))
    items = [("項目 1", "1 行"), ("項目 2", "2 行になる長い説明")]
    assert texts(lambda: cards.card(csid, 1, 1, 4, 3, head="見出し", items=items)) == 2  # items は既定で 1 つの枠に流す（見出し＋本文）
    assert texts(lambda: cards.card(csid, 1, 1, 4, 3, head="見出し", items=items, step=0.9)) == 3  # step を渡すと項目ごとの枠
    start = len(corners.reqs)
    corners.box(sid,1,1,4,2,fill=CARD,line=RULE)  # 枠線つき: 線の色の角丸 + 内側の塗りの角丸。線（createLine）は使わない（継ぎ目の段が出る）
    made = [r["createShape"] for r in corners.reqs[start:] if "createShape" in r]
    assert not any("createLine" in r for r in corners.reqs[start:]) and sum(c["shapeType"] == "ELLIPSE" for c in made) == 8
    assert any(c["shapeType"] == "ELLIPSE" and abs(c["elementProperties"]["size"]["width"]["magnitude"] - (.2 - 1.5/72)*EMU) < 2 for c in made)  # 内側の半径は線の太さだけ小さい
    start = len(corners.reqs)
    corners.box(sid,1,1,4,2,line=RULE,kind="ROUND_RECTANGLE")  # 塗りのない角丸: 辺は線 4 本、角は円弧 4 つ（短い線でつながない）
    made = corners.reqs[start:]
    assert sum("createLine" in r for r in made) == 4 and sum(r.get("createShape",{}).get("shapeType") == "ARC" for r in made) == 4
    assert {(r["createShape"]["elementProperties"]["transform"]["scaleX"], r["createShape"]["elementProperties"]["transform"]["scaleY"]) for r in made
            if r.get("createShape",{}).get("shapeType") == "ARC"} == {(1,1),(-1,1),(1,-1),(-1,-1)}
    start = len(corners.reqs)
    corners.box(sid,1,1,4,2,line=RED,kind="ROUND_RECTANGLE",dash=True)  # 点線の角丸: 辺 4 本と円弧 4 つに点線と 2pt（赤の線の既定）
    made = corners.reqs[start:]
    lines = [r["updateLineProperties"]["lineProperties"] for r in made if "updateLineProperties" in r]
    arcs = {r["createShape"]["objectId"] for r in made if r.get("createShape",{}).get("shapeType") == "ARC"}
    arc_lines = [r["updateShapeProperties"]["shapeProperties"]["outline"] for r in made if r.get("updateShapeProperties",{}).get("objectId") in arcs]
    assert len(lines) == 4 and len(arc_lines) == 4 and all(o["dashStyle"] == "DASH" and o["weight"]["magnitude"] == 2 for o in lines + arc_lines)
    assert not any(r.get("createShape",{}).get("shapeType") == "ROUND_RECTANGLE" for r in made)  # Google 標準の角丸（曲率が合わない）を使わない
    for color, want in ((RED, 2), (RULE, .75)):  # 赤の線の囲みは実線でも 2pt、ほかは 0.75pt
        start = len(corners.reqs)
        corners.box(sid,1,1,4,2,line=color,kind="ROUND_RECTANGLE")
        ws = [r["updateLineProperties"]["lineProperties"]["weight"]["magnitude"] for r in corners.reqs[start:] if "updateLineProperties" in r]
        ws += [r["updateShapeProperties"]["shapeProperties"]["outline"]["weight"]["magnitude"] for r in corners.reqs[start:]
               if "outline" in r.get("updateShapeProperties", {}).get("shapeProperties", {}) and "weight" in r["updateShapeProperties"]["shapeProperties"]["outline"]]
        assert len(ws) == 8 and set(ws) == {want}, (color, ws)
    start = len(corners.reqs)
    corners.box(sid,1,1,4,2,fill=CARD,line=RED,dash=True)  # 塗りと点線: 塗りの角丸（円 4 つ）の上に点線の輪郭
    made = corners.reqs[start:]
    assert sum("createLine" in r for r in made) == 4 and sum(r.get("createShape",{}).get("shapeType") == "ELLIPSE" for r in made) == 4
    start = len(corners.reqs)
    corners.box(sid,1,1,2,1,line=SUB,kind="FOLDED_CORNER",dash=True)  # 1 つの図形は枠線に点線
    assert corners.reqs[start+1]["updateShapeProperties"]["shapeProperties"]["outline"]["dashStyle"] == "DASH"
    corners.arrow(sid,0,0,1,0,dash=True)
    assert corners.reqs[-1]["updateLineProperties"]["lineProperties"]["dashStyle"] == "DASH" and "dashStyle" in corners.reqs[-1]["updateLineProperties"]["fields"]
    anchor = corners.box(sid,1,1,.1,.1,fill=PANEL)  # 半径を短辺の半分に抑える。背景 1 要素でも groupObjects は 2 要素以上
    start = len(corners.reqs)
    square = corners.box(sid,1,1,2,1,fill=PANEL,kind="RECTANGLE")
    assert len(corners.reqs)-start == 2 and corners.reqs[start]["createShape"]["objectId"] == square
    for n, fw in (("1", .3), ("10", em_width("10")*14/72 + 2*INSET)):  # 正円の番号: 塗りの円 + 円と同じ高さの透明の枠。幅は 1 字なら円と同じ、2 字なら数字の幅
        start = len(corners.reqs)
        frame = corners.text(sid,1,1,.3,.3,n,size=14,align="CENTER",valign="MIDDLE",fill=RED,kind="ELLIPSE")
        made = [r["createShape"] for r in corners.reqs[start:] if "createShape" in r]
        assert [c["shapeType"] for c in made] == ["ELLIPSE","RECTANGLE"] and made[1]["objectId"] == frame == corners.round_groups[-1][1]
        size, move = made[1]["elementProperties"]["size"], made[1]["elementProperties"]["transform"]
        assert abs(size["width"]["magnitude"] - fw*EMU) < 2 and abs(size["height"]["magnitude"] - .3*EMU) < 2
        assert abs(move["translateX"] - (1.15 - fw/2)*EMU) < 2 and abs(move["translateY"] - EMU) < 2  # 円の中心にそろえる
        assert not any(r.get("updateParagraphStyle",{}).get("style",{}).get("lineSpacing") == 125 for r in corners.reqs[start:])  # 行間は 100
    start = len(corners.reqs)
    corners.num(sid, 3, 2, 2, "L")  # 中心で置き、大きさと文字は NUM から
    circle = next(r["createShape"]["elementProperties"] for r in corners.reqs[start:] if r.get("createShape",{}).get("shapeType") == "ELLIPSE")
    assert abs(circle["size"]["width"]["magnitude"] - NUM["L"][0]*EMU) < 2 and abs(circle["transform"]["translateX"] - (2 - NUM["L"][0]/2)*EMU) < 2
    assert any(r.get("updateTextStyle",{}).get("style",{}).get("fontSize") == pt(NUM["L"][1]) for r in corners.reqs[start:])
    corners.finish()
    assert len(corners.round_groups) == 12 and all(len(r["groupObjects"]["childrenObjectIds"]) >= 2 for r in corners.reqs if "groupObjects" in r)
    assert all(any(r.get("groupObjects",{}).get("childrenObjectIds") == [bg,e] for r in corners.reqs) for bg,e,gid in corners.round_groups)  # 文字と背景を 1 つにする
    assert any(r.get("insertText",{}).get("text") == "角丸の文字" for r in corners.reqs)
    # 塗りの箱の左寄せの文字は、箱の端から 1 字分（文字の大きさ）。中央寄せと塗りのない文字は枠のまま。四角の箱も図形と文字の枠を分ける
    g = Deck("余白")
    sid = g.slide()
    frame_x = lambda e: next(r["createShape"]["elementProperties"]["transform"]["translateX"] for r in g.reqs if r.get("createShape", {}).get("objectId") == e) / EMU
    assert abs(frame_x(g.label(sid, "札", 1, 1, 4, .5, size=14, align="START")) - (1 + 14 / 72 - INSET)) < 1e-6
    assert abs(frame_x(g.text(sid, 1, 1, 4, .5, "札", size=12, fill=PANEL, kind="RECTANGLE", align="END")) - (1 + 12 / 72 - INSET)) < 1e-6
    assert g.round_groups[-1][1] != g.round_groups[-1][0]
    assert abs(frame_x(g.label(sid, "札", 1, 1, 4, .5)) - 1) < 1e-6 and abs(frame_x(g.text(sid, 1, 1, 4, .5, "本文")) - 1) < 1e-6
    assert abs(frame_x(g.label(sid, "札", 1, 1, 4, .5, align="START", pad=INSET)) - 1) < 1e-6  # pad で前の置き方に戻せる
    big_only = g.text(sid, 1, 1, 4, .5, [("$20,000", {"size": 32}), (" / 年", {"size": 16})], fill=PANEL)  # 枠でいちばん小さい文字（16pt）の 1 字
    assert abs(frame_x(big_only) - (1 + 16 / 72 - INSET)) < 1e-6
    assert abs(frame_x(g.text(sid, 1, 1, 4, .5, "本文", edge=True)) - (1 - INSET)) < 1e-6  # 文字の端を (x, y) に
    # 大きな数字の段落だけ行間 100。段落の間の空き（gap）は最後の段落に付けない
    start = len(g.reqs)
    e = g.text(sid, 1, 1, 4, 2, [("97%\n", {"size": 40, "bold": True}), "説明\n2 行目"], size=12, spacing=125, gap=4)
    styles = [r["updateParagraphStyle"] for r in g.reqs[start:] if r.get("updateParagraphStyle", {}).get("objectId") == e and r["updateParagraphStyle"]["textRange"]["type"] == "FIXED_RANGE"]
    assert [(s["textRange"]["endIndex"], s["style"]) for s in styles] == [(4, {"lineSpacing": 100}), (u16("97%\n説明\n"), {"spaceBelow": pt(4)})]
    start = len(g.reqs)
    g.text(sid, 1, 1, 4, 2, "表紙の\n2 行", size=34, spacing=110)  # 同じ大きさの段落は行間を変えない
    assert not any(r.get("updateParagraphStyle", {}).get("textRange", {}).get("type") == "FIXED_RANGE" for r in g.reqs[start:])
    start = len(g.reqs)
    g.card(sid, 1, 1, 3, 2)  # 見出しを省くと箱だけ
    assert not any("insertText" in r for r in g.reqs[start:])
    start = len(g.reqs)
    g.code(sid, 1, 1, 6, 1, ["ln -s a b", "pi mcp list"], hot=(1,))  # コードの箱: 等幅、hot の行は赤の太字
    assert any(r.get("updateTextStyle", {}).get("style", {}).get("fontFamily") == MONO for r in g.reqs[start:])
    assert any(r.get("updateTextStyle", {}).get("style", {}).get("foregroundColor") == {"opaqueColor": paint(RED_ON_NAVY)} for r in g.reqs[start:])

    def make(d):
        d.cover("t", "k")
        s = d.page("t")
        d.image(s, "x.png", 0, 0, 1, 1)
        d.text(s, X, Y_BODY, W, 1, ["出典: ", ("次のページ", {"link": 3}), "、", ("docs", {"link": "https://docs.databricks.com/"})])
        d.card(d.page("t"), X, Y_BODY, 4, 2, "見出し", items=[("項目", "説明")])
    d = make_deck(make, "foot")
    assert d.reqs[-1] == {"deleteObject": {"objectId": d.slides[0] + "_n"}} and d.images[0].endswith("x.png")
    assert sum(1 for r in d.reqs if r.get("insertText", {}).get("text") == COPYRIGHT) == 3  # 表紙も含む全ページに著作権表示
    assert [r["updateTextStyle"]["objectId"] for r in d.reqs if r.get("updateTextStyle", {}).get("style", {}).get("fontSize") == pt(COPYRIGHT_PT)
            and r["updateTextStyle"]["objectId"].endswith("_n")] == [s + "_n" for s in d.slides[1:]]  # 表紙のほかのページ番号を著作権表示と同じ大きさに
    assert not any(r.get("insertText", {}).get("text") == "foot" for r in d.reqs)  # 資料名は表示しない
    links = [r["updateTextStyle"]["style"]["link"] for r in d.reqs if "link" in r.get("updateTextStyle", {}).get("style", {})]
    assert {"pageObjectId": d.slides[2]} in links and {"url": "https://docs.databricks.com/"} in links  # ページへのリンクは ID で付ける
    assert est_lines("あ" * 10, 10 * 11 / 72, 11) == 1 and est_lines("あ" * 11, 10 * 11 / 72, 11) == 2 and est_lines("a\nb", 1, 11) == 2
    w = make_deck(lambda d: (d.text(d.page("t"), 0, 0, 1.2, 1, "短い\nとても長くて枠に収まらない行"), d.text(d.slides[-1], 0, 0, 1.2, 1, "")), "foot")
    assert len(w.warnings) == 1 and "収まらない" in w.warnings[0]  # 手で改行した行の見込み。空の文字は置かない
    one = 10 * 11 / 72  # 11pt の 10 字の幅
    assert wrap_lines("あ" * 9 + " Codex", one, 11) == (2, em_width("Codex"))  # 英数字の語は行をまたがず送る（空白は行頭に残さない）
    assert est_lines("あ" * 9 + " Codex", one, 11) == 2
    assert wrap_lines("W" * 20, 1, 11)[0] == 3  # 1 行より長い語は字で折る
    w = make_deck(lambda d: d.text(d.page("t"), 0, 0, 1 + 2 * INSET, 1, "W" * 20 + "\nOK"), "foot")
    assert len(w.warnings) == 1 and "収まらない" in w.warnings[0]  # 長い識別子だけの行も、収まらない見込みに出す
    w = make_deck(lambda d: d.text(d.page("t"), 0, 0, one + 2 * INSET, 1, "あ" * 10, bullets=True), "foot")
    assert len(w.warnings) == 1 and "最終行が 2 字以下" in w.warnings[0]  # 箇条書きの字下げで 10 字が 2 行になる
    w = make_deck(lambda d: [d.text(d.page("t"), 0, 0, one + 2 * INSET, 1, t) for t in ("あ" * 11, "あ" * 14, "×")], "foot")
    assert len(w.warnings) == 1 and "最終行が 2 字以下" in w.warnings[0]  # 11 字は 1 字の最終行。14 字（4 字）と 1 字だけの枠は出さない
    c = Deck("c")
    sid = c.page("t")
    assert c.card(sid, 1, 1, 3, None, "見出し", body="あ" * 30) == 1 + card_h(3, "見出し", body="あ" * 30)  # h を省くと中身から決め、下端を返す
    assert card_h(3, "見出し", body="あ" * 30) > card_h(3, "見出し", body="あ" * 10) > card_h(3, "見出し") > 0.5
    assert card_h(3, items=[("a", "b"), ("c", "d")]) == card_h(3, body="a\nb\n\nc\nd")  # items は空行を挟んで 1 つの枠に流す
    try:
        c.card(sid, 1, 1, 3)
        raise AssertionError("中身のないカードを h なしで通した")
    except ValueError:
        pass
    t = make_deck(lambda d: d.source(d.page("t"), ["Databricks"]), "foot")
    assert any(r.get("insertText", {}).get("text") == "出典: Databricks" for r in t.reqs)  # 出典の行の頭
    t = make_deck(lambda d: d.band(d.page("t"), "あ" * 120, "補足"), "foot")
    shapes = [r["createShape"]["elementProperties"] for r in t.reqs if "createShape" in r]
    assert any(e["size"]["height"]["magnitude"] > 1.0 * EMU for e in shapes)  # 2 行ならバンドが伸びる（1 行ずつなら 0.86 in）
    assert any(e["transform"]["translateX"] == round((X + BAND_PAD_X - INSET) * EMU) for e in shapes)  # 文字の左端は箱から BAND_PAD_X
    f = make_deck(lambda d: (d.cover("t", "k"), d.slide(foot=False)), "foot")
    assert {"deleteObject": {"objectId": f.slides[1] + "_n"}} in f.reqs and not any(r.get("insertText", {}).get("text") == "foot" for r in f.reqs)
    assert sum(r.get("insertText", {}).get("text") == COPYRIGHT for r in f.reqs) == 1  # 流用ページには著作権表示を重ねない
    f = make_deck(lambda d: (d.cover("t", "k"), d.divider("1", "扉"), d.page("本文")), "資料名｜Internal Only")
    feet = [r["insertText"] for r in f.reqs if r.get("insertText", {}).get("text") == COPYRIGHT + "｜Internal Only"]
    assert len(feet) == 3 and not f.warnings  # 秘密区分を表紙にも残し、1 行で収める
    colors = {r["updateTextStyle"]["objectId"]: r["updateTextStyle"]["style"].get("foregroundColor")
              for r in f.reqs if "updateTextStyle" in r and "foregroundColor" in r["updateTextStyle"]["style"]}
    assert [colors[r["objectId"]] for r in feet] == [{"opaqueColor": paint(c)} for c in (RULE, RULE, SUB)]  # 地に合わせる
    try:
        make_deck(lambda d: d.text(d.page("t"), 0, 0, 1, 1, [("p.9", {"link": 9})]), "foot")
        raise AssertionError("ないページへのリンクを通した")
    except ValueError:
        pass
    # SVG の URL の中の ? と # が wsrv.nl に渡る前に解けないよう、二重にエンコードする（# は %2523）
    assert png("https://api.iconify.design/tabler/database.svg?color=%23303F47", 512) == ("https://wsrv.nl/?url=https%3A%2F%2Fapi.iconify.design"
                                                                                       "%2Ftabler%2Fdatabase.svg%3Fcolor%3D%2523303F47&output=png&w=512")
    try:
        make_deck(lambda d: d.image(d.page("t"), "https://example.com/a.svg?v=1", 0, 0, 1, 1), "foot")
        raise AssertionError("SVG の URL を通した")
    except SystemExit:
        pass
    try:
        make_deck(lambda d: d.icon(d.page("t"), "tabler:database", 0, 0, 0.4, NAVY), "foot")
        raise AssertionError("アイコンにテーマの色を通した")
    except SystemExit:
        pass
    # テーマの名前はマスターかレイアウトの代替テキストから読む。名前がなければ None
    mark = lambda d: {"masters": [{"pageElements": [{"description": d, **ph("SLIDE_NUMBER", FONT)}]}]}
    assert deck_theme(mark("ai-deck-factory theme=plain")) == "plain" and deck_theme({"layouts": [mark("ai-deck-factory theme=a-1")["masters"][0]]}) == "a-1"
    assert deck_theme(mark("")) is None and deck_theme({"masters": [{}]}) is None and theme_table(None) == {}
    use_theme({"TEXT": "#37352f", "DECOR": "3E5159", "copyright": "© 2026 Me. All rights reserved."})  # テーマの値で組む（既定と同じ値は置き換えない）
    assert _SWAP == {TEXT: "37352F"} and paint(TEXT) == paint("303f47") == {"rgbColor": rgb("37352F")} and paint(RULE) == {"rgbColor": rgb(RULE)} and paint(NAVY) == {"themeColor": NAVY}
    t = make_deck(lambda d: d.text(d.page("t"), 0, 0, 1, 1, "本文"), "foot")
    assert sum(r.get("insertText", {}).get("text") == "© 2026 Me. All rights reserved." for r in t.reqs) == 1
    assert {"opaqueColor": {"rgbColor": rgb("37352F")}} in [r["updateTextStyle"]["style"].get("foregroundColor") for r in t.reqs if "updateTextStyle" in r]
    use_theme({"mono": "IBM Plex Mono"})  # テーマの等幅の書体で組む（字の幅の見込みは MONO_EM のまま）
    assert {r["updateTextStyle"]["style"]["fontFamily"] for r in mono_reqs("e", "a あ b")} == {"IBM Plex Mono"}
    for empty in ({}, theme_table("ない")):  # 値がないテーマと、factory.toml にないテーマは、今の値に戻す
        use_theme(empty)
        assert not _SWAP and COPYRIGHT == BRAND_COPYRIGHT and theme_fixed(empty) == FIXED and paint(TEXT) == {"rgbColor": rgb("303F47")} and MONO == MONO_DEFAULT
    for bad in ("Fira Code", " "):  # リガチャの出る書体と、名前でないもの
        try:
            theme_mono({"mono": bad})
            raise AssertionError(f"mono {bad!r} を通した")
        except SystemExit:
            pass
    try:
        theme_fixed({"RULE": "灰色"})
        raise AssertionError("6 桁でない色を通した")
    except SystemExit:
        pass
    print("selftest ok")


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        return selftest()
    if a == ["themes"]:
        return cmd_themes()
    if not (a[:1] == ["build"] and len(a) >= 2 or a[:1] == ["new"] and len(a) >= 3):
        sys.exit(__doc__)
    theme = a[a.index("--theme") + 1] if "--theme" in a else None
    if a[0] == "new":
        need_theme(theme)
    src = template_id(theme) if a[0] == "new" else file_id(a[1])
    use_theme(theme_table(theme_of(src)))  # テーマはデッキ（new ならテンプレート）から読む。複製は同じ代替テキストを持つ
    need_brand()  # 複製する前に止める（build でも止まるが、作った複製をゴミ箱に移すことになる）
    deck = make_deck(*load_pages())
    if a[0] == "build":
        return build(src, deck, "--force" in a)
    pid = new(a[1], a[2], src)
    try:
        build(pid, deck, force=True)  # 複製したばかりなので、画面での直しもコメントもない
    except BaseException:  # 組めなかった複製を残さない。直してから new をやり直す（同じ名前の空のプレゼンが増えないように）
        trash(pid)
        print(f"組めなかったので、作った複製 {pid} をゴミ箱に移した", file=sys.stderr)
        raise


if __name__ == "__main__":
    run(main)
