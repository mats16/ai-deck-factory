#!/usr/bin/env python3
"""usage: lint.py <deck.json> [--talk]   Google Slides（Slides API の presentations.get の JSON。gslides.py check が書き出して呼ぶ）
       lint.py <doc.json>              Google Docs（Docs API の documents.get の JSON。docs.py check が書き出して呼ぶ）
       python3 lint.py --selftest で自己確認、--stats で要確認の残り方（規則ごと）
--talk は LT など話す資料（聞き手が初めて聞く中身を短く話すもの）。1 枚の本文の字数も見る。
書いたルールのうち、機械で見られるものを数える。標準ライブラリだけで動く。
要修正（HARD）が 1 つでもあれば exit 1。要確認（WARN）は 1 件ずつ見て、直すか、残す理由を言えるようにする。
ルールの出典は ../../deck-practices/ と、ワークスペースの Research/deck_research/log/。pptx を読んでいた版は Archive/pptx_pipeline_20261007/、docx を読んでいた部分は Archive/docx_pipeline_20261010/。"""
import hashlib, itertools, json, math, os, re, subprocess, sys, time
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slides import BAR_MARK, BAND_BOTTOM, COPYRIGHT_PT, EMU, FONT, INSET, LAYOUT_MARK, MONO_DEFAULT, STAGE_FILL, Y_BODY, Y_BODY_NOLEAD, Y_FOOT, Y_LEAD, deck_card, deck_font, deck_mono, em_width, use_font  # 版面・書体・字幅の見積もりは、組む側（slides.py）と同じものを使う

DOC_MIN_PT = 9  # ドキュメントの文字の下限。図表の題・出典・表の中・フッターが 9pt（visual_doc.md の 1）
MIN_PT = 11  # [lint-001] スライドの文字の下限。社内資料の差し替え用（名前に「差し替え用」）は元の大きさのままなので見ない
FIG_MIN_PT = MIN_PT - 2  # [lint-022] 塗りのある図形の中の文字（ガントのバー、図のラベル）は本文から 2pt 下まで（visual-037）。表のセル、塗りのない文字、別の図形の塗りに重ねた文字（カードの本文、背景の四角の上の出典）は MIN_PT のまま
COPYRIGHT_FOOTER = re.compile(r"^©\s*\d{4}\s+.+?\s+All rights reserved\.(?:\s*｜\s*(?:Internal Only|Confidential))?\s*$", re.I)
COPYRIGHT_NG = f"{COPYRIGHT_PT}pt 未満の著作権フッター"
JA = r"぀-ゟァ-ヺー-ヿ㐀-鿿"  # かなと漢字（中黒「・」と全角の記号は含めない）

HARD = {
    "絵文字": re.compile("[\U0001F300-\U0001FAFF☀-⛿✅✨❌⭐️]"),
    "長いダッシュ": re.compile("[—―](?!$)|(?<!^)[—―]"),  # 「—」だけのセル（該当なし）は数えない
    "置き換え忘れ": re.compile(r"TODO|FIXME|XXX|lorem|ipsum|〇〇|○○|ここに.{0,6}(入|書)|\[insert", re.I),
    "差し替えの仮ページ": re.compile(r"差し替え："),  # 札の残り。人には Drive の URL で渡し、差し替える人はいない（2026-10-07）
}
WARN = {
    "空疎な言い回し": re.compile(r"(を|の)(実現|加速|最適化|効率化|高度化|強化|推進|促進|変革|最大化)(する|します|。|$)"
                          r"|革新的|次世代の|シームレス|ゲームチェンジ|新たな価値|可能性を広げ|解き放|圧倒的|劇的に|飛躍的"),
    "あおり": re.compile(r"乗り遅れ|取り残さ|このままでは|待ったなし|手遅れ"),
    "英語の大文字ラベル": re.compile(r"^(?![0-9A-F]{6}$)[A-Z][A-Z0-9 &/\-]{3,}$"),  # 6 桁の色の値（F9F7F4 など）は数えない
    "和欧間のスペース抜け": re.compile(rf"[{JA}][A-Za-z0-9]|[A-Za-z0-9][{JA}]"),
    "約物の前後のスペース": re.compile(r" [、。，．）」』]|[（「『] "),
    "要確認・TBD": re.compile(r"要確認|TBD"),
    "社外秘の表示": re.compile(r"Internal Only|Internal Use|Confidential|社外秘|社内限り", re.I),
}
SLIDE_ONLY = {"スライドに です・ます": re.compile(r"(です|ます|でした|ました|ません|ください)(。|$|」)")}
NOTES_ONLY = {"ノートに だ・である": re.compile(r"(だ|である|だった)。")}
NUM = re.compile(r"\d[\d,.]*\s?(%|％|倍|億|万|兆|円|ドル|USD|ms|TB|GB|PB|K\b|M\b)|[$＄]\s?\d")  # 統計らしい数字だけ（「2 時間」「3 社」は数えない）
URL = re.compile(r"https?://\S+")



def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)



BODY_LINES = "本文が 8 行を超える見込み"
NO_LINK = "出典の行にリンクがない"
TALK_MAX = 125  # [lint-002] 話す資料の 1 枚の本文の目安。5 行 × 1 行 25 字（Research/deck_research/log/20261006_jp_content.md の 1-13、visual.md の 2）
TALK = f"話す資料で本文が {TALK_MAX} 字を超える"
# [lint-003] 章の扉（濃紺の地）。本編が長いのに扉がないと、テーマの切り替わりが唐突になる。扉の間が 1 枚だけなら細切れ（visual.md の 1）
DIVIDER_MIN = 12
NO_DIVIDER = f"{DIVIDER_MIN} 枚を超えるのに章の扉がない"
SHORT_CH = "扉のあとが 1 枚だけの章"
NO_COVER = "1 枚目が表紙（濃紺の地）でない"
ARROW_MID = "横向きの矢印が、両側の箱の上下の中央にない"
LINE_GRID = "格子を線で組んでいる（標準の表にできないか）"
NO_NOTES = "ノートがない"
NO_SOURCE = "数字に出典の行がない"
TWO_LINES = "見出しかリードが 2 行の見込み"  # 見出しは 1 行、リードは 1 文（visual.md の 1）
HEAD_PERIOD, BULLET_PERIOD = "見出しの句点", "箇条書きの句点の混在"  # content.md の 6。名前は Docs の規則と同じ（Docs は見出しのスタイル、箇条書きのリストごと）
# [lint-023] 見出しは短い名詞句。言い切りは判断を頼むページと数字の結論のページの 2〜3 枚だけ（content.md の 4・6、visual_doc.md の 2）
HEAD_POLITE, HEAD_CLAIMS, CLAIM_MAX = "見出しが「ください・します」で終わる", "言い切りの見出しが多い", 3
POLITE_END = re.compile(r"(ください|します|しましょう)$")
CLAIM_END = re.compile(r"[るうくすつむぶぐただい]$")  # 読点があり、動詞・形容詞らしい仮名で終わるものを言い切りの見込みにする。「N つ」で終わる名詞句は除く。形態素解析は入れない
# [lint-004] 空きと結論バンド。目安は、空いて見えたページを拾う値にした
EMPTY_BELOW = "本文の下が空いている"
EMPTY_BOX = "箱の中の下が空いている"
EMPTY_HOLE = "本文の中ほどが空いている"  # [lint-005] 要素と要素の間・結論バンドの上・本文の上の大きな空き。中身より大きい箱やページの中の穴を、レビューより先に出す
PAD_NG = "塗りの箱の端と文字の間が 1 字分より狭い"  # visual.md の 4
NUM_NO_UNIT = "大きな数字に単位がない"  # [lint-006] visual.md の 2。数字だけの段落は何の数か分からない
PHRASE_BREAK = "自動の折り返しが文節の途中に入る見込み"  # [lint-024] visual.md の visual-013。Google Slides は和文を 1 字ずつ折り返す。レビューで直した改行でいちばん多かった
NO_HEAD = "、。，．）」』】〕・ー!?！？：；"  # 行頭に来ない字（禁則で前の行に戻るので、見込みの位置で折れない）
OPEN_HEAD = "手の改行のあとの行頭に全角の開き括弧"  # [lint-007] visual.md の 2 の「改行」。行頭の「（」「「」は半字下がって見え、左端がそろわない
COL_SHIFT = "隣り合う列の箱の上端か下端がずれている"  # [lint-008] visual.md の 4。片方の列にだけ小見出しを置くと、箱の上下がそろわない
BIG_NUM_PT, COL_TOL, COL_MAX, NEST = 28, 0.03 * EMU, 1.0 * EMU, 0.25 * EMU  # 大きな数字の大きさ。列のずれは 0.03〜1.0 in を出す（それより大きいのは中身の量の違いとみなす）
DASH_ROUND = "点線の角丸が Google 標準の丸み"  # slides.md の 5。中のカード（半径 0.1 in）と曲率が合わない。JSON の box の dash にする（2026-10-08）
CODE_NOT_MONO = f"濃紺の地のコードが等幅の {MONO_DEFAULT} でない"  # [lint-009] visual.md の 2。pages.py に残った古いコードの箱の部品で、等幅にならなかった（レビューでも見落としやすい）
CODE_LINE = re.compile(r"\s*(SELECT|UPDATE|INSERT|DELETE|CREATE|ALTER|WITH|FROM|WHERE|SET|ANALYZE|GROUP BY|ORDER BY|import|def|pip|uv|curl|psql|python3?|databricks)(?=[\s(;]|$)")  # コードの行の頭（URL の databricks.com などは数えない）
BLOCK_ON_NAVY = "濃紺の箱の上に NAVY_BLOCK の箱"  # [lint-010] visual.md の 1。地との差が小さく、群の境が見えない。本文ページでは淡色（PANEL・CARD）にする。扉（濃紺の地）は見ない
STAGE_NG = "提供ステージの札の塗りが言葉と合わない"  # [lint-011] visual.md の 1。Public Preview（本番で使える）を Beta・Private Preview の黄と分ける
MANY_BANDS = "結論バンドが本文の 3 分の 1 を超える"  # [lint-012] visual.md の 1「要るページにだけ」
GAP_BELOW, GAP_BOX = 1.0 * EMU, 0.6 * EMU  # 本文の下（本文の領域 5 in の 2 割）と、箱の中の文字より下
GAP_HOLE, GAP_TOP = 0.65 * EMU, 1.0 * EMU  # 要素の間の穴と、本文の上の空き
THIN = 0.05 * EMU  # これより細い四角は線として数える（四角で罫線や軸を引いても、格子と矢印の確かめから漏れないように）  # 全ページにスピーカーノートを書く（visual.md の 1）
MONO = MONO_DEFAULT  # 見ている資料の等幅の書体。lint_slides がデッキのテーマから入れ直す（is_mono などが読む。ponytail: 1 つずつ見る前提の大域の値）
FONT_NG = f"書体が {FONT} でない"  # スライドはテンプレートの書体（deck_font）と比べる。Google Fonts にない書体は、API が受け付けても黙って別の書体で描かれる（slides.md の 5）。英数字だけの MONO（コード）は通す
MONO_NG = f"等幅の {MONO_DEFAULT} に和文"  # 名前は既定の書体のまま（台帳と lint_runs.jsonl が名前で数える）。テーマの mono なら指摘にその名前を出す。MONO に和文の字形はなく、Google が別の書体で描く。和文は FONT にする（slides.py の mono_reqs。visual.md の 2）
DECK_WIDE = {NO_COVER, NO_DIVIDER, SHORT_CH, MANY_BANDS, HEAD_CLAIMS}  # デッキ全体を見て出す規則。lint_slides の only で絞らない（ページの番号が付いていても、ほかのページで決まる）
PAGE_ONLY = {NO_NOTES, NO_SOURCE, NO_LINK, TALK, TWO_LINES, HEAD_PERIOD, HEAD_POLITE, EMPTY_BELOW, EMPTY_HOLE}  # ページを見て出す規則。部品だけを見るときは出さない
ESTIMATE = {TWO_LINES, BODY_LINES, PHRASE_BREAK, EMPTY_BELOW, EMPTY_BOX, EMPTY_HOLE}  # 字幅と行の高さの見積もりから出す指摘。Google が描いた画像で確定する（ほかは JSON で決まる）
HARD_NAMES = set(HARD) | {HEAD_PERIOD, HEAD_POLITE, f"{MIN_PT}pt 未満の文字", f"{DOC_MIN_PT}pt 未満の文字", COPYRIGHT_NG, FONT_NG, MONO_NG, "用紙が A4 でない", "追跡の印の付いたリンク"}
INS = INSET * 72  # 文字の枠の内側の余白（pt）。Slides API の既定は 0.1 in で、変えられない
BODY_TOP, BODY_BOTTOM = Y_BODY_NOLEAD * EMU, BAND_BOTTOM * EMU  # 本文の領域（visual.md の 1 の配置）
FOOT_TOP = (Y_FOOT - 0.13) * EMU  # これより下はフッター（出典の行 6.68 in とフッター 7.08 in の間）


