#!/usr/bin/env python3
"""Google Slides を Slides API で直接組む（2026-10-07 に pptx から切り替えた。組み方は ../pages.md・../commands.md、落とし穴は ../api.md）。
資料ごとの build/deck.json（kind deck。資料名と、ページのファイルの並び）と、1 ページ 1 つの build/p<番号>.json（kind page）に書く（../pages.md の slides-pages-034。書く形は schema）。
前の資料の build/pages.py（NAME・ページの関数・make(d)。部品は Deck のメソッド）も組める。
usage（資料の build/ で。deck.json か pages.py は今いるフォルダのもの）:
  slides.py new <Drive のフォルダの URL か ID> <Drive 上の名前> [--theme <テーマ>]   テンプレートを複製して組む（テンプレートは factory.toml の [slides.templates] の <テーマ>。
                                          組む前にマスターをテーマのファイルの値にそろえる。build も同じ）
  slides.py plan <URL か ID> [<ファイル>...]   build が書くもの（マスターのテーマの違い・作り直すページ・選んでいないので残すページ・消す枚数・並べ替え・画面での直し）を出す。書かない
  slides.py build <URL か ID> [<ファイル>...] [--force]   組み直す（中身の変わったページだけを作り直し、順をそろえる。URL は変わらない）。JSON のページ・デッキのファイルを渡すと、
                                          そのページだけを作り直し、ほかのページは前のまま残す（テーマはいつもそろえる）。前に組んだあとに画面で直されているか、
                                          未解決のコメントがあれば止まる。直しをページの JSON（前の資料は pages.py）に入れてから --force で組み直す（--force は全ページ〔ファイルを渡せばそのページ〕を作り直す）。
                                          作り直したページを /tmp/slides_<ID の頭 8 字>/changed.json に、工程ごとの秒を標準エラーに出す
  slides.py lint [<ファイル>] [<URL か ID>] [--pages 3,5 | --all] [--talk]   組まずに、組む要求を手元で presentations.get の形にして lint をかける（テストの unit。
                                          直すたびに回す）。既定は前に回したときから変わったページ（と要修正が残ったページ。テーマか規則が変わったら全ページ）。テーマはテーマのファイルから読み、Google を読まない
                                          （URL はテーマのファイルがないデッキだけに要る）。テーマのファイル（kind theme）を渡すと、形と役割の組のコントラストを見る
  slides.py dry [<ファイル>] [<URL か ID>]   組まずに make を走らせ、組むときの警告・枚数・ノートのないページを出す（既定は deck.json か pages.py。子が書いた JSON のページの .json か build/pages_<担当>.py を確かめる。
                                          テーマは lint と同じ。../pages.md）
  slides.py resolve [<ファイル>.json] [<URL か ID>]   JSON のページを解いた形（in の位置とすべての値。Deck のメソッドの呼び出し）を出す（../pages.md の slides-pages-034）
  slides.py schema [--brief]   JSON のページの書く形の JSON Schema を出す（--brief は型・キー・色の早見表）
  slides.py stats   JSON のページの形の外の書き方（raw）を、キーごとに使った資料の数で出す（ワークスペースの .factory/spec_raw.jsonl。形に足す候補）
  slides.py upgrade <ファイル>...   JSON のページの raw のうち、形のキーで書けるものを書き換える
  slides.py themes   テーマの名前・説明・テンプレートがあるか・既定か。資料ごとに選ぶ（../../deck-practices/start.md の 5）。
                     [drive] shared_themes と [drive] factory の下の Themes の、[slides.templates] にないテンプレートも候補に出す
  slides.py theme <URL か ID> [<名前>] [--force]   テンプレートかデッキが持つテーマ（マスターの配色・書体・目印）を、ワークスペースの themes/slides/<名前>.json に書く。
                     テンプレートなら [slides.templates] にも書く（共有テーマを使い始めるとき、画面で直した色を戻すとき）
  slides.py merge <ファイル>...   pages.py の資料で、子が別のファイルに書いたページの関数を pages.py に合わせる（組まない。../../deck-review/SKILL.md の手順 5）
  slides.py --selftest
テンプレートの管理は template.py。色は下の「色の役割」の名前で渡す。役割の名前はテーマの色（マスターの配色）を指すので、テンプレートを替えると色が変わる。
見た目の決まりは ../visual.md の 1。"""
import ast, atexit, contextlib, functools, hashlib, importlib, inspect, io, itertools, json, math, os, re, shutil, subprocess, sys, tempfile, time, tomllib, types, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True  # build/ と scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deck-practices", "scripts"))  # ドキュメントと共有する部品（gapi・brand・textlint）
import brand, gapi
from gapi import (DRIVE, GSLIDES, PPTX, SLIDES, batch, carry, delete, factory, factory_path, file_id, folder_id, png, request, run, slide_ids, thumbnail,
                  trash, u16, upload)
from brand import (ASCII_BOLD_EM, ASCII_EM, BRAND_COPYRIGHT, COMPANY, COPYRIGHT_PT, DM_SANS_BOLD_EM, DM_SANS_EM, FONT, FONT_EM, JP_FONTS, LIGATURE_MONO, LOGO,
                   MONO_DEFAULT, PLACEHOLDER_COPYRIGHT, RULE, TEXT, WHITE, asset, theme_font, theme_mono)  # 書体・字幅・色の既定・著作権表示はドキュメントと同じ

# ---- テンプレート。ID・置き場所・既定のテーマは人ごとに違うので、Documents の直下の factory.toml の [slides] に置く（作り方は template.py） ----
BLANK = "Content E - Blank"  # テンプレートに残した、置き物のないレイアウト。ページ番号の枠だけを持つ

# ---- 版面（visual.md の 1。上端は in） ----
MONO = MONO_DEFAULT  # 組むデッキの等幅の書体。テーマの mono があればそれ（use_theme）
MONO_EM = 0.586  # Cascadia Mono の英数字の幅（em。hmtx で測った。2026-10-09）。テーマで等幅の書体を替えても、この幅で見込む（ずれる。slides-template の「Fonts」）
EMU = 914400
INSET = 0.1  # 文字の枠の内側の余白（API で変えられない）。枠をこの分だけ外に出し、文字の端を箱の端にそろえる
PAD = 0.08   # 箱と、その上に重ねる文字の枠の間（INSET と合わせて、枠と文字の間が 1 字分ほどになる）
CORNER_RADIUS = 0.1  # in。元の AI Deck Factory の pptx と同じ、辺の長さによらない丸み
X, W = 0.6, 12.13  # 本文の左端と幅（左右の余白 0.6 in）
Y_KICK, Y_TITLE, Y_LEAD = 0.40, 0.62, 1.20
Y_BODY, Y_BODY_NOLEAD = 1.78, 1.62  # 本文の上端（リードがあるとき、ないとき）
BAND_BOTTOM, Y_SRC, Y_FOOT = 6.60, 6.68, 7.08  # 結論バンドの下端、出典の行、フッター


COPYRIGHT = BRAND_COPYRIGHT  # 組むデッキの著作権表示。テーマの copyright があればそれ（use_theme）
# 結論バンドの内側の余白（in）。枠と文字の間は 1 字分より大きめに取る（見た目 1-8。13pt の 1 字は 0.18 in）。左右は pptx 版と同じ 18pt
BAND_PAD_X, BAND_PAD_Y = 0.25, 0.2
# [slides-component-001] 正円の番号の直径（in）と数字（pt）。medium・large は数字の高さが円の 4 割ほど。small は周りの 11pt の文字に合わせて 11pt（11pt の太字なので、赤に白の 3.62:1 で届く。visual.md の 3 の slides-visual-039）
NUM = {"small": (0.3, 11), "medium": (0.36, 14), "large": (0.48, 18)}  # 図の中の印／カードと手順（既定）／大きな段
NUM_SHAPES = ("ellipse", "round_rectangle")  # 番号の形。角丸は高さを円の直径にし、幅を数字に合わせる（num_w）
# [slides-component-002] 赤（RED）の線の太さ（pt）。強調の囲みは実線でも点線でも 2pt（強調のための線なので、細くしない）。ほかの枠線は 0.75pt
EMPH_PT = 2

# ---- 色の役割（visual.md の 1）。テーマの色の枠の名前 ----
NAVY, BG, RED_ON_NAVY, PANEL = "DARK1", "LIGHT1", "DARK2", "LIGHT2"  # 表紙・扉の地、結論バンド、表の見出しの行、コードの箱／本文の地／濃紺の上の赤／パネル
NAVY_BLOCK, GA, RED_TEXT, PREVIEW = "ACCENT1", "ACCENT2", "ACCENT3", "ACCENT4"  # 扉の中のブロック／GA の札／18pt 未満の赤の文字／Beta・Preview の札
SUB, OSS, RED = "ACCENT5", "ACCENT6", "HYPERLINK"  # 補助の文字とフッター／OSS の札／赤のアクセント（塗りと 18pt 以上の文字）
# テーマに入れない色。WHITE はどのテーマでも同じ
RED_SOFT, STAGE_TEXT, DECOR = "FFECE8", "0B2026", "6B8089"  # 淡い赤／札の文字／章番号（飾り。濃紺の上で 3.28:1）。WHITE・TEXT（本文）・RULE（罫線と濃紺の上の補足）は brand.py
# TEXT・RULE と上の 3 色は既定の値。テーマのファイルの colors に同じ名前で書くと、そのテーマのデッキでは paint とアイコンが置き換える（use_theme）。
# pages.py には名前（か既定の 6 桁）で書く。マスターの配色に枠が残っていない（12 の枠をすべて使う）ので、組むときに置き換える
FIXED = {"TEXT": TEXT, "RULE": RULE, "RED_SOFT": RED_SOFT, "STAGE_TEXT": STAGE_TEXT, "DECOR": DECOR}
# 名前で引く役割（名前 → 書かないときの色）。既定は今の色（役割の枠か、上の色）と同じで、暗い本文のテーマ（../../slides-template/SKILL.md）が分けて書く。
# 既定の値を WHITE や NAVY と共有するので、FIXED のように値では置き換えない。pages.py には名前で書く
NAMED = {"HEAD": NAVY, "CARD": WHITE, "SUB_ON_NAVY": RULE, "ON_RED": WHITE}
HEAD, CARD, SUB_ON_NAVY, ON_RED = NAMED  # 本文のページの見出しの文字／カードと表のセルの地／濃紺の上の補足の文字とフッター／RED の塗りの上の文字
# テーマの目印。マスターのページ番号の枠の代替テキストに、名前と、マスターの配色・書体・レイアウトの目印に入らない値（theme_extras の JSON）を書く。
# Drive の複製でも残る（2026-10-13）ので、デッキはテーマの値をすべて持ち、theme_from で theme.json に戻せる
THEME_MARK = re.compile(r"ai-deck-factory theme=([A-Za-z0-9_-]+)(?: (\{.*\}))?", re.S)
THEME_PROP = "adf.theme"  # template.py がテンプレートの Drive のプロパティ（公開。どの OAuth クライアントでも読める）に書くテーマの名前。共有テーマのフォルダでテンプレートを見分ける
THEMES_DIR = "Themes"  # template.py --from-base がテンプレートを作る Drive のフォルダ。[drive] factory の下（なければ作る）。使うテンプレートは [slides.templates] で 1 つずつ指す
# テーマのファイル（kind theme）。組み込みは slides-build/themes/<名前>.json、ワークスペースは themes/slides/<名前>.json（同じ名前ならワークスペースが勝つ）。
# ドキュメントのテーマも、あとで themes/docs/<名前>.json に同じ形で置く
BUILTIN_THEMES = Path(__file__).resolve().parent.parent / "themes"
WS_THEMES = ("themes", "slides")
THEME_KEYS = ("description", "font", "mono", "copyright", "colors", "cover", "section")
READ_ERRORS = (gapi.ApiError, OSError)  # Drive を読めない（権限・URL・認証・回線）。request は HTTP のエラーだけを ApiError にし、取り直しても通らない回線のエラー（URLError・ConnectionError・TimeoutError。どれも OSError）はそのまま上げる
# 会社のテンプレートから残した表紙・扉のレイアウト（図形・ロゴ・写真付き。パターンごとに番号）。template.py がそのレイアウトのページ番号の枠の
# 代替テキストに書く。w は元のタイトルの枠の右端までの文字の幅（in）、tone は地の明るさ（文字の色を決める）。なければ表紙・扉も Blank に組む
# （2026-10-13、ユーザー「元の図形が入ったタイトルスライドなどを、維持して欲しい」「セクション区切りで異なる背景の区切りページを使い分けることはよくします」）
BAR_MARK = "ai-deck-factory bar"  # 棒グラフの棒の代替テキストの title（description は名前と数）。lint が、棒の中の数字の下を「箱の中の下の空き」に数えない
LAYOUT_MARK = re.compile(r"ai-deck-factory layout=(cover|section):(\d+)(?: w=([\d.]+))?(?: tone=(dark|accent|light))?")
VARIANTS = {}  # 組んでいるデッキの {"cover"・"section": {番号: (文字の幅 in か None, tone)}}（目印の番号で引く。build の @COVER<番号> と同じ。use_layouts が決める）
# 表紙・扉の地の明るさごとの文字の色（タイトル、小見出し・副題、章番号、社名とフッター）。dark は濃紺の地（Blank に組むときも）、accent は
# 白が大きな文字にだけ届く赤の地（小さな文字は NAVY）、light は白の地
# 章番号は、どの地でも 3:1 に届く色（slides-visual-038。赤の地は濃紺、白の地は DECOR）
TONES = {"dark": (WHITE, RED_ON_NAVY, DECOR, SUB_ON_NAVY), "accent": (WHITE, NAVY, NAVY, NAVY), "light": (HEAD, RED_TEXT, DECOR, SUB)}
_SWAP = {}  # 組んでいるデッキの、FIXED の既定の値 → テーマの値（use_theme が決める）
_NAMED = {}  # 組んでいるデッキの、テーマが書いた NAMED の値（use_theme が決める）
# 提供ステージの札の塗り（visual.md の 1）。本番で使える Public Preview は、Beta・Private Preview（本番向けではない）の黄と分け、GA の緑を 4 割にした色（2026-10-09）
PUBLIC_PREVIEW = "99DDC7"
STAGE_FILL = {"GA": GA, "Public Preview": PUBLIC_PREVIEW, "Beta": PREVIEW, "Private Preview": PREVIEW, "OSS": OSS}  # 札の文字は OSS だけ WHITE、ほかは STAGE_TEXT
SLOTS = ("DARK1", "LIGHT1", "DARK2", "LIGHT2", "ACCENT1", "ACCENT2", "ACCENT3", "ACCENT4", "ACCENT5", "ACCENT6", "HYPERLINK", "FOLLOWED_HYPERLINK")
# テーマのファイルに書く役割の名前 → テーマの枠（visual.md の 1）。FOLLOWED_HYPERLINK は役割がなく、どのテーマも同じ色
ROLE = {"NAVY": NAVY, "BG": BG, "RED_ON_NAVY": RED_ON_NAVY, "PANEL": PANEL, "NAVY_BLOCK": NAVY_BLOCK, "GA": GA, "RED_TEXT": RED_TEXT, "PREVIEW": PREVIEW,
        "SUB": SUB, "OSS": OSS, "RED": RED}
FOLLOWED = "954F72"
# 組み込みの visual の 12 の枠。テーマが書かない役割はこの色（テーマのファイルの色は役割の名前で書く）。visual は 2025 年版の公式パレットから
# コントラストを確かめて選んだ色。company は 2026 年の公式テンプレートの色で、本文の地は白、小さな赤の文字（Lava 600、白の上で 3.62:1）と
# SUB（618794、白の上で 3.89:1）は色相を保って暗くした（2026-10-13）
VISUAL = {**{s: json.loads((BUILTIN_THEMES / "visual.json").read_text())["colors"][r] for r, s in ROLE.items()}, "FOLLOWED_HYPERLINK": FOLLOWED}


TEXT_EM, TEXT_BOLD_EM = FONT_EM[FONT]  # 組む・見るデッキの書体の英数字の幅（use_font。ponytail: 1 つずつ組む前提の大域の値）


def use_font(f):
    """字幅の見積もり（em_width）を、本文の書体 f の幅にする。組む側（theme_of、テンプレートの見本は template.py）と見る側（lint_slides）が呼ぶ。"""
    global TEXT_EM, TEXT_BOLD_EM
    TEXT_EM, TEXT_BOLD_EM = FONT_EM.get(f, FONT_EM[FONT])


def em_width(s, mono=False, bold=False):
    """文字の幅の見積もり（em）。全角と、矢印・丸数字・× などの記号（U+2100 から上と ×÷±…※†‡）は 1、英数字と記号は TEXT_EM（bold なら TEXT_BOLD_EM、mono なら MONO_EM）、ほかは 0.57。"""
    em = TEXT_BOLD_EM if bold else TEXT_EM
    return sum(1.0 if ord(c) >= 0x2100 or c in "×÷±…※†‡" else MONO_EM if mono and c in em else em.get(c, 0.57) for c in s)


def num_w(n, size="medium", shape="ellipse"):
    """番号の見える幅（in）。円は直径。角丸は、直径と、太字の数字の幅に直径の半分（左右に 1/4 ずつ）を足した幅の広いほう（1 字なら正方形）。"""
    dia, pt_ = NUM[size]
    return dia if shape == "ellipse" else max(dia, em_width(str(n), bold=True) * pt_ / 72 + dia / 2)


def all_bold(parts, bold=False):
    """parts（文字列か (文字列, 書式) の並び）の見える文字がすべて太字か。bold は書式に太さのない文字の太さ（Deck.text の bold）。
    1 つの文字列で行数を見るところ（行間の 125・100、最終行の字数）が使う。ponytail: 太さの交ざる文字は Regular の幅で見る（段落ごとに見る spec_text_h の行数とは別）"""
    vis = [bold if isinstance(p, str) else p[1].get("bold", bold) for p in ([parts] if isinstance(parts, str) else parts) if (p if isinstance(p, str) else p[0]).strip()]
    return all(vis) if vis else bold


def wrap_lines(s, avail, size, mono=False, bold=False):
    """1 段落を幅 avail（in）で折り返したときの (行数, 最終行の幅 em) の見込み。和文は 1 字ずつ、英数字の語はまとめて次の行へ送る。
    ponytail: 行頭の句読点を前の行に戻す禁則は見ない"""
    n, cur, cap = 1, 0.0, max(avail, 0.05) * 72 / size
    for word in re.findall(r"[!-~]+| +|.", s):
        for t in (word if em_width(word, mono, bold) > cap else [word]):  # 1 行より長い語（長い識別子・URL）は、字で折る
            tw = em_width(t, mono, bold)
            if cur + tw > cap + 1e-9 and cur > 0:
                n, cur = n + 1, (0.0 if t.isspace() else tw)
            else:
                cur += tw
    return n, cur


def run_lines(runs, avail, mono=False):
    """runs（(文字, pt, 太字) の並び）の 1 段落を幅 avail（in）で折り返した行数の見込み。wrap_lines と同じ送り方（英数字の語はまとめて次の行へ、
    1 行より長い語は字で折る）を、文字ごとの大きさと太さで見る（lint の wrap_breaks と同じ）。\n で改行する。"""
    t = "".join(c for c, *_ in runs)
    ws = [em_width(ch, mono, b) * sz / 72 for c, sz, b in runs for ch in c]
    n, cur = 1, 0.0
    for m in re.finditer(r"[!-~]+| +|\n|.", t):
        if m.group() == "\n":
            n, cur = n + 1, 0.0
            continue
        a, z = m.span()
        for k, e in ([(k, k + 1) for k in range(a, z)] if sum(ws[a:z]) > avail + 1e-9 else [(a, z)]):
            w = sum(ws[k:e])
            if cur + w > avail + 1e-9 and cur > 0:
                n, cur = n + 1, (0.0 if t[k].isspace() else w)
            else:
                cur += w
    return n


def est_lines(s, avail, size, mono=False, bold=False):
    """幅 avail（in。文字の枠の内側）に size pt で置いたときの行数の見込み。\n と \v で改行する。英数字の語は行をまたがない
    （1 字ずつ詰めて数えると、英語の多いカードで 1 行少なく見込み、h を省いたカードから文字がはみ出した。2026-10-13）。"""
    return sum(wrap_lines(p, avail, size, mono, bold)[0] for p in re.split(r"[\n\v]", s))


def mono_reqs(oid, s, cell=None):
    """s の中の ASCII の続き（行頭の字下げの空白も含める）を MONO にする updateTextStyle。和文は FONT のまま（MONO に和文の字形がない。lint が見る）。"""
    loc = {"cellLocation": cell} if cell else {}
    return [{"updateTextStyle": {"objectId": oid, **loc, "textRange": {"type": "FIXED_RANGE", "startIndex": u16(s[:m.start()]), "endIndex": u16(s[:m.end()])},
                                 "style": {"fontFamily": MONO}, "fields": "fontFamily"}} for m in re.finditer(r"[ -~]+", s)]


CARD_DOWN, CARD_END = 0.09, 0.13  # d.card の中身を箱の上から下げる分、本文の枠の下の空き（in）。最終行の下には行間の空きがあるので、上の空きを下（box_pad の 0.28 in）と
# 同じ見た目にする（2026-10-20 の画像で、前は上 0.2 in・下 0.32 in、これで上下とも 0.3 in ほど）


def card_top(w, head):
    """d.card の本文の枠の上端（箱の上端から、in）。見出し（太字 12pt）が折り返す見込みなら、1 行（0.2 in）ごとに下げる（決め打ちの 0.5 in では、2 行の見出しが本文に重なった）。"""
    return CARD_DOWN + (0.5 + (est_lines(head, w - 2 * PAD - 2 * INSET, 12, bold=True) - 1) * 0.2 if head else 0.1)


def card_items(items):
    """d.card の items（(見出し, 説明) の並び）を 1 つの文字の枠に流す parts。見出しは太字、項目の間に空行。"""
    parts = []
    for i, (h2, b) in enumerate(items):
        parts += [(h2 + "\n", {"bold": True}), b + ("\n\n" if i < len(items) - 1 else "")]
    return parts


def card_h(w, head=None, body=None, items=None, step=None, bullets=False, size=11, least=False):
    """[slides-component-012] d.card の高さの見込み（in）。d.card の h を省くと、これで中身から決める。隣の列やページの下端に合わせて伸ばすと、
    中身より大きい箱になる（代表の 3 枚の記録で、ほぼすべてのデッキに出た）。列の高さをそろえるなら、並ぶカードの card_h の最大を渡す。
    least なら、文字が枠に収まる最小（JSON のページの h の警告。#52）。最終行と下端の間は、本文の枠の下の 0.1 in だけを残し、step は最後の項目の後ろの空きを除く。
    文字は d.card が置く parts のまま spec_text_h で数える（項目の見出しの太字、run ごとの大きさ）。"""
    top = card_top(w, head)
    avail = w - 2 * PAD - 2 * INSET - (size * 1.3 / 72 if bullets else 0)
    if step is not None:  # 最後の項目の文字が step の間隔より高ければ、その分を足す（下端との間を下の CARD_END と同じだけ空ける）
        n = len(items or [])
        last = spec_text_h(card_items(items[-1:]), avail, size, 125) + 2 * INSET + (0 if least else CARD_END) if n else 0.1
        return top + ((n - 1) * step + last if least and n else max(n * step + 0.1, (n - 1) * step + last))
    parts = card_items(items) if items else [body] if isinstance(body, str) else body or []
    return top + (spec_text_h(parts, avail, size, 125) + 2 * INSET if any(p if isinstance(p, str) else p[0] for p in parts) else 0) + (0.1 if least else CARD_END)  # 本文の枠は下端の 0.1 in 上まで（d.card）


def table_grid(rows, n, pad=False):
    """d.table の行を、置く位置ごとのセルにする。セルは文字列、parts の並び、dict（text・colspan・rowspan・fill・align・valign・color・bullets）。
    結合したセルが覆う位置には、セルを書かない（HTML の colspan・rowspan と同じ）。戻り: (行, 列, dict) の並び（行の順、行の中は書いた順）。
    セルが n 列に合わない・表の下を越える・重なるなら ValueError。pad なら、足りない位置は空のセルにする（前の d.table と同じ。pages.py の短い行）。"""
    taken, out = set(), []
    for r, row in enumerate(rows):
        c = 0
        for cell in row:
            while (r, c) in taken:
                c += 1
            d = dict(cell) if isinstance(cell, dict) else {"text": cell}
            rs, cs = d.get("rowspan", 1), d.get("colspan", 1)
            if c + cs > n:
                raise ValueError(f"{r + 1} 行目のセルが列の数（{n}）を越える（上の行の rowspan と colspan が覆う位置には、セルを書かない）")
            if r + rs > len(rows):
                raise ValueError(f"{r + 1} 行目 {c + 1} 列目の rowspan {rs} が表の下を越える（{len(rows)} 行）")
            cover = {(r + i, c + j) for i in range(rs) for j in range(cs)}
            if cover & taken:
                raise ValueError(f"{r + 1} 行目 {c + 1} 列目のセルが、上の行の rowspan のセルと重なる")
            taken |= cover
            out.append((r, c, d))
            c += cs
        if pad:
            for j in [j for j in range(n) if (r, j) not in taken]:
                taken.add((r, j))
                out.append((r, j, {"text": ""}))
        if (have := sum((r, j) in taken for j in range(n))) < n:
            raise ValueError(f"{r + 1} 行目のセルが {have} 列分しかない（列は {n}。colspan は覆う列の数だけ数える）")
    return out


def cell_parts(d):
    """table_grid のセルの文字を parts の並びにする。"""
    t = d.get("text", "")
    return [t] if isinstance(t, str) else t


def table_h(widths, rows, size=11, row_h=0.36, header=True, mono_cols=(), first_col=True):
    """d.table の高さの見込み（in）。行は文字に合わせて伸びる（row_h は最小。行ごとの並びでもよい）。見出しの行（header は行の数か真偽）と 1 列目（first_col）は太字で見込む。
    rowspan のセルは、覆う行の高さの合計に足りない分を、覆う最後の行に足す（ponytail: Google の配り方は測っていない）。"""
    hs, nh = list(row_h) if isinstance(row_h, (list, tuple)) else [row_h] * len(rows), int(header)
    for r, c, d in sorted(table_grid(rows, len(widths), pad=True), key=lambda t: t[2].get("rowspan", 1)):  # 1 行のセルで行の高さを決めてから、rowspan のセルを見る
        head, cs, rs = r < nh, d.get("colspan", 1), d.get("rowspan", 1)
        avail = sum(widths[c:c + cs]) - 2 * INSET - (size * 1.3 / 72 if d.get("bullets") else 0)
        h = 0.16 + spec_text_h(cell_parts(d), avail, size, 120, mono=c in mono_cols and not head, bold=head or first_col and c == 0)
        hs[r + rs - 1] += max(h - sum(hs[r:r + rs]), 0)
    return sum(hs)


def band_h(head, sub=None):
    """結論バンドの高さの見込み（in。Deck.band が h を省いたとき。JSON のページは本文の下端の限りにも使う）。"""
    avail = W - 2 * BAND_PAD_X
    return 2 * BAND_PAD_Y + est_lines(head, avail, 13, bold=True) * 0.25 + (est_lines(sub, avail, 11) * 0.21 if sub else 0)


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


@functools.lru_cache(maxsize=None)
def iconify(name, color=TEXT, w=512):
    """Iconify のアイコン（"tabler:database"、"logos:aws"）の PNG の URL。color（6 桁）は 1 色のセットにだけ効く。名前がなければ止める。
    [slides-component-004] 同じアイコンは 1 回だけ確かめる（20 枚で 60 回ほど問い合わせると 429 が返った）。"""
    svg = "https://api.iconify.design/" + name.replace(":", "/", 1) + ".svg"
    if name in icons_ok():
        return png(f"{svg}?color=%23{color}", w)
    try:  # 名前の間違いは、組むときに Slides API の「画像を取れない」としか出ないので、先に確かめる。既定の User-Agent は 403 になる
        urllib.request.urlopen(urllib.request.Request(svg, method="HEAD", headers={"User-Agent": "slides.py"}), timeout=15)
        icons_ok().add(name)  # 同じ名前を別の色で使っても、もう問い合わせない
        try:
            with open(ICONS_OK, "a") as f:
                f.write(name + "\n")
        except OSError:  # 書けなければ、次の回も問い合わせるだけ
            pass
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit(f"アイコンがない: {name}。名前は https://icon-sets.iconify.design/ で探す")
        print(f"警告: アイコンの名前を確かめられなかった: {name}（{e.code}）。組むときに Slides API が取れなければ止まる", file=sys.stderr)
    return png(f"{svg}?color=%23{color}", w)


ICONS_OK = Path(tempfile.gettempdir()) / f"slides_iconify_ok_{gapi.user()}"  # あると確かめたアイコンの名前。組み直すたび・lint のたびに問い合わせない（53 枚で 35 個、2.5 秒かかった）。人ごと（Linux の /tmp は人で共有する）


@functools.cache
def icons_ok():
    try:
        return set(ICONS_OK.read_text().split())
    except OSError:
        return set()


def rgb(h):
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def fixed(c):
    """FIXED の既定の値なら、デッキのテーマの値（6 桁で書いた同じ値も置き換わる。refont と同じ）。ほかはそのまま。"""
    return _SWAP.get(c.upper(), c) if isinstance(c, str) else c


PALETTE = dict(VISUAL)  # 組むデッキの配色（テーマの色の枠 → 6 桁。use_palette がマスターから読む）。アイコンの色を役割の名前で書くため


def scheme(p):
    """デッキ p のマスターの配色（枠 → 6 桁）。API は色を RgbColor のまま返し、0 の成分は省く（前は rgbColor の下を読んでいて、どのテーマも visual の色になっていた）。"""
    return {c["type"]: "".join(f"{round(c['color'].get(k, 0) * 255):02X}" for k in ("red", "green", "blue"))
            for c in (p.get("masters") or [{}])[0].get("pageProperties", {}).get("colorScheme", {}).get("colors", []) if "color" in c}


def use_palette(p):
    """デッキ p のマスターの配色を PALETTE にする（use_pages）。マスターが書いていない枠は既定の配色（前のデッキの色を残さない）。"""
    PALETTE.clear()
    PALETTE.update(VISUAL | scheme(p))


def hex_of(c):
    """役割の名前か 6 桁の色を、組むデッキの 6 桁にする（paint と同じ引き方）。"""
    c = _NAMED[c] if c in _NAMED else fixed(NAMED.get(c, c))
    return PALETTE.get(c, c)


def paint(c):  # 役割の名前ならテーマの色、6 桁ならその色（固定の色はテーマの値）。NAMED はテーマが書いた値、書いていなければ既定の色
    c = _NAMED[c] if c in _NAMED else fixed(NAMED.get(c, c))
    return {"themeColor": c} if c in SLOTS else {"rgbColor": rgb(c)}


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


_RUN = [0]


def new_run():
    """Deck の ID の頭。ミリ秒の時刻で、同じプロセスの中でも繰り返さない。build は前に組んだページを残すので、その ID とぶつけない
    （前の秒の下 5 けたは 27.8 時間ごとに同じ値になり、残したページの ID と同じ ID を作ると batchUpdate が止まる）。"""
    _RUN[0] = max(time.time_ns() // 1_000_000, _RUN[0] + 1)
    return f"r{_RUN[0]}"


class Deck:
    """ページを組む要求（batchUpdate）を貯める。Google の API は build まで呼ばない。"""

    def __init__(self, name):
        self.name, self.reqs, self.notes, self.slides, self.images, self.n = name, [], {}, [], [], 0
        self.dark = set()   # 濃紺の地のページ（表紙・扉。フッターとページ番号を SUB_ON_NAVY にする）。本文の地が暗いテーマでも、本文のページは入らない
        self.footc = {}     # 表紙・扉のパターンのページの、フッターとページ番号の色（地の明るさごと。TONES）
        self.links = []     # ページへのリンク（要求, ページ番号）。すべてのページを作ってから付ける
        self.nofoot = set()  # フッターとページ番号を置かないページ（全面に画像を貼るページなど）
        self.round_groups = []  # 角丸・正円の背景と文字の枠を、文字を書き終わってから 1 つにまとめる
        self.warnings = []   # 組むときの見込みの警告（折り返し、見出しを縮めた、など）
        self.run = new_run()  # 組み直すときに、前の ID（残したページのものも）とぶつけない
        self.page_names = {}  # JSON のページのファイル名（拡張子なし）→ ページの ID。[名前](#p12) のリンク先
        self.resolved, self.spec_index, self.spec_esc = [], {}, []  # JSON のページ（spec）の解いた形、ページごとの (部品の場所, 文字)（lint の指摘に場所を付ける）、
        # 形の外の書き方（ページ, 場所, キー）
        self.anchor = None  # 直前の card・code の箱の文字の枠（矢印をつなぐ先。JSON のページの id）

    def oid(self):
        self.n += 1
        return f"{self.run}_{self.n:04d}"

    def warn(self, msg):
        msg = f"[p{len(self.slides)}] {msg}"
        self.warnings.append(msg)
        print("警告:", msg, file=sys.stderr)

    # ---- ページ ----
    def slide(self, bg=BG, foot=True, layout="@LAYOUT"):
        """ページ番号はテンプレートの枠（自動で振られる。表紙では消す）。foot=False のページには、フッターもページ番号も置かない。
        layout は @LAYOUT（Blank）か、表紙・扉の @COVER・@SECTION（テンプレートになければ Blank。build が置き換える）。"""
        sid = self.oid()
        self.slides.append(sid)
        if bg == NAVY:
            self.dark.add(sid)
        if not foot:
            self.nofoot.add(sid)
        self.reqs.append({"createSlide": {"objectId": sid, "slideLayoutReference": {"layoutId": layout},
                                          "placeholderIdMappings": [{"layoutPlaceholder": {"type": "SLIDE_NUMBER"}, "objectId": sid + "_n"}]}})
        if bg:  # None は表紙・扉のパターン（レイアウトの地と絵を見せる）
            self.reqs.append({"updatePageProperties": {"objectId": sid, "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": paint(bg)}}},
                                                       "fields": "pageBackgroundFill"}})
        return sid

    def variant(self, kind, n):
        """表紙・扉のパターン n（1 から）のページを作る。戻り: (ページ, 文字の幅, 文字の色 TONES)。テンプレートにパターンがなければ、1 は Blank に濃紺の地。"""
        vs = VARIANTS.get(kind, {})
        if n not in (vs or {1: None}):
            raise ValueError(f"{'表紙' if kind == 'cover' else '扉'}のパターン {n} がない（テンプレートにあるのは {', '.join(f'{i}（地: {vs[i][1]}）' for i in sorted(vs)) or '1'}。見本のページで番号を見る）")
        if not vs:
            return self.slide(NAVY), W + 2 * INSET, TONES["dark"]
        w, tone = vs[n]
        s = self.slide(None, layout=f"@{kind.upper()}{n}")
        self.footc[s] = TONES[tone][3]
        if tone == "dark":
            self.dark.add(s)
        return s, w or W + 2 * INSET, TONES[tone]

    def note(self, sid, text):
        self.notes[sid] = text

    def spec(self, src):
        """JSON で書いたページ（ファイルのパス、dict、その並び、deck.json、部品 1 つ）を解いて組み、ページの ID の並びを返す。
        書き方は ../pages.md の slides-pages-034。解いた形は self.resolved に残る（slides.py resolve）。"""
        return [spec_page(self, p, base, loc, name) for p, base, loc, name in spec_files(src)]

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

    def box(self, sid, x, y, w, h, fill=None, line=None, kind=None, radius=CORNER_RADIUS, inner=0, dash=False, weight=None, alt=None, title=None):
        """塗りの箱は半径 0.1 in の角丸が既定。輪郭だけの枠は四角。kind='RECTANGLE' で四角を明示できる。
        ROUND_RECTANGLE は四角と円の合成で半径を固定する。radius=None だけが Google 規定の丸み。
        戻りは文字を入れる透明の枠の ID。finish で背景とまとめ、編集可能な 1 グループにする。
        inner（in）は、文字の枠を左右だけ箱の内に縮める幅（枠の内側の余白 0.1 in に足す。text の pad）。
        dash で枠線を点線にし、weight（pt）で枠線の太さを変える。角丸の点線は、辺の線と角の円弧に点線を付けるので、半径は 0.1 in のまま
        [slides-component-005] （Google 標準の角丸に点線を付けると、半径が短い辺の約 1/6 になって中のカードと曲率が合わない）。
        weight を省くと、赤（RED）の線は EMPH_PT（2pt。強調の囲み）、ほかは 0.75pt。
        alt・title は代替テキストの description・title（1 つの図形で描く箱だけ。棒グラフの棒の BAR_MARK）。"""
        weight = weight or (EMPH_PT if line == RED else 0.75)
        kind = kind or ("ROUND_RECTANGLE" if fill else "RECTANGLE")
        if inner > 0 and (kind != "ROUND_RECTANGLE" or radius is None):  # 1 つの図形では余白を変えられないので、図形と文字の枠を分けて 1 グループにする
            if alt or title:
                raise ValueError("alt・title は 1 つの図形で描く箱（四角か Google 規定の角丸）だけに付けられる")
            bg = self._shape(sid, x, y, w, h, fill, line, kind, dash=dash, weight=weight)
            e = self._shape(sid, x + inner, y, w - 2 * inner, h)
            self.round_groups.append((bg, e, self.oid()))
            return e
        if kind != "ROUND_RECTANGLE" or radius is None:
            e = self._shape(sid, x, y, w, h, fill, line, kind, dash=dash, weight=weight)
            if alt or title:
                self.reqs.append({"updatePageElementAltText": {"objectId": e, "title": title or "", "description": alt or ""}})
            return e
        if alt or title:
            raise ValueError("alt・title は 1 つの図形で描く箱（四角か Google 規定の角丸）だけに付けられる")
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
            # [slides-component-006] 円の輪郭と辺の線をつなぐと、Google の描画で継ぎ目に 1〜2 px の段が出た
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
             dash=False, weight=None, mono=False, wide=False):
        """parts は文字列か、(文字列, {"bold":…, "color":…, "size":…, "link":…}) の並び。改行は \\n（段落を分ける）、\\v は段落の中の改行。
        link は URL か、ページ番号（int。Appendix の出典のページなど）。リンクの文字は周りの色のまま下線を付ける。
        spacing（行間、%）を省くと、2 行以上の見込みなら 125、1 行なら 100（visual.md の 2）。基準（size）の 2 倍以上の文字の段落
        （大きな数字）は、spacing によらず 100 にする（125 だと、Google の行送りでは数字と説明が離れて見えた。2026-10-08）。
        edge=True で、文字の端を (x, y)・幅 w・高さ h にそろえる（塗りのない文字。枠を INSET だけ外に出す。pages.md の「Laying out shapes and text」）。
        pad（in）は、塗りか枠線のある文字の、左寄せ・右寄せのときの箱の端と文字の間。省くと 1 字分（枠でいちばん小さい文字の大きさ。lint と同じ測り方）。
        枠の内側の余白は 0.1 in で変えられず 1 字分に足りないので、文字の枠を内に縮める（visual.md の 4。lint が見る）。中央寄せには効かない。
        gap（pt）は段落の間の空き（最後の段落には付けない。付けると上下の中央が上にずれる）。
        改行を含む part は、その行が枠に収まるかを見て、収まらない見込みなら警告する（fit=False で見ない）。
        mono=True で、英数字を等幅の MONO にする（コードの箱・コマンドだけの札。visual.md の 2）。
        wide=True で、楕円でない図形も、楕円と同じく文字の枠を図形より広げる（角丸の番号。Deck.num）。"""
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
        # [slides-component-007] （0.3 in で右 3.5 pt・上 2 pt。書体を替えても直らない）。
        # 円は塗りだけにし、円と同じ大きさの透明の枠を重ねて、1 グループにする。四角の枠なら、文字の場所が数字より狭くても、はみ出しを上下・左右に
        # 均等に振って中央に置く。ただし 2 字以上は幅が足りないと折り返す（「10」は文字の場所 0.20 in で折り返し、0.22 in で 1 行）。数字の幅の見積もりちょうどでは
        # 書体で折り返す（medium の「10」は 0.218 in。#51）ので、字数によらず、横を円か数字の幅の広いほうに左右 0.05 in ずつ足した幅まで広げる。
        # 番号でない楕円の文字（JSON の shape: ellipse）も同じ枠になり、枠が楕円より 0.1 in 広い
        # 角丸の番号（wide）も、図形の内側の余白で 2 桁が折り返すので同じ枠にする
        ring = (x, y, w, h) if kind == "ELLIPSE" or wide else None
        if ring:
            fw = max(w, em_width(full) * size / 72 + 2 * INSET) + 0.1
            x, w, spacing = x - (fw - w) / 2, fw, spacing or 100  # 行の見込みで 125 にしない（1 行で中央に置く）
        avail = w - 2 * INSET - 2 * inner - (size * 1.3 / 72 if bullets else 0)  # 箇条書きは下の indentStart の分だけ狭い（card_h と同じ）
        if fit:
            over = set()
            for p in parts:
                t, sz, b = (p, size, bold) if isinstance(p, str) else (p[0], p[1].get("size", size), p[1].get("bold", bold))
                for ln in (re.split(r"[\n\v]", t) if re.search(r"[\n\v]", t) else []):
                    if ln and est_lines(ln, avail, sz, mono, b) > 1:
                        over.add(ln)
                        self.warn(f"手で改行した行が枠に収まらない見込み「{ln}」（{em_width(ln, mono, b) * sz / 72:.2f} in > {avail:.2f} in）")
            # [slides-component-013] 自動で折り返す行の、最終行の 1〜2 字（代表の 3 枚の記録で、ほぼすべてのデッキに出た）。ponytail: size の 1 つの大きさで見る
            for ln in re.split(r"[\n\v]", full):
                n, last = wrap_lines(ln, avail, size, mono, all_bold(parts, bold))
                if n > 1 and last <= 2 and ln not in over:
                    self.warn(f"折り返した最終行が 2 字以下の見込み「{ln}」（{n} 行。言い換えか \\v で行を決める）")
        if spacing is None:
            spacing = 125 if est_lines(full.strip("\n"), avail, size, mono, all_bold(parts, bold)) > 1 else 100
        if ring and kind != "ELLIPSE":  # 角丸は box が背景を組む。負の inner で文字の枠を背景より広げる
            e = self.box(sid, *ring, fill, line, kind, radius, -(w - ring[2]) / 2, dash, weight)
        elif ring:
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
        self.runs(e, parts, color)
        if mono:
            self.reqs += mono_reqs(e, full)
        if spacing > 100:
            self.big_paras(e, parts, size)
        if gap and "\n" in full:
            self.reqs.append({"updateParagraphStyle": {"objectId": e, "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": u16(full[:full.rindex("\n")]) + 1},
                                                       "style": {"spaceBelow": pt(gap)}, "fields": "spaceBelow"}})
        if bullets:  # Google は黒丸を、最初の行の字下げより文字の大きさの半分ほど左に描く（11pt で 6 pt、14pt で 7.2 pt。2026-10-08 に測った）。半分だけ字下げして、黒丸の左端を本文の左端にそろえる
            self.reqs += [{"createParagraphBullets": {"objectId": e, "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
                          {"updateParagraphStyle": {"objectId": e, "textRange": {"type": "ALL"}, "style": {"indentStart": pt(size * 1.3), "indentFirstLine": pt(size / 2)},
                                                    "fields": "indentStart,indentFirstLine"}}]
        return e

    def big_paras(self, oid, parts, size, cell=None):
        """基準（size）の 2 倍以上の文字の段落（大きな数字）の行間を 100 にする（spec_text_h の見込みと同じ。d.text の docstring）。"""
        loc, full = {"cellLocation": cell} if cell else {}, spec_plain(parts)
        start, big, i = 0, 0, 0  # 段落ごとに、いちばん大きい文字を見る
        for s, sz in [(p, size) if isinstance(p, str) else (p[0], p[1].get("size", size)) for p in parts] + [("\n", 0)]:
            for k, piece in enumerate(s.split("\n")):
                if k:  # 段落の終わり
                    if big >= 2 * size:
                        self.reqs.append({"updateParagraphStyle": {"objectId": oid, **loc, "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": min(i + 1, u16(full))},
                                                                   "style": {"lineSpacing": 100}, "fields": "lineSpacing"}})
                    i += 1
                    start, big = i, 0
                i += u16(piece)
                big = max(big, sz) if piece else big

    def runs(self, oid, parts, color, cell=None):
        """parts の run の書式（太字・大きさ・色・リンク）を、文字の枠か表のセル（cell は cellLocation）に付ける。ページへのリンクは finish で付ける。"""
        loc, i = {"cellLocation": cell} if cell else {}, 0
        for p in parts:
            s, st = (p, {}) if isinstance(p, str) else p
            if st:
                style, fields = run_style(st, color)
                req = {"updateTextStyle": {"objectId": oid, **loc, "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + u16(s)},
                                           "style": style, "fields": fields}}
                if isinstance(st.get("link"), (int, dict)):  # ページの番号か、JSON のページの名前（{"page": "p12"}）
                    self.links.append((req, st["link"]))
                else:
                    self.reqs.append(req)
            i += u16(s)

    def num(self, sid, n, cx, cy, size="medium", fill=RED, shape="ellipse"):
        """番号。(cx, cy) は図形の中心（大きさを替えても位置が動かず、横に並べる見出しと中心をそろえやすい）。size は NUM の small・medium・large。
        shape は NUM_SHAPES の ellipse（正円）か round_rectangle（高さは円の直径、幅は num_w）。数字は、RED の塗りなら ON_RED、ほかの塗りなら WHITE。"""
        if size not in NUM:
            raise ValueError(f"番号の大きさ {size!r} は書けない（{'・'.join(NUM)}）")
        if shape not in NUM_SHAPES:
            raise ValueError(f"番号の形 {shape!r} は書けない（{'・'.join(NUM_SHAPES)}）")
        dia, pt_ = NUM[size]
        w = num_w(n, size, shape)
        return self.text(sid, cx - w / 2, cy - dia / 2, w, dia, str(n), size=pt_, color=ON_RED if fill == RED else WHITE, bold=True, align="CENTER", valign="MIDDLE",
                         fill=fill, kind=SHAPES[shape], wide=True)

    def label(self, sid, v, x, y, w, h, fill=PANEL, color=HEAD, size=11, bold=True, align="CENTER", radius=CORNER_RADIUS, pad=None, mono=False):
        """塗りの箱と、その中の短い言葉（札・日付・工程の名前）。図形と文字を 1 つにする（pages.md の「Laying out shapes and text」）。
        左寄せ（align="START"）なら、箱の端と文字の間を 1 字分空ける（text の pad）。"""
        return self.text(sid, x, y, w, h, v, size=size, color=color, bold=bold, align=align, valign="MIDDLE", fill=fill, radius=radius, pad=pad, mono=mono)

    def code(self, sid, x, y, w, h, lines, hot=(), size=11):
        """濃紺のコードの箱。lines は 1 行ずつの文字列で、英数字は等幅（MONO）。hot の行（0 始まりの番号）は濃紺の上の赤の太字。
        [slides-component-008] 3 つ目の資料で要ったので pages.py から移した（pages.md）。"""
        self.anchor = self.box(sid, x, y, w, h, NAVY)
        parts = [(ln + ("\n" if i < len(lines) - 1 else ""), {"color": RED_ON_NAVY, "bold": True} if i in hot else {}) for i, ln in enumerate(lines)]
        return self.text(sid, x + 0.22, y + 0.14, w - 0.4, h - 0.24, parts, size=size, color=WHITE, spacing=110, edge=True, mono=True)

    def card(self, sid, x, y, w, h=None, head=None, body=None, items=None, fill=CARD, line=RULE, step=None, bullets=False):
        """見出しと本文の箱。箱の上に一回り小さい文字の枠を重ねる（文字の枠の内側の余白は変えられないので、枠と文字の間をここで空ける）。
        head・body・items を省くと、白い地に罫線の箱だけを置く（中身を自分で組むカード。h を渡す）。
        body は 1 つの文字の枠に入れるもの（text の parts と同じ。bullets で箇条書き）。
        items は (見出し, 説明) の並びで、既定では 1 つの文字の枠に空行を挟んで流す（1 行と 2 行の項目が混ざっても間がそろう）。
        [slides-component-009] step（in）を渡すと、前のように項目ごとに決まった間隔で置く（左右のカードで項目の上端をそろえたいときだけ。
        決まった間隔だと、行数の違う項目の間がそろわない）。
        h を省くと中身から決める（card_h）。戻りは箱の下端（in。下に置く要素の位置に使う）。"""
        if h is None:
            if not (head or body or items):
                raise ValueError("中身を自分で組むカードは h を渡す")
            h = card_h(w, head, body, items, step, bullets)
        self.anchor = self.box(sid, x, y, w, h, fill, line)
        top = y + card_top(w, head)
        if head:
            self.text(sid, x + PAD, y + 0.1 + CARD_DOWN, w - 2 * PAD, top - y - 0.16 - CARD_DOWN, head, size=12, color=HEAD, bold=True, spacing=100)  # card_top は 1 行 0.2 in で下げる
        bh = max(h - (top - y) - 0.1, 0.2)  # 本文の枠。見出しが折り返して h より高くなっても、高さ 0 以下の枠は送らない（h の警告は SpecPage が出す）
        if items and step is None:
            self.text(sid, x + PAD, top, w - 2 * PAD, bh, card_items(items), spacing=125)
        for i, item in enumerate(items if step is not None else []):
            self.text(sid, x + PAD, top + i * step, w - 2 * PAD, step - 0.08, card_items([item]), spacing=125)
        if body:
            self.text(sid, x + PAD, top, w - 2 * PAD, bh, body, spacing=125, bullets=bullets)
        return y + h

    def table(self, sid, x, y, widths, rows, size=11, row_h=0.36, header=True, first_col=True, zebra=True, align=None, mono_cols=(), fills=(), vlines=None,
              valign="middle", borders="rows"):
        """rows は行の並びで、セルは文字列か、parts の並び（d.text と同じ書式。改行は \\n）か、dict。header は見出しの行の数（True は 1）。
        見出しの行は濃紺に白の太字、1 列目は HEAD の太字（first_col）、行は 1 行おきに PANEL（zebra）、ほかは CARD。align は列ごとの "left"・"center"・"right" の並び（金額は右）、
        valign はセルの上下の寄せ（top・middle・bottom）。罫線は borders で、rows は横の罫線だけを RULE で引き（visual.md の 5。既定）、grid は縦横と外枠、none は引かない。
        dict のセルは text（文字列か parts）と、colspan・rowspan（右と下へ結合する数。覆う位置にはセルを書かない。HTML と同じ）、fill（そのセルの塗り）、
        align・valign（そのセルの寄せ）、color（文字の色。濃い fill なら WHITE などを渡す）、bullets（箇条書き）。
        行は文字に合わせて伸びる（row_h は最小）。戻りは表の下端の見込み（in。下に置く要素の位置に使う）。
        mono_cols の列は、見出しの行を除いて英数字を等幅の MONO にする（コマンドの一覧など。visual.md の 2）。
        row_h は行ごとの並びでもよい。fills は (行, 列, 色) の並び（0 始まり。行か列が None ならその列か行の全部）で、1 行おきの塗りの上に塗る（行か列の強調）。
        vlines は (始めの列, 列の数) で、見出しの行の下のその列の左右と間に縦の罫線を引く（ガントの月の区切り。線の図形で引くと lint の格子に出る）。"""
        t, nr, nc, nh = self.oid(), len(rows), len(widths), int(header)
        grid = table_grid(rows, nc, pad=True)
        hs = list(row_h) if isinstance(row_h, (list, tuple)) else [row_h] * nr
        if len(hs) != nr:
            raise ValueError(f"row_h の数（{len(hs)}）が行の数（{nr}）と違う")
        whole = {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nr, "columnSpan": nc}

        def rng(r, c, rs=1, cs=1):
            return {"location": {"rowIndex": r, "columnIndex": c}, "rowSpan": rs, "columnSpan": cs}

        def border(pos, alpha, at=whole):
            return {"updateTableBorderProperties": {"objectId": t, "tableRange": at, "borderPosition": pos,
                                                    "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": paint(RULE), "alpha": alpha}}, "weight": pt(0.75)},
                                                    "fields": "tableBorderFill,weight"}}

        def cell_props(at, props, fields):
            return {"updateTableCellProperties": {"objectId": t, "tableRange": at, "tableCellProperties": props, "fields": fields}}

        def fill(at, color):
            return cell_props(at, {"tableCellBackgroundFill": {"solidFill": {"color": paint(color)}}}, "tableCellBackgroundFill")

        lines = {"rows": [border("ALL", 0), border("INNER_HORIZONTAL", 1), border("BOTTOM", 1)], "grid": [border("ALL", 1)], "none": [border("ALL", 0)]}[borders]
        self.reqs += [{"createTable": {"objectId": t, "rows": nr, "columns": nc, "elementProperties": place(sid, x, y, sum(widths), sum(hs))}}, *lines,
                      *[border(pos, 1, rng(nh, vlines[0], nr - nh, vlines[1])) for pos in ("LEFT", "INNER_VERTICAL", "RIGHT") if vlines],
                      cell_props(whole, {"contentAlignment": VALIGN[valign]}, "contentAlignment"),
                      *[{"updateTableRowProperties": {"objectId": t, "rowIndices": [r for r in range(nr) if hs[r] == h], "tableRowProperties": {"minRowHeight": emu(h)},
                                                      "fields": "minRowHeight"}} for h in dict.fromkeys(hs)]]
        self.reqs += [{"updateTableColumnProperties": {"objectId": t, "columnIndices": [j], "tableColumnProperties": {"columnWidth": emu(w)}, "fields": "columnWidth"}}
                      for j, w in enumerate(widths)]
        self.reqs += [fill(rng(r, 0, 1, nc), NAVY if r < nh else PANEL if zebra and (r - nh) % 2 else CARD) for r in range(nr)]
        self.reqs += [fill(rng(0 if r is None else r, 0 if c is None else c, nr if r is None else 1, nc if c is None else 1), color) for r, c, color in fills]
        # セルの塗りと寄せは、結合する前に覆う範囲の全部に付ける（結合したあとに、結合したセルの一部にかかる範囲を送らない）
        span = {(r, c): rng(r, c, d.get("rowspan", 1), d.get("colspan", 1)) for r, c, d in grid}
        self.reqs += [fill(span[r, c], d["fill"]) for r, c, d in grid if d.get("fill")]
        self.reqs += [cell_props(span[r, c], {"contentAlignment": VALIGN[d["valign"]]}, "contentAlignment") for r, c, d in grid if d.get("valign")]
        self.reqs += [{"mergeTableCells": {"objectId": t, "tableRange": span[r, c]}} for r, c, d in grid if d.get("rowspan", 1) > 1 or d.get("colspan", 1) > 1]
        for r, c, d in grid:
            head, parts, bul = r < nh, cell_parts(d), d.get("bullets", False)
            first, mono, s = first_col and c == 0 and not head, c in mono_cols and not head, spec_plain(parts)
            avail = sum(widths[c:c + d.get("colspan", 1)]) - 2 * INSET - (size * 1.3 / 72 if bul else 0)
            for ln in re.split(r"[\n\v]", s):
                if ln and est_lines(ln, avail, size, mono, head or first) > 1:
                    self.warn(f"表のセルが折り返す見込み「{ln}」（列の幅 {avail + 2 * INSET:.2f} in）")
            if not s:
                continue
            loc, color = {"rowIndex": r, "columnIndex": c}, d.get("color") or (WHITE if head else HEAD if first else TEXT)
            spacing = 120 if est_lines(s, avail, size, bold=head or first) > 1 else 100
            self.reqs += [{"insertText": {"objectId": t, "cellLocation": loc, "insertionIndex": 0, "text": s}},
                          {"updateTextStyle": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"},
                                               "style": {"fontFamily": FONT, "fontSize": pt(size), "bold": head or first, "foregroundColor": {"opaqueColor": paint(color)}},
                                               "fields": "fontFamily,fontSize,bold,foregroundColor"}},
                          {"updateParagraphStyle": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"},
                                                    "style": {"lineSpacing": spacing, "spaceAbove": pt(0), "spaceBelow": pt(0),
                                                              "alignment": ALIGN[d.get("align") or (align or ["left"] * nc)[c]]},
                                                    "fields": "lineSpacing,spaceAbove,spaceBelow,alignment"}}]
            self.runs(t, parts, color, loc)
            if spacing > 100:  # 大きな文字の段落は 100（table_h の spec_text_h と同じ見込み）
                self.big_paras(t, parts, size, loc)
            if mono:
                self.reqs += mono_reqs(t, s, loc)
            if bul:  # d.text の箇条書きと同じ字下げ
                self.reqs += [{"createParagraphBullets": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
                              {"updateParagraphStyle": {"objectId": t, "cellLocation": loc, "textRange": {"type": "ALL"},
                                                        "style": {"indentStart": pt(size * 1.3), "indentFirstLine": pt(size / 2)}, "fields": "indentStart,indentFirstLine"}}]
        return y + table_h(widths, rows, size, hs, header, mono_cols, first_col)

    def arrow(self, sid, x1, y1, x2, y2, color=SUB, head=True, dash=False, weight=1.25, link=None, bent=False):
        """細い線。横の矢印は、両側の箱の上下の中央に引く（visual.md の 4。lint が見る）。dash で点線（「できるが手間」などの意味）、weight は太さ（pt）。
        link は (始めの図形の ID, 辺, 終わりの図形の ID, 辺) で、線を四角の図形の辺の中央（接続点）につなぐ（画面で箱を動かしても付いてくる）。辺は top・left・bottom・right。
        (x1, y1)・(x2, y2) はその接続点に置く（Google がつないだ点に引き直す）。bent は折れ線（両端をつないだときだけ。つないだ辺に合わせて、横・縦・横、縦・横・縦、1 回だけ折れる形に Google が引く）。
        [slides-component-024] 2026-10-16 の sandbox で、つないだ線の形、グループの中の図形につなげること、つないでいない折れ線は形が崩れることを確かめた。
        2026-10-19 の sandbox で、横の辺から上下の辺（縦の辺から左右の辺）につないだ折れ線が、1 回だけ折れる形（BENT_CONNECTOR_2）になることと、
        中央がそろって幅か高さが 0 の折れ線は作れないことを確かめた（SpecPage.link の辺を書いた矢印と、そろった bent をまっすぐ引くこと）。"""
        if bent and not link:
            raise ValueError("折れ線（bent）は、両端を図形につないだときだけ引ける")
        e = self.oid()
        props = {"lineFill": {"solidFill": {"color": paint(color)}}, "weight": pt(weight), "endArrow": "FILL_ARROW" if head else "NONE"}
        if dash:
            props["dashStyle"] = "DASH"
        if link:
            a, sa, b, sb = link
            props |= {"startConnection": {"connectedObjectId": a, "connectionSiteIndex": SITE[sa]}, "endConnection": {"connectedObjectId": b, "connectionSiteIndex": SITE[sb]}}
        self.reqs += [{"createLine": {"objectId": e, "category": "BENT" if bent else "STRAIGHT", "elementProperties": place(
                          sid, x1, y1, abs(x2 - x1), abs(y2 - y1), 1 if x2 >= x1 else -1, 1 if y2 >= y1 else -1)}},
                      {"updateLineProperties": {"objectId": e, "lineProperties": props, "fields": ",".join(props)}}]
        return e

    def image(self, sid, src, x, y, w, h, alt=None):
        """src は PNG・JPG・GIF の URL（SVG は png() を通す）か、手元の画像のパス（asset() か build/assets/。SVG も可）。
        縦横の比は保ったまま枠に収まり、枠の中央に置かれる。手元の画像は、build のときに carry で Slides API が読める URL にする。
        ロゴには alt に名前を入れる（代替テキスト）。"""
        e = self.oid()
        if src.startswith("http") and re.search(r"\.svg($|[?#])", src, re.I):
            sys.exit(f"Slides API は SVG の URL を読めない: {src}。png(<URL>) で PNG の URL にする（../images.md）")
        if not src.startswith("http"):
            self.images.append(os.path.abspath(src))
            src = f"@IMG{len(self.images) - 1}"
        self.reqs.append({"createImage": {"objectId": e, "url": src, "elementProperties": place(sid, x, y, w, h)}})
        if alt:
            self.reqs.append({"updatePageElementAltText": {"objectId": e, "title": alt, "description": alt}})
        return e

    def icon(self, sid, name, x, y, size, color=TEXT):
        """アイコンを size（in）の正方形に置く。name は Iconify の名前（"tabler:database"。URL のまま貼る。既定）か、react-icons の名前
        （"TbDatabase"。組むときに手元で PNG にして carry で貼る。前の pages.py のため）。color は役割の名前か 6 桁（1 色のアイコンにだけ効く）。代替テキストは名前。"""
        color = hex_of(color)  # 役割の名前（NAVY は "DARK1"）は、デッキの配色の 6 桁にする（画像の色はテーマの色を指せない）
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", str(color)):
            sys.exit(f"アイコンの色は役割の名前か 6 桁で渡す: {name} に {color!r}")
        return self.image(sid, iconify(name, color) if ":" in name else render_icon(name, color), x, y, size, size, alt=name)

    # ---- 1 枚の型（visual.md の 1） ----
    def page(self, title, lead=None, kicker=None):
        sid = self.slide()
        if kicker:
            self.text(sid, X - INSET, Y_KICK, W + 2 * INSET, 0.26, kicker, size=11, color=RED_TEXT, bold=True)
        sz = 24  # 1 行に収まらなければ 18pt まで縮め、警告する（言い切りを短くするのが先）
        while em_width(title, bold=True) * sz / 72 > W and sz > 18:
            sz -= 0.5
        if sz < 24:
            self.warn(f"見出しを {sz:g}pt に縮めた「{title}」")
        self.text(sid, X - INSET, Y_TITLE, W + 2 * INSET, 0.5, title, size=sz, color=HEAD, bold=True)
        if lead:
            if est_lines(lead, W, 12) > 1:
                self.warn(f"リードが 2 行の見込み「{lead}」")
            self.text(sid, X - INSET, Y_LEAD, W + 2 * INSET, 0.34, lead, size=12)
        return sid

    def cover(self, title, kicker, sub=None, variant=1):
        """表紙: 小見出し（相手と日付）→ タイトル（2 行まで）→ 副題、左下に社名。variant はテンプレートの表紙のパターンの番号（見本のページにある）。"""
        s, tw, (head, accent, _, foot) = self.variant("cover", variant)  # 文字の幅は、元のタイトルの枠の右端まで（図形・写真に重ねない）
        self.text(s, X - INSET, 2.3, tw, 0.3, kicker, size=11, color=accent, bold=True)
        lines = title.count("\n") + 1  # 2 行にするときは、文節の切れ目に \n を入れる
        self.text(s, X - INSET, 2.7, tw, 0.62 * lines, title, size=34, color=head, bold=True, spacing=110)
        if sub:
            self.text(s, X - INSET, 2.7 + 0.62 * lines + 0.23, tw, 0.4, sub, size=13, color=accent, bold=True)
        if COMPANY:
            self.text(s, X - INSET, 6.7, tw, 0.3, COMPANY, size=11, color=foot)
        return s

    def divider(self, num, title, sub=None, variant=1):
        """章の扉: 章番号（飾り）→ 章タイトル → 副題。variant はテンプレートの扉のパターンの番号（章ごとに地を変えられる）。"""
        s, tw, (head, accent, decor, _) = self.variant("section", variant)
        self.text(s, X - INSET, 1.9, tw, 1.4, num, size=88, color=decor, bold=True)
        self.text(s, X - INSET, 3.45, tw, 0.6, title, size=30, color=head, bold=True)
        if sub:
            self.text(s, X - INSET, 4.2, tw, 0.4, sub, size=12.5, color=accent, bold=True)
        return s

    def band(self, sid, head, sub=None, h=None):
        """結論バンド。下端を BAND_BOTTOM に固め、中身に合わせて上へ伸ばす（h を省いたとき。1 文目と補足が 1 行ずつなら 0.86 in、1 文目だけなら 0.65 in）。
        文字と枠の間は、左右 BAND_PAD_X・上下 BAND_PAD_Y（1 字分より大きめ。見た目 1-8）。箱と文字の枠を分ける。戻りはバンドの上端（in）。"""
        h = h or band_h(head, sub)
        parts = [(head, {"bold": True, "size": 13})] + ([("\n" + sub, {"size": 11, "color": SUB_ON_NAVY})] if sub else [])
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
        ページ番号は著作権表示と同じ大きさにする。濃紺の地（表紙・扉）では、著作権表示とページ番号を SUB_ON_NAVY にする（SUB は届かない）。foot=False の流用ページは元の表示を維持する。
        ページへのリンクを、ページの ID で付ける（番号で持つと、画面でページを足したり並べ替えたりしたときにずれる）。"""
        classification = re.search(r"(?:^|[｜|])\s*(Internal Only|Confidential)\s*$", self.name, re.I)
        footer = COPYRIGHT + (f"｜{classification.group(1)}" if classification else "")
        for sid in self.slides:
            if sid in self.nofoot:
                if sid != self.slides[0]:
                    self.reqs.append({"deleteObject": {"objectId": sid + "_n"}})
                continue
            c = self.footc.get(sid) or (SUB_ON_NAVY if sid in self.dark else SUB)
            self.text(sid, X - INSET, Y_FOOT, W - 1.2, 0.28, footer, size=COPYRIGHT_PT, color=c)
            if sid != self.slides[0]:  # 前のテンプレート（ページ番号が 11pt）から作ったデッキも、組み直せばそろう
                self.reqs += number_style(sid + "_n", c)
        for req, n in self.links:
            if isinstance(n, dict):
                if n["page"] not in self.page_names:
                    sys.exit(f"リンク先のページ「{n['page']}」がない（このデッキの JSON のページ: {'・'.join(self.page_names) or 'なし'}）")
                target = self.page_names[n["page"]]
            elif not 1 <= n <= len(self.slides):
                raise ValueError(f"リンク先の p.{n} がない（{len(self.slides)} 枚）")
            else:
                target = self.slides[n - 1]
            req["updateTextStyle"]["style"]["link"] = {"pageObjectId": target}
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


# ---- JSON のページ（Deck.spec。../pages.md の slides-pages-034） ----
# 書く形（LLM が書く。並べ方と意味だけ）→ 解く（spec_page。並べ方・記法・ID・既定の値・画像のパス）→ 解いた形（d.resolved。in の絶対位置で、
# Deck のメソッドの引数をすべて持つ。slides.py resolve が出す）→ 要求（Deck）。
# 形の版は k8s にならい、ファイルの頭の apiVersion と kind で持つ。上げるのは、キーの意味が変わるときだけ（足すときは上げない。../pages.md の slides-pages-035）
API_VERSION = "slides/v1"
KINDS = ("deck", "page", "component", "theme")
COLOR_NAMES = ("NAVY", "BG", "RED_ON_NAVY", "PANEL", "NAVY_BLOCK", "GA", "RED_TEXT", "PREVIEW", "SUB", "OSS", "RED", "WHITE", "PUBLIC_PREVIEW",
               "TEXT", "RULE", "RED_SOFT", "STAGE_TEXT", "DECOR", "HEAD", "CARD", "SUB_ON_NAVY", "ON_RED")
ON_FILL = {"NAVY": ("WHITE", "RED_ON_NAVY"), "NAVY_BLOCK": ("WHITE", "RED_ON_NAVY"), "RED": ("ON_RED", "ON_RED"), "OSS": ("WHITE", "WHITE")}  # 濃い塗り → (文字の色, ***強調*** の色)。ほかの地は TEXT・RED_TEXT
ALIGN = {"left": "START", "center": "CENTER", "right": "END"}
VALIGN = {"top": "TOP", "middle": "MIDDLE", "bottom": "BOTTOM"}
# 図形の形（Slides API の shapeType を小文字に）。過去の資料で使った形と、矢羽根の段の頭（home_plate）だけ。ほかは使われたら足す（slides-pages-035）
SHAPES = {k.lower(): k for k in ("RECTANGLE", "ROUND_RECTANGLE", "ELLIPSE", "CHEVRON", "HOME_PLATE", "FOLDED_CORNER", "CAN")}
GAP_BODY, GAP, GAP_ARROW, ARROW_PAD = 0.3, 0.24, 0.6, 0.08  # 本文の部品の間、stack・row・grid の間、arrows の row の間、矢印と箱の間（in）
BOX_IN, EDGED = 0.08, ("card", "box", "label", "code", "stat", "table")  # 囲み（box）の辺と中の部品の間の下限（in。slides-visual-044）、縁の見える部品（塗りか枠線のある text も）
LABEL_GAP = 0.04  # 矢印の札と線の間（in。縦の線の右は 2 倍。文字の上には行の高さの空きがあり、横の左にはない）
# 印のあるカード（過去の資料の node・icard・ncard。2026-10-16）: 印の大きさ（アイコン・番号／画像）、カードの端から印、印から文字（in）
MARK, MARK_IMG, MARK_IN, MARK_GAP = 0.36, 0.5, 0.18, 0.14
STAT_PAD, HEAD_GAP = 0.2, 0.06  # 数字の強調の箱の端と文字の間、印のあるカードの見出しと本文の間（in）
LIST_GAP = 0.16  # list の項目の間（in）
MARK_TOP, MARK_END = 0.29, 0.22  # 印のあるカードの文字の上（上に印を置くカードは印の上で、0.05 in 詰める）と最終行の下（本文が 2 行以上は、行の高さの見積もりの誤差の分 0.03 in 足す）の空き（in）。
# 最終行の下には行間の空きがあるので、上を下より 0.07 in 広くすると上下が同じに見える（2026-10-20 の画像で測った）
# ガント（過去の資料の gantt。slides-pages-010）: 項目の列、補足の列の最小、月の列の最大と最小、バーの高さ（9pt の 2 行）、段の間、行の上下、バーと列の端、
# 余った高さを 1 行に足す上限（in）
G_HEAD, G_NOTE, G_COL, G_COL_MIN, G_BAR, G_LANE, G_PAD, G_INSET, G_GROW = 2.2, 2.4, 1.0, 0.4, 0.42, 0.06, 0.1, 0.04, 0.4
G_MARK, G_MARK_GAP = 0.2, 0.06  # 節目の印（赤の菱形）の大きさ、印と言葉の間（in）
# 棒グラフ: 縦の棒の既定の高さ、数字と名前の行の高さ、棒の幅（枠の幅に対する比）と最大、横の棒の行の高さと棒の太さ、
# 折れ線の段の高さ（点の数字の行と、いちばん下の点と棒の段の間を含む）と、その下の間、点の大きさ（in）
B_H, B_LABEL, B_FILL, B_MAX, B_ROW, B_BAR, B_LINE, B_LINE_GAP, B_DOT = 2.6, 0.3, 0.6, 1.2, 0.42, 0.28, 0.8, 0.1, 0.1
TABLE_BORDERS = ("rows", "grid", "none")  # 表の罫線: 横の罫線だけ（既定。visual.md の 5）、縦横と外枠、なし
SITE = {"top": 0, "left": 1, "bottom": 2, "right": 3}  # 四角の図形の辺 → Slides API の接続点の番号（Deck.arrow の link）
CONNECT = ("text", "label", "card", "stat", "code", "box")  # 矢印をつなげる部品（SpecPage.place が、四角の枠が箱と同じ大きさのものだけを選ぶ）
# キーの型。s 文字列、md 記法つきの文字（spec_md）、n 数、i 整数、b 真偽、c 色、els 部品の並び、pt ID か [x, y]、ほかは SPEC_OK
_GEO = {"id": "s", "w": "w", "h": "p", "x": "n", "y": "n"}  # どの部品にも書ける（x・y は frame の中だけ、w の "fit" は label だけ）
_ESC = {"raw": "raw"}  # 形の外の書き方（どの部品にも書ける。lint が要確認に出し、build が数を残す。slides-pages-035）
_BOX = {"fill": "c", "line": "c", "dash": "b", "weight": "p", "shape": tuple(SHAPES), "radius": "n"}
_TEXT = {"size": "p", "color": "c", "bold": "b", "align": tuple(ALIGN), "mono": "b", "pad": "n", "spacing": "p", "para_gap": "n"}
SPEC_EL = {  # type → (要るキー, 書けるキー)
    "text": ({"text": "md"}, {**_TEXT, **_BOX, "valign": tuple(VALIGN)}),
    "label": ({"text": "md"}, {k: _TEXT[k] for k in ("size", "color", "bold", "align", "mono", "pad")} | {"fill": "c", "radius": "n"}),
    "card": ({}, {"head": "s", "text": "md", "items": "items", "fill": "c", "line": "c", "step": "p",
                  "icon": "s", "num": "ns", "image": "s", "shape": NUM_SHAPES, "align": ("left", "center"), "valign": ("top", "middle")}),  # icon・num・image は印（どれか 1 つ）。shape は num の形
    "stat": ({"value": "s"}, {"unit": "s", "label": "s", "sub": "s", "size": "p", "color": "c", "fill": "c", "line": "c", "align": ("left", "center")}),  # 数字の強調
    "code": ({"text": "s"}, {"hot": "ints", "size": "p"}),
    "table": ({"rows": "rows"}, {"widths": "nums", "header": "hn", "first_col": "b", "zebra": "b", "align": "aligns", "valign": tuple(VALIGN), "borders": TABLE_BORDERS,
                                 "mono_cols": "ints", "size": "p", "row_h": "nh", "fills": "fills"}),  # セルは記法つきの文字か TABLE_CELL
    "image": ({"src": "s"}, {"alt": "s"}),
    "icon": ({"name": "s"}, {"size": "p", "color": "c"}),
    "num": ({"n": "ns"}, {"size": tuple(NUM), "fill": "c", "shape": NUM_SHAPES}),
    "list": ({"items": "litems"}, {"icon": "s", "start": "pi", "digits": "pi", "size": tuple(NUM), "shape": NUM_SHAPES, "gap": "n", "color": "c"}),  # 印（番号かアイコン）と文字の並び。印の中心を項目の 1 行目にそろえる。digits は整数の番号を 0 で埋める桁、shape は番号の形
    "box": ({}, _BOX),
    "arrow": ({"from": "pt", "to": "pt"}, {"color": "c", "head": "b", "dash": "b", "weight": "p", "route": ("straight", "bent"), "label": "md",
                         "label_side": ("top", "bottom", "left", "right"), "offset": "f"}),  # label は線の札、label_side はその置き場所、offset は線を横（縦）にずらす in
    "gantt": ({"cols": "cols", "rows": "grows"}, {"today": "p"}),  # 予定表（slides-pages-010）
    "bars": ({"items": "bitems"}, {"unit": "s", "horizontal": "b", "hot": "ints", "line": "bline", "threshold": "bthr"}),  # 1 系列の棒グラフ（visual.md の 5）。折れ線と直線を重ねられる
    "row": ({"items": "kids"}, {"gap": "n", "widths": "nums", "arrows": "b"}),
    "stack": ({"items": "kids"}, {"gap": "n"}),
    "grid": ({"items": "kids", "cols": "pi"}, {"gap": "n"}),
    "frame": ({"items": "kids", "h": "p"}, {}),
}
LIST_ITEM = ({}, {"text": "md", "head": "s", "icon": "s", "num": "ns", "image": "s"})  # list の項目（文字だけなら "文字" と書ける）。印は icon・num・image のどれか 1 つで、list の icon と番号より勝つ
TABLE_CELL = ({"text": "md"}, {"colspan": "pi", "rowspan": "pi", "fill": "c", "color": "c", "align": tuple(ALIGN), "valign": tuple(VALIGN)})  # 表のセル（HTML の td にならった）
GANTT_ROW = ({"head": "s"}, {"bars": "gbars", "marks": "gmarks", "note": "s"})  # ガントの行: 項目、バーの並び、節目の並び、補足（右の列。どれかの行に書くと列ができる）
GANTT_STATUS = {"plan": "NAVY", "tbd": "CARD", "done": "PANEL", "hot": "RED_SOFT"}  # バーの状態 → 塗り（決まった予定・未定〔点線の枠〕・終わった・強調〔赤の文字〕）。色は書かせず、資料をまたいで意味をそろえる
# 強調を RED の地にしないのは、9pt の白の文字が 3.62:1 で 4.5:1 に届かないから（2026-10-19、見本を組んで lint が止めた）。淡い赤の地に RED_TEXT は 4.69:1
GANTT_BAR = ({"from": "pi", "to": "pi"}, {"text": "s", "status": tuple(GANTT_STATUS)})  # バー: 何列目から何列目まで（1 から、両端を含む）、文字、状態（既定は plan）
GANTT_MARK = ({"at": "p", "text": "s"}, {})  # 節目: 位置（today と同じ。3 は 3 列目の左端、3.5 は中ほど）、言葉（11pt の 1 行）
BARS_LINE = ({"values": "bvals"}, {"unit": "s", "label": "s"})  # 棒の折れ線: 棒ごとの数（items の順。mermaid の xychart の line [..]）、単位、何の数か
BARS_THRESHOLD = ({"value": "n"}, {"label": "s"})  # 棒の直線（目標・上限など）: 棒と同じ目盛りの数、何の線か
OUTLINE = ("text", "box")  # shape が部品そのものの形（num・list・card の shape は番号の形）
NO_SIZE = ("icon", "num", "arrow")  # w・h を書かない（大きさは size、矢印は両端）
CONTAINERS = ("row", "stack", "grid", "frame")  # 並べ方の箱（中の部品を置くだけで、Deck を呼ばない）
NO_ESC = (*CONTAINERS, "list")  # raw を書けない（並べ方の箱は Deck を呼ばない。list は印と文字で呼ぶメソッドが分かれる）
NO_H = ("row", "stack", "grid", "gantt", "list")  # h を書かない（高さは中身から決まる。中身より小さい h は次の部品と重なる。frame だけは h が要る）
STRETCH = ("card", "stat", "box", "label", "code", "frame", "stack")  # row・grid で行の高さまで伸ばす（text は塗りか枠線のあるときだけ）
SPEC_PAGE = {
    "page": ({"title": "s"}, {"lead": "s", "kicker": "s", "body": "els", "band": "band", "source": "md", "speakerNotes": "s", "authorNotes": "strs"}),
    "cover": ({"title": "s", "kicker": "s"}, {"sub": "s", "variant": "pi", "speakerNotes": "s", "authorNotes": "strs"}),
    "divider": ({"num": "s", "title": "s"}, {"sub": "s", "variant": "pi", "speakerNotes": "s", "authorNotes": "strs"}),
    "slide": ({}, {"bg": "c", "foot": "b", "body": "els", "source": "md", "speakerNotes": "s", "authorNotes": "strs"}),
}
SPEC_DECK = ({"name": "s", "pages": "pages"}, {"theme": "s", "authorNotes": "strs"})  # theme はいちばん上のデッキのファイルのもの（slides.py themes の名前）。authorNotes はどこにも組まない（ページの authorNotes と同じ）
# テーマのファイル（read_theme）。colors は役割の名前（ROLE）・テーマに入れない色（FIXED）・名前で引く役割（NAMED）→ 6 桁。cover・section は
# 会社のテンプレートから残す表紙・扉のレイアウトの名前の並び（template.py が文字の幅 w と地の明るさ tone を測って書き込む。../../slides-template/SKILL.md）
SPEC_THEME = ({}, {"description": "s", "font": "s", "mono": "s", "copyright": "s", "colors": "colors", "cover": "layouts", "section": "layouts"})
# raw に書いた Deck の引数のうち、形のキーで書けるもの（type, 引数 → 形のキー）。lint が知らせ、slides.py upgrade が書き換える。形に足したらここにも足す
# 同じ名前で同じ意味のもの（数え始めや単位の違う mono_cols・hot・fills・widths と、stat の size・color〔数字の大きさと色〕は入れない。2026-10-16 のレビュー）
_SAME = {"text": "size color bold align valign mono fill line dash weight radius pad spacing", "label": "size color fill bold align mono pad radius",
         "card": "head fill line step", "code": "size", "table": "size header first_col zebra align valign borders row_h", "image": "alt", "icon": "size color",
         "num": "size fill shape", "box": "fill line dash weight radius", "arrow": "color head dash weight", "stat": "fill line align"}
SPEC_PROMOTED = {(t, k): k for t, ks in _SAME.items() for k in ks.split()} | {("text", "gap"): "para_gap", ("text", "kind"): "shape", ("box", "kind"): "shape"}
MD = re.compile(r"\\([\\*`\[\]<{}])|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\{(\d+(?:\.\d+)?):(.+?)\}|`([^`]+)`|\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)|<br>")  # URL の中の 1 段の () も読む


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _strs(v, n=None):
    return isinstance(v, list) and all(isinstance(y, str) for y in v) and (n is None or len(v) == n)


def _color(v):
    """ページの JSON の色。役割の名前だけ（6 桁は書けない。値はテーマが決め、どの組もテーマの色で測れる。どうしても要る色は raw に書き、lint が要確認に出す）。"""
    return v in COLOR_NAMES


_pos = lambda v: _num(v) and v > 0  # 大きさ・太さ・行間など、0 だと描けないもの
SPEC_OK = {"s": lambda v: isinstance(v, str), "md": lambda v: isinstance(v, str), "n": lambda v: _num(v) and v >= 0, "f": _num, "p": _pos, "i": _int,
           "pi": lambda v: _int(v) and v >= 1, "b": lambda v: isinstance(v, bool), "c": _color,
           "w": lambda v: _pos(v) or v == "fit", "nh": lambda v: _pos(v) or isinstance(v, list) and bool(v) and all(map(_pos, v)),
           "els": lambda v: isinstance(v, list), "kids": lambda v: isinstance(v, list) and bool(v),  # 並べ方の箱の中は 1 つ以上
           "pages": lambda v: isinstance(v, list) and bool(v) and all(isinstance(x, str) and x.endswith(".json") for x in v),
           "pt": lambda v: isinstance(v, str) or isinstance(v, list) and len(v) == 2 and all(map(_num, v)),
           "items": lambda v: isinstance(v, list) and all(_strs(x, 2) for x in v),
           "litems": lambda v: isinstance(v, list) and bool(v) and all(isinstance(x, (str, dict)) for x in v),
           "strs": _strs, "cols": lambda v: _strs(v) and bool(v), "grows": lambda v: isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v),
           "gbars": lambda v: isinstance(v, list) and all(isinstance(x, dict) for x in v), "gmarks": lambda v: isinstance(v, list) and all(isinstance(x, dict) for x in v),
           "bline": lambda v: isinstance(v, dict), "bthr": lambda v: isinstance(v, dict),
           "bvals": lambda v: isinstance(v, list) and bool(v) and all(_num(x) and x >= 0 for x in v),
           "bitems": lambda v: isinstance(v, list) and bool(v) and all(isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and _num(x[1]) and x[1] >= 0 for x in v),
           "rows": lambda v: isinstance(v, list) and bool(v) and all(isinstance(x, list) and all(isinstance(c, (str, dict)) for c in x) for x in v) and bool(v[0]),  # 上の rowspan が全部の列を覆う行は []
           "hn": lambda v: isinstance(v, bool) or _int(v) and v >= 0,
           "nums": lambda v: isinstance(v, list) and all(_num(x) and x > 0 for x in v), "ints": lambda v: isinstance(v, list) and all(_int(x) and x > 0 for x in v),
           "fills": lambda v: isinstance(v, list) and all(isinstance(x, list) and len(x) == 3 and all(i == "all" or _int(i) and i >= 1 for i in x[:2]) and _color(x[2]) for x in v),
           "aligns": lambda v: isinstance(v, list) and bool(v) and all(a in ALIGN for a in v), "ns": lambda v: isinstance(v, str) or _int(v),
           "band": lambda v: isinstance(v, str) or isinstance(v, dict) and isinstance(v.get("text"), str) and set(v) <= {"text", "sub"} and isinstance(v.get("sub", ""), str),
           "raw": lambda v: isinstance(v, dict) and bool(v),
           "colors": lambda v: isinstance(v, dict) and all(k in (*ROLE, *FIXED, *NAMED) and isinstance(c, str) and bool(re.fullmatch(r"[0-9A-Fa-f]{6}", c)) for k, c in v.items()),
           "layouts": lambda v: isinstance(v, list) and all(isinstance(x, str) or isinstance(x, dict) and isinstance(x.get("layout"), str) and set(x) <= {"layout", "w", "tone"}
                                                           and (_pos(x["w"]) if "w" in x else True) and x.get("tone", "dark") in TONES for x in v)}


def spec_ok(v, t):
    """v が型 t（SPEC_OK の名前か、選ぶものの並び）に合うか。"""
    return SPEC_OK[t](v) if isinstance(t, str) else v in t


def spec_check(o, schema, loc, extra=None):
    """o（dict）が schema の (要るキー, 書けるキー) と extra（キー → 型）に合うか。合わなければ場所を付けて止める。"""
    need, opt = schema
    known = {"type": "s", **need, **opt, **(extra or {})}
    if not isinstance(o, dict):
        sys.exit(f"{loc}: {{…}} で書く")
    if bad := [k for k in o if k not in known]:
        sys.exit(f"{loc}: 知らないキー {', '.join(bad)}（書けるもの: {'・'.join(known)}。新しい形のキーなら、プラグインを update する）")
    if lack := [k for k in need if k not in o]:
        sys.exit(f"{loc}: {', '.join(lack)} がない")
    for k, v in o.items():
        if not spec_ok(v, known[k]):
            t = known[k]
            sys.exit(f"{loc}.{k}: {v!r} は書けない（{'・'.join(t) if isinstance(t, tuple) else SPEC_TYPES[t]}）")


SPEC_TYPES = {"s": "文字列", "md": "記法つきの文字列", "n": "0 以上の数", "f": "数（負の数も書ける）", "p": "0 より大きい数", "i": "整数", "pi": "1 以上の整数", "b": "true か false", "c": f"色の名前（{'・'.join(COLOR_NAMES)}。6 桁は書けない。値はテーマのファイルで決める）",
              "w": '0 より大きい数（in）か "fit"（label だけ。中身の文字の幅にする）', "nh": "0 より大きい数（in）か、行ごとのその並び",
              "els": "部品の並び", "kids": "1 つ以上の部品の並び", "pages": "ページかデッキのファイルのパス（.json）の並び", "pt": "部品の id（\"<id>.<辺>\" で出る辺・入る辺。辺は top・bottom・left・right）か [x, y]", "items": '[["見出し", "説明"], …]', "strs": '文字列の並び（["…", "…"]）',
              "litems": '["文字", {"head": 見出し, "text": 文字, "icon"・"num"・"image": 印}, …]（文字は記法が書ける）',
              "rows": '[["見出しの行", …], ["セル", {"text": "セル", "colspan": 2}, …], …]（セルは記法つきの文字か {"text": …, …}）', "hn": "true・false か、見出しの行の数（0 以上の整数）", "nums": "正の数の並び",
              "cols": '列の名前の並び（["10 月", "11 月", …]）', "grows": '[{"head": 項目, "bars": [{"from": 列, "to": 列, …}], "marks": [{"at": 位置, "text": 言葉}], "note": 補足}, …]',
              "bitems": '[["名前", 0 以上の数], …]', "bvals": "0 以上の数の並び（items の順）", "bline": '{"values": [数, …], "unit": 単位, "label": 何の数か}',
              "bthr": '{"value": 数, "label": 何の線か}', "gbars": '[{"from": 列, "to": 列, "text": 文字, "status": "plan"・"tbd"・"done"・"hot"}, …]', "gmarks": '[{"at": 位置, "text": 言葉}, …]', "ints": "1 から始まる番号の並び", "aligns": '列ごとの left・center・right の並び（["left", "right", "right"]）',
              "fills": '[[行, 列, 色], …]（rows の何番目かで、見出しの行が 1 行目・いちばん左の列が 1 列目。"all" はその列か行の全部）', "ns": "文字列か整数", "band": '"文字" か {"text": …, "sub": …}',
              "raw": "Deck のメソッドの引数（{\"zebra\": false} など）",
              "colors": f"役割の名前（{'・'.join([*ROLE, *FIXED, *NAMED])}）→ 6 桁の色（# は付けない）", "layouts": 'レイアウトの名前か {"layout": 名前, "w": 幅, "tone": "dark"・"accent"・"light"} の並び'}


def spec_color(c):
    return globals()[c] if c in COLOR_NAMES else c


def spec_md(s, emph=RED_TEXT, loc=""):
    """記法つきの文字を Deck の parts にする。**太字**、***赤の太字***（emph の色）、{32:文字}（32pt）、[名前](URL)、[名前](#p12)（p12.json のページへのリンク）、
    <br>（段落の中の改行）、\\n（段落）。太字・赤・大きさの中には、ほかの書式とリンクを入れられる（**{32:48}**）。
    `コード` は ` を外して本文の書体のまま（地の文の中のコマンド名は等幅にしない。slides-visual-014）。記号そのものは \\* のように \\ を付ける。"""
    out = []

    def add(t, st=None):
        if not t:
            return
        if st:
            out.append((t, st))
        elif out and isinstance(out[-1], str):
            out[-1] += t
        else:
            out.append(t)

    def inner(t, st):  # 中を読み、外の書式を重ねる（中の書式が勝つ）
        parts = spec_md(t, emph, loc)
        for p in [parts] if isinstance(parts, str) else parts:
            if isinstance(p, str):
                add(p, st)
            else:
                add(p[0], {**st, **p[1]})
    i = 0
    for m in MD.finditer(s):
        add(s[i:m.start()])
        esc, red, bold, size, sized, code, name, url = m.groups()
        if esc:
            add(esc)
        elif red:
            inner(red, {"bold": True, "color": emph})
        elif bold:
            inner(bold, {"bold": True})
        elif size:
            inner(sized, {"size": float(size) if "." in size else int(size)})
        elif code:
            add(code)
        elif name:
            if url.startswith("#") and not re.fullmatch(r"#[\w.-]+", url):
                sys.exit(f"{loc}: ページへのリンクは [名前](#<ページのファイル名>) の形（p12.json なら #p12）: {url}")
            inner(name, {"link": {"page": url[1:]} if url.startswith("#") else url})
        else:
            add("\v")
        i = m.end()
    add(s[i:])
    return out[0] if len(out) == 1 and isinstance(out[0], str) else out


def widest_em(s, loc=""):
    """記法つきの文字の、いちばん広い行の幅（em）。段落と <br> で行を分ける。太字（**…**）の run は太字の幅で測る。"""
    md, ws = spec_md(s, loc=loc), [0.0]
    for p in [md] if isinstance(md, str) else md:
        t, b = (p, False) if isinstance(p, str) else (p[0], p[1].get("bold", False))
        for k, piece in enumerate(re.split(r"[\n\v]", t)):
            if k:
                ws.append(0.0)
            ws[-1] += em_width(piece, bold=b)
    return max(ws)


def point_in(p, r, t=0.02):
    """点 p が四角 r（x, y, w, h）の中か縁から t の内にあるか。"""
    return r[0] - t <= p[0] <= r[0] + r[2] + t and r[1] - t <= p[1] <= r[1] + r[3] + t


def rect_in(a, b, t=0.02):
    """四角 a が四角 b の中に収まるか（縁から t のはみ出しは収まると見る）。"""
    return point_in(a[:2], b, t) and point_in((a[0] + a[2], a[1] + a[3]), b, t)


def seg_hits(p, q, r, m=0.03):
    """線分 p–q が四角 r（x, y, w, h）を m だけ内に縮めた中を通るか（Liang–Barsky）。"""
    lo, hi, t0, t1 = (r[0] + m, r[1] + m), (r[0] + r[2] - m, r[1] + r[3] - m), 0.0, 1.0
    if lo[0] >= hi[0] or lo[1] >= hi[1]:
        return False
    for k in (0, 1):
        d = q[k] - p[k]
        if abs(d) < 1e-9:
            if not lo[k] <= p[k] <= hi[k]:
                return False
            continue
        u, v = sorted(((lo[k] - p[k]) / d, (hi[k] - p[k]) / d))
        t0, t1 = max(t0, u), min(t1, v)
    return t0 < t1


def spec_plain(parts):
    return parts if isinstance(parts, str) else "".join(p if isinstance(p, str) else p[0] for p in parts)


def first_pt(parts, size, avail):
    """parts を幅 avail（in）で折り返した 1 行目の、いちばん大きな文字の大きさ（pt。{32:…} の文字があればその大きさ。{8:…} だけなら 8）。
    折り返しは run_lines と同じ送り方で見る。空白だけの文字も、その大きさで行の高さが決まる。"""
    runs = [(p, size, False) if isinstance(p, str) else (p[0], p[1].get("size", size), p[1].get("bold", False)) for p in ([parts] if isinstance(parts, str) else parts)]
    t = "".join(c for c, *_ in runs)
    pts = [sz for c, sz, _ in runs for _ in c]
    ws = [em_width(ch, False, b) * sz / 72 for c, sz, b in runs for ch in c]
    out, cur = 0, 0.0
    for m in re.finditer(r"[!-~]+| +|[\n\v]|.", t):
        a, z = m.span()
        if t[a] in "\n\v":
            break
        for k, e in ([(k, k + 1) for k in range(a, z)] if sum(ws[a:z]) > avail + 1e-9 else [(a, z)]):
            if cur + sum(ws[k:e]) > avail + 1e-9 and cur > 0:
                return out or size
            out, cur = max(out, *pts[k:e]), cur + sum(ws[k:e])
    return out or size


def spec_bullets(s, loc=""):
    """段落がすべて「- 」で始まるなら、頭を外して箇条書きにする。「- 」の段落とほかの段落が交ざっていたら止める
    （箇条書きは枠の全部の段落に付くので、交ぜると「- 」がそのまま出る。2026-10-16 の sandbox で起きた）。"""
    ps = [p for p in s.split("\n") if p.strip()]
    marked = [p.startswith("- ") for p in ps]
    if any(marked) and not all(marked):
        sys.exit(f"{loc}: 「- 」で始まる段落（箇条書き）とほかの段落が交ざっている。箇条書きと地の文は、別の text に分ける")
    if ps and all(marked):  # 箇条の間の空の段落は落とす（空の箇条になる。間を空けるなら para_gap）
        return "\n".join(p[2:] for p in ps), True
    return s, False


def image_ratio(path):
    """手元の画像の幅 / 高さ（PNG・GIF・JPEG・SVG）。読めなければ None。"""
    b = Path(path).read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    elif b[:6] in (b"GIF87a", b"GIF89a"):
        w, h = int.from_bytes(b[6:8], "little"), int.from_bytes(b[8:10], "little")
    elif b[:2] == b"\xff\xd8":
        i, w = 2, 0
        while i + 9 < len(b) and b[i] == 0xFF:
            if b[i + 1] == 0xFF:  # 印の前の詰めの FF
                i += 1
                continue
            if 0xC0 <= b[i + 1] <= 0xCF and b[i + 1] not in (0xC4, 0xC8, 0xCC):  # SOF の印に高さと幅がある
                h, w = int.from_bytes(b[i + 5:i + 7], "big"), int.from_bytes(b[i + 7:i + 9], "big")
                break
            i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
        if not w:
            return None
    elif m := re.search(rb'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', b[:4096]):
        w, h = float(m.group(1)), float(m.group(2))
    elif (mw := re.search(rb'<svg[^>]*\swidth="([\d.]+)(?:px)?"', b[:4096])) and (mh := re.search(rb'<svg[^>]*\sheight="([\d.]+)(?:px)?"', b[:4096])):
        w, h = float(mw.group(1)), float(mh.group(1))  # viewBox のない SVG
    else:
        return None
    return w / h if h else None


def spec_text_h(parts, avail, size, spacing=None, gap=0, mono=False, bold=False):
    """parts の文字の高さの見込み（in）。段落ごとに、行の高さはその段落でいちばん大きい文字で見る（Deck.text と同じく、行間を省けば 2 行以上で 125、
    基準の 2 倍以上の大きさの段落は 100）。gap は段落の間（pt）。mono は英数字を等幅の幅で見る（Deck.text の mono と同じ）。bold は太さを書いていない文字の太さ（Deck.text の bold と同じ）。
    大きさか太さの違う文字が交ざる段落は、run_lines で文字ごとの幅を見て、語ごとに折り返す。"""
    paras = [[]]
    for p in [parts] if isinstance(parts, str) else parts:
        t, sz, b = (p, size, bold) if isinstance(p, str) else (p[0], p[1].get("size", size), p[1].get("bold", bold))
        for k, piece in enumerate(t.split("\n")):
            if k:
                paras.append([])
            paras[-1].append((piece.replace("\v", "\n"), sz, b))
    full = "\n".join("".join(t for t, *_ in q) for q in paras)
    sp = spacing or (125 if est_lines(full.strip("\n"), avail, size, mono, all_bold(parts, bold)) > 1 else 100)  # Deck.text と同じ見方
    h = 0
    for q in paras:
        big = max([sz for t, sz, _ in q if t] or [size])
        pb = next((b for t, _, b in q if t), bold)  # 太さが交ざらない段落の太さ
        if len({sz for t, sz, _ in q if t}) > 1 or len({b for t, _, b in q if t}) > 1:  # 大きさか太さの違う文字が交ざる段落（行の高さはいちばん大きい文字）
            n = run_lines(q, avail, mono)
        else:
            n = est_lines("".join(t for t, *_ in q) or " ", avail, big, mono, pb)
        h += n * big * 1.2 * (100 if big >= 2 * size else sp) / 100 / 72
    return h + gap / 72 * (len(paras) - 1)


class SpecPage:
    """1 ページを解く。部品を in の絶対位置に置き、Deck の呼び出し（解いた形）を out に貯める。"""

    def __init__(self, base, bg=None):
        self.bg = bg  # ページの地（slide の bg）。塗りのない文字の色を地から決める
        self.base, self.out, self.ids, self.arrows, self.index, self.esc = base, [], {}, [], [], []  # 画像のパスの起点、解いた形、id → (x, y, w, h)、
        # あとで引く矢印、(場所, 文字)、形の外の書き方（場所, キー）
        self.warns, self.placed = [], []  # 組むときの警告（spec_page が d.warn に出す）、置いた部品の (種類, 場所, 位置, 塗りの箱か, 塗りのない文字か, 部品)
        self.anchors, self.body, self.room = {}, None, None  # id → 矢印をつなぐ部品の場所、本文の場所と下端の限り（最後のガントが余った高さを使う）
        self.id_loc, self.lines = {}, []  # id → 部品の場所、引いた矢印の (場所, 折れ点, 矢じりか, 両端の部品の場所, 札の場所)（tangles が見る）

    def emit(self, call, loc, e=None, **kw):
        """Deck の呼び出しを解いた形に足す。部品 e の raw は同じメソッドの引数に重ねる。"""
        if e and (raw := e.get("raw")):
            ps = [n for n in inspect.signature(getattr(Deck, call)).parameters if n not in ("self", "sid", "title") and (call, n) != ("box", "alt")]  # title は棒の印（BAR_MARK。raw で付けると lint が箱を見ない）、box の alt は棒だけ
            if bad := [k for k in raw if k not in ps]:
                sys.exit(f"{loc}（{e['type']}）.raw: {call} の引数にない {', '.join(bad)}（書けるもの: {'・'.join(ps)}）")
            kw |= {k: spec_color(v) if k in ("fill", "line", "color", "bg") else v for k, v in raw.items()}
            self.esc += [(loc, f"{e['type']}.raw.{k}") for k in raw]
        self.out.append({"call": call, "loc": loc, **{k: round(v, 4) if isinstance(v, float) else v for k, v in kw.items()}})

    def check(self, e, loc, in_frame):
        """部品 e と、その中の部品を確かめ、type を返す。x・y は frame の中だけに書ける。"""
        kind = e.get("type") if isinstance(e, dict) else None
        if kind not in SPEC_EL:
            sys.exit(f"{loc}: 部品は {{\"type\": …}} で書き、type は {'・'.join(SPEC_EL)}")
        geo = {k: t for k, t in _GEO.items() if not (kind in NO_SIZE and k in ("w", "h")) and not (kind in NO_H and k == "h") and (in_frame or k not in ("x", "y"))}
        spec_check(e, SPEC_EL[kind], f"{loc}（{kind}）", geo | ({} if kind in NO_ESC else _ESC))
        if kind == "table":  # 列の数がそろうかは、高さを見込む前に見る（table_h が列の幅を引く）
            self.table_check(e, loc)
        if kind == "gantt":
            self.gantt_check(e, loc)
        if kind == "bars":
            self.bars_check(e, loc)
        if kind == "card" and "shape" in e and "num" not in e:  # カードの shape は番号の形（カードの箱の形ではない）
            sys.exit(f"{loc}（card）.shape: 番号（num）の形なので、num を書いたカードで使う")
        if kind == "list":
            for i, it in enumerate(e["items"]):
                l = f"{loc}（list）.items[{i}]"
                if isinstance(it, dict):
                    spec_check(it, LIST_ITEM, l)
                    if len(ms := [k for k in ("icon", "num", "image") if k in it]) > 1:
                        sys.exit(f"{l}: 項目の印は icon・num・image のどれか 1 つ: {'・'.join(ms)}")
                it = {"text": it} if isinstance(it, str) else it
                if not (spec_plain(spec_md(it.get("text", ""))).strip() or it.get("head", "").strip()):  # 記法を外した文字で見る（"***  ***" は空白だけ）
                    sys.exit(f"{l}: text か head を書く（空の項目は印だけになる）")
                if spec_bullets(it.get("text", ""), l)[1]:  # 項目の本文は箇条書きにしない（「- 」がそのまま出る）
                    sys.exit(f"{l}: 項目の本文に箇条書き（- ）は書けない。項目を分けるか、card にする")
        if e.get("w") == "fit" and kind != "label":
            sys.exit(f"{loc}（{kind}）.w: \"fit\"（中身の幅）は label だけ")
        if in_frame and kind != "arrow" and ("x" not in e or "y" not in e or "w" not in e and kind not in NO_SIZE):
            sys.exit(f"{loc}（{kind}）: frame の中の部品には x・y{'・w' if kind not in NO_SIZE else ''} を書く（frame の左上からの in）")
        for i, c in enumerate(e.get("items", []) if kind in ("row", "stack", "grid", "frame") else []):
            if self.check(c, f"{loc}.items[{i}]", kind == "frame") == "arrow" and kind in ("row", "grid"):
                sys.exit(f"{loc}.items[{i}]: row・grid の中の矢印は、row の \"arrows\": true で引く")
        return kind

    @staticmethod
    def table_cols(e):
        """表の列の数（1 行目のセルの colspan の合計。1 行目の上には rowspan のセルがない）。"""
        return sum(c.get("colspan", 1) if isinstance(c, dict) else 1 for c in e["rows"][0])

    def table_cells(self, e, w, loc):
        """表の列の幅（in）と、Deck.table に渡す行（セルは dict）。記法は parts にし、「- 」で始まる段落だけのセルは箇条書きにする。
        塗り（セルの fill か、そのセルにかかる fills）が濃ければ、文字と ***強調*** の色を ON_FILL にする。見出しの行に淡い塗りを書いたら、文字は本文の色にする。"""
        n, nh = self.table_cols(e), int(e.get("header", True))
        ws = [w * r / sum(e["widths"]) for r in e["widths"]] if e.get("widths") else [w / n] * n
        grid, out = iter(table_grid(e["rows"], n)), []
        for i, row in enumerate(e["rows"]):
            out.append([])
            for j, src in enumerate(row):
                r, c, d = next(grid)
                l = f"{loc}（table）.rows[{i}][{j}]"
                fill = d.get("fill") or next((f for fr, fc, f in reversed(e.get("fills", [])) if fr in ("all", r + 1) and fc in ("all", c + 1)), None)
                if fill in ON_FILL:
                    on, emph = ON_FILL[fill]
                elif fill and r < nh:  # 見出しの行の淡い塗り
                    on, emph = "TEXT", "RED_TEXT"
                else:  # 文字の色は Deck.table の既定（見出しの行は白、1 列目は HEAD）
                    on, emph = None, "RED_ON_NAVY" if r < nh else "RED_TEXT"
                text, bul = spec_bullets(d["text"], l)
                cell = {"text": spec_md(text, spec_color(emph), l), "bullets": bul, **{k: d[k] for k in ("colspan", "rowspan", "align", "valign") if k in d}}
                if d.get("fill"):
                    cell["fill"] = spec_color(d["fill"])
                if color := d.get("color") or on:
                    cell["color"] = spec_color(color)
                out[-1].append(cell)
        return ws, out

    def table_check(self, e, loc):
        rows = e["rows"]
        for i, r in enumerate(rows):
            for j, c in enumerate(r):
                if isinstance(c, dict):
                    spec_check(c, TABLE_CELL, f"{loc}（table）.rows[{i}][{j}]")
        n = self.table_cols(e)
        if len(e.get("widths", [1] * n)) != n:
            sys.exit(f"{loc}（table）: widths の数（{len(e['widths'])}）が列の数（{n}。1 行目のセルの colspan の合計）と違う")
        try:
            grid = table_grid(rows, n)
        except ValueError as x:
            sys.exit(f"{loc}（table）.rows: {x}")
        covered = {(r + i, c + j) for r, c, d in grid for i in range(d.get("rowspan", 1)) for j in range(d.get("colspan", 1)) if i or j}
        if bad := [f for f in e.get("fills", []) if (f[0] - 1 if f[0] != "all" else None, f[1] - 1 if f[1] != "all" else None) in covered]:
            sys.exit(f"{loc}（table）.fills: {bad} は結合したセルが覆う位置（塗っても出ない）。結合したセルは、そのセルの fill に書く")
        if int(e.get("header", True)) > len(rows):
            sys.exit(f"{loc}（table）.header: 見出しの行の数（{int(e['header'])}）が行の数（{len(rows)}）より多い")
        if len(e.get("align", [None] * n)) != n:
            sys.exit(f"{loc}（table）: align の数が列の数（{n}）と違う")
        if isinstance(e.get("row_h"), list) and len(e["row_h"]) != len(rows):
            sys.exit(f"{loc}（table）.row_h: 行ごとに書くなら、行の数（{len(rows)}）だけ並べる")
        if bad := [f for f in e.get("fills", []) if f[0] != "all" and f[0] > len(rows) or f[1] != "all" and f[1] > n]:
            sys.exit(f"{loc}（table）.fills: 表にない行か列 {bad}（{len(rows)} 行 {n} 列。1 から数え、\"all\" はその列か行の全部）")

    def bars_check(self, e, loc):
        n = len(e["items"])
        if bad := [i for i in e.get("hot", []) if i > n]:
            sys.exit(f"{loc}（bars）.hot: 棒の数（{n}）より大きい番号 {bad}")
        if "line" in e:
            spec_check(e["line"], BARS_LINE, f"{loc}（bars）.line")
            if e.get("horizontal"):
                sys.exit(f"{loc}（bars）.line: 折れ線は縦の棒（時の流れ）だけに重ねる。横の棒には書けない")
            if len(e["line"]["values"]) != n:
                sys.exit(f"{loc}（bars）.line.values: 数の数（{len(e['line']['values'])}）が棒の数（{n}）と違う（items の順に 1 つずつ）")
        if "threshold" in e:
            spec_check(e["threshold"], BARS_THRESHOLD, f"{loc}（bars）.threshold")

    def gantt_check(self, e, loc):
        n = len(e["cols"])
        if bad := next((c for c in e["cols"] if re.search(r"\*\*|`|\]\(|<br>", c)), None):
            sys.exit(f"{loc}（gantt）.cols: ガントの列の名前には記法を書けない: {bad!r}")
        for i, r in enumerate(e["rows"]):
            l = f"{loc}（gantt）.rows[{i}]"
            spec_check(r, GANTT_ROW, l)
            if bad := next((r[k] for k in ("head", "note") if re.search(r"\*\*|`|\]\(|<br>", r.get(k, ""))), None):
                sys.exit(f"{l}: ガントの項目と補足には記法を書けない（改行は \\n）: {bad!r}")
            for j, b in enumerate(r.get("bars", [])):
                spec_check(b, GANTT_BAR, f"{l}.bars[{j}]")
                if not b["from"] <= b["to"] <= n:
                    sys.exit(f"{l}.bars[{j}]: from・to は 1〜{n}（cols の何列目か。両端を含む）で、from ≤ to")
                if b.get("text", "").count("\n") > 1:
                    sys.exit(f"{l}.bars[{j}].text: バーの文字は 2 行まで（1 行 5 字ほど。改行の位置は \\n で決める。slides-pages-010）")
            for j, m in enumerate(r.get("marks", [])):
                spec_check(m, GANTT_MARK, f"{l}.marks[{j}]")
                if not 1 <= m["at"] <= n + 1:
                    sys.exit(f"{l}.marks[{j}].at: 1〜{n + 1}（today と同じ。1 が 1 列目の左端、1.5 が 1 列目の中ほど）")
                if "\n" in m["text"]:
                    sys.exit(f"{l}.marks[{j}].text: 節目の言葉は 1 行（短い名前にし、詳しいことは補足の列に書く）")
                if re.search(r"\*\*|`|\]\(|<br>", m["text"]):  # 言葉は記法を解かずに描く（項目・補足と同じ）
                    sys.exit(f"{l}.marks[{j}].text: 節目の言葉には記法を書けない: {m['text']!r}")
        if "today" in e and not 1 <= e["today"] <= n + 1:
            sys.exit(f"{loc}（gantt）.today: 1〜{n + 1}（1 が 1 列目の左端、1.5 が 1 列目の中ほど）")

    def gantt_layout(self, e, w, loc):
        """ガントの列の幅、月の列の幅、表のセル（見出しの行と各行）、見出しの行の高さ、行の高さ（余りを足す前）、行ごとの (段の数, [(段, 何番目, バー)])。
        重なるバーは下の段に回す。行の高さは、段とセルの文字の高いほう。"""
        n, note = len(e["cols"]), any("note" in r for r in e["rows"])
        cw = min(G_COL, (w - G_HEAD - G_NOTE) / n) if note else (w - G_HEAD) / n
        if cw < G_COL_MIN:
            sys.exit(f"{loc}（gantt）: 列が多くて 1 列が {cw:.2f} in になる（{G_COL_MIN} in 以上。期間を分けるか、週を月にまとめる）")
        widths = [G_HEAD] + [cw] * n + ([w - G_HEAD - n * cw] if note else [])
        rows = [["", *e["cols"], *([""] if note else [])]] + [[r["head"], *[""] * n, *([r.get("note", "")] if note else [])] for r in e["rows"]]
        hs, lanes = [], []
        for r, cells in zip(e["rows"], rows[1:]):
            # バーと節目が占める [左, 右)（列の境目の位置。today と同じ数え方）。左から順に、空いたいちばん上の段に置く
            spans = [(b["from"], b["to"] + 1, j, b) for j, b in enumerate(r.get("bars", []))] + [(*self.gantt_mark(m, cw, n)[:2], j, m) for j, m in enumerate(r.get("marks", []))]
            ends, lane = [], []
            for a, z, j, o in sorted(spans, key=lambda t: t[0]):
                k = next((i for i, end in enumerate(ends) if end <= a + 1e-9), len(ends))
                ends[k:k + 1] = [z]
                lane.append((k, j, o))
            nl = max(len(ends), 1)
            hs.append(max(nl * G_BAR + (nl - 1) * G_LANE + 2 * G_PAD, table_h(widths, [cells], 11, 0.36, False)))
            lanes.append((nl, lane))
        return widths, cw, rows, table_h(widths, rows[:1], 11, 0.36, True), hs, lanes

    @staticmethod
    def gantt_mark(m, cw, n):
        """節目の印と言葉が占める [左, 右)（列の境目の位置）、言葉の幅（in）、言葉を印の左に置くか。言葉は印の右に置き、表の右端を越えるなら左に置く。"""
        tw = em_width(m["text"]) * 11 / 72 + 0.1
        side = (G_MARK / 2 + G_MARK_GAP + tw) / cw
        left = m["at"] + side > n + 1
        return (m["at"] - side, m["at"] + G_MARK / 2 / cw, tw, True) if left else (m["at"] - G_MARK / 2 / cw, m["at"] + side, tw, False)

    def gantt(self, e, x, y, w, h, loc):
        """[slides-component-025] ガント（過去の資料の gantt。slides-pages-010）: 表を格子にし（見出しの行に列の名前、1 列目に項目、月の間に縦の罫線）、バーを塗りの札（9pt。slides-visual-037）で重ね、
        節目に赤の菱形と 11pt の言葉（塗りのない文字なので 9pt にしない）を置き、today に赤の縦線を引く。バーの塗りは status から決める（GANTT_STATUS）。h が中身より大きければ（本文の最後のガント）、余りを行に等しく配り、バーは行の上下の中央に置く。"""
        widths, cw, rows, hd, hs, lanes = self.gantt_layout(e, w, loc)
        n = len(e["cols"])
        hs = [v + max(h - hd - sum(hs), 0) / len(hs) for v in hs]
        self.index.append((loc, " ".join(c for r in rows for c in r)))
        self.emit("table", loc, e, x=x, y=y, widths=widths, rows=rows, size=11, header=True, first_col=True, zebra=False, align=["left"] + ["center"] * n + ["left"] * (len(widths) - n - 1),
                  mono_cols=[], row_h=[hd] + hs, fills=[], vlines=(1, n))
        x0, top = x + G_HEAD, y + hd
        if "today" in e:  # バーの下に引く
            tx = x0 + (e["today"] - 1) * cw
            self.emit("arrow", f"{loc}.today", x1=tx, y1=top, x2=tx, y2=top + sum(hs), color=RED, head=False, weight=1.5)
        for i, ((nl, lane), rh) in enumerate(zip(lanes, hs)):
            by = top + (rh - nl * G_BAR - (nl - 1) * G_LANE) / 2
            for k, j, b in lane:
                ly = by + k * (G_BAR + G_LANE)
                if "at" in b:  # 節目
                    l, (a, _, tw, left) = f"{loc}.rows[{i}].marks[{j}]", self.gantt_mark(b, cw, n)
                    mx = x0 + (b["at"] - 1) * cw
                    if left and a < 1 - 1e-9:  # 左に回した言葉が 1 列目の左端を越える（右に置くときの a は印の左端なので見ない）
                        self.warns.append(f"{l}.text: 節目の言葉「{b['text']}」が表の月の列に収まらない見込み。短くする")
                    self.index.append((l, b["text"]))
                    self.emit("box", l, x=mx - G_MARK / 2, y=ly + (G_BAR - G_MARK) / 2, w=G_MARK, h=G_MARK, fill=spec_color("RED"), kind="DIAMOND")
                    self.emit("text", f"{l}.text", x=mx - G_MARK / 2 - G_MARK_GAP - tw if left else mx + G_MARK / 2 + G_MARK_GAP, y=ly, w=tw, h=G_BAR,
                              parts=b["text"], size=11, color=spec_color("TEXT"), align="END" if left else "START", valign="MIDDLE", spacing=100, edge=True)
                    continue
                l, status = f"{loc}.rows[{i}].bars[{j}]", b.get("status", "plan")
                fill, tbd = GANTT_STATUS[status], status == "tbd"
                on, emph = ("RED_TEXT", "RED_TEXT") if status == "hot" else ON_FILL.get(fill, ("TEXT", "RED_TEXT"))
                parts = spec_md(b.get("text", ""), spec_color(emph), l)
                self.index.append((l, spec_plain(parts)))
                bw = (b["to"] - b["from"] + 1) * cw - 2 * G_INSET
                if sum(est_lines(ln, bw - 2 * INSET, 9, bold=True) for ln in spec_plain(parts).split("\n")) > 2:  # バーの高さは 9pt の 2 行
                    self.warns.append(f"{l}.text: バーの文字が 3 行以上に折り返す見込み「{spec_plain(parts)}」。短くするか、\\n で 2 行に分ける（1 行 5 字ほど）")
                self.emit("text", l, x=x0 + (b["from"] - 1) * cw + G_INSET, y=ly, w=bw, h=G_BAR,
                          parts=parts, size=9, color=spec_color(on), bold=True, align="CENTER", valign="MIDDLE", spacing=100, fill=spec_color(fill),
                          line=SUB if tbd else None, dash=tbd)
            top += rh

    def bars(self, e, x, y, w, h, loc):
        """[slides-component-026] 1 系列の棒グラフ（visual.md の 5）。凡例と目盛りを置かず、棒の端に数字を書く（直接のラベル）。棒は NAVY、hot の棒は RED と赤の数字。
        縦の棒（既定）は、下に名前、棒の上に数字、下端に基準の線。横の棒（horizontal）は、左に名前、棒の右に数字、左端に基準の線。
        line（縦の棒だけ）は、棒の上の段に、棒と別の目盛りで SUB の折れ線を引き、点の上に数字を書く。何の数か（label）は段の左上。
        折れ線は棒と違い 0 から始めず、いちばん小さい数を段の下、いちばん大きい数を段の上にする（段が低いので、0 からだと動きが見えない。数は点に書く）。
        threshold は、棒と同じ目盛りで赤の点線を引き、縦の棒は線の右、横の棒は線の上に札を置く（札の場所は棒の場所から引く）。
        直線が棒の端の数字を通るときは、その数字を棒の中（白）に入れる（線の外に出すと、線を越えた数に見える）。棒が短くて入らなければ警告する。"""
        items, hot, line, th = e["items"], set(e.get("hot", [])), e.get("line"), e.get("threshold")
        top = max([v for _, v in items] + ([th["value"]] if th else [])) or 1  # 直線が棒より高ければ、直線が高さいっぱい
        fmt = lambda v, unit=e.get("unit", ""): f"{int(v) if float(v).is_integer() else v:,}" + (" " + unit.strip() if unit.strip() else "")  # 100.0 も 100 と書く  # 単位の前は 1 字空ける（" 分" と書いても空きを 2 つにしない）
        tl = th and " ".join(filter(None, (th.get("label", "").strip(), fmt(th["value"]))))  # 直線の札（「目標 90 分」）
        tw = th and em_width(tl) * 11 / 72 + 0.1
        self.index.append((loc, " ".join(f"{n} {fmt(v)}" for n, v in items) + (f" {tl}" if th else "")))
        bar = lambda i: spec_color("RED" if i in hot else "NAVY")

        def num(i, v, inside=False):  # 棒の端の数字。棒の中は白（赤の棒は ON_RED）、外は本文の色（赤の棒は RED_TEXT）
            plain, emph = ("WHITE", "ON_RED") if inside else ("TEXT", "RED_TEXT")
            return [(fmt(v), {"bold": True, "color": spec_color(emph if i in hot else plain)})]
        common, pad = dict(size=11, color=spec_color("TEXT"), spacing=100, edge=True), 11 / 72 + 0.02  # pad は棒の中の数字と棒の端の間（1 字分。slides-visual-027）
        thr = lambda **k: self.emit("arrow", f"{loc}.threshold", **k, color=RED, head=False, dash=True, weight=1.25)
        thl = lambda **k: self.emit("text", f"{loc}.threshold.label", **k, parts=[(tl, {"color": spec_color("RED_TEXT")})], **common)
        if e.get("horizontal"):
            lw = min(max(em_width(n) for n, _ in items) * 11 / 72 + 0.1, w * 0.35)
            vw = max(em_width(fmt(v), bold=True) for _, v in items) * 11 / 72 + 0.05
            y0 = y + (B_LABEL if th else 0)  # 直線の札の行
            x0, pw, rh = x + lw + 0.1, w - lw - vw - 0.2, (y + h - y0) / len(items)
            if rh < B_ROW - 1e-6:  # 棒の太さと 11pt の名前が 1 本の行に収まる高さ（札の行を引いた割り算の誤差は見ない）
                sys.exit(f"{loc}（bars）: h が小さくて 1 本の行が {rh:.2f} in になる（{B_ROW} in 以上。h を省くと 1 本 {B_ROW} in）")
            if pw < 1:
                sys.exit(f"{loc}（bars）: 棒を引く幅が {pw:.2f} in しかない（名前か数字が長い。短くするか、幅を広げる）")
            if th and tw > w:
                sys.exit(f"{loc}（bars）: 直線の札「{tl}」が幅 {w:.2f} in に収まらない（label を短くするか、幅を広げる）")
            tx = th and x0 + th["value"] / top * pw
            for i, (n, v) in enumerate(items, 1):
                cy, bl, l = y0 + (i - 1) * rh, v / top * pw, f"{loc}.items[{i - 1}]"
                if est_lines(n, lw, 11) > 1:  # 名前の列は本文の幅の 35% まで
                    self.warns.append(f"{l}: 棒の名前「{n}」が折り返す見込み（名前の列 {lw:.2f} in）。短くする")
                self.emit("text", f"{l}.name", x=x, y=cy, w=lw, h=rh, parts=n, align="END", valign="MIDDLE", **common)
                if bl > 0:
                    self.emit("box", l, x=x0, y=cy + (rh - B_BAR) / 2, w=bl, h=B_BAR, fill=bar(i), kind="RECTANGLE", title=BAR_MARK, alt=f"{n} {fmt(v)}")
                nw = em_width(fmt(v), bold=True) * 11 / 72
                if th and x0 + bl <= tx <= x0 + bl + 0.08 + nw:  # 直線が数字を通る
                    if bl < nw + 2 * pad:
                        self.warns.append(f"{l}: 直線（threshold）が数字「{fmt(v)}」に重なる見込み（棒が短くて数字を中に入れられない）")
                    else:
                        self.emit("text", f"{l}.value", x=x0 + bl - nw - pad - 0.1, y=cy, w=nw + 0.1, h=rh, parts=num(i, v, True), align="END", valign="MIDDLE", **common)
                        continue
                self.emit("text", f"{l}.value", x=x0 + bl + 0.08, y=cy, w=vw, h=rh, parts=num(i, v), valign="MIDDLE", **common)
            self.emit("arrow", f"{loc}.base", x1=x0, y1=y0, x2=x0, y2=y + h, color=RULE, head=False, weight=0.75)
            if th:
                thr(x1=tx, y1=y0, x2=tx, y2=y + h)
                thl(x=max(min(tx - tw / 2, x + w - tw), x), y=y, w=tw, h=B_LABEL - 0.04, align="CENTER", valign="BOTTOM")
            return
        lh = B_LINE + (B_LABEL if line.get("label") else 0) if line else 0  # 折れ線の段（何の数かの行を含む）
        pw = w - (tw + 0.08 if th else 0)  # 直線の札は棒の右に置く
        if th and pw < 1:
            sys.exit(f"{loc}（bars）: 直線の札「{tl}」を右に置くと、棒を引く幅が {pw:.2f} in しかない（label を短くするか、幅を広げる）")
        slot, ph = pw / len(items), h - 2 * B_LABEL - lh
        bw, base = min(slot * B_FILL, B_MAX), y + h - B_LABEL
        if ph < 0.5:
            sys.exit(f"{loc}（bars）: h が小さくて棒を引く高さが {ph:.2f} in しかない" + (f"（折れ線の段に {lh:.2f} in を使う。h を省くと棒の段は {B_H - 2 * B_LABEL} in）" if line else ""))
        ty = th and base - th["value"] / top * ph
        for i, (n, v) in enumerate(items, 1):
            sx, bh, l = x + (i - 1) * slot, v / top * ph, f"{loc}.items[{i - 1}]"
            if bad := [t for t, b in ((n, False), (fmt(v), True)) if est_lines(t, slot, 11, bold=b) > 1]:
                self.warns.append(f"{l}: 棒の名前か数字「{bad[0]}」が折り返す見込み（1 本の幅 {slot:.2f} in）。短くするか、横の棒（horizontal）にする")
            if bh > 0:
                self.emit("box", l, x=sx + (slot - bw) / 2, y=base - bh, w=bw, h=bh, fill=bar(i), kind="RECTANGLE", title=BAR_MARK, alt=f"{n} {fmt(v)}")
            vy, inside = base - bh - B_LABEL, False
            if th and vy <= ty <= base - bh:  # 直線が数字を通る
                if bh < B_LABEL + pad or em_width(fmt(v), bold=True) * 11 / 72 + 2 * INSET > bw:  # 白い数字は棒の塗りの中に収める（はみ出すと地の上で読めない。中央寄せなので左右は枠の余白だけ）
                    self.warns.append(f"{l}: 直線（threshold）が数字「{fmt(v)}」に重なる見込み（棒が低いか細くて数字を中に入れられない）")
                else:
                    vy, inside = base - bh + pad, True
            self.emit("text", f"{l}.value", x=sx, y=vy, w=slot, h=B_LABEL - 0.04, parts=num(i, v, inside), align="CENTER", valign="TOP" if inside else "BOTTOM", **common)
            self.emit("text", f"{l}.name", x=sx, y=base + 0.06, w=slot, h=B_LABEL - 0.06, parts=n, align="CENTER", **common)
        self.emit("arrow", f"{loc}.base", x1=x, y1=base, x2=x + pw, y2=base, color=RULE, head=False, weight=0.75)
        if th:
            thr(x1=x, y1=ty, x2=x + pw, y2=ty)
            thl(x=x + pw + 0.08, y=ty - B_LABEL / 2, w=tw, h=B_LABEL, valign="MIDDLE")
        if line:  # 点は、段の上の数字の行の下から、棒の段の B_LINE_GAP 上まで（いちばん高い棒の数字と離す）
            vals, lu = line["values"], line.get("unit", "")
            low, span, lo, hi = y + lh - B_LINE_GAP - B_DOT / 2, B_LINE - B_LABEL - B_LINE_GAP - B_DOT, min(vals), max(vals)
            pts = [(x + (i + 0.5) * slot, low - ((v - lo) / (hi - lo) if hi > lo else 0.5) * span) for i, v in enumerate(vals)]  # 数がみな同じなら段の中ほど
            self.index.append((f"{loc}.line", " ".join([line.get("label", "")] + [fmt(v, lu) for v in vals]).strip()))
            if line.get("label"):
                self.emit("text", f"{loc}.line.label", x=x, y=y, w=pw, h=B_LABEL - 0.04, parts=[(line["label"], {"color": SUB})], valign="BOTTOM", **common)
            for i, ((px, py), (qx, qy)) in enumerate(zip(pts, pts[1:])):
                self.emit("arrow", f"{loc}.line.seg[{i}]", x1=px, y1=py, x2=qx, y2=qy, color=SUB, head=False, weight=2)
            for i, ((px, py), v) in enumerate(zip(pts, vals)):
                l = f"{loc}.line.values[{i}]"
                if est_lines(fmt(v, lu), slot, 11, bold=True) > 1:
                    self.warns.append(f"{l}: 折れ線の数字「{fmt(v, lu)}」が折り返す見込み（1 本の幅 {slot:.2f} in）。単位を短くするか、幅を広げる")
                self.emit("box", l, x=px - B_DOT / 2, y=py - B_DOT / 2, w=B_DOT, h=B_DOT, fill=SUB, kind="ELLIPSE")
                self.emit("text", f"{l}.value", x=px - slot / 2, y=py - B_DOT / 2 - B_LABEL, w=slot, h=B_LABEL - 0.04, parts=[(fmt(v, lu), {"bold": True, "color": SUB})],
                          align="CENTER", valign="BOTTOM", **common)

    # ---- 大きさ ----
    def fixed_w(self, e):
        if e.get("w") == "fit":  # 札の幅を中身の文字に合わせる（左右に 1 字分）
            size = e.get("size", 11)
            mono, bold = e.get("mono", False), e.get("bold", e["type"] == "label")  # 札（Deck.label）は既定で太字
            return max(em_width(ln, mono, bold) for ln in spec_plain(spec_md(e["text"])).replace("\v", "\n").split("\n")) * size / 72 + 2 * size / 72 + 0.06
        return e.get("w") or (num_w(e["n"], e.get("size", "medium"), e.get("shape", "ellipse")) if e["type"] == "num" else e.get("size", 0.5) if e["type"] == "icon" else None)

    def slot_w(self, e, w):
        """縦に並べるときの幅。書いた幅か決まった幅、なければ並びの幅（超えない）。"""
        return min(self.fixed_w(e) or w, w)

    def widths(self, e, w, loc):
        items = [c for c in e["items"] if c.get("type") != "arrow"]
        gap = e.get("gap", GAP_ARROW if e.get("arrows") else GAP)
        if e["type"] == "grid":
            return [(w - gap * (e["cols"] - 1)) / e["cols"]] * len(items), gap
        free = w - gap * (len(items) - 1)
        if r := e.get("widths"):
            if len(r) != len(items):
                sys.exit(f"{loc}: widths の数（{len(r)}）が items の数（{len(items)}）と違う")
            return [free * x / sum(r) for x in r], gap
        fixed = [self.fixed_w(c) for c in items]
        flex, rest = sum(f is None for f in fixed), free - sum(f for f in fixed if f)
        if rest < 0 or flex and rest <= 0.3:
            sys.exit(f"{loc}: 幅が足りない（{w:.2f} in に、決まった幅の部品が {sum(f for f in fixed if f):.2f} in と間が {gap * (len(items) - 1):.2f} in）")
        return [f if f is not None else rest / flex for f in fixed], gap

    def rows_of(self, e):
        items = [c for c in e["items"] if c.get("type") != "arrow"]
        n = e["cols"] if e["type"] == "grid" else len(items)
        return [items[i:i + n] for i in range(0, len(items), n)]

    def measure(self, e, w, loc, least=False):
        """幅 w に置いたときの高さ（in）。least なら、文字（と印）が箱に収まる最小の高さ（見た目の余白と既定の下限を除く。h を書いて詰めてよい分。#52）。"""
        kind, size = e["type"], e.get("size", 11)
        if "h" in e and not least:  # frame は h が要る
            return e["h"]
        if kind in ("text", "label"):
            s, bul = spec_bullets(e["text"], f"{loc}（text）") if kind == "text" else (e["text"], False)
            boxed = kind == "label" or e.get("fill") or e.get("line")
            center = e.get("align", "center" if kind == "label" else "left") == "center"
            inner = max((size / 72 if e.get("pad") is None else e["pad"]) - INSET, 0) if boxed and not center and e.get("shape") != "ellipse" else 0  # Deck.text と同じ
            avail = (w - 2 * INSET - 2 * inner if boxed else w) - (size * 1.3 / 72 if bul else 0)
            body = spec_text_h(spec_md(s, loc=loc), avail, size, e.get("spacing"), e.get("para_gap", 0), e.get("mono", False), e.get("bold", kind == "label"))
            if least:  # 文字の枠の余白（INSET）だけを残す
                return body + 2 * INSET
            if kind == "label":
                return max(0.4, body + 2 * size / 72)
            return body + (2 * size / 72 + 0.1 if boxed else 0.02)  # 塗りか枠線があれば、上下に 1 字分（slides-visual-027）
        if kind == "card" and (self.mark(e) or self.dark_card(e, loc)):
            return self.marked(e, 0, 0, w, None, loc)["least" if least else "h"]
        if kind == "stat":
            parts, kw = self.stat_parts(e)
            inner = 0 if e.get("align") == "center" else STAT_PAD - INSET
            return spec_text_h(parts, w - 2 * INSET - 2 * inner, 11, 110, 2) + (2 * INSET if least else 2 * STAT_PAD + 0.1)
        if kind == "card":
            if "step" in e:
                return card_h(w, e.get("head"), items=[tuple(x) for x in e.get("items", [])], step=e["step"], least=least)
            body, bul = self.card_body(e, loc)  # card_h は本文をすべて 11pt で数えるので、文字ごとの大きさを見る spec_text_h で、d.card の本文の枠と同じ幅に見込む
            avail = w - 2 * PAD - 2 * INSET - (11 * 1.3 / 72 if bul else 0)
            return card_top(w, e.get("head")) + (spec_text_h(body, avail, 11, 125) + 2 * INSET if body else 0) + (0.1 if least else CARD_END)  # 本文の枠は下端の 0.1 in 上まで（d.card）
        if kind == "code":
            return sum(est_lines(ln, w - 0.4, size, True) for ln in e["text"].split("\n")) * size * 1.2 * 1.1 / 72 + 0.28
        if kind == "table":
            ws, rows = self.table_cells(e, w, loc)
            return table_h(ws, rows, size, e.get("row_h", 0.36), e.get("header", True), [c - 1 for c in e.get("mono_cols", [])], e.get("first_col", True))
        if kind == "gantt":
            _, _, _, hd, hs, _ = self.gantt_layout(e, w, loc)
            return hd + sum(hs)
        if kind == "bars":
            if e.get("horizontal"):
                return len(e["items"]) * B_ROW + (B_LABEL if "threshold" in e else 0)  # 直線の札の行
            return B_H + (B_LINE + (B_LABEL if e["line"].get("label") else 0) if "line" in e else 0)  # 折れ線の段
        if kind == "image":
            src = self.src(e, loc)
            if src.startswith("http") or not (r := image_ratio(src)):
                sys.exit(f"{loc}（image）: 画像の縦横の比が分からないので h を書く（URL の画像と、読めない形式の手元の画像）")
            return w / r
        if kind == "num":  # 角丸の番号は幅と高さが違う
            return NUM[e.get("size", "medium")][0]
        if kind == "icon":
            return self.fixed_w(e)
        if kind == "list":
            rows = self.list_rows(e, w, loc)
            return sum(r[-1] for r in rows) + e.get("gap", LIST_GAP) * (len(rows) - 1)
        if kind == "box":
            return 0
        if kind == "stack":
            hs = [self.measure(c, self.slot_w(c, w), f"{loc}.items[{i}]") for i, c in enumerate(e["items"]) if c["type"] != "arrow"]
            return sum(hs) + e.get("gap", GAP) * max(len(hs) - 1, 0)
        ws, gap = self.widths(e, w, loc)
        it = iter(ws)
        return sum(max(self.measure(c, next(it), loc) for c in row) for row in self.rows_of(e)) + gap * (len(self.rows_of(e)) - 1)

    def list_rows(self, e, w, loc):
        """list の項目ごとの (場所, 印の種類, 印, 見出しの parts, 本文の parts, 見出しの高さ, 本文の高さ, 文字の上端, 印の上端, 項目の高さ)。上端は項目の上端から。
        印の中心を 1 行目（見出しがあればその行）の中心にそろえる。2 行目からは文字の左端にそろえて下げ、印は 1 行目の横に残る。
        印は list_marks、文字の左端は印の列（list_mark_w）の右。"""
        d, emph = NUM[e.get("size", "medium")][0], spec_color(ON_FILL.get(self.bg, ("TEXT", "RED_TEXT"))[1])
        marks = self.list_marks(e)
        mw = self.list_mark_w(e, marks)
        tw, out = w - mw - MARK_GAP, []
        if tw <= 0.3:
            sys.exit(f"{loc}（list）: 幅が足りない（{w:.2f} in に、印 {mw:.2f} in と間 {MARK_GAP} in）")
        for i, (it, (kind, v)) in enumerate(zip(e["items"], marks)):
            it, l = {"text": it} if isinstance(it, str) else it, f"{loc}.items[{i}]"
            head = [(it["head"], {"bold": True, "size": 12})] if it.get("head", "").strip() else []  # 空白だけの見出しは置かない（check と同じ見方）
            body = spec_md(it.get("text", ""), emph, l)
            body = body if spec_plain(body).strip() else []  # 記法を外して空白だけの本文は置かない（check と同じ見方）
            hh = spec_text_h(head, tw, 12, 100) if head else 0
            bh = spec_text_h(body, tw, 11) if body else 0
            first = (12 if head else first_pt(body, 11, tw)) * 1.2 / 72  # 1 行目の高さ。2 行以上の行間 125% は 1 行目の下に足される（2026-10-20 に Google が描いた画像で測った。125% で見込むと 3.5 px 上に出た）
            ty, my = max((d - first) / 2, 0), max((first - d) / 2, 0)
            out.append((l, kind, v, head, body, hh, bh, ty, my, max(my + d, ty + hh + (HEAD_GAP if head and body else 0) + bh)))
        return out

    @staticmethod
    def list_marks(e):
        """list の項目ごとの (印の種類, 印)。印を書かない項目は、list の icon か、start から項目の順で数えた番号。整数の番号は digits の桁まで 0 で埋める。"""
        out = []
        for i, it in enumerate(e["items"]):
            it = it if isinstance(it, dict) else {}
            m = next((k for k in ("icon", "num", "image") if k in it), None)  # 印が 2 つ以上の項目は check が止めている
            kind, v = (m, it[m]) if m else ("icon", e["icon"]) if "icon" in e else ("num", e.get("start", 1) + i)
            out.append((kind, f"{v:0{e['digits']}d}" if kind == "num" and isinstance(v, int) and "digits" in e else v))
        return out

    @staticmethod
    def list_mark_w(e, marks):
        """list の印の列の幅。いちばん広い印（角丸の 2 桁の番号など）に合わせ、各印は列の中央に置く（本文の左端がそろう）。"""
        size, shape = e.get("size", "medium"), e.get("shape", "ellipse")
        return max(num_w(v, size, shape) if kind == "num" else NUM[size][0] for kind, v in marks)

    def list(self, e, x, y, w, loc):
        dark = self.bg in ON_FILL
        on = spec_color(ON_FILL[self.bg][0] if dark else "TEXT")
        size = e.get("size", "medium")
        d, mw = NUM[size][0], self.list_mark_w(e, self.list_marks(e))
        tx, tw, mx = x + mw + MARK_GAP, w - mw - MARK_GAP, x + (mw - d) / 2  # mx はアイコン・画像の左端（列の中央に置く）
        for l, kind, v, head, body, hh, bh, ty, my, ih in self.list_rows(e, w, loc):
            self.index.append((l, spec_plain(head) + spec_plain(body)))
            if kind == "num":
                self.emit("num", f"{l}.num", n=v, cx=x + mw / 2, cy=y + my + d / 2, size=size, fill=RED,
                          **({"shape": e["shape"]} if "shape" in e else {}))  # 地によらず赤（印のあるカードと同じ）
            elif kind == "icon":
                self.emit("icon", f"{l}.icon", name=v, x=mx, y=y + my, size=d, color=hex_of(spec_color(e.get("color")) if "color" in e else on))
            else:
                self.emit("image", f"{l}.image", src=self.src({"src": v}, l), x=mx, y=y + my, w=d, h=d, alt=spec_plain(head or body))
            if head:
                self.emit("text", f"{l}.head", x=tx, y=y + ty, w=tw, h=max(hh, 0.2), parts=head, size=12, color=on if dark else spec_color("HEAD"), spacing=100, edge=True)
            if body:  # 見出しがあれば、本文は灰色の補足
                self.emit("text", f"{l}.text", x=tx, y=y + ty + hh + (HEAD_GAP if head else 0), w=tw, h=max(bh, 0.2), parts=body, size=11,
                          color=spec_color(("SUB_ON_NAVY" if dark else "SUB") if head else on), edge=True)
            y += ih + e.get("gap", LIST_GAP)

    def mark(self, e):
        """カードの印（icon・num・image のどれか）。2 つ以上なら止める。"""
        ms = [k for k in ("icon", "num", "image") if k in e]
        if len(ms) > 1:
            sys.exit(f"カードの印は icon・num・image のどれか 1 つ: {'・'.join(ms)}")
        return ms[0] if ms else None

    def dark_card(self, e, loc):
        """濃い地（NAVY など）の印のないカード。d.card は見出しと本文の色を地で替えないので、印のあるカードと同じく marked で組む（印なし）。"""
        if e.get("fill") not in ON_FILL:
            return False
        if "step" in e:
            sys.exit(f"{loc}（card）: 濃い地（{e['fill']}）のカードに step は使えない（文字の色を地に合わせられない）。地を CARD・PANEL にするか、step を外す")
        return True

    def marked(self, e, x, y, w, h, loc):
        """印のあるカード。印を左（align left）か上の中央（center）に置き、見出し（太字 12pt）と本文を横か下に置く。h が None なら置かずに高さ（と、文字と印が収まる最小の高さ least）を返す。
        中身は枠の上下の中央に置き、伸ばされたカードと valign top は上寄せにする。横に置く印は 1 行目にそろえる。valign middle は、伸ばされても上下の中央にし、印も文字の中央に置く（構成図の箱など）。"""
        m, fill = self.mark(e), e.get("fill", "CARD")
        on, emph = (spec_color(c) for c in ON_FILL.get(fill, ("TEXT", "RED_TEXT")))
        size = 0 if m is None else MARK_IMG if m == "image" else MARK  # 印のない濃い地のカード（dark_card）は印の場所を取らない
        mw = num_w(e["num"], "medium", e.get("shape", "ellipse")) if m == "num" else size  # 印の幅（角丸の 2 桁の番号は高さより広い）
        center, valign = e.get("align") == "center", e.get("valign")
        if center and valign == "middle":
            sys.exit(f"{loc}（card）: 印を上に置く align center と、valign middle は一緒に使えない")
        body, bul = self.card_body(e, loc, emph)
        head = [(e["head"], {"bold": True, "size": 12, "color": spec_color("WHITE" if fill in ON_FILL else "HEAD")})] if e.get("head") else []
        tw = w - 2 * MARK_IN if center or m is None else w - 2 * MARK_IN - mw - MARK_GAP
        hh = spec_text_h(head, tw, 12, 100) if head else 0  # 見出しと本文は別の枠（箇条書きが見出しに付かないように。d.card と同じ）
        bh = spec_text_h(body, tw - (11 * 1.3 / 72 if bul else 0), 11, 125) if body else 0
        th = hh + (HEAD_GAP if head and body else 0) + bh
        # 中身（印と文字）は、上下の空きが同じに見える位置に置く。横に置く印と枠の間は MARK_IN
        start, end = MARK_TOP - (0.05 if center else 0), MARK_END + (0.03 if bh > 0.3 else 0)
        content = size + (MARK_GAP + th if th else 0) if center else th
        # 横に置く印は、文字の量によらず、印の中心を 1 行目（見出しの 12pt か、見出しがなければ本文の 1 行目のいちばん大きな文字。list と同じ）の中心にそろえる。
        # 置き方（row・grid・frame・stack）によらず、隣のカードと印の高さがそろう（2026-10-20 の p18。frame に 1 枚ずつ置いたカードで、短い文字を中央に置くと番号がずれた）
        first = (12 if head or not body else first_pt(body, 11, tw - (11 * 1.3 / 72 if bul else 0))) * 1.2 / 72
        # 印の上端の、文字の上端からの位置。本文の最終行の下には行間の空き（MARK_TOP と MARK_END の差）があるので、文字の上下の中央はその半分だけ上（2026-10-20 の画像で 0.033 in 下に見えた）
        mark = 0 if center else ((th - (MARK_TOP - MARK_END if body else 0) if valign == "middle" else first) - size) / 2
        lo, hi = min(mark, 0), max(content, mark + size)  # 印と文字を合わせた範囲の上端と下端（文字の上端から）
        if not th:  # 文字のない、印だけのカードは、印の上下を MARK_IN にする
            start = end = MARK_IN - lo
        # 印が文字より上に出るなら、印の下も上と同じだけ空ける（valign middle は枠の中央に置くので MARK_IN）
        need = start + content + end if center else max(start + th + end, size + 2 * (MARK_IN if valign == "middle" else start + lo))
        # 文字の上は、どのカードも start に置く（行数や印の違うカードを並べても見出しの高さがそろう）。row・grid で隣に合わせて伸ばされたカードも同じで、上寄せになる
        top = valign == "top" or valign is None and h is not None and h > need - 0.01
        if h is None:  # least は印と文字が収まる最小（上寄せは、上の空きも）
            return {"h": need, "least": start + hi if valign == "top" else hi - lo}
        # h を書いて高くしたカードは上寄せになる。中身（印と文字）がカードの半分までの低さなら、下だけが空いて見えるので middle を勧める。
        # 行数ではなく高さで見る（文字の大きさと印の大きさで変わる）。row・grid で隣に合わせて伸ばされたカードは、見出しの高さをそろえるので出さない
        if not center and valign is None and "h" in e and h - need >= 0.1 and hi - lo <= h / 2:
            self.warns.append(f"{loc}（card）: 中身の高さ {hi - lo:.2f} in がカードの高さ {h:.2f} in の半分までで、上寄せのため下が上より {h - need:.2f} in 広く空く。"
                              "\"valign\": \"middle\" にするか、h を外して中身に合わせる（隣のカードと見出しの高さをそろえるなら \"valign\": \"top\" を書く）")
        self.index.append((loc, spec_plain(head) + spec_plain(body or "")))
        self.emit("card", loc, e, x=x, y=y, w=w, h=h, fill=spec_color(fill), line=spec_color(e.get("line", "RULE" if fill == "CARD" else None)))
        mx = x + (w - mw) / 2 if center else x + MARK_IN
        # 印と文字を合わせた範囲の上端（枠の上端から）。valign middle は枠のちょうど中央（構成図の箱。矢印は箱の辺の中央に付く）。
        # h を書いて中身より低くしたカードは、上下の空きの比を保って縮める（h が need なら、文字の上は start）
        if top:
            uy = start + lo
        elif valign == "middle":
            uy = (h - hi + lo) / 2
        else:
            gap_top, gap_end = start + lo, need - start - hi
            uy = (h - hi + lo) * gap_top / (gap_top + gap_end)
        cy = y + uy - lo  # 文字の上端（上に印を置くカードは、印の上端）
        ty = cy + size + MARK_GAP if center else cy
        my = cy + mark
        if m is None:
            pass
        elif m == "icon":
            self.emit("icon", f"{loc}.icon", name=e["icon"], x=mx, y=my, size=size, color=hex_of(on))
        elif m == "num":
            self.emit("num", f"{loc}.num", n=e["num"], cx=mx + mw / 2, cy=my + size / 2, size="medium", fill=RED,
                      **({"shape": e["shape"]} if "shape" in e else {}))  # 地によらず赤（数字は ON_RED）
        else:
            self.emit("image", f"{loc}.image", src=self.src({"src": e["image"]}, loc), x=mx, y=my, w=size, h=size, alt=e.get("head"))
        tx = x + MARK_IN if center or m is None else mx + mw + MARK_GAP
        align = "CENTER" if center else "START"
        if head:
            self.emit("text", f"{loc}.head", x=tx, y=ty, w=tw, h=max(hh, 0.2), parts=head, size=12, color=on, spacing=100, edge=True, align=align)
        if body:
            self.emit("text", f"{loc}.text", x=tx, y=ty + hh + (HEAD_GAP if head else 0), w=tw, h=max(bh, 0.2), parts=body, size=11, color=on, spacing=125,
                      edge=True, bullets=bul, align=align)

    def stat_parts(self, e):
        """数字の強調（過去の資料の stat・bignum）: 大きな数字（size、既定 32pt の太字）と単位（半分の大きさ）、何の数か（太字 12pt）、補足（SUB）。"""
        fill = e.get("fill", "CARD")
        dark = fill in ON_FILL
        num = spec_color(e.get("color", ON_FILL[fill][1] if dark else "RED_TEXT"))
        vs = e.get("size", 32)
        parts = [(e["value"], {"size": vs, "bold": True, "color": num})] + ([(" " + e["unit"], {"size": round(vs / 2), "bold": True, "color": num})] if e.get("unit") else [])
        parts += [("\n" + e["label"], {"size": 12, "bold": True, "color": spec_color("WHITE" if dark else "HEAD")})] if e.get("label") else []
        parts += [("\n" + e["sub"], {"color": spec_color("SUB_ON_NAVY" if dark else "SUB")})] if e.get("sub") else []
        return parts, dict(fill=spec_color(fill), line=spec_color(e.get("line", "RULE" if fill == "CARD" else None)), color=spec_color(ON_FILL[fill][0] if dark else "TEXT"))

    def card_body(self, e, loc, emph=RED_TEXT):
        if e.get("text") and e.get("items"):
            sys.exit(f"{loc}（card）: text と items はどちらか 1 つ")
        if any(not b.strip() for _, b in e.get("items", [])):  # 2026-10-16 の sandbox で、説明のない項目を並べて、太字の項目の間が空いた
            sys.exit(f"{loc}（card）: items に説明のない項目がある。見出しと説明の組でないなら、text の箇条書き（- ）にする")
        if e.get("items"):  # d.card の items と同じ形（見出しは太字、項目の間に空行）を、記法つきで作る
            parts = []
            for i, (h2, b) in enumerate(e["items"]):
                b = spec_md(b, loc=loc)
                parts += [(h2 + "\n", {"bold": True}), *([b] if isinstance(b, str) else b), *(["\n\n"] if i < len(e["items"]) - 1 else [])]
            return parts, False
        s, bul = spec_bullets(e.get("text", ""), f"{loc}（card）")
        return (spec_md(s, emph, loc) if s else None), bul

    def src(self, e, loc):
        s = e["src"]
        if s.startswith("asset:"):
            return asset(s[6:])
        if re.match(r"https?://", s):
            return png(s) if re.search(r"\.svg($|[?#])", s, re.I) else s
        path = (self.base / s).resolve()  # 手元の画像は、JSON のファイルのあるフォルダから。組むとき（build の carry）に上げる
        if not path.is_file():
            sys.exit(f"{loc}（image）: 画像がない: {path}")
        return str(path)

    # ---- 置く ----
    def flow(self, items, x, y, w, gap, loc, frame=None):
        """items を上から順に gap を空けて並べ、下端を返す。frame（frame の高さ）を渡すと、部品の x・y を (x, y) からの位置にし、frame の幅 w と高さに収まるかを見る。
        矢印は場所を取らず、ほかの部品を置き終えてから引く（[x, y] の端は (x, y) からの位置）。"""
        origin, bottom, spans, arrows = (x, y), y, [], False
        for i, e in enumerate(items):
            l = f"{loc}[{i}]"
            if self.check(e, l, frame is not None) == "arrow":
                self.arrows.append((e, l, origin, (w, frame) if frame else None))
                arrows = True
                continue
            ew = self.fixed_w(e) if frame else self.slot_w(e, w)
            eh = self.measure(e, ew, l)
            if e["type"] == "gantt" and loc == self.body and all(c.get("type") == "arrow" for c in items[i + 1:]) and self.room:  # 矢印は場所を取らない  # 本文の最後のガントは、余った高さを行に配る（slides-pages-010）
                eh += min(G_GROW * len(e["rows"]), max(self.room - y - eh, 0))
            if frame and (e["x"] + ew > w + 0.01 or e["y"] + eh > frame + 0.01):  # frame の外に描くと、ページの下端の見込みにも入らない
                sys.exit(f"{l}（{e['type']}）: frame の外に出る（ページの左上から、部品は右端 {x + e['x'] + ew:.2f} in・下端 {y + e['y'] + eh:.2f} in、"
                         f"frame は右端 {x + w:.2f} in・下端 {y + frame:.2f} in）")
            self.place(e, x + e["x"] if frame else x, y + e["y"] if frame else y, ew, eh, l)
            if frame:
                spans.append((e["y"], e["y"] + eh))
            else:
                bottom = y + eh
                y = bottom + gap
        if frame and arrows and len(spans) >= 3 and max(a for a, _ in spans) < min(b for _, b in spans):  # どの部品も同じ高さの帯にかかる = 横 1 列
            self.warns.append(f"{loc}: 横 1 列に並べて矢印でつないだ図は、row の \"arrows\": true に印のあるカードか label を並べて書ける（幅を本文いっぱいに使い、"
                              "高さと矢印の位置がそろう。../pages.md の slides-pages-034 の「Free-form diagrams」）")
        return bottom

    def lone_text(self):
        """塗りの箱の中に、ほかの部品がなく、塗りのない文字が 1 つだけ入っていたら止める（札は図形と文字を 1 つにする。角丸と箱の端と文字の間がそろう。
        visual.md の 4。2026-10-16 の sandbox で、構成図の箱を box と text を重ねて組んでいた）。見出しとカードを入れた囲みは、ほかの部品が入るので通る。"""
        for kind, loc, r, filled, _, _ in self.placed:
            if filled and len(ins := [p for p in self.placed if p[1] != loc and rect_in(p[2], r)]) == 1 and ins[0][4]:
                sys.exit(f"{ins[0][1]}（text）: {loc} の塗りの箱の中に、文字だけを重ねた。塗りの箱と文字は、1 つの label か、fill のある text にする（アイコンも置くなら印のあるカード）")

    def place(self, e, x, y, w, h, loc):
        kind = e["type"]
        if kind in ("icon", "num"):  # 決まった大きさで置く。grid や比で分けた row の列の幅に広げない（measure と同じ大きさ）
            w, h = self.fixed_w(e), self.measure(e, 0, loc)
        if (i := e.get("id")) is not None:
            if i in self.ids:
                sys.exit(f"{loc}: id「{i}」が 2 つある")
            self.ids[i], self.id_loc[i] = (x, y, w, h), loc
            # つなぐのは、文字の枠が見える箱と同じ大きさの四角になる部品だけ（接続点は四角の辺の中央。SITE）。楕円や矢羽根の図形と、
            # 左寄せ・右寄せの塗りの文字・札・数字の強調（Deck.text が文字の枠を箱の内に縮める）はつながない。矢印の先が箱の中に出る。
            # 番号（num）は文字の枠が円より広い（Deck.text の ring）ので、CONNECT に入れない
            center = e.get("align", "center" if kind == "label" else "left") == "center"
            shrink = kind in ("text", "label", "stat") and not center and (kind == "stat" or e.get("pad") is None or e["pad"] > INSET)
            if kind in CONNECT and (kind != "text" or e.get("fill") or e.get("line")) and (kind not in OUTLINE or e.get("shape", "rectangle") in ("rectangle", "round_rectangle")) and not shrink:
                self.anchors[i] = loc
        fill = e.get("fill")
        ground = fill or (self.bg if kind == "text" else None)  # 文字の下の地。塗りのない文字（枠線だけの箱も）はページの地
        on, emph = (spec_color(c) for c in ON_FILL.get(ground, ("TEXT", "RED_TEXT")))
        if kind not in ("row", "stack", "grid", "frame"):
            self.placed.append((kind, loc, (x, y, w, h), kind == "box" and bool(fill), kind == "text" and not (fill or e.get("line")), e))
        if "h" in e and (kind in ("card", "stat", "label") or kind == "text" and (fill or e.get("line"))):  # 書いた h は中身を見ずに使うので、収まらなくても組んだ画像まで分からない（#52）
            if (need := self.measure(e, w, loc, least=True)) > e["h"] + 0.05:  # 文字の高さは見積もりなので 0.05 in まで許す
                full = self.measure({k: v for k, v in e.items() if k != "h"}, w, loc)
                self.warns.append(f"{loc}（{kind}）: h {e['h']} in では中身が収まらない見込み（中身に要る高さ {need:.2f} in。h を省くと {full:.2f} in）。h を外すか、文字を短くする")
        if e.get("shape") == "rectangle" and (fill or kind == "label"):
            self.warns.append(f"{loc}: 塗りの箱を四角（shape: rectangle）にした。塗りの箱は、書かなければ角丸（visual.md の 4）。四角にする理由がなければ shape を外す")
        if kind in ("text", "label"):
            s, bul = spec_bullets(e["text"], f"{loc}（text）") if kind == "text" else (e["text"], False)
            parts = spec_md(s, emph, loc)
            self.index.append((loc, spec_plain(parts)))
            kw = dict(size=e.get("size", 11), color=spec_color(e.get("color", "HEAD" if kind == "label" and not fill else on)),
                      align=ALIGN[e.get("align", "center" if kind == "label" else "left")], mono=e.get("mono", False),
                      fill=spec_color(fill or ("PANEL" if kind == "label" else None)),
                      **{k2: e[k] for k, k2 in (("bold", "bold"), ("pad", "pad"), ("radius", "radius"), ("spacing", "spacing"), ("para_gap", "gap")) if k in e})
            if kind == "label":
                return self.emit("label", loc, e, x=x, y=y, w=w, h=h, v=parts, **kw)
            boxed = fill or e.get("line")
            return self.emit("text", loc, e, x=x, y=y, w=w, h=h, parts=parts, line=spec_color(e.get("line")), bullets=bul, edge=not boxed,
                             valign=VALIGN[e.get("valign", "middle" if boxed else "top")], dash=e.get("dash", False), weight=e.get("weight"),
                             **({"kind": SHAPES[e["shape"]]} if "shape" in e else {}), **kw)
        if kind == "card" and (self.mark(e) or self.dark_card(e, loc)):
            return self.marked(e, x, y, w, h, loc)
        if kind == "stat":
            parts, kw = self.stat_parts(e)
            self.index.append((loc, spec_plain(parts)))
            return self.emit("text", loc, e, x=x, y=y, w=w, h=h, parts=parts, size=11, valign="MIDDLE", spacing=110, gap=2, pad=STAT_PAD,
                             align=ALIGN[e.get("align", "left")], **kw)
        if kind == "card":
            if (e.get("align") or e.get("valign")) and not self.mark(e):
                sys.exit(f"{loc}（card）: align・valign は、印（icon・num・image）のあるカードで使う")
            colors = dict(fill=spec_color(e.get("fill", "CARD")), line=spec_color(e.get("line", "RULE" if e.get("fill", "CARD") == "CARD" else None)))
            if "step" in e:  # 項目を決まった間隔で置く（左右のカードで項目の上端をそろえる）。d.card の items のまま渡すので、記法は書けない
                if not e.get("items") or any(re.search(r"\*\*|\]\(|<br>|\{\d", b) for _, b in e["items"]):
                    sys.exit(f"{loc}（card）: step は items と使い、items に記法を書かない")
                self.index.append((loc, (e.get("head") or "") + "".join(a + b for a, b in e["items"])))
                return self.emit("card", loc, e, x=x, y=y, w=w, h=h, head=e.get("head"), items=[tuple(i) for i in e["items"]], step=e["step"], **colors)
            body, bul = self.card_body(e, loc)
            self.index.append((loc, (e.get("head") or "") + spec_plain(body or "")))
            return self.emit("card", loc, e, x=x, y=y, w=w, h=h, head=e.get("head"), body=body, bullets=bul, **colors)
        if kind == "code":
            self.index.append((loc, e["text"]))
            return self.emit("code", loc, e, x=x, y=y, w=w, h=h, lines=e["text"].split("\n"), hot=[n - 1 for n in e.get("hot", [])], size=e.get("size", 11))
        if kind == "table":
            ws, rows = self.table_cells(e, w, loc)
            self.index.append((loc, " ".join(spec_plain(c["text"]) for r in rows for c in r)))
            return self.emit("table", loc, e, x=x, y=y, widths=ws, rows=rows, size=e.get("size", 11), header=e.get("header", True), first_col=e.get("first_col", True),
                             zebra=e.get("zebra", True), align=e.get("align"), valign=e.get("valign", "middle"), borders=e.get("borders", "rows"),
                             mono_cols=[c - 1 for c in e.get("mono_cols", [])], row_h=e.get("row_h", 0.36),
                             fills=[(None if r == "all" else r - 1, None if c == "all" else c - 1, spec_color(col)) for r, c, col in e.get("fills", [])])
        if kind == "image":
            return self.emit("image", loc, e, src=self.src(e, loc), x=x, y=y, w=w, h=h, alt=e.get("alt"))
        if kind == "icon":
            return self.emit("icon", loc, e, name=e["name"], x=x, y=y, size=w, color=hex_of(spec_color(e.get("color", "TEXT"))))
        if kind == "num":
            return self.emit("num", loc, e, n=e["n"], cx=x + w / 2, cy=y + h / 2, size=e.get("size", "medium"), fill=spec_color(e.get("fill", "RED")),
                             **({"shape": e["shape"]} if "shape" in e else {}))
        if kind == "box":
            if h <= 0:
                sys.exit(f"{loc}（box）: h がない（row・grid の中なら行の高さになる）")
            return self.emit("box", loc, e, x=x, y=y, w=w, h=h, fill=spec_color(fill), line=spec_color(e.get("line")), dash=e.get("dash", False), weight=e.get("weight"),
                             **({"kind": SHAPES[e["shape"]]} if "shape" in e else {}), **({"radius": e["radius"]} if "radius" in e else {}))
        if kind == "gantt":
            return self.gantt(e, x, y, w, h, loc)
        if kind == "list":
            return self.list(e, x, y, w, loc)
        if kind == "bars":
            return self.bars(e, x, y, w, h, loc)
        if kind == "frame":
            return self.flow(e["items"], x, y, w, 0, f"{loc}.items", frame=h)
        if kind == "stack":
            return self.flow(e["items"], x, y, w, e.get("gap", GAP), f"{loc}.items")
        # row・grid: 列の幅を決め、行ごとに高さをそろえる
        if any({c["type"] for c in r} & {"num", "icon"} and any(c["type"] == "text" and not (c.get("fill") or c.get("line")) for c in r) for r in self.rows_of(e)):  # 塗りか枠線のある文字は行の高さまで伸びる  # 2026-10-20 の sandbox で、row の上端そろえで文字が円の中心より上に出た
            self.warns.append(f"{loc}（{kind}）: 番号かアイコンと文字を同じ行に並べた（{kind} は上端をそろえるので、文字が印の中心より上に出る）。印と文字の並びは list にする")
        ws, gap = self.widths(e, w, loc)
        if kind == "row" and not e.get("arrows") and max(ws) - min(ws) < 0.01:  # 同じ形の列（slides-visual-024）。grid は矢印を引けず、列を等分にするので、そのまま grid に移せる row にだけ勧める
            cols = [[t for t in c["items"] if t["type"] != "arrow"] for c in e["items"] if c.get("type") == "stack"]
            shapes = [[t["type"] for t in c] for c in cols]
            if len(cols) == len(ws) > 1 and len(shapes[0]) > 1 and all(s == shapes[0] for s in shapes):
                hs = [[self.measure(t, self.slot_w(t, cw), loc) for t in c] for c, cw in zip(cols, ws)]
                if any(max(h[i] for h in hs) - min(h[i] for h in hs) > 0.03 for i in range(len(shapes[0]) - 1)):  # 最後の段は上端がそろえばよい
                    self.warns.append(f"{loc}（row）: 同じ形の stack を並べたが、段の高さがそろわず、下の段の上端がずれる。段の順に grid（cols: {len(cols)}）に並べる"
                                      "（grid は行ごとに高さをそろえる。../visual.md の slides-visual-024）")
        it, cy, k = iter(ws), y, 0
        for row in self.rows_of(e):
            cw = [next(it) for _ in row]
            hs = [self.measure(c, cw[j], f"{loc}.items[{k + j}]") for j, c in enumerate(row)]
            rh = max(hs)
            grow = ["h" not in c and (c["type"] in STRETCH or c["type"] == "text" and (c.get("fill") or c.get("line"))) for c in row]
            cx = x
            for j, c in enumerate(row):
                l = f"{loc}.items[{k + j}]"
                self.place(c, cx, cy, cw[j], rh if grow[j] else hs[j], l)
                if e.get("arrows") and j < len(row) - 1:
                    self.emit("arrow", f"{loc}.arrows[{k + j}]", x1=cx + cw[j] + ARROW_PAD, y1=cy + rh / 2, x2=cx + cw[j] + gap - ARROW_PAD, y2=cy + rh / 2)
                cx += cw[j] + gap
            k += len(row)
            cy += rh + gap

    def link(self, e, loc, origin, bounds=None):
        """ID か [x, y] の両端から矢印を引く。ID なら、箱の向き合う辺の間に、重なる範囲の中央で引く（slides-visual-025）。
        "<id>.<辺>" で両端の辺を指すと、その辺の中央どうしを結ぶ（直交する辺は 1 回、向き合う辺は 2 回折れる）。"""
        def split(v, k):  # "<id>.<辺>" を id と辺に分ける。id そのものに . が入っていれば、そのまま id
            if not isinstance(v, str) or v in self.ids or "." not in v:
                return v, None
            i, side = v.rsplit(".", 1)
            if side not in SITE:
                sys.exit(f"{loc}（arrow）.{k}: 「{v}」の辺「{side}」はない（top・bottom・left・right）" if i in self.ids else
                         f"{loc}（arrow）.{k}: id「{v}」の部品がない（このページにあるもの: {'・'.join(self.ids) or 'なし'}）")
            return i, side

        def end(v, k):
            if isinstance(v, list):
                if bounds and not (0 <= v[0] <= bounds[0] + 0.01 and 0 <= v[1] <= bounds[1] + 0.01):  # frame の部品と同じく、frame の外を指さない
                    sys.exit(f"{loc}（arrow）.{k}: {v} は frame の外（ページの左上から、点は {origin[0] + v[0]:.2f}, {origin[1] + v[1]:.2f} in、"
                             f"frame は左端 {origin[0]:.2f} in・上端 {origin[1]:.2f} in・右端 {origin[0] + bounds[0]:.2f} in・下端 {origin[1] + bounds[1]:.2f} in）")
                return (origin[0] + v[0], origin[1] + v[1], 0, 0)
            if v not in self.ids:
                sys.exit(f"{loc}（arrow）.{k}: id「{v}」の部品がない（このページにあるもの: {'・'.join(self.ids) or 'なし'}）")
            return self.ids[v]
        (fa, sa), (fb, sb) = split(e["from"], "from"), split(e["to"], "to")
        (ax, ay, aw, ah), (bx, by, bw, bh) = end(fa, "from"), end(fb, "to")
        a, b = (self.anchors.get(v) if isinstance(v, str) else None for v in (fa, fb))
        route, off, sided = e.get("route", "straight"), e.get("offset", 0), bool(sa or sb)
        bent, elbow = route == "bent", False  # 2 回折れる線と、1 回だけ折れる線（辺を書いた矢印は、辺から決める）
        if sided and not all(isinstance(v, str) for v in (fa, fb)):
            sys.exit(f"{loc}（arrow）: 辺を書いた矢印は、両端を id にする（[x, y] の点には辺がない。点まで引くなら、辺を書かない）")
        if sided and not (sa and sb):
            sys.exit(f"{loc}（arrow）: 辺は両端に書く（from は「{e['from']}」、to は「{e['to']}」。片方だけでは、もう片方の辺が決まらない）")
        if sided and "route" in e:
            sys.exit(f"{loc}（arrow）.route: 両端に辺を書いたら route は書かない（線の形は辺から決まる。直交する辺は 1 回、向き合う辺は 2 回折れる）")
        if off and (route != "straight" or sided or not all(isinstance(v, str) for v in (fa, fb))):
            sys.exit(f"{loc}（arrow）.offset: 線をずらすのは、両端を id で指したまっすぐの矢印だけ（折れ線、辺を書いた端、[x, y] の端には書けない）")
        boxed = bool(a and b)
        if off:  # ずらした線は辺の中央の接続点に付かないので、図形につながず、箱の辺から辺へ引く（画面で箱を動かすと付いてこない）
            a = b = None
        if (bent or sided) and not (a and b):
            sys.exit(f"{loc}（arrow）{'' if sided else '.route'}: {'辺を書いた矢印' if sided else '折れ線（bent）'}は、"
                     "両端を id でつなげる部品（card・code・box と、中央寄せの label・stat・塗りか枠線のある text。shape は四角か角丸）に引く")
        # 両端がつなげる部品なら、図形につなぐ（画面で動かしても付いてくる）。つないだ線は接続点（辺の中央）から引くので、間を空けない
        pa, pb = (ARROW_PAD if (aw or ah) and not boxed else 0), (ARROW_PAD if (bw or bh) and not boxed else 0)  # [x, y] の端はその点まで
        sites = None
        if sided:  # 指した辺の中央どうしを結ぶ。出る辺は相手の入る点に、入る辺は始めの出る点に向いている（線が両端の箱の中を通らない）
            def mid(x, y, w, h, side):
                return {"top": (x + w / 2, y), "bottom": (x + w / 2, y + h), "left": (x, y + h / 2), "right": (x + w, y + h / 2)}[side]

            def around(px, py, x, y, w, h):  # 点が箱のどちらにあるか（エラーで、向きの合う辺を示す）
                return "".join(n for n, c in (("左", px < x), ("右", px > x + w), ("上", py < y), ("下", py > y + h)) if c) or "中"
            (x1, y1), (x2, y2), sites = mid(ax, ay, aw, ah, sa), mid(bx, by, bw, bh, sb), (sa, sb)
            toward = {"right": (1, 0), "left": (-1, 0), "bottom": (0, 1), "top": (0, -1)}
            if sa == sb:
                sys.exit(f"{loc}（arrow）: 両端が同じ向きの辺（{sa}）なので、U 字になって引けない。出る辺か入る辺を変える")
            if toward[sa][0] * (x2 - x1) + toward[sa][1] * (y2 - y1) < 0.01:
                sys.exit(f"{loc}（arrow）.from: 出る辺 {sa} が相手を向いていない（相手の入る点は、始めの箱の{around(x2, y2, ax, ay, aw, ah)}にある。"
                         "その向きの辺にするか、0.01 in より離す）")
            if toward[sb][0] * (x1 - x2) + toward[sb][1] * (y1 - y2) < 0.01:
                sys.exit(f"{loc}（arrow）.to: 入る辺 {sb} が始めの箱を向いていない（始めの出る点は、相手の箱の{around(x1, y1, bx, by, bw, bh)}にある。"
                         "その向きの辺にするか、0.01 in より離す）")
            elbow = (sa in ("left", "right")) != (sb in ("left", "right"))
            bent = not elbow  # 向き合う辺は横・縦・横か縦・横・縦。中央がそろっていれば、下でまっすぐにする
        elif not (aw or ah or bw or bh):
            x1, y1, x2, y2 = ax, ay, bx, by
        elif bx >= ax + aw or ax >= bx + bw:  # 左右に離れている。向き合う辺の中央どうしを結ぶ（中央が同じ高さなら横の矢印。違えば斜め。
            # 重なる範囲の中央に横に引くと、どちらの箱の中央にも付かない。2026-10-16 の見本で 0.25 in ずれた）
            y1, y2 = ay + ah / 2 + off, by + bh / 2 + off
            x1, x2 = (ax + aw + pa, bx - pb) if bx >= ax + aw else (ax - pa, bx + bw + pb)
            if off and not (ay < y1 < ay + ah and by < y2 < by + bh):
                sys.exit(f"{loc}（arrow）.offset: {off} in ずらすと、線の端が箱の上下の外に出る（箱の高さの半分より小さくする）")
            sites = ("right", "left") if bx >= ax + aw else ("left", "right")  # 右の辺から左の辺へ、左の辺から右の辺へ
        elif by >= ay + ah or ay >= by + bh:
            x1, x2 = ax + aw / 2 + off, bx + bw / 2 + off
            y1, y2 = (ay + ah + pa, by - pb) if by >= ay + ah else (ay - pa, by + bh + pb)
            if off and not (ax < x1 < ax + aw and bx < x2 < bx + bw):
                sys.exit(f"{loc}（arrow）.offset: {off} in ずらすと、線の端が箱の左右の外に出る（箱の幅の半分より小さくする）")
            sites = ("bottom", "top") if by >= ay + ah else ("top", "bottom")
        else:
            sys.exit(f"{loc}（arrow）: 両端の部品が重なっているので引けない")
        if bent:  # Google は幅か高さが 0 の折れ線を作れず、build が止まる。along は出る向き、across はそれと直交する向きの長さ
            along, across = (abs(x1 - x2), abs(y1 - y2)) if sites[0] in ("left", "right") else (abs(y1 - y2), abs(x1 - x2))
            if along < 0.01:  # 箱の辺が接している（辺を書いた矢印は、上で止まる）
                sys.exit(f"{loc}（arrow）.route: 折れ線（bent）の線に 0.01 in より短い区間ができる（箱の間が狭い）。箱を離すか、まっすぐの矢印にする")
            if across < 0.01:
                bent = False  # 中央がそろった箱の折れ線は、まっすぐ引く
        if bent and route == "bent":  # 辺を書いた矢印（下の段から上の段へ戻る線など）は、書き手が辺を決めたので見ない
            def eid(v):  # split と同じ分け方。止めないので、ほかの矢印の辺の誤りは、その矢印を引くときに、その矢印の場所で止まる
                return v if v in self.ids or "." not in v else v.rsplit(".", 1)[0]
            ends = Counter((k, eid(a[k])) for a, *_ in self.arrows for k in ("from", "to") if isinstance(a[k], str))
            if ends["from", fa] == 1 and ends["to", fb] == 1:  # fa から出る線も fb に入る線も 1 本だけ  # 2026-10-20、ワークスペースの決まりから（避けて回した 1 本の線は、どこからどこへの流れかが読みにくい）
                self.warns.append(f"{loc}: 枝分かれでも合流でもない 1 本の流れを折れ線（bent）にした。つなぐ 2 つの箱を同じ行か同じ列に置き直し、まっすぐ引く（../visual.md の slides-visual-043）")
        if boxed and route == "straight" and not sided and abs(x1 - x2) > 0.01 and abs(y1 - y2) > 0.01:  # ずらした線（offset）も、両端の箱の中央からずらすので同じ  # 2026-10-16 の依頼文の試しで、枝の 1 本だけ直線にして斜めになった
            self.warns.append(f"{loc}: 矢印が斜めになる。枝分かれなら、どの枝も \"route\": \"bent\" にする（中央が同じ高さの枝はまっすぐ引かれる）か、両端の箱の高さをそろえる")
        self.emit("arrow", loc, e, x1=x1, y1=y1, x2=x2, y2=y2, color=spec_color(e.get("color", "SUB")), head=e.get("head", True), dash=e.get("dash", False), weight=e.get("weight", 1.25),
                  **({"link": [a, sites[0], b, sites[1]], "bent": bent or elbow} if a and b else {}))
        pts = [(x1, y1), (x2, y2)]
        if elbow:
            pts[1:1] = [(x2, y1) if sites[0] in ("left", "right") else (x1, y2)]
        if bent:  # Google は横・縦・横（縦・横・縦）の真ん中で折る（見込み）
            m = (x1 + x2) / 2 if sites[0] in ("left", "right") else (y1 + y2) / 2
            pts[1:1] = [(m, y1), (m, y2)] if sites[0] in ("left", "right") else [(x1, m), (x2, m)]
        lab = None
        if "label_side" in e and "label" not in e:
            sys.exit(f"{loc}（arrow）.label_side: label がない")
        if "label" in e:  # 札は線の真ん中の区間に付ける（既定は、横なら上、縦なら右）。札を位置で置くと、線から浮くか線に重なる（2026-10-16 の deck-review で 6 件）
            (px, py), (qx, qy) = pts[len(pts) // 2 - 1], pts[len(pts) // 2]
            mx, my, flat = (px + qx) / 2, (py + qy) / 2, abs(qx - px) >= abs(qy - py)
            side = e.get("label_side", "top" if flat else "right")
            if (side in ("top", "bottom")) != flat:
                sys.exit(f"{loc}（arrow）.label_side: {side} は{'縦' if flat else '横'}の線の置き場所。札を置く区間は{'横' if flat else '縦'}の線なので、"
                         f"{'top か bottom' if flat else 'left か right'}にする")
            t = {"type": "text", "text": e["label"], "color": "SUB", "align": {"top": "center", "bottom": "center", "left": "right", "right": "left"}[side]}
            lw = widest_em(e["label"], loc) * 11 / 72 + 0.06
            lh = self.measure(t, lw, f"{loc}.label")
            lx = {"left": mx - lw - 2 * LABEL_GAP, "right": mx + 2 * LABEL_GAP}.get(side, mx - lw / 2)
            ly = {"top": my - lh - LABEL_GAP, "bottom": my + LABEL_GAP}.get(side, my - lh / 2)
            self.place(t, lx, ly, lw, lh, lab := f"{loc}.label")
        self.lines.append((loc, pts, e.get("head", True), {self.id_loc[v] for v in (fa, fb) if isinstance(v, str)}, lab))

    def tangles(self):
        """矢印と部品の位置を、解いた形で確かめる（組むときの警告）。frame の図で画像を見て直していたもの（線が部品の上を通る、矢じりが 1 点に集まる、
        部品が一部だけ重なる）を、組む前に出す（2026-10-16。JSON の 1 本目の 29 枚で、1〜2 ページだけ組み直した 13 回のうち 10 回と、
        deck-review の 2〜3 ラウンド目の画像の指摘の半分が frame の図だった）。文字の高さは見積もりなので、ぎりぎりのものは画像で確かめる。"""
        def ink(kind, r, e):  # 塗りのない文字は、文字のあるところだけ（枠は広く取ることが多い）
            if kind != "text" or e.get("fill") or e.get("line"):
                return r
            tw = min(r[2], widest_em(e["text"]) * e.get("size", 11) / 72)
            return (r[0] + {"left": 0, "center": (r[2] - tw) / 2, "right": r[2] - tw}[e.get("align", "left")], r[1], tw, r[3])
        rs = [(loc, kind, ink(kind, r, e)) for kind, loc, r, _, _, e in self.placed if r[2] > 0 and r[3] > 0]
        rings = {loc for kind, loc, _, _, _, e in self.placed if kind in OUTLINE and e.get("shape") == "ellipse"}  # 輪の上にカードを載せる図は、重ねるのが意図
        for i, (l1, k1, a) in enumerate(rs):
            for l2, k2, b in rs[i + 1:]:
                if l1 not in rings and min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > 0.03 and min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > 0.03 and not rect_in(a, b) and not rect_in(b, a):
                    self.warns.append(f"{l1}（{k1}）と {l2}（{k2}）が一部だけ重なる。離すか、一方をもう一方の中に収める")
        edged = [(loc, kind, r) for kind, loc, r, _, _, e in self.placed if kind in EDGED or kind == "text" and (e.get("fill") or e.get("line"))]
        for kind, l1, a, _, _, e in self.placed:  # 囲みの中の縁のある部品は、4 辺から BOX_IN 以上内側に（slides-visual-044。端が囲みの線に重なって 1 本に見える）
            if kind == "box" and e.get("shape") != "ellipse":
                for l2, k2, b in edged:
                    if l2 != l1 and rect_in(b, a) and (gap := min(b[0] - a[0], a[0] + a[2] - b[0] - b[2], b[1] - a[1], a[1] + a[3] - b[1] - b[3])) < BOX_IN - 0.005:
                        self.warns.append(f"{l2}（{k2}）が囲みの {l1} の辺から {max(gap, 0):.2f} in。中の部品を細くするか間を詰めて、4 辺から {BOX_IN} in 以上内側に置く（../visual.md の slides-visual-044）")
        for loc, pts, _, ends, lab in self.lines:
            for l2, k2, r in rs:
                if l2 not in ends and not point_in(pts[0], r) and not point_in(pts[-1], r) and any(seg_hits(p, q, r) for p, q in zip(pts, pts[1:])):
                    self.warns.append((f"{loc}: 斜めの線の札（label）が線に重なる。両端の高さをそろえるか、折れ線にする" if len(pts) == 2 else
                                       f"{loc}: 折れ線の札（label）が線に重なる。label_side で反対の側に置くか、札を置く区間を長くする") if l2 == lab else
                                      f"{loc}: 矢印の線が {l2}（{k2}）の上を通る。部品か矢印の端を動かす")
        heads = [(loc, pts[-1]) for loc, pts, head, _, _ in self.lines if head]
        for i, (l1, p) in enumerate(heads):
            for l2, q in heads[i + 1:]:
                if math.dist(p, q) < 0.1:
                    self.warns.append(f"{l1} と {l2}: 矢じりの先が 1 点に集まる（{p[0]:.2f}, {p[1]:.2f} in）。入る辺か位置をずらす")


def spec_files(src, base=None, where=None, file=False):
    """src（ファイルのパス、dict、そのどちらかの並び）から (ページ, 画像のパスの起点, 場所, 名前) を順に出す。デッキのページのファイルは、デッキのファイルのあるフォルダから読む。
    名前はページのファイル名（拡張子なし。[名前](#p12) のリンク先）で、ファイルでないページは None。
    ファイルの頭には apiVersion と kind（deck・page・component）が要る。Python から渡した dict は、書いていなければ中身から kind を決める。"""
    base = base or Path.cwd()
    if isinstance(src, (str, Path)):
        path, where = base / src, where or str(src)
        try:
            src = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            sys.exit(f"{where}: 読めない（{e}）")
        yield from spec_files(src, path.parent, where, True)
        return
    where = where or "spec"
    if isinstance(src, list) and not file:
        for i, p in enumerate(src):
            yield from spec_files(p, base, None if isinstance(p, str) else f"{where}[{i}]")
        return
    if not isinstance(src, dict):
        sys.exit(f'{where}: ファイルの頭は {{"apiVersion": "{API_VERSION}", "kind": "deck"・"page"・"component", …}}')
    if file or "apiVersion" in src or "kind" in src:
        if (v := src.get("apiVersion")) != API_VERSION:
            sys.exit(f'{where}: ' + (f'apiVersion がない（頭に "apiVersion": "{API_VERSION}" を書く）' if v is None else
                                     f"apiVersion {v!r} は読めない（この slides.py は {API_VERSION}。新しい形ならプラグインを update する）"))
        if (kind := src.get("kind")) not in KINDS:
            sys.exit(f"{where}: kind {kind!r} はない（{'・'.join(KINDS)}）")
    else:
        kind = "deck" if "pages" in src else "component" if src.get("type") in SPEC_EL else "page"
    src = {k: v for k, v in src.items() if k not in ("apiVersion", "kind")}
    if kind == "deck":
        spec_check(src, SPEC_DECK, f"{where}（deck）")
        for p in src["pages"]:
            yield from spec_files(p, base, p)
    elif kind == "theme":
        sys.exit(f"{where}: テーマのファイルはページに並べない（deck.json の theme に名前を書く。テーマのファイルだけを見るなら slides.py lint <ファイル>）")
    elif kind == "component":  # 部品 1 つだけのファイルは、型のないページに置く
        yield {"type": "slide", "body": [src]}, base, where, None
    else:
        yield src, base, where, Path(where).stem if file else None


def spec_page(d, p, base, loc, name=None):
    kind = p.get("type", "page") if isinstance(p, dict) else None
    if kind not in SPEC_PAGE:
        sys.exit(f"{loc}: type「{kind}」はない（ページは {'・'.join(SPEC_PAGE)}、部品は {'・'.join(SPEC_EL)}）")
    spec_check(p, SPEC_PAGE[kind], f"{loc}（{kind}）")
    kw = {k: spec_color(v) if k == "bg" else v for k, v in p.items() if k not in ("type", "body", "band", "source", "speakerNotes", "authorNotes")}
    sid = getattr(d, kind)(**kw)
    if name:
        if name in d.page_names:
            sys.exit(f"{loc}: ページの名前「{name}」が 2 つある（ファイル名をページの名前にする。同じファイルを 2 回並べない）")
        d.page_names[name] = sid
    sp = SpecPage(base, p.get("bg"))
    sp.index += [(f"{loc}.{k}", p[k]) for k in ("title", "lead", "kicker", "sub") if k in p]
    band = p.get("band")
    b = {"text": band} if isinstance(band, str) else band
    limit = BAND_BOTTOM - band_h(b["text"], b.get("sub")) - 0.2 if band else Y_SRC - 0.08  # 本文の下端の限り（結論バンドか出典の行の上）
    sp.body, sp.room = f"{loc}.body", limit
    bottom = sp.flow(p.get("body", []), X, Y_BODY if p.get("lead") else Y_BODY_NOLEAD, W, GAP_BODY, f"{loc}.body")
    sp.lone_text()
    for e, l, origin, bounds in sp.arrows:
        sp.link(e, l, origin, bounds)
    sp.tangles()
    for w in sp.warns:
        d.warn(w)
    made = {}  # 部品の場所 → 組んだ図形の ID（矢印をつなぐ先。card・code は箱）
    for c in sp.out:
        ckw = {k: v for k, v in c.items() if k not in ("call", "loc")}
        if ckw.get("link"):
            a, sa, z, sz = ckw["link"]
            ckw["link"] = (made[a], sa, made[z], sz)
        r = getattr(d, c["call"])(sid, **ckw)
        made.setdefault(c["loc"], d.anchor if c["call"] in ("card", "code") else r)
    if band:
        d.band(sid, b["text"], b.get("sub"))
        sp.index.append((f"{loc}.band", b["text"] + b.get("sub", "")))
    if p.get("body") and bottom > limit + 0.01:
        d.warn(f"本文が{'結論バンド' if band else '出典の行'}に重なる見込み（{loc}.body の下端 {bottom:.2f} in > {limit:.2f} in）。中身を減らすか、ページを分ける")
    if src := p.get("source"):
        d.source(sid, parts := spec_md(src, SUB, f"{loc}.source"))
        sp.index.append((f"{loc}.source", "出典: " + spec_plain(parts)))
    if p.get("speakerNotes"):
        d.note(sid, p["speakerNotes"])
    d.spec_index[sid] = sp.index
    d.spec_esc += [(sid, l, k) for l, k in sp.esc]
    d.resolved.append({"type": kind, "loc": loc, **kw, "els": sp.out, **({"band": band} if band else {}), **({"source": p["source"]} if "source" in p else {}),
                       **({"speakerNotes": p["speakerNotes"]} if "speakerNotes" in p else {})})
    return sid


def spec_where(deck):
    """lint の指摘（「p3: …「文」…」）が引いている文から、JSON の部品の場所を引く（lint.Report.where）。ponytail: 文の頭の 12 字で探す。文を引かない指摘には付かない。
    同じ文で始まる部品が 2 つ以上なら、候補をすべて出す"""
    def where(hit):
        n, q = re.match(r"p(\d+)", hit), re.search(r"「(.+?)」", hit)
        if not n or not q or int(n.group(1)) > len(deck.slides):
            return ""
        t = re.sub(r"[\s\v⏎]", "", q.group(1).split(" / ")[0]).strip("…")[:12]
        locs = [loc for loc, s in deck.spec_index.get(deck.slides[int(n.group(1)) - 1], []) if t and t in re.sub(r"[\s\v]", "", s)]
        return f"（{'・'.join(dict.fromkeys(locs))}）" if locs else ""  # 同じ文で始まる部品が 2 つ以上なら、どれかを決めずに全部出す
    return where


SPEC_UNIT = {"w": "幅（in）", "h": "高さ（in）", "x": "frame の左上からの位置（in。frame の中だけ）", "y": "frame の左上からの位置（in。frame の中だけ）",
             "size": "pt", "icon.size": "in", "num.size": "small は図の中の印、medium はカードと手順（既定）、large は大きな段",
             "variant": "会社のテンプレートの表紙・扉のパターンの番号（テンプレートの見本のページにある。テンプレートがなければ 1 だけ）", "gap": "部品の間（in）", "id": "矢印の from・to で指す名前", "spacing": "行間（%）",
             "authorNotes": "スライドにもノートにも組まない注記（スライドから外した事実・断り書き・そのページで言いたいこと）。書き換えてもページを作り直さない", "para_gap": "段落の間（pt）",
             "pad": "箱の端と文字の間（in）", "radius": "角の丸み（in）", "step": "項目の間隔（in）",
             "route": "bent は折れ線（両端を id でつないだとき）。id の両端が箱なら、線は箱につながる。出る辺・入る辺を決めるときは、route を書かずに from・to を \"<id>.<辺>\" にする", "today": "今日の縦線の位置（1 が 1 列目の左端、1.5 が 1 列目の中ほど）",
             "label_side": "札の置き場所。横の線は top（既定）か bottom、縦の線は right（既定）か left",
             "offset": "線を箱の中央からずらす in。横の線は下が正、縦の線は右が正。ずらした線は箱につながない（同じ 2 つの箱の間に 2 本引くとき）",
             "bars.unit": "数のあとに付ける単位", "stat.unit": "単位（数字の半分の大きさ）", "horizontal": "横の棒（名前が長い・順位）。既定は縦の棒（時の流れ）", "bars.hot": "強調する棒の番号（1 から。赤）",
             "bars.line": "折れ線（縦の棒だけ）。棒と別の目盛りで、棒の上の段に引く（率・累計など単位の違う数）。threshold と一緒に書ける",
             "bars.threshold": "目標・上限などの直線（いつも棒と同じ目盛り。赤の点線）。折れ線の目盛りの線は引けない", "values": "棒ごとの数（items の順）",
             "code.hot": "赤の太字にする行（1 から）", "table.header": "見出しの行の数（true は 1、false は 0）", "table.valign": "セルの上下の寄せ（既定は middle）",
             "borders": "罫線。rows は横の罫線だけ（既定）、grid は縦横と外枠（結合したセルの区切りを見せるとき）、none はなし",
             "colspan": "右へ結合する列の数（覆う位置にはセルを書かない。HTML と同じ）", "rowspan": "下へ結合する行の数（下の行の、覆う位置にはセルを書かない）",
             "cell.fill": "そのセルの塗り（濃い色なら文字は白）。行か列の全部は表の fills", "cell.color": "文字の色（書かなければ塗りから決まる）",
             "cell.align": "そのセルの横の寄せ（書かなければ列の align）", "cell.valign": "そのセルの上下の寄せ（書かなければ表の valign）",
             "list.icon": "全部の項目の印（Iconify の名前）。書かなければ番号", "start": "最初の番号（既定 1。印を書いた項目も 1 つと数える）",
             "list.size": "印の大きさ（num と同じ。既定は medium）", "list.color": "アイコンの色（既定は本文の色）", "list.gap": "項目の間（in。既定 0.16）",
             "item.text": "本文（見出しがあれば灰色の補足）", "item.head": "見出し（太字 12pt）", "item.icon": "その項目の印（Iconify の名前）",
             "item.num": "その項目の番号", "item.image": "その項目の印の画像（ロゴなど。image の src と同じ書き方）"}


def spec_unit(kind, k):
    """キー k の説明（型ごとのものがあれば、そちら）。"""
    return SPEC_UNIT.get(f"{kind}.{k}") or SPEC_UNIT.get(k)


def spec_brief():
    """書く形の早見表（slides.py schema --brief）。SPEC_EL・SPEC_PAGE・SPEC_DECK と型の説明から作るので、形と食い違わない。* は要るキー。
    pom の llm.txt にならい、ページを書く子が JSON Schema の全文の代わりに読む（prompt_pages.md）。"""
    short = {"s": "文字", "md": "記法", "n": "数", "f": "正か負の数", "p": "正の数", "i": "整数", "pi": "1 以上", "b": "真偽", "c": "色", "els": "部品の並び", "kids": "部品の並び",
             "w": '正の数か "fit"', "nh": "正の数か行ごとの並び", "ints": "1 からの番号の並び", "nums": "比の並び", "ns": "文字か整数", "hn": "真偽か行の数", "rows": "行の並び。セルは記法か {…}", "strs": "文字の並び", "litems": "項目の並び。記法か {…}", "pt": "id（id.辺）か [x, y]"}
    def keys(schema, kind=""):
        need, opt = schema
        out = []
        for k, v in {**need, **opt}.items():
            ty = "|".join(v) if isinstance(v, tuple) else short.get(v) or SPEC_TYPES.get(v, v)
            out.append(f"{k}{'*' if k in need else ''}（{ty}{'。' + u if (u := spec_unit(kind, k)) else ''}）")
        return " ".join(out)
    lines = [f"# {API_VERSION} の早見表（全部は slides.py schema。見本は samples/json/。* は要るキー）",
             f'ファイルの頭: {{"apiVersion": "{API_VERSION}", "kind": "deck"・"page"・"component"}}。deck は 1 ページ 1 ファイルを pages に並べる',
             f"色: {'・'.join(COLOR_NAMES)}（役割の名前だけ。値はテーマが決める。文字の色は塗りと地から決まる）",
             "記法: **太字** ***赤の太字*** {32:文字}（32pt） [名前](URL) [名前](#p12)（p12.json のページ） <br>（段落の中の改行）。\\n で段落、どの段落も「- 」で始めると箇条書き", "",
             "## デッキ", "deck: " + keys(SPEC_DECK), "", "## ページ（type。省くと page）"]
    lines += [f"{k}: {keys(v)}" for k, v in SPEC_PAGE.items()]
    lines += ["", "## 部品（type）", "どの部品にも: id（矢印の from・to で指す）、w（幅 in）、h（高さ in。row・stack・grid・gantt・list と icon・num・arrow は書かない）。"
              "x・y は frame の中だけ。raw は形の外の書き方（lint が要確認に出す）"]
    lines += [f"{k}: {keys(v, k)}" for k, v in SPEC_EL.items()]
    lines += ["  table の rows のセル（記法つきの文字か {…}）: " + keys(TABLE_CELL, "cell"), "  list の items の項目（記法つきの文字か {…}）: " + keys(LIST_ITEM, "item"), "  gantt の rows: " + keys(GANTT_ROW), "  gantt の bars: " + keys(GANTT_BAR), "  gantt の marks: " + keys(GANTT_MARK), "  bars の line: " + keys(BARS_LINE), "  bars の threshold: " + keys(BARS_THRESHOLD)]
    return "\n".join(lines)


def spec_schema():
    """書く形の JSON Schema（slides.py schema が出す）。SPEC_EL・SPEC_PAGE・SPEC_DECK から作る。structured outputs やエディタの確かめに渡す。"""
    md = ("記法: **太字** ***赤の太字*** {32:文字}（32pt） [名前](URL) [名前](#p12) <br>（段落の中の改行）。太字・赤・大きさの中に書式を入れられる（**{32:48}**）。"
          "\\n で段落、どの段落も「- 」で始めると箇条書き。`コード` は ` を外して本文の書体のまま")
    color = {"enum": list(COLOR_NAMES), "description": "役割の名前。値はテーマのファイルが決める（6 桁は書けない）"}
    num, pos = {"type": "number"}, {"type": "number", "exclusiveMinimum": 0}
    cell = {"anyOf": [{"type": "integer", "minimum": 1}, {"const": "all"}]}  # fills の行と列
    t = {"s": {"type": "string"}, "md": {"type": "string", "description": md}, "n": {"type": "number", "minimum": 0}, "f": num, "p": pos, "i": {"type": "integer"},
         "pi": {"type": "integer", "minimum": 1}, "b": {"type": "boolean"}, "c": color,
         "w": {"anyOf": [pos, {"const": "fit"}], "description": "幅（in）。label は \"fit\" で中身の文字の幅"},
         "nh": {"anyOf": [pos, {"type": "array", "items": pos}], "description": "行の高さの最小（in）。行ごとに並べてもよい"},
         "els": {"type": "array", "items": {"$ref": "#/$defs/element"}}, "kids": {"type": "array", "items": {"$ref": "#/$defs/element"}, "minItems": 1}, "pages": {"type": "array", "items": {"type": "string", "pattern": "\\.json$"}, "minItems": 1, "description": "ページかデッキのファイルのパス"},
         "pt": {"anyOf": [{"type": "string", "description": "部品の id。\"<id>.<辺>\"（辺は top・bottom・left・right）で出る辺・入る辺を指す（両端に書く）"}, {"type": "array", "items": num, "minItems": 2, "maxItems": 2}]},
         "items": {"type": "array", "items": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2, "description": "[見出し, 説明（記法つき）]"}},
         "strs": {"type": "array", "items": {"type": "string"}},
         "hn": {"anyOf": [{"type": "boolean"}, {"type": "integer", "minimum": 0}]},
         "nums": {"type": "array", "items": {"type": "number", "exclusiveMinimum": 0}, "description": "比"},
         "cols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "description": "列の名前（月・週）。左から 1 列目"},
         "gbars": {"type": "array", "items": {"type": "object", "properties": {"from": {"type": "integer", "minimum": 1}, "to": {"type": "integer", "minimum": 1},
                                                                               "text": {"type": "string", "description": "9pt。1 行 5 字・2 行まで（改行は \\n）"},
                                                                               "status": {"enum": list(GANTT_STATUS), "description": "plan（決まった予定。既定、濃紺）・tbd（未定。点線の枠）・done（終わった。淡い灰色）・hot（遅らせられないもの。淡い赤の地に赤の文字）"}},
                                               "required": ["from", "to"], "additionalProperties": False}, "description": "何列目から何列目まで（1 から、両端を含む）。重なるバーは下の段に回る"},
         "gmarks": {"type": "array", "items": {"type": "object", "properties": {"at": pos, "text": {"type": "string", "description": "11pt の 1 行（印の右。表の右端を越えるなら左）。記法なし"}},
                                                "required": ["at", "text"], "additionalProperties": False},
                    "description": "節目（赤の菱形と言葉）。at は today と同じ位置で、3 は 3 列目の左端、3.5 は 3 列目の中ほど。バーと重なれば下の段に回る"},
         "bitems": {"type": "array", "items": {"type": "array", "prefixItems": [{"type": "string"}, {"type": "number", "minimum": 0}], "minItems": 2, "maxItems": 2},
                    "minItems": 1, "description": "[名前, 数]。数は棒の端に書く"},
         "bline": {"type": "object", "properties": {"values": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 1, "description": "棒ごとの数（items の順。数は棒と同じだけ）"},
                                                     "unit": {"type": "string"}, "label": {"type": "string", "description": "何の数か（段の左上に書く）"}},
                   "required": ["values"], "additionalProperties": False},
         "bthr": {"type": "object", "properties": {"value": {"type": "number", "minimum": 0}, "label": {"type": "string", "description": "何の線か（「目標」。札は「目標 90 分」）"}},
                  "required": ["value"], "additionalProperties": False},
         "ints": {"type": "array", "items": {"type": "integer", "minimum": 1}, "description": "1 から始まる番号"},
         "fills": {"type": "array", "items": {"type": "array", "prefixItems": [cell, cell, color], "minItems": 3, "maxItems": 3},
                   "description": "[行, 列, 色]。rows の何番目かで数え、見出しの行が 1 行目、いちばん左の列が 1 列目。\"all\" はその列か行の全部（[3, \"all\", \"RED_SOFT\"] は見出しの次の次の行）"},
         "aligns": {"type": "array", "items": {"enum": list(ALIGN)}, "minItems": 1, "description": "列ごとの寄せ"}, "ns": {"type": ["string", "integer"]},
         "band": {"anyOf": [{"type": "string"}, {"type": "object", "properties": {"text": {"type": "string"}, "sub": {"type": "string"}}, "required": ["text"], "additionalProperties": False}]},
         "raw": {"type": "object", "description": "形の外の書き方: Deck のメソッドの引数（lint が要確認に出す）"},
         "colors": {"type": "object", "properties": {k: {"type": "string", "pattern": "^[0-9A-Fa-f]{6}$"} for k in (*ROLE, *FIXED, *NAMED)}, "additionalProperties": False,
                    "description": "役割の名前 → 6 桁の色（# は付けない）。書かない役割は visual の色、テーマに入れない色は既定の値"},
         "layouts": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "object", "properties": {"layout": {"type": "string"}, "w": pos, "tone": {"enum": list(TONES)}},
                                                                             "required": ["layout"], "additionalProperties": False}]},
                     "description": "会社のテンプレートから残す表紙・扉のレイアウトの名前（並びの順が variant の番号）。w（文字の幅）と tone（地の明るさ）は template.py が書き込む"}}
    cell = {"type": "object", "properties": {k: dict(t[v]) if isinstance(v, str) else {"enum": list(v)} for k, v in {**TABLE_CELL[0], **TABLE_CELL[1]}.items()},
            "required": list(TABLE_CELL[0]), "additionalProperties": False}
    for k in cell["properties"]:
        cell["properties"][k] |= {"description": u} if (u := spec_unit("cell", k)) else {}
    row = {"type": "array", "items": {"anyOf": [t["md"], cell]}}
    item = {"type": "object", "properties": {k: dict(t[v]) | ({"description": u} if (u := spec_unit("item", k)) else {}) for k, v in LIST_ITEM[1].items()},
            "anyOf": [{"required": ["text"]}, {"required": ["head"]}], "additionalProperties": False}
    t["litems"] = {"type": "array", "items": {"anyOf": [t["md"], item]}, "minItems": 1, "description": "項目。文字だけなら記法つきの文字で書く"}
    t["rows"] = {"type": "array", "prefixItems": [row | {"minItems": 1}], "items": row, "minItems": 1,  # 1 行目は空にできない（列の数を決める）
                 "description": "1 行目が見出しの行。セルは記法つきの文字か {\"text\": …}。結合したセルが覆う位置には、セルを書かない（HTML と同じ。上の rowspan が全部の列を覆う行は []）"}
    t["grows"] = {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {"head": {"type": "string", "description": "項目（表のセル。記法なし）"}, "bars": t["gbars"],
                                                                                           "marks": t["gmarks"], "note": {"type": "string", "description": "補足（右の列。記法なし）"}},
                                                             "required": ["head"], "additionalProperties": False}}
    head = {"apiVersion": {"const": API_VERSION}}

    def obj(kind, schema, extra=None, need_type=True, k8s="component"):
        need, opt = schema
        props = {"type": {"const": kind}, **head, "kind": {"const": k8s}}
        for k, v in {**need, **opt, **(extra or {})}.items():
            props[k] = dict(t[v] if isinstance(v, str) else {"enum": list(v)}) | ({"description": u} if (u := spec_unit(kind, k)) and "description" not in t.get(v, {}) else {})
        return {"type": "object", "properties": props, "required": ([] if not need_type else ["type"]) + list(need), "additionalProperties": False}
    defs = {f"el_{k}": obj(k, v, {g: x for g, x in _GEO.items() if not (k in NO_SIZE and g in ("w", "h")) and not (k in NO_H and g == "h")} | ({} if k in NO_ESC else _ESC))
            for k, v in SPEC_EL.items()}
    defs |= {f"page_{k}": obj(k, v, need_type=k != "page", k8s="page") for k, v in SPEC_PAGE.items()}
    defs |= {"element": {"oneOf": [{"$ref": f"#/$defs/el_{k}"} for k in SPEC_EL]}, "page": {"anyOf": [{"$ref": f"#/$defs/page_{k}"} for k in SPEC_PAGE]},
             "deck": obj("deck", SPEC_DECK, need_type=False, k8s="deck"), "theme": obj("theme", SPEC_THEME, need_type=False, k8s="theme")}
    defs["deck"]["properties"].pop("type")
    defs["theme"]["properties"].pop("type")
    root = lambda ref, k8s: {"allOf": [{"$ref": f"#/$defs/{ref}"}], "properties": {"kind": {"const": k8s}}, "required": ["apiVersion", "kind"]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://github.com/mats16/ai-deck-factory/{API_VERSION}", "title": f"AI Deck Factory のページ（{API_VERSION}）",
            "anyOf": [root("deck", "deck"), root("page", "page"), root("element", "component"), root("theme", "theme")], "$defs": defs}


SPEC_OUT = "JSON の形の外の書き方（raw）"


def spec_promoted(kind, k):
    """raw に書いた Deck の引数 k を書ける、形のキー（SPEC_PROMOTED にあるものだけ。同じ名前でも意味の違うキーがある）。なければ None。"""
    return SPEC_PROMOTED.get((kind, k))


DECK_ENUM = {"START": "left", "CENTER": "center", "END": "right", "TOP": "top", "MIDDLE": "middle", "BOTTOM": "bottom"}  # Deck の揃えの値 → 形の値


def spec_from_deck(kind, key, v):
    """raw に書いた Deck の値 v を、形のキー key の値に直す（揃えは小文字の名前、形は小文字、色はテーマの枠の名前を役割の名前に）。形の型に合わなければ None。"""
    if key in ("align", "valign") and isinstance(v, str):  # 表の align は Deck でも形でも語の並び
        v = DECK_ENUM.get(v, v)
    elif key == "shape" and isinstance(v, str):
        v = v.lower()
    elif key in ("fill", "line", "color", "bg") and isinstance(v, str) and not _color(v):
        v = next((n for n in COLOR_NAMES if globals()[n] == v), v)  # "DARK1" → "NAVY"
    need, opt = SPEC_EL.get(kind, ({}, {}))
    t = {**need, **opt, **_GEO}.get(key)
    return v if t and spec_ok(v, t) else None


def spec_out_hits(deck):
    """形の外の書き方（raw）を、lint の要確認の行にする。形のキーで書ける raw には、そのキーを添える。"""
    pages = {s: i for i, s in enumerate(deck.slides, 1)}
    out = []
    for sid, loc, key in deck.spec_esc:
        t, _, k = key.partition(".raw.")
        hint = (f"。形の {spec_promoted(t, k)} で書ける（slides.py upgrade で書き換える）" if spec_promoted(t, k) else
                "。ほかの資料でも要るなら、形に足す提案にする（slides.py stats）")
        out.append(f"p{pages[sid]}: {key}（{loc}）{hint}")
    return out


def spec_log_path():
    return gapi.factory_path().parent / ".factory" / "spec_raw.jsonl"


def spec_record(deck, pid):
    """組んだ JSON のページのデッキの形の外の書き方の数を、ワークスペースの .factory/spec_raw.jsonl に 1 行で残す（slides.py stats が数える。raw がなくても残し、前の数を 0 にする）。資料の文は残さず、キーと数だけ。
    名前に tmp の入った資料と、factory-kaizen の検証の資料（FACTORY_VERIFY）は数えない（lint_runs.jsonl と同じ）。"""
    if not deck.resolved or os.environ.get("FACTORY_VERIFY") or "tmp" in deck.name.lower():  # JSON のページのデッキは、raw がなくても残す（前の数を 0 にする）
        return
    path = spec_log_path()
    try:  # 組み終えたあとの記録。書けなくても組んだデッキは止めない
        path.parent.mkdir(exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deck": pid, "uses": dict(Counter(k for _, _, k in deck.spec_esc))},
                               ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"警告: 形の外の書き方の数を {path} に残せなかった（{e}）", file=sys.stderr)


def spec_stats(path=None):
    """形の外の書き方を、キーごとに、使った資料の数と使った数で出す（資料ごとに最後に組んだときの数）。2 本以上の資料で使ったキーは、形に足す候補（factory-kaizen）。"""
    path, last, bad = Path(path or spec_log_path()), {}, 0
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            d = json.loads(line)
            last[d["deck"]] = dict(d["uses"])
        except (ValueError, KeyError, TypeError):  # 途中で切れた行・手で直した行は飛ばす
            bad += line.strip() != ""
    if bad:
        print(f"警告: {path} の読めない {bad} 行を飛ばした", file=sys.stderr)
    rows = defaultdict(lambda: [0, 0])
    for uses in last.values():
        for k, n in uses.items():
            rows[k][0] += 1
            rows[k][1] += n
    print(f"資料 {len(last)} 本\nキー\t資料\t使った数")
    for k, (a, n) in sorted(rows.items(), key=lambda x: (-x[1][0], -x[1][1])):
        print(f"{k}\t{a}\t{n}")
    return dict(rows)


def spec_upgrade(paths):
    """JSON のページのファイルの raw のうち、形のキーで書けるもの（spec_promoted）を、そのキーに書き換える。書き換えた数を返す。
    書き換えたファイルは、JSON を整え直して書く（手で付けた改行の位置は残らない。標準ライブラリだけで書き方を保つと、JSON の書き換えの仕組みが要る）。
    形の版（apiVersion）を上げたときの書き換えも、ここに足す（slides-pages-035）。"""
    total = 0
    for path in paths:
        try:
            o, n = json.loads(Path(path).read_text()), 0
        except (OSError, json.JSONDecodeError) as e:
            sys.exit(f"{path}: 読めない（{e}）")

        def walk(x):
            nonlocal n
            if isinstance(x, list):
                for v in x:
                    walk(v)
                return
            if not isinstance(x, dict):
                return
            raw = x.get("raw")
            for k in list(raw) if isinstance(raw, dict) else []:
                key = spec_promoted(x.get("type"), k)
                v = spec_from_deck(x.get("type"), key, raw[k]) if key else None  # 形の型に直せない値は raw に残す
                if key and key not in x and v is not None:
                    x[key] = v
                    del raw[k]
                    n += 1
            if isinstance(raw, dict) and not raw:
                del x["raw"]
            for k in ("body", "items", "pages"):
                walk(x.get(k))
        walk(o)
        if n:
            Path(path).write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n")
        print(f"{path}: {n} 個を形のキーに書き換えた")
        total += n
    return total


STAMP = "slides_py_revision"  # 組んだときの版（revision）を、Drive のファイルの appProperties に残す


def revision(pid):
    """Drive の版の一覧の最後の ID。中身を直すと進み、コメント・返信・解決と appProperties の書き込みでは進まない。presentations の revisionId は
    コメントを付けても返信しても解決しても進み、comments.py reply --resolve のあとの build が画面で直されたと取り違えるので使わない（2026-10-19 に確かめた）。"""
    last, page = None, None
    while True:  # 古い順に並ぶ
        r = request("GET", f"{DRIVE}/files/{pid}/revisions?pageSize=1000&fields=nextPageToken,revisions(id)" + (f"&pageToken={urllib.parse.quote(page)}" if page else ""))
        last = (r.get("revisions") or [{"id": last}])[-1]["id"]
        if not (page := r.get("nextPageToken")):
            return last


def need_brand():
    """組むデッキの著作権表示（テーマの copyright があればそれ）で brand.need_brand を呼ぶ。"""
    brand.need_brand(COPYRIGHT)


def deck_mark(p):
    """presentations の masters・layouts の代替テキストにある、テーマの目印（THEME_MARK の match）。なければ None（template.py で合わせ直す前のテンプレートから作ったデッキ）。"""
    return next((m for pg in p.get("masters", []) + p.get("layouts", []) for e in pg.get("pageElements", [])
                 if (m := THEME_MARK.search(e.get("description", "")))), None)


def deck_theme(p):
    """デッキ p のテーマの名前（deck_mark）。なければ None。"""
    return m.group(1) if (m := deck_mark(p)) else None


def mark_values(p):
    """デッキ p のテーマの目印の JSON（theme_extras）を、テーマの表の形にしたもの。書いていない（前の template.py の目印）か読めなければ {}。"""
    try:
        e = json.loads(m.group(2)) if (m := deck_mark(p)) and m.group(2) else {}
    except json.JSONDecodeError:
        return {}
    if not isinstance(e, dict) or not isinstance(e.get("colors", {}), dict):  # 画面で書き換えた目印など
        return {}
    return {k: v for k, v in e.items() if k != "colors"} | e.get("colors", {})


def layout_marks(p):
    """presentations の layouts のうち、表紙・扉の目印（LAYOUT_MARK）を持つもの。[(レイアウト, 目印の match)]。"""
    return [(l, m) for l in p.get("layouts", []) for e in l.get("pageElements", []) if (m := LAYOUT_MARK.search(e.get("description", "")))]


def layout_mark(kind, n, l):
    """表紙・扉のパターンの目印（LAYOUT_MARK）。l はテーマの cover・section の 1 つ（{"layout", "w", "tone"}）。"""
    return f"ai-deck-factory layout={kind}:{n}" + (f" w={l['w']}" if l.get("w") else "") + (f" tone={l['tone']}" if l.get("tone") else "")


def deck_layouts(p):
    """{("cover"・"section", 番号): レイアウト}。build が @COVER<番号>・@SECTION<番号> を置き換える。"""
    return {(m.group(1), int(m.group(2))): l for l, m in layout_marks(p)}


def use_layouts(p):
    """表紙・扉のパターン（文字の幅と地の明るさ）を、デッキ（new ならテンプレート）の目印から決める。make_deck の前に呼ぶ。"""
    VARIANTS.clear()
    for _, m in layout_marks(p):
        VARIANTS.setdefault(m.group(1), {})[int(m.group(2))] = (float(m.group(3)) if m.group(3) else None, m.group(4) or "dark")


def ws_themes():
    """ワークスペースのテーマのフォルダ（themes/slides）。ワークスペースの外なら None。"""
    return ws.parent.joinpath(*WS_THEMES) if (ws := gapi.find_factory()) else None


def theme_path(name):
    """テーマ name のファイル（ワークスペースの themes/slides/<name>.json、なければ組み込みの slides-build/themes/<name>.json）。どちらもなければ None。"""
    return next((f for d in (ws_themes(), BUILTIN_THEMES) if d and (f := d / f"{name}.json").is_file()), None)


def theme_names():
    """テーマの名前（組み込みと、ワークスペースのファイル）。"""
    return list(dict.fromkeys(f.stem for d in (BUILTIN_THEMES, ws_themes()) if d and d.is_dir() for f in sorted(d.glob("*.json"))))


def read_theme(path):
    """テーマのファイル path（kind theme）を確かめて、テーマの表（colors を開いた平らな dict。theme_values・template.py が読む形）にする。
    cover・section の名前だけの書き方は {"layout": 名前} にする。書けない値なら場所を付けて止める（組む前に。slides.py lint <ファイル> が見る）。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", Path(path).stem):  # 目印（THEME_MARK）と factory.toml の [slides.templates] のキーに、引用符なしで書く
        sys.exit(f"{path}: テーマのファイルの名前は英数字と - _ だけにする（名前がテーマの名前）")
    try:
        o = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{path}: 読めない（{e}）")
    if not isinstance(o, dict) or o.get("apiVersion") != API_VERSION or o.get("kind") != "theme":
        sys.exit(f'{path}: ファイルの頭は {{"apiVersion": "{API_VERSION}", "kind": "theme", …}}')
    o = {k: v for k, v in o.items() if k not in ("apiVersion", "kind")}
    spec_check(o, SPEC_THEME, f"{path}（theme）")
    t = {k: v for k, v in o.items() if k != "colors"} | {k: v.upper() for k, v in o.get("colors", {}).items()}
    for k in ("cover", "section"):
        if k in t:
            t[k] = [{"layout": l} if isinstance(l, str) else l for l in t[k]]
    if both := {l["layout"] for l in t.get("cover", [])} & {l["layout"] for l in t.get("section", [])}:  # 目印はレイアウトに 1 つなので、両方に書くと後のものだけが残る
        sys.exit(f"{path}: レイアウト「{'」「'.join(sorted(both))}」が cover と section の両方にある。どちらか一方に書く")
    theme_values(t), theme_font(t)
    return t


def load_theme(name):
    """テーマ name の表（read_theme）。name が None か、ファイルがなければ None。"""
    return read_theme(f) if name and (f := theme_path(name)) else None


def theme_slots(t):
    """テーマの表 t の 12 の枠の色。書いていない役割は visual の色。"""
    return VISUAL | {ROLE[k]: t[k] for k in ROLE if k in t}


def theme_extras(t):
    """テーマの表 t のうち、マスターの配色・書体・表紙と扉の目印に入らない値（テーマの目印の JSON。テーマのファイルの形）。"""
    c = {k: t[k] for k in (*FIXED, *NAMED) if k in t}
    return {k: t[k] for k in ("description", "mono", "copyright") if k in t} | ({"colors": c} if c else {})


def theme_mark(name, t):
    """テーマ t の目印（THEME_MARK）。名前と theme_extras の JSON。"""
    return f"ai-deck-factory theme={name} " + json.dumps(theme_extras(t), ensure_ascii=False, separators=(",", ":"))


def theme_file(t):
    """テーマの表 t を、テーマのファイルの形（apiVersion・kind と colors の入れ子）にする（read_theme の逆）。"""
    out = {"apiVersion": API_VERSION, "kind": "theme"}
    for k in THEME_KEYS:
        if k == "colors":
            if colors := {c: t[c] for c in (*ROLE, *FIXED, *NAMED) if c in t}:
                out[k] = colors
        elif k in t:
            out[k] = t[k]
    return out


def theme_from(p):
    """[slides-component-019] プレゼン p（masters・layouts）が持つテーマの表（read_theme の形）。役割の色はマスターの配色、書体はマスターのプレースホルダー、
    表紙・扉はレイアウトの目印と名前、ほかはテーマの目印の JSON から読む。画面のテーマビルダーで替えた色と書体も入る。slides.py theme がテーマのファイルに戻し、
    theme_diff がテーマのファイルと比べる。ponytail: 表紙・扉の番号が飛んでいる（レイアウトを手で消した）デッキは、詰めた番号になる。"""
    sch, t = scheme(p), mark_values(p)
    t |= {"font": deck_font(p)} | {r: sch[s] for r, s in ROLE.items() if s in sch}
    for l, m in sorted(layout_marks(p), key=lambda x: (x[1].group(1), int(x[1].group(2)))):
        t.setdefault(m.group(1), []).append({"layout": l.get("layoutProperties", {}).get("displayName", ""),
                                             **({"w": float(m.group(3))} if m.group(3) else {}), "tone": m.group(4) or "dark"})
    return t


def theme_pages(name, t):
    """テーマ t を当てたテンプレートの masters・layouts（presentations.get の形。マスターと Blank と表紙・扉のパターン）。lint・dry が Google を読まずに見る。
    theme_from で読むと t に戻る（書いていない値は埋まる）。"""
    font = theme_font(t)
    num = lambda oid, desc: {"objectId": oid, "description": desc, "shape": {"placeholder": {"type": "SLIDE_NUMBER"},
                                                                             "text": {"textElements": [{"textRun": {"content": "\n", "style": {"fontFamily": font}}}]}}}
    lay = lambda oid, title, desc, fill=None: {"objectId": oid, "layoutProperties": {"displayName": title, "masterObjectId": "theme_m"}, "pageElements": [num(oid + "_n", desc)],
                                               **({"pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"themeColor": fill}}}}} if fill else {})}
    # ponytail: 表紙・扉の地は、地の明るさの代表の色（dark は NAVY、accent は RED、light は BG）で塗る。写真や図形の地は見ない（lint のコントラストはその色で見る）
    tone = {"dark": NAVY, "accent": RED, "light": BG}
    return {"masters": [{"objectId": "theme_m", "pageProperties": {"colorScheme": {"colors": [{"type": k, "color": rgb(v)} for k, v in theme_slots(t).items()]}},
                         "pageElements": [num("theme_m_n", theme_mark(name, t))]}],
            "layouts": [lay("theme_blank", BLANK, theme_mark(name, t))] + [lay(f"theme_{k}{i}", l["layout"], layout_mark(k, i, l), tone[l.get("tone", "dark")])
                                                                         for k in ("cover", "section") for i, l in enumerate(t.get(k, []), 1)]}


def deck_parts(p):
    """デッキ p の (マスター, Blank のレイアウト, {"cover"・"section": [レイアウト, …]}（番号の順）)。テーマを当てる枠（theme_reqs）。Blank がなければ None。"""
    marked = {l["objectId"] for l, _ in layout_marks(p)}
    ls = [l for l in p.get("layouts", []) if is_blank(l) and l["objectId"] not in marked]
    blank = next((l for l in ls if l.get("layoutProperties", {}).get("displayName") == BLANK), ls[0] if ls else None)
    extras = {}
    for l, m in sorted(layout_marks(p), key=lambda x: int(x[1].group(2))):
        extras.setdefault(m.group(1), []).append(l)
    return p["masters"][0], blank, extras


def theme_reqs(name, t, master, blank, extras):
    """マスター master と、レイアウト blank・表紙と扉のパターン extras（{"cover"・"section": [レイアウト, …]}）を、テーマ t の配色・書体・目印にする要求。
    目印はページ番号の枠の代替テキストに書く（マスターと Blank にテーマの目印、表紙・扉に t の cover・section の目印）。template.py と build が送る。"""
    font = theme_font(t)
    reqs = [{"updatePageProperties": {"objectId": master["objectId"], "pageProperties": {"colorScheme": {"colors": [
        {"type": k, "color": rgb(v)} for k, v in theme_slots(t).items()]}}, "fields": "colorScheme.colors"}}]
    marks = {}
    for pg in (master, blank):
        for e in (pg or {}).get("pageElements", []):
            if placeholders({"pageElements": [e]}) == ["SLIDE_NUMBER"]:
                marks[e["objectId"]] = theme_mark(name, t)
    for k, ls in extras.items():
        for i, (l, v) in enumerate(zip(ls, t.get(k, [])), 1):  # 目印はページ番号の枠に書く（2 つ目は template.py の strip が消した。pick が枠のあるレイアウトだけを選ぶ）
            if e := next((e for e in l.get("pageElements", []) if placeholders({"pageElements": [e]}) == ["SLIDE_NUMBER"]), None):
                marks[e["objectId"]] = layout_mark(k, i, v)
    for pg in (master, blank, *(l for ls in extras.values() for l in ls)):
        for e in (pg or {}).get("pageElements", []):
            if not (ph := e.get("shape", {}).get("placeholder", {}).get("type")) or pg not in (master, blank) and e["objectId"] not in marks:
                continue  # 表紙・扉のほかの枠は template.py の strip が消した
            reqs.append({"updateTextStyle": {"objectId": e["objectId"], "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}})
            if ph == "SLIDE_NUMBER":
                reqs.append({"updatePageElementAltText": {"objectId": e["objectId"], "description": marks[e["objectId"]]}})
    return reqs


DECK_FIELDS = ("masters(objectId,pageProperties,pageElements(objectId,description,shape)),"
               "layouts(objectId,layoutProperties,pageElements(objectId,description,shape(placeholder)))")  # テーマを読む・当てるのに要るもの（theme_from・theme_reqs）


def theme_diff(name, t, p):
    """[slides-component-020] デッキ p（DECK_FIELDS）のマスターとテーマのファイルの値 t の違い（値の違うキーの並び。同じなら []）。build がマスターをそろえる（theme_reqs）。
    デッキを作ったあとでテーマのファイルを直しても、組み直せば新しい値になる（役割の色はマスターの色を指すので、組み直さないページも替わる）。
    表紙・扉のパターンが違えば止める（図形やロゴはテンプレートのレイアウトにしかない。template.py で合わせ直し、new で作り直す）。"""
    want, have = theme_from(theme_pages(name, t)), theme_from(p)
    if want == have:
        return []
    pats = lambda x: {k: [l["layout"] for l in x.get(k, [])] for k in ("cover", "section")}
    if pats(want) != pats(have):
        sys.exit(f"テーマ {name} の表紙・扉のパターン {pats(want)} が、デッキのもの {pats(have)} と違う。マスターの色と書体だけでは合わせられないので、"
                 f"template.py {name} でテンプレートを合わせ直し、slides.py new で作り直す")
    if bare := [l["layout"] for k in ("cover", "section") for l in t.get(k, []) if "tone" not in l]:  # 地の明るさはレイアウトの図形から測る。黙って dark にしない
        sys.exit(f"テーマ {name} のファイルの表紙・扉「{'」「'.join(bare)}」に地の明るさ（tone）がない。template.py {name} で測って書き込んでから組む")
    return [k for k in dict.fromkeys([*want, *have]) if want.get(k) != have.get(k)]


def templates():
    """テーマごとのテンプレートの ID（factory.toml の [slides.templates] の「名前 = URL」）。"""
    return {k: file_id(u) for k, u in factory().get("slides", {}).get("templates", {}).items() if u} if gapi.find_factory() else {}


def set_template(text, name, url):
    """factory.toml の文字列の [slides.templates] の name の行を url にする（なければ表の頭に足し、表もなければファイルの最後に足す）。コメントと並びはそのまま。"""
    text = text if text.endswith("\n") else text + "\n"  # 見出しがファイルの最後の行でも見つける
    m = re.search(r"^\[slides\.templates\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.S | re.M)
    if not m:
        return text.rstrip("\n") + f'\n\n[slides.templates]\n{name} = "{url}"\n'
    line = re.compile(rf'^{re.escape(name)}\s*=\s*"[^"]*"', re.M)
    body = line.sub(f'{name} = "{url}"', m.group(1), count=1) if line.search(m.group(1)) else f'{name} = "{url}"\n' + m.group(1)
    return text[:m.start(1)] + body + text[m.end(1):]


def record_template(name, pid=None):
    """テンプレートの URL を factory.toml の [slides.templates] に書く。書いたあとの TOML が読めて、URL が入っていることを確かめてから書く（壊さない）。
    pid が None なら、書けるかだけを確かめる（template.py --from-base が複製する前に呼ぶ。書けないのに Drive に複製を残さない）。"""
    p, url = gapi.factory_path(), f"https://docs.google.com/presentation/d/{pid or 'CHECK'}/edit"
    text = set_template(p.read_text(), name, url)
    try:
        ok = tomllib.loads(text)["slides"]["templates"][name] == url
    except (tomllib.TOMLDecodeError, KeyError):
        ok = False
    if not ok:
        sys.exit(f"factory.toml の [slides.templates] に {name} を書けない（見出しの書き方が違うかもしれない。[slides.templates] の形にする）"
                 + (f"。テンプレートは {url}。手で {name} = \"{url}\" を書く" if pid else "。テンプレートはまだ作っていない"))
    if pid:
        p.write_text(text)


def theme_files(folder, named=True):
    """Drive のフォルダ folder（ID）の Google Slides のうち、template.py がテーマの名前（THEME_PROP）を書いたもの（named が False なら全部）。新しい順。"""
    q = urllib.parse.urlencode({"q": f"'{folder}' in parents and mimeType = '{GSLIDES}' and trashed = false", "orderBy": "modifiedTime desc", "pageSize": 1000,
                                "fields": "files(id,description,properties)", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true", "corpora": "allDrives"})
    return [f for f in request("GET", f"{DRIVE}/files?{q}")["files"] if not named or (f.get("properties") or {}).get(THEME_PROP)]


@functools.cache
def shared_files():
    """[drive] shared_themes（全社の共有テーマのフォルダ）のテンプレート（theme_files）。書いていなければ []。
    探すときだけ読む（使うテーマは slides.py theme <URL> でワークスペースに写す）。"""
    if not (gapi.find_factory() and (f := factory().get("drive", {}).get("shared_themes"))):
        return []
    return theme_files(folder_id(f))


def find_themes_folder(root):
    """[drive] factory（root）の下の Themes の ID。なければ None（作るのは template.py の themes_folder）。"""
    return gapi.subfolder(root, THEMES_DIR)


@functools.cache
def own_files():
    """[drive] factory の下の Themes（template.py --from-base がテンプレートを作るフォルダ）のテンプレート（theme_files）。なければ []（作らない）。"""
    if not (gapi.find_factory() and (root := factory().get("drive", {}).get("factory"))):
        return []
    return theme_files(f) if (f := find_themes_folder(root)) else []


def unlisted():
    """共有テーマのフォルダと自分の Themes にあって、[slides.templates] が指していないテンプレート。[(テーマの名前, url, 説明, どこ)]（どこは 共有・個人。新しい順）。
    自分の Themes は、[slides.templates] にない名前の、いちばん新しいものだけ（--from-base で作り直す前の古いテンプレートを出さない）。同じファイルが両方にあれば共有（管理者が自分の Themes を共有のフォルダにしたとき。名前が同じでも別のファイルなら両方出す）。
    探すためだけなので、フォルダを読めなければ知らせて飛ばす（themes と new を止めない）。"""
    seen, own_skip, rows = set(templates().values()), set(templates()), []  # own_skip: 自分の Themes で出さない名前（テンプレートがある・もう出した）
    for where, folder, get in (("共有", "[drive] shared_themes", shared_files), ("個人", f"[drive] factory の下の {THEMES_DIR}", own_files)):
        try:
            files = get()
        except READ_ERRORS as e:
            print(f"{folder} を読めない（そこのテーマを候補に出さない）: {str(e).splitlines()[0]}", file=sys.stderr)
            continue
        for f in files:
            name = f["properties"][THEME_PROP]
            if f["id"] in seen or where == "個人" and name in own_skip:
                continue
            seen.add(f["id"])
            if where == "個人":
                own_skip.add(name)
            rows.append((name, f"https://docs.google.com/presentation/d/{f['id']}/edit", f.get("description", ""), where))
    return rows


def theme_fixed(t):
    """テーマの表 t の固定の色（名前 → 6 桁）。FIXED は書いていなければ既定の値、NAMED は書いたものだけ。"""
    if bad := [k for k in (*FIXED, *NAMED) if k in t and not re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(t[k]))]:
        sys.exit(f"テーマの {', '.join(bad)} が 6 桁の 16 進の色でない（例: \"TEXT\": \"37352F\"）")
    return {k: str(t.get(k, v)).lstrip("#").upper() for k, v in FIXED.items()} | {k: str(t[k]).lstrip("#").upper() for k in NAMED if k in t}


def theme_values(t):
    """テーマの表 t の、組むときに引く値（固定の色, 著作権表示, 等幅の書体）。書いていなければ今の値。書けない値なら止める。"""
    c = t.get("copyright", BRAND_COPYRIGHT)
    if "copyright" in t and not isinstance(c, str):  # [brand] の値は need_brand と factory-doctor が見る
        sys.exit(f"テーマの copyright {c!r} は文字列でない（例: \"copyright\": \"© 2026 Acme, Inc. All rights reserved.\"）")
    return theme_fixed(t), c, theme_mono(t)


def use_theme(t):
    """テーマの表 t（read_theme・theme_from）の固定の色・著作権表示・等幅の書体で組む。make_deck の前に呼ぶ（pages.py が作る要求に効かせる）。"""
    global COPYRIGHT, MONO
    colors, COPYRIGHT, MONO = theme_values(t)
    _SWAP.clear()
    _SWAP.update({FIXED[k]: colors[k] for k in FIXED if colors[k] != FIXED[k]})
    _NAMED.clear()
    _NAMED.update({k: colors[k] for k in NAMED if k in colors})


def deck_mono(p):
    """デッキの等幅の書体（デッキのテーマの mono。lint が比べる）。マスターにコードの枠がないので、テーマの目印の値から引く。"""
    return theme_mono(mark_values(p))


def deck_card(p):
    """デッキのカードの地の 6 桁（デッキのテーマの CARD。書かなければ白）。lint と box_pad がカードを見分ける。"""
    return theme_fixed(mark_values(p)).get(CARD, WHITE)


def need_mark(want, mark):
    """new で、選んだテーマ want のテンプレートが、そのテーマの目印 mark を持つか。違えば止める（複製したデッキは目印のテーマで組み直すので、ここでそろえる）。
    値が違っても止めない（組むときに build がテーマのファイルの値にそろえる）。"""
    if mark != want:
        sys.exit(f"テーマ {want} のテンプレートは" + ("、テーマの名前を持たない（template.py で合わせ直す前のもの）" if mark is None else
                                                f"、テーマ {mark} の名前を持つ（[slides.templates] の URL が同じか、template.py {mark} で合わせ直した）")
                 + f"。テーマごとにテンプレートを分け、template.py {want} で合わせ直す")


def use_pages(p):
    """表紙・扉のパターン（use_layouts）、アイコンの色の配色（use_palette）、字幅の見積もりの書体（use_font）を、デッキか theme_pages の p から決める。"""
    use_layouts(p)
    use_palette(p)
    use_font(deck_font(p))


def deck_context(path, url=None):
    """組む・見るデッキのテーマを決める（make_deck の前に呼ぶ）。テーマは deck.json の theme、なければ url のデッキの目印、なければ既定のテーマ
    （deck.json の theme のファイルがあれば、url のデッキは読まない）。
    テーマのファイルがあればその値で（Google を読まない。url のデッキも組むときにこの値にそろう）、なければ url のデッキが持つ値で組む。
    戻り: (テーマの名前, テーマの表, presentations.get の形の masters・layouts)。"""
    want, p = declared_theme(path), None
    if url and load_theme(want) is None:  # deck.json の theme のファイルがあれば、URL のデッキは読まない（認証が切れていても、手元だけで見る）
        p = request("GET", f"{SLIDES}/{file_id(url)}?fields=title,{DECK_FIELDS}")
        need_deck_theme(want, deck_theme(p))
    name = want or (deck_theme(p) if p else None) or default_theme()
    if (t := load_theme(name)) is not None:
        p = {"title": (p or {}).get("title", ""), **theme_pages(name, t)}
    elif p is None:
        sys.exit(f"テーマ {name} のファイルがない（{', '.join(theme_names())}。ワークスペースの themes/slides/{name}.json に書くか、slides.py theme <テンプレートの URL> で写す）")
    else:
        t = theme_from(p)
    use_pages(p)
    use_theme(t)
    return name, t, p


def resolved(deck, p):
    """deck の要求に、デッキ p（layouts・masters）の書体と、Blank・表紙・扉のレイアウトの ID を入れたもの（JSON の文字列）。build が送り、lint が手元で組む。"""
    kinds = {l["objectId"]: f"@{k.upper()}{n}" for (k, n), l in deck_layouts(p).items()}  # 表紙・扉のパターンのレイアウト（template.py が残したもの）
    ls = [l for l in p["layouts"] if is_blank(l) and l["objectId"] not in kinds]  # 会社のテンプレートから作ったものは、template.py が残した Blank が 1 つだけ（名前は会社のもの）
    layout = next((l["objectId"] for l in ls if l["layoutProperties"]["displayName"] == BLANK), ls[0]["objectId"] if len(p["layouts"]) == len(kinds) + 1 and ls else None)
    if not layout:
        sys.exit(f"レイアウト「{BLANK}」がない。AI Deck Factory のテンプレートから作ったプレゼンではない（slides.py new で作る）")
    lay = {"@LAYOUT": layout} | {k: i for i, k in kinds.items()}
    if miss := sorted(set(re.findall(r'"(@(?:COVER|SECTION)\d+)"', json.dumps(deck.reqs))) - set(lay)):
        sys.exit(f"デッキに表紙・扉のパターン {', '.join(miss)} のレイアウトがない（テンプレートを作り直す前に複製したデッキ）。番号を変えるか、slides.py new で作り直す")
    return re.sub(r'"(@LAYOUT|@COVER\d+|@SECTION\d+)"', lambda m: json.dumps(lay[m.group(1)]), json.dumps(refont(deck.reqs, deck_font(p))))


PAGE_HASH = re.compile(r"h([0-9a-f]{16})$")  # build がページの ID の末尾に付ける、中身のハッシュ


def pages_of(deck, reqs):
    """(要求ごとの持ち主のページ, ページごとの中身のハッシュ, ページごとのリンク先のページ, ノートも入れたハッシュ)。build が、変わったページだけを作り直すのに使う。
    ハッシュは、そのページの要求の ID を出てくる順の番号に、手元の画像を中身のハッシュに置き換えて取る（組むたびに変わる ID で変わらない）。
    ページへのリンクは、リンクの場所にリンク先のハッシュを入れる。ノートは入れない（ノートだけ変わったページは、build が残してノートを書き換える）。
    ノートも入れたハッシュは、2026-10-23 より前の build が ID に付けたもの（そのページを残すため）と、lint の変わったページ。"""
    own, owner, per, links = {}, [], defaultdict(list), defaultdict(set)
    for r in reqs:
        (k, v), = r.items()
        o = v.get("objectId", v.get("groupObjectId"))
        if k == "createSlide":
            pg = own[o] = own[o + "_n"] = o
        elif "elementProperties" in v:
            pg = own[o] = v["elementProperties"]["pageObjectId"]
        elif k == "groupObjects":
            pg = own[o] = own[v["childrenObjectIds"][0]]
        else:
            pg = own[o]
        owner.append(pg)
        per[pg].append(r)
        if t := v.get("style", {}).get("link", {}).get("pageObjectId"):
            links[pg].add(t)
    files = {}

    def img(m):  # 手元の画像は中身のハッシュにする（同じパスのまま中身を替えても作り直す）
        f = deck.images[int(m.group(1))]
        if f not in files:
            files[f] = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        return json.dumps(f"@IMG:{files[f]}")

    sha = lambda t: hashlib.sha256(t.encode()).hexdigest()
    body = {}
    for s in deck.slides:
        ids = {}
        b = re.sub(r'"link": \{"pageObjectId": "([^"]+)"\}', r'"link": {"pageObjectId": "@LINK:\1"}', json.dumps(per[s], sort_keys=True))  # リンク先は下でハッシュにする
        b = re.sub(rf'"{deck.run}_\d+', lambda m: '"#' + str(ids.setdefault(m.group(), len(ids))), b)
        body[s] = re.sub(r'"@IMG(\d+)"', img, b)

    keys = {sid: page_key(n) for n, sid in deck.page_names.items()}

    def digest(notes):  # リンク先のページのハッシュを、リンクの出てくる場所に入れる（リンク先が変われば、リンク元も変わる。1 ページの中でリンク先を入れ替えても変わる）
        b = {s: body[s] + (json.dumps(deck.notes.get(s)) if notes else "") for s in deck.slides}
        base = {s: sha(re.sub(r'@LINK:[^"]+', "@LINK", b[s])) for s in deck.slides}
        # JSON のページへのリンクは、ファイル名の印も入れる（ノートだけ違う同じ見た目のページのどれへのリンクかを分ける。前の build のハッシュには入れない）
        return {s: sha(re.sub(r'@LINK:([^"]+)', lambda m: base[m.group(1)] + ("" if notes else keys.get(m.group(1), "")), b[s]))[:16] for s in deck.slides}
    return owner, digest(False), links, digest(True)


def notes_of(slides):
    """ページの番号（"1" から）→ スピーカーノートの文字（末尾の改行は落とす。Slides が読み返すときに付ける）。"""
    import lint
    return {str(i): lint.note_text(s).rstrip("\n") for i, s in enumerate(slides, 1)}


def note_reqs(slides, script, font):
    """ノートを script（ページの番号 → 文字。None のページは触らない）に書き換える要求。変わらないページは書かない。"""
    reqs, before = [], notes_of(slides)
    for i, s in enumerate(slides, 1):
        if (t := script[str(i)]) is None or t == before[str(i)]:
            continue
        nid = s["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]  # 枠がまだなくても、insertText が作る
        if before[str(i)]:
            reqs.append({"deleteText": {"objectId": nid, "textRange": {"type": "ALL"}}})
        if t:
            reqs += [{"insertText": {"objectId": nid, "insertionIndex": 0, "text": t}},
                     {"updateTextStyle": {"objectId": nid, "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}}]
    return reqs


PAGE_KEY = re.compile(r"k([0-9a-f]{8})h[0-9a-f]{16}$")  # JSON のページのファイル名の印（page_key）。中身のハッシュの前に入れる


def page_key(name):
    """JSON のページのファイル名 name の印（8 けた）。並べ替えても中身が変わっても、前に組んだ同じページのスライドを探せる（ファイルを選んで組むとき）。"""
    return hashlib.sha1(name.encode()).hexdigest()[:8]


def build_plan(pid, deck, force=False, theme=None, only=None):
    """[slides-component-016] build が送るもの（まだ送らない。slides.py plan はこれを出すだけ）。変わったページだけを作り直す。ページの ID の末尾に中身のハッシュ（pages_of）を付け、
    デッキに同じハッシュのページがあれば残して並べ替えるだけにする。ハッシュのないページ（前の版の build で組んだもの、画面で足したもの）は消して作り直す。
    force なら、全ページを作り直す（画面での直しも消す）。theme（(名前, テーマの表)）があれば、マスターとの違い（theme_diff）を出し、書いたあとの書体で組む。
    only（ページの名前の集合）を渡すと、ほかのページは前に組んだスライドを残す（中身が変わっていても。そのページへのリンクを作り直すときと、前に組んでいないときは作る）。"""
    p = request("GET", f"{SLIDES}/{pid}?fields=slides(objectId),{DECK_FIELDS}")
    gapi.CLOCK.lap("GET")
    themed = theme_diff(*theme, p) if theme else []
    q = {**p, "masters": theme_pages(*theme)["masters"]} if themed else p  # マスターをテーマの値にしたあとの書体
    reqs = json.loads(resolved(deck, q))
    owner, digest, links, full = pages_of(deck, reqs)
    olds, have, keep = [s["objectId"] for s in p.get("slides", [])], defaultdict(list), {}
    for o in olds if not force else []:
        if m := PAGE_HASH.search(o):
            have[m.group(1)].append(o)
    new_n = Counter(digest.values())
    twins = {h for h in new_n if new_n[h] > 1 or len(have[h]) > 1}  # 中身の同じページ（今の pages.py か、前に組んだデッキに 2 枚以上）
    twins |= {digest[s] for s in deck.slides if len(have[full[s]]) > 1}  # 前の build の ID（ノートも入れたハッシュ）で 2 枚以上
    names = {sid: n for n, sid in deck.page_names.items()}
    key = lambda o: m.group(1) if (m := PAGE_KEY.search(o)) else None
    by_key, claimed, frozen = {k: o for o in olds if (k := key(o))}, set(), set()
    if only is not None:  # 選んでいないページは、先に前に組んだ同じページ（ファイル名の印）を取る（同じ中身のほかのページに、ハッシュで取られないように）
        for s in deck.slides:
            if s in names and names[s] not in only and (o := by_key.get(page_key(names[s]))):
                keep[s] = o
                claimed.add(o)
                if PAGE_HASH.search(o).group(1) not in (digest[s], full[s]):
                    frozen.add(s)
    # 中身のハッシュが同じ前のページを残す。同じファイル名の印のものを、先に全ページで選ぶ（同じ中身のページが 2 枚以上あっても、どれも元のページに戻す）
    for by_name in (True, False):
        for s in deck.slides:
            if s not in keep and (cands := [o for o in have[digest[s]] + have[full[s]] if o not in claimed]):
                if o := next((o for o in cands if s in names and key(o) == page_key(names[s])), None if by_name else cands[0]):
                    keep[s] = o
                    claimed.add(o)
    chose = lambda s: only is None or names.get(s) in only
    # 中身の同じページのどれへのリンクかはハッシュで分からないので、リンク元を作り直す。JSON のページは、印で元のページに戻り、リンクのハッシュにも印が入るので要らない
    # （前の build の ID で残したリンク元は、ハッシュに印がないので作り直す。選んでいないページは前のリンクのまま）
    told = lambda s, t: t in names and PAGE_HASH.search(keep[s]).group(1) == digest[s]
    for s in [s for s in keep if chose(s) and any(digest[t] in twins and not told(s, t) for t in links[s])]:
        keep.pop(s)
    # 前のまま残すページは、前の中身のリンク（デッキから読む）で見る。今の中身のリンク（links）とは違うことがある
    old_links = {sl["objectId"]: set(re.findall(r'"pageObjectId": "([^"]+)"', json.dumps(sl)))
                 for sl in request("GET", f"{SLIDES}/{pid}?fields=slides(objectId,pageElements)").get("slides", [])} if frozen else {}
    gone = lambda s: old_links.get(keep[s], set()) - set(keep.values()) if s in frozen else links[s] - set(keep)
    while lost := [s for s in keep if gone(s)]:  # 作り直すページ・消すページへのリンクは、新しい ID を指すように、リンク元も作り直す
        for s in lost:
            keep.pop(s)
    ids = {s: keep.get(s, f"{s}{'k' + page_key(names[s]) if s in names else ''}h{digest[s]}") for s in deck.slides}
    body = json.dumps([r for r, o in zip(reqs, owner) if o not in keep])
    body = re.sub(rf'"({deck.run}_\d+)(_n)?"', lambda m: f'"{ids.get(m.group(1), m.group(1))}{m.group(2) or ""}"', body)
    # 新しいページを先に作ってから、前のページを消す。ページが 0 枚になると、使われていないマスターごと消える
    old = [{"deleteObject": {"objectId": o}} for o in olds if o not in keep.values()]
    made = [ids[r["createSlide"]["objectId"]] for r in reqs if "createSlide" in r and r["createSlide"]["objectId"] not in keep]  # 作った順に末尾へ足される
    cur, moves = [o for o in olds if o in keep.values()] + made, []
    for k, o in enumerate(ids[s] for s in deck.slides):  # 前から 1 枚ずつ置く（まとめて動かすと、元の順のまま動く。gslides.py keep と同じ）
        if cur[k] != o:
            moves.append({"updateSlidesPosition": {"slideObjectIds": [o], "insertionIndex": k}})
            cur.remove(o)
            cur.insert(k, o)
    gapi.CLOCK.lap("差分を出す")
    return types.SimpleNamespace(p=p, themed=themed, font=deck_font(q), ids=ids, keep=keep, frozen=frozen & set(keep), body=body, old=old, moves=moves,
                                 rebuilt=[i for i, s in enumerate(deck.slides, 1) if s not in keep])


def build(pid, deck, force=False, theme=None, only=None):
    """pid のプレゼンのページを、deck のページに置き換える（build_plan のとおりに送る）。force=False なら、先に guard で画面での直しとコメントを確かめる。
    theme を渡すと、確かめたあとでマスターをその値にそろえる（先に書くと、自分の書いた版を画面での直しと取り違える）。"""
    need_brand()
    if not force:
        gapi.guard(pid, revision(pid), STAMP, "ページのファイル（deck.json・pages.py）")
        gapi.CLOCK.lap("画面の直しの確かめ")
    x = build_plan(pid, deck, force, theme, only)
    ids, keep, body, old, moves, font = x.ids, x.keep, x.body, x.old, x.moves, x.font
    if x.themed:
        batch(pid, theme_reqs(*theme, *deck_parts(x.p)))
        if not force:  # 自分の書き込みの版を残す（このあとページを組めずに止まっても、次の build が画面での直しと取り違えない）
            gapi.stamp(pid, revision(pid), STAMP)
        if os.path.exists(shots := f"/tmp/slides_{pid[:8]}/shots.json"):  # ID の変わらないページも色が替わるので、gslides.py check が前の画像を使わずに全ページを取る
            os.remove(shots)
        print(f"テーマ {theme[0]} のファイルの値（{'・'.join(x.themed)}）を、デッキのマスターに書いた", file=sys.stderr)
    carrier = None
    try:
        if used := sorted({int(i) for i in re.findall(r'"@IMG(\d+)"', body)}):  # 作り直すページの手元の画像だけを運ぶ
            urls, carrier = carry([deck.images[i] for i in used])
            body = re.sub(r'"@IMG(\d+)"', lambda m: json.dumps(urls[used.index(int(m.group(1)))]), body)
            gapi.CLOCK.lap("手元の画像を運ぶ")
        send = json.loads(body) + old + moves
        batch(pid, send)
        gapi.CLOCK.lap(f"batchUpdate（{len(send)} 件）")
    finally:
        if carrier:  # 貼った画像はデッキの中に写し取られているので、仮のファイルは消してよい
            delete(carrier)
    # ノートは 2 回目に書く（作ったページのノートの枠は、作ったあとでないと ID が分からない）。残したページも、ノートが変わっていれば書き換える（ノートはハッシュに入れない）
    p = request("GET", f"{SLIDES}/{pid}?fields=slides(objectId,slideProperties(notesPage(notesProperties,pageElements(objectId,shape(text)))))")
    names = {sid: n for n, sid in deck.page_names.items()}
    skip = lambda s: s in keep and only is not None and names.get(s) not in only  # 選んでいないページは、ノートも前のまま
    want = {str(i): None if skip(s) else (deck.notes.get(s) or "").rstrip("\n") for i, s in enumerate(deck.slides, 1)}
    before = notes_of(p["slides"])
    renoted = [i for i, s in enumerate(deck.slides, 1) if s in keep and want[str(i)] not in (None, before[str(i)])]  # 残したページで、ノートを書き換えたもの
    if nreqs := note_reqs(p["slides"], want, font):
        batch(pid, nreqs)
    gapi.CLOCK.lap("ノート（GET と batchUpdate）")
    gapi.stamp(pid, revision(pid), STAMP)
    gapi.CLOCK.lap("版の記録")
    d = f"/tmp/slides_{pid[:8]}"  # gslides.py check と同じフォルダ。画像は check が取り、同じファイルに画像のパスと指摘を足して書き直す
    os.makedirs(d, exist_ok=True)
    json.dump({"url": f"https://docs.google.com/presentation/d/{pid}/edit", "by": "build", "slides": len(deck.slides),
               "pages": [{"page": i, "objectId": ids[s]} for i, s in enumerate(deck.slides, 1) if s not in keep]}, open(f"{d}/changed.json", "w"), indent=1)
    print(json.dumps({"presentationId": pid, "url": f"https://docs.google.com/presentation/d/{pid}/edit",
                      "slides": len(deck.slides), "rebuilt": x.rebuilt, "frozen": [i for i, s in enumerate(deck.slides, 1) if s in x.frozen], "removed": len(old),
                      "requests": len(send) + len(nreqs), "notes_rewritten": renoted,
                      "warnings": len(deck.warnings)}, ensure_ascii=False))
    gapi.CLOCK.show("build ")


def chosen(files, deck, mark):
    """build・plan に渡したファイル（JSON のページ・デッキ・テーマのファイル）の、ページの名前の集合（build_plan の only）。テーマのファイルはページを選ばない
    （テーマはデッキ全体のものなので、渡さなくても違えばそろえる。テーマのファイルだけを渡すと、マスターだけを書く）。"""
    if not deck.page_names:
        sys.exit("ファイルを選んで組めるのは JSON のページのデッキだけ（pages.py のデッキは、ファイルを渡さずに組む）")
    names = set()
    for f in files:
        if (kind := file_kind(f)) == "theme":
            if not (want := theme_path(mark)) or Path(f).resolve() != want.resolve():  # そろえるのはデッキのテーマのファイル（load_theme）。別のファイルを渡して違う値を当てたと思わせない
                sys.exit(f"{f}: デッキのテーマのファイルは {want or f'（{mark} のファイルがない）'}（テーマを替えるなら slides.py new で作り直す）")
        elif kind in ("page", "deck"):
            names |= {n for _, _, _, n in spec_files(f) if n}
        else:
            sys.exit(f"{f}: 読めないか、JSON のページ・デッキ・テーマのファイルでない（選べるのはその 3 つ）")
    if miss := sorted(names - set(deck.page_names)):
        sys.exit(f"{'・'.join(miss)} は deck.json に並んでいない")
    return names


def cmd_plan(pid, deck, theme, only):
    """[slides-component-023] slides.py plan: build が送るもの（build_plan）と、画面での直し・コメント（あれば build は止まる）を出す。Google には書かない。
    rebuild は作り直す・作るページ、frozen は中身が変わったが選んでいないので前のまま残すページ（番号はデッキの何枚目）。"""
    screen = gapi.guard(pid, revision(pid), STAMP, "pages.py", stop=False) or []
    x = build_plan(pid, deck, False, theme, only)
    print(json.dumps({"presentationId": pid, "theme": x.themed, "rebuild": x.rebuilt, "frozen": [i for i, s in enumerate(deck.slides, 1) if s in x.frozen],
                      "kept": len(x.keep) - len(x.frozen), "remove": len(x.old), "moves": len(x.moves), "screen": screen}, ensure_ascii=False))


def local_json(reqs, deck, p):
    """[slides-component-017] 組む要求 reqs（resolved）を、Google を呼ばずに presentations.get の JSON の形にする（slides.py lint が lint をかける）。p はデッキの masters・layouts。
    表の大きさは、Google と同じく 3,000,000 EMU の正方形にする（presentations.get の表は、行と列の大きさを要素の大きさに持たない）。
    Google が描いてから決まるもの（画像の縦横の比に合わせた枠、ページ番号の枠、実際の折り返し）は入らない。"""
    master = {l["objectId"]: l.get("layoutProperties", {}).get("masterObjectId") for l in p.get("layouts", [])}
    slides, els, texts = [], {}, {}  # els: ID → (要素, 入っている並び)。texts: (ID, 行, 列) → [文字, 文字の書式, 段落の書式]（UTF-16 の 1 単位に 1 つ）

    def merge(d, style, fields):
        for f in fields.split(","):
            d.pop(f, None)
            if f in style:
                d[f] = style[f]

    def span(t, rng):
        return (0, len(t)) if rng.get("type") == "ALL" else (rng.get("startIndex", 0), rng.get("endIndex", len(t)))

    def paras(t, rng):  # 範囲にかかる段落の終わりの改行
        a, b = span(t, rng)
        ends = [j for j, c in enumerate(t) if c[0] == "\n"]
        return [t[j] for i, j in enumerate(ends) if (ends[i - 1] + 1 if i else 0) < max(b, a + 1) and j >= a]

    def emit(t):
        out, start = [], 0
        for j, (c, _, ps) in enumerate(t):
            if c == "\n":
                ps = dict(ps)
                out.append({"paragraphMarker": {"style": ps, **({"bullet": {}} if ps.pop("_bullet", False) else {})}})
                for st, g in itertools.groupby(t[start:j + 1], key=lambda x: json.dumps(x[1], sort_keys=True)):
                    out.append({"textRun": {"content": "".join(x[0] for x in g), "style": json.loads(st)}})
                start = j + 1
        return {"textElements": out}

    for r in reqs:
        (k, v), = r.items()
        o, key = v.get("objectId"), (v.get("objectId"), *((v["cellLocation"].get("rowIndex", 0), v["cellLocation"].get("columnIndex", 0)) if "cellLocation" in v else ()))
        if k == "createSlide":
            lid = v["slideLayoutReference"]["layoutId"]
            slides.append({"objectId": o, "pageElements": [], "pageProperties": {}, "slideProperties": {"layoutObjectId": lid, "masterObjectId": master.get(lid)}})
            els[o] = (slides[-1], None)
        elif k in ("createShape", "createLine", "createImage", "createTable"):
            ep = v["elementProperties"]
            e = {"objectId": o, "size": ep["size"], "transform": ep["transform"]}
            if k in ("createShape", "createLine"):  # Google は図形と線を 3,000,000 EMU の正方形の縮尺で返し、縮尺を小数 4 けたに丸める（箱の端に載った要素の内外が変わる）
                sq, t = {"magnitude": 3000000, "unit": "EMU"}, dict(ep["transform"])
                for a, d in (("scaleX", "width"), ("scaleY", "height")):
                    t[a] = round(t[a] * ep["size"][d]["magnitude"] / 3000000, 4)
                    if not t[a]:
                        del t[a]  # 0 の値は省く（lint の flatten の読み方）
                e |= {"size": {"width": sq, "height": sq}, "transform": t}
            if k == "createShape":
                e["shape"] = {"shapeType": v["shapeType"], "shapeProperties": {}}
            elif k == "createLine":
                e["line"] = {"lineCategory": v["category"], "lineProperties": {}}
            elif k == "createImage":
                e["image"] = {"contentUrl": v["url"]}
            else:
                e |= {"size": {"width": {"magnitude": 3000000, "unit": "EMU"}, "height": {"magnitude": 3000000, "unit": "EMU"}},
                      "transform": {**ep["transform"], "scaleX": 1, "scaleY": 1},
                      "table": {"rows": v["rows"], "columns": v["columns"], "tableRows": [{"tableCells": [{"location": {"rowIndex": i, "columnIndex": j}, "tableCellProperties": {}}
                                                                                                         for j in range(v["columns"])]} for i in range(v["rows"])]}}
            lst = els[ep["pageObjectId"]][0]["pageElements"]
            lst.append(e)
            els[o] = (e, lst)
        elif k == "groupObjects":
            kids = {id(els[c][0]) for c in v["childrenObjectIds"]}
            lst = els[v["childrenObjectIds"][0]][1]
            at = [i for i, x in enumerate(lst) if id(x) in kids]
            g = {"objectId": v["groupObjectId"], "transform": {"scaleX": 1, "scaleY": 1, "unit": "EMU"}, "elementGroup": {"children": [lst[i] for i in at]}}
            for i in reversed(at):
                del lst[i]
            lst.insert(at[0], g)
            for c in g["elementGroup"]["children"]:
                els[c["objectId"]] = (c, g["elementGroup"]["children"])
            els[g["objectId"]] = (g, lst)
        elif o not in els:  # ページ番号の枠（_n）。Google がレイアウトから作るので、手元にはない
            continue
        elif k == "deleteObject":
            e, lst = els.pop(o)
            lst[:] = [x for x in lst if x is not e]
        elif k == "insertText":
            t = texts.setdefault(key, [["\n", {}, {}]])
            t[v["insertionIndex"]:v["insertionIndex"]] = [[x, {}, {}] for c in v["text"] for x in [c] + [""] * (u16(c) - 1)]
        elif k == "updateTextStyle" and key in texts:
            a, b = span(texts[key], v["textRange"])
            for c in texts[key][a:b]:
                c[1] = dict(c[1])
                merge(c[1], v["style"], v["fields"])
        elif k == "updateParagraphStyle" and key in texts:
            for c in paras(texts[key], v["textRange"]):
                merge(c[2], v["style"], v["fields"])
        elif k == "createParagraphBullets" and key in texts:
            for c in paras(texts[key], v["textRange"]):
                c[2]["_bullet"] = True
        elif k == "updateShapeProperties":
            merge(els[o][0]["shape"]["shapeProperties"], v["shapeProperties"], v["fields"])
        elif k == "updateLineProperties":
            merge(els[o][0]["line"]["lineProperties"], v["lineProperties"], v["fields"])
        elif k == "updatePageProperties":
            merge(els[o][0]["pageProperties"], v["pageProperties"], v["fields"])
        elif k == "updatePageElementAltText":
            els[o][0].update(title=v["title"], description=v["description"])
        elif k == "updateTableCellProperties":
            rng, rows = v["tableRange"], els[o][0]["table"]["tableRows"]
            r0, c0 = rng["location"].get("rowIndex", 0), rng["location"].get("columnIndex", 0)
            for row in rows[r0:r0 + rng["rowSpan"]]:
                for cell in row["tableCells"][c0:c0 + rng["columnSpan"]]:
                    merge(cell["tableCellProperties"], v["tableCellProperties"], v["fields"])
        elif k == "mergeTableCells":  # 結合したセルは、左上のセルが rowSpan・columnSpan を持つ
            rng = v["tableRange"]
            els[o][0]["table"]["tableRows"][rng["location"]["rowIndex"]]["tableCells"][rng["location"]["columnIndex"]] |= {"rowSpan": rng["rowSpan"], "columnSpan": rng["columnSpan"]}
    for (o, *cell), t in texts.items():
        e = els[o][0]
        (e["table"]["tableRows"][cell[0]]["tableCells"][cell[1]] if cell else e["shape"])["text"] = emit(t)
    for s in slides:
        if note := deck.notes.get(s["objectId"]):
            s["slideProperties"]["notesPage"] = {"notesProperties": {"speakerNotesObjectId": s["objectId"] + ":notes"},
                                                 "pageElements": [{"objectId": s["objectId"] + ":notes", "shape": {"text": emit([[c, {}, {}] for c in note] + [["\n", {}, {}]])}}]}
    return {"title": p.get("title", deck.name), "slides": slides, "masters": p.get("masters", []), "layouts": p.get("layouts", [])}


def placeholders(page):
    """ページ（マスター・レイアウト）のプレースホルダーの型の並び。"""
    return [e["shape"]["placeholder"]["type"] for e in page.get("pageElements", []) if "placeholder" in e.get("shape", {})]


def is_blank(layout):
    """slides.py が組めるレイアウトか。プレースホルダーはページ番号の枠だけ（ほかの枠があると、全ページに空の枠が残る）。"""
    return placeholders(layout) == ["SLIDE_NUMBER"]


def deck_font(p):
    """デッキの書体。テンプレートのマスターのプレースホルダーの書体（template.py が書く。本文の枠を先に見る）のうち、JP_FONTS にあるもの。
    欧文の書体（FONT_EM の DM Sans）は、template.py が書いたテーマの名前（deck_theme）があるデッキだけ。
    なければ FONT（社内資料の複製など、マスターが欧文の書体のデッキは FONT で組み、lint も FONT と比べる）。pages.py は FONT で組み、build が置き換える。"""
    fonts = JP_FONTS | set(FONT_EM) if deck_theme(p) else JP_FONTS
    els = [e for m in p.get("masters", []) for e in m.get("pageElements", []) if "placeholder" in e.get("shape", {})]
    for e in sorted(els, key=lambda e: e["shape"]["placeholder"].get("type") != "BODY"):
        for t in e["shape"].get("text", {}).get("textElements", []):
            if (f := t.get("textRun", {}).get("style", {}).get("fontFamily")) in fonts:
                return f
    return FONT


def refont(o, font):
    """組む requests の書体 FONT を font にする（fontFamily の値だけ。資料の文に書体の名前があっても変えない）。"""
    if isinstance(o, dict):
        return {k: font if k == "fontFamily" and v == FONT else refont(v, font) for k, v in o.items()}
    return [refont(v, font) for v in o] if isinstance(o, list) else o


def default_theme():
    """factory.toml の [slides] default_theme（書いていなければ visual。factory-doctor と同じ）。"""
    return factory().get("slides", {}).get("default_theme", "visual") if gapi.find_factory() else "visual"


def theme_list():
    """(名前, 説明, テンプレートがあるか, 既定か, ファイルがあるか) の並び。テーマのファイル（組み込みとワークスペース）と、[slides.templates] の名前。"""
    temps, d = templates(), default_theme()
    rows = []
    for n in dict.fromkeys([*theme_names(), *temps]):
        try:
            t = load_theme(n)
        except SystemExit as e:  # 書きかけのファイルが 1 つあっても、ほかのテーマは出す（直すところを説明の欄に出す）
            rows.append((n, f"（読めない: {e}）", n in temps, n == d, True))
            continue
        rows.append((n, (t or {}).get("description", ""), n in temps, n == d, t is not None))
    return rows


def cmd_themes():
    """テーマを 1 行ずつ出す。エージェントが、資料の種類と聞き手に合うものを選ぶ。テンプレートのないテーマは選べない（template.py で作る）。"""
    for name, note, has, default, file in theme_list():
        if not file:
            note = f"（テーマのファイルがない。slides.py theme <[slides.templates] の {name} の URL> で写す）"
        elif not note:
            note = f"（説明がない。themes/slides/{name}.json の description に書く）"
        print(f"{name}{'（既定）' if default else ''}\t{'テンプレートあり' if has else 'テンプレートなし'}\t{note}")
    if rows := unlisted():
        for name, url, note, where in rows:
            state = "factory.toml の [slides.templates] にない" if name not in templates() else "[slides.templates] の同じ名前は別のテンプレート"
            print(f"{name}（{where}。{state}）\t{url}\t{note}")
        print("共有・個人のテーマを使うときは、slides.py theme <url> を回す（テーマのファイルを themes/slides/<名前>.json に写し、[slides.templates] に url を書く。"
              "同じ名前のテーマがあれば、今のテンプレートの代わりになる）")


def need_theme(theme):
    """new で、テンプレートのあるテーマが 2 つ以上あるのに --theme がなければ、一覧を出して止める。資料ごとに description でテーマを選ばせる
    （Agent Skills でスキルの一覧が毎回出るのと同じ役目。deck-practices/start.md の 5）。factory-kaizen の検証で組む仮の資料は止めない。"""
    if theme is None and len(templates()) >= 2 and not os.environ.get("FACTORY_VERIFY"):
        cmd_themes()
        sys.exit("テーマを選んでから組む。上の description と、資料の種類・聞き手を突き合わせて、slides.py new <フォルダ> <名前> --theme <名前> で渡す"
                 "（description で決まらなければ既定のテーマ）。選んだテーマと理由は構成案の前提に書く")


def template_id(theme):
    """テーマのテンプレートの ID（[slides.templates]）。"""
    if theme not in (T := templates()):
        sys.exit(f"テーマ {theme} のテンプレートが factory.toml の [slides.templates] にない（あるテーマ: {', '.join(T) or 'なし'}）。template.py {theme} --from-base で作る")
    return T[theme]


def cmd_theme(url, name=None, force=False):
    """[slides-component-021] プレゼン url（テンプレートかデッキ）が持つテーマ（theme_from）を、ワークスペースの themes/slides/<名前>.json に書く。名前を省くと目印の名前。
    共有テーマを使い始めるときと、画面のテーマビルダーで直した色・書体をファイルに戻すときに使う。テンプレート（Drive のプロパティにテーマの名前があるもの）なら、
    [slides.templates] にも URL を書く。中身の違う同じ名前のファイルがあれば、force がなければ止める（手で直した値を黙って消さない）。"""
    if not (d := ws_themes()):
        sys.exit("slides.py theme はワークスペース（factory.toml のあるフォルダ）の中で回す")
    pid = file_id(url)
    p = request("GET", f"{SLIDES}/{pid}?fields={DECK_FIELDS}")
    mark = deck_theme(p)
    if not (name := name or mark):
        sys.exit("プレゼンにテーマの名前がない（template.py で合わせ直す前のもの）。slides.py theme <URL> <名前> で名前を渡す")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        sys.exit(f"テーマの名前 {name!r} は英数字と - _ だけにする")
    template = THEME_PROP in (request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=properties").get("properties") or {})
    if template and name != mark:  # new が、テンプレートの目印の名前とテーマの名前をそろえる（need_mark）
        sys.exit(f"テンプレートはテーマ {mark} の名前を持つ。同じ名前で写す（slides.py theme <URL>）か、template.py {name} で合わせ直してから写す")
    f, have = d / f"{name}.json", theme_from(p)
    if f.is_file() and not force and theme_from(theme_pages(name, read_theme(f))) != have:  # 書いていない値（既定の書体・visual の色）は埋めて比べる
        sys.exit(f"{f} がもうあり、中身が違う。今のファイルを残すなら別の名前を渡し（slides.py theme <URL> <名前>）、置き換えるなら --force を付ける")
    if template:
        record_template(name)  # 書けるかを、ファイルを書く前に確かめる
    d.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(theme_file(have), ensure_ascii=False, indent=1) + "\n")
    if template:
        record_template(name, pid)
    print(f"{f} に書いた" + (f"。factory.toml の [slides.templates] に {name} を書いた" if template else ""))


def new(folder, name, src):
    """テンプレート src（template_id）を Drive のフォルダに複製して、その ID を返す。"""
    if not re.match(r"\d{8}_", name):
        sys.exit("Drive 上の名前は YYYYMMDD_ で始める: " + name)
    return request("POST", f"{DRIVE}/files/{src}/copy?supportsAllDrives=true&fields=id",
                   {"name": name, "parents": [folder_id(folder)]})["id"]


def load_pages(name="pages"):
    """今いるフォルダの pages.py（name を渡すと <name>.py）を読み、モジュールを返す。pages.py の「from slides import …」には、このモジュールを
    そのまま渡す（2 つ目を読み込まない）。"""
    sys.modules["slides"] = sys.modules[__name__]
    sys.path.insert(0, os.getcwd())
    return importlib.import_module(name)


def load_make(path):
    """ファイルの NAME と make。JSON のページ（.json）は d.spec で組み、NAME は deck.json の name。"""
    if not path.endswith(".json"):
        return load_pages(Path(path).stem)
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{path}: 読めない（{e}）")
    deck = isinstance(data, dict) and data.get("kind") == "deck"
    return types.SimpleNamespace(NAME=data["name"] if deck and "name" in data else "dry", THEME=data.get("theme") if deck else None, make=lambda d: d.spec(path))


def declared_theme(path):
    """デッキのファイル（deck.json）に書いた theme。pages.py は読み込まない（読み込むと slides の値を、テーマを決める前に写す）。"""
    return load_make(path).THEME if path.endswith(".json") else None


def file_kind(path):
    """JSON のファイル path の kind。JSON でない・読めない・頭が dict でなければ None（読めないことは、あとで読むところが場所を付けて止める）。"""
    try:
        o = json.loads(Path(path).read_text()) if path.endswith(".json") else None
    except (OSError, json.JSONDecodeError):
        return None
    return o.get("kind") if isinstance(o, dict) else None


def lint_scope(path):
    """slides.py lint が見る単位。deck.json・pages.py はデッキ全体、部品 1 つのファイル（kind component）は部品、ほかはページ（子の担当のファイルも）。"""
    if path in ("pages.py", "deck.json"):
        return "deck"
    if file_kind(path) == "component":
        return "component"
    return "page"


def need_deck_theme(want, mark):
    """deck.json に書いた theme と、組むデッキ（new はテンプレート）のテーマが同じか。違えば止める（テーマを替えるなら new で作り直す）。"""
    if want and mark and want != mark:
        sys.exit(f"deck.json の theme は {want} だが、デッキのテーマは {mark}。テーマを替えるなら、slides.py new で作り直す（themes.md）")


def default_pages():
    """組むデッキのファイル。今いるフォルダの pages.py か deck.json（JSON だけで書いたデッキ）。両方あれば止める。"""
    have = [f for f in ("pages.py", "deck.json") if Path(f).is_file()]
    if len(have) == 2:
        sys.exit("pages.py と deck.json の両方がある。どちらか 1 つにする（pages.py から JSON のページを呼ぶなら、d.spec(\"pages.json\") のように別の名前にする）")
    if not have:
        sys.exit("今いるフォルダに deck.json（か前の資料の pages.py）がない。資料の build/ で回す（../pages.md）")
    return have[0]


def dry(path="pages.py", url=None, show=False):
    """[slides-component-015] 組まずに path の make(d) を走らせ、組むときの警告と枚数を出す（Google には書かない。アイコンの名前だけは確かめる）。
    子が担当のページを別のファイルに書いたとき、親が組む前に子が自分で確かめる（../pages.md）。番号は担当の中の何枚目。finish は呼ばない（ページへのリンクは、親が組むときに確かめる）。
    テーマ・表紙と扉のパターンは deck_context（テーマのファイルがあれば Google を読まない。url はテーマのファイルがないデッキだけに要る）。"""
    if Path(path).parent != Path("."):  # 今いるフォルダから読むので、別のフォルダのファイルを黙って取り違えない
        sys.exit(f"dry はファイルのあるフォルダ（build/）で、名前だけを渡して回す: {path}")
    deck_context(path, url)
    d = Deck("dry")
    load_make(path).make(d)
    if show:  # slides.py resolve: JSON のページの解いた形
        print(json.dumps(d.resolved, ensure_ascii=False, indent=1))
    print(json.dumps({"file": path, "slides": len(d.slides), "warnings": len(d.warnings)}, ensure_ascii=False), file=sys.stderr if show else sys.stdout)
    return d


LOCAL_ONLY = ("手元の lint（組んでいない）。「（見積もり）」の付いた指摘と組むときの警告は、組むときと同じ字幅の見積もりで、Google が描いた画像で確定する。"
              "見ていないもの: 画像で測る箱の余白（box_pad）、Google が描いた折り返し・画像の枠・ページ番号")


def page_numbers(args):
    """引数の並び args の --pages の次の値（「3,5」）を、ページの番号の集合にする。値がないか数でなければ止める（slides.py lint・gslides.py check）。"""
    k = args.index("--pages") + 1
    s = args[k] if k < len(args) else ""
    if not re.fullmatch(r"\d+(,\d+)*", s):
        sys.exit(f"--pages には 1 から始まるページの番号を「3,5」の形で渡す: {s!r}")
    return {int(n) for n in s.split(",")}


def clean_after(clean, hashes, pages, bad):
    """lint_local が残す、要修正のなかったページのハッシュ。hashes はページの順のハッシュ、pages は今回見たページ、bad は要修正の出たページ（番号）。
    見たページで要修正のなかったものを足し、見なかったページは前の記録を残す。要修正の出たページのハッシュは外す（同じ中身のページが別の番号で通っていても）。"""
    seen = {h for i, h in enumerate(hashes, 1) if i in pages and i not in bad}
    return ((clean & set(hashes)) | seen) - {h for i, h in enumerate(hashes, 1) if i in bad}


def lint_theme(path):
    """[slides-component-022] テーマのファイル path だけを見る（Google を読まない）: 形と書体（read_theme）と、役割の組のコントラスト（template.py の check）。
    届かない組があれば、直す案を出して止める。"""
    t = read_theme(path)
    sys.modules["slides"] = sys.modules[__name__]  # template.py の「from slides import …」に、このモジュールをそのまま渡す
    import template
    if not template.check(Path(path).stem, t):
        sys.exit("役割の組のコントラストが基準に届かない（上の直す案をユーザーに見せて、テーマのファイルの colors を直す）")


def lint_local(path="pages.py", url=None, talk=False, pages=None):
    """[slides-component-018] 組まずに path の make(d) から組む要求を作り、presentations.get の形に組み立てて（local_json）lint をかける（テストの unit。直すたびに回す）。
    テーマは deck_context（テーマのファイルがあれば Google を読まない。url はテーマのファイルがないデッキだけに要る）。pages（番号の集合）のページの指摘だけを出す。
    pages が None なら、前回この pages.py に同じデッキと同じ規則で回したときから変わったページと、前回の要修正が残ったページ（ページの中身のハッシュ pages_of で見る）。
    デッキ全体の規則（扉・結論バンドの数など）とワークスペースの点検はいつも全ページを見る。組んで画像を取るのは区切りだけにする（../commands.md）。"""
    if file_kind(path) == "theme":  # テーマのファイル（themes/slides/）は、形と役割の組のコントラストを見る
        return lint_theme(path)
    if Path(path).parent != Path("."):
        sys.exit(f"lint はファイルのあるフォルダ（build/）で、名前だけを渡して回す: {path}")
    _, _, p = deck_context(path, url)
    m = load_make(path)
    with contextlib.redirect_stderr(io.StringIO()) as err:  # 組むときの警告は、見るページのものだけを出す
        deck = Deck(getattr(m, "NAME", "dry"))
        m.make(deck)
        if path not in ("pages.py", "deck.json"):  # 子のファイルと JSON のページの、ページへのリンクは、全体の番号を指すので、親が組むときに確かめる（dry と同じ）
            deck.links.clear()
        deck.finish()
    reqs = json.loads(resolved(deck, p))
    *_, digest = pages_of(deck, reqs)  # ノートだけ変えたページも見る
    ws = gapi.find_factory()
    rules = [Path(__file__).with_name("lint.py"), Path(__file__), Path(brand.__file__).with_name("textlint.py"), Path(brand.__file__)] + ([ws.parent / "rules" / "slides-build" / "checks.py"] if ws else [])
    import lint
    facts = lint.load_facts()  # 資料のフォルダ（build/ の親）の出典の表。変われば、前に通ったページも見直す（deck-lint-026）
    key = "\0".join([str(Path(path).resolve()), str(talk), json.dumps(p, sort_keys=True), str(facts)] + [f.read_text() if f.is_file() else "" for f in rules])  # lint の結果を変えるもの（見るテーマのマスター・レイアウト、--talk、規則の lint.py・slides.py・ワークスペースの checks.py）が変われば、前の記録を使わない
    state = Path(tempfile.gettempdir()) / f"slides_lint_{gapi.user()}_{hashlib.sha1(key.encode()).hexdigest()[:8]}.json"
    clean = set(json.loads(state.read_text())) if state.is_file() else set()  # 前に見て、要修正のなかったページのハッシュ
    if pages in (None, "all"):
        pages = {i for i, s in enumerate(deck.slides, 1) if pages == "all" or not state.is_file() or digest[s] not in clean}
    elif over := sorted(pages - set(range(1, len(deck.slides) + 1))):
        sys.exit(f"--pages の {', '.join(map(str, over))} がない（{len(deck.slides)} 枚）")
    for chunk in re.split(r"(?m)^(?=警告: \[p\d+\])", err.getvalue()):  # 警告の文に改行が入ることがある
        if not (w := re.match(r"警告: \[p(\d+)\]", chunk)) or int(w.group(1)) in pages:
            print(chunk, end="", file=sys.stderr)
    q = local_json(reqs, deck, p)
    r = lint.Report()
    r.where = spec_where(deck)  # JSON のページなら、指摘に部品の場所を付ける
    hard = lint.lint_slides(q, r, "差し替え用" in q["title"], talk, pages, lint_scope(path), facts=facts)
    if out := [h for h in spec_out_hits(deck) if lint.hit_page(h) in pages]:
        r.hits[SPEC_OUT] = out
        r.show([SPEC_OUT], "要確認（JSON の形の外の書き方）")
    bad = {lint.hit_page(h) for k in lint.HARD_NAMES | r.extra_hard for h in r.hits.get(k, [])}
    state.write_text(json.dumps(sorted(clean_after(clean, [digest[s] for s in deck.slides], pages, bad))))
    warnings = sum(int(re.match(r"\[p(\d+)\]", w).group(1)) in pages for w in deck.warnings)
    print(f"\n{LOCAL_ONLY}\n" + json.dumps({"file": path, "slides": len(deck.slides), "pages": sorted(pages), "warnings": warnings}, ensure_ascii=False))
    if hard:
        sys.exit("lint の要修正が残っている（上の出力を直す）")


def merge(pages, fixes):
    """[slides-component-014] 子が別のファイル（build/fix_<担当>.py）に書いたページの関数を pages.py に合わせる（../../deck-review/SKILL.md の deck-review-011）。
    子は pages.py を書かず、親がここで合わせて 1 回だけ組む。同じ名前の関数は置き換え、pages.py にない関数は make の前に足す。import と docstring は読み飛ばす
    （名前は pages.py の import を使う）。make と、関数でない文（定数など）があれば合わせずに止める（共通のものとページの順は親が書く）。2 つのファイルが同じ関数を
    書いても止める。足した関数を make が呼んでいなければ警告する。前の pages.py は pages.py.bak に残す（直して欠陥が増えたら戻すため。あれば上書きせず pages.py.bak1 …）。
    戻り: {ファイル: {"replaced": [...], "added": [...]}}。"""
    src, owner, out = Path(pages).read_text(), {}, {}
    start = lambda n: (n.decorator_list[0] if n.decorator_list else n).lineno - 1
    for f in fixes:
        text = Path(f).read_text()
        lines, got = text.splitlines(keepends=True), {"replaced": [], "added": []}
        for i, n in enumerate(ast.parse(text, f).body):
            if isinstance(n, (ast.Import, ast.ImportFrom)) or i == 0 and isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
                continue
            if not isinstance(n, ast.FunctionDef) or n.name == "make":
                sys.exit(f"{f}:{n.lineno} は関数でないか make なので合わせない（共通のものとページの順は親が pages.py に書く）")
            if n.name in owner:
                sys.exit(f"{n.name} を {owner[n.name]} と {f} の両方が書いた（同じ関数に当たる行は同じ子に渡す）")
            owner[n.name] = f
            body = "".join(lines[start(n):n.end_lineno]).rstrip("\n") + "\n"
            at = {m.name: m for m in ast.parse(src, pages).body if isinstance(m, ast.FunctionDef)}
            old = src.splitlines(keepends=True)
            if n.name in at:
                old[start(at[n.name]):at[n.name].end_lineno] = [body]
                got["replaced"].append(n.name)
            elif "make" in at:
                old[start(at["make"]):start(at["make"])] = [body, "\n\n"]
                got["added"].append(n.name)
            else:
                sys.exit(f"{pages} に make がない")
            src = "".join(old)
        out[f] = got
    make = next(m for m in ast.parse(src, pages).body if isinstance(m, ast.FunctionDef) and m.name == "make")
    called = {n.id for n in ast.walk(make) if isinstance(n, ast.Name)}
    for name in (k for g in out.values() for k in g["added"] if k not in called):
        print(f"警告: {owner[name]} の {name} を足したが、make から呼ばれていない（名前の誤りか、make に足し忘れ）", file=sys.stderr)
    bak = next(b for b in (pages + ".bak" + (str(i) if i else "") for i in range(1000)) if not os.path.exists(b))
    shutil.copy(pages, bak)
    Path(pages).write_text(src)
    return out


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
    marked = lambda f: {"masters": [{"pageElements": [ph("TITLE", f), {"description": "ai-deck-factory theme=acme", **ph("SLIDE_NUMBER", f)}]}]}
    assert deck_font(marked("DM Sans")) == "DM Sans" and deck_font(marked("Inter")) == FONT  # template.py が DM Sans で組んだテーマのデッキは DM Sans。測っていない欧文の書体は FONT
    assert deck_font({"masters": [{"pageElements": [ph("TITLE", "Noto Serif JP"), ph("BODY", "BIZ UDPGothic")]}]}) == "BIZ UDPGothic"  # 本文の枠を先に見る
    assert refont([{"style": {"fontFamily": FONT}}, {"insertText": {"text": FONT}}], "X") == [{"style": {"fontFamily": "X"}}, {"insertText": {"text": FONT}}]
    assert is_blank({"pageElements": [{"shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}]}) and not is_blank({"pageElements": [ph("TITLE", FONT)]})
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
    for (dia, sz), n in itertools.product(NUM.values(), ("1", "10", "12", "99")):  # 正円の番号: 塗りの円 + 円と同じ高さの透明の枠
        start = len(corners.reqs)
        frame = corners.text(sid,1,1,dia,dia,n,size=sz,align="CENTER",valign="MIDDLE",fill=RED,kind="ELLIPSE")
        made = [r["createShape"] for r in corners.reqs[start:] if "createShape" in r]
        assert [c["shapeType"] for c in made] == ["ELLIPSE","RECTANGLE"] and made[1]["objectId"] == frame == corners.round_groups[-1][1]
        assert abs(made[0]["elementProperties"]["size"]["width"]["magnitude"] - dia*EMU) < 2  # 円の大きさは変えない
        size, move = made[1]["elementProperties"]["size"], made[1]["elementProperties"]["transform"]
        fw = size["width"]["magnitude"] / EMU
        assert abs(fw - (max(dia, em_width(n)*sz/72 + 2*INSET) + .1)) < 1e-6  # 字数によらず、円か数字の幅の広いほうに 0.1 in の余り（#51）
        assert abs(size["height"]["magnitude"] - dia*EMU) < 2
        assert abs(move["translateX"] - (1 + dia/2 - fw/2)*EMU) < 2 and abs(move["translateY"] - EMU) < 2  # 円の中心にそろえる
        assert not any(r.get("updateParagraphStyle",{}).get("style",{}).get("lineSpacing") == 125 for r in corners.reqs[start:])  # 行間は 100
    start = len(corners.reqs)
    corners.num(sid, 3, 2, 2, "large")  # 中心で置き、大きさと文字は NUM から
    try:
        corners.num(sid, 1, 2, 2, "L")  # 前の略号は止める（語で書く。2026-10-18）
        raise AssertionError
    except ValueError as e:
        assert "small・medium・large" in str(e)
    circle = next(r["createShape"]["elementProperties"] for r in corners.reqs[start:] if r.get("createShape",{}).get("shapeType") == "ELLIPSE")
    assert abs(circle["size"]["width"]["magnitude"] - NUM["large"][0]*EMU) < 2 and abs(circle["transform"]["translateX"] - (2 - NUM["large"][0]/2)*EMU) < 2
    assert any(r.get("updateTextStyle",{}).get("style",{}).get("fontSize") == pt(NUM["large"][1]) for r in corners.reqs[start:])
    for n in ("1", "10"):  # 角丸の番号: 角丸の背景（box）+ 円と同じ幅の取り方の透明の枠。中心は (cx, cy)
        start = len(corners.reqs)
        frame = corners.num(sid, n, 2, 2, shape="round_rectangle")
        made = {r["createShape"]["objectId"]: r["createShape"]["elementProperties"] for r in corners.reqs[start:] if "createShape" in r}
        w, (dia, sz) = num_w(n, "medium", "round_rectangle"), NUM["medium"]
        fw = made[frame]["size"]["width"]["magnitude"] / EMU
        assert abs(fw - (max(w, em_width(n)*sz/72 + 2*INSET) + .1)) < 1e-6 and abs(made[frame]["transform"]["translateX"] / EMU - (2 - fw/2)) < 1e-6
        assert abs(made[frame]["size"]["height"]["magnitude"] - dia*EMU) < 2 and corners.round_groups[-1][1] == frame and len(made) > 2  # 角は円と四角で組む
        assert min(p["transform"]["translateX"] for k, p in made.items() if k != frame) / EMU >= 2 - w/2 - 1e-6  # 背景は見える幅の内
    corners.finish()
    assert len(corners.round_groups) == 24 and all(len(r["groupObjects"]["childrenObjectIds"]) >= 2 for r in corners.reqs if "groupObjects" in r)
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
    assert abs(card_h(3, "今", items=[("a", "b"), ("c", "d")], step=0.62) - card_h(3, "今", items=[("a", "b")]) - 0.62) < 1e-9 and abs(card_h(3, items=[("a", "b")], step=2) - 2.2 - CARD_DOWN) < 1e-9  # step の最後の項目も下端と 0.28 in より空け、広い step はそのまま
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
    assert hex_of(NAVY) == hex_of(HEAD) == PALETTE["DARK1"] and hex_of(TEXT) == fixed(TEXT)  # アイコンの役割の名前は、デッキの配色の 6 桁にする
    use_palette({"masters": [{"pageProperties": {"colorScheme": {"colors": [{"type": "DARK1", "color": {"red": 1}}, {"type": "ACCENT1", "color": {}}]}}}]})
    assert PALETTE["DARK1"] == "FF0000" and PALETTE["ACCENT1"] == "000000"  # 0 の成分は省かれる
    use_palette({"masters": [{"pageProperties": {"colorScheme": {"colors": [{"type": "DARK1", "color": {"blue": 1}}]}}}]})
    assert PALETTE["DARK1"] == "0000FF" and PALETTE["ACCENT1"] == VISUAL["ACCENT1"]  # 前のデッキの色を残さない
    PALETTE.update(VISUAL)
    try:
        make_deck(lambda d: d.icon(d.page("t"), "tabler:database", 0, 0, 0.4, "navy"), "foot")
        raise AssertionError("アイコンに名前でも 6 桁でもない色を通した")
    except SystemExit:
        pass
    # テーマの名前はマスターかレイアウトの代替テキストから読む。名前がなければ None
    mark = lambda d: {"masters": [{"pageElements": [{"description": d, **ph("SLIDE_NUMBER", FONT)}]}]}
    assert deck_theme(mark("ai-deck-factory theme=plain")) == "plain" and deck_theme({"layouts": [mark("ai-deck-factory theme=a-1")["masters"][0]]}) == "a-1"
    assert deck_theme(mark("")) is None and deck_theme({"masters": [{}]}) is None
    lays = {"layouts": [{"objectId": "c", "pageElements": [{"description": "ai-deck-factory layout=cover:1 w=7.08 tone=light"}]},
                        {"objectId": "s2", "pageElements": [{"description": "ai-deck-factory layout=section:2 tone=accent"}]},
                        {"objectId": "s1", "pageElements": [{"description": "ai-deck-factory layout=section:1 w=10.19 tone=dark"}]}]}
    use_layouts(lays)  # 目印の番号で引く（並びの順でない）。扉の 2 は本文の幅のまま
    assert {k: l["objectId"] for k, l in deck_layouts(lays).items()} == {("cover", 1): "c", ("section", 2): "s2", ("section", 1): "s1"}
    assert VARIANTS == {"cover": {1: (7.08, "light")}, "section": {2: (None, "accent"), 1: (10.19, "dark")}}
    v = Deck("v")
    c, d2 = v.cover("t", "k"), v.divider("01", "t", variant=2)
    assert [r["createSlide"]["slideLayoutReference"]["layoutId"] for r in v.reqs if "createSlide" in r] == ["@COVER1", "@SECTION2"]
    assert not any("updatePageProperties" in r for r in v.reqs) and v.footc == {c: SUB, d2: NAVY} and not v.dark  # レイアウトの地を見せる。白地の表紙のフッターは SUB
    assert [r["updateTextStyle"]["style"]["foregroundColor"]["opaqueColor"] for r in v.reqs
            if r.get("updateTextStyle", {}).get("style", {}).get("fontSize", {}).get("magnitude") == 34] == [paint(HEAD)]  # 白地の表紙のタイトルは HEAD
    try:
        v.divider("02", "t", variant=3)
        raise AssertionError
    except ValueError:
        pass
    use_layouts({"layouts": [lays["layouts"][2], {"objectId": "s3", "pageElements": [{"description": "ai-deck-factory layout=section:3 tone=light"}]}]})
    g = Deck("g")  # 番号が飛んでも（扉の 2 のレイアウトを手で消したデッキ）、3 は 3 の地で組み、2 はないと言う
    g.divider("03", "t", variant=3)
    assert g.footc == {g.slides[0]: SUB} and [r["createSlide"]["slideLayoutReference"]["layoutId"] for r in g.reqs if "createSlide" in r] == ["@SECTION3"]
    try:
        g.divider("02", "t", variant=2)
        raise AssertionError
    except ValueError as e:
        assert "1（地: dark）, 3（地: light）" in str(e)  # 地の明るさを添えて、見本を見なくても選べる
    use_layouts({})
    use_theme({"TEXT": "#37352f", "DECOR": "6B8089", "copyright": "© 2026 Me. All rights reserved."})  # テーマの値で組む（既定と同じ値は置き換えない）
    assert _SWAP == {TEXT: "37352F"} and paint(TEXT) == paint("303f47") == {"rgbColor": rgb("37352F")} and paint(RULE) == {"rgbColor": rgb(RULE)} and paint(NAVY) == {"themeColor": NAVY}
    t = make_deck(lambda d: d.text(d.page("t"), 0, 0, 1, 1, "本文"), "foot")
    assert sum(r.get("insertText", {}).get("text") == "© 2026 Me. All rights reserved." for r in t.reqs) == 1
    assert {"opaqueColor": {"rgbColor": rgb("37352F")}} in [r["updateTextStyle"]["style"].get("foregroundColor") for r in t.reqs if "updateTextStyle" in r]
    use_theme({"mono": "IBM Plex Mono"})  # テーマの等幅の書体で組む（字の幅の見込みは MONO_EM のまま）
    assert {r["updateTextStyle"]["style"]["fontFamily"] for r in mono_reqs("e", "a あ b")} == {"IBM Plex Mono"}
    noto, dm = .56 + .35 + .56 + .22 + 1, .31 + .54 + .31 + .27 + 1  # 「1-1 あ」の幅
    use_pages(marked("DM Sans"))  # テーマのファイルのない（ほかの人のテーマの）デッキ: マスターの DM Sans の幅で組む
    assert abs(em_width("1-1 あ") - dm) < 1e-9 and em_width("ab", mono=True) == 2 * MONO_EM  # 英数字の幅は本文の書体のもの（和文と等幅は変わらない）
    use_font(FONT)
    assert abs(em_width("1-1 あ") - noto) < 1e-9
    # テーマのファイル: 組み込みは役割の名前で 11 の枠を書き、説明がある。読むと colors を開いた表になり、theme_file で戻る
    vis = read_theme(BUILTIN_THEMES / "visual.json")
    assert theme_slots(vis) == VISUAL and all(set(t) == {"description", *ROLE} and t["description"] and set(theme_slots(t)) == set(SLOTS)
                                             for t in map(read_theme, BUILTIN_THEMES.glob("*.json")))  # 配色は 12 の枠をすべて決める（API の決まり）
    with tempfile.TemporaryDirectory() as d:
        f = Path(d, "acme.json")
        put = lambda o: f.write_text(json.dumps({"apiVersion": API_VERSION, "kind": "theme", **o}))
        put({"font": "DM Sans", "copyright": "© 2026 Acme, Inc. All rights reserved.", "colors": {"NAVY": "002b5c", "TEXT": "111111", "HEAD": "222222"},
             "cover": ["Title 1", {"layout": "Title 2", "w": 7.08, "tone": "accent"}]})
        acme = read_theme(f)
        assert acme == {"font": "DM Sans", "copyright": "© 2026 Acme, Inc. All rights reserved.", "NAVY": "002B5C", "TEXT": "111111", "HEAD": "222222",
                        "cover": [{"layout": "Title 1"}, {"layout": "Title 2", "w": 7.08, "tone": "accent"}]}
        Path(d, "back.json").write_text(json.dumps(theme_file(acme)))
        assert read_theme(Path(d, "back.json")) == acme
        for bad, want in (({"colors": {"NAVY": "#002B5C"}}, "colors"), ({"colors": {"BLUE": "002B5C"}}, "colors"), ({"font": "Inter"}, "font"), ({"fonts": "x"}, "知らないキー"),
                          ({"cover": ["A"], "section": ["A"]}, "両方"), ({"cover": [{"layout": "A", "tone": "dim"}]}, "cover"), ({"copyright": 2026}, "copyright")):
            put(bad)
            try:
                read_theme(f)
                raise AssertionError(f"{bad} を通した")
            except SystemExit as e:
                assert want in str(e), (bad, str(e))
        for path, text, want in ((f, json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "x"}), '"kind": "theme"'), (f, "[]", '"kind": "theme"'),
                                 (Path(d, "a b.json"), "{}", "英数字")):
            path.write_text(text)
            try:
                read_theme(path)
                raise AssertionError(path)
            except SystemExit as e:
                assert want in str(e), str(e)
    # スライドの形（マスターの配色・書体・目印）に当てて読み戻すと、同じ値に戻る。書いていない役割は visual の色、測っていない表紙・扉の地の明るさは dark
    pages = theme_pages("acme", acme)
    assert theme_from(pages) == {**acme, **{r: VISUAL[s] for r, s in ROLE.items() if r not in acme}, "cover": [{"layout": "Title 1", "tone": "dark"}, acme["cover"][1]]}
    assert deck_theme(pages) == "acme" and deck_font(pages) == "DM Sans" and mark_values(pages) == {"copyright": acme["copyright"], "TEXT": "111111", "HEAD": "222222"}
    assert deck_mono(pages) == MONO_DEFAULT and deck_card(pages) == WHITE and deck_card(theme_pages("d", {"CARD": "0A0A0A"})) == "0A0A0A"  # lint と box_pad がカードを見分ける色
    assert mark_values(mark("ai-deck-factory theme=old")) == {} and mark_values(mark("ai-deck-factory theme=x {壊れた")) == {}  # 前の template.py の目印・読めない目印
    assert mark_values(mark('ai-deck-factory theme=x {"colors":"x"}')) == {} and deck_card(mark('ai-deck-factory theme=x {"colors":[1]}')) == WHITE  # 形の違う目印
    argv = sys.argv  # build・plan・new は、知らない引数（打ち間違えたファイル・フラグ）を黙って捨てずに止める（捨てると全ページを組み直す）
    for args, want in ((["build", "u", "cover.jsn"], "cover.jsn"), (["plan", "u", "p.json", "--force"], "--force"), (["new", "f", "n", "--theme", "x", "--forse"], "--forse"),
                       (["new", "f", "--theme", "x"], "usage"), (["new", "f", "n", "--theme"], "usage")):
        sys.argv = ["slides.py", *args]
        try:
            main()
            raise AssertionError(args)
        except SystemExit as e:
            assert want == "usage" and "usage" in str(e) or "知らない引数" in str(e) and want in str(e), str(e)
        finally:
            sys.argv = argv
    assert scheme({"masters": [{"pageProperties": {"colorScheme": {"colors": [{"type": "DARK1", "color": {"red": 1}}, {"type": "ACCENT1", "color": {}}]}}}]}) == {"DARK1": "FF0000", "ACCENT1": "000000"}
    # theme_diff: デッキのマスターがテーマのファイルと同じなら []。違えば値の違うキー（build が theme_reqs で書く）。表紙・扉のパターンが違う・地の明るさを測っていないなら止める
    assert theme_diff("visual", vis, theme_pages("visual", vis)) == []
    navy = {**vis, "NAVY": "000000", "TEXT": "111111"}
    assert sorted(theme_diff("visual", navy, theme_pages("visual", vis))) == ["NAVY", "TEXT"]
    bare = theme_pages("visual", {**vis, "cover": [{"layout": "T", "tone": "dark"}]})
    bare["layouts"][1]["pageElements"] = []  # 表紙のパターンのページ番号の枠を画面で消した
    assert theme_reqs("visual", vis, bare["masters"][0], bare["layouts"][0], {"cover": [bare["layouts"][1]]})  # 止まらず、その枠の目印だけを書かない
    reqs = theme_reqs("visual", navy, *deck_parts(theme_pages("visual", vis)))
    sch = {c["type"]: c["color"] for c in reqs[0]["updatePageProperties"]["pageProperties"]["colorScheme"]["colors"]}
    assert sch["DARK1"] == rgb("000000") and any('"TEXT":"111111"' in r.get("updatePageElementAltText", {}).get("description", "") for r in reqs)
    old = theme_pages("visual", vis)
    old["masters"][0]["pageElements"][0]["description"] = "ai-deck-factory theme=visual"  # 前の template.py のテンプレートから作ったデッキ: 目印に値を書き足す
    assert theme_diff("visual", vis, old) == ["description"]
    for t, p, want in (({**vis, "cover": [{"layout": "T", "tone": "dark"}]}, theme_pages("visual", vis), "パターン"),
                       ({**vis, "cover": [{"layout": "T"}]}, theme_pages("visual", {**vis, "cover": [{"layout": "T", "tone": "light"}]}), "tone")):
        try:
            theme_diff("visual", t, p)
            raise AssertionError(want)
        except SystemExit as e:
            assert want in str(e), str(e)
    # [slides.templates] の行を書き換える（コメントと並びはそのまま）。なければ表の頭に足し、表もなければ最後に足す
    md = '# 設定\n[slides.templates]  # 注\nvisual = "a"  # 書き込む\nvisual2 = "z"\n\n[drive]\nx = 1\n'
    assert set_template(md, "visual", "b") == md.replace('"a"', '"b"') and '[slides.templates]  # 注\nacme = "c"\nvisual' in set_template(md, "acme", "c")
    assert set_template("[drive]\nx = 1\n", "company", "c").endswith('x = 1\n\n[slides.templates]\ncompany = "c"\n')
    assert tomllib.loads(set_template("[slides.templates]", "acme", "c"))["slides"]["templates"] == {"acme": "c"}  # 見出しがファイルの最後の行（改行なし）でも
    assert tomllib.loads(set_template(set_template(md, "a-1", "c"), "visual", "e"))["slides"]["templates"] == {"a-1": "c", "visual": "e", "visual2": "z"}
    # 共有テーマのフォルダと自分の Themes は、[slides.templates] にないものを探すときだけ読む
    def gone(*_):
        raise gapi.ApiError("404 GET x")

    def cut(*_):  # request が取り直しても通らない回線のエラーは、ApiError でなくそのまま上がる
        raise TimeoutError("timed out")
    saved = (templates, shared_files, own_files, theme_list)
    files = [{"id": "t1", "properties": {THEME_PROP: "acme"}}, {"id": "t2", "description": "新しい", "properties": {THEME_PROP: "corp"}}]
    own = [{"id": "t5", "properties": {THEME_PROP: "mine"}}, {"id": "t6", "properties": {THEME_PROP: "mine"}}, {"id": "t7", "properties": {THEME_PROP: "acme"}},
           {"id": "t2", "properties": {THEME_PROP: "corp"}}]  # 新しい順。mine の古い t6、作り直す前の acme の t7、共有と同じ t2 は出さない
    globals().update(templates=lambda: {"acme": "t1", "own": "t3"}, shared_files=lambda: files, own_files=lambda: own)
    try:
        assert unlisted() == [("corp", "https://docs.google.com/presentation/d/t2/edit", "新しい", "共有"), ("mine", "https://docs.google.com/presentation/d/t5/edit", "", "個人")]
        rows = theme_list()
        assert ("visual", vis["description"], False, default_theme() == "visual", True) in rows and ("acme", "", True, False, False) in rows  # テンプレートだけでファイルのないテーマ
        with tempfile.TemporaryDirectory() as d:  # 書きかけのテーマのファイルがあっても、ほかのテーマは出す
            Path(d, "bad.json").write_text("{書きかけ")
            tn, tp = theme_names, theme_path
            globals().update(theme_names=lambda: ["visual", "bad"], theme_path=lambda n: Path(d, "bad.json") if n == "bad" else tp(n))
            try:
                rows = theme_list()
            finally:
                globals().update(theme_names=tn, theme_path=tp)
        assert rows[0][0] == "visual" and rows[1][0] == "bad" and rows[1][1].startswith("（読めない"), rows
        files.append({"id": "t4", "properties": {THEME_PROP: "own"}})
        with contextlib.redirect_stdout(out := io.StringIO()):
            cmd_themes()
        assert "acme\tテンプレートあり\t（テーマのファイルがない" in out.getvalue() and "corp（共有。factory.toml の [slides.templates] にない）" in out.getvalue()
        assert "mine（個人。" in out.getvalue() and "own（共有。[slides.templates] の同じ名前は別のテンプレート）" in out.getvalue()
        globals().update(shared_files=gone, own_files=gone)
        assert unlisted() == []  # 共有テーマのフォルダと Themes を読めなくても、themes と new は止めない
        globals().update(own_files=cut)
        assert unlisted() == []
    finally:
        globals().update(templates=saved[0], shared_files=saved[1], own_files=saved[2], theme_list=saved[3])
    # slides.py theme: デッキかテンプレートが持つテーマを、ワークスペースのテーマのファイルに書く。テンプレートなら [slides.templates] にも書く
    with tempfile.TemporaryDirectory() as d:
        saved, recorded, props, src = (ws_themes, request, record_template), [], {}, [theme_pages("acme", acme)]
        globals().update(ws_themes=lambda: Path(d, "themes", "slides"), record_template=lambda n, pid=None: recorded.append((n, pid)),
                         request=lambda m, u: {"properties": props} if u.startswith(DRIVE) else src[0])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_theme("https://docs.google.com/presentation/d/deck1/edit")
                f = Path(d, "themes", "slides", "acme.json")
                assert read_theme(f) == theme_from(src[0]) and not recorded
                cmd_theme("deck1")  # 同じ中身なら書き直してよい
                src[0] = theme_pages("acme", {**acme, "NAVY": "000000"})  # 画面のテーマビルダーで色を替えた
                try:
                    cmd_theme("deck1")
                    raise AssertionError("中身の違うファイルを上書きした")
                except SystemExit as e:
                    assert "--force" in str(e)
                cmd_theme("deck1", force=True)
                assert read_theme(f)["NAVY"] == "000000"
                props[THEME_PROP] = "acme"
                cmd_theme("tpl1")
                assert recorded == [("acme", None), ("acme", "tpl1")]
                try:  # テンプレートは目印の名前で写す（new が名前をそろえる）
                    cmd_theme("tpl1", "other")
                    raise AssertionError
                except SystemExit as e:
                    assert "名前を持つ" in str(e)
        finally:
            globals().update(ws_themes=saved[0], request=saved[1], record_template=saved[2])
    use_theme({})  # 値がないテーマは、今の値に戻す
    assert not _SWAP and COPYRIGHT == BRAND_COPYRIGHT and theme_fixed({}) == FIXED and paint(TEXT) == {"rgbColor": rgb("303F47")} and MONO == MONO_DEFAULT
    assert load_theme(None) is None and load_theme("ない") is None
    # NAMED の役割: 書かなければ今の色（HEAD は NAVY の枠、CARD・ON_RED は白、SUB_ON_NAVY は RULE。RULE を替えたらそれに付いていく）
    use_theme({})
    assert paint(HEAD) == paint(NAVY) == {"themeColor": "DARK1"} and paint(CARD) == paint(ON_RED) == paint(WHITE) == {"rgbColor": rgb("FFFFFF")} and paint(SUB_ON_NAVY) == paint(RULE)
    use_theme({"RULE": "C9CDD0"})
    assert paint(SUB_ON_NAVY) == paint(RULE) == {"rgbColor": rgb("C9CDD0")}
    dark = {"HEAD": "F0F0FA", "CARD": "#0a0a0a", "SUB_ON_NAVY": "C0C0C8", "ON_RED": "000000", "RULE": "2E3033", "TEXT": "D8D8E1"}
    use_theme(dark)  # 暗い本文: 書いた役割だけが替わり、同じ値を共有していた WHITE・NAVY・RULE は替わらない
    assert paint(HEAD) == {"rgbColor": rgb("F0F0FA")} and paint(NAVY) == {"themeColor": "DARK1"} and paint(CARD) == {"rgbColor": rgb("0A0A0A")}
    assert paint(WHITE) == {"rgbColor": rgb("FFFFFF")} and paint(SUB_ON_NAVY) == {"rgbColor": rgb("C0C0C8")} and paint(RULE) == {"rgbColor": rgb("2E3033")}
    t = make_deck(lambda d: (d.cover("t", "k"), d.divider("1", "扉"), d.num(d.page("本文"), 1, 2, 2), d.num(d.slides[-1], 2, 3, 3, fill=NAVY)), "foot")
    assert t.dark == set(t.slides[:2])  # 本文の地が暗くても、本文のページは扉に入れない（フッターは SUB）
    fg = [r["updateTextStyle"]["style"]["foregroundColor"]["opaqueColor"] for r in t.reqs if r.get("updateTextStyle", {}).get("style", {}).get("fontSize") == pt(NUM["medium"][1])]
    assert fg == [paint(ON_RED), paint(WHITE)]  # RED の塗りの数字は ON_RED、ほかの塗りは WHITE
    assert theme_fixed(dark)["CARD"] == "0A0A0A" and theme_fixed({}) == FIXED  # NAMED は書いたものだけ
    use_theme({})
    for bad in ("Fira Code", "jetbrains  mono", " "):  # リガチャの出る書体（書き方の揺れも）と、名前でないもの
        try:
            theme_mono({"mono": bad})
            raise AssertionError(f"mono {bad!r} を通した")
        except SystemExit:
            pass
    for bad in ({"RULE": "灰色"}, {"copyright": 2026}, {"font": ["BIZ UDPGothic"]}, {"font": "Inter"}):  # 書けない値は traceback でなく止める
        try:
            theme_values(bad), theme_font(bad)
            raise AssertionError(f"{bad} を通した")
        except SystemExit:
            pass
    # new: 選んだテーマのテンプレートが、そのテーマの目印を持たなければ止める（値の違いは build がそろえる）
    need_mark("p", "p")
    for want, mk in (("p", None), ("o", "p")):
        try:
            need_mark(want, mk)
            raise AssertionError(f"テーマ {want} をテンプレートの目印 {mk} で通した")
        except SystemExit as e:
            assert f"template.py {want}" in str(e)
    # merge: 同じ名前の関数は置き換え（上のコメントは残す）、ない関数は make の前に足す。make・関数でない文・2 つのファイルが同じ関数を書いたら止める
    with tempfile.TemporaryDirectory() as t:
        pg, fa, fb = (os.path.join(t, n) for n in ("pages.py", "fix_a.py", "fix_b.py"))
        Path(pg).write_text("from slides import X\nNAME = 'n'\n# p2 の説明\ndef p2(d):\n    d.page('前')\n\n\ndef make(d):\n    p2(d)\n")
        Path(fa).write_text('"""直した: p2"""\nfrom slides import X\n\ndef p2(d):\n    d.page(\'後\')\n    d.note(s, \'後\')\n')
        Path(fb).write_text("def p3(d):\n    d.page('足した')\n")
        assert merge(pg, [fa, fb]) == {fa: {"replaced": ["p2"], "added": []}, fb: {"replaced": [], "added": ["p3"]}}
        got = Path(pg).read_text()
        assert "前" not in got and "# p2 の説明\ndef p2(d):\n    d.page('後')\n    d.note(s, '後')\n" in got and "直した" not in got
        assert got.index("def p3") < got.index("def make") and "前" in Path(pg + ".bak").read_text()
        ast.parse(got)
        Path(fb).write_text("def p2(d):\n    d.page('再')\n")
        merge(pg, [fb])  # 同じラウンドに 2 回合わせても、最初の .bak は上書きしない
        assert "前" in Path(pg + ".bak").read_text() and "後" in Path(pg + ".bak1").read_text()
        Path(pg).write_text(got)
        Path(fb).write_text("def p4(d):\n    pass\n\n'''途中の文字列'''\n")  # docstring でない文字列は関数でない文として止める
        try:
            merge(pg, [fb])
            raise AssertionError("途中の文字列を読み飛ばした")
        except SystemExit as e:
            assert "親が" in str(e)
        for bad in ("X = 1\n", "def make(d):\n    pass\n"):
            Path(fb).write_text(bad)
            try:
                merge(pg, [fb])
                raise AssertionError(f"{bad!r} を合わせた")
            except SystemExit as e:
                assert "親が" in str(e)
        Path(fb).write_text("def p2(d):\n    pass\n")
        try:
            merge(pg, [fa, fb])
            raise AssertionError("2 つのファイルの同じ関数を合わせた")
        except SystemExit as e:
            assert "両方" in str(e) and Path(pg).read_text() == got  # 止めたら pages.py を書かない
    # 子が書いた別のファイル: pages.py の共通の関数を読み込み、1 枚 1 関数で書く。親は make の中で読み込み、ページの関数を並べる（頭で読み込むと、読み込み合って止まる。../pages.md）
    here = os.getcwd()
    with tempfile.TemporaryDirectory() as t:
        Path(t, "pages.py").write_text('from slides import X, W\nNAME = "分け"\ndef common(d, n):\n    s = d.page(f"見出し {n}", "リード")\n    d.note(s, "ノート。")\n'
                                       'def make(d):\n    import pages_a\n    common(d, 1)\n    pages_a.p02(d)\n    pages_a.p03(d)\n')
        Path(t, "pages_a.py").write_text('from pages import common\ndef p02(d):\n    common(d, 2)\ndef p03(d):\n    d.page("ノートのないページ", "")\n'
                                         'def make(d):\n    p02(d)\n    p03(d)\n')
        os.chdir(t)
        try:
            m = load_pages()
            assert len(make_deck(m.make, m.NAME).slides) == 3
            assert len(dry("pages_a.py").slides) == 2
            Path(t, "pages_s.py").write_text('def make(d):\n    d.divider("02", "扉", variant=2)\n')  # テンプレートの扉のパターン 2
            saved = default_theme, ws_themes
            globals().update(default_theme=lambda: "visual", ws_themes=lambda: None)  # 回すワークスペースの既定のテーマに左右されない（組み込みの visual には扉のパターンがない）
            try:
                dry("pages_s.py")
                raise AssertionError("デッキを読まずに扉のパターン 2 を通した")
            except ValueError:
                pass
            finally:
                globals().update(default_theme=saved[0], ws_themes=saved[1])
            seen, real = [], request
            def fake_request(m, u):  # デッキを読む代わりに、テーマのファイルのないテーマ acme の、扉のパターン 2 を持つデッキを渡す
                seen.append(u)
                return {"masters": [{"pageElements": [{"description": "ai-deck-factory theme=acme"}]}],
                        "layouts": [{"objectId": "s2", "pageElements": [{"description": "ai-deck-factory layout=section:2 tone=accent"}]}]}
            globals()["request"] = fake_request
            try:
                assert len(dry("pages_s.py", "https://docs.google.com/presentation/d/abc/edit").slides) == 1 and "/abc?" in seen[0]  # URL を渡すとデッキのパターンで通る
            finally:
                globals()["request"] = real
                VARIANTS.clear()
            try:
                dry("build/pages_a.py")
                raise AssertionError("別のフォルダのファイルを今いるフォルダから読んだ")
            except SystemExit as e:
                assert "名前だけ" in str(e)
        finally:
            os.chdir(here)
            for k in ("pages", "pages_a", "pages_s"):
                sys.modules.pop(k, None)
            sys.path[:] = [x for x in sys.path if Path(x).resolve() != Path(t).resolve()]
    selftest_diff()
    selftest_spec()
    selftest_sample()
    print("selftest ok")


def selftest_sample():
    """JSON のページの見本（../samples/json）は、形のすべての型とキーを使い（キーを足したら見本にも足す）、警告なしに組む要求まで作れる。
    見た目は sandbox でこの見本を組んで画像で見る（AGENTS.md の「直すときの決まり」）。"""
    root = Path(__file__).resolve().parent.parent / "samples" / "json"
    used, kinds, geo = defaultdict(set), set(), set()

    def el(e):
        used[e["type"]] |= set(e) - {"type"} - set(_ESC)
        geo.update(set(e) & set(_GEO))
        for r in e["rows"] if e["type"] == "gantt" else []:  # ガントの行とバーのキーも
            used["gantt.rows"] |= set(r)
            for b in r.get("bars", []):
                used["gantt.bars"] |= set(b) | {f"status:{b.get('status', 'plan')}"}
            for m in r.get("marks", []):
                used["gantt.marks"] |= set(m)
        for c in (c for r in e["rows"] for c in r if isinstance(c, dict)) if e["type"] == "table" else ():  # 表のセルのキーも
            used["table.cell"] |= set(c)
        for k in ("line", "threshold") if e["type"] == "bars" else ():  # 棒の折れ線と直線のキーも
            used[f"bars.{k}"] |= set(e.get(k, {}))
        for it in e["items"] if e["type"] == "list" else []:  # list の項目のキーも
            used["list.item"] |= set(it) if isinstance(it, dict) else set()
        for c in e["items"] if e["type"] in ("row", "stack", "grid", "frame") else []:
            el(c)
    for f in root.glob("*.json"):
        o = json.loads(f.read_text())
        kinds.add(o["kind"])
        if o["kind"] == "deck":
            used["deck"] |= set(o) - {"apiVersion", "kind"}
        elif o["kind"] == "theme":
            read_theme(f)
            used["theme"] |= set(o) - {"apiVersion", "kind"}
        elif o["kind"] == "page":
            used["page:" + o.get("type", "page")] |= set(o) - {"apiVersion", "kind", "type"}
            for e in o.get("body", []):
                el(e)
        else:
            el({k: v for k, v in o.items() if k not in ("apiVersion", "kind")})
    want = {t: set(n) | set(o) for t, (n, o) in SPEC_EL.items()} | {f"page:{t}": set(n) | set(o) for t, (n, o) in SPEC_PAGE.items()}
    want["deck"] = set(SPEC_DECK[0]) | set(SPEC_DECK[1])
    want["theme"] = set(SPEC_THEME[1])
    want |= {"gantt.rows": set(GANTT_ROW[0]) | set(GANTT_ROW[1]), "gantt.bars": set(GANTT_BAR[0]) | set(GANTT_BAR[1]) | {f"status:{k}" for k in GANTT_STATUS},
             "gantt.marks": set(GANTT_MARK[0]),  # バーの状態は、どれも見本で組む
             "table.cell": set(TABLE_CELL[0]) | set(TABLE_CELL[1]), "bars.line": set(BARS_LINE[0]) | set(BARS_LINE[1]), "bars.threshold": set(BARS_THRESHOLD[0]) | set(BARS_THRESHOLD[1]),
             "list.item": set(LIST_ITEM[1])}
    miss = {t: sorted(k - used[t]) for t, k in want.items() if k - used[t]}
    assert not miss and geo == set(_GEO) and kinds == set(KINDS), ("見本に足りない型とキー", miss, set(_GEO) - geo, set(KINDS) - kinds)
    real = {k: globals()[k] for k in ("iconify", "asset")}
    globals()["iconify"] = lambda name, color=TEXT, w=512: f"https://x/{name}.png"  # アイコンの名前を問い合わせない
    globals()["asset"] = lambda path: str(Path(__file__).resolve().parent.parent / "assets" / path)  # factory.toml のないところでも回す
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            d = make_deck(lambda x: x.spec(root / "deck.json"), "見本")
            c = make_deck(lambda x: x.spec(root / "component.json"), "部品")
    finally:
        globals().update(real)
    assert len(d.slides) == len(json.loads((root / "deck.json").read_text())["pages"]) and not d.warnings and not c.warnings, d.warnings + c.warnings
    assert "diagram" in d.page_names


def selftest_spec():
    """JSON のページ（Deck.spec）: 記法、並べ方、ID の矢印、frame、地に合わせた文字の色、手元の画像、deck.json、誤りの止め方、lint の場所、Schema。"""
    md = spec_md("a**b**c***d***`e`[f](https://x)[g](#p2)<br>h\\*", emph="E")
    assert md == ["a", ("b", {"bold": True}), "c", ("d", {"bold": True, "color": "E"}), "e", ("f", {"link": "https://x"}), ("g", {"link": {"page": "p2"}}), "\vh*"], md
    assert spec_md("注*") == "注*" and spec_bullets("- a\n- b") == ("a\nb", True) and spec_bullets("a\nb")[1] is False and spec_bullets("- a\n\n- b\n") == ("a\nb", True)
    assert spec_md("[a](https://x/(y))") == [("a", {"link": "https://x/(y)"})]  # URL の中の () も読む

    near = lambda a, b: abs(a - b) < 1e-3  # 解いた形は 4 桁に丸める

    def run(src):
        d = Deck("spec")
        d.spec(src)
        d.finish()
        return d, d.resolved[0]["els"]
    body = ["Bronze は届いたまま", "Silver は型をそろえて重複を外し、結合できる形にする", "Gold"]
    page = {"title": "見出し", "lead": "リード", "speakerNotes": "話すこと", "source": "[公式](https://docs.databricks.com/)", "band": {"text": "結論", "sub": "補足"},
            "body": [{"type": "row", "items": [{"type": "card", "head": h, "text": b, "id": h} for h, b in zip(("B", "S", "G"), body)]},
                     {"type": "text", "text": "下の文は ***強調*** と `uv run` を含む", "fill": "PANEL"},
                     {"type": "arrow", "from": "B", "to": "S"}]}
    d, els = run(page)
    da, _ = run({**page, "authorNotes": ["外した事実"]})
    assert da.resolved == d.resolved and list(da.notes.values()) == list(d.notes.values())  # authorNotes はページにもノートにも組まない
    cards, (txt,), (arr,) = [e for e in els if e["call"] == "card"], [e for e in els if e["call"] == "text"], [e for e in els if e["call"] == "arrow"]
    h = max(card_h(w, hd, body=b) for (_, w), hd, b in zip(cols(3), "BSG", body))
    assert all(near(c["x"], x) and near(c["w"], w) and near(c["h"], h) for c, (x, w) in zip(cards, cols(3))) and cards[0]["y"] == Y_BODY  # 列は cols、高さは最大にそろえる
    assert near(txt["y"], Y_BODY + h + GAP_BODY) and txt["valign"] == "MIDDLE" and txt["parts"][1] == ("強調", {"bold": True, "color": RED_TEXT})
    assert not any(r.get("updateTextStyle", {}).get("style", {}).get("fontFamily") == MONO for r in d.reqs)  # `コード` は地の文のまま（slides-visual-014）
    assert arr["y1"] == arr["y2"] and near(arr["y1"], Y_BODY + h / 2) and near(arr["x1"], cards[0]["x"] + cards[0]["w"])  # 箱の上下の中央に横に、箱の辺から引く
    conn = next(r["updateLineProperties"]["lineProperties"] for r in d.reqs if "startConnection" in r.get("updateLineProperties", {}).get("lineProperties", {}))
    assert arr["link"] == ["spec.body[0].items[0]", "right", "spec.body[0].items[1]", "left"] and conn["endConnection"]["connectionSiteIndex"] == 1  # 右の辺から左の辺へ、箱につなぐ
    assert conn["startConnection"]["connectedObjectId"] in {g[1] for g in d.round_groups}  # つなぐのはカードの箱の文字の枠（角丸の図形のまとまりには、つなげない）
    assert els[-1]["call"] == "arrow" and d.notes and json.dumps(d.resolved)  # 矢印は最後に引く。解いた形は JSON にできる
    assert d.resolved[0]["title"] == "見出し" and d.resolved[0]["lead"] == "リード"  # 解いた形のページの値は、最後の部品の値で上書きしない
    assert any(r.get("insertText", {}).get("text") == "出典: 公式" for r in d.reqs)
    assert spec_where(d)("p1: 「下の文は強調と uv」の") == f"（spec.body[1]）" and spec_where(d)("p1: 12 個") == ""  # lint の指摘に部品の場所を付ける
    two = Deck("x")
    two.slides, two.spec_index = ["s"], {"s": [("a", "同じ文で始まる一つ目"), ("b", "同じ文で始まる二つ目")]}
    assert spec_where(two)("p1: 「同じ文で始まる」") == "（a・b）"  # 候補が 2 つなら両方

    _, els = run({"type": "slide", "body": [{"type": "stack", "items": [{"type": "box", "h": 1, "id": "a", "fill": "PANEL"}, {"type": "box", "h": 1, "id": "b", "fill": "PANEL"}]},
                                            {"type": "arrow", "from": "a", "to": "b"},
                                            {"type": "frame", "h": 1.2, "items": [{"type": "text", "text": "x", "x": 1, "y": 0.5, "w": 2, "fill": "NAVY", "id": "f"},
                                                                                {"type": "arrow", "from": [0, 0], "to": [1, 0.5]}]},
                                            {"type": "row", "arrows": True, "items": [{"type": "num", "n": 1}, {"type": "label", "text": "工程"}]}]})
    a, b, arrows = els[0], els[1], [e for e in els if e["call"] == "arrow"]
    assert near(b["y"], a["y"] + 1 + GAP) and near(arrows[-2]["x1"], a["x"] + a["w"] / 2) and near(arrows[-2]["y1"], a["y"] + 1) and arrows[-2]["link"][1::2] == ["bottom", "top"]  # 縦に離れていれば、下の辺から上の辺へ
    assert "link" not in arrows[0] and "link" not in arrows[-1]  # [x, y] の端と、row の arrows はつながない
    f = next(e for e in els if e["call"] == "text")
    assert near(f["x"], X + 1) and near(f["y"], b["y"] + 1 + GAP_BODY + 0.5) and f["color"] == WHITE  # frame の中は左上からの位置。濃紺の地の文字は白
    assert spec_md("***x***", ON_FILL["NAVY"][1])[0][1]["color"] == "RED_ON_NAVY" and f["valign"] == "MIDDLE"
    assert near(arrows[-1]["x1"], X) and near(arrows[-1]["y1"], f["y"] - 0.5)  # [x, y] の端は frame の左上から
    _, diag = run({"title": "t", "body": [{"type": "frame", "h": 2, "items": [{"type": "box", "id": "a", "x": 0, "y": 1, "w": 1, "h": 0.5, "fill": "PANEL"},
                                                                            {"type": "box", "id": "b", "x": 3, "y": 0, "w": 1, "h": 0.5, "fill": "PANEL"}]},
                                         {"type": "arrow", "from": "a", "to": "b"}]})
    arr = diag[-1]
    assert near(arr["y1"], Y_BODY_NOLEAD + 1.25) and near(arr["y2"], Y_BODY_NOLEAD + 0.25)  # 上下が重ならなければ、向き合う辺の中央どうしを斜めに
    n = next(e for e in els if e["call"] == "num")
    lab = next(e for e in els if e["call"] == "label")
    assert near(lab["x"], X + NUM["medium"][0] + GAP_ARROW) and near(n["cx"], X + NUM["medium"][0] / 2)  # 番号は決まった幅、残りを label に

    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "img").mkdir()
        (Path(t) / "img" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (200).to_bytes(4, "big") + (100).to_bytes(4, "big"))
        (Path(t) / "sub").mkdir()
        head = {"apiVersion": API_VERSION}
        (Path(t) / "sub" / "p.json").write_text(json.dumps({**head, "kind": "page", "title": "画像", "body": [{"type": "image", "src": "../img/a.png", "w": 4}]}))
        (Path(t) / "pages_a.json").write_text(json.dumps({**head, "kind": "deck", "name": "a", "pages": ["sub/p.json"]}))  # 子が担当のページを並べたもの
        (Path(t) / "cover.json").write_text(json.dumps({**head, "kind": "page", "type": "cover", "title": "表紙", "kicker": "k", "speakerNotes": "[画像のページ](#p)"}))
        (Path(t) / "deck.json").write_text(json.dumps({**head, "kind": "deck", "name": "資料", "theme": "visual", "pages": ["pages_a.json", "cover.json"]}))
        for bad, want in [({"kind": "page", "title": "t"}, "apiVersion がない"), ({"apiVersion": "slides/v2", "kind": "page", "title": "t"}, "apiVersion 'slides/v2' は読めない"),
                          ({**head, "kind": "Slide", "title": "t"}, "kind 'Slide' はない"), ([{"title": "t"}], "ファイルの頭は")]:
            (Path(t) / "bad.json").write_text(json.dumps(bad))
            try:
                make_deck(lambda x: x.spec(Path(t) / "bad.json"), "x")
                raise AssertionError(f"通した: {bad}")
            except SystemExit as e:
                assert want in str(e), (want, str(e))
        here = os.getcwd()
        os.chdir(t)
        try:
            m = load_make("deck.json")
            d = make_deck(m.make, m.NAME)
            assert m.THEME == "visual" and declared_theme("deck.json") == "visual" and declared_theme("pages.py") is None
            try:
                need_deck_theme("visual", "company")
                raise AssertionError("deck.json と違うテーマのデッキに組んだ")
            except SystemExit as e:
                assert "new で作り直す" in str(e)
            (Path(t) / "cover.json").write_text(json.dumps({**head, "kind": "page", "type": "page", "title": "目次", "body": [{"type": "text", "text": "[画像のページ](#p) へ"}]}))
            dl = make_deck(m.make, m.NAME)
            link = next(r["updateTextStyle"]["style"]["link"] for r in dl.reqs if "link" in r.get("updateTextStyle", {}).get("style", {}))
            assert link == {"pageObjectId": dl.page_names["p"]} == {"pageObjectId": dl.slides[0]}  # リンクはページのファイル名で指す（並べ替えてもずれない）
            (Path(t) / "cover.json").write_text(json.dumps({**head, "kind": "page", "title": "目次", "body": [{"type": "text", "text": "[x](#nai)"}]}))
            try:
                make_deck(m.make, m.NAME)
                raise AssertionError("ないページへのリンクを通した")
            except SystemExit as e:
                assert "「nai」がない" in str(e)
            (Path(t) / "deck.json").write_text(json.dumps({**head, "kind": "deck", "name": "資料", "pages": ["sub/p.json", "pages_a.json"]}))
            try:
                make_deck(load_make("deck.json").make, "x")
                raise AssertionError("同じページを 2 回並べた")
            except SystemExit as e:
                assert "「p」が 2 つ" in str(e)
            assert len(make_deck(lambda x: x.spec(["sub/p.json"]), "x").slides) == 1  # ページのファイルの並び
        finally:
            os.chdir(here)
        img = d.resolved[0]["els"][0]
        assert m.NAME == "資料" and len(d.slides) == 2 and list(d.page_names) == ["p", "cover"] and img["h"] == 2 and img["src"] == str((Path(t) / "img" / "a.png").resolve())  # 比から高さ。パスは JSON のファイルから
        assert d.images == [img["src"]]  # 組むとき（carry）に上げる
    d, _ = run({"type": "label", "text": "札"})
    assert len(d.slides) == 1  # 部品 1 つだけは型のないページ
    d, _ = run({"title": "t", "body": [{"type": "box", "h": 5, "fill": "PANEL"}]})
    assert any("重なる見込み" in w for w in d.warnings)  # 本文が出典の行まで届く
    assert spec_md("**{32:48}** モデル") == [("48", {"bold": True, "size": 32}), " モデル"]  # 大きさは太字の中にも書ける
    assert spec_md("***[a](#p3)***", "E") == [("a", {"bold": True, "color": "E", "link": {"page": "p3"}})] and spec_md("\\{1:x}") == "{1:x}"
    big = spec_text_h(spec_md("{32:48}<br>モデル"), 3, 11)
    assert big > spec_text_h("48<br>モデル".replace("<br>", "\v"), 3, 11)  # 大きな文字の段落は高く見込む
    d, els = run({"title": "t", "body": [
        {"type": "row", "items": [{"type": "label", "text": "GA", "w": "fit"}, {"type": "text", "text": "説明", "bold": True, "spacing": 110, "para_gap": 4, "shape": "chevron", "fill": "PANEL"}]},
        {"type": "table", "rows": [["a", "b"], ["c", "d"], ["e", "f"]], "row_h": [0.5, 0.4, 0.4], "fills": [[2, "all", "RED_SOFT"], [3, 2, "PANEL"]],
         "raw": {"zebra": False}},
        {"type": "card", "head": "h", "items": [["a", "b"]], "step": 0.6},
        {"type": "box", "h": 0.5, "fill": "PANEL", "shape": "ellipse", "raw": {"radius": 0.2}}]})
    lab, txt, tab, card, box = [e for e in els if e["call"] != "arrow"]
    assert near(lab["w"], em_width("GA", bold=True) * 11 / 72 + 2 * 11 / 72 + 0.06) and txt["kind"] == "CHEVRON" and txt["bold"] and txt["spacing"] == 110 and txt["gap"] == 4
    assert tab["row_h"] == [0.5, 0.4, 0.4] and tab["fills"] == [(1, None, RED_SOFT), (2, 1, PANEL)] and tab["zebra"] is False and card["step"] == 0.6 and box["kind"] == "ELLIPSE"
    assert [r["updateTableRowProperties"]["rowIndices"] for r in d.reqs if "updateTableRowProperties" in r] == [[0], [1, 2]]  # 行ごとの高さ
    dt, _ = run({"title": "t", "body": [{"type": "table", "header": 2, "borders": "grid", "valign": "top", "fills": [[3, 2, "NAVY"]], "rows": [
        [{"text": "a", "rowspan": 2}, {"text": "[b](https://x)", "colspan": 2}], ["c", {"text": "***d***", "fill": "RED"}],
        ["**e**", "f", {"text": "- g\n- h", "valign": "bottom"}]]}]})
    by = lambda k: [r[k] for r in dt.reqs if k in r and "cellLocation" in r[k]]
    at = lambda v: (v["cellLocation"]["rowIndex"], v["cellLocation"]["columnIndex"])
    assert [m["mergeTableCells"]["tableRange"] for m in dt.reqs if "mergeTableCells" in m] == [
        {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 2, "columnSpan": 1}, {"location": {"rowIndex": 0, "columnIndex": 1}, "rowSpan": 1, "columnSpan": 2}]
    assert {at(v): v["text"] for v in by("insertText")} == {(0, 0): "a", (0, 1): "b", (1, 1): "c", (1, 2): "d", (2, 0): "e", (2, 1): "f", (2, 2): "g\nh"}  # 覆う位置は飛ばす
    base = {at(v): v["style"] for v in by("updateTextStyle") if v["textRange"]["type"] == "ALL"}
    assert base[0, 0]["foregroundColor"] == base[1, 1]["foregroundColor"] == {"opaqueColor": paint(WHITE)} and base[0, 0]["bold"]  # 見出しの 2 行
    assert base[1, 2]["foregroundColor"] == {"opaqueColor": paint(ON_RED)} and base[2, 1]["foregroundColor"] == {"opaqueColor": paint(WHITE)}  # 濃い塗りのセルは白い文字（fills も）
    runs = {at(v): v["style"] for v in by("updateTextStyle") if v["textRange"]["type"] == "FIXED_RANGE"}
    assert runs[0, 1]["link"] == {"url": "https://x"} and runs[1, 2]["foregroundColor"] == {"opaqueColor": paint(ON_RED)} and runs[2, 0]["bold"]  # 記法（赤の地の強調は ON_RED）
    assert [at(v) for v in by("createParagraphBullets")] == [(2, 2)]  # 「- 」の段落だけのセルは箇条書き
    props = [r["updateTableCellProperties"] for r in dt.reqs if "updateTableCellProperties" in r]
    assert props[0]["tableCellProperties"] == {"contentAlignment": "TOP"} and {"contentAlignment": "BOTTOM"} in [p["tableCellProperties"] for p in props]
    assert [r["updateTableBorderProperties"]["borderPosition"] for r in dt.reqs if "updateTableBorderProperties" in r] == ["ALL"]  # grid は縦横すべて
    assert [p["tableCellProperties"]["tableCellBackgroundFill"]["solidFill"]["color"] for p in props[1:3]] == [paint(NAVY)] * 2  # 見出しの 2 行は濃紺
    _, et = run({"title": "t", "body": [{"type": "table", "header": False, "rows": [[{"text": "a", "colspan": 2, "rowspan": 2}], []]}]})
    assert next(e for e in et if e["call"] == "table")["rows"][1] == []  # 上の rowspan が全部の列を覆う行は []（HTML の空の tr）
    assert near(table_h([1, 1], [["a", "b"], ["c"]]), table_h([1, 1], [["a", "b"], ["c", ""]]))  # pages.py の短い行は、前の d.table と同じく空のセルで埋める
    make_deck(lambda d: d.table(d.page("t"), 0, 0, [1, 1], [["a", "b"], ["c"]]), "short")
    db, _ = run({"title": "t", "body": [{"type": "table", "header": False, "first_col": False, "rows": [["{32:A}<br>{32:B}\n小"]]}]})
    assert [r["updateParagraphStyle"]["style"] for r in db.reqs if "updateParagraphStyle" in r and r["updateParagraphStyle"].get("cellLocation") and
            r["updateParagraphStyle"]["textRange"]["type"] == "FIXED_RANGE"] == [{"lineSpacing": 100}]  # 大きな文字の段落の行間は見込みと同じ 100（PR #72 のレビュー）
    tall = {"text": "1\n2\n3\n4", "rowspan": 2}
    assert near(table_h([1, 1], [[tall, "x"], ["y"]], row_h=0.1, header=False), 0.16 + spec_text_h("1\n2\n3\n4", 0.8, 11, 120))  # 覆う行に足りない分を足す
    assert near(table_h([1, 1], [[{"text": "x", "rowspan": 2}, "x"], ["y"]], row_h=0.1, header=False), 2 * (0.16 + spec_text_h("x", 0.8, 11, 120)))
    hits = spec_out_hits(d)
    assert [h.split("（")[0] for h in hits] == ["p1: table.raw.zebra", "p1: box.raw.radius"], hits
    assert "形の radius で書ける" in hits[-1] and "形の zebra で書ける" in hits[0]
    dd = Deck("x")
    dd.spec_esc = [("s", "l", "table.raw.border")]
    dd.slides = ["s"]
    assert "slides.py stats" in spec_out_hits(dd)[0]  # 形にない引数は、形に足す提案に
    with tempfile.TemporaryDirectory() as t:
        log = Path(t) / "spec_raw.jsonl"
        real_log = globals()["spec_log_path"]
        globals()["spec_log_path"] = lambda: log
        try:
            spec_record(d, "deck1")
            spec_record(d, "deck1")  # 組み直しは最後の数だけ
            dd = Deck("資料 2")
            dd.resolved, dd.spec_esc = [{"type": "page"}], [("s", "l", "table.raw.zebra")]
            spec_record(dd, "deck2")
            with contextlib.redirect_stdout(io.StringIO()):
                rows = spec_stats(log)
            assert rows["table.raw.zebra"] == [2, 2] and rows["box.raw.radius"] == [1, 1]
            gone = Deck("資料 1")
            gone.resolved = [{"type": "page"}]  # 最後の raw を外して組み直した JSON のデッキ
            spec_record(gone, "deck1")
            with contextlib.redirect_stdout(io.StringIO()):
                rows = spec_stats(log)
            assert "box.raw.radius" not in rows and rows["table.raw.zebra"] == [1, 1]  # 古い数は残らない
            tmp = Deck("tmp_試し")
            tmp.spec_esc = dd.spec_esc
            spec_record(tmp, "deck3")
            assert len(log.read_text().splitlines()) == 4  # tmp の資料は数えない
        finally:
            globals()["spec_log_path"] = real_log
        f = Path(t) / "p.json"
        f.write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "t", "body": [
            {"type": "box", "h": 1, "raw": {"kind": "CAN", "radius": 0.2, "dash": True}}, {"type": "stack", "items": [{"type": "table", "rows": [["a"]], "raw": {"row_h": 0.5}}]},
            {"type": "text", "text": "a", "raw": {"align": "CENTER", "fill": NAVY, "kind": "STAR"}},
            {"type": "table", "rows": [["a"]], "raw": {"mono_cols": [0], "zebra": False}}]}))
        with contextlib.redirect_stdout(io.StringIO()):
            assert spec_upgrade([f]) == 7
        up = json.loads(f.read_text())
        assert up["body"][0] == {"type": "box", "h": 1, "shape": "can", "radius": 0.2, "dash": True} and up["body"][1]["items"][0]["row_h"] == 0.5
        assert up["body"][2] == {"type": "text", "text": "a", "raw": {"kind": "STAR"}, "align": "center", "fill": "NAVY"}  # 値を形の書き方に直す。形にない形は raw に残す
        assert up["body"][3] == {"type": "table", "rows": [["a"]], "raw": {"mono_cols": [0]}, "zebra": False}  # 数え始めの違う mono_cols は移さない
        log.write_text('{"deck": "d1", "uses": {"a": 1}}\n{"deck": \n')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            assert spec_stats(log) == {"a": [1, 1]} and "1 行を飛ばした" in err.getvalue()  # 途中で切れた行は飛ばす
        svg, jpg = Path(t) / "a.svg", Path(t) / "a.jpg"
        svg.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="200px" height="100">')
        jpg.write_bytes(b"\xff\xd8\xff\xff\xc0\x00\x11\x08\x00\x64\x00\xc8" + b"\0" * 16)  # 詰めの FF のあとの SOF0（高さ 100・幅 200）
        assert image_ratio(svg) == image_ratio(jpg) == 2
    _, lg = run({"title": "t", "body": [{"type": "row", "items": [{"type": "card", "image": "https://x/a.png", "head": "製品"}, {"type": "card", "num": 1, "head": "段"},
                                                                   {"type": "card", "num": 2, "head": "段", "text": "1 行の本文"}]}]})
    lc, heads = [e for e in lg if e["call"] == "card"], [e for e in lg if e["loc"].endswith(".head")]
    assert len(lc) == len(heads) == 3 and all(near(t["y"] - c["y"], MARK_TOP) for t, c in zip(heads, lc))  # 見出しの上は、印が高さを決めるロゴのカードも、伸ばされたカードも同じ（PR のレビュー）
    _, lg = run({"title": "t", "body": [{"type": "row", "items": [{"type": "card", "num": 1, "head": "段", "text": "1 行の本文"},
                                                                   {"type": "card", "num": 2, "head": "段", "text": "長い本文が続く。" * 12}]}]})
    lc, nm = [e for e in lg if e["call"] == "card"], [e for e in lg if e["call"] == "num"]
    assert near(nm[0]["cy"] - lc[0]["y"], nm[1]["cy"] - lc[1]["y"])  # 伸ばされて下が空いた短い文字のカードも、印を 1 行目にそろえる（2026-10-20 の画像）
    _, lg = run({"title": "t", "body": [{"type": "row", "items": [{"type": "card", "num": 1, "head": "段", "text": "1 行の本文"},
                                                                   {"type": "card", "num": 2, "head": "段", "text": "本文<br>2 行目"}, {"type": "card", "num": 3}]}]})
    lc, nm = [e for e in lg if e["call"] == "card"], [e for e in lg if e["call"] == "num"]
    assert near(nm[0]["cy"] - lc[0]["y"], nm[1]["cy"] - lc[1]["y"])  # 短い文字どうしでも、いちばん高いカードと印の高さがそろう（PR のレビュー）
    assert near(nm[2]["cy"] - lc[2]["y"], MARK_IN + MARK / 2)  # 印だけのカードは、1 行目にそろえず、印の上を MARK_IN のままにする（PR のレビュー）
    two = {"type": "card", "num": 1, "head": "段", "text": "本文<br>2 行目"}
    two["h"] = round(SpecPage(Path(".")).measure(two, 5, "c") + 0.005, 3)  # 中身の高さとほぼ同じ h（上寄せで、下はほとんど空かない）
    _, lg = run({"title": "t", "body": [{"type": "row", "w": 10, "items": [two, {"type": "card", "num": 2, "head": "段"}]}]})
    lc, nm = [e for e in lg if e["call"] == "card"], [e for e in lg if e["call"] == "num"]
    assert near(nm[0]["cy"] - lc[0]["y"], nm[1]["cy"] - lc[1]["y"])  # h を書いたカードも、隣と印の高さがそろう（PR #76 のレビュー）
    card = {"type": "card", "num": 1, "head": "段", "text": "1 行の本文"}
    _, lg = run({"title": "t", "body": [{"type": "row", "items": [card, card, {"type": "text", "text": "x", "fill": "PANEL"}]}]})
    lc, nm = [e for e in lg if e["call"] == "card"], [e for e in lg if e["call"] == "num"]
    assert near(nm[0]["cy"], nm[1]["cy"])  # 伸びるのがほかの部品だけでも、印は 1 行目
    for text in ("1 行の本文", "本文<br>2 行目"):
        for v in (None, "middle"):
            _, lg = run({"title": "t", "body": [{"type": "card", "num": 1, "head": "段", "text": text, "w": 5} | ({"valign": v} if v else {})]})
            nm, hd, tx = (next(e for e in lg if e["call"] == "num" and c == "num" or e["loc"].endswith(f".{c}")) for c in ("num", "head", "text"))
            # 印は、短い文字でも 1 行目にそろえる（1 枚ずつ frame に置いたカードの番号の高さがそろう。2026-10-20 の p18）。
            # valign middle は、最終行の下の行間の空きを除いた文字の中央（本文の行数によらない。PR のレビュー）
            assert near(nm["cy"], (hd["y"] + tx["y"] + tx["h"] - (MARK_TOP - MARK_END)) / 2 if v else hd["y"] + 12 * 1.2 / 72 / 2), (text, v)
    _, lg = run({"title": "t", "body": [{"type": "frame", "h": 1.8, "items": [{"type": "card", "num": i + 1, "head": "段", "text": text, "x": 3 * i, "y": 0, "w": 2.8}
                                                                          for i, text in enumerate(("1 行の本文", "本文<br>2 行目"))]}]})
    nm = [e for e in lg if e["call"] == "num"]
    assert near(nm[0]["cy"], nm[1]["cy"])  # frame に 1 枚ずつ置いたカードも、本文の行数によらず番号の高さがそろう（2026-10-20 の p18）
    short, long = {"type": "card", "num": 1, "head": "段", "text": "1 行の本文"}, {"type": "card", "num": 1, "head": "段", "text": "長い本文が続く。" * 12}
    for c, warned in ((short | {"h": 1.6}, True), (short | {"h": 1.6, "valign": "middle"}, False), (short | {"h": 1.6, "valign": "top"}, False), (short, False),
                      ({"type": "card", "head": "段", "text": "1 行の本文", "fill": "NAVY", "h": 1.6}, True),  # 印のない濃い地のカードも、印のあるカードと同じく組むので見る
                      (long | {"h": round(SpecPage(Path(".")).measure(long, 4, "c") + 0.3, 2)}, False)):
        d, _ = run({"title": "t", "body": [{"type": "frame", "h": 2.5, "items": [c | {"x": 0, "y": 0, "w": 4}]}]})
        assert any("\"valign\": \"middle\" にするか" in w for w in d.warnings) == warned, c  # h で高くした低い中身のカードは middle を勧める（行数でなく高さで見る）
    d, _ = run({"title": "t", "body": [{"type": "row", "items": [short, long]}]})
    assert not any("\"valign\": \"middle\" にするか" in w for w in d.warnings)  # 隣に合わせて伸ばされたカードは、見出しをそろえる上寄せなので出さない
    _, lg = run({"title": "t", "body": [{"type": "card", "image": "https://x/a.png", "head": "製品"}]})
    lc, li = (next(e for e in lg if e["call"] == c) for c in ("card", "image"))
    assert near(li["y"] - lc["y"], lc["y"] + lc["h"] - li["y"] - li["h"])  # 印が高さを決めるカードは、印の上下の空きが同じ
    _, lg = run({"title": "t", "body": [{"type": "card", "image": "https://x/a.png"}]})
    lc, li = (next(e for e in lg if e["call"] == c) for c in ("card", "image"))
    assert near(li["y"] - lc["y"], MARK_IN) and near(lc["y"] + lc["h"] - li["y"] - li["h"], MARK_IN)  # 印だけのカードは、印の上下を MARK_IN にする
    _, lg = run({"title": "t", "body": [{"type": "card", "num": 1, "text": "{32:Revenue}\nDetails\nMore details", "w": 5}]})
    tx, nm = (next(e for e in lg if e["call"] == c) for c in ("text", "num"))
    assert near(nm["cy"], tx["y"] + 32 * 1.2 / 72 / 2)  # 見出しのないカードは、本文の 1 行目の大きさで印をそろえる（PR #74 のレビュー）
    _, lg = run({"title": "t", "body": [{"type": "card", "image": "https://x/a.png", "align": "center"}]})
    lc, li = (next(e for e in lg if e["call"] == c) for c in ("card", "image"))
    assert near(li["y"] - lc["y"], MARK_IN) and near(lc["y"] + lc["h"] - li["y"] - li["h"], MARK_IN)  # 上に印を置くカードも同じ
    long = {"type": "card", "image": "https://x/a.png", "head": "製品", "text": "長い本文が続く。" * 12, "w": 4}
    need = SpecPage(Path(".")).measure(long, 4, "c", least=True)
    d, lg = run({"title": "t", "body": [long | {"h": round(need + 0.005, 3)}]})
    lc, li = (next(e for e in lg if e["call"] == c) for c in ("card", "image"))
    assert not any("収まらない" in w for w in d.warnings) and li["y"] >= lc["y"] - 1e-9  # least の高さに縮めても、1 行目にそろえた印は枠の上から出ない（PR のレビュー）
    globals()["iconify"], real_iconify = (lambda name, color=TEXT, w=512: f"https://x/{name}.png"), iconify  # アイコンの名前を問い合わせない
    try:
        d, els = run({"title": "t", "body": [{"type": "row", "items": [
        {"type": "card", "icon": "tabler:database", "head": "表", "text": "取り込んだ表"},
        {"type": "card", "num": 2, "head": "段", "text": "整える"},
        {"type": "card", "image": "https://x/a.png", "head": "製品", "text": "ロゴ", "align": "center"},
        {"type": "stat", "value": "16", "unit": "モデル", "label": "本番の数", "sub": "2026 年 9 月"}]},
        {"type": "card", "icon": "tabler:server", "head": "名前", "valign": "middle", "fill": "NAVY", "w": 3}]})
    finally:
        globals()["iconify"] = real_iconify
    cards = [e for e in els if e["call"] == "card"]
    icon, num, img = (next(e for e in els if e["call"] == c) for c in ("icon", "num", "image"))
    assert len({c["h"] for c in cards[:3]}) == 1 and cards[0]["line"] == RULE and cards[3]["line"] is None  # 列の高さをそろえる。濃い地のカードは枠線なし
    assert near(icon["x"], cards[0]["x"] + MARK_IN) and near(num["cx"], cards[1]["x"] + MARK_IN + MARK / 2) and near(img["x"], cards[2]["x"] + (cards[2]["w"] - MARK_IMG) / 2)
    by = {e["loc"]: e for e in els}
    h0, b1 = by["spec.body[0].items[0].head"], by["spec.body[0].items[1].text"]
    assert h0["parts"] == [("表", {"bold": True, "size": 12, "color": "HEAD"})] and near(h0["x"], icon["x"] + MARK + MARK_GAP) and by["spec.body[0].items[2].head"]["align"] == "CENTER"
    assert b1["bullets"] is False and not by["spec.body[0].items[1].head"].get("bullets")  # 見出しは本文と別の枠
    stat = by["spec.body[0].items[3]"]
    assert stat["parts"][:2] == [("16", {"size": 32, "bold": True, "color": RED_TEXT}), (" モデル", {"size": 16, "bold": True, "color": RED_TEXT})] and stat["fill"] == CARD
    dark = by["spec.body[1].head"]
    assert dark["color"] == WHITE and dark["parts"][0][1]["color"] == WHITE and near(dark["y"], cards[3]["y"] + (cards[3]["h"] - max(dark["h"], 0.2)) / 2)  # 上下の中央
    assert any(r.get("updateTextStyle", {}).get("style", {}).get("foregroundColor") == {"opaqueColor": paint(WHITE)} for r in d.reqs)
    _, sl = run({"type": "slide", "bg": "NAVY", "body": [{"type": "text", "text": "***地の文***"}, {"type": "text", "text": "枠", "line": "RULE"}]})
    assert sl[0]["color"] == sl[1]["color"] == WHITE and sl[0]["parts"][0][1]["color"] == RED_ON_NAVY  # 濃い地のページの文字。枠線だけの箱も地を塗らない
    _, dk = run({"title": "t", "body": [{"type": "card", "fill": "NAVY", "head": "見出し", "text": "***強調***"}]})
    dh, dt = (next(e for e in dk if e["loc"] == f"spec.body[0].{k}") for k in ("head", "text"))
    assert dh["color"] == WHITE and dh["parts"][0][1]["color"] == WHITE and dt["parts"][0][1]["color"] == RED_ON_NAVY  # 濃い地の印のないカードも地から色を決める
    assert near(dt["x"], X + MARK_IN) and not any(e["call"] in ("icon", "num", "image") for e in dk)
    globals()["iconify"], real_iconify = (lambda name, color=TEXT, w=512: f"https://x/{name}.png"), iconify
    try:  # grid の中のアイコンと番号は、列の幅に広げず決まった大きさで置き、下の部品はその下端から
        _, gi = run({"title": "t", "body": [{"type": "grid", "cols": 2, "items": [{"type": "icon", "name": "tabler:a", "size": 0.5}, {"type": "num", "n": 1}]},
                                            {"type": "text", "text": "下"}]})
    finally:
        globals()["iconify"] = real_iconify
    ic, nm, below = gi
    assert ic["size"] == 0.5 and near(nm["cx"], cols(2)[1][0] + NUM["medium"][0] / 2) and near(below["y"], Y_BODY_NOLEAD + 0.5 + GAP_BODY)
    _, bc = run({"title": "t", "body": [{"type": "card", "text": "{64:48}"}, {"type": "text", "text": "下"}]})
    assert bc[0]["h"] > 64 * 1.2 / 72 and near(bc[-1]["y"], bc[0]["y"] + bc[0]["h"] + GAP_BODY)  # 印のないカードも文字ごとの大きさで高さを見込む
    _, mo = run({"title": "t", "body": [{"type": "text", "text": "i" * 80, "w": 1, "mono": True}, {"type": "label", "text": "iiii", "w": "fit", "mono": True}]})
    assert near(mo[0]["h"], est_lines("i" * 80, 1, 11, True) * 11 * 1.2 * 1.25 / 72 + 0.02)  # 等幅の字幅で行数を見る
    assert near(mo[1]["w"], 4 * MONO_EM * 11 / 72 + 2 * 11 / 72 + 0.06)
    for bad, want in [({"type": "card", "icon": "a:b", "num": 1}, "どれか 1 つ"), ({"type": "card", "head": "h", "align": "center"}, "印（icon・num・image）のあるカード"),
                      ({"type": "card", "icon": "a:b", "align": "center", "valign": "middle"}, "一緒に使えない"),
                      ({"type": "list", "items": [{"icon": "a:b", "num": 1, "text": "t"}]}, "どれか 1 つ"), ({"type": "list", "items": [{"icon": "a:b"}]}, "text か head"),
                      ({"type": "list", "items": ["a"], "raw": {"x": 1}}, "知らないキー raw"), ({"type": "list", "items": ["a", " "]}, "text か head"), ({"type": "list", "items": ["***  ***"]}, "text か head"),
                      ({"type": "list", "items": [{"head": "h", "text": "- a\n- b"}]}, "箇条書き"), ({"type": "list", "size": "large", "items": ["a"], "w": 0.8}, "幅が足りない"),
                      ({"type": "card", "icon": "a:b", "shape": "round_rectangle"}, "num を書いたカード"), ({"type": "num", "n": 1, "shape": "chevron"}, "shape")]:
        try:
            make_deck(lambda x: x.spec({"title": "t", "body": [bad]}), "x")
            raise AssertionError(f"通した: {bad}")
        except SystemExit as e:
            assert want in str(e), (want, str(e))
    # list: 印の中心を項目の 1 行目（見出しがあればその行）の中心にそろえ、番号は start から項目の順。印を書いた項目が勝つ
    globals()["iconify"], real_iconify = (lambda name, color=TEXT, w=512: f"https://x/{name}.png"), iconify
    try:
        d, li = run({"title": "t", "body": [{"type": "list", "start": 3, "items": ["一", "長い文" * 40, {"icon": "tabler:a", "head": "見出し", "text": "補足"}]},
                                            {"type": "list", "icon": "tabler:check", "items": [{"num": 9, "text": "九"}, "印", {"head": " ", "text": "本"}, {"head": "見", "text": "*** ***"}]},
                                            {"type": "row", "items": [{"type": "num", "n": 1}, {"type": "text", "text": "文"}]}]})
    finally:
        globals()["iconify"] = real_iconify
    by = {e["loc"]: e for e in li}
    n0, t0, n1, t1, h2, s2 = (by[f"spec.body[0].items[{i}].{k}"] for i, k in ((0, "num"), (0, "text"), (1, "num"), (1, "text"), (2, "head"), (2, "text")))
    one, d0 = 11 * 1.2 / 72, NUM["medium"][0]
    assert (n0["n"], n1["n"]) == (3, 4) and near(t0["y"] + one / 2, n0["cy"]) and near(t1["y"] + one / 2, n1["cy"])  # 2 行の項目も 1 行目（行間 125% の増えた分は 1 行目の下）
    assert near(t0["x"], X + d0 + MARK_GAP) and near(n1["cy"] - d0 / 2, t0["y"] - (d0 - one) / 2 + d0 + LIST_GAP)  # 1 行の項目の高さは円の直径
    ic = by["spec.body[0].items[2].icon"]
    assert near(h2["y"] + 12 * 1.2 / 72 / 2, ic["y"] + d0 / 2) and h2["color"] == HEAD and s2["color"] == SUB and t0["color"] == TEXT and near(s2["x"], t0["x"])
    assert by["spec.body[1].items[0].num"]["n"] == 9 and by["spec.body[1].items[1].icon"]["name"] == "tabler:check"
    assert "spec.body[1].items[2].head" not in by and by["spec.body[1].items[2].text"]["color"] == TEXT and "spec.body[1].items[3].text" not in by  # 空白だけの見出しと本文は置かない
    assert any("list にする" in w for w in d.warnings)  # row に番号と文字を並べたら知らせる
    d, _ = run({"title": "t", "body": [{"type": "row", "items": [{"type": "num", "n": 1}, {"type": "text", "text": "文", "fill": "PANEL"}]}]})
    assert not any("list にする" in w for w in d.warnings)  # 塗りのある文字は行の高さまで伸びるので知らせない
    assert first_pt([("48", {"size": 32}), "件\n", ("次", {"size": 40})], 11, 5) == 32 and first_pt("a\nb", 11, 5) == 11 and first_pt([("小", {"size": 8})], 11, 5) == 8
    assert first_pt([(" ", {"size": 20}), "abc"], 11, 5) == 20 and first_pt(["あ" * 20, ("大", {"size": 32})], 11, 1.5) == 11  # 1 行目の大きさ（折り返した先の大きな文字は見ない）
    # 角丸の番号: 高さは円の直径、幅は数字に合わせる。list の印の列はいちばん広い番号に合わせて中央に置き、row・card の文字は見える幅の右から
    wide = num_w("10", "medium", "round_rectangle")
    assert num_w(1, "medium", "round_rectangle") == d0 == num_w("10") < wide
    globals()["iconify"] = lambda name, color=TEXT, w=512: f"https://x/{name}.png"
    try:
        _, rr = run({"title": "t", "body": [{"type": "list", "shape": "round_rectangle", "digits": 2, "start": 9, "items": ["九", "十"]},
                                            {"type": "list", "shape": "round_rectangle", "start": 9, "items": ["九", {"icon": "tabler:a", "text": "a"}, "十一"]},
                                            {"type": "row", "items": [{"type": "num", "n": "01", "shape": "round_rectangle"}, {"type": "text", "text": "文", "fill": "PANEL"}]},
                                            {"type": "card", "num": 10, "shape": "round_rectangle", "head": "見出し"}]})
    finally:
        globals()["iconify"] = real_iconify
    by = {e["loc"]: e for e in rr}
    a, b = by["spec.body[0].items[0].num"], by["spec.body[0].items[1].num"]
    assert (a["n"], b["n"], a["shape"]) == ("09", "10", "round_rectangle") and near(a["cx"], X + wide / 2) and near(by["spec.body[0].items[0].text"]["x"], X + wide + MARK_GAP)
    n9, ic, n11 = by["spec.body[1].items[0].num"], by["spec.body[1].items[1].icon"], by["spec.body[1].items[2].num"]
    assert (n9["n"], n11["n"]) == (9, 11) and near(n9["cx"], n11["cx"]) and near(ic["x"] + d0 / 2, n9["cx"])  # 桁の違う番号とアイコンは列の中央
    rn, rt = by["spec.body[2].items[0]"], by["spec.body[2].items[1]"]
    assert near(rt["x"], X + num_w("01", "medium", "round_rectangle") + GAP) and near(rn["cy"] - d0 / 2, rt["y"])  # row の幅は見える幅、高さは直径
    cn, ch = by["spec.body[3].num"], by["spec.body[3].head"]
    assert cn["shape"] == "round_rectangle" and near(ch["x"], cn["cx"] + wide / 2 + MARK_GAP)
    with tempfile.TemporaryDirectory() as t:
        here = os.getcwd()
        os.chdir(t)
        try:
            Path("c.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "component", "type": "stat", "value": "3"}))
            Path("p.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "t"}))
            Path("c.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "component", "type": "label", "text": "札"}))
            real_dp, real_argv = default_pages, sys.argv
            globals()["default_pages"] = lambda: (_ for _ in ()).throw(AssertionError("ファイルを渡したのに default_pages を呼んだ"))
            sys.argv = ["slides.py", "dry", "c.json"]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    main()  # pages.py も deck.json もないフォルダで、渡したファイルだけを見る
            finally:
                globals()["default_pages"], sys.argv = real_dp, real_argv
            Path("c.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "component", "type": "stat", "value": "3"}))
            Path("l.json").write_text("[]")
            assert [lint_scope(f) for f in ("deck.json", "pages.py", "c.json", "p.json", "pages_a.py", "l.json")] == ["deck", "deck", "component", "page", "page", "page"]
            Path("bad.json").write_text("{壊れた")
            assert lint_scope("bad.json") == "page" and file_kind("bad.json") is None and file_kind("pages.py") is None  # 読めない JSON は、読むところが場所を付けて止める
        finally:
            os.chdir(here)
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 2, "items": [  # 囲みの中に見出しとカードを入れるのはよい。横 1 列の流れは row を勧める
        {"type": "box", "x": 0, "y": 0, "w": 6, "h": 2, "fill": "PANEL"}, {"type": "text", "text": "囲みの見出し", "x": 0.2, "y": 0.1, "w": 3},
        {"type": "label", "text": "A", "id": "a", "x": 0.2, "y": 1, "w": 1}, {"type": "label", "text": "B", "id": "b", "x": 2, "y": 1, "w": 1},
        {"type": "label", "text": "C", "id": "c", "x": 4, "y": 1, "w": 1}, {"type": "arrow", "from": "a", "to": "b"}, {"type": "arrow", "from": "b", "to": "c"}]}]})
    assert not any("横 1 列" in w for w in d.warnings)  # 囲みの見出しがあるので 1 列ではない
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 1, "items": [
        {"type": "label", "text": "A", "id": "a", "x": 0, "y": 0, "w": 1}, {"type": "label", "text": "B", "id": "b", "x": 2, "y": 0.1, "w": 1},
        {"type": "label", "text": "C", "id": "c", "x": 4, "y": 0, "w": 1}, {"type": "arrow", "from": "a", "to": "b"}, {"type": "arrow", "from": "b", "to": "c"}]}]})
    assert any("横 1 列" in w for w in d.warnings)
    d, _ = run({"title": "t", "body": [{"type": "box", "h": 0.5, "fill": "PANEL", "shape": "rectangle"}, {"type": "box", "h": 0.5, "line": "RULE", "shape": "rectangle"}]})
    assert sum("四角（shape: rectangle）" in w for w in d.warnings) == 1  # 塗りの箱だけ知らせる（枠線だけの箱は四角が既定）
    mid = lambda t, h=None: {"type": "card", "num": 1, "valign": "middle", "head": "見出し", "text": t, "w": 5, **({"h": h} if h else {})}  # #52 の番号のある上下中央のカード（幅 5 in）
    one, two = "1 行の本文", "2 行になる本文。" * 4
    sp = SpecPage(Path("."))
    need = sp.measure(mid(two), 5, "m", least=True)
    assert sp.measure(mid(one), 5, "m") > 0.65 and need > 0.65  # 1 行でも h を省けば 0.6 in より高い（詰めるのは使い方のうち）。2 行は文字が 0.6 in に収まらない
    small = {"type": "label", "text": "小さい札", "size": 8}
    assert sp.measure(small, 2, "s") == 0.4 and sp.measure(small, 2, "s", least=True) < 0.35  # 札の 0.4 in は既定の下限で、文字に要る高さではない
    steps = {"type": "card", "head": "見出し", "items": [["項目", "説明の文"]] * 3, "step": 1.0}
    assert near(card_h(4, "見出し", items=[("項目", "説明の文")] * 3, step=1.0, least=True), 2.5 + card_h(4, items=[("項目", "説明の文")], least=True) - 0.2)  # 最後の項目の下端まで（後ろの空きは要らない）
    assert sp.measure(steps, 4, "c") > sp.measure(steps, 4, "c", least=True) + 0.25
    d, _ = run({"title": "t", "body": [{"type": "stack", "items": [  # 文字に要る高さより 0.05 in を超えて低いものだけ。row の中も、伸ばす前の h で見る
        mid(one, 0.6), mid(two, round(need - 0.04, 2)), mid(two, 0.6), {"type": "row", "items": [mid(two, 0.6), {"type": "card", "head": "高い", "text": two * 6}]},
        {"type": "text", "text": two * 3, "h": 0.2}, {"type": "text", "text": two * 3, "fill": "PANEL", "h": 0.2}, {"type": "stat", "value": "3", "label": "件", "h": 0.3},
        small | {"h": 0.3}, {"type": "card", "num": 1, "head": "見出し", "valign": "top", "w": 5, "h": 0.4},  # 上寄せの印のあるカードは、上の空きと印が収まるかも見る
        {"type": "card", "head": "Heading", "text": "Body", "w": 5, "h": 0.9}]}]})  # 印のないカードの本文の枠は、下端の 0.1 in 上で終わる（PR #54 のレビュー）
    w = "\n".join(d.warnings)
    assert w.count("収まらない見込み") == 6 and "items[9]（card）" in w and "items[2]（card）: h 0.6 in では" in w and "items[3].items[0]（card）" in w and "items[5]（text）" in w and "items[6]（stat）" in w, w  # 塗りのない文字は見ない
    assert "items[8]（card）" in w and "items[7]" not in w, w
    _, els = run({"title": "t", "body": [{"type": "card", "icon": "tabler:database", "valign": "middle", "head": "kuromoji（Java）", "text": "Lucene の日本語", "w": 2.3, "h": 0.8}]})
    hd, tx = (next(e for e in els if e["loc"] == f"spec.body[0].{k}") for k in ("head", "text"))
    assert near(hd["h"], 0.4) and near(tx["y"], hd["y"] + hd["h"] + HEAD_GAP)  # 太字の見出しは Bold の字幅（1.47 in）で 1.44 in の枠から折れる。本文はその下（2026-10-19。Regular の字幅で 1 行と見て、本文に重なった）
    assert near(card_top(5, "見出し"), 0.5 + CARD_DOWN) and near(card_top(2.5, "長い見出しが二行に折れるカード"), 0.7 + CARD_DOWN)  # d.card も、折り返す見出しの分だけ本文を下げる
    kj = "kuromoji（Java）"  # Regular で 1 行、Bold で 2 行になる幅（12pt で 1.44 in）。太字で描く部品は、どれも太字の幅で見込む
    assert est_lines(kj, 1.44, 12) == 1 and est_lines(kj, 1.44, 12, bold=True) == 2
    assert sp.measure({"type": "text", "text": kj, "size": 12, "bold": True}, 1.44, "t") > sp.measure({"type": "text", "text": kj, "size": 12}, 1.44, "t")
    assert sp.fixed_w({"type": "label", "text": kj, "w": "fit"}) > sp.fixed_w({"type": "label", "text": kj, "w": "fit", "bold": False})  # 札は既定で太字
    assert table_h([1.64], [[kj]], 12, 0) > table_h([1.64], [[kj]], 12, 0, header=False, first_col=False)  # 表の見出しの行と 1 列目
    narrow = 1.44 + 2 * PAD + 2 * INSET  # 本文の枠の内側が 1.44 in のカード
    assert near(card_h(narrow, items=[(kj, "説明")], size=12) - card_h(narrow, items=[("短い", "説明")], size=12), 12 * 1.2 * 1.25 / 72)  # 項目の見出しは太字
    assert near(sp.measure({"type": "card", "text": "**MMMM** MMMMM **MMMM**"}, 1.36, "c"), CARD_DOWN + 0.1 + 3 * 11 * 1.2 * 1.25 / 72 + 2 * INSET + CARD_END)  # 太さの交ざる段落も語ごとに折り返す（3 語が 3 行。PR #69 のレビュー）
    assert run_lines([("あ" * 9, 11, False), (" Codex", 11, True)], 10 * 11 / 72) == 2 and run_lines([("a\nb", 11, False)], 1) == 2
    assert all_bold([(kj, {"bold": True})]) and not all_bold([(kj, {"bold": True}), "地の文"]) and all_bold(kj, True) and widest_em(f"**{kj}**") == em_width(kj, bold=True)
    d, els = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [  # 位置の確かめ（tangles）。囲みの中の線と、線の両端の部品は数えない
        {"type": "box", "x": 0, "y": 0, "w": 9, "h": 3, "fill": "PANEL"},
        {"type": "label", "id": "a", "text": "A", "x": 0.2, "y": 1, "w": 2, "h": 0.6}, {"type": "label", "id": "m", "text": "途中", "x": 3.5, "y": 1, "w": 1.2, "h": 0.6},
        {"type": "label", "id": "c", "text": "C", "x": 6, "y": 1, "w": 2, "h": 0.6}, {"type": "card", "head": "はみ出す", "x": 7, "y": 1.4, "w": 1.8},
        {"type": "text", "text": "② 渡す", "x": 2.2, "y": 2.2, "w": 6, "align": "center"},
        {"type": "arrow", "from": [2.2, 1.3], "to": [6, 1.3]}, {"type": "arrow", "from": [5, 0.1], "to": [5, 2.9]},
        {"type": "arrow", "from": "m", "to": "c", "label": "① 要求"}]}]})
    w = "\n".join(d.warnings)
    assert "札（label）が線に重なる" not in w  # 横の線の札は線の上に離れる
    assert "items[6]: 矢印の線が spec.body[0].items[2]（label）の上を通る" in w and "items[7]: 矢印の線が spec.body[0].items[5]（text）の上を通る" in w, w  # 文字のあるところだけ見る
    assert "items[6] と spec.body[0].items[8]: 矢じりの先が 1 点に集まる" in w and "items[3]（label）と spec.body[0].items[4]（card）が一部だけ重なる" in w, w
    assert w.count("上を通る") == 2 and w.count("重なる") == 1, w  # 囲みの box、両端の部品、自分の札は数えない
    dc, ec = run({"title": "t", "body": [{"type": "frame", "h": 2, "items": [  # カードの shape は番号の形。円の番号のカードも、箱としてつなぎ、重なりを見る
        {"type": "card", "id": "a", "num": 1, "shape": "ellipse", "head": "番号", "x": 0, "y": 0, "w": 3}, {"type": "label", "id": "b", "text": "B", "x": 4, "y": 0, "w": 2, "h": 0.6},
        {"type": "label", "text": "C", "x": 2.5, "y": 0.5, "w": 1, "h": 0.6}, {"type": "arrow", "from": "a", "to": "b"},
        {"type": "num", "n": 1, "shape": "ellipse", "x": 0, "y": 1.2}, {"type": "list", "shape": "ellipse", "items": ["項目"], "x": 2, "y": 1.2, "w": 2},
        {"type": "label", "text": "D", "x": 0.2, "y": 1.4, "w": 2.2, "h": 0.4}]}]})
    w = "\n".join(dc.warnings)
    assert next(e for e in ec if e["call"] == "arrow")["link"][0] == "spec.body[0].items[0]" and "items[0]（card）と spec.body[0].items[2]（label）が一部だけ重なる" in w
    assert "items[4]（num）と spec.body[0].items[6]（label）が一部だけ重なる" in w and "items[5]（list）と spec.body[0].items[6]（label）が一部だけ重なる" in w, w
    arr, lab = next(e for e in els if e["loc"] == "spec.body[0].items[8]"), next(e for e in els if e["loc"] == "spec.body[0].items[8].label")
    assert lab["call"] == "text" and lab["parts"] == "① 要求" and near(lab["x"] + lab["w"] / 2, (arr["x1"] + arr["x2"]) / 2) and near(lab["y"] + lab["h"] + LABEL_GAP, arr["y1"])  # 横の線の上の中央
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [  # 囲みの辺に近い縁のある部品（slides-visual-044）。塗りのない文字は数えない
        {"type": "box", "x": 0, "y": 0, "w": 9, "h": 3, "line": "RULE"}, {"type": "card", "head": "端", "x": 0, "y": 1, "w": 3},
        {"type": "label", "text": "内", "x": 4, "y": 1, "w": 2}, {"type": "text", "text": "見出し", "x": 0.05, "y": 0.05, "w": 3}]}]})
    near_edge = [w for w in d.warnings if "囲みの" in w]
    assert len(near_edge) == 1 and "items[1]（card）が囲みの spec.body[0].items[0] の辺から 0.00 in" in near_edge[0], d.warnings
    col = lambda t: {"type": "stack", "items": [{"type": "card", "head": "見出し", "text": t}, {"type": "code", "text": "x = 1"}]}
    d, _ = run({"title": "t", "body": [{"type": "row", "items": [col("短い"), col("長い。" * 30), col("短い")]}]})  # 同じ形の列の段がずれる（slides-visual-024）
    assert any("grid（cols: 3）" in w for w in d.warnings), d.warnings
    for row_e in ({"type": "row", "items": [col("短い"), col("短い")]}, {"type": "row", "arrows": True, "items": [col("短い"), col("長い。" * 30)]},  # 段がそろう列、grid にすると矢印が消える列、
                  {"type": "row", "widths": [2, 1], "items": [col("短い"), col("長い。" * 30)]}):  # 幅の比が消える列
        d, _ = run({"title": "t", "body": [row_e]})
        assert not any("grid" in w for w in d.warnings), (row_e, d.warnings)
    lab = lambda i, x, y: {"type": "label", "id": i, "text": i, "x": x, "y": y, "w": 1.5, "h": 0.5}
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [lab("a", 0, 0), lab("b", 4, 2), {"type": "arrow", "from": "a", "to": "b", "route": "bent"}]}]})  # 1 本の流れの折れ線（slides-visual-043）
    assert any("1 本の流れを折れ線" in w for w in d.warnings), d.warnings
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [lab("a", 0, 1), lab("b", 4, 0), lab("c", 4, 2),  # 枝分かれは折る
        {"type": "arrow", "from": "a", "to": "b", "route": "bent"}, {"type": "arrow", "from": "a", "to": "c", "route": "bent"}]}]})
    assert not any("1 本の流れ" in w for w in d.warnings), d.warnings
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [lab("a", 0, 0), lab("c", 0, 2), lab("b", 4, 1),  # 合流も折る
        {"type": "arrow", "from": "a", "to": "b", "route": "bent"}, {"type": "arrow", "from": "c", "to": "b", "route": "bent"}]}]})
    assert not any("1 本の流れ" in w for w in d.warnings), d.warnings
    try:  # 枝分かれを数えるときは止めない。あとの矢印の辺の誤りは、その矢印の場所で止まる
        run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [lab("a", 0, 0), lab("b", 4, 2), lab("c", 8, 0),
            {"type": "arrow", "from": "a", "to": "b", "route": "bent"}, {"type": "arrow", "from": "a.rigth", "to": "c.left"}]}]})
        raise AssertionError("辺の誤り")
    except SystemExit as ex:
        assert "items[4]（arrow）.from" in str(ex) and "辺「rigth」はない" in str(ex), ex
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [  # 輪（楕円）の上にカードを載せる図は、一部だけ重なっても知らせない
        {"type": "text", "text": "輪", "shape": "ellipse", "fill": "PANEL", "x": 1, "y": 0.4, "w": 8, "h": 2.4}, {"type": "card", "head": "載せる", "x": 0, "y": 1, "w": 2.5, "h": 0.8}]}]})
    assert not any("重なる" in w for w in d.warnings), d.warnings
    _, els = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "label", "id": "a", "text": "A", "x": 0, "y": 0, "w": 2},
        {"type": "label", "id": "b", "text": "B", "x": 0, "y": 2, "w": 2}, {"type": "arrow", "from": "a", "to": "b", "label": "縦"}]}]})
    arr, lab = (e for e in els if e["call"] in ("arrow", "text"))
    d, bent = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "label", "id": "a", "text": "A", "x": 0, "y": 0, "w": 2},
        {"type": "label", "id": "b", "text": "B", "x": 0, "y": 2, "w": 2}, {"type": "arrow", "from": "a", "to": "b", "route": "bent", "label": "transfer"}]}]})
    assert not d.warnings and near(next(e for e in bent if e["call"] == "text")["x"], arr["x1"] + 2 * LABEL_GAP), d.warnings  # 中央のそろった折れ線も縦の線の右（PR #47 のレビュー）
    assert not next(e for e in bent if e["call"] == "arrow")["bent"]  # 中央のそろった折れ線は、まっすぐ引く（Google は幅 0 の折れ線を作れない）
    try:  # 辺の接した階段の箱の折れ線は、まっすぐにすると箱の辺の上を通るので止める（round 3 のレビュー）
        run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "label", "id": "a", "text": "A", "x": 0, "y": 0, "w": 2, "h": 0.6},
            {"type": "label", "id": "b", "text": "B", "x": 2, "y": 1.5, "w": 2, "h": 0.6}, {"type": "arrow", "from": "a", "to": "b", "route": "bent"}]}]})
        raise AssertionError("階段の bent")
    except SystemExit as ex:
        assert "0.01 in より短い区間" in str(ex), ex
    elbow = lambda *arrows: run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "label", "id": "a", "text": "A", "x": 0, "y": 2, "w": 2, "h": 0.6},
        {"type": "label", "id": "b", "text": "B", "x": 4, "y": 0, "w": 2, "h": 0.6}, {"type": "label", "id": "c", "text": "C", "x": 0, "y": 0, "w": 2, "h": 0.6}, *arrows]}]})
    A = lambda f, t, **k: {"type": "arrow", "from": f, "to": t, **k}  # 辺を書いた矢印（"<id>.<辺>"）
    d, els = elbow(A("a.right", "b.bottom", label="札"), A("b.bottom", "a.right"), A("b.left", "a.top"), A("a.top", "b.left"))
    hv, vh, hv2, vh2 = (e for e in els if e["call"] == "arrow")
    assert len(d.warnings) == 2 and all("（label）の上を通る" in w and "items[2]" in w for w in d.warnings), d.warnings  # 左上へ戻る 2 本は C の上を通る（L 字の線も見る）
    assert hv["bent"] and hv["link"][1::2] == ["right", "bottom"] and vh["link"][1::2] == ["bottom", "right"], (d.warnings, hv, vh)  # 横に出て下の辺に入る・縦に出て右の辺に入る
    assert hv2["link"][1::2] == ["left", "top"] and vh2["link"][1::2] == ["top", "left"], (hv2, vh2)  # 左に出て上の辺に入る・上に出て左の辺に入る
    assert near(hv["x1"], X + 2) and near(hv["y1"], Y_BODY_NOLEAD + 2.3) and near(hv["x2"], X + 5) and near(hv["y2"], Y_BODY_NOLEAD + 0.6)
    elab = next(e for e in els if e["loc"].endswith(".label"))
    assert near(elab["x"] + elab["w"] / 2, X + 3.5) and near(elab["y"] + elab["h"] + LABEL_GAP, hv["y1"])  # 1 回だけ折れる線の札は、出る区間（横の線）の上の中央
    d, els = elbow(A("a.top", "b.bottom", label="縦・横・縦"), A("c.right", "b.left"))  # 斜めに離れた箱を縦・横・縦に。中央のそろった向き合う辺はまっすぐ
    z, flat = (e for e in els if e["call"] == "arrow")
    zlab = next(e for e in els if e["loc"].endswith(".label"))
    assert not d.warnings and z["bent"] and z["link"][1::2] == ["top", "bottom"] and not flat["bent"] and flat["link"][1::2] == ["right", "left"], (d.warnings, z, flat)
    assert near(zlab["y"] + zlab["h"] + LABEL_GAP, Y_BODY_NOLEAD + 1.3)  # 札は真ん中の区間（横の線）の上
    d, _ = elbow({"type": "label", "id": "d", "text": "D", "x": 1.6, "y": 0.8, "w": 1, "h": 0.4},  # 出る区間が短く、上に置いた札を縦の線が通る
                 A("a.right", "d.bottom", label="とても長い札の名前"))
    assert any("折れ線の札（label）が線に重なる" in w for w in d.warnings), d.warnings
    short = {"type": "label", "id": "d", "text": "D", "x": 1.5, "y": 0.8, "w": 1.01, "h": 0.4}  # 中央が a の右の辺の 0.005 in 外
    for bad, want in [([A("a.right", "b")], "辺は両端に書く"), ([A("a.right", [3, 1])], "両端を id にする"), ([A("a.right", "b.bottom", route="bent")], "route は書かない"),
                      ([A("a.right", "b.right")], "U 字"), ([A("a.left", "b.bottom")], "出る辺 left が相手を向いていない（相手の入る点は、始めの箱の右上"),
                      ([A("a.right", "b.top")], "入る辺 top が始めの箱を向いていない（始めの出る点は、相手の箱の左下"), ([short, A("a.right", "d.bottom")], "出る辺 right"),
                      ([A("a.rihgt", "b.top")], "辺「rihgt」はない"), ([A("x.right", "b.top")], "id「x」の部品がない"),
                      ([A("a.right", "b.bottom", offset=0.1)], "まっすぐの矢印だけ")]:
        try:
            elbow(*bad)
            raise AssertionError(bad)
        except SystemExit as ex:
            assert want in str(ex), (bad, ex)
    d, _ = run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "arrow", "from": [0, 0], "to": [4, 2.5], "label": "斜めの線"}]}]})
    assert any("札（label）が線に重なる" in w for w in d.warnings), d.warnings  # 斜めの線の上の中央に置いた札は、線にかかる（fixture 04 の子が見つけた）
    assert near(lab["x"], arr["x1"] + 2 * LABEL_GAP) and near(lab["y"] + lab["h"] / 2, (arr["y1"] + arr["y2"]) / 2)  # 縦の線は右の中ほど
    pair = lambda *arrows: run({"title": "t", "body": [{"type": "frame", "h": 3, "items": [{"type": "label", "id": "a", "text": "A", "x": 0, "y": 0, "w": 2, "h": 0.8},
        {"type": "label", "id": "b", "text": "B", "x": 4, "y": 0, "w": 2, "h": 0.8}, {"type": "label", "id": "c", "text": "C", "x": 0, "y": 2, "w": 2, "h": 0.6}, *arrows]}]})
    d, els = pair({"type": "arrow", "from": "a", "to": "b", "offset": -0.2, "label": "行き"}, {"type": "arrow", "from": "b", "to": "a", "offset": 0.2, "label": "帰り", "label_side": "bottom"},
                  {"type": "arrow", "from": "a", "to": "c", "label": "左", "label_side": "left", "offset": 0.3})
    go, back, down = (e for e in els if e["call"] == "arrow")
    lg, lb, ll = (e for e in els if e["loc"].endswith(".label"))
    assert not d.warnings and "link" not in go and near(go["y1"], 0.4 - 0.2 + Y_BODY_NOLEAD) and near(back["y1"], 0.4 + 0.2 + Y_BODY_NOLEAD), d.warnings  # ずらした線は箱につながない
    assert near(go["x1"], X + 2) and near(go["x2"], X + 4) and near(down["x1"], X + 1.3)  # 辺から辺へ（つないだ線と同じく間を空けない）。縦の線は右へずらす
    assert near(lg["y"] + lg["h"] + LABEL_GAP, go["y1"]) and near(lb["y"], back["y1"] + LABEL_GAP) and near(ll["x"] + ll["w"] + 2 * LABEL_GAP, down["x1"])  # 上・下・左
    for bad, want in [({"type": "arrow", "from": "a", "to": "b", "offset": 0.5}, "箱の上下の外"), ({"type": "arrow", "from": "a", "to": "b", "route": "bent", "offset": 0.1}, "まっすぐの矢印だけ"),
                      ({"type": "arrow", "from": [0, 0], "to": "b", "offset": 0.1}, "まっすぐの矢印だけ"), ({"type": "arrow", "from": "a", "to": "b", "label": "x", "label_side": "left"}, "top か bottom"),
                      ({"type": "arrow", "from": "a", "to": "c", "label": "x", "label_side": "top"}, "left か right"), ({"type": "arrow", "from": "a", "to": "b", "label_side": "top"}, "label がない")]:
        try:
            pair(bad)
            raise AssertionError(bad)
        except SystemExit as ex:
            assert want in str(ex), (bad, ex)
    d, _ = pair({"type": "label", "id": "t", "text": "T", "x": 4, "y": 1.2, "w": 2, "h": 1.2}, {"type": "arrow", "from": "c", "to": "t", "offset": 0.1})
    assert any("斜めになる" in w for w in d.warnings), d.warnings  # 中央の高さの違う箱の間でずらしても斜めになる
    schema = spec_schema()
    assert {f"el_{k}" for k in SPEC_EL} <= set(schema["$defs"]) and json.dumps(schema, ensure_ascii=False)
    assert schema["$defs"]["el_text"]["properties"]["fill"]["enum"] == list(COLOR_NAMES)  # 色は役割の名前だけ（6 桁は書けない）
    assert all(c in globals() for c in COLOR_NAMES)
    for bad, want in [({"title": "t", "body": [{"type": "card", "titel": "x"}]}, "spec.body[0]（card）: 知らないキー titel"),
                      ({"title": "t", "body": [{"type": "text"}]}, "text がない"),
                      ({"title": "t", "body": [{"type": "text", "text": "a", "fill": "NAVYY"}]}, "spec.body[0]（text）.fill"),
                      ({"title": "t", "body": [{"type": "text", "text": "a", "fill": "FF3621"}]}, "6 桁は書けない"),  # 色は役割の名前だけ
                      ({"title": "t", "body": [{"type": "text", "text": "a", "x": 1}]}, "知らないキー x"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "text", "text": "a"}]}]}, "x・y・w を書く"),
                      ({"title": "t", "body": [{"type": "box", "h": 1, "id": "a"}, {"type": "box", "h": 1, "id": "a"}]}, "id「a」が 2 つ"),
                      ({"title": "t", "body": [{"type": "arrow", "from": "a", "to": "b"}]}, "id「a」の部品がない"),
                      ({"title": "t", "body": [{"type": "row", "items": [{"type": "arrow", "from": "a", "to": "b"}]}]}, "arrows"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a", "b"], ["c"]]}]}, "2 行目のセルが 1 列分しかない"),
                      ({"title": "t", "body": [{"type": "table", "rows": [[{"text": "a", "rowspan": 2}, "b"], ["c", "d"]]}]}, "列の数（2）を越える"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a", {"text": "b", "rowspan": 3}], ["c"]]}]}, "表の下を越える"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a", "b"], [{"text": "c", "colspan": 3}]]}]}, "列の数（2）を越える"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a"]], "header": 2}]}, "見出しの行の数（2）"),
                      ({"title": "t", "body": [{"type": "table", "rows": [[{"text": "a", "rowspan": 2}, "b"], ["c"]], "fills": [[2, 1, "PANEL"]]}]}, "結合したセルが覆う位置"),
                      ({"title": "t", "body": [{"type": "table", "rows": [[], ["a"]]}]}, "rows"),
                      ({"title": "t", "body": [{"type": "table", "rows": [[{"text": "a", "span": 2}]]}]}, "知らないキー span"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["[a](#x/y)"]]}]}, "ページへのリンクは"),
                      ({"title": "t", "body": [{"type": "image", "src": "nai.png", "h": 1}]}, "画像がない"),
                      ({"title": "t", "body": [{"type": "image", "src": "https://x/a.png"}]}, "h を書く"),
                      ({"type": "chart"}, "type「chart」はない"),
                      ({"title": "t", "source": "[a](#)"}, "[名前](#<ページのファイル名>)"),
                      ({"title": "t", "body": [{"type": "text", "text": "a", "w": "fit"}]}, "label だけ"),
                      ({"title": "t", "body": [{"type": "box", "h": 1, "raw": {"nai": 1}}]}, "box の引数にない nai"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a"]], "fills": [[3, 1, "PANEL"]]}]}, "表にない行か列"),
                      ({"title": "t", "body": [{"type": "card", "items": [["a", "**b**"]], "step": 1}]}, "step は items と使い"),
                      ({"title": "t", "body": [{"type": "box", "h": 1, "shape": "star"}]}, "shape"),
                      ({"title": "t", "body": [{"type": "grid", "cols": 0, "items": [{"type": "card", "head": "a", "text": "b"}]}]}, "1 以上の整数"),
                      ({"title": "t", "body": [{"type": "text", "text": "a", "size": 0}]}, "0 より大きい数"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "box", "x": 0, "y": 0, "w": 1, "h": -1, "fill": "PANEL"}]}]}, "0 より大きい数"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "box", "x": 0, "y": 2.5, "w": 2, "h": 1, "fill": "PANEL"}]}]}, "frame の外に出る"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "box", "x": 12, "y": 0, "w": 1, "h": 1, "fill": "PANEL"}]}]}, "ページの左上から、部品は右端 13.60 in"),  # frame の右端（12.73 in）と並べる
                      ({"type": "cover", "title": "t", "kicker": "k", "variant": 0}, "1 以上の整数"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "arrow", "from": [0, 0], "to": [1, 3]}]}]}, "は frame の外（ページの左上から、点は 1.60,"),
                      ({"title": "t", "body": [{"type": "row", "items": []}]}, "1 つ以上の部品"),
                      ({"title": "t", "body": [{"type": "table", "rows": [[]]}]}, "rows"),
                      ({"title": "t", "body": [{"type": "grid", "cols": 2, "h": 1, "items": [{"type": "card", "head": "a", "text": "b"}]}]}, "知らないキー h"),
                      ({"title": "t", "body": [{"type": "card", "fill": "NAVY", "items": [["a", "b"]], "step": 0.6}]}, "step は使えない"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a", "b", "c"]], "widths": [1, 2]}]}, "widths の数（2）が列の数（3。"),
                      ({"title": "t", "body": [{"type": "table", "rows": [["a"], ["b"]], "row_h": [0.4]}]}, "行の数（2）だけ"),
                      ({"title": "t", "body": [{"type": "row", "raw": {"gap": 0.5}, "items": [{"type": "box", "h": 1, "fill": "PANEL"}]}]}, "知らないキー raw"),
                      ({"title": "t", "body": [{"type": "text", "text": "- a\n- b\n\n詳しくは c"}]}, "別の text に分ける"),
                      ({"title": "t", "body": [{"type": "card", "head": "h", "text": "- a\nb"}]}, "別の text に分ける"),
                      ({"title": "t", "body": [{"type": "card", "head": "h", "items": [["a", ""], ["b", "c"]]}]}, "説明のない項目"),
                      ({"title": "t", "body": [{"type": "frame", "h": 1, "items": [{"type": "box", "x": 0, "y": 0, "w": 1, "h": 0.5, "fill": "PANEL"},
                                                                                   {"type": "text", "text": "a", "x": 0, "y": 0, "w": 1, "h": 0.5}]}]}, "1 つの label か"),
                      ({"title": "t", "body": [{"type": "frame", "h": 2, "items": [{"type": "box", "x": 0, "y": 0, "w": 1, "h": 1.4, "fill": "PANEL"},
                                                                                   {"type": "text", "text": "a", "x": 0, "y": 0.2, "w": 1, "h": 1}]}]}, "文字だけを重ねた")]:
        try:
            make_deck(lambda d: d.spec(bad), "spec")
            raise AssertionError(f"通した: {bad}")
        except SystemExit as e:
            assert want in str(e), (want, str(e))

    with contextlib.redirect_stderr(io.StringIO()):
        for bad, want in [({"type": "slide", "body": [{"type": "frame", "h": 1, "items": [{"type": "text", "text": "a", "x": 0, "y": 0, "w": 1, "id": "a"},
                                                                                      {"type": "label", "text": "b", "x": 3, "y": 0, "w": 1, "id": "b"},
                                                                                      {"type": "arrow", "from": "a", "to": "b", "route": "bent"}]}]}, "折れ線（bent）は"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "bars": [{"from": 1, "to": 2}]}]}]}, "from・to は 1〜1"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "**a**"}]}]}, "記法を書けない"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["**1 月**"], "rows": [{"head": "a"}]}]}, "列の名前には記法を書けない"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "marks": [{"at": 2.5, "text": "x"}]}]}]}, "at: 1〜2"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "marks": [{"at": 1, "text": "x\ny"}]}]}]}, "節目の言葉は 1 行"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "marks": [{"at": 1, "text": "**本番**"}]}]}]}, "節目の言葉には記法を書けない"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "bars": [{"from": 1, "to": 1, "fill": "RED"}]}]}]}, "fill"),
                          ({"type": "slide", "body": [{"type": "gantt", "cols": [str(i) for i in range(30)], "rows": [{"head": "a"}]}]}, "列が多くて"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1]], "hot": [2]}]}, "棒の数（1）より大きい"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1]], "horizontal": True, "line": {"values": [1]}}]}, "横の棒には書けない"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1], ["b", 2]], "line": {"values": [1]}}]}, "棒の数（2）と違う"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1]], "line": {"values": [1], "color": "RED"}}]}, "知らないキー color"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1]], "line": {"values": [1]}, "h": 1.8}]}, "折れ線の段に"),
                          ({"type": "slide", "body": [{"type": "bars", "items": [["a", 1]], "w": 1.5, "threshold": {"value": 1, "label": "目標"}}]}, "直線の札「目標 1」"),
                          ({"type": "slide", "body": [{"type": "bars", "horizontal": True, "items": [["a", 1]], "w": 2, "threshold": {"value": 1, "label": "とても長い目標の名前とその説明"}}]}, "収まらない"),
                          ({"type": "slide", "body": [{"type": "box", "fill": "PANEL", "h": 1, "raw": {"title": "ai-deck-factory bar"}}]}, "引数にない title"),
                          ({"type": "slide", "body": [{"type": "box", "fill": "PANEL", "h": 1, "raw": {"alt": "x"}}]}, "引数にない alt")]:
            try:
                run(bad)
                raise AssertionError(f"止まらない: {want}")
            except SystemExit as x:
                assert want in str(x), (want, str(x))
    # ガント: 重なるバーは下の段、本文の最後なら余った高さを行に配る（1 行に 0.4 in まで）、今日の線はバーより先に引く
    g = {"type": "gantt", "cols": ["10 月", "11 月", "12 月"], "today": 2, "rows": [{"head": "a", "bars": [{"from": 1, "to": 2, "text": "x"}, {"from": 2, "to": 3, "text": "y"}]},
                                                                                {"head": "b", "note": "補足", "bars": [{"from": 3, "to": 3, "text": "z", "status": "tbd"}]}]}
    _, els = run({"title": "t", "body": [g]})
    tb, today, bars = els[0], els[1], [e for e in els if e["call"] == "text"]
    assert tb["call"] == "table" and tb["vlines"] == (1, 3) and len(tb["widths"]) == 5 and near(sum(tb["widths"]), W) and today["call"] == "arrow" and near(today["x1"], tb["x"] + G_HEAD + tb["widths"][1])
    assert bars[1]["y"] > bars[0]["y"] and near(bars[1]["y"] - bars[0]["y"], G_BAR + G_LANE) and bars[2]["line"] == SUB and bars[2]["dash"] and bars[0]["size"] == 9
    sp = SpecPage(Path("."))
    *_, hd, hs, _ = sp.gantt_layout(g, W, "g")
    assert near(sum(tb["row_h"][1:]), sum(hs) + 2 * G_GROW) and tb["row_h"][0] == hd  # 2 行に 0.4 in ずつ
    _, els = run({"title": "t", "body": [g, {"type": "arrow", "from": [0, 0], "to": [1, 0]}]})
    assert near(sum(els[0]["row_h"][1:]), sum(hs) + 2 * G_GROW)  # 後ろが矢印だけなら伸ばす（矢印は場所を取らない）
    _, els = run({"title": "t", "body": [g, {"type": "text", "text": "下"}]})
    assert near(sum(els[0]["row_h"][1:]), sum(hs))  # 下に部品があれば伸ばさない
    # 節目: 赤の菱形の中心が at の位置。バーと重なれば下の段、表の右端では言葉を左に置く。状態の塗り
    g = {"type": "gantt", "cols": ["10 月", "11 月", "12 月"], "rows": [{"head": "a", "bars": [{"from": 1, "to": 2, "text": "x", "status": "done"}],
                                                                       "marks": [{"at": 2.5, "text": "本番"}, {"at": 3, "text": "振り返り"}, {"at": 4, "text": "終わり"}]}]}
    _, els = run({"title": "t", "body": [g]})
    tb, bar, (m1, m2, m3) = els[0], els[1], [e for e in els if e["call"] == "box"]
    x0, cw = tb["x"] + G_HEAD, tb["widths"][1]
    assert bar["fill"] == PANEL and m1["kind"] == "DIAMOND" and m1["fill"] == RED and near(m1["x"] + G_MARK / 2, x0 + 1.5 * cw)
    assert near(m1["y"], bar["y"] + G_BAR + G_LANE + (G_BAR - G_MARK) / 2) and near(m2["y"], m1["y"]) and near(m3["y"], bar["y"] + (G_BAR - G_MARK) / 2)  # バーに重なる 2 つは下の段（2 つは重ならない）、右端の 1 つは上の段
    t3 = next(e for e in els if e["loc"].endswith("marks[2].text"))
    assert t3["align"] == "END" and near(t3["x"] + t3["w"], m3["x"] - G_MARK_GAP) and t3["size"] == 11
    d, _ = run({"title": "t", "body": [{"type": "gantt", "cols": ["1 月", "2 月"], "rows": [{"head": "a", "marks": [{"at": 1, "text": "開始"}]}]}]})
    assert not d.warnings, d.warnings  # 1 列目の左端の節目は、言葉が右に収まれば警告しない
    with contextlib.redirect_stderr(io.StringIO()):
        d, _ = run({"title": "t", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "marks": [{"at": 2, "text": "あ" * 80}]}]}]})
    assert any("収まらない見込み" in w for w in d.warnings)  # 左に回しても収まらない言葉は警告する
    _, els = run({"title": "t", "body": [{"type": "gantt", "cols": ["1 月"], "rows": [{"head": "a", "bars": [{"from": 1, "to": 1, "text": "x", "status": "hot"}]}]}]})
    assert els[1]["fill"] == RED_SOFT and els[1]["color"] == RED_TEXT  # 強調は淡い赤の地に赤の文字（赤の地に白の 9pt は 4.5:1 に届かない）
    # 棒グラフ: 一番大きい数の棒が高さいっぱい。hot は赤
    _, els = run({"type": "slide", "body": [{"type": "bars", "items": [["a", 50], ["b", 100]], "unit": "件", "hot": [2]}]})
    boxes = [e for e in els if e["call"] == "box"]
    assert boxes[1]["title"] == BAR_MARK and boxes[1]["alt"] == "b 100 件"  # 棒の代替テキスト（lint が棒と見分ける）
    d, _ = run({"type": "slide", "body": [{"type": "bars", "items": [[str(i), i] for i in range(1, 13)], "line": {"values": list(range(1, 13)), "unit": "ポイント/月"}}]})
    assert any("折れ線の数字" in w for w in d.warnings)  # 折れ線の数字の折り返し
    try:
        Deck("t").box("s", 0, 0, 1, 1, fill=NAVY, title=BAR_MARK)  # 角丸（複数の図形）には付けられない
        raise AssertionError("角丸の箱に title を付けても止まらない")
    except ValueError:
        pass
    assert near(boxes[1]["h"], B_H - 2 * B_LABEL) and near(boxes[0]["h"], boxes[1]["h"] / 2) and boxes[1]["fill"] == RED and boxes[0]["fill"] == NAVY
    assert any(e["call"] == "text" and e["parts"] == [("100 件", {"bold": True, "color": RED_TEXT})] for e in els)
    # 折れ線: 棒の上の段に別の目盛りで引き（いちばん大きい数が段の上）、棒の高さは既定のまま。直線: 棒と同じ目盛りで、棒より高ければ高さいっぱい
    _, els = run({"type": "slide", "body": [{"type": "bars", "items": [["a", 50], ["b", 100], ["c", 80]], "line": {"values": [5, 10, 0], "unit": "%", "label": "率"}}]})
    segs, dots = [e for e in els if e["loc"].split(".")[-1].startswith("seg")], [e for e in els if e["call"] == "box" and e["kind"] == "ELLIPSE"]
    bar_top = min(e["y"] for e in els if e["call"] == "box" and e["kind"] == "RECTANGLE")
    assert len(segs) == 2 and len(dots) == 3 and dots[1]["y"] < dots[0]["y"] < dots[2]["y"] and dots[2]["y"] + B_DOT < bar_top - B_LABEL  # 点は棒の数字より上
    assert near(max(e["h"] for e in els if e["call"] == "box" and e["kind"] == "RECTANGLE"), B_H - 2 * B_LABEL)
    assert any(e["call"] == "text" and e["parts"] == [("10 %", {"bold": True, "color": SUB})] for e in els) and any(e["loc"].endswith("line.label") for e in els)
    _, els = run({"type": "slide", "body": [{"type": "bars", "items": [["a", 50], ["b", 100]], "unit": "件", "threshold": {"value": 200, "label": "目標"}}]})
    boxes, th = [e for e in els if e["call"] == "box"], next(e for e in els if e["loc"].endswith("threshold"))
    assert near(boxes[1]["h"], (B_H - 2 * B_LABEL) / 2) and th["dash"] and th["color"] == RED and near(th["y1"], boxes[1]["y"] - boxes[1]["h"])
    assert any(e["call"] == "text" and e["parts"] == [("目標 200 件", {"color": RED_TEXT})] and e["x"] > th["x2"] for e in els)  # 札は線の右
    # 折れ線と直線を一緒に書くと、直線は棒の段に、札は棒の右の外に置き、折れ線の段は棒の幅だけ使う
    d, els = run({"type": "slide", "body": [{"type": "bars", "items": [["a", 50], ["b", 100]], "line": {"values": [1, 2], "label": "率"}, "threshold": {"value": 80}}]})
    th, tl = (next(e for e in els if e["loc"].endswith(k)) for k in ("threshold", "threshold.label"))
    dots = [e for e in els if e["call"] == "box" and e["kind"] == "ELLIPSE"]
    assert not d.warnings and th["y1"] > max(e["y"] + B_DOT for e in dots) + B_LABEL and all(e["x"] + B_DOT < tl["x"] for e in dots)
    _, els = run({"type": "slide", "body": [{"type": "bars", "items": [["a", 95], ["b", 3]], "threshold": {"value": 100}}]})
    assert next(e for e in els if e["loc"].endswith("items[0].value"))["parts"][0][1]["color"] == WHITE  # 直線が通る数字は棒の中に白で
    assert any("棒が低いか細くて" in w for w in run({"type": "slide", "body": [{"type": "bars", "items": [["a", 100], ["b", 2]], "threshold": {"value": 3}}]})[0].warnings)
    d, els = run({"type": "slide", "body": [{"type": "bars", "w": 3.2, "items": [["Q1", 99999], ["Q2", 100000], ["Q3", 99999], ["Q4", 99999]], "threshold": {"value": 100000}}]})
    assert any("棒が低いか細くて" in w for w in d.warnings) and not any(e["loc"].endswith(".value") and e["parts"][0][1]["color"] == WHITE for e in els)  # 数字が棒の幅に入らなければ白にしない
    _, els = run({"type": "slide", "body": [{"type": "bars", "horizontal": True, "items": [["a", 78], ["b", 100]], "threshold": {"value": 80}}]})
    v = next(e for e in els if e["loc"].endswith("items[0].value"))
    assert v["parts"][0][1]["color"] == WHITE and v["x"] + v["w"] < next(e for e in els if e["loc"].endswith("threshold"))["x1"]  # 棒の中に白で
    th, base, tl = (next(e for e in els if e["loc"].endswith(k)) for k in ("threshold", "base", "threshold.label"))
    assert near(th["x1"], th["x2"]) and th["x1"] > base["x1"] and near(th["y1"], base["y1"]) and near(tl["y"] + B_LABEL, base["y1"])  # 縦の線、上に札の行
    brief = spec_brief()
    assert "bars の line:" in brief and "bars の threshold:" in brief
    assert all(re.search(rf"^{k}: ", brief, re.M) for k in [*SPEC_EL, *SPEC_PAGE]) and "gantt の bars:" in brief  # 早見表に、すべての型
    # 四角でない図形はつながない（接続点の番号が違う）。つながない斜めの矢印は、折れ線を勧めない
    d, els = run({"type": "slide", "body": [{"type": "frame", "h": 2, "items": [{"type": "box", "id": "o", "shape": "ellipse", "fill": "PANEL", "x": 0, "y": 0, "w": 1, "h": 1},
                                                                             {"type": "label", "id": "n", "text": "x", "x": 3, "y": 1, "w": 1},
                                                                             {"type": "arrow", "from": "o", "to": "n"}]}]})
    assert "link" not in next(e for e in els if e["call"] == "arrow") and not d.warnings
    _, els = run({"type": "slide", "body": [{"type": "frame", "h": 2, "items": [{"type": "text", "id": "l", "text": "左寄せ", "fill": "PANEL", "x": 0, "y": 0, "w": 2},
                                                                             {"type": "text", "id": "c", "text": "中央", "fill": "PANEL", "align": "center", "x": 4, "y": 0, "w": 2},
                                                                             {"type": "stat", "id": "s", "value": "3", "x": 8, "y": 0, "w": 2},
                                                                             {"type": "arrow", "from": "l", "to": "c"}, {"type": "arrow", "from": "c", "to": "s"}]}]})
    assert not any("link" in e for e in els if e["call"] == "arrow")  # 文字の枠が箱の内に縮む部品（左寄せの塗りの文字・stat）はつながない
    _, els = run({"type": "slide", "body": [{"type": "frame", "h": 1, "items": [{"type": "num", "id": "a", "n": 1, "x": 0, "y": 0}, {"type": "num", "id": "b", "n": 10, "x": 2, "y": 0},
                                                                             {"type": "label", "id": "c", "text": "x", "x": 4, "y": 0, "w": 1, "h": 0.36},
                                                                             {"type": "arrow", "from": "a", "to": "c"}, {"type": "arrow", "from": "b", "to": "c"}]}]})
    assert not any("link" in e for e in els if e["call"] == "arrow")  # 番号は字数によらず枠が円より広いのでつながない
    with contextlib.redirect_stderr(io.StringIO()):
        d, els = run({"type": "slide", "body": [{"type": "gantt", "cols": [f"{i} 月" for i in range(1, 13)], "rows": [{"head": "a", "bars": [{"from": 1, "to": 1, "text": "ユーザーの受け入れの試験と確かめ"}]}]},
                                                {"type": "bars", "items": [["a", 100.0]] + [[str(i), 12345678] for i in range(15)], "unit": "件"}]})
    assert any("3 行以上に折り返す" in w for w in d.warnings) and any("12,345,678 件" in w for w in d.warnings)  # バーの文字と、棒の数字の折り返し
    assert any(e["call"] == "text" and e["parts"][0][0] == "100 件" for e in els)
    try:
        run({"type": "slide", "body": [{"type": "bars", "horizontal": True, "h": 2, "items": [[str(i), 1] for i in range(12)]}]})
        raise AssertionError("横の棒の行が狭くても止まらない")
    except SystemExit as x:
        assert "1 本の行が" in str(x)
    d, _ = run({"type": "slide", "body": [{"type": "bars", "horizontal": True, "items": [["a", 1], ["とても長い名前" * 6, 2]]}]})
    assert any("名前の列" in w for w in d.warnings)  # 横の棒の名前の折り返し
    assert "stat: value*（文字） unit（文字。単位（数字の半分の大きさ））" in brief  # 同じ名前のキーは、型ごとの説明


def selftest_diff():
    """手元の JSON（local_json）と、変わったページだけを組む build（pages_of）。Google は呼ばない（request・batch などを差し替える）。"""
    global COPYRIGHT
    old_c, COPYRIGHT = COPYRIGHT, "© 2026 T. All rights reserved."  # need_brand を通す（どのデッキもこれで作る）
    p = {"title": "t", "masters": [{"objectId": "M", "pageProperties": {"colorScheme": {"colors": []}}}],
         "layouts": [{"objectId": "L", "layoutProperties": {"displayName": BLANK, "masterObjectId": "M"}, "pageElements": [{"objectId": "Ln", "shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}]}]}

    def make(lead):
        def m(d):
            d.cover("表紙", "k")
            s = d.page("見出し", lead)
            d.text(s, X, Y_BODY, W, 1, ["本文𝄞の", ("太字", {"bold": True}), "\n2 段落目"], bullets=True)
            d.label(s, "札", X, 3, 2, 0.4)  # 角丸の箱と文字の枠のグループ
            d.table(s, X, 4, [2, 2], [[{"text": "見出し", "colspan": 2}], ["行", "値"]])
            d.note(s, "ノート。")
            d.text(d.page("付録"), X, Y_BODY, W, 1, ["出典: ", ("前のページ", {"link": 2})])
        return m

    d = make_deck(make("リード"), "t")
    q = local_json(json.loads(resolved(d, p)), d, p)
    s2 = q["slides"][1]
    assert [s["slideProperties"]["layoutObjectId"] for s in q["slides"]] == ["L"] * 3 and s2["slideProperties"]["masterObjectId"] == "M"
    body = next(e for e in s2["pageElements"] if "本文" in json.dumps(e.get("shape", {}).get("text", {}), ensure_ascii=False))
    te = body["shape"]["text"]["textElements"]
    assert [x["textRun"]["content"] for x in te if "textRun" in x] == ["本文𝄞の", "太字", "\n", "2 段落目\n"] and all("bullet" in x["paragraphMarker"] for x in te if "paragraphMarker" in x)
    assert next(x["textRun"]["style"] for x in te if x.get("textRun", {}).get("content") == "太字")["bold"] is True
    table = next(e for e in s2["pageElements"] if "table" in e)
    assert table["size"]["width"]["magnitude"] == 3000000 and table["table"]["tableRows"][1]["tableCells"][1]["text"]["textElements"][1]["textRun"]["content"] == "値\n"
    assert table["table"]["tableRows"][0]["tableCells"][0]["columnSpan"] == 2  # 結合したセルは左上のセルが持つ
    assert any("elementGroup" in e for e in s2["pageElements"]) and s2["slideProperties"]["notesPage"]["pageElements"][0]["shape"]["text"]["textElements"][1]["textRun"]["content"] == "ノート。\n"
    assert not any(e["objectId"] == s2["objectId"] + "_n" for e in s2["pageElements"])  # ページ番号の枠は Google が作るので、手元にはない
    import lint
    with contextlib.redirect_stdout(io.StringIO()):
        lint.lint_slides(q, r := lint.Report(), only={3})
    assert r.hits[lint.EMPTY_BELOW] and all(h.startswith("p3") for h in r.hits[lint.EMPTY_BELOW])  # 選んだページの指摘だけ（全体では p1 にも出る）
    with contextlib.redirect_stdout(io.StringIO()):
        lint.lint_slides(dict(q, slides=q["slides"][1:]), r := lint.Report(), only={2})  # 表紙を外したデッキの 2 枚目だけを見ても
    assert r.hits[lint.NO_COVER]  # 「1 枚目が表紙でない」（デッキ全体の規則）は絞らない

    # ページのハッシュ: 組むたびに変わる ID では変わらず、中身が変わったページと、そこへリンクするページだけが変わる
    _, h1, links, n1 = pages_of(d, json.loads(resolved(d, p)))
    e = make_deck(make("リード"), "t")
    assert e.run != d.run  # 続けて作っても、ID の頭は別
    for bad_arg in ([], ["3,x"], ["3,"]):
        try:
            page_numbers(["--pages", *bad_arg])
            raise AssertionError(f"--pages {bad_arg!r} を通した")
        except SystemExit:
            pass
    assert page_numbers(["lint", "--pages", "3,5", "--talk"]) == {3, 5}
    assert clean_after({"A", "B", "Z"}, ["A", "B", "A", "C"], {3, 4}, {3}) == {"B", "C"}  # 通っていた A も、今回要修正なら外す。消えたページ（Z）は落とす
    assert clean_after(set(), ["A", "A"], {1, 2}, {None, 2}) == set()  # 同じ中身の 2 枚のうち 1 枚が要修正（デッキ全体の要修正の None は数えない）
    _, h2, _, _ = pages_of(e, json.loads(resolved(e, p)))
    f = make_deck(make("別のリード"), "t")
    _, h3, _, _ = pages_of(f, json.loads(resolved(f, p)))
    assert list(h1.values()) == list(h2.values()) and links[d.slides[2]] == {d.slides[1]}
    assert [a == b for a, b in zip(h1.values(), h3.values())] == [True, False, False]
    d.notes[d.slides[1]] = "別のノート。"
    _, h4, _, n4 = pages_of(d, json.loads(resolved(d, p)))
    assert h4 == h1 and [a == b for a, b in zip(n1.values(), n4.values())] == [True, False, False]  # ノートはハッシュに入れない（ノートも入れたほうは、リンク元まで変わる）
    d.notes[d.slides[1]] = "ノート。"

    def swap(a, b):  # 1 枚目から 2 枚目・3 枚目へのリンク（a, b の順に置く）と、手元の画像
        def m(d):
            s = d.page("S")
            d.text(s, X, Y_BODY, W, 1, [("先 1", {"link": a}), "、", ("先 2", {"link": b})])
            d.image(s, img, X, 3, 1, 1)
            d.page("二")
            d.page("三")
        return m
    with tempfile.TemporaryDirectory() as t:
        img = os.path.join(t, "x.png")
        Path(img).write_bytes(b"1")
        hs = [pages_of(e, json.loads(resolved(e, p)))[1][e.slides[0]] for e in (make_deck(swap(2, 3), "t"), make_deck(swap(3, 2), "t"))]
        assert hs[0] != hs[1]  # 1 ページの中でリンク先を入れ替えたら変わる
        st = os.stat(img)
        Path(img).write_bytes(b"2")
        os.utime(img, ns=(st.st_atime_ns, st.st_mtime_ns))  # 同じパス・同じ更新時刻のまま中身を替える
        e = make_deck(swap(2, 3), "t")
        assert pages_of(e, json.loads(resolved(e, p)))[1][e.slides[0]] != hs[0]

    # build: 前に組んだページと同じハッシュのページは残し、変わったページだけを作って、古いページを消し、順をそろえる
    sent, live, notes, real = [], [], {}, {k: globals()[k] for k in ("request", "batch", "revision")}
    old_g, old_s = gapi.guard, gapi.stamp

    def fake_batch(pid, reqs):  # デッキのページの並びだけを手元で動かす
        sent.append(reqs)
        for r in reqs:
            (k, v), = r.items()
            if k == "createSlide":
                live.append(v["objectId"])
            elif k == "deleteObject" and v["objectId"] in live:
                live.remove(v["objectId"])
            elif k in ("insertText", "deleteText"):  # ノートの枠（<ページ>_sp）
                notes[v["objectId"]] = v.get("text", "")
            elif k == "updateSlidesPosition":
                live.remove(v["slideObjectIds"][0])
                live.insert(v["insertionIndex"], v["slideObjectIds"][0])

    revs = {"": {"revisions": [{"id": "1"}, {"id": "4"}], "nextPageToken": "t+1"}, "t%2B1": {"revisions": [{"id": "8"}], "nextPageToken": "t2"}, "t2": {}}
    globals()["request"] = lambda m, u, *a, **k: revs[u.partition("pageToken=")[2]]
    assert revision("x") == "8"  # 版の一覧は古い順。最後のページの最後の ID（空のページが続いても前の ID）
    globals().update(request=lambda m, u, *a, **k: {**p, "slides": [{"objectId": o, "slideProperties": {"notesPage": {"notesProperties": {"speakerNotesObjectId": o + "_sp"}, "pageElements": [
        {"objectId": o + "_sp", "shape": {"text": {"textElements": [{"paragraphMarker": {}}, {"textRun": {"content": notes.get(o + "_sp", "") + "\n"}}]}}}]}}} for o in live]},
                     batch=fake_batch, revision=lambda pid: "rev")
    gapi.guard = gapi.stamp = lambda *a: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            build("x" * 10, d)
            made = list(live)
            assert len(made) == 3 and all(PAGE_HASH.search(o) for o in made)  # 初めては全部
            sent.clear()
            build("x" * 10, f)  # 2 枚目のリードだけ変えた
            new = [r["createSlide"]["objectId"] for r in sent[0] if "createSlide" in r]
            assert len(new) == 2 and live == [made[0], *new]  # 2 枚目と、そこへリンクする 3 枚目を作り直し、古い 2 枚を消す
            assert next(r["updateTextStyle"]["style"]["link"] for r in sent[0] if "link" in r.get("updateTextStyle", {}).get("style", {})) == {"pageObjectId": new[0]}
            assert not any(made[0] in json.dumps(r) for r in sent[0])  # 1 枚目には触らない
            assert json.load(open(f"/tmp/slides_{('x' * 10)[:8]}/changed.json"))["pages"] == [{"page": 2, "objectId": new[0]}, {"page": 3, "objectId": new[1]}]
            sent.clear()
            build("x" * 10, make_deck(make("別のリード"), "t"))  # 変えていない
            assert not any(sent) and len(live) == 3, sent  # ノートも書かない
            nd = make_deck(make("別のリード"), "t")
            nd.notes[nd.slides[1]] = "台本。[short pause]"
            with contextlib.redirect_stdout(o := io.StringIO()):
                build("x" * 10, nd)  # ノートだけ変えた
            assert json.loads(o.getvalue().splitlines()[-1])["notes_rewritten"] == [2], o.getvalue()  # 残したページのノートを書き換えたら出す（pages.py の d.note で、push した台本を書き戻したときに気づく）
            assert [list(r) for r in sent[-1]] == [["deleteText"], ["insertText"], ["updateTextStyle"]] and notes[live[1] + "_sp"] == "台本。[short pause]"
            assert not any("createSlide" in r for rs in sent for r in rs) and len(live) == 3  # ページは作り直さない
            sent.clear()

            def to_legacy(dk):  # live を、2026-10-23 より前の build の ID（ノートも入れたハッシュ）にする
                *_, legacy = pages_of(dk, json.loads(resolved(dk, p)))
                for i, sd in enumerate(dk.slides):
                    notes[PAGE_HASH.sub("h" + legacy[sd], live[i]) + "_sp"] = notes.get(live[i] + "_sp", "")
                    live[i] = PAGE_HASH.sub("h" + legacy[sd], live[i])
            to_legacy(nd)
            build("x" * 10, nd)
            assert not any(sent), sent  # 前の ID のページも残す
            g = make_deck(lambda d: [make("別のリード")(d), d.slides.insert(0, d.slides.pop(1))], "t")  # 2 枚目を先頭に（1 枚目の扱いとリンク先が変わる）
            build("x" * 10, g)
            _, hg, _, _ = pages_of(g, json.loads(resolved(g, p)))
            assert [PAGE_HASH.search(o).group(1) for o in live] == [hg[s] for s in g.slides]  # デッキの順が pages.py の順
            sent.clear()
            build("x" * 10, f, force=True)
            assert sum("createSlide" in r for r in sent[0]) == 3 and len(live) == 3  # --force は全部

            def twin(n, to):  # 1 枚目から、中身の同じ n 枚のうち to 枚目へリンクする
                def m(d):
                    d.text(d.page("S"), X, Y_BODY, W, 1, ["出典: ", ("先", {"link": to})])
                    for _ in range(n):
                        d.page("同じ")
                return m
            build("x" * 10, make_deck(twin(2, 3), "t"), force=True)
            first = live[0]
            sent.clear()
            build("x" * 10, make_deck(twin(1, 2), "t"))  # 3 枚目を消し、2 枚目へリンクし直す（S のハッシュは変わらない）
            link = next(r["updateTextStyle"]["style"]["link"] for rs in sent for r in rs if "link" in r.get("updateTextStyle", {}).get("style", {}))
            assert live[0] != first and link == {"pageObjectId": live[1]} and len(live) == 2, (first, live, link)  # S を作り直し、残ったページを指す
            build("x" * 10, td := make_deck(twin(2, 3), "t"), force=True)
            to_legacy(td)
            first = live[0]
            build("x" * 10, make_deck(twin(1, 2), "t"))  # 前の build の ID の、中身の同じ 2 枚でも
            assert live[0] != first and len(live) == 2, (first, live)
            # ファイルを選んで組む: 選んだページだけを作り直し、選んでいないページは中身が変わっていても前のスライドを残す（ID のファイル名の印で探す）
            with tempfile.TemporaryDirectory() as t:
                page = lambda n, title: Path(t, f"{n}.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": title, "speakerNotes": "ノート。"}))
                Path(t, "deck.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "deck", "name": "選ぶ", "pages": ["p1.json", "p2.json", "p3.json"]}))
                for n in ("p1", "p2", "p3"):
                    page(n, f"{n} の前")
                spec = lambda: make_deck(lambda d: d.spec(Path(t, "deck.json")), "選ぶ")
                build("x" * 10, spec(), force=True)
                before = list(live)
                assert [PAGE_KEY.search(o).group(1) for o in before] == [page_key(n) for n in ("p1", "p2", "p3")]
                page("p2", "p2 の後")
                page("p3", "p3 の後")
                cur = os.getcwd()
                os.chdir(t)
                try:
                    dk = spec()
                    with contextlib.redirect_stdout(out := io.StringIO()):
                        gapi.guard = lambda *a, **k: ["前に組んだあとに画面で直されている"]
                        cmd_plan("x" * 10, dk, None, chosen(["p2.json"], dk, None))
                        gapi.guard = lambda *a, **k: None
                    got = json.loads(out.getvalue())
                    assert got["rebuild"] == [2] and got["frozen"] == [3] and got["kept"] == 1 and got["screen"] == ["前に組んだあとに画面で直されている"], got
                    Path(t, "p1.json").write_text(json.dumps({**json.loads(Path(t, "p1.json").read_text()), "speakerNotes": "選んでいない。"}))
                    dk = spec()
                    build("x" * 10, dk, only=chosen(["p2.json"], dk, None))
                    assert live[0] == before[0] and live[2] == before[2] and live[1] != before[1] and PAGE_KEY.search(live[1]).group(1) == page_key("p2")
                    assert notes[live[0] + "_sp"] == "ノート。"  # 選んでいないページは、ノートも前のまま
                    page("p1", "p1 の前")
                    for bad, want in ((["nope.json"], "読めない"), ([str(Path(t, "deck.json"))], None)):
                        try:
                            assert chosen(bad, dk, None) == {"p1", "p2", "p3"} and want is None  # デッキのファイルは、その全ページ
                        except SystemExit as e:
                            assert want and want in str(e), str(e)
                    # 選んでいないページは、中身の同じページへのリンクを持っていても前のまま（twins の作り直しは、作り直すページにだけ当てる）
                    Path(t, "p1.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "p1 の前", "speakerNotes": "ノート。",
                                                             "body": [{"type": "text", "text": "[p2 へ](#p2)"}]}))
                    page("p2", "同じ")
                    page("p3", "同じ")
                    build("x" * 10, spec(), force=True)
                    before = list(live)
                    dk = spec()
                    build("x" * 10, dk, only=chosen(["p3.json"], dk, None))
                    assert live == before, (live, before)  # 変えていない p1
                    Path(t, "p1.json").write_text(json.dumps({**json.loads(Path(t, "p1.json").read_text()), "title": "p1 の後"}))
                    dk = spec()
                    build("x" * 10, dk, only=chosen(["p3.json"], dk, None))
                    assert live == before, (live, before)  # 変えた p1 も
                    # 前のまま残すページは、前の中身のリンク（デッキから読む）で見る: 前の p1 は p3 へリンクしていて、p3 を作り直すと p1 も作り直す
                    page("p3", "p3 だけ")
                    build("x" * 10, spec(), force=True)
                    before = list(live)
                    Path(t, "p1.json").write_text(json.dumps({**json.loads(Path(t, "p1.json").read_text()), "title": "p1 をまた直した"}))
                    page("p3", "p3 を直した")
                    req0 = globals()["request"]
                    globals()["request"] = lambda m, u, *a, **k: ({"slides": [{"objectId": before[0], "pageElements": [{"shape": {"text": {"textElements": [
                        {"textRun": {"style": {"link": {"pageObjectId": before[2]}}}}]}}}]}]} if "slides(objectId,pageElements)" in u else req0(m, u, *a, **k))
                    try:
                        dk = spec()
                        build("x" * 10, dk, only=chosen(["p3.json"], dk, None))
                    finally:
                        globals()["request"] = req0
                    assert live[0] != before[0] and live[1] == before[1] and live[2] != before[2], (live, before)
                    # 同じ中身のページがあっても、選んでいないページは前のスライドのまま（ハッシュで先に取られない）
                    page("p1", "p1 だけの")
                    page("p2", "同じ")
                    page("p3", "同じ")
                    build("x" * 10, spec(), force=True)
                    before = list(live)
                    page("p2", "p2 を直している")
                    dk = spec()
                    with contextlib.redirect_stdout(out := io.StringIO()):
                        cmd_plan("x" * 10, dk, None, chosen(["p1.json"], dk, None))
                    assert json.loads(out.getvalue())["frozen"] == [2], out.getvalue()
                    build("x" * 10, dk, only=chosen(["p1.json"], dk, None))
                    assert live == before, (live, before)
                    # ノートだけ違う同じ見た目のページへのリンク: 組み直すたびにリンク元を作り直さない。リンク先を替えたら作り直す
                    linker = lambda to: Path(t, "p1.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "p1", "speakerNotes": "ノート。",
                                                                                   "body": [{"type": "text", "text": f"[先へ](#{to})"}]}))
                    linker("p2")
                    for n, note in (("p2", "2 枚目のノート。"), ("p3", "3 枚目のノート。")):
                        Path(t, f"{n}.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "同じ", "speakerNotes": note}))
                    build("x" * 10, spec(), force=True)
                    before = list(live)
                    sent.clear()
                    build("x" * 10, spec())
                    assert live == before and not any("createSlide" in r for rs in sent for r in rs), (live, before)
                    linker("p3")
                    build("x" * 10, spec())
                    assert live[0] != before[0] and live[1:] == before[1:], (live, before)
                    for n in ("p2", "p3"):  # 前の build の ID では、リンクのハッシュに印がない: 同じ中身の 2 枚のあいだでリンク先を替えたら作り直す
                        Path(t, f"{n}.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "page", "title": "同じ", "speakerNotes": "同じノート。"}))
                    build("x" * 10, spec(), force=True)
                    to_legacy(spec())
                    before = list(live)
                    linker("p2")
                    build("x" * 10, spec())
                    assert live[0] != before[0] and live[1:] == before[1:], (live, before)
                    # deck.json の theme のファイルがあれば、URL を渡しても Google を読まない
                    Path(t, "d2.json").write_text(json.dumps({"apiVersion": API_VERSION, "kind": "deck", "name": "d", "theme": "visual", "pages": ["p1.json"]}))
                    req0, c0 = globals()["request"], COPYRIGHT
                    globals()["request"] = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Google を読んだ"))
                    try:
                        assert deck_context("d2.json", "https://docs.google.com/presentation/d/abc/edit")[0] == "visual"
                    finally:
                        globals()["request"], COPYRIGHT = req0, c0  # deck_context はテーマの著作権表示で組むようにする（ここの仮の値に戻す）
                        use_pages(p)
                    # テーマのファイルは、デッキのテーマのファイルそのものだけを受け付ける（名前が同じ別のファイルで、違う値を当てたと思わせない）
                    Path(t, "visual.json").write_text((BUILTIN_THEMES / "visual.json").read_text())
                    assert chosen([str(theme_path("visual"))], dk, "visual") == set()
                    try:
                        chosen([str(Path(t, "visual.json"))], dk, "visual")
                        raise AssertionError("別の場所のテーマのファイルを通した")
                    except SystemExit as e:
                        assert "デッキのテーマのファイルは" in str(e)
                    # テーマを書いたあとでページを組めずに止まっても、次の build が自分の書き込みを画面での直しと取り違えない（書いたすぐあとに版を残す）
                    stamps, fb = [], globals()["batch"]
                    gapi.stamp = lambda *a: stamps.append(a)

                    def fail_pages(pid, reqs):
                        if not any("updatePageProperties" in r and r["updatePageProperties"]["objectId"] == "M" for r in reqs):
                            raise gapi.ApiError("500 batchUpdate")
                        fb(pid, reqs)
                    globals()["batch"] = fail_pages
                    vis = read_theme(BUILTIN_THEMES / "visual.json")
                    os.makedirs(f"/tmp/slides_{('x' * 10)[:8]}", exist_ok=True)
                    Path(f"/tmp/slides_{('x' * 10)[:8]}/shots.json").write_text("[]")  # 前に取った画像の記録
                    try:
                        build("x" * 10, spec(), force=False, theme=("visual", {**vis, "NAVY": "000000"}))
                        raise AssertionError("ページの batch の失敗を通した")
                    except gapi.ApiError:
                        pass
                    finally:
                        globals()["batch"], gapi.stamp = fb, lambda *a: None
                    assert len(stamps) == 1 and not Path(f"/tmp/slides_{('x' * 10)[:8]}/shots.json").exists()  # マスターを書いたら、次の check は全ページを取る
                    try:
                        chosen(["p2.json"], make_deck(lambda d: d.page("pages.py の"), "t"), None)
                        raise AssertionError("pages.py のデッキでページを選べた")
                    except SystemExit as e:
                        assert "JSON のページのデッキだけ" in str(e)
                finally:
                    os.chdir(cur)
    finally:
        globals().update(real)
        gapi.guard, gapi.stamp, COPYRIGHT = old_g, old_s, old_c
        shutil.rmtree(f"/tmp/slides_{('x' * 10)[:8]}", ignore_errors=True)


PAGE_FILES = (".py", ".json")  # lint・dry に渡せるページのファイル（pages.py の形か、JSON のページ）


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        return selftest()
    if a == ["themes"]:
        return cmd_themes()
    if a[:1] == ["theme"] and 2 <= len([x for x in a if x != "--force"]) <= 3:
        rest = [x for x in a[1:] if x != "--force"]
        return cmd_theme(rest[0], rest[1] if len(rest) > 1 else None, "--force" in a)
    if a[:1] == ["merge"] and len(a) >= 2:
        return print(json.dumps(merge("pages.py", a[1:]), ensure_ascii=False))
    if a == ["stats"]:
        return spec_stats()
    if a[:1] == ["upgrade"] and len(a) >= 2:
        return spec_upgrade(a[1:])
    if a == ["schema"]:
        return print(json.dumps(spec_schema(), ensure_ascii=False, indent=1))
    if a == ["schema", "--brief"]:
        return print(spec_brief())
    if a[:1] in (["dry"], ["resolve"]) and len(a) <= 3:
        return dry(next((x for x in a[1:] if x.endswith(PAGE_FILES)), None) or default_pages(), next((x for x in a[1:] if not x.endswith(PAGE_FILES)), None), a[0] == "resolve")
    if a[:1] == ["lint"]:
        if bad := [x for x in a[1:] if x.startswith("--") and x not in ("--pages", "--all", "--talk")]:
            sys.exit(f"slides.py lint が知らないフラグ: {' '.join(bad)}（--pages 3,5・--all・--talk）")
        if "--pages" in a and "--all" in a:
            sys.exit("slides.py lint の --pages と --all は、どちらか 1 つだけ渡す")
        pick = page_numbers(a) if "--pages" in a else "all" if "--all" in a else None
        rest = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] != "--pages"]
        return lint_local(next((x for x in rest if x.endswith(PAGE_FILES)), None) or default_pages(), next((x for x in rest if not x.endswith(PAGE_FILES)), None), "--talk" in a, pick)
    if not (a[:1] in (["build"], ["plan"]) and len(a) >= 2 or a[:1] == ["new"] and len(a) >= 3):
        sys.exit(__doc__)
    files = [x for x in a[2:] if x.endswith(".json")] if a[0] != "new" else []  # 選んだページ（build_plan の only）
    if a[0] == "new" and ("--theme" in a[1:3] or "--theme" in a and a.index("--theme") + 1 >= len(a)):  # 名前の書き忘れ・値のない --theme
        sys.exit(__doc__)
    rest = [x for i, x in enumerate(a[3:], 3) if not (x == "--theme" or a[i - 1] == "--theme")] if a[0] == "new" else [x for x in a[2:] if x not in files]
    if bad := [x for x in rest if x != "--force" or a[0] != "build"]:  # 打ち間違えたファイルやフラグを黙って捨てると、選んだつもりで全ページを組み直す
        sys.exit(f"slides.py {a[0]} が知らない引数: {' '.join(bad)}（{'<フォルダ> <名前> [--theme <テーマ>]' if a[0] == 'new' else '<URL> [<ページ>.json …]' + (' [--force]' if a[0] == 'build' else '')}）")
    path = default_pages()
    want = declared_theme(path)
    theme = a[a.index("--theme") + 1] if "--theme" in a else want
    if a[0] == "new":
        need_theme(theme)
    src = template_id(theme or default_theme()) if a[0] == "new" else file_id(a[1])
    p = request("GET", f"{SLIDES}/{src}?fields={DECK_FIELDS}")  # テーマの名前はデッキ（new ならテンプレート）の目印。複製は同じ代替テキストを持つ
    mark = deck_theme(p)
    if a[0] == "new":
        need_mark(theme or default_theme(), mark)
    need_deck_theme(want, mark)
    t = load_theme(mark)
    own = (mark, t) if t is not None else None  # 組む前にマスターをテーマのファイルの値にそろえる（テンプレートを作ったあとで直していても）
    if t is None:  # テーマのファイルがない（ほかの人のテーマのデッキ）なら、デッキが持つ値で組む
        t = theme_from(p)
        use_pages(p)
    else:
        use_pages(theme_pages(mark, t))
    use_theme(t)
    gapi.CLOCK.lap("テーマを読む")
    need_brand()  # 複製する前に止める（build でも止まるが、作った複製をゴミ箱に移すことになる）
    m = load_make(path)
    deck = make_deck(m.make, m.NAME)
    gapi.CLOCK.lap("要求を作る")
    only = chosen(files, deck, mark) if files else None
    if a[0] == "plan":
        return cmd_plan(src, deck, own, only)
    if a[0] == "build":
        out = build(src, deck, "--force" in a, own, only)
        if only is None:  # ページを選んだときは、前のまま残したページの形の外の書き方が数えられないので残さない（次に全体を組んだときに残す）
            spec_record(deck, src)
        return out
    pid = new(a[1], a[2], src)
    try:
        build(pid, deck, force=True, theme=own)  # 複製したばかりなので、画面での直しもコメントもない
    except BaseException:  # 組めなかった複製を残さない。直してから new をやり直す（同じ名前の空のプレゼンが増えないように）
        trash(pid)
        print(f"組めなかったので、作った複製 {pid} をゴミ箱に移した", file=sys.stderr)
        raise
    spec_record(deck, pid)


if __name__ == "__main__":
    run(main)