# ---- Slides API の presentations.get の JSON を読む ----
def hexof(c, scheme):
    """OpaqueColor（テーマの色か RGB）を 6 桁にする。テーマの色はマスターの配色で引く。"""
    if not c:
        return None
    c = c.get("opaqueColor", c)
    if "themeColor" in c:
        return scheme.get(c["themeColor"])
    if "rgbColor" not in c:
        return None
    return "%02X%02X%02X" % tuple(round(c["rgbColor"].get(k, 0) * 255) for k in ("red", "green", "blue"))


def solid(fill, scheme):  # 塗り（shapeBackgroundFill・pageBackgroundFill・tableCellBackgroundFill）。透明と継承は None
    if (fill or {}).get("propertyState") in ("NOT_RENDERED", "INHERIT"):  # 塗らない枠にも、API は既定の色を返す
        return None
    sf = (fill or {}).get("solidFill")
    return hexof(sf.get("color"), scheme) if sf and sf.get("alpha", 1) > 0 else None


def scheme_of(p, mid):
    m = next((m for m in p.get("masters", []) if m["objectId"] == mid), (p.get("masters") or [{}])[0])
    return {c["type"]: hexof({"rgbColor": c["color"]}, {}) for c in m.get("pageProperties", {}).get("colorScheme", {}).get("colors", [])}


def page_fill(p, s, scheme):  # ページの地の塗りの色（テーマの色か RGB のまま）。継承ならレイアウト、マスターの順に見る
    sp = s.get("slideProperties", {})
    pages = [s] + [x for x in p.get("layouts", []) if x["objectId"] == sp.get("layoutObjectId")] \
        + [x for x in p.get("masters", []) if x["objectId"] == sp.get("masterObjectId")]
    for pg in pages:
        f = pg.get("pageProperties", {}).get("pageBackgroundFill")
        if solid(f, scheme):
            return f["solidFill"]["color"]
    return None


def page_bg(p, s, scheme):  # ページの地
    return hexof(page_fill(p, s, scheme), scheme) or "FFFFFF"


def is_dark(p, s, scheme):
    """表紙・扉のページか。slides.py は表紙・扉の地を NAVY（DARK1）、本文の地を BG（LIGHT1）のテーマの色で塗るので、地の色の値でなく枠で見る
    （本文の地が暗いテーマでも、本文のページを扉と取り違えない）。RGB で塗ったページ（手で作ったもの）は、DARK1 と同じ値なら扉とみなす。
    会社のテンプレートの表紙・扉のパターン（白や赤の地もある）は、レイアウトの目印（slides.py の LAYOUT_MARK）で見る。"""
    lay = next((x for x in p.get("layouts", []) if x["objectId"] == s.get("slideProperties", {}).get("layoutObjectId")), {})
    if any(LAYOUT_MARK.search(e.get("description", "")) for e in lay.get("pageElements", [])):
        return True
    c = page_fill(p, s, scheme) or {}
    return c.get("themeColor") == "DARK1" if "themeColor" in c else page_bg(p, s, scheme) == scheme.get("DARK1", "1B3139")


def mag(d):
    return d.get("magnitude", 0) * (12700 if d.get("unit") == "PT" else 1)


def flatten(els, g=(1, 1, 0, 0)):
    """グループをほどき、(要素, [x, y, w, h]) を重なりの順に返す（EMU）。グループの変形は縮尺と移動だけを合成する。"""
    for e in els:
        t = e.get("transform", {})
        one = 0 if t else 1  # API の JSON は 0 の値を省く（横の線は scaleY、縦の線は scaleX がない）。2026-10-08 まで 1 と読み、線の検査が効いていなかった
        sx, sy = t.get("scaleX", one) * g[0], t.get("scaleY", one) * g[1]
        tx, ty = g[0] * t.get("translateX", 0) + g[2], g[1] * t.get("translateY", 0) + g[3]
        if "elementGroup" in e:
            yield from flatten(e["elementGroup"].get("children", []), (sx, sy, tx, ty))
            continue
        w, h = mag(e.get("size", {}).get("width", {})) * sx, mag(e.get("size", {}).get("height", {})) * sy
        yield e, [min(tx, tx + w), min(ty, ty + h), abs(w), abs(h)]


def group_lines(els, inside=False):
    """グループの中の線の ID。slides.py の塗りのない角丸の囲みは、辺と弧を線でつないでグループにする。矢印・罫線・格子の線としては見ない。
    ponytail: 画面で線をまとめてグループにした格子も見逃す。困ったら、弧の短い線を含むグループだけを外す"""
    for e in els:
        if "elementGroup" in e:
            yield from group_lines(e["elementGroup"].get("children", []), True)
        elif inside and "line" in e:
            yield e["objectId"]


def ancestry(els, up=()):
    """要素の ID から、入っているグループの ID の並び（外から内）。slides.py の角丸・正円は、背景と文字の枠を 1 つのグループにする（Deck.box）。"""
    for e in els:
        if "elementGroup" in e:
            yield from ancestry(e["elementGroup"].get("children", []), up + (e.get("objectId"),))
        else:
            yield e.get("objectId"), up


def cells(e, scheme=None):
    """要素の (文字, 地の色) の並び。図形は 1 つ、表はセルごと（行の順）。地の色は塗りがなければ None。"""
    scheme = scheme or {}
    if "shape" in e:
        return [(e["shape"].get("text"), solid(e["shape"].get("shapeProperties", {}).get("shapeBackgroundFill"), scheme))]
    return [(c.get("text"), solid(c.get("tableCellProperties", {}).get("tableCellBackgroundFill"), scheme))
            for row in e.get("table", {}).get("tableRows", []) for c in row.get("tableCells", [])]


def note_text(s):
    """ページのスピーカーノートの文字。"""
    notes = s.get("slideProperties", {}).get("notesPage", {})
    spk = notes.get("notesProperties", {}).get("speakerNotesObjectId")
    return "\n".join(ptext(x) for e, _ in flatten(notes.get("pageElements", [])) if e["objectId"] == spk
                     for x in paras(e.get("shape", {}).get("text")))


def body_chars(els, title=None):
    """見出し・リード・出典・フッターを除いた本文の字数（空白は数えない）。図形と表の文字を数える。"""
    return sum(len(re.sub(r"\s", "", ptext(x))) for e, b in els if e is not title and BODY_TOP <= b[1] < BODY_BOTTOM
               for text, _ in cells(e) for x in paras(text) if not re.match(r"\s*(出典|Sources?)[：:]", ptext(x), re.I))


def paras(text):
    """段落ごとに (段落の書式, [(文字, 書式), …]) を返す。段落の中の改行（\\v）は文字に残す。箇条書きの段落は書式に bullet: True を足す。"""
    out = []
    for te in (text or {}).get("textElements", []):
        if "paragraphMarker" in te:
            out.append((te["paragraphMarker"].get("style", {}) | ({"bullet": True} if "bullet" in te["paragraphMarker"] else {}), []))
        elif "textRun" in te and out:
            out[-1][1].append((te["textRun"]["content"].replace("\n", ""), te["textRun"].get("style", {})))
    return out


def ptext(para):
    return "".join(c for c, _ in para[1]).replace("\v", " ")


def size_of(st):
    return st.get("fontSize", {}).get("magnitude")


def est_lines(para, avail):
    """段落の行数の見込み。文字の大きさの分からない run（プレースホルダーの継承）があれば None。"""
    segs = [0.0]
    for c, st in para[1]:
        if c and size_of(st) is None:
            return None
        for i, part in enumerate(c.split("\v")):
            if i:
                segs.append(0.0)
            segs[-1] += em_width(part) * (size_of(st) or 0)
    return sum(max(1, math.ceil(x / avail - 1e-9)) for x in segs)


def wrap_breaks(para, avail):
    """段落を幅 avail（pt）で自動で折り返したときに、行の頭になる字の位置（段落の文字列の位置）の見込み。数え方は slides.py の wrap_lines と同じ
    （和文は 1 字ずつ、英数字の語はまとめて次の行へ、1 行より長い語は字で折る）。run ごとの大きさを見る。文字の大きさの分からない run があれば []"""
    if any(size_of(st) is None for c, st in para[1] if c.strip()):
        return []
    ws = [em_width(ch, st.get("fontFamily") == MONO) * (size_of(st) or 0) for c, st in para[1] for ch in c]
    t, out, cur = "".join(c for c, _ in para[1]), [], 0.0
    for m in re.finditer(r"[!-~]+| +|\v|.", t):
        if m.group() == "\v":
            cur = 0.0
            continue
        a, b = m.span()
        for k, e in ([(k, k + 1) for k in range(a, b)] if sum(ws[a:b]) > avail + 1e-9 else [(a, b)]):
            w = sum(ws[k:e])
            if cur + w > avail + 1e-9 and cur > 0:
                if t[k].isspace():  # 行末の空白は次の行に送らない
                    cur = 0.0
                else:
                    out.append(k)
                    cur = w
            else:
                cur += w
    return out


def segment(texts):
    """文字列ごとの文節の切れ目の位置の集合。BudouX を uv で別に呼ぶ（lint.py は標準ライブラリだけのまま。box_pad.py の Pillow と同じ）。
    uv か BudouX が使えないとき・時間切れ・形の合わない結果のときは None（この点検を数えない）"""
    code = "import sys, json, budoux; p = budoux.load_default_japanese_parser(); print(json.dumps([p.parse(t) for t in json.load(sys.stdin)]))"
    try:
        res = subprocess.run(["uv", "run", "-q", "--no-project", "--with", "budoux==0.9.3", "python", "-c", code], input=json.dumps(texts),
                             capture_output=True, text=True, timeout=60)  # 版を固定して文節の分け方をそろえる。初めてだけ BudouX を取りにネットワークが要る
        segs = json.loads(res.stdout) if res.returncode == 0 else None
        if isinstance(segs, list) and len(segs) == len(texts) and all("".join(x) == t for x, t in zip(segs, texts)):
            return {t: set(itertools.accumulate(map(len, x))) for t, x in zip(texts, segs)}
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        pass
    return None


def mid_phrase(cands):
    """cands は (場所, 段落の文字列, 折り返しの位置) の並び。文節の切れ目にない折り返しを返す。候補がなければ uv を呼ばない。
    行頭に来ない字の前と、空白の後（英数字の語の切れ目）は数えない。文節が分からなければ None"""
    if not cands:
        return []
    cuts = segment(sorted({t for _, t, _ in cands}))
    if cuts is None:
        return None
    return [f"{where}: 「{t[max(0, k - 8):k]}／{t[k:k + 6]}」".replace("\v", "⏎") + "。文節の切れ目で手で改行するか、言い換えるか、枠の幅を変える（見込みなので画像で確かめる）"
            for where, t, bs in cands for k in bs if k not in cuts[t] and t[k] not in NO_HEAD and t[k - 1] not in " 　"]


def body_lines(e, b, title=None):
    """本文の領域の文字の枠の行数の見込み。見出し・出典・フッター・表は数えない。"""
    sh = e.get("shape")
    if not sh or e is title or b[1] < BODY_TOP or b[1] >= BODY_BOTTOM or is_mono(sh):
        return None
    text = "\n".join(ptext(x) for x in paras(sh.get("text"))).strip()
    if not text or re.match(r"^(出典|Sources?)[：:]", text, re.I):
        return None
    return text_lines(sh, b[2])


def text_lines(sh, width):
    """図形の文字の行数の見込み（width は枠の幅、EMU）。文字の大きさの分からない段落があれば None。"""
    total = 0
    for para in paras(sh.get("text")):
        avail = width / EMU * 72 - 2 * INS - para[0].get("indentStart", {}).get("magnitude", 0)
        n = est_lines(para, avail) if avail > 0 else None
        if n is None:
            return None
        total += n
    return total


def text_bottom(sh, b):
    """文字の下端の見込み（EMU）。行送りは slides.py の est_h と同じ（大きさの 1.2 倍 × 行間）。上下の中央・下のそろえも見る。大きさの分からない段落があれば None。"""
    h = 0
    for para in paras(sh.get("text")):
        avail = b[2] / EMU * 72 - 2 * INS - para[0].get("indentStart", {}).get("magnitude", 0)
        n = est_lines(para, avail) if avail > 0 else None
        sz = max((size_of(st) or 0 for _, st in para[1]), default=0)
        if n is None or not sz:
            return None
        h += n * sz * 1.2 * para[0].get("lineSpacing", 100) / 100 / 72 * EMU
    return {"MIDDLE": b[1] + (b[3] + h) / 2, "BOTTOM": b[1] + b[3]}.get(sh.get("shapeProperties", {}).get("contentAlignment"), b[1] + INSET * EMU + h)


def ink_bottom(e, b, scheme):
    """見える下端（EMU）。塗りのない文字の枠は文字の下端、ほかは枠の下端。
    ponytail: 表は JSON の高さ（行の最小の高さ）で見るので、折り返して伸びた表の下は空きを多めに見積もる。困ったら行ごとの文字から高さを見積もる"""
    sh = e.get("shape")
    if not sh or not sh.get("text") or solid(sh.get("shapeProperties", {}).get("shapeBackgroundFill"), scheme):
        return b[1] + b[3]
    return text_bottom(sh, b) or b[1] + b[3]


def is_band(e, b, scheme):  # 結論バンド（slides.py の band）: 濃紺の塗り、下端 6.60 in、本文の幅いっぱい
    fill = solid(e.get("shape", {}).get("shapeProperties", {}).get("shapeBackgroundFill"), scheme)
    return fill == scheme.get("DARK1", "1B3139") and abs(b[1] + b[3] - BODY_BOTTOM) < 0.05 * EMU and b[2] > 11 * EMU


def empty_space(els, scheme):
    """(結論バンドがあるか, 本文の下の空き, [箱の中の文字より下の空き]) を返す（EMU）。本文は、結論バンド（なければ 6.60 in）より上で、1.62 in より下に届く要素。
    [lint-013] 下の空きは、上の空き（本文の上端 1.78 in から最初の要素まで）を引いたもの。上下の中央に置いた図（時系列など）は出さない。"""
    band = next((b for e, b in els if "shape" in e and is_band(e, b, scheme)), None)
    floor = band[1] if band else BODY_BOTTOM
    body = [(e, b, ink_bottom(e, b, scheme)) for e, b in els if b[1] < floor - 0.01 * EMU and b[1] + b[3] > BODY_TOP]
    top = min((b[1] for _, b, _ in body if b[1] >= BODY_TOP), default=Y_BODY * EMU)  # 本文の領域で始まる最初の要素（見出し・リードの枠が下へ伸びていても数えない）
    below = floor - max(k for *_, k in body) - max(0, top - Y_BODY * EMU) if body else 0
    boxes = []
    for e, b, _ in body:
        sh = e.get("shape")  # 箱は塗りで見分ける（slides.py は文字の枠も塗りのない RECTANGLE で作る）
        if not sh or not solid(sh.get("shapeProperties", {}).get("shapeBackgroundFill"), scheme) or min(b[2], b[3]) < THIN:
            continue
        if e.get("title") == BAR_MARK:  # 棒グラフの棒（slides.py の bars）。棒の中の数字の下が空くのは決まった形
            continue
        inner = [k for e2, b2, k in body if e2 is not e and (has_text(e2) or "table" in e2 or "image" in e2)  # 文字のない図形（角丸を組む部品・枠線）は中身に数えない
                 and b[0] <= b2[0] + b2[2] / 2 <= b[0] + b[2] and b[1] <= b2[1] + b2[3] / 2 <= b[1] + b[3]]
        own = text_bottom(sh, b) if sh.get("text") else None
        if inner or own:
            boxes.append(b[1] + b[3] - max(inner + [own or 0]))
    return band is not None, below, boxes


def page_holes(els, scheme):
    """本文の中ほどの大きな空き（EMU の組の一覧）。中身（文字・表・画像・塗りの箱）の縦の範囲を重ね、間が GAP_HOLE 以上のところ。
    表の下は数えない（JSON の高さは行の最小で、折り返して伸びた分が分からない）。結論バンドの上と、本文の上（GAP_TOP 以上）も見る。"""
    band = next((b for e, b in els if "shape" in e and is_band(e, b, scheme)), None)
    floor = band[1] if band else BODY_BOTTOM
    iv = []
    for e, b in els:
        if "line" in e or b[1] < BODY_TOP - 0.05 * EMU or b[1] >= floor - 0.01 * EMU:
            continue
        sh = e.get("shape")
        filled = sh and solid(sh.get("shapeProperties", {}).get("shapeBackgroundFill"), scheme)
        if sh and not has_text(e) and not filled:
            continue
        top = b[1] + (INSET * EMU if sh and not filled else 0)
        iv.append((top, max(ink_bottom(e, b, scheme), top), "table" in e))
    out = []
    if not iv:
        return out
    iv.sort()
    if iv[0][0] - Y_BODY * EMU >= GAP_TOP:
        out.append(("上", Y_BODY * EMU, iv[0][0]))
    cur, tab = iv[0][1], iv[0][2]
    for a, z, t in iv[1:]:
        if a - cur >= GAP_HOLE and not tab:
            out.append(("間", cur, a))
        if z > cur:
            cur, tab = z, t
    if band and floor - cur >= GAP_HOLE and not tab:
        out.append(("結論バンドの上", cur, floor))
    return out


def tight_pad(sh, b, box):  # [lint-014] 塗りの箱に左寄せ・右寄せで置いた文字と、箱の端の間が 1 字分（文字の大きさ）より狭い（visual.md の 4。pptx から作り直した札の余白は、枠の内側の余白 0.1 in のままになりやすい）
    ps = [x for x in paras(sh.get("text")) if ptext(x).strip()]
    if not box or not ps or ps[0][0].get("alignment", "START") not in ("START", "END"):
        return None
    sz = min((size_of(st) or 99) for x in ps for c, st in x[1] if c.strip())  # 本文の 1 字（大きな数字と説明の枠は、説明の大きさで測る）
    sz = 0 if sz == 99 else sz
    start = ps[0][0].get("alignment", "START") == "START"
    gap = b[0] + INSET * EMU - box[0] if start else box[0] + box[2] - (b[0] + b[2] - INSET * EMU)
    need = sz / 72 * EMU
    if sz and 0 <= gap < need - 0.01 * EMU:
        return f"{gap / EMU:.2f} in（{sz:g}pt の 1 字は {need / EMU:.2f} in）「{ptext(ps[0])[:20]}」"
    return None


def is_mono(sh):  # 文字がすべて等幅（コードの箱）。出典・行数・大文字のラベルの検査から外す（2026-10-11、コードの `source:`・SELECT・行数で誤検知が出た）
    runs = [(c, st) for x in paras(sh.get("text")) for c, st in x[1] if c.strip()]
    return bool(runs) and all(st.get("fontFamily") == MONO for _, st in runs)


def has_text(e):
    sh = e.get("shape")
    return bool(sh and "".join(ptext(x) for x in paras(sh.get("text"))).strip())


def src_without_link(sh):  # [lint-015] 出典の行なのに、リンクが 1 つもない（ブログや講演はそのページから飛べるようにする）
    ps = paras(sh.get("text"))
    return not is_mono(sh) and any(re.match(r"(出典|Sources?)[：:]", ptext(x).strip(), re.I) for x in ps) and not any("link" in st for x in ps for _, st in x[1])


def off_center_arrows(lines, boxes):  # [lint-016] 2 つの箱をつなぐ横の線の高さが、どちらかの箱の上下の中央から 0.02 in を超えてずれている（言葉の置き場所のために矢印をずらすことがある）
    # 同じ 2 つの箱の間に 2 本以上の横の線があれば、上下にずらすのが意図なので見ない（行きと帰りの矢印。slides.md の arrow の offset）
    pairs, gap, tol = {}, 0.3 * EMU, 0.02 * EMU
    for x, y, w, h in lines:
        if h > 0:
            continue
        inside = [b for b in boxes if b[1] < y < b[1] + b[3]]
        left = [b for b in inside if 0 <= x - (b[0] + b[2]) <= gap]
        right = [b for b in inside if 0 <= b[0] - (x + w) <= gap]
        if left and right:
            pairs.setdefault((tuple(left[0]), tuple(right[0])), []).append((max(abs(y - (b[1] + b[3] / 2)) for b in (left[0], right[0])), y))
    return [f"{d / EMU:.2f} in ずれている（y={y / EMU:.2f} in）" for ys in pairs.values() if len(ys) == 1 for d, y in ys if d > tol]


def column_shift(cards, filled):
    """白いカードと濃紺の箱（入れ子でないもの）を左端で列に分け、隣り合う列（横に重ならず、縦に重なる）の上端・下端のずれを返す。b は [x, y, w, h]（EMU）。"""
    merged = []  # slides.py の角丸のカードは、横長と縦長の白い四角を重ねて作る。重なる四角は 1 枚のカードにまとめる
    for c in sorted(cards):
        for m in merged:
            if c[0] < m[0] + m[2] and m[0] < c[0] + c[2] and c[1] < m[1] + m[3] and m[1] < c[1] + c[3]:
                x0, y0 = min(m[0], c[0]), min(m[1], c[1])
                m[:] = [x0, y0, max(m[0] + m[2], c[0] + c[2]) - x0, max(m[1] + m[3], c[1] + c[3]) - y0]
                break
        else:
            merged.append(list(c))
    cards = merged
    # 入れ子は、縦横とも 0.25 in より大きい塗りの中にあるもの（同じカードの枠線の色の四角は数えない）
    top = [c for c in cards if not any(f[2] > c[2] + NEST and f[3] > c[3] + NEST and f[0] <= c[0] + c[2] / 2 <= f[0] + f[2] and f[1] <= c[1] + c[3] / 2 <= f[1] + f[3]
                                       for f in filled)]
    cols = []
    for c in sorted(top):
        if cols and abs(cols[-1][0][0] - c[0]) <= COL_TOL:
            cols[-1].append(c)
        else:
            cols.append([c])
    span = [(min(c[0] for c in k), max(c[0] + c[2] for c in k), min(c[1] for c in k), max(c[1] + c[3] for c in k)) for k in cols]
    out = []
    for (l1, r1, t1, b1), (l2, r2, t2, b2) in zip(span, span[1:]):
        if r1 > l2 or min(b1, b2) <= max(t1, t2):  # 横に重なる・縦に重ならない
            continue
        for what, d in (("上端", t2 - t1), ("下端", b2 - b1)):
            if COL_TOL < abs(d) < COL_MAX:
                out.append(f"{l1 / EMU:.2f} in と {l2 / EMU:.2f} in の列の{what}が {abs(d) / EMU:.2f} in ずれている")
    return out


def line_grid(lines):  # [lint-017] 上端と長さが同じ縦線が 3 本以上。ガントや表の格子を線と四角で組んでいる
    seen = Counter((round(b[1]), round(b[3])) for b in lines if b[2] == 0 and b[3] > 0)
    return [n for n in seen.values() if n >= 3]


def hit_page(h):
    """指摘の頭のページの番号（「p3: …」「p3 の見出し: …」）。頭が p<番号> でない指摘（デッキ全体のもの）は None。"""
    m = re.match(r"p(\d+)", h)
    return int(m.group(1)) if m else None


class Report:
    def __init__(self):
        self.hits = defaultdict(list)
        self.extra_hard = set()  # ワークスペースの点検（checks.py の HARD）の要修正の名前（workspace_checks が足す）
        self.where = lambda hit: ""  # 指摘の後ろに付ける、作ったものの中の場所（slides.py lint が JSON のページの部品の場所を引く）

    def scan(self, where, text, rules):
        text = URL.sub("", text).strip()
        for name, rx in rules.items():
            m = rx.search(text)
            if m:
                self.hits[name].append(f"{where}: 「{text[max(0, m.start() - 12):m.end() + 12].strip()}」")

    def show(self, names, title):
        n, est = sum(len(self.hits[k]) for k in names), sum(len(self.hits[k]) for k in names if k in ESTIMATE)
        print(f"\n== {title}: {n}" + (f"（うち見積もり {est}。画像で確定する）" if est else "") + " ==")
        for k in names:
            for line in self.hits[k][:6]:
                print(f"[{k}] {line}" + self.where(line) + ("（見積もり）" if k in ESTIMATE else ""))
            if len(self.hits[k]) > 6:
                print(f"[{k}] ほか {len(self.hits[k]) - 6} 件")
        return n


def lint_slides(p, r, reuse=False, talk=False, only=None, scope="deck"):
    """p は presentations.get の JSON。reuse は社内資料の差し替え用（元の大きさのままなので 11pt の下限と表紙を見ない）。
    only（ページの番号の集合）を渡すと、そのページの指摘・見出し・字数だけを出す（slides.py lint --pages）。デッキ全体の規則（DECK_WIDE）と、
    ワークスペースの点検（ページをまたいで見るものがありうる）は絞らない。"""
    titles, sizes, pairs, chars, dark, foot_secret, bands, claims, wraps = [], Counter(), defaultdict(list), [], [], [], [], [], []
    global MONO
    font, MONO = deck_font(p), deck_mono(p)  # 会社のテンプレートは会社の書体（deck-template）。等幅はデッキのテーマの mono
    use_font(font)  # 字幅の見積もり（行数・折り返し）もデッキの書体のもの
    card = deck_card(p)  # カードの地。デッキのテーマの CARD（書かなければ白）
    for i, s in enumerate(p.get("slides", []), 1):
        scheme = scheme_of(p, s.get("slideProperties", {}).get("masterObjectId"))
        bg = page_bg(p, s, scheme)
        dark.append(is_dark(p, s, scheme))
        grid = []
        shapes, lines, boxes, best, top, has_src, nums = [], [], [], (0, None, None), (0, None, None), False, []
        els = list(flatten(s.get("pageElements", [])))
        ups = dict(ancestry(s.get("pageElements", [])))
        parts = set(group_lines(s.get("pageElements", [])))
        for e, b in els:
            sh = e.get("shape", {})
            if e.get("objectId") in parts:
                continue
            if "line" in e or (sh.get("shapeType") == "RECTANGLE" and not sh.get("text") and min(b[2], b[3]) < THIN):
                lines.append([b[0], b[1], b[2] if b[2] >= THIN else 0, b[3] if b[3] >= THIN else 0])  # 高さ・幅がほぼ 0 の線も 0 とみなす
                lp = e.get("line", {}).get("lineProperties", {})
                if lp.get("startArrow", "NONE") == lp.get("endArrow", "NONE") == "NONE":  # 矢印は格子の線でない（並んだ下向きの矢印を格子と読まない）
                    grid.append(lines[-1])
                continue
            if "shape" not in e and "table" not in e:  # 画像・動画など。上に重ねた文字の地は分からない
                shapes.append((b, "IMAGE", None))
                continue
            texts = cells(e, scheme)
            own = texts[0][1] if "shape" in e else None
            if "shape" in e and e["shape"].get("shapeType") in ("RECTANGLE", "ROUND_RECTANGLE") and b[3] > 0:
                boxes.append(b)
            cx, cy, under, ub, uid = b[0] + b[2] / 2, b[1] + b[3] / 2, bg, None, None
            for ob, of, oi in shapes:  # 下に重なっている最後の塗り
                if of and ob[0] <= cx <= ob[0] + ob[2] and ob[1] <= cy <= ob[1] + ob[3]:
                    under, ub, uid = (None, None, None) if of == "IMAGE" else (of, ob, oi)
            up = ups.get(e.get("objectId"))
            framed = bool(up and uid and up[-1] in ups.get(uid, ()))  # 下の塗りと同じグループの文字の枠（d.label の角丸）。カードの本文や背景の四角の上の文字は別の図形
            footer = b[1] >= FOOT_TOP
            if "shape" in e and not footer and not reuse and (m := tight_pad(e["shape"], b, b if own else ub)):
                r.hits[PAD_NG].append(f"p{i}: {m}")
            if own and own == scheme.get("ACCENT1") and under == scheme.get("DARK1") and ub and not dark[-1]:
                r.hits[BLOCK_ON_NAVY].append(f"p{i}: {b[2] / EMU:.2f} × {b[3] / EMU:.2f} in。PANEL か CARD に濃紺の文字にする")
            if "shape" in e and (want := STAGE_FILL.get("".join(ptext(x) for x in paras(sh.get("text"))).strip())):
                got, want = own or under, scheme.get(want, want)
                if got != want:
                    r.hits[STAGE_NG].append(f"p{i}: 「{''.join(ptext(x) for x in paras(sh.get('text'))).strip()}」の塗りが {got}（{want} にする。slides.py の STAGE_FILL）")
            if sh.get("shapeType") == "ROUND_RECTANGLE" and sh.get("shapeProperties", {}).get("outline", {}).get("dashStyle", "SOLID") not in ("SOLID", "DASH_STYLE_UNSPECIFIED"):
                r.hits[DASH_ROUND].append(f"p{i}: {b[2]:.2f} × {b[3]:.2f} in。JSON の box に \"shape\": \"round_rectangle\", \"dash\": true を書き、半径 0.1 in の点線にする（pages.py は d.box(…, kind=\"ROUND_RECTANGLE\", dash=True)）")
            if "shape" in e and src_without_link(e["shape"]):
                r.hits[NO_LINK].append(f"p{i}: 「{''.join(ptext(x) for x in paras(e['shape'].get('text'))).strip()[:30]}」")
            for text, f in texts:
                items = [ptext(x).strip() for x in paras(text) if x[0].get("bullet") and ptext(x).strip()]
                if len({t.endswith("。") for t in items}) > 1:  # 1 つの枠の箇条書き（ひとまとまり）で、句点のある項目とない項目が混ざる
                    r.hits[BULLET_PERIOD].append(f"p{i}: 「{items[0][:20]}」から {len(items)} 項目。文なら全部に「。」、語なら全部なし")
                for para in paras(text):
                    t = ptext(para)
                    if not t.strip():
                        continue
                    if footer and WARN["社外秘の表示"].search(t):  # フッターの Internal Only は 1 件にまとめる（社内向けなら意図どおり）
                        foot_secret.append(i)
                    mono = all(st.get("fontFamily") == MONO for c, st in para[1] if c.strip())  # コードの行は大文字のラベル・数字の出典の検査から外す
                    r.scan(f"p{i}", t, {k: v for k, v in {**HARD, **WARN, **SLIDE_ONLY}.items() if not (footer and k == "社外秘の表示") and not (mono and k == "英語の大文字ラベル")})
                    raw = "".join(c for c, st in para[1] if st.get("fontFamily") != MONO)
                    if "shape" in e and not footer and not mono and re.search(f"[{JA}]", t):  # 表のセルは列の幅を見積もりに通していないので見ない
                        avail = b[2] / EMU * 72 - 2 * INS - para[0].get("indentStart", {}).get("magnitude", 0)
                        if avail > 0 and (bs := wrap_breaks(para, avail)):
                            wraps.append((f"p{i}", "".join(c for c, _ in para[1]), bs))
                    if m := re.search(r"\v\s*[（「『]", raw):
                        r.hits[OPEN_HEAD].append(f"p{i}: 「{raw[max(0, m.start() - 12):m.end() + 12].replace(chr(11), '⏎')}」。括弧の前で改行せず、括弧の後か句読点で改行する")
                    if (f or under) == scheme.get("DARK1") and CODE_LINE.match(t) and any(st.get("fontFamily") != MONO and re.search("[A-Za-z]", c) for c, st in para[1]):
                        r.hits[CODE_NOT_MONO].append(f"p{i}: 「{t.strip()[:30]}」。JSON の code か、text の \"mono\": true にする（pages.py は d.code か d.text(…, mono=True)）")
                    if not dark[-1] and re.fullmatch(r"[\d.,]+", t.strip()) and max((size_of(st) or 0) for _, st in para[1]) >= BIG_NUM_PT:
                        r.hits[NUM_NO_UNIT].append(f"p{i}: 「{t.strip()}」。単位と何の数かを数字と同じ枠に書く（例: 16 モデル）")
                    if "出典" in t:
                        has_src = True
                    elif not footer and not mono and NUM.search(t):
                        nums.append(t)
                    for c, st in para[1]:
                        txt, sz = c.strip(), size_of(st)
                        if not txt:
                            continue
                        if st.get("fontFamily") == MONO:
                            if re.search(r"[^\x00-\x7e]", txt):
                                r.hits[MONO_NG].append(f"p{i}: " + (f"{MONO}" if MONO != MONO_DEFAULT else "") + f"「{txt[:20]}」")
                        elif st.get("fontFamily") not in (None, font):
                            r.hits[FONT_NG].append(f"p{i}: {st['fontFamily']}" + (f"（このデッキはテンプレートの {font}）" if font != FONT else "") + f"「{txt[:20]}」")
                        if sz is None:  # プレースホルダーから継承（ページ番号など）
                            continue
                        sizes[sz] += 1
                        copyright_footer = footer and COPYRIGHT_FOOTER.fullmatch(t.strip())
                        if copyright_footer:
                            minimum = COPYRIGHT_PT
                        elif "shape" in e and (f or framed):  # 塗りのある図形の中（自分の塗りか、同じグループの塗り）
                            minimum = FIG_MIN_PT
                        else:
                            minimum = MIN_PT
                        if sz < minimum and not reuse:
                            r.hits[COPYRIGHT_NG if copyright_footer else f"{MIN_PT}pt 未満の文字"].append(f"p{i}: {sz:g}pt「{txt[:20]}」")
                        col, ground = hexof(st.get("foregroundColor"), scheme), f or under
                        if col and ground:
                            large = sz >= 18 or (sz >= 11 and st.get("bold"))  # 太字は本文の 11pt から大きな文字（WCAG の 14pt より下げた。visual.md の 3）
                            pairs[(col, ground, 3.0 if large else 4.5)].append(txt)
                        if sz > best[0] and not re.fullmatch(r"[\d\s.]+", txt):
                            best = (sz, e, b)
                        if 0.3 * EMU <= b[1] <= 1.3 * EMU and sz >= 20 and sz > top[0]:
                            top = (sz, e, b)
            if "shape" in e:
                shapes.append((b, own, e.get("objectId")))
        if top[1] is not None:
            best = top
        if best[1] is not None:
            sz, e, b = best
            ts = [ptext(x) for text, _ in cells(e) for x in paras(text) if ptext(x).strip()]
            avail = b[2] / EMU * 72 - 2 * INS
            n = sum(max(1, -(-em_width(t) * sz // avail)) for t in ts) if avail > 0 else 1
            titles.append(f"p{i}  {' / '.join(ts)}" + (f"  （{int(n)} 行の見込み）" if n > 1 else ""))
            head = "".join(ts).rstrip()
            if "。" in head:  # 文の途中の句点も（2 文の見出しは短い名詞句でない）
                r.hits[HEAD_PERIOD].append(f"p{i}: 「{' / '.join(ts)[:30]}」")
            if POLITE_END.search(head):
                r.hits[HEAD_POLITE].append(f"p{i}: 「{' / '.join(ts)[:30]}」。頼みごとはリードか本文で言う")
            if not dark[-1] and "、" in head and CLAIM_END.search(head) and not re.search(r"\d+ つ$", head):
                claims.append(i)
            if top[1] is not None and n > 1:
                r.hits[TWO_LINES].append(f"p{i} の見出し: 「{' / '.join(ts)[:30]}」")
        for e, b in els:  # リード（上端 1.20 in の 1 文）
            if "shape" in e and e is not best[1] and abs(b[1] / EMU - Y_LEAD) < 0.12:
                lead = "".join(ptext(x) for x in paras(e["shape"].get("text"))).strip()
                if lead:  # 名詞句の見出しのページは、言えることをリードで言うので、一覧に並べる
                    titles.append(f"      {lead}")
                k = text_lines(e["shape"], b[2])
                if k and k > 1:
                    r.hits[TWO_LINES].append(f"p{i} のリード: 「{lead[:30]}」")
        r.hits[ARROW_MID].extend(f"p{i}: {m}" for m in off_center_arrows(lines, boxes))
        r.hits[LINE_GRID].extend(f"p{i}: 同じ長さの縦線が {n} 本。格子は表にし、月をまたぐバーなどだけ図形で上に置く（slides.md の 4）" for n in line_grid(grid))
        n = body_chars(els, best[1])
        chars.append(f"p{i} {n}")
        if talk and n > TALK_MAX:
            r.hits[TALK].append(f"p{i}: {n} 字")
        for e, b in els:
            k = body_lines(e, b, best[1])
            if k is not None and k > 8:
                r.hits[BODY_LINES].append(f"p{i}: {k} 行の見込み「{' / '.join(ptext(x) for x in paras(e['shape'].get('text')))[:30]}」")
        if not dark[-1] and not reuse:  # 扉・表紙と、社内資料の差し替え用は見ない
            filled = [b for e, b in els if "shape" in e and solid(e["shape"].get("shapeProperties", {}).get("shapeBackgroundFill"), scheme)]
            cards = [b for e, b in els if "shape" in e and b[1] >= BODY_TOP and b[2] >= 1.5 * EMU and b[3] >= 0.5 * EMU
                     and solid(e["shape"].get("shapeProperties", {}).get("shapeBackgroundFill"), scheme) in (card, scheme.get("DARK1", "1B3139"))]  # カード（CARD）と濃紺の箱（コード）
            r.hits[COL_SHIFT].extend(f"p{i}: {m}" for m in column_shift(cards, filled))
            band, below, boxes = empty_space(els, scheme)
            if band:
                bands.append(i)
            if below >= GAP_BELOW:
                r.hits[EMPTY_BELOW].append(f"p{i}: {below / EMU:.1f} in（{'結論バンドまで' if band else '6.60 in まで'}）。中身の少ないページはそのままでよい。箱を広げて埋めない（画像で見る）")
            if any(g >= GAP_BOX for g in boxes):
                r.hits[EMPTY_BOX].append(f"p{i}: {sum(g >= GAP_BOX for g in boxes)} 個、最大 {max(boxes) / EMU:.1f} in。箱を中身に合わせて縮める（縮めて下が空くのはよい）")
            holes = [h for h in page_holes(els, scheme) if not (h[0] == "結論バンドの上" and below >= GAP_BELOW)]  # 本文の下の空きで出したものは重ねない
            if holes:
                r.hits[EMPTY_HOLE].append(f"p{i}: " + "、".join(f"{w} {(z - a) / EMU:.1f} in（{a / EMU:.2f}〜{z / EMU:.2f} in）" for w, a, z in holes)
                                          + "。箱を中身に合わせて縮め、間を詰める。上下の中央に置いた図ならそのままでよい（画像で見る）")
        if nums and not has_src:
            r.hits[NO_SOURCE].append(f"p{i}: 「{nums[0][:30]}」")
        note = note_text(s)
        if not note.strip() and not reuse:
            r.hits[NO_NOTES].append(f"p{i}")
        for t in note.split("\n"):
            if t.strip():
                r.scan(f"p{i} のノート", t, {**HARD, **NOTES_ONLY})

    if dark and not dark[0] and not reuse:  # [lint-018] どの資料にも表紙を付ける（visual.md の 1）
        r.hits[NO_COVER].append("p1 が濃紺の地でない。表紙を付ける（定例の資料も）")
    divs = [i for i, d in enumerate(dark, 1) if d and i > 1]  # 1 枚目（表紙）は扉に数えない
    if len(dark) > DIVIDER_MIN and not divs:
        r.hits[NO_DIVIDER].append(f"{len(dark)} 枚。テーマの切り替わりに扉を置く（意味のある単位で、挟みすぎない）")
    for a, b in zip(divs, divs[1:] + [len(dark) + 1]):  # 最後の章も見る。扉が続いて間が空の章も出す
        if b - a <= 2:
            r.hits[SHORT_CH].append(f"p{a} の扉のあとが {f'p{a + 1} だけ' if b - a == 2 else '1 枚もない'}。前後の章とまとめる")
    body_pages = dark.count(False)
    if not reuse and len(bands) > max(1, body_pages / 3):
        r.hits[MANY_BANDS].append(f"本文 {body_pages} 枚中 {len(bands)} 枚（{', '.join(f'p{k}' for k in bands)}）。見出しかリードで言い切れているページからは外す（visual.md の 1）")
    if len(claims) > CLAIM_MAX:
        r.hits[HEAD_CLAIMS].append(f"{len(claims)} 枚（{', '.join(f'p{k}' for k in claims)}）。名詞句にし、言い切りは判断を頼むページと数字の結論のページの 2〜3 枚に絞る（content.md の 4）")
    if only is not None:  # 選んだページの指摘だけを残す（デッキ全体の規則 DECK_WIDE と、p<番号> で始まらない指摘は残す）。文節の点検（uv を呼ぶ）も、そのページだけにする
        on = lambda h: hit_page(h) is None or hit_page(h) in only
        wraps = [w for w in wraps if on(w[0])]
        for k in r.hits:
            if k not in DECK_WIDE:
                r.hits[k] = [h for h in r.hits[k] if on(h)]
        kept, cur = [], False
        for t in titles:  # リード（字下げの行）は、上の見出しのページについていく
            if t.startswith("p"):
                cur = on(t)
            if cur:
                kept.append(t)
        titles = kept
        chars = [c for c in chars if on(c)]
    if scope != "deck":  # ページか部品だけを見るときは、デッキ全体の規則を出さない（slides.py lint のページ・部品のファイル）
        for k in DECK_WIDE:
            r.hits.pop(k, None)
    if scope == "component":  # 部品だけのときは、ページの規則（見出し・ノート・出典・ページの空き・字数）も出さない。部品の中の規則は出す
        for k in PAGE_ONLY:
            r.hits.pop(k, None)
        titles, chars = [], []
    if (mp := mid_phrase(wraps)) is None:
        print(f"（uv か BudouX が使えないので、「{PHRASE_BREAK}」は数えていない）")
    r.hits[PHRASE_BREAK] += mp or []
    if foot_secret and scope == "deck":
        r.hits["社外秘の表示"].append(f"フッター: {len(foot_secret)} ページ（p{foot_secret[0]}〜p{foot_secret[-1]}）。社内向けなら意図どおり、顧客向けなら外す")
    print("== 見出し（各ページでいちばん大きい文字）とリード（字下げ）。順に読んで話が通るか ==")
    print("\n".join(titles))
    print(f"\n== 本文の字数（見出し・リード・出典・フッターを除く。話す資料は {TALK_MAX} 字まで） ==")
    print(" / ".join(chars))
    hard = r.show(list(HARD) + [f"{MIN_PT}pt 未満の文字", COPYRIGHT_NG, FONT_NG, MONO_NG, HEAD_PERIOD, HEAD_POLITE], "要修正")
    r.show(list(WARN) + list(SLIDE_ONLY) + list(NOTES_ONLY) + [NO_SOURCE, NO_LINK, BODY_LINES, TWO_LINES, HEAD_CLAIMS, BULLET_PERIOD, TALK, NO_NOTES, ARROW_MID, LINE_GRID, EMPTY_BELOW, EMPTY_BOX, EMPTY_HOLE, PAD_NG, NUM_NO_UNIT, OPEN_HEAD, PHRASE_BREAK, COL_SHIFT, DASH_ROUND, STAGE_NG, CODE_NOT_MONO, BLOCK_ON_NAVY, MANY_BANDS, NO_COVER, NO_DIVIDER, SHORT_CH], "要確認")
    hard += workspace_checks("slides", p, r)
    print("\n== 文字サイズ（pt: run の数） ==")
    print(", ".join(f"{k:g}: {v}" for k, v in sorted(sizes.items())))
    print("\n== コントラストが基準に届かない色の組（文字 / 地） ==")
    for (fg, bk, need), ts in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
        c = contrast(fg, bk)
        if c < need:
            print(f"{fg} / {bk}  {c:.2f}（基準 {need:g}）  {len(ts)} か所  例:「{ts[0][:20]}」")
    return hard


# ---- Docs API の documents.get の JSON を読む（docs.py check が書き出して呼ぶ。2026-10-09） ----
SENTENCE_MAX, PARA_SENT_MAX, LINE_MAX = 100, 8, 40  # 一文の字数（textlint の sentence-length の既定）、1 段落の文の数（3〜8 文。木下・倉島・サイボウズ）、
# 1 行の字数（jlreq・デジタル庁）。visual_doc.md の 1・3
BOLD_PER_1000 = 3  # 本文 1,000 字あたりの太字の数（Qiita の 2019〜22 年の平均は 1.26、2026 年は 3.83。visual_doc.md の 3）
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
    """factory.toml の [docs.themes] の用紙（pt の幅・高さ）。会社のテンプレートに合わせた版面なので、A4 でなくても、1 行の字数が多くても通す。"""
    import gapi, tomllib
    try:
        cfg = tomllib.loads(p.read_text()) if (p := gapi.locate()) else {}
    except tomllib.TOMLDecodeError:
        return []
    return [tuple(x * 72 / 25.4 for x in t["page"]) for t in cfg.get("docs", {}).get("themes", {}).values() if "page" in t]


def lint_gdoc(doc, r, template=False, font=FONT, mono=MONO_DEFAULT):
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
        r.hits[A4_NG].append(f"用紙 {pw:.0f} × {ph:.0f}pt（A4 は 595 × 842。テーマの用紙は factory.toml の [docs.themes]）。docs.py build で入れ直す")
    per_line = width / base.get("fontSize", {}).get("magnitude", 11)
    if per_line > LINE_MAX + 1 and not themed:  # [lint-019] テーマの版面は会社のテンプレートに合わせたもので、1 行の字数が多くなることがある
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
        if style == "TITLE" and text.rstrip("。").endswith("について"):
            r.hits["題が「について」で終わる"].append(f"{where}: 「{text[:30]}」。主題と文書の性格（提案・報告・計画）を入れる（visual_doc.md の 2）")
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
        r.hits["冒頭に要旨がない"].append(f"最初の章「{h1[0][:20]}」。結論と読み手に求めることを最初の章で言う（visual_doc.md の 2）")
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
    r.show(list(WARN) + [NO_LINK] + list(DOC_ONLY), "要確認")
    hard += workspace_checks("doc", doc, r)
    return hard


def workspace_checks(kind, data, r):
    """ワークスペースの点検。rules/deck-build/checks.py の slides(p, r)・doc(doc, r) を呼ぶ（修正の指示から育てる、そのワークスペースだけの点検。
    deck-practices/rules.md の「決まりの層」）。足された指摘のうち、checks.py の HARD にある名前は要修正、ほかは要確認。"""
    import importlib.util, gapi
    try:
        path = gapi.factory_path().parent / "rules" / "deck-build" / "checks.py"
    except SystemExit:  # factory.toml がない
        return 0
    if not path.is_file():
        return 0
    spec = importlib.util.spec_from_file_location("workspace_checks", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not (fn := getattr(mod, kind, None)):
        return 0
    before = {k for k, v in r.hits.items() if v}
    fn(data, r)
    new = [k for k, v in r.hits.items() if v and k not in before]
    hard = [k for k in new if k in getattr(mod, "HARD", ())]
    r.extra_hard |= set(hard)
    n = r.show(hard, f"要修正（ワークスペースの点検 {path}）")
    r.show([k for k in new if k not in hard], "要確認（ワークスペースの点検）")
    return n


def log_path():
    """要確認の記録。ワークスペース（factory.toml のあるフォルダ）の .factory/ に置く（プラグインのフォルダは入れ直すと消える）。
    ponytail: 足すだけで消さない（1 回 1 行）。重くなったら古い行を落とす"""
    import gapi
    return str(gapi.factory_path().parent / ".factory" / "lint_runs.jsonl")


def log_run(r, deck, path=None):
    """要確認を 1 行で残す（--stats が、組み直しても残った指摘を規則ごとに数える。dreaming の 5）。
    資料の文は残さず、場所（p3・段落 12）を除いた指摘のハッシュだけにする（ページが増えても同じ指摘と分かる）。"""
    warn = {k: sorted({hashlib.sha1(re.sub(r"^(p\d+|段落 \d+)", "", h).encode()).hexdigest()[:8] for h in v})
            for k, v in r.hits.items() if v and k not in HARD_NAMES}
    if os.environ.get("FACTORY_VERIFY"):  # factory-kaizen の検証で組んだ仮の資料は数えない
        return
    path = path or log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deck": deck, "warn": warn}, ensure_ascii=False) + "\n")


def stats(path=None):
    """規則ごとに、出た指摘の数と、その資料の最後の確認まで残った数。残ったものが、残す理由のある指摘か外れかは、ここからは分からない。"""
    runs, path = defaultdict(list), path or log_path()
    for line in open(path, encoding="utf-8") if os.path.exists(path) else []:
        d = json.loads(line)
        runs[d["deck"]].append(d["warn"])
    rows = defaultdict(lambda: [set(), 0, 0])  # 資料、出た、残った
    for deck, ws in runs.items():
        for k in {k for w in ws for k in w}:
            seen = {h for w in ws for h in w.get(k, [])}
            rows[k][0].add(deck)
            rows[k][1] += len(seen)
            rows[k][2] += len(seen & set(ws[-1].get(k, [])))
    out = sorted(((k, len(a), b, c) for k, (a, b, c) in rows.items()), key=lambda x: (-x[3] / x[2], -x[2]))
    print(f"確認 {sum(map(len, runs.values()))} 回・資料 {len(runs)} 本\n規則\t資料\t出た\t残った（最後の確認まで）")
    for x in out:
        print("\t".join(map(str, x)))
    return out


def selftest():
    globals()["theme_pages"] = lambda: []  # 回す場所の factory.toml のテーマ（用紙）に左右されない
    ws_checks, globals()["workspace_checks"] = workspace_checks, lambda *a: 0  # 回す場所のワークスペースの checks.py にも左右されない（最後に戻して試す）
    real_segment, globals()["segment"] = segment, lambda ts: {t: set(range(len(t) + 1)) for t in ts}  # uv と BudouX を呼ばない（どこでも文節の切れ目とみなす）
    import contextlib, io
    assert abs(contrast("FFFFFF", "000000") - 21) < 0.01
    assert abs(contrast("7D8E95", "F5F7F8") - 3.16) < 0.02
    assert WARN["和欧間のスペース抜け"].search("2026年") and not WARN["和欧間のスペース抜け"].search("2026 年")
    assert WARN["空疎な言い回し"].search("業務効率化を実現する") and not WARN["空疎な言い回し"].search("実現の条件")
    assert HARD["絵文字"].search("完了 ✅") and not HARD["絵文字"].search("○ × △")
    assert em_width("あいう") == 3 and abs(em_width("a b") - 1.40) < 1e-9 and em_width("D→") == 1.69
    assert HARD["長いダッシュ"].search("— 売っていない") and not HARD["長いダッシュ"].search("—")
    assert not WARN["和欧間のスペース抜け"].search("Apps・Lakebase")
    assert WARN["英語の大文字ラベル"].search("KEY POINTS") and not WARN["英語の大文字ラベル"].search("F9F7F4")  # 色の値はラベルでない
    assert HARD["差し替えの仮ページ"].search("差し替え：紹介資料 p.10") and "差し替えの仮ページ" not in WARN
    rgb = lambda h: {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}
    scheme = [{"type": k, "color": rgb(v)} for k, v in (("DARK1", "1B3139"), ("LIGHT1", "F9F7F4"), ("ACCENT1", "303F47"), ("ACCENT2", "00A972"), ("ACCENT4", "FFAB00"), ("ACCENT5", "618794"))]
    box = lambda x, y, w, h: {"size": {"width": {"magnitude": w * EMU, "unit": "EMU"}, "height": {"magnitude": h * EMU, "unit": "EMU"}},
                              "transform": {"scaleX": 1, "scaleY": 1, "translateX": x * EMU, "translateY": y * EMU, "unit": "EMU"}}

    def shape(lines, y=2, w=(120 + 2 * INS) / 72, prefix="", size=12, kind="TEXT_BOX", link=False, font=FONT, color=None, fill=None, x=0, text=None):
        els = []
        for t in (text or [prefix + "あ" * 10] * lines):
            st = {"fontFamily": font, "fontSize": {"magnitude": size, "unit": "PT"}}
            if link:
                st["link"] = {"url": "https://example.com"}
            if color:
                st["foregroundColor"] = {"opaqueColor": color}
            els += [{"paragraphMarker": {"style": {}}}, {"textRun": {"content": t + "\n", "style": st}}]
        sp = {"shapeBackgroundFill": {"solidFill": {"color": fill}}} if fill else {}
        return {"objectId": "e", **box(x, y, w, 4), "shape": {"shapeType": kind, "text": {"textElements": els}, "shapeProperties": sp}}

    def deck(pages, notes="ノートです。"):  # pages は (地の色, [要素]) の並び
        sl = [{"objectId": f"s{k}", "pageElements": els, "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": bgc}}},
               "slideProperties": {"masterObjectId": "m", "notesPage": {"notesProperties": {"speakerNotesObjectId": "n"},
                                                                         "pageElements": [shape(1, text=[notes]) | {"objectId": "n"}] if notes else []}}}
              for k, (bgc, els) in enumerate(pages)]
        return {"title": "t", "masters": [{"objectId": "m", "pageProperties": {"colorScheme": {"colors": scheme}}}], "layouts": [], "slides": sl}

    def run(p, **kw):
        res, out = Report(), io.StringIO()
        with contextlib.redirect_stdout(out):
            hard = lint_slides(p, res, **kw)
        return res, out.getvalue(), hard

    NAVY, OAT = {"themeColor": "DARK1"}, {"rgbColor": rgb("F9F7F4")}
    title = lambda t="見出し": shape(1, y=0.62, size=24, w=12, text=[t])
    # 8 行と 9 行の境目。見出し・フッター・出典・表は数えない
    flat = lambda e: next(flatten([e]))
    _, out, _ = run(deck([(OAT, [title("問い合わせの一次回答の推移"), shape(1, y=Y_LEAD, w=12, text=["一次回答が 3 割減った"])])]))
    assert "p1  問い合わせの一次回答の推移\n      一次回答が 3 割減った\n" in out  # 名詞句の見出しのページは、リードも一覧に出す
    assert body_lines(*flat(shape(8))) == 8 and body_lines(*flat(shape(9))) == 9
    t = shape(9)
    assert body_lines(t, flat(t)[1], t) is None and body_lines(*flat(shape(9, y=0.62))) is None
    assert body_lines(*flat(shape(9, y=7.08))) is None and body_lines(*flat(shape(9, prefix="出典："))) is None
    assert body_lines({"objectId": "t", **box(0, 2, 2, 2), "table": {}}, [0, 2 * EMU, 2 * EMU, 2 * EMU]) is None
    assert body_lines(*flat(shape(1, text=["あ" * 90]))) == 9 and body_lines(*flat(shape(1, size=24))) == 2  # 1 段落の折り返しも数える
    assert src_without_link(shape(1, prefix="出典：")["shape"]) and not src_without_link(shape(1)["shape"]) and not src_without_link(shape(1, prefix="出典：", link=True)["shape"])
    for lines in (8, 9):
        res, _, hard = run(deck([(NAVY, [title(), shape(lines), shape(9, y=7.08), shape(9, prefix="出典：")])]))
        assert hard == 0 and len(res.hits[BODY_LINES]) == (1 if lines == 9 else 0)
    # 文字の下限: 塗りのない文字は 11pt 未満で止め、塗りのある図形の中の文字は 9pt まで通す（8pt は止める）
    for size, fill, n in ((9, None, 1), (9, NAVY, 0), (8, NAVY, 1)):
        res, _, _ = run(deck([(NAVY, [title(), shape(1, y=3, size=size, fill=fill)])]))
        assert len(res.hits[f"{MIN_PT}pt 未満の文字"]) == n, (size, fill)
    # 角丸の札（背景と文字の枠が 1 グループ）は 9pt まで通す。カードの本文・背景の四角の上の出典・中心だけに塗りがある枠は、下に塗りがあっても 11pt で止める
    under = lambda oid, x, y, w, h: {"objectId": oid, **box(x, y, w, h), "shape": {"shapeType": "RECTANGLE", "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": OAT}}}}}
    group = lambda oid, *ch: {"objectId": oid, "elementGroup": {"children": list(ch)}}
    for els, n in (([group("g", group("bgs", under("bg", 0, 3, 2, 4)), shape(1, y=3, size=9) | {"objectId": "lb"})], 0),
                   ([group("g", under("bg", 0, 3, 2, 4), shape(1, y=3, size=8) | {"objectId": "lb"})], 1),
                   ([under("bg", 0, 2.8, 3, 4.4), shape(1, y=3, size=9) | {"objectId": "lb"}], 1),
                   ([under("bg", 0, 0, 13.33, 7.5), shape(1, y=3, size=9, prefix="出典：") | {"objectId": "lb"}], 1),
                   ([under("bg", 0.8, 4.9, 0.2, 0.2), shape(1, y=3, size=9) | {"objectId": "lb"}], 1)):
        res, _, _ = run(deck([(OAT, [title(), *els])]))
        assert len(res.hits[f"{MIN_PT}pt 未満の文字"]) == n, els
    # 話す資料の字数: 本文 120 字は出さず、130 字は出す。--talk がなければ出さない
    for lines, talk in ((12, True), (13, True), (13, False)):
        res, out, _ = run(deck([(NAVY, [title(), shape(lines), shape(9, y=7.08), shape(9, prefix="出典：")])]), talk=talk)
        assert f"p1 {lines * 10}" in out and len(res.hits[TALK]) == (1 if talk and lines == 13 else 0)
    # 見出しの位置の文字を、本文の大きな数字より先に見出しとみなす
    _, out, _ = run(deck([(NAVY, [title("見出しあ"), shape(1, y=3, size=48, w=10, text=["数字" + "あ" * 10])])]))
    assert "p1  見出しあ" in out and "p1 12" in out
    # 章の扉: 13 枚で扉がなければ出す。扉の間が 1 枚だけなら出す。表紙（1 枚目）は扉に数えない
    dk = lambda darks, n: run(deck([(NAVY if k in darks else OAT, []) for k in range(1, n + 1)]))[0]
    assert len(dk({1}, 13).hits[NO_DIVIDER]) == 1 and not dk({1, 4}, 13).hits[NO_DIVIDER] and not dk({1}, 12).hits[NO_DIVIDER]
    assert len(dk({1, 3, 5, 9}, 13).hits[SHORT_CH]) == 1 and not dk({1, 3, 6, 9}, 13).hits[SHORT_CH]
    assert len(dk(set(), 3).hits[NO_COVER]) == 1 and not dk({1}, 3).hits[NO_COVER]
    assert len(dk({1, 5, 12}, 13).hits[SHORT_CH]) == 1 and len(dk({1, 5, 6}, 9).hits[SHORT_CH]) == 1  # 最後の章が 1 枚、扉が続く
    marked = {"layouts": [{"objectId": "L", "pageElements": [{"description": "ai-deck-factory layout=cover:2 w=7.08 tone=light"}]}]}
    assert is_dark(marked, {"slideProperties": {"layoutObjectId": "L"}}, {}) and not is_dark(marked, {"slideProperties": {"layoutObjectId": "B"}}, {})  # 白地の表紙のパターンも表紙
    # 本文の地が暗いテーマ（DARK1 と LIGHT1 が同じ黒）でも、扉は地の色の値でなく枠（NAVY = DARK1）で見分ける
    black = [{"type": k, "color": rgb("000000")} for k in ("DARK1", "LIGHT1")]
    dark_deck = lambda darks, n: (lambda p: (p["masters"][0]["pageProperties"]["colorScheme"].update(colors=black), run(p)[0])[1])(
        deck([(NAVY if k in darks else {"themeColor": "LIGHT1"}, [title("問い合わせが、3 割減っている")]) for k in range(1, n + 1)]))
    assert len(dark_deck({1}, 13).hits[NO_DIVIDER]) == 1 and not dark_deck({1}, 3).hits[NO_COVER] and len(dark_deck(set(), 3).hits[NO_COVER]) == 1
    assert len(dark_deck({1, 5, 6}, 9).hits[SHORT_CH]) == 1 and dark_deck({1}, 5).hits[HEAD_CLAIMS]  # 本文のページを扉と取り違えない
    # 横の矢印: 2 つの箱（上端 1 in・高さ 0.46 in）の間。ずれが 0.02 in を超えたら出す
    rect = lambda x, w: [x * EMU, EMU, w * EMU, 0.46 * EMU]
    assert not off_center_arrows([[1.58 * EMU, 1.23 * EMU, 1.34 * EMU, 0]], [rect(0, 1.5), rect(3, 2)])
    assert len(off_center_arrows([[1.58 * EMU, 1.31 * EMU, 1.34 * EMU, 0]], [rect(0, 1.5), rect(3, 2)])) == 1
    cb = lambda x, y, w, h: [x * EMU, y * EMU, w * EMU, h * EMU]
    assert not column_shift([cb(0, 2, 3, 1), cb(4, 2, 3, 1)], [])  # そろっている
    assert not column_shift([cb(0, 2.1, 3, 0.8), cb(0.1, 2, 2.8, 1), cb(4, 2.1, 3, 0.8), cb(4.1, 2, 2.8, 1)], [])  # 角丸のカードの横長・縦長の四角
    assert len(column_shift([cb(0, 2.16, 3, 2.8), cb(4, 1.78, 3, 2.85)], [])) == 2  # [lint-020] 上端 0.38・下端 0.33 ずれる
    assert not column_shift([cb(0, 2, 3, 1), cb(4, 2.3, 3, 1)], [cb(3.5, 1.5, 4, 3)])  # 右は入れ子なので見ない
    vl = lambda n: [[k * EMU, EMU, 0, 4 * EMU] for k in range(n)]
    assert line_grid(vl(3)) == [3] and not line_grid(vl(2))  # 格子の縦線は 3 本から
    def on_red(text, size, bold, y):  # 赤の塗りに白の文字（3.62:1）
        e = shape(1, size=size, text=[text], color={"rgbColor": rgb("FFFFFF")}, fill={"rgbColor": rgb("FF3621")}, y=y)
        e["shape"]["text"]["textElements"][1]["textRun"]["style"]["bold"] = bold
        return e
    _, out, _ = run(deck([(OAT, [title(), on_red("太字11", 11, True, 2), on_red("細字11", 11, False, 3), on_red("太字9", 9, True, 4)])]))
    low = out[out.index("== コントラスト"):]
    assert "FFFFFF / FF3621  3.62（基準 4.5）  2 か所" in low and "太字11" not in low  # 11pt 以上の太字は 3:1（visual-039）。細字と 9pt の太字は 4.5:1
    # 書体、ノート、テーマの色のコントラスト（ACCENT5 の 618794 は Oat の上で 3.64:1）
    res, _, hard = run(deck([(NAVY, [title(), shape(1, font="Arial")])]))
    assert hard == 1 and len(res.hits[FONT_NG]) == 1
    res, _, hard = run(deck([(NAVY, [title(), shape(1, font=MONO, text=["import mlflow"])])]))
    assert hard == 0  # 英数字だけの等幅は通す
    res, _, hard = run(deck([(NAVY, [title(), shape(1, font=MONO, text=["# 名前"])])]))
    assert hard == 1 and len(res.hits[MONO_NG]) == 1
    import slides  # テーマの mono（マスターの代替テキストのテーマの目印の値）と比べる
    themed = deck([(NAVY, [title(), shape(1, font="IBM Plex Mono", text=["# 名前"]), shape(1, font=MONO_DEFAULT, text=["x = 1"])])])
    themed["masters"][0]["pageElements"] = [{"description": 'ai-deck-factory theme=code {"mono":"IBM Plex Mono"}', "shape": {"placeholder": {"type": "SLIDE_NUMBER"}}}]
    res, _, hard = run(themed)
    assert len(res.hits[MONO_NG]) == 1 and "IBM Plex Mono" in res.hits[MONO_NG][0] and len(res.hits[FONT_NG]) == 1 and MONO == "IBM Plex Mono"
    res, _, hard = run(deck([(NAVY, [title(), shape(1, font=MONO_DEFAULT, text=["# 名前"])])]))
    assert len(res.hits[MONO_NG]) == 1 and MONO == MONO_DEFAULT  # テーマの名前のないデッキは既定に戻す
    dm = deck([(NAVY, [shape(1, y=0.62, size=24, w=12, text=["見出し"], font="DM Sans"), shape(1, font="DM Sans")])])  # template.py が DM Sans で組んだテーマのデッキ
    dm["masters"][0]["pageElements"] = [{"description": "ai-deck-factory theme=dm", "shape": {"placeholder": {"type": "SLIDE_NUMBER"}, "text": {"textElements": [{"textRun": {"style": {"fontFamily": "DM Sans"}}}]}}}]
    res, _, hard = run(dm)
    assert not res.hits[FONT_NG] and slides.TEXT_EM is slides.DM_SANS_EM  # 書体はマスターの DM Sans と比べ、字幅も DM Sans で見込む
    run(deck([(NAVY, [title()])]))
    assert slides.TEXT_EM is slides.ASCII_EM  # 次のデッキは、その書体の字幅に戻す
    copyright_text = "© 2026 Databricks, Inc. All rights reserved.｜Internal Only"
    for y, size, text, expected in ((7.08, 9, copyright_text, 0), (7.08, 8, copyright_text, 1),
                                    (2, 9, copyright_text, 1), (7.08, 9, "資料名", 1)):
        assert run(deck([(NAVY, [title(), shape(1, y=y, size=size, text=[text])])]))[2] == expected  # 9pt の例外は著作権フッターだけ
    assert len(run(deck([(NAVY, [title()])], notes=None))[0].hits[NO_NOTES]) == 1
    oat = rgb("F9F7F4")
    assert len(run(deck([(NAVY, [title()]), (oat, [title(), shape(1, size=36, text=["55"])])]))[0].hits[NUM_NO_UNIT]) == 1
    assert not run(deck([(NAVY, [title()]), (oat, [title(), shape(1, size=36, text=["55 モデル"])])]))[0].hits[NUM_NO_UNIT]
    # 手の改行のあとの行頭の全角の開き括弧（visual.md の 2）。括弧の後で改行したものは出さない
    assert len(run(deck([(NAVY, [title()]), (oat, [title(), shape(1, text=["表と同じ権限\v（Unity Catalog）"])])]))[0].hits[OPEN_HEAD]) == 1
    assert not run(deck([(NAVY, [title()]), (oat, [title(), shape(1, text=["表と同じ権限（Unity\vCatalog）"])])]))[0].hits[OPEN_HEAD]
    # 自動の折り返しが文節の途中に入る見込み（visual-013）。数え方は slides.py の wrap_lines と同じ。文節は BudouX の結果を差し替えて試す
    pa = lambda *runs: ({}, [(c, {"fontSize": {"magnitude": sz}} if sz else {}) for c, sz in runs])
    t = "データを見る人と評価者がいる"
    assert wrap_breaks(pa((t, 12)), 120) == [10] and wrap_breaks(pa((t, 12)), 200) == []  # 12pt で 10 字の幅。11 字目の「者」が次の行の頭
    assert wrap_breaks(pa(("あいうえおかきくけ\vこさしすせそたちつてとな", 12)), 120) == [20]  # 手の改行で数え直す
    assert wrap_breaks(pa(("大きい", 24), ("あいうえおか", 12)), 120) == [7]  # run ごとの大きさ。24pt の 3 字で 6 字分
    assert wrap_breaks(pa(("あいう Databricks", 12)), 90) == [4] and wrap_breaks(pa(("あ abcdefghijklmnopqrstu", 12)), 60) == [9, 18]  # 英数字の語はまとめて送り、1 行より長い語は字で折る
    from slides import wrap_lines
    assert all(len(wrap_breaks(pa((x, 12)), 60)) + 1 == wrap_lines(x, 60 / 72, 12)[0] for x in (t, "あいう Databricks の", "あ abcdefghijklmnopqrstu"))  # 組む側と同じ行の数（行末の空白で折れる文は、空白の後を数えないので除く）
    assert wrap_breaks(pa((t, None)), 120) == []  # 大きさの分からない run（プレースホルダーの継承）は見ない
    cuts = {t: {4, 6, 8, 12, 14}, "あいう Databricks": {4, 15}}  # 「データを／見る／人と／評価者が／いる」
    globals()["segment"] = lambda ts: {x: cuts.get(x, set()) for x in ts}
    assert len(mid_phrase([("p1", t, [10])])) == 1 and "評価／者がいる" in mid_phrase([("p1", t, [10])])[0]
    assert mid_phrase([("p1", t, [8])]) == [] and mid_phrase([("p1", "あいう Databricks", [4])]) == []  # 文節の頭と、空白の後
    assert mid_phrase([("p1", "見込みの位置、で", [6])]) == []  # 行頭に来ない字の前は、禁則で前の行に戻る
    wrapped = lambda **kw: shape(1, text=[t], **kw)  # 幅は 12pt で 10 字
    res, _, hard = run(deck([(NAVY, [title()]), (oat, [title(), wrapped()])]))
    assert len(res.hits[PHRASE_BREAK]) == 1 and hard == 0
    assert not run(deck([(NAVY, [title()]), (oat, [title(), wrapped(y=7.08)])]))[0].hits[PHRASE_BREAK]  # フッター
    assert not run(deck([(NAVY, [title()]), (oat, [title(), wrapped(font=MONO_DEFAULT)])]))[0].hits[PHRASE_BREAK]  # 等幅だけの段落
    cell = {"objectId": "t", **box(0, 2, (120 + 2 * INS) / 72, 2), "table": {"tableRows": [{"tableCells": [{"text": wrapped()["shape"]["text"]}]}]}}
    assert not run(deck([(NAVY, [title()]), (oat, [title(), cell])]))[0].hits[PHRASE_BREAK]  # 表のセル
    globals()["segment"] = lambda ts: None
    res2, out, hard2 = run(deck([(NAVY, [title()]), (oat, [title(), wrapped()])]))
    assert not res2.hits[PHRASE_BREAK] and "は数えていない" in out and hard2 == hard
    assert {k: v for k, v in res2.hits.items() if v} == {k: v for k, v in res.hits.items() if v and k != PHRASE_BREAK}  # ほかの指摘は変わらない
    import types
    sp_run = subprocess.run
    try:
        for got in ([0, json.dumps([["データを", "見る"]])], [1, json.dumps([["データを見る"]])], [0, json.dumps([["データ"]])], [0, "["], [0, json.dumps([[1]])], OSError()):
            subprocess.run = lambda *a, **k: (_ for _ in ()).throw(got) if isinstance(got, Exception) else types.SimpleNamespace(returncode=got[0], stdout=got[1])
            assert real_segment(["データを見る"]) == ({"データを見る": {4, 6}} if got == [0, json.dumps([["データを", "見る"]])] else None)  # 起動の失敗・形の合わない結果は数えない
    finally:
        subprocess.run = sp_run
    globals()["segment"] = lambda ts: {t: set(range(len(t) + 1)) for t in ts}
    _, out, _ = run(deck([(NAVY, [title()]), (OAT, [title(), shape(1, color={"themeColor": "ACCENT5"})])]))
    assert "618794 / F9F7F4  3.64" in out
    _, out, _ = run(deck([(OAT, [shape(1, y=2, w=4, fill={"themeColor": "DARK1"}, text=[""]), shape(1, y=2.5, color={"themeColor": "ACCENT5"})])]))
    assert "618794 / 1B3139" in out  # 下に重なった箱の塗りを地にする
    assert solid({"solidFill": {"color": NAVY}, "propertyState": "NOT_RENDERED"}, {"DARK1": "1B3139"}) is None
    # 線と格子は JSON の道筋で: 横線（向きを反転したもの、高さ 1 EMU のもの）と、細い四角の縦線。
    # 線は API の返す形にする: 大きさは 3000000 EMU の正方形で、長さは scaleX・scaleY。0 の値は省かれる（w は in、h は EMU）
    def line(x, y, w, h, sx=1, oid="l"):
        t = {"translateX": x * EMU, "translateY": y * EMU, "unit": "EMU"}
        t |= {"scaleX": sx * w * EMU / 3e6} if w else {}
        t |= {"scaleY": h / 3e6} if h else {}
        return {"objectId": oid, "line": {}, "size": {"width": {"magnitude": 3e6, "unit": "EMU"}, "height": {"magnitude": 3e6, "unit": "EMU"}}, "transform": t}
    two = [{"objectId": "a", "shape": {"shapeType": "RECTANGLE", "shapeProperties": {}}, **box(0, 1, 1.5, 0.46)},
           {"objectId": "b", "shape": {"shapeType": "RECTANGLE", "shapeProperties": {}}, **box(3, 1, 2, 0.46)}]
    for ln, hit in ((line(1.58, 1.23, 1.34, 0), 0), (line(2.92, 1.31, 1.34, 1, sx=-1), 1), (line(1.58, 1.31, 1.34, 1), 1)):
        assert len(run(deck([(NAVY, two + [ln])]))[0].hits[ARROW_MID]) == hit
    assert not run(deck([(NAVY, two + [line(1.58, 1.1, 1.34, 0, oid="m"), line(1.58, 1.36, 1.34, 0, oid="n")])]))[0].hits[ARROW_MID]  # 同じ 2 つの箱の間の 2 本はずらすのが意図
    thin = [{"objectId": f"v{k}", "shape": {"shapeType": "RECTANGLE", "shapeProperties": {}}, **box(k, 1, 0.03, 4)} for k in range(3)]
    assert len(run(deck([(NAVY, thin)]))[0].hits[LINE_GRID]) == 1  # 細い四角の格子も見る
    dashed = lambda kind: [{"objectId": "d", "shape": {"shapeType": kind, "shapeProperties": {"outline": {"dashStyle": "DASH"}}}, **box(1, 1, 3, 2)}]
    # 濃紺の箱の上の NAVY_BLOCK: 本文ページでは出し、淡色なら出さない。扉（濃紺の地）では出さない
    blk = lambda pg_bg, h: len(run(deck([(pg_bg, [title(), shape(1, y=2, w=6, text=[""], fill=NAVY), shape(1, y=2.5, w=3, text=["群"], fill={"rgbColor": rgb(h)})])]))[0].hits[BLOCK_ON_NAVY])
    assert blk(OAT, "303F47") == 1 and blk(OAT, "EEEDE9") == 0 and blk(NAVY, "303F47") == 0
    # 濃紺の地のコード: 等幅でなければ出す。等幅なら出さない。地の文（和文で始まる行）は見ない
    code = lambda t, font: len(run(deck([(OAT, [title(), shape(1, text=[t], font=font, fill=NAVY)])]))[0].hits[CODE_NOT_MONO])
    assert code("SELECT 1;", FONT) == 1 and code("SELECT 1;", MONO) == 0 and code("Lakebase が担当する", FONT) == 0 and code("databricks.com/product/pricing", FONT) == 0
    # 提供ステージの札: Public Preview を黄で塗ったら出し、淡い緑なら出さない。Beta は黄
    stg = lambda t, h: len(run(deck([(NAVY, [title(), shape(1, text=[t], fill={"rgbColor": rgb(h)})])]))[0].hits[STAGE_NG])
    assert stg("Public Preview", "FFAB00") == 1 and stg("Public Preview", "99DDC7") == 0 and stg("Beta", "FFAB00") == 0 and stg("GA", "FFAB00") == 1
    assert len(run(deck([(NAVY, dashed("ROUND_RECTANGLE"))]))[0].hits[DASH_ROUND]) == 1 and not run(deck([(NAVY, dashed("ARC"))]))[0].hits[DASH_ROUND]  # 標準の角丸の点線だけ
    vert = [line(k, 1, 0, 4 * EMU, oid=f"w{k}") for k in range(3)]
    grouped = {"objectId": "g", "elementGroup": {"children": vert}, "transform": {"scaleX": 1, "scaleY": 1, "unit": "EMU"}}
    assert len(run(deck([(NAVY, vert)]))[0].hits[LINE_GRID]) == 1 and not run(deck([(NAVY, [grouped])]))[0].hits[LINE_GRID]  # 角丸の囲みの辺は格子でない
    arrows = [v | {"line": {"lineProperties": {"endArrow": "FILL_ARROW"}}} for v in vert]
    assert not run(deck([(NAVY, arrows)]))[0].hits[LINE_GRID]  # 並んだ矢印も格子でない
    # フッターの Internal Only は 1 件。見出しとリードが 2 行
    foot = lambda: shape(1, y=7.08, w=9, text=["資料名｜Internal Only"])
    res = run(deck([(NAVY, [title(), foot()]), (OAT, [title(), foot()])]))[0]
    assert len(res.hits["社外秘の表示"]) == 1 and "2 ページ" in res.hits["社外秘の表示"][0]
    res = run(deck([(NAVY, [title("あ" * 40), shape(1, y=1.2, w=12, size=12, text=["い" * 80])])]))[0]
    assert len(res.hits[TWO_LINES]) == 2
    # 見出しの句点と、1 つの枠の箇条書きの句点の混在（content.md の 6）。箇条書きでない段落は数えない
    def bulleted(ts):
        e = shape(1, text=ts)
        for te in e["shape"]["text"]["textElements"]:
            if "paragraphMarker" in te:
                te["paragraphMarker"]["bullet"] = {"listId": "b"}
        return e
    hp = lambda els: (lambda r: (len(r.hits[HEAD_PERIOD]), len(r.hits[BULLET_PERIOD])))(run(deck([(NAVY, [title()]), (OAT, els)]))[0])
    assert hp([title("問い合わせが減っている。")]) == (1, 0) and hp([title("問い合わせが減っている")]) == (0, 0)
    assert hp([title(), bulleted(["夜間に集計する。", "朝に見る"])]) == (0, 1) and hp([title(), bulleted(["夜間の集計", "朝の確認"])]) == (0, 0)
    assert hp([title(), shape(1, text=["夜間に集計する。", "朝に見る"])]) == (0, 0)
    hd = lambda t: run(deck([(NAVY, [title()]), (OAT, [title(t)])]))[2]
    assert hd("問い合わせが減っている。") > hd("問い合わせが減っている") == 0 and hd("減っている。理由は 2 つ") > 0  # 見出しの句点は文の途中でも要修正
    pol = lambda t: bool(run(deck([(NAVY, [title()]), (OAT, [title(t)])]))[0].hits[HEAD_POLITE])
    assert pol("移行の順番をご確認ください") and pol("夜間の集計を移します") and not pol("夜間の集計の移し先")
    cl = lambda ts: bool(run(deck([(NAVY, [title("言い切りの扉、多くなる")])] + [(OAT, [title(t)]) for t in ts]))[0].hits[HEAD_CLAIMS])
    assert cl(["問い合わせが、3 割減っている"] * 4) and not cl(["問い合わせが、3 割減っている"] * 3)  # 扉（濃紺の地）は数えない
    assert not cl(["問い合わせの推移"] * 4 + ["移す理由、3 つ"] * 2)  # 名詞句と「N つ」で終わるものは数えない
    # 空き: 1 行の本文だけなら下が空く。塗りの箱の中に 1 行なら箱の中が空く。中身で埋まった箱は出さない。結論バンドは本文の 3 分の 1 まで
    fill = lambda c: {"shapeBackgroundFill": {"solidFill": {"color": c}}}
    card = lambda y, h: {"objectId": "c", "shape": {"shapeType": "RECTANGLE", "shapeProperties": fill({"rgbColor": rgb("FFFFFF")})}, **box(0.6, y, 6, h)}
    hits = lambda els: (lambda r: (len(r.hits[EMPTY_BELOW]), len(r.hits[EMPTY_BOX])))(run(deck([(OAT, [title()] + els)]))[0])
    assert hits([shape(1)]) == (1, 0) and hits([card(2, 4), shape(1, y=2.1)]) == (0, 1) and hits([card(2, 4.4), shape(20)]) == (0, 0)
    assert hits([shape(1, y=3.9)]) == (0, 0)  # 上下の中央に置いた 1 行（上にも同じだけ空いている）は出さない
    # 塗りの箱の端と文字の間: 枠の内側の余白（0.1 in）だけなら 14pt の 1 字に足りない。中央寄せと、1 字分を空けた文字は出さない
    pads = lambda els: len(run(deck([(OAT, [title()] + els)]))[0].hits[PAD_NG])
    centered = shape(1, x=0.6, y=2.1, size=14)
    centered["shape"]["text"]["textElements"][0]["paragraphMarker"]["style"]["alignment"] = "CENTER"
    assert pads([card(2, 4), shape(1, x=0.6, y=2.1, size=14)]) == 1 and pads([card(2, 4), shape(1, x=0.7, y=2.1, size=14)]) == 0
    assert pads([card(2, 4), centered]) == 0 and pads([shape(1, x=1, w=4, size=14, fill={"rgbColor": rgb("EEEDE9")}, text=["札"])]) == 1
    stat = shape(1, x=0.8, y=2.1, size=12, text=["97%", "説明"])  # 40pt の数字と 12pt の説明。0.3 in 空けていれば、12pt の 1 字で足りる
    stat["shape"]["text"]["textElements"][1]["textRun"]["style"]["fontSize"]["magnitude"] = 40
    assert pads([card(2, 4), stat]) == 0
    frame = {"objectId": "f", "shape": {"shapeType": "RECTANGLE", "shapeProperties": {}}, **box(0.6, 2, 6, 4)}  # 角丸のカードを組む、文字のない枠
    assert hits([card(2, 4), frame, shape(1, y=2.1)]) == (0, 1)  # [lint-021] 文字のない部品は中身に数えない
    assert hits([card(3, 3) | {"title": BAR_MARK}, shape(1, y=3.1, text=["260 百万円/月"])]) == (0, 0) and hits([card(3, 3), shape(1, y=3.1, text=["98 %"])]) == (0, 1)  # 棒（代替テキストの印）だけは見ない
    # 本文の中ほどの穴: 1 行の文字が 2 つ、2 in 離れていれば出す。近ければ出さない
    holes = lambda els: len(run(deck([(OAT, [title()] + els)]))[0].hits[EMPTY_HOLE])
    assert holes([shape(1, y=2), shape(1, y=4.5)]) == 1 and holes([shape(1, y=2), shape(1, y=2.6)]) == 0
    # コードの箱（等幅）: `source:` を出典の行、SELECT を大文字のラベル、長いコードを本文の行数に数えない
    mono = lambda t, font: run(deck([(OAT, [title(), shape(1, y=2, font=font, text=t)])]))[0]
    assert len(mono(["source: samples.tpch.orders"], MONO).hits[NO_LINK]) == 0 and len(mono(["source: samples.tpch.orders"], FONT).hits[NO_LINK]) == 1
    assert len(mono(["SELECT"], MONO).hits["英語の大文字ラベル"]) == 0 and len(mono(["SELECT"], FONT).hits["英語の大文字ラベル"]) == 1
    assert len(mono(["x = 1"] * 10, MONO).hits[BODY_LINES]) == 0 and len(mono(["あ"] * 10, FONT).hits[BODY_LINES]) == 1
    band = {"objectId": "b", "shape": {"shapeType": "RECTANGLE", "shapeProperties": fill(NAVY)}, **box(0.6, 5.88, 12.13, 0.72)}
    assert len(run(deck([(OAT, [band])] * 3))[0].hits[MANY_BANDS]) == 1 and not run(deck([(OAT, [band]), (OAT, []), (OAT, [])]))[0].hits[MANY_BANDS]
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
    globals()["theme_pages"] = lambda: [(612, 792)]  # factory.toml の [docs.themes] に Letter のテーマがあるとき
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
    # 記録と集計: ページがずれても同じ指摘は同じもの。最後の確認で消えたものは残ったに数えない。要修正は記録しない
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        log, a, b = os.path.join(tmp, "runs.jsonl"), Report(), Report()
        a.hits["あおり"] += ["p3: 「このままでは」", "p5: 「乗り遅れ」"]
        a.hits["絵文字"] += ["p2: 「✅」"]
        b.hits["あおり"] += ["p4: 「このままでは」"]
        log_run(a, "d1", log), log_run(b, "d1", log), log_run(b, "d2", log)
        with contextlib.redirect_stdout(io.StringIO()):
            assert stats(log) == [("あおり", 2, 3, 2)]
    globals()["workspace_checks"] = ws_checks
    import gapi, tempfile  # ワークスペースの点検: HARD の名前だけ要修正になる
    from pathlib import Path
    with tempfile.TemporaryDirectory() as ws, contextlib.chdir(ws), contextlib.redirect_stdout(io.StringIO()):
        Path(ws, "factory.toml").write_text("")
        Path(ws, "rules", "deck-build").mkdir(parents=True)
        Path(ws, "rules", "deck-build", "checks.py").write_text(
            'HARD = {"禁止の語"}\ndef slides(p, r):\n    r.hits["禁止の語"].append("p1")\n    r.hits["気になる語"].append("p2")\n')
        gapi.find_factory.cache_clear()
        r = Report()
        assert workspace_checks("slides", {}, r) == 1 and r.hits["気になる語"] and workspace_checks("doc", {}, Report()) == 0
    gapi.find_factory.cache_clear()
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if a == ["--stats"]:
        stats()
        sys.exit(0)
    path = [x for x in a if x != "--talk"][0]
    if "documentId" in (p := json.load(open(path, encoding="utf-8"))):
        n = lint_gdoc(p, Report())
    else:
        n = lint_slides(p, Report(), "差し替え用" in p.get("title", ""), "--talk" in a)
    sys.exit(1 if n else 0)
