#!/usr/bin/env python3
"""Google Docs を Docs API で直接組み、確かめる（2026-10-09 に docx から切り替えた。組み方と落とし穴は ../SKILL.md）。
資料ごとの build/doc.md（markdown）が中身の正本。頭の front matter に名前・テーマ・テンプレートを書き、本文は markdown で書く（書き方は from_md）。
markdown で内容を詰め、テンプレートとともに API で組み、直しを繰り返す（doc.py の make(d) から移した）。
usage（資料の build/ で。doc.md は今いるフォルダのもの）:
  docs.py themes   テーマ（既定とワークスペースの themes/docs/<名前>.json）の名前と説明。資料ごとに選ぶ（docs-build の SKILL.md の 1.2。テーマのファイルの書き方は ../themes.md）
  docs.py init <テンプレートの名前>   テンプレート（ワークスペースの rules/docs-build/templates/<名前>/doc.md）を写して doc.md を作る
  docs.py new <Drive のフォルダの URL か ID> <Drive 上の名前>   空の Google Doc を作って組む
  docs.py build <URL か ID> [--force]   組み直す（本文をすべて入れ替える。URL は変わらない）。前に組んだあとに画面で直されているか、
                                        未解決のコメントがあれば止まる。直しを doc.md に入れてから --force で組み直す
  docs.py check <URL か ID>   仕上げの確認。JSON・テキスト・lint・ページの画像（Drive が書き出した PDF）・画像でのレイアウトの確かめ（doc_layout.py）、
                              doc.md と組んだ文書の照合、テンプレートとの照合、元のテンプレートとの骨組みの比較を /tmp/docs_<ID の頭 8 字>/ に出す
  docs.py export <URL か ID> <出力.docx か .pdf>   Word か PDF で書き出す（相手が Word を求めたときだけ。納品は Google Docs の URL）
  docs.py --selftest
見た目の決まりは ../visual.md。書体・色・著作権表示はスライドと同じもの（../../deck-practices/scripts/brand.py）を使う。lint は doc_lint.py。"""
import contextlib, difflib, glob, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile
from collections import Counter
from itertools import zip_longest
from pathlib import Path

sys.dont_write_bytecode = True  # build/ と scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deck-practices", "scripts"))  # Google の API・lint の部品・書体と色はスライドと共有する
import doc_lint
import gapi
import textlint
from gapi import DOCS, DRIVE, GDOCS, carry, delete, file_id, folder_id, png, request, run, trash, u16
from brand import BRAND_COPYRIGHT as COPYRIGHT, COPYRIGHT_PT, LOGO, need_brand, FONT, FONT as FONT_DEFAULT, MONO_DEFAULT, MONO_DEFAULT as MONO, theme_font, theme_mono, RULE, TEXT, WHITE, asset  # FONT・MONO はテーマで替わる（load_theme）

# ---- 版面と書体（../visual.md の 1。大きさは pt、版面は mm） ----
# 1 行は全角 40 字まで（jlreq・デジタル庁。../visual.md の 1）。左右 30 mm（Word の和文の既定と同じ）で、本文の幅 150 mm・10.5pt が 40 字
PAGE_MM, MARGIN_TB_MM, MARGIN_LR_MM = (210, 297), 25, 30  # A4 縦
TEXT_MM = PAGE_MM[0] - 2 * MARGIN_LR_MM
NAVY, SUB, PANEL = "1B3139", "5A6F77", "EEEDE9"  # テーマ visual の DARK1・ACCENT5・LIGHT2 の値（visual.md の 1）。Docs にはテーマの色がない
RED_TEXT = "CC2B17"  # ***赤の太字***。テーマ visual の ACCENT3（18pt 未満の赤の文字。白の地で 4.5:1 に届く。../visual.md の 1）
HEAD = NAVY  # 題と見出しの色。この色と TEXT・SUB・RULE・PANEL・RED_TEXT・TABLE_HEAD は、テーマのファイルの colors で替わる（load_theme）
BODY_PT, SMALL_PT, CODE_PT, COVER_PT = 10.5, 9, 9.5, 30  # 本文、図表の題・出典・表の中、コード、表紙の題
# 名前付きスタイル: 大きさ、太字、色、上の空き、下の空き、行間（%）。組むたびに入れ直す（ここを変えれば、組み直した資料すべてに効く）
# 行送りは「字の 1.88 倍 × 行間の %」（Noto Sans JP。2026-10-09 に PDF で測った）。行のアキは、本文は全角近く（100% = 1.88 em）、
# 表の中と図表の題は二分（80% = 1.5 em）、折り返す見出しは三分ほど（75% = 1.41 em）にする（小林敏「行間の選択」。../visual.md の 1）
STYLES = {
    "TITLE": (20, True, NAVY, 0, 4, 75),
    "SUBTITLE": (11, False, SUB, 0, 18, 100),
    "HEADING_1": (15, True, NAVY, 20, 8, 75),
    "HEADING_2": (12.5, True, NAVY, 16, 6, 75),
    "HEADING_3": (11, True, NAVY, 12, 4, 75),
    "NORMAL_TEXT": (BODY_PT, False, TEXT, 0, 6, 100),
}
# テーマ: doc.md の頭に theme: <名前> と書くと、ワークスペースの themes/docs/<名前>.json の版面・名前付きスタイル・色・書体に入れ替える（from_md・load_theme）。
# 会社の文書のテンプレートに合わせるもの（docs-build の ../themes.md の docs-write-010）なので、プラグインには持たない
TABLE_HEAD = (NAVY, WHITE)  # 表の見出しの行の地と文字の色
SCALE = 1  # 図の幅は、本文の幅 150 mm で書く。テーマで本文の幅が変わったら、この比で広げる（表は Doc.table が本文の幅に合わせる）
TIGHT, CODE_LS = 80, 85  # 表の中・図表の題・出典の行間と、コードの行間（%）
# 組んだ直後の本文の指紋を、Drive のファイルの appProperties に残す（gapi.guard が比べる）。revisionId は「24 時間しか有効でなく、内部の理由でも変わる」
# と公式に書いてあり、直していないのに止まるので使わない（ワークスペースの Research/deck_research/log/20261009_en_gdocs_generation.md の 1-2。2 回読んで同じ指紋になることを確かめた）
STAMP = "docs_py_body"
FONTS = "docs_py_fonts"  # 組んだときの本文と等幅の書体（タブで区切る）。check はこれと比べる（今いるフォルダの doc.md が別の文書のものでも、取り違えない）
SRC = "docs_py_src"  # 組んだ doc.md のフォルダ（factory.toml のフォルダからの相対パス）。check が build/ の外で動いても、照合の相手を見つける
P_FIELDS = ("namedStyleType,alignment,indentStart,indentFirstLine,indentEnd,shading,borderTop,borderBottom,borderLeft,borderRight,"
            "spaceAbove,spaceBelow,lineSpacing,keepWithNext")
T_FIELDS = "bold,italic,underline,strikethrough,link,weightedFontFamily,fontSize,foregroundColor,backgroundColor"  # 書かない項目は、名前付きスタイルに戻す
INLINE = re.compile(r"\\([\\*`\[\]])|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^)\s]+)\)")  # スライドの記法（slides.py の MD）のうち、ドキュメントで使うもの
ASCII = re.compile(r"[ -~]+")


def color(h):
    return {"color": {"rgbColor": {k: int(h[i:i + 2], 16) / 255 for k, i in (("red", 0), ("green", 2), ("blue", 4))}}}


def pt(v):
    return {"magnitude": v, "unit": "PT"}


def mm(v):
    return pt(round(v * 72 / 25.4, 2))


def runs(s, st=None):
    """本文の中の書き方（スライドの記法と同じ。slides.py の spec_md）: **太字**、***赤の太字***（RED_TEXT）、[文字](URL)、`コード`、記号そのものは \\* のように \\ を付ける。
    太字・赤の中にはリンクとコードを、リンクの中にはコードを入れられる（***[文字](URL)***）。大きさの {32:…} はスライドだけ。戻り: (文字, 文字の書式) の並び。"""
    st, out, i = st or {}, [], 0

    def add(t, x):
        if not t:
            return
        if out and out[-1][1] == x:  # 同じ書式は 1 つにつなぐ（組んだ文書の JSON と同じ形。canon_json と比べる）
            out[-1] = (out[-1][0] + t, x)
        else:
            out.append((t, x))
    for m in INLINE.finditer(s):
        add(s[i:m.start()], st)
        esc, red, bold, code, label, url = m.groups()
        if esc:
            inner = [(esc, st)]
        elif code is not None:
            inner = [(code, {**st, "code": True})]
        elif red is not None:
            inner = runs(red, {**st, "bold": True, "red": True})
        elif bold is not None:
            inner = runs(bold, {**st, "bold": True})
        else:
            inner = runs(label, {**st, "link": {"url": url}})
        for t, x in inner:
            add(t, x)
        i = m.end()
    add(s[i:], st)
    return out


def font(name, bold=False):
    return {"weightedFontFamily": {"fontFamily": name, "weight": 700 if bold else 400}}


def style_reqs():
    """用紙・余白と、名前付きスタイル（書体・大きさ・色・空き）。見出しは次の段落と同じページに置く（ページの末尾に見出しだけが残らない）。"""
    r = [{"updateDocumentStyle": {"documentStyle": {"pageSize": {"width": mm(PAGE_MM[0]), "height": mm(PAGE_MM[1])},
                                                    **{f"margin{s}": mm(MARGIN_TB_MM) for s in ("Top", "Bottom")},
                                                    **{f"margin{s}": mm(MARGIN_LR_MM) for s in ("Left", "Right")},
                                                    "documentFormat": {"documentMode": "PAGES"}},
                                  "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight,documentFormat"}}]
    for name, (size, bold, c, above, below, spacing) in STYLES.items():
        r.append({"updateNamedStyle": {"namedStyle": {
            "namedStyleType": name,
            "textStyle": {**font(FONT, bold), "fontSize": pt(size), "bold": bold, "foregroundColor": color(c)},
            "paragraphStyle": {"spaceAbove": pt(above), "spaceBelow": pt(below), "lineSpacing": spacing, "keepWithNext": name != "NORMAL_TEXT"}},
            "fields": "namedStyleType,textStyle.weightedFontFamily,textStyle.fontSize,textStyle.bold,textStyle.foregroundColor,"
                      "paragraphStyle.spaceAbove,paragraphStyle.spaceBelow,paragraphStyle.lineSpacing,paragraphStyle.keepWithNext"}})
    return r


class Doc:
    """本文の塊を貯める。Google の API は build まで呼ばない。"""

    def __init__(self, name):
        self.name, self.blocks, self.warnings, self.fig, self.tab = name, [], [], 0, 0
        self.meta = {}  # doc.md の頭（from_md）

    def warn(self, msg):
        msg = f"[塊 {len(self.blocks)}] {msg}"
        self.warnings.append(msg)
        print("警告:", msg, file=sys.stderr)

    def para(self, text, style="NORMAL_TEXT", **opt):
        self.blocks.append(("p", style, runs(text) if isinstance(text, str) else text, opt))

    # ---- 中身 ----
    def title(self, text, sub=None):
        """表紙の代わりの題と副題（日付・宛先など）。ドキュメントは表紙のページを作らない（../visual.md の 2）。"""
        self.para(text, "TITLE")
        if sub:
            self.para(sub, "SUBTITLE")

    def cover(self, lines, left=None, logo=LOGO):
        """表紙のページ（テンプレートに表紙があるとき）。題の行を中央に大きく置き、その下に左の語（顧客のロゴの代わりの社名など）と
        自社のロゴ（factory.toml の [brand] logo。なければ置かない）を並べ、改ページする。表紙を作るかは ../visual.md の 2（資料ごとに聞く）。"""
        if logo and not re.match(r"https?://", logo):
            logo = asset(logo)
        self.blocks.append(("cover", lines, left, logo or None))
        self.pagebreak()

    def h1(self, text):
        self.para(text, "HEADING_1")

    def h2(self, text):
        self.para(text, "HEADING_2")

    def h3(self, text):
        self.para(text, "HEADING_3")

    def p(self, text):
        """本文の 1 段落。**太字**、[文字](URL)、`コード` が書ける。"""
        self.para(text)

    def keep_lead(self):
        """直前の本文の段落（「次のとおりです。」などの前置き）を、次の箇条書き・表と同じページに置く。"""
        if self.blocks and self.blocks[-1][0] == "p" and self.blocks[-1][1] == "NORMAL_TEXT" and not self.blocks[-1][3]:
            self.blocks[-1][3]["keep"] = True

    def bullets(self, items, numbered=False):
        """箇条書き。numbered=True で 1. 2. 3.。頭にタブを 1 つ付けた項目は 2 段目（"\tGenie（推奨）"）。"""
        self.keep_lead()
        self.blocks.append(("list", numbered, [runs(x) for x in items]))

    def code(self, text):
        """コードやコマンド。英数字は等幅の MONO、和文は FONT（MONO に和文の字形はない。visual.md の 2）。"""
        self.blocks.append(("code", text.strip("\n")))

    def quote(self, text):
        """引用（顧客の声など）。左に線を引き、補助の色にする。"""
        self.para(text, quote=True)

    def src(self, text):
        """出典の行（表と図の下）。リンクを付ける（content.md の 6）。「出典: 」がなければ付ける。"""
        if not re.match(r"(出典|Sources?)[：:]", text):
            text = "出典: " + text
        self.para(text, small=True)

    def table(self, rows, caption=None, widths=None):
        """表。rows の 1 行目は見出しの行（濃紺の地に白の太字。ページをまたぐと次のページにも出す）。caption は表の上に「表 N　…」で置く。
        [docs-write-005] widths は列の幅の比（mm で書いてよい）。表は本文の左端から右端まで広げるので、
        合計を本文の幅 TEXT_MM に合わせて伸び縮みさせる。省くと均等。セルの中も **太字**・[リンク](URL) が書ける。"""
        n = max(map(len, rows))
        self.keep_lead()
        if widths and len(widths) != n:
            self.warn(f"表の列の幅 {widths} が、列の数 {n} に合わない。均等にした")
            widths = None
        widths = widths and [round(x * TEXT_MM / sum(widths), 1) for x in widths]
        if caption:
            self.tab += 1
            caption = f"表 {self.tab}　{caption}"
        self.blocks.append(("table", [[runs(c) for c in r] + [[]] * (n - len(r)) for r in rows], caption, widths))

    def image(self, src, caption=None, width=120):
        """図。src は assets/ の中のパス（"gcp/bigquery.png"）か、手元のパス、URL（SVG は png() で PNG にする）。
        width は mm（本文の幅は TEXT_MM = 150 mm）。高さは縦横比のまま。caption は図の下に「図 N　…」で置く。"""
        width = round(width * SCALE, 1)
        if width > TEXT_MM:
            self.warn(f"図の幅 {width} mm が本文の幅 {TEXT_MM} mm を超える。{TEXT_MM} mm にした")
            width = TEXT_MM
        if re.match(r"https?://", src):
            src = png(src) if re.search(r"\.svg($|\?)", src, re.I) else src
        elif not os.path.isfile(src):
            src = asset(src)
        if caption:
            self.fig += 1
            caption = f"図 {self.fig}　{caption}"
        self.blocks.append(("image", src, caption, width))

    def mermaid(self, code, caption=None, width=None):
        """mermaid の図。手元の mermaid-cli で PNG に描いて（mermaid_png）、図として置く。width は image と同じ mm（本文の幅 150 mm で書く）。
        省くと、図の文字が本文と同じ大きさになる幅（本文の幅を超えるなら本文の幅）。縮めて図の文字が 9pt 未満になるときは警告する。"""
        path = mermaid_png(code)
        natural = image_px(path) / MERMAID_SCALE * 25.4 / 96  # 文字を本文の大きさ（mermaid_png の fontSize）で描いたときの幅（mm）
        w = min(width * SCALE if width else natural, TEXT_MM)
        if (got := STYLES["NORMAL_TEXT"][0] * w / natural) < SMALL_PT:
            self.warn(f"mermaid の図を {w:.0f} mm に縮めると、図の文字が {got:.1f}pt になる（9pt 未満）。向きを変える（flowchart LR → TB）か、図を分ける")
        self.image(path, caption, w / SCALE)

    def pagebreak(self):
        self.blocks.append(("break",))


# [docs-write-011] mermaid の図は、手元の mermaid-cli（npx で版を固定して取ってくる）で描く。URL から図を作るサービス（mermaid.ink など）には、図の中身が
# 第三者に渡るので渡さない（../../slides-build/assets/README.md）。色はテーマの colors、書体はテーマの FONT、文字は本文と同じ大きさ。書体は手元に入っているもので描かれる
MERMAID_CLI = "@mermaid-js/mermaid-cli@11.17.0"  # 版を固定する（版が変わると描き方が変わりうる。PNG の指紋に入れる）。手元の mmdc は版が分からないので使わない
MERMAID_SCALE = 3  # 描く倍率（PNG の画素 / CSS の画素）。印刷してもにじまない
MERMAID_DIR = "mermaid"  # 描いた PNG を置く build/ の中のフォルダ。中身・テーマ・倍率が同じなら描き直さない（名前が指紋）


def mermaid_config():
    """mermaid の設定（テーマの色と書体）。base のテーマの色だけを替える（https://mermaid.js.org/config/theming.html）。文字は本文の大きさ
    （sequenceDiagram は fontSize を見ず、既定で 14・16px なので別に書く）。"""
    px = STYLES["NORMAL_TEXT"][0] * 96 / 72
    return {"theme": "base", "themeVariables": {
        "fontFamily": f"{FONT}, sans-serif", "fontSize": f"{px:g}px",
        "primaryColor": "#" + PANEL, "primaryTextColor": "#" + TEXT, "primaryBorderColor": "#" + HEAD, "lineColor": "#" + SUB, "textColor": "#" + TEXT,
        "secondaryColor": "#" + WHITE, "tertiaryColor": "#" + WHITE},
        "sequence": {"actorFontSize": px, "messageFontSize": px, "noteFontSize": px}}


def mermaid_png(code):
    """mermaid の図 code を PNG に描き、build/ からのパスを返す（MERMAID_DIR/<指紋>.png。あれば描かない）。"""
    cfg = mermaid_config()
    out = os.path.join(MERMAID_DIR, hashlib.sha1(json.dumps([code, cfg, MERMAID_SCALE, MERMAID_CLI], ensure_ascii=False).encode()).hexdigest()[:12] + ".png")
    if os.path.isfile(out):
        return out
    if not shutil.which("npx"):
        sys.exit("mermaid の図を描くには Node.js が要る（npx で mermaid-cli を取ってくる。初めては数分かかる）。Node.js を入れるか、図を画像にして ![題](画像) で置く")
    print(f"mermaid の図を描く: {out}", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        src, conf, png_ = (os.path.join(tmp, x) for x in ("in.mmd", "config.json", "out.png"))
        open(src, "w", encoding="utf-8").write(code)
        json.dump(cfg, open(conf, "w"))
        try:  # 初めては mermaid-cli と Chrome を取ってくるので長い（2026-10-19 に約 100 秒）。止まったままにしない
            r = subprocess.run(["npx", "-y", MERMAID_CLI, "-i", src, "-o", png_, "-s", str(MERMAID_SCALE), "-b", "white", "-c", conf, "-q"],
                               capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            sys.exit(f"mermaid の図を 15 分で描けなかった（npx が mermaid-cli か Chrome を取ってこられない）。回線を確かめて組み直す:\n{code}")
        if r.returncode or not os.path.isfile(png_):
            sys.exit(f"mermaid の図を描けなかった（書き方の誤りか、mermaid-cli が動かない）:\n{code}\n{(r.stderr or r.stdout).strip()[-800:]}")
        os.makedirs(MERMAID_DIR, exist_ok=True)
        shutil.copyfile(png_, out + ".tmp")  # 同じフォルダで置き換える（途中で止まっても、壊れた PNG を描いたものとして残さない）
        os.replace(out + ".tmp", out)
    return out


def image_px(path):
    """PNG の幅（画素）。"""
    b = open(path, "rb").read(24)
    return int.from_bytes(b[16:20], "big")


class Writer:
    """本文の末尾（最後の空の段落の頭、cur）に塊を足していく要求を作る。要求は前から順に効くので、足すたびに cur を進める。"""

    def __init__(self, cur):
        self.cur, self.reqs = cur, []

    def text(self, rs, style="NORMAL_TEXT", pstyle=None, tstyle=None, size=None):
        """1 段落を足す。pstyle・tstyle は段落全体の書式（P_FIELDS・T_FIELDS の中のもの）。"""
        text = "".join(t for t, _ in rs) + "\n"
        s, n = self.cur, u16(text)
        rng = {"startIndex": s, "endIndex": s + n}
        self.reqs += [{"insertText": {"location": {"index": s}, "text": text}},
                      {"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": style, **(pstyle or {})}, "fields": P_FIELDS}},
                      {"updateTextStyle": {"range": rng, "textStyle": {**(tstyle or {}), **({"fontSize": pt(size)} if size else {})}, "fields": T_FIELDS}}]
        self.styles(s, rs, size)
        self.cur += n
        return s

    def styles(self, s, rs, size=None):
        for t, st in rs:
            k = u16(t)
            if st.get("code"):
                self.mono(s, t, size or CODE_PT)
            ts = {x: st[x] for x in ("bold", "link") if x in st} | ({"foregroundColor": color(RED_TEXT)} if st.get("red") else {})
            if ts:
                self.reqs.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": s + k}, "textStyle": ts, "fields": ",".join(ts)}})
            s += k

    def mono(self, s, t, size):
        """英数字の続きだけ MONO にする（和文は FONT のまま）。"""
        for m in ASCII.finditer(t):
            a = s + u16(t[:m.start()])
            self.reqs.append({"updateTextStyle": {"range": {"startIndex": a, "endIndex": a + u16(m.group())},
                                                  "textStyle": {**font(MONO), "fontSize": pt(size)}, "fields": "weightedFontFamily,fontSize"}})

    def block(self, b, uri):
        kind = b[0]
        if kind == "p":
            _, style, rs, opt = b
            if opt.get("quote"):
                # 線は文字の左端から内側の余白と線の太さだけ左に描かれる。字下げをその分にすると、線が本文の左端に来る。
                # 1 行目の位置は indentFirstLine（左端からの位置。indentStart は 2 行目から）なので、両方に入れる（2026-10-09 に画像で測った）
                ind = pt(8 + 3)
                self.text(rs, pstyle={"indentStart": ind, "indentFirstLine": ind,
                                      "borderLeft": {"color": color(RULE), "width": pt(3), "padding": pt(8), "dashStyle": "SOLID"}},
                          tstyle={"foregroundColor": color(SUB)})
            elif opt.get("small"):
                self.text(rs, pstyle={"spaceBelow": pt(10), "lineSpacing": TIGHT}, tstyle={"foregroundColor": color(SUB)}, size=SMALL_PT)
            else:
                self.text(rs, style, pstyle={"keepWithNext": True} if opt.get("keep") else None)
        elif kind == "list":
            _, numbered, items = b
            s = self.cur
            for i, rs in enumerate(items):  # 項目の間は詰め、最後の項目のあとは本文と同じだけ空ける
                self.text(rs, pstyle={"spaceBelow": pt(3)} if i < len(items) - 1 else None)
            self.reqs.append({"createParagraphBullets": {"range": {"startIndex": s, "endIndex": self.cur},
                                                         "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN" if numbered else "BULLET_DISC_CIRCLE_SQUARE"}})
            self.cur -= sum(len(rs[0][0]) - len(rs[0][0].lstrip("\t")) for rs in items if rs)  # 段を決めた頭のタブは、API が消す
        elif kind == "code":  # 1 つの段落にし、行は段落の中の改行（\v）でつなぐ（塗りが行の間で切れない）
            # 塗りには内側の余白がないので、塗りと同じ色の枠線の padding で取る。枠は字下げの分だけ外に出るので、その分を字下げして本文の端にそろえる
            edge, ind = {"color": color(PANEL), "width": pt(0.75), "padding": pt(6), "dashStyle": "SOLID"}, pt(6 + 0.75)
            s = self.text([(b[1].replace("\n", "\v"), {})], size=CODE_PT,
                          pstyle={"shading": {"backgroundColor": color(PANEL)}, "lineSpacing": CODE_LS, "spaceAbove": pt(10), "spaceBelow": pt(14),
                                  "indentStart": ind, "indentFirstLine": ind, "indentEnd": ind, **{f"border{x}": edge for x in ("Top", "Bottom", "Left", "Right")}})
            self.mono(s, b[1].replace("\n", "\v"), CODE_PT)
        elif kind == "image":
            _, src, caption, width = b
            s = self.cur
            self.reqs += [{"insertText": {"location": {"index": s}, "text": "\n"}},
                          {"insertInlineImage": {"location": {"index": s}, "uri": uri[src], "objectSize": {"width": mm(width)}}},
                          {"updateParagraphStyle": {"range": {"startIndex": s, "endIndex": s + 2},
                                                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "alignment": "CENTER", "keepWithNext": bool(caption),
                                                                       "spaceAbove": pt(6)}, "fields": P_FIELDS}}]
            self.cur += 2
            if caption:
                self.text([(caption, {})], pstyle={"alignment": "CENTER", "spaceBelow": pt(12), "lineSpacing": TIGHT}, tstyle={"foregroundColor": color(SUB)},
                          size=SMALL_PT)
        elif kind == "cover":  # 上に空きを取り、題を中央に。左の語とロゴは 1 つの段落に並べる（表を使わない）
            _, lines, left, logo = b
            for i, t in enumerate(lines):
                self.text([(t, {})], "TITLE", pstyle={"alignment": "CENTER", "spaceAbove": pt(120 if i == 0 else 0), "spaceBelow": pt(8)},
                          size=COVER_PT)
            s = self.cur
            lead = left or ""
            if left and logo:
                lead += "\u3000" * 6  # 左の語とロゴの間
            self.reqs += [{"insertText": {"location": {"index": s}, "text": lead + "\n"}}]
            if logo:
                self.reqs.append({"insertInlineImage": {"location": {"index": s + u16(lead)}, "uri": uri[logo], "objectSize": {"width": mm(70)}}})
            self.reqs += [{"updateParagraphStyle": {"range": {"startIndex": s, "endIndex": s + u16(lead) + 1 + bool(logo)},
                                                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "alignment": "CENTER", "spaceAbove": pt(90)},
                                                    "fields": P_FIELDS}},
                          {"updateTextStyle": {"range": {"startIndex": s, "endIndex": s + u16(lead) + 1}, "textStyle": {"fontSize": pt(20)},
                                               "fields": T_FIELDS}}]
            self.cur += u16(lead) + 1 + bool(logo)
        elif kind == "break":
            self.reqs.append({"insertPageBreak": {"location": {"index": self.cur}}})
            self.cur += 2  # 改ページと、そのあとの改行


def put_table(did, cur, rows, caption, widths):
    """表を cur に入れる。API は表の前に改行を 1 つ入れるので、その段落を表の題にする（題がなければ空の段落のまま）。
    セルの位置は入れたあとの JSON で取り、後ろのセルから埋める（前のセルの位置がずれない）。戻り: 表のあとの段落の頭。"""
    nr, nc = len(rows), len(rows[0])
    w = Writer(cur)
    w.reqs.append({"insertTable": {"rows": nr, "columns": nc, "location": {"index": cur}}})
    if caption:  # 表の前の段落（cur）に題を入れる。改行は API が入れたものを使う
        w.reqs += [{"insertText": {"location": {"index": cur}, "text": caption}},
                   {"updateParagraphStyle": {"range": {"startIndex": cur, "endIndex": cur + u16(caption) + 1},
                                             "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "alignment": "CENTER", "keepWithNext": True, "spaceAbove": pt(6),
                                                                "lineSpacing": TIGHT},
                                             "fields": P_FIELDS}},
                   {"updateTextStyle": {"range": {"startIndex": cur, "endIndex": cur + u16(caption)},
                                        "textStyle": {"foregroundColor": color(SUB), "fontSize": pt(SMALL_PT)}, "fields": T_FIELDS}}]
    batch_doc(did, w.reqs)
    body = request("GET", f"{DOCS}/{did}?fields=body(content(startIndex,table(tableRows(tableCells(content(startIndex))))))")["body"]["content"]
    t = next(e for e in body if "table" in e and e["startIndex"] >= cur)
    at = {"tableStartLocation": {"index": t["startIndex"]}}
    w = Writer(0)
    for r in reversed(range(nr)):
        for c in reversed(range(nc)):
            rs = rows[r][c]
            if not rs:
                continue
            w.cur = t["table"]["tableRows"][r]["tableCells"][c]["content"][0]["startIndex"]
            text = "".join(x for x, _ in rs)
            rng = {"startIndex": w.cur, "endIndex": w.cur + u16(text)}
            w.reqs += [{"insertText": {"location": {"index": w.cur}, "text": text}},
                       {"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "lineSpacing": TIGHT, "spaceBelow": pt(0)},
                                                 "fields": P_FIELDS}},
                       {"updateTextStyle": {"range": rng, "textStyle": {"fontSize": pt(SMALL_PT), **(
                           {"bold": True, "foregroundColor": color(TABLE_HEAD[1])} if r == 0 else {})}, "fields": T_FIELDS}}]
            w.styles(w.cur, rs, SMALL_PT)
    edge = {"color": color(RULE), "width": pt(0.75), "dashStyle": "SOLID"}
    w.reqs += [{"updateTableCellStyle": {"tableRange": {"tableCellLocation": {**at, "rowIndex": 0, "columnIndex": 0}, "rowSpan": nr, "columnSpan": nc},
                                         "tableCellStyle": {**{f"border{s}": edge for s in ("Top", "Bottom", "Left", "Right")},
                                                            **{f"padding{s}": pt(5) for s in ("Top", "Bottom", "Left", "Right")}},
                                         "fields": "borderTop,borderBottom,borderLeft,borderRight,paddingTop,paddingBottom,paddingLeft,paddingRight"}},
               {"updateTableCellStyle": {"tableRange": {"tableCellLocation": {**at, "rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": nc},
                                         "tableCellStyle": {"backgroundColor": color(TABLE_HEAD[0])}, "fields": "backgroundColor"}},
               {"pinTableHeaderRows": {"tableStartLocation": at["tableStartLocation"], "pinnedHeaderRowsCount": 1}}]
    if widths:
        w.reqs += [{"updateTableColumnProperties": {"tableStartLocation": at["tableStartLocation"], "columnIndices": [i],
                                                    "tableColumnProperties": {"widthType": "FIXED_WIDTH", "width": mm(x)}, "fields": "widthType,width"}}
                   for i, x in enumerate(widths)]
    batch_doc(did, w.reqs)
    return request("GET", f"{DOCS}/{did}?fields=body(content(startIndex))")["body"]["content"][-1]["startIndex"]


def batch_doc(did, reqs):
    """documents.batchUpdate。まとめて送った要求は、どれか 1 つが失敗すると全部が入らない。"""
    return request("POST", f"{DOCS}/{did}:batchUpdate", {"requests": reqs}) if reqs else {}


def fingerprint(did):
    body = request("GET", f"{DOCS}/{did}?fields=body")["body"]
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def footer_text(name):
    """スライドと同じ著作権表示と、NAME の末尾の秘密区分（slides.py の finish）。資料名は出さない。"""
    c = re.search(r"(?:^|[｜|])\s*(Internal Only|Confidential)\s*$", name, re.I)
    return COPYRIGHT + (f"｜{c.group(1)}" if c else "")


def footer(did, name):
    """フッターがなければ作って著作権表示を入れる。あるフッターは触らない（画面で入れたページ番号を消さない。ページ番号は API で入れられない）。"""
    if request("GET", f"{DOCS}/{did}?fields=documentStyle(defaultFooterId)").get("documentStyle", {}).get("defaultFooterId"):
        return
    fid = batch_doc(did, [{"createFooter": {"type": "DEFAULT"}}])["replies"][0]["createFooter"]["footerId"]
    text = footer_text(name)
    batch_doc(did, [{"insertText": {"location": {"segmentId": fid, "index": 0}, "text": text}},
                    {"updateTextStyle": {"range": {"segmentId": fid, "startIndex": 0, "endIndex": u16(text)},
                                         "textStyle": {**font(FONT), "fontSize": pt(COPYRIGHT_PT), "foregroundColor": color(SUB)},
                                         "fields": "weightedFontFamily,fontSize,foregroundColor"}}])


def build(did, doc, force=False):
    """did の本文を、doc の塊に置き換える。force=False なら、先に画面での直しとコメントを確かめる（gapi.guard）。"""
    need_brand()
    if not force:
        gapi.guard(did, fingerprint(did), STAMP, "doc.md")
    imgs = [b[1] for b in doc.blocks if b[0] == "image"] + [b[3] for b in doc.blocks if b[0] == "cover" and b[3]]
    local = sorted({x for x in imgs if not re.match(r"https?://", x)})
    uri = {x: x for x in imgs}
    carrier = None
    try:
        if local:  # 手元の画像は、Google が読める URL（30 分で切れる）にしてから貼る（gapi.py の carry）
            urls, carrier = carry(local)
            uri.update(zip(local, urls))
        end = request("GET", f"{DOCS}/{did}?fields=body(content(endIndex))")["body"]["content"][-1]["endIndex"]
        # 本文を消し、残る最後の段落を素の本文に戻す（新しい段落は、そこから書式を受け継ぐ）
        reset = [{"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end - 1}}}] if end > 2 else []
        reset += [{"deleteParagraphBullets": {"range": {"startIndex": 1, "endIndex": 2}}},
                  {"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": 2}, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": P_FIELDS}},
                  {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 2}, "textStyle": {}, "fields": T_FIELDS}}]
        batch_doc(did, reset + style_reqs())
        w, n = Writer(1), 0
        for b in doc.blocks:
            if b[0] == "table":  # 表はセルの位置を JSON で取るので、そこまでを送ってから入れる
                batch_doc(did, w.reqs)
                n += len(w.reqs)
                w = Writer(put_table(did, w.cur, *b[1:]))
            else:
                w.block(b, uri)
        batch_doc(did, w.reqs)
        n += len(w.reqs)
    finally:
        if carrier:  # 貼った画像は文書の中に写し取られているので、仮のファイルは消してよい
            delete(carrier)
    footer(did, doc.name)
    gapi.stamp(did, f"{FONT}\t{MONO}", FONTS)  # 版（STAMP）より先に書く。途中で止まっても、版の新しい文書に前の書体が残らない
    gapi.stamp(did, fingerprint(did), STAMP)
    gapi.stamp(did, os.path.relpath(os.getcwd(), gapi.factory_path().parent), SRC)
    used = {os.path.realpath(x) for x in imgs}  # doc.md が ./mermaid/… や絶対パスで指す画像も消さない
    for f in glob.glob(os.path.join(MERMAID_DIR, "*.png")):  # 書き直す前の mermaid の図（doc.md から消えた図）。指紋を残したあとに消す
        if os.path.realpath(f) not in used:
            os.remove(f)
    print(json.dumps({"documentId": did, "url": f"https://docs.google.com/document/d/{did}/edit", "blocks": len(doc.blocks),
                      "requests": n, "warnings": len(doc.warnings)}, ensure_ascii=False))


def new(folder, name):
    if not re.match(r"\d{8}_", name):
        sys.exit("Drive 上の名前は YYYYMMDD_ で始める: " + name)
    return request("POST", f"{DRIVE}/files?supportsAllDrives=true&fields=id", {"name": name, "mimeType": GDOCS, "parents": [folder_id(folder)]})["id"]


STANDARD = "standard"  # 組み込みのテーマ（docs.py の既定の値）。theme を書かず、[docs] default_theme もないとき。doc.md に theme: standard とも書ける
DEFAULT_NOTE = "既定。A4・本文 10.5pt・濃紺の見出し・濃紺の地の表の見出しの行（../visual.md）"  # themes/docs/standard.json の description で書き換えられる
# [docs-write-012] テーマのファイル。スライドのテーマのファイル（slides.py の read_theme）と同じ形で、頭の apiVersion・kind と description・font・mono・colors は
# 同じキー。page・margins・styles はドキュメントだけのキー。版はキーの意味が変わるときだけ上げる（../../slides-build/pages.md の slides-pages-035 と同じ考え方）
API_VERSION = "docs/v1"
WS_THEMES = ("themes", "docs")  # ワークスペースの themes/docs/<名前>.json（ファイルの名前がテーマの名前）
# colors に書ける役割（6 桁の色）。HEAD・TEXT・SUB・RULE・PANEL・RED_TEXT はスライドの役割と同じ意味。TABLE_HEAD・TABLE_HEAD_TEXT はドキュメントだけ
COLOR_ROLES = {"HEAD": "題と見出し", "TEXT": "本文", "SUB": "補助（副題・図表の題・出典・引用・フッター）", "RULE": "罫線と引用の線", "PANEL": "コードの地",
               "RED_TEXT": "***赤の太字***", "TABLE_HEAD": "表の見出しの行の地", "TABLE_HEAD_TEXT": "表の見出しの行の文字"}
STYLE_KEYS = {"TITLE": "TITLE", "SUBTITLE": "SUBTITLE", "H1": "HEADING_1", "H2": "HEADING_2", "H3": "HEADING_3", "BODY": "NORMAL_TEXT"}  # styles の名前 → 名前付きスタイル
STYLE_PROPS = ("size", "color", "above", "below", "spacing")  # 大きさ（pt）、色、上・下の空き（pt）、行間（%）。STYLES の太字のほかの値と同じ順


def docs_cfg():
    """factory.toml の [docs]（なければ空。selftest は factory.toml なしで回る）。"""
    return gapi.factory().get("docs", {}) if gapi.find_factory() else {}


def ws_themes():
    """ワークスペースのテーマのフォルダ（themes/docs）。factory.toml がなければ None。"""
    return ws.parent.joinpath(*WS_THEMES) if (ws := gapi.find_factory()) else None


def theme_names():
    return sorted(f.stem for f in d.glob("*.json")) if (d := ws_themes()) and d.is_dir() else []


def read_theme(path):
    """テーマのファイル path（kind theme）を確かめて dict にする（load_theme が読む形）。書けない値は、場所を付けてまとめて止める（組む前に。factory-doctor も呼ぶ）。
    色のコントラストでは止めない（会社の文書のテンプレートの色に合わせるテーマなので。poc の見出しの 4A86E8 は白の地で 3.58:1）。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", Path(path).stem):
        sys.exit(f"{path}: テーマのファイルの名前は英数字と - _ だけにする（名前がテーマの名前）")
    try:
        o = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{path}: 読めない（{e}）")
    if not isinstance(o, dict) or o.get("apiVersion") != API_VERSION or o.get("kind") != "theme":
        sys.exit(f'{path}: ファイルの頭は {{"apiVersion": "{API_VERSION}", "kind": "theme", …}}')
    num = lambda v, pos=False: isinstance(v, (int, float)) and not isinstance(v, bool) and (v > 0 if pos else v >= 0)
    hex6 = lambda v: isinstance(v, str) and re.fullmatch(r"[0-9A-Fa-f]{6}", v)
    bad = []
    for k, v in o.items():
        if k in ("apiVersion", "kind"):
            continue
        if k in ("description", "font", "mono"):
            bad += [] if isinstance(v, str) else [f"{k}: 文字列でない"]
        elif k in ("page", "margins"):
            bad += [] if isinstance(v, list) and len(v) == 2 and all(num(x, k == "page") for x in v) else [f"{k}: [{'幅, 高さ' if k == 'page' else '上下, 左右'}]（mm）の 2 つの数でない"]
        elif k == "colors" and isinstance(v, dict):
            for c, x in v.items():
                bad += [f"colors.{c}: 知らない役割（{'・'.join(COLOR_ROLES)}）"] if c not in COLOR_ROLES else [] if hex6(x) else [f"colors.{c}: 6 桁の 16 進の色でない（# は付けない）"]
        elif k == "styles" and isinstance(v, dict):
            for n, props in v.items():
                if n not in STYLE_KEYS:
                    bad.append(f"styles.{n}: 知らないスタイル（{'・'.join(STYLE_KEYS)}）")
                elif not isinstance(props, dict):
                    bad.append(f"styles.{n}: {{\"size\": …}} の形でない")
                else:
                    for q, x in props.items():
                        if q not in STYLE_PROPS:
                            bad.append(f"styles.{n}.{q}: 知らないキー（{'・'.join(STYLE_PROPS)}）")
                        elif q == "color" and not hex6(x):
                            bad.append(f"styles.{n}.color: 6 桁の色でない")
                        elif q != "color" and not num(x, q in ("size", "spacing")):
                            bad.append(f"styles.{n}.{q}: 0 以上の数でない（大きさと行間は 0 より大きく）")
        else:
            bad.append(f"{k}: {'形が違う' if k in ('colors', 'styles') else '知らないキー（description・font・mono・colors・page・margins・styles）'}")
    if bad:
        sys.exit(f"{path}: " + "。".join(bad))
    theme_font(o), theme_mono(o)  # 書体の確かめはスライドと同じ（和文を描けない書体、リガチャのある等幅を止める）
    return o


def theme(name):
    """テーマのファイル（themes/docs/<名前>.json）を入れる。standard はファイルがなければ既定の値のまま。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):  # themes/docs/ の外のファイルを指させない
        sys.exit(f"テーマの名前 {name!r} は英数字と - _ だけにする（themes/docs/<名前>.json のファイルの名前）")
    if (d := ws_themes()) and (f := d / f"{name}.json").is_file():
        return load_theme(read_theme(f))
    if name in docs_cfg().get("themes", {}):  # 2026-10-19 までの書き方（standard も、書いた値を黙って捨てない）
        sys.exit(f"テーマ {name} がない（themes/docs/{name}.json）。factory.toml の [docs.themes.{name}] はもう読まない。テーマのファイルに移す（docs-build の ../SKILL.md を開いてから、その themes.md の docs-write-010）")
    if name != STANDARD:
        sys.exit(f"テーマ {name} がない（themes/docs/{name}.json）。docs.py themes が一覧を出す（docs-build の ../SKILL.md を開いてから、その themes.md の docs-write-010）")


def cmd_themes():
    """テーマの名前と説明を 1 行ずつ出す。エージェントが、資料の種類と聞き手に合うものを選ぶ。書けない値のあるファイルは、その行に誤りを出して続ける
    （ほかのテーマを選べるように。組むときは read_theme が止める）。"""
    default, names = docs_cfg().get("default_theme", STANDARD), theme_names()
    for name in dict.fromkeys([STANDARD, *names]):
        try:
            t = read_theme(ws_themes() / f"{name}.json") if name in names else {}
        except SystemExit as e:
            t = {"description": f"（使えない: {e}）"}
        note = t.get("description") or (DEFAULT_NOTE if name == STANDARD else f"（説明がない。themes/docs/{name}.json の description に書く）")
        print(f"{name}{'（既定）' if name == default else ''}\t{note}")


def need_theme(doc):
    """new で、standard のほかにテーマがあるのに doc.md の頭に theme: がなければ、一覧を出して止める（slides.py の need_theme と同じく、選ぶものがあるときだけ。
    themes/docs/standard.json に説明だけを書いたときは止めない。factory-kaizen の検証では止めない）。"""
    if not doc.meta.get("theme") and set(theme_names()) - {STANDARD} and not os.environ.get("FACTORY_VERIFY"):
        cmd_themes()
        sys.exit(f"テーマを選んでから組む。上の description と、資料の種類・聞き手を突き合わせて、doc.md の頭に theme: <名前> を書く"
                 f"（既定のままなら theme: {docs_cfg().get('default_theme', STANDARD)}）。選んだテーマと理由は構成案の前提に書く")


def load_theme(t):
    """テーマ（read_theme の dict）の版面・名前付きスタイル・色・書体を入れる（style_reqs・put_table・Doc が読む値）。書いていない値は既定のまま。
    page・margins は mm（[幅, 高さ]・[上下, 左右]）。styles は TITLE・SUBTITLE・H1〜H3・BODY ごとの size（pt）・color・above・below（pt）・spacing（%）。
    styles に color を書かなければ、題と見出しは colors の HEAD、副題は SUB、本文は TEXT。font・mono は本文と等幅の書体（brand.py の theme_font・theme_mono）。
    font は和文を描けると確かめた書体（JP_FONTS）と DM Sans（FONT_EM）だけ。行送りの見込みは Noto Sans JP のまま。description は使い分けの説明（cmd_themes）。"""
    global PAGE_MM, MARGIN_TB_MM, MARGIN_LR_MM, TEXT_MM, TABLE_HEAD, SCALE, FONT, MONO, HEAD, TEXT, SUB, RULE, PANEL, RED_TEXT
    FONT, MONO = theme_font(t), theme_mono(t)
    c = {k: v.upper() for k, v in t.get("colors", {}).items()}
    HEAD, TEXT, SUB, RULE, PANEL, RED_TEXT = (c.get(k, v) for k, v in (("HEAD", HEAD), ("TEXT", TEXT), ("SUB", SUB), ("RULE", RULE), ("PANEL", PANEL), ("RED_TEXT", RED_TEXT)))
    TABLE_HEAD = (c.get("TABLE_HEAD", TABLE_HEAD[0]), c.get("TABLE_HEAD_TEXT", TABLE_HEAD[1]))
    PAGE_MM = tuple(t.get("page", PAGE_MM))
    MARGIN_TB_MM, MARGIN_LR_MM = t.get("margins", (MARGIN_TB_MM, MARGIN_LR_MM))
    TEXT_MM = round(PAGE_MM[0] - 2 * MARGIN_LR_MM, 1)
    SCALE = TEXT_MM / 150
    for key, name in STYLE_KEYS.items():
        size, bold, col, above, below, spacing = STYLES[name]
        p = {**dict(zip(STYLE_PROPS, (size, {"SUBTITLE": SUB, "NORMAL_TEXT": TEXT}.get(name, HEAD), above, below, spacing))), **t.get("styles", {}).get(key, {})}
        STYLES[name] = (p["size"], bold, p["color"].upper(), p["above"], p["below"], p["spacing"])


# ---- doc.md（中身の正本） ----
# 頭（--- で挟む）: name（資料名・秘密区分。docs.py の NAME と同じ）、theme、template（照合するテンプレートの名前）、omit（テンプレートの節のうち、外す節）、
# cover（表紙の題の行の並び）と cover_left、title と subtitle、source（テンプレートだけ。元にした文書の URL。骨組みを比べる）。
# 本文: # ## ### は見出し、段落は空行で区切る（行は「。」の後で分けてよい。組むときにつなぐ）、「出典: 」で始まる段落は出典の行、> は引用（書き手への注記も）、
# - と 1. は箇条書き（2 字以上下げると 2 段目）、表の直前の「表: 題 {widths: 30 80 40}」は表の題と列の幅の比、| の表（1 行目が見出しの行）、
# ![題](画像){width=150} は図（幅は mm）、``` はコード、```mermaid は mermaid の図（直前の「図: 題 {width: 120}」は図の題と幅）、\newpage は改ページ、
# <br> は段落・セルの中の改行、<!-- --> は組まない覚え書き
MD_CAPTION = re.compile(r"表[:：]\s*(.*?)\s*(?:\{widths?[:=]?\s*([\d.,\s]+)\})?")
MD_FIGURE = re.compile(r"図[:：]\s*(.*?)\s*(?:\{width[:=]?\s*([\d.]+)\})?")
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)\s*(?:\{width[:=]?\s*([\d.]+)\})?")
MD_ITEM = re.compile(r"( *)([-*]|\d+\.) +(.*)")
MD_SEP = re.compile(r"\|?(\s*:?-+:?\s*\|)*\s*:?-+:?\s*\|?")


def meta_of(head):
    """front matter の「名前: 値」と、その下の「  - 値」の並び（YAML の一部だけ）。"""
    m, key = {}, None
    for ln in head.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if ln.lstrip().startswith("- ") and key:
            m[key] = (m[key] or []) + [ln.lstrip()[2:].strip()]
        else:
            key, _, v = ln.partition(":")
            key = key.strip()
            m[key] = re.sub(r"\s+#\s.*$", "", v).strip().strip('"')  # 行末の「  # 覚え書き」は値に入れない
    return m


def join(lines):
    """段落の行をつなぐ。英数字どうしの間だけ空白を入れる（和文は詰める）。<br> は段落の中の改行。"""
    out = ""
    for ln in (x.strip() for x in lines):
        out += (" " if out and ASCII.fullmatch(out[-1]) and ASCII.fullmatch(ln[0]) else "") + ln
    return out.replace("<br>", "\v")


def cells(row):
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return [c.strip().replace("\\|", "|").replace("<br>", "\v") for c in re.split(r"(?<!\\)\|", row)]


def from_md(path, apply_theme=True):
    """doc.md を読んで Doc にする。apply_theme=False はテンプレートを照合のために読むとき（今のテーマを変えない）。"""
    text = re.sub(r"<!--.*?-->", "", open(path, encoding="utf-8").read(), flags=re.S)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = meta_of(m.group(1)) if m else {}
    if not meta.get("name"):
        sys.exit(f"{path} の頭に name: がない")
    if (name := meta.get("theme") or docs_cfg().get("default_theme")) and apply_theme:  # theme を書かなければ [docs] default_theme
        theme(name)
    d = Doc(meta["name"])
    d.meta = meta
    if meta.get("cover"):
        d.cover(meta["cover"], meta.get("cover_left") or None)
    if meta.get("title"):
        d.title(meta["title"], meta.get("subtitle") or None)
    L, i, para, cap, fig = text[m.end() if m else 0:].split("\n"), 0, [], None, None

    def flush():
        if para:
            t = join(para)
            para.clear()
            (d.src if re.match(r"(出典|Sources?)[：:]", t) else d.p)(t)

    while i < len(L):
        ln, s = L[i], L[i].strip()
        if cap and s and not s.startswith("|"):
            d.warn(f"「表: {cap[0]}」の次の行が表でない（{i + 1} 行目）")
            cap = None
        if not s:
            flush()
            i += 1
        elif s.startswith("```"):
            flush()
            j = next((k for k in range(i + 1, len(L)) if L[k].strip().startswith("```")), len(L))
            if s == "```mermaid":
                if apply_theme:  # テンプレートを照合のために読むときは描かない（照合は節と表だけを見る）
                    d.mermaid("\n".join(L[i + 1:j]), *(fig or (None, None)))
                fig = None
            else:
                d.code("\n".join(L[i + 1:j]))
            i = j + 1
        elif h := re.fullmatch(r"(#{1,3}) +(.+)", s):
            flush()
            getattr(d, f"h{len(h[1])}")(h[2].strip())
            i += 1
        elif s == "\\newpage":
            flush()
            d.pagebreak()
            i += 1
        elif s.startswith(">"):
            flush()
            q = []
            while i < len(L) and L[i].strip().startswith(">"):
                q.append(L[i].strip()[1:])
                i += 1
            d.quote(join(q))
        elif c := MD_CAPTION.fullmatch(s):
            flush()
            cap = (c[1] or None, [float(x) for x in re.split(r"[,\s]+", c[2].strip())] if c[2] else None)
            i += 1
        elif (c := MD_FIGURE.fullmatch(s)) and next((x.strip() for x in L[i + 1:] if x.strip()), "") == "```mermaid":  # 次が図でない「図: …」は本文の行
            flush()
            fig = (c[1] or None, float(c[2]) if c[2] else None)
            i += 1
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(L) and L[i].strip().startswith("|"):
                if not MD_SEP.fullmatch(L[i].strip()):
                    rows.append(cells(L[i]))
                i += 1
            d.table(rows, *(cap or (None, None)))
            cap = None
        elif g := MD_IMAGE.fullmatch(s):
            flush()
            d.image(g[2], g[1] or None, float(g[3]) if g[3] else 120)
            i += 1
        elif it := MD_ITEM.fullmatch(ln):
            flush()
            items, numbered = [], it[2][0].isdigit()
            while i < len(L) and L[i].strip():
                if x := MD_ITEM.fullmatch(L[i]):
                    items.append(("\t" if len(x[1]) >= 2 else "") + x[3].strip())
                elif L[i].startswith(" "):  # 項目の続きの行
                    items[-1] = "\t" * items[-1].startswith("\t") + join([items[-1].lstrip("\t"), L[i]])
                else:
                    break
                i += 1
            d.bullets([x.replace("<br>", "\v") for x in items], numbered)
        else:
            para.append(s)
            i += 1
    flush()
    return d


def load_doc():
    """今いるフォルダ（資料の build/）の doc.md を読む。"""
    if not os.path.isfile("doc.md"):
        sys.exit("今いるフォルダに doc.md がない。資料の build/ で動かす（テンプレートから書き始めるなら docs.py init <テンプレートの名前>）")
    return from_md("doc.md")


def template_md(name):
    """テンプレートの doc.md（ワークスペースの rules/docs-build/templates/<名前>/。会社の文書の型なので、プラグインには入れない）。"""
    p = gapi.factory_path().parent / "rules" / "docs-build" / "templates" / name / "doc.md"
    if not p.is_file():
        sys.exit(f"テンプレート {name} がない（{p}）")
    return str(p)


def cmd_init(name):
    """テンプレートの doc.md を写して、今いるフォルダの doc.md にする。頭の name は仮にし、template を足し、source・skeleton_ok を外す。"""
    if os.path.exists("doc.md"):
        sys.exit("doc.md がもうある。消してから")
    text = open(template_md(name), encoding="utf-8").read()
    head, body = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S).groups()
    keep, out = True, []
    for x in head.splitlines():  # テンプレートだけの項目（source・skeleton_ok）は、続く「  - 」の行ごと外す
        if not x.startswith(" "):
            keep = not re.match(r"(name|source|skeleton_ok|template)\s*:", x)
        if keep:
            out.append(x)
    head = "\n".join(out)
    open("doc.md", "w", encoding="utf-8").write(f"---\nname: <資料名>\ntemplate: {name}\n{head}\n---\n{body}")
    print("doc.md を作った。name: を直し、本文の [ ] の札と > <担当: …> の注記を中身に置き換える")


# ---- 確かめる ----
def md_text(p):
    """段落の文字。リンクは [文字](URL) にする（レビューで出典を確かめられるように）。"""
    out = []
    for x in p.get("elements", []):
        t = x.get("textRun", {})
        c, url = t.get("content", "").replace("\v", "\n"), t.get("textStyle", {}).get("link", {}).get("url")
        out.append(f"[{c.rstrip(chr(10))}]({url})" + "\n" * c.endswith("\n") if url and c.strip() else c)
    return "".join(out)


def text_of(doc):
    """レビューに渡すテキスト。見出しは #、表は 1 行を「 | 」でつなぎ、画像は［画像］、リンクは [文字](URL)。"""
    out = []
    for e in doc["body"]["content"]:
        if "paragraph" in e:
            p = e["paragraph"]
            t = md_text(p)
            st = p["paragraphStyle"].get("namedStyleType", "")
            img = any("inlineObjectElement" in x for x in p["elements"])
            head = {"TITLE": "# ", "SUBTITLE": "", "HEADING_1": "## ", "HEADING_2": "### ", "HEADING_3": "#### "}.get(st, "- " if "bullet" in p else "")
            if img:
                out.append("［画像］")
            if t.strip():
                out.append(head + t.strip())
        elif "table" in e:
            out += [" | ".join(" ".join(md_text(x["paragraph"]).strip() for x in c["content"] if "paragraph" in x) for c in row["tableCells"])
                    for row in e["table"]["tableRows"]]
        out.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


HEAD_TAG = {"TITLE": "TITLE", "SUBTITLE": "SUBTITLE", "HEADING_1": "H1", "HEADING_2": "H2", "HEADING_3": "H3"}


def render(rs):
    """(文字, 書式) の並びを、比べる形の 1 行にする（**太字**・***赤の太字***・[リンク](URL)・`コード`、段落の中の改行は ⏎）。"""
    out = []
    for t, st in rs:
        t = t.replace("\v", "⏎")
        t = ASCII.sub(lambda m: f"`{m.group()}`", t) if st.get("code") else t  # コードは英数字だけが MONO になる（Writer.mono）
        t = f"[{t}]({st['link']['url']})" if st.get("link") else t
        out.append(f"***{t}***" if st.get("red") else f"**{t}**" if st.get("bold") else t)
    return "".join(out).strip()


def plain(rs):
    return [(t, {}) for t, _ in rs]


def style_line(name, font_name, size, bold, c):
    return f"STYLE {name} {font_name} {size:g}pt{' 太字' if bold else ''} {c}"


def canon_doc(d):
    """組む前の Doc を、比べる形（1 行 1 要素）にする。canon_json が組んだ文書から同じ形を作る。"""
    out = [f"PAGE {round(PAGE_MM[0])}x{round(PAGE_MM[1])} 余白 {round(MARGIN_TB_MM)}/{round(MARGIN_LR_MM)}"]
    out += [style_line(n, FONT, size, bold, c) for n, (size, bold, c, *_) in STYLES.items()]
    for b in d.blocks:
        if b[0] == "p":
            _, style, rs, opt = b
            out.append(f"{HEAD_TAG.get(style) or ('QUOTE' if opt.get('quote') else 'SRC' if opt.get('small') else 'P')} {render(rs)}")
        elif b[0] == "list":
            for rs in b[2]:
                lvl = 2 if rs and rs[0][0].startswith("\t") else 1
                out.append(f"{'OL' if b[1] else 'UL'}{lvl} {render([(rs[0][0].lstrip(chr(9)), rs[0][1])] + rs[1:] if rs else rs)}")
        elif b[0] == "code":
            out.append("CODE " + b[1].replace("\n", "⏎").strip())
        elif b[0] == "image":
            out += [f"IMG {ptr(b[3])}pt"] + ([f"CAPTION {b[2]}"] if b[2] else [])
        elif b[0] == "table":
            _, rows, cap, widths = b
            out += ([f"CAPTION {cap}"] if cap else []) + [f"TABLE {len(rows)}x{len(rows[0])} " + ("/".join(str(ptr(x)) for x in widths) if widths else "均等")]
            out += ["ROW " + " | ".join(render(plain(c) if r == 0 else c) for c in row) for r, row in enumerate(rows)]  # 見出しの行の太字は表が付ける
        elif b[0] == "break":
            out.append("BREAK")
        elif b[0] == "cover":
            out += [f"TITLE {t}" for t in b[1]]
            if b[3]:
                out.append(f"COVER {b[2] or ''} IMG {ptr(70)}pt")
            elif b[2]:  # ロゴがなければ、左の語は中央寄せの段落
                out.append(f"CAPTION {b[2]}")
    return out


def hexc(c):
    rgb = (c or {}).get("color", {}).get("rgbColor", {})
    return "".join(f"{round(rgb.get(k, 0) * 255):02X}" for k in ("red", "green", "blue"))


def mmr(v):
    return round(v * 25.4 / 72)


def ptr(v):  # 幅は pt の整数で比べる（mm の 0.5 の丸めが両側で割れる）
    return round(mm(v)["magnitude"])


def runs_of(p, flat=False):
    """組んだ文書の段落の文字を (文字, 書式) の並びにする。書式は太字・赤（RED_TEXT の太字）・リンク・MONO だけ見る（render と同じ）。"""
    rs = []
    for x in p.get("elements", []):
        t = x.get("textRun")
        text = t and t["content"].replace("\n", "")
        if not text:
            continue
        ts, st = t.get("textStyle", {}), {}
        if not flat:
            if ts.get("bold") is True:
                st["bold"] = True
                if hexc(ts.get("foregroundColor")) == RED_TEXT:
                    st["red"] = True
            if ts.get("link", {}).get("url"):
                st["link"] = {"url": ts["link"]["url"]}
            if ts.get("weightedFontFamily", {}).get("fontFamily") == MONO:
                st["code"] = True
        if rs and rs[-1][1] == st:
            rs[-1] = (rs[-1][0] + text, st)
        else:
            rs.append((text, st))
    return rs


def canon_json(doc):
    """組んだ文書（documents.get の JSON）を、canon_doc と同じ形にする。書式で塊の種類を見分ける（引用は左の線、コードは塗り、題は中央）。"""
    st, objs, lists = doc["documentStyle"], doc.get("inlineObjects", {}), doc.get("lists", {})
    g = lambda k: st.get(k, {}).get("magnitude", 72)
    out = [f"PAGE {mmr(st['pageSize']['width']['magnitude'])}x{mmr(st['pageSize']['height']['magnitude'])} 余白 {mmr(g('marginTop'))}/{mmr(g('marginLeft'))}"]
    ns = {x["namedStyleType"]: x.get("textStyle", {}) for x in doc["namedStyles"]["styles"]}
    for n in STYLES:
        ts = ns.get(n, {})
        out.append(style_line(n, ts.get("weightedFontFamily", {}).get("fontFamily"), ts.get("fontSize", {}).get("magnitude", 0), ts.get("bold") is True,
                              hexc(ts.get("foregroundColor"))))
    for e in doc["body"]["content"]:
        if "table" in e:
            t = e["table"]
            cps = t.get("tableStyle", {}).get("tableColumnProperties", [])
            fixed = cps and all(c.get("widthType") == "FIXED_WIDTH" for c in cps)
            out.append(f"TABLE {t['rows']}x{t['columns']} " + ("/".join(str(round(c["width"]["magnitude"])) for c in cps) if fixed else "均等"))
            out += ["ROW " + " | ".join(" ".join(render(runs_of(x["paragraph"], flat=r == 0)) for x in c["content"] if "paragraph" in x).strip()
                                        for c in row["tableCells"]) for r, row in enumerate(t["tableRows"])]
            continue
        p = e.get("paragraph")
        if not p:
            continue
        if any("pageBreak" in x for x in p["elements"]):
            out.append("BREAK")
        text = render(runs_of(p))
        img = next((x["inlineObjectElement"]["inlineObjectId"] for x in p["elements"] if "inlineObjectElement" in x), None)
        if img:
            w = round(objs[img]["inlineObjectProperties"]["embeddedObject"]["size"]["width"]["magnitude"])
            out.append(f"COVER {text} IMG {w}pt" if text else f"IMG {w}pt")
            continue
        if not text:
            continue
        ps, nst = p["paragraphStyle"], p["paragraphStyle"].get("namedStyleType", "NORMAL_TEXT")
        small = any(x.get("textRun", {}).get("textStyle", {}).get("fontSize", {}).get("magnitude") == SMALL_PT for x in p["elements"])
        if "bullet" in p:
            lvl = p["bullet"].get("nestingLevel", 0)
            gl = lists.get(p["bullet"]["listId"], {}).get("listProperties", {}).get("nestingLevels", [{}] * (lvl + 1))[lvl]
            out.append(f"{'OL' if gl.get('glyphType') not in (None, 'GLYPH_TYPE_UNSPECIFIED', 'NONE') else 'UL'}{lvl + 1} {text}")
        elif nst in HEAD_TAG:
            out.append(f"{HEAD_TAG[nst]} {text}")
        elif ps.get("shading", {}).get("backgroundColor", {}).get("color"):
            out.append("CODE " + render(runs_of(p, flat=True)))
        elif ps.get("borderLeft", {}).get("width", {}).get("magnitude"):
            out.append(f"QUOTE {text}")
        elif ps.get("alignment") == "CENTER":
            out.append(f"CAPTION {text}")
        else:
            out.append(f"{'SRC' if small else 'P'} {text}")
    return out


def fidelity(d, doc):
    """doc.md（組む前の Doc）と組んだ文書の差。戻り: unified diff の行（- は doc.md、+ は組んだ文書）。"""
    return [x for x in difflib.unified_diff(canon_doc(d), canon_json(doc), n=0, lineterm="") if not x.startswith(("---", "+++"))]


def outline(d):
    """H1 ごとの (見出し, 表の見出しの行の並び)。"""
    secs = []
    for b in d.blocks:
        if b[0] == "p" and b[1] == "HEADING_1":
            secs.append((render(b[2]), []))
        elif b[0] == "table" and secs:
            secs[-1][1].append([render(plain(c)) for c in b[1][0]])
    return secs


def texts(d):
    for b in d.blocks:
        if b[0] == "cover":
            yield from ((False, x) for x in b[1] + [b[2] or ""])
        elif b[0] == "p":
            yield b[3].get("quote", False), render(b[2])
        elif b[0] == "list":
            yield from ((False, render(rs)) for rs in b[2])
        elif b[0] == "table":
            yield from ((False, render(c)) for row in b[1] for c in row)


def conform(d, t):
    """doc.md をテンプレートと比べる（template: に書いた名前）。戻り: (要修正, 要確認)。
    見るもの: テンプレートの H1 の節があるか（外すなら頭の omit: に書く）と順、節の中の表の列（[会社名] などの札は何にでも合う）、表紙とテーマ、
    残った書き手への注記（> <担当: …>）とテンプレートの札（[会社名] など、リンクでない [ ]）。"""
    hard, soft, omit = [], [], d.meta.get("omit") or []
    ds, ts = outline(d), outline(t)
    dn, tn = [x for x, _ in ds], [x for x, _ in ts]
    for name, heads in ts:
        if name not in dn:
            (soft if name in omit else hard).append(f"テンプレートの節「{name}」がない" + ("（omit: に書いてある）" if name in omit else "。外すなら頭の omit: に書く"))
            continue
        mine = dict(ds)[name]
        for h in heads:
            pat = [re.compile(".+".join(map(re.escape, re.split(r"\s*\[[^\]]*\]\s*", c)))) for c in h]  # 札と、その前後の空白は何にでも合う
            if not any(len(x) == len(h) and all(p.fullmatch(c) for p, c in zip(pat, x)) for x in mine):
                hard.append(f"節「{name}」に、テンプレートの表と同じ列（{'・'.join(h)}）の表がない")
    common = [x for x in dn if x in tn]
    if common != [x for x in tn if x in dn]:
        soft.append("節の順がテンプレートと違う: " + " → ".join(common))
    soft += [f"テンプレートにない節「{x}」" for x in dn if x not in tn]
    if any(b[0] == "cover" for b in t.blocks) != any(b[0] == "cover" for b in d.blocks):
        hard.append("表紙の有無がテンプレートと違う")
    if d.meta.get("theme") != t.meta.get("theme"):
        hard.append(f"テーマ {d.meta.get('theme')} がテンプレートのテーマ {t.meta.get('theme')} と違う")
    for quote, x in texts(d):
        if quote and x.startswith("<"):
            hard.append(f"書き手への注記が残っている: {x[:30]}")
        hard += [f"テンプレートの札が残っている: {m.group()}（「{x[:20]}…」）" for m in re.finditer(r"\[[^\]\n]{1,30}\](?!\()", x)]
    return hard, soft


def skeleton(doc):
    """節ごとの骨組み（箇条書きの段ごとの項目の数、表の大きさ、図の数）。言葉の違う版どうし（元の英語版と訳したテンプレートなど）を比べる。
    節は、文字のある見出しのうち、いちばん上の段で分ける（英語版は H2、訳した版は H1）。頭（最初の節の前）は表紙。"""
    heads = [p["paragraphStyle"]["namedStyleType"] for e in doc["body"]["content"] if (p := e.get("paragraph"))
             and p["paragraphStyle"].get("namedStyleType", "").startswith("HEADING_") and render(runs_of(p, flat=True))]
    top = min(heads, default="HEADING_1")
    secs = [["（表紙）", Counter()]]
    for e in doc["body"]["content"]:
        if "table" in e:
            secs[-1][1][f"表 {e['table']['rows']}×{e['table']['columns']}"] += 1
        elif p := e.get("paragraph"):
            text = render(runs_of(p, flat=True))
            if p["paragraphStyle"].get("namedStyleType") == top and text:
                secs.append([text, Counter()])
            elif "bullet" in p:
                secs[-1][1][f"箇条書き {p['bullet'].get('nestingLevel', 0) + 1} 段目"] += 1
            if any("inlineObjectElement" in x for x in p["elements"]):
                secs[-1][1]["図"] += 1
    return [(n, "、".join(f"{k} {v}" for k, v in sorted(c.items())) or "なし") for n, c in secs]


def compare_skeleton(a, b):
    """元（a）と組んだ版（b）の骨組みを、節の順に並べて違うところを出す。"""
    return [f"節 {i}: 元「{x[0][:24] if x else '（なし）'}」{x[1] if x else ''} ／ 組んだ版「{y[0][:24] if y else '（なし）'}」{y[1] if y else ''}"
            for i, (x, y) in enumerate(zip_longest(a, b)) if not (x and y and x[1] == y[1])]


def source_dir(did):
    """照合の相手の doc.md があるフォルダ。今いるフォルダになければ、build が文書に残したフォルダ（SRC）。"""
    if os.path.isfile("doc.md"):
        return os.getcwd()
    rel = request("GET", f"{DRIVE}/files/{did}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(SRC)
    p = rel and os.path.join(gapi.factory_path().parent, rel)
    return p if p and os.path.isfile(os.path.join(p, "doc.md")) else None


def built_fonts(did):
    """build が文書に残した (本文, 等幅) の書体（FONTS）。残していない文書は、テーマで書体を変えられる前の版で組んだものなので、既定の書体。"""
    v = request("GET", f"{DRIVE}/files/{did}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(FONTS, "")
    return tuple(v.split("\t")) if v.count("\t") == 1 else (FONT_DEFAULT, MONO_DEFAULT)


def source_checks(doc, d):
    """doc.md と比べる（doc.md と組んだ文書の照合、テンプレートとの照合、元の文書との骨組みの比較）。戻り: 要修正があるか。"""
    if not d:
        print("\n== 要確認（照合）: doc.md が見つからないので、doc.md とテンプレートとの照合をしなかった。資料の build/ で動かすか、組み直す ==")
        return False
    if d.name.split("｜")[0] not in doc["title"]:
        print(f"\n（doc.md の name「{d.name}」が文書の名前「{doc['title']}」にないので、照合をしなかった。資料の build/ で動かしているか）")
        return False
    diff = fidelity(d, doc)
    print(f"\n== 要修正（doc.md と組んだ文書の差。- が doc.md、+ が組んだ文書）: {sum(x[0] in '+-' for x in diff)} ==")
    if diff:
        print("\n".join(diff[:60]) + ("\n…" if len(diff) > 60 else ""))
    hard = bool(diff)
    if d.meta.get("template"):
        h, soft = conform(d, from_md(template_md(d.meta["template"]), apply_theme=False))
        print(f"\n== 要修正（テンプレート {d.meta['template']} との照合）: {len(h)} ==", *h, sep="\n")
        print(f"\n== 要確認（テンプレートとの照合）: {len(soft)} ==", *soft, sep="\n")
        hard = hard or bool(h)
    if d.meta.get("source"):  # 頭の skeleton_ok: に「<組んだ版の節の名前>: <理由>」と書いた節の違いは、認めたものとして数だけ出す
        ok = {x.split(": ", 1)[0] for x in d.meta.get("skeleton_ok") or []}
        diff = compare_skeleton(skeleton(request("GET", f"{DOCS}/{file_id(d.meta['source'])}")), skeleton(doc))
        left = [x for x in diff if re.search(r"組んだ版「(.*?)」", x)[1] not in ok]
        print(f"\n== 要確認（元の文書との骨組みの違い。{d.meta['source']}）: {len(left)}（skeleton_ok: で認めた違い {len(diff) - len(left)}）==", *left, sep="\n")
    return hard


def cmd_check(src):
    did = file_id(src)
    doc = request("GET", f"{DOCS}/{did}")
    d = f"/tmp/docs_{did[:8]}"
    os.makedirs(d, exist_ok=True)
    json.dump(doc, open(f"{d}/doc.json", "w", encoding="utf-8"), ensure_ascii=False)
    open(f"{d}/text.md", "w", encoding="utf-8").write(text_of(doc))
    print(doc["title"] + "\n")
    src = source_dir(did)
    if src:  # 画像のパスは build/ からなので、そこで読む（出力は /tmp に書く）
        os.chdir(src)
    md = load_doc() if src else None
    font, mono = built_fonts(did)  # 書体は組んだときのもの（doc.md のテーマではない）
    hard = doc_lint.lint_gdoc(doc, r := doc_lint.Report(), template=bool(md and (md.meta.get("template") or md.meta.get("source"))), font=font, mono=mono,
                         facts=textlint.load_facts() if src else None)  # テンプレートとその見本は、節の順をテンプレートが決める
    if not any(w in doc["title"].lower() for w in ("tmp", "template", "作業用", "テンプレート")):  # 一時の文書は数えない（gslides.py と同じ）
        textlint.log_run(r, did)
    for f in glob.glob(f"{d}/p-*.png"):
        os.remove(f)
    open(f"{d}/doc.pdf", "wb").write(request("GET", f"{DRIVE}/files/{did}/export?mimeType=application/pdf", binary=True))
    subprocess.run(["pdftoppm", "-png", "-r", "110", f"{d}/doc.pdf", f"{d}/p"], check=True)  # Google が描いたページ（A4 で 910 × 1286）
    subprocess.run(["pdftotext", "-bbox-layout", f"{d}/doc.pdf", f"{d}/bbox.html"], check=True)  # 行と語の位置（doc_layout.py が読む）
    fonts = subprocess.run(["pdffonts", f"{d}/doc.pdf"], capture_output=True, text=True).stdout.splitlines()[2:]
    names = sorted({re.sub(r"^[A-Z]{6}\+", "", x.split()[0]).split("-")[0] for x in fonts})
    print(f"\nPDF の書体: {', '.join(names)}（箇条書きの記号と番号は Arial になる。API で変えられない）")
    lay = subprocess.run(["uv", "run", "-q", os.path.join(os.path.dirname(os.path.abspath(__file__)), "doc_layout.py"), f"{d}/doc.json", d],
                         capture_output=True, text=True)  # ページの末尾の見出し・余白へのはみ出し・下の空きは、Google が描いたページで測る（Pillow が要るので uv）
    print(lay.stdout.rstrip() if lay.returncode == 0 else f"\n（doc_layout.py が止まった: {lay.stderr.strip()[-300:]}）")
    hard = source_checks(doc, md) or hard
    pages = sorted(glob.glob(f"{d}/p-*.png"))
    print(f"\nテキスト: {d}/text.md\n画像: {d}/p-N.png（{len(pages)} ページ）\nJSON: {d}/doc.json")
    if hard:
        sys.exit("要修正が残っている（上の出力を直す）")


def cmd_export(src, out):
    mime = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pdf": "application/pdf"}[os.path.splitext(out)[1]]
    open(out, "wb").write(request("GET", f"{DRIVE}/files/{file_id(src)}/export?mimeType={mime}", binary=True))
    print(out)


def selftest():
    assert runs("**太字**と[リンク](https://a.b/c)と`x=1`") == [("太字", {"bold": True}), ("と", {}), ("リンク", {"link": {"url": "https://a.b/c"}}), ("と", {}),
                                                                ("x=1", {"code": True})]
    assert runs("ふつう") == [("ふつう", {})] and runs("") == []
    # スライドと同じ記法: 赤の太字、中のリンクとコード、記号そのもの（slides.py の spec_md）
    assert runs("a***b[c](https://x)***\\*d") == [("a", {}), ("b", {"bold": True, "red": True}), ("c", {"bold": True, "red": True, "link": {"url": "https://x"}}), ("*d", {})]
    assert runs("**`x`**") == [("x", {"bold": True, "code": True})] and render(runs("***赤*** と **太**")) == "***赤*** と **太**"
    w = Writer(1)
    w.text(runs("***赤***"))
    assert w.reqs[-1]["updateTextStyle"]["textStyle"] == {"bold": True, "foregroundColor": color(RED_TEXT)}
    link = {"elements": [{"textRun": {"content": "出典: "}}, {"textRun": {"content": "docs", "textStyle": {"link": {"url": "https://d"}}}}, {"textRun": {"content": "\n"}}]}
    assert md_text(link) == "出典: [docs](https://d)\n"
    assert footer_text("A｜Internal Only").endswith("｜Internal Only") and footer_text("A") == COPYRIGHT
    w = Writer(1)
    w.text(runs("あ**い**"))  # 「あい\n」は 3 単位。太字は 2〜3
    assert w.cur == 4 and w.reqs[0]["insertText"] == {"location": {"index": 1}, "text": "あい\n"}
    assert w.reqs[-1]["updateTextStyle"]["range"] == {"startIndex": 2, "endIndex": 3}
    w = Writer(10)
    w.block(("code", "a = 1\nprint(a)"), {})
    assert w.cur == 10 + u16("a = 1\vprint(a)\n") and any("shading" in r.get("updateParagraphStyle", {}).get("paragraphStyle", {}) for r in w.reqs)
    w = Writer(1)
    w.block(("list", False, [runs("a"), runs("\tb")]), {})  # 2 段目のタブは消えるので、次の位置は「a\nb\n」の後ろ
    assert w.cur == 1 + u16("a\nb\n")
    w = Writer(1)
    w.text(runs("**`x`**"))  # コードの中の太字も入れる
    assert [r["updateTextStyle"]["textStyle"] for r in w.reqs[-2:]] == [{**font(MONO), "fontSize": pt(CODE_PT)}, {"bold": True}]
    w = Writer(5)
    w.block(("image", "u", "図 1　構成", 100), {"u": "https://x/y.png"})
    assert w.reqs[1]["insertInlineImage"]["location"]["index"] == 5 and w.cur == 5 + 2 + u16("図 1　構成\n")
    d = Doc("t")
    d.table([["a", "b"], ["c"]], caption="比べる", widths=[80, 80])  # 幅は本文の幅に合わせて縮め、足りないセルは空にする
    assert d.blocks[0][1][1][1] == [] and d.blocks[0][2] == "表 1　比べる" and d.blocks[0][3] == [TEXT_MM / 2] * 2 and not d.warnings
    d.table([["a", "b"]], widths=[10, 20, 30])  # 列の数に合わない幅は均等に
    assert d.blocks[1][3] is None and d.warnings
    d.p("次のとおりです。")
    d.bullets(["a", "b"])  # 前置きの段落は、箇条書きと同じページに置く
    assert d.blocks[2][3] == {"keep": True}
    md_selftest()
    mermaid_selftest()
    # テーマ: 書いた値だけを入れ替え、本文の幅に合わせて図の倍率も変える（最後に試す。あとの試しに効くので）
    rest = STYLES["HEADING_1"][3:]  # 書かなければ、見出しの上下の空きと行間は既定のまま
    load_theme({"page": [215.9, 279.4], "margins": [12.7, 12.7], "colors": {"HEAD": "4a86e8", "TABLE_HEAD": "F3F3F3", "TABLE_HEAD_TEXT": TEXT},
                "styles": {"BODY": {"size": 10}, "H1": {"size": 12}, "H2": {"size": 11}, "H3": {"size": 10.5, "color": "303F47", "above": 6, "spacing": 90}}})
    assert PAGE_MM == (215.9, 279.4) and TEXT_MM == 190.5 and STYLES["NORMAL_TEXT"][:3] == (10, False, TEXT) and STYLES["HEADING_2"][:3] == (11, True, "4A86E8")
    assert TABLE_HEAD == ("F3F3F3", TEXT) and STYLES["HEADING_1"][3:] == rest and STYLES["TITLE"][2] == "4A86E8"  # 題も HEAD の色
    assert STYLES["HEADING_3"] == (10.5, True, "303F47", 6, 4, 90) and mermaid_config()["themeVariables"]["primaryBorderColor"] == "#4A86E8"
    assert (FONT, MONO) == ("Noto Sans JP", "Cascadia Mono")  # 書かなければ既定の書体
    tmp = tempfile.mkdtemp()  # テーマのファイルの確かめ
    put = lambda o, name="t": (open(f := os.path.join(tmp, f"{name}.json"), "w").write(json.dumps({"apiVersion": API_VERSION, "kind": "theme", **o})), f)[1]
    assert read_theme(put({"description": "d", "styles": {"H1": {"size": 14, "above": 0}}}))["styles"]["H1"]["above"] == 0
    for o, want in (({"leading": 1.3}, "leading: 知らないキー"), ({"colors": {"NAVY": "000000"}}, "colors.NAVY: 知らない役割"), ({"colors": {"TEXT": "#303F47"}}, "6 桁"),
                    ({"styles": {"H4": {}}}, "styles.H4"), ({"styles": {"H1": {"size": 0, "bold": True}}}, "styles.H1.size: 0 以上"), ({"page": [210]}, "page:"),
                    ({"font": "Inter"}, "Inter")):
        try:
            read_theme(put(o))
            raise AssertionError(f"{o} を通した")
        except SystemExit as e:
            assert want in str(e), (o, str(e))
    globals()["ws_themes"], real_ws = (lambda: Path(tmp)), ws_themes  # 一覧は、書けない値のあるファイル（t.json は最後の試しの font: Inter）で止まらない
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        put({"description": "よい"}, "a")
        cmd_themes()
    assert "よい" in out.getvalue() and "使えない" in out.getvalue(), out.getvalue()
    globals()["ws_themes"] = real_ws
    real_cfg = docs_cfg
    globals()["docs_cfg"] = lambda: {"themes": {STANDARD: {"page": [215.9, 279.4]}}}  # 前の書き方の [docs.themes.standard] を黙って捨てない
    for bad in (lambda: read_theme(put({}, "a b")), lambda: theme("../x"), lambda: theme(STANDARD)):  # ファイルの名前、doc.md の theme: の名前、前の書き方
        try:
            bad()
            raise AssertionError("書けない名前を通した")
        except SystemExit:
            pass
    globals()["docs_cfg"] = real_cfg
    shutil.rmtree(tmp)
    load_theme({"font": "BIZ UDPGothic", "mono": "IBM Plex Mono"})
    w = Writer(1)
    w.mono(1, "a あ", 9)
    assert {r["updateTextStyle"]["textStyle"]["weightedFontFamily"]["fontFamily"] for r in w.reqs} == {"IBM Plex Mono"}  # テーマの mono で組む
    assert any(x["textStyle"]["weightedFontFamily"]["fontFamily"] == "BIZ UDPGothic" for r in style_reqs() if "updateNamedStyle" in r for x in [r["updateNamedStyle"]["namedStyle"]])
    for bad in ({"font": "Inter"}, {"font": ["BIZ UDPGothic"]}, {"mono": "Fira Code"}):
        try:
            load_theme(bad)
            raise AssertionError(f"{bad} を通した")
        except SystemExit:
            pass
    got = lambda props: (globals().__setitem__("request", lambda *a, **k: {"appProperties": props}), built_fonts("x"))[1]
    assert got({FONTS: "BIZ UDPGothic\tIBM Plex Mono"}) == ("BIZ UDPGothic", "IBM Plex Mono") and got({}) == ("Noto Sans JP", "Cascadia Mono") != (FONT, MONO)  # 組んだときの書体。印のない文書は、入れたテーマによらず既定
    print("selftest ok")


def md_selftest():
    """doc.md の読み取り、doc.md と組んだ文書の照合（canon_doc と canon_json）、テンプレートとの照合。"""
    import tempfile
    tmp = tempfile.mkdtemp()
    md = os.path.join(tmp, "doc.md")
    open(md, "w", encoding="utf-8").write("""---
name: 試し｜Internal Only
template: t
---
<!-- 覚え書き -->
# 1. 要旨

一文目です。
二文目は **太字** と [リンク](https://a.b/c) と ***赤*** です。

Unity
Catalog

- 一つ目
  - 二段目
    の続き

1. 番号

> 引用<br>二行目

表: 比べる {widths: 1 3}
| 項目 | 中身 \\| 縦線 |
|---|---|
| a<br>b |  |

出典: [docs](https://d)

![構成](https://x/y.png){width=100}

```
a = 1
```

\\newpage
""")
    d = from_md(md)
    kinds = [b[0] for b in d.blocks]
    assert kinds == ["p", "p", "p", "list", "list", "p", "table", "p", "image", "code", "break"], kinds
    assert d.blocks[2][2] == [("Unity Catalog", {})]  # 英数字の行どうしは空白でつなぐ
    assert [render(x) for x in d.blocks[3][2]] == ["一つ目", "二段目の続き"] and d.blocks[3][2][1][0][0].startswith("\t") and d.blocks[4][1]
    assert d.blocks[5][3] == {"quote": True} and d.blocks[5][2][0][0] == "引用\v二行目"
    assert d.blocks[6][2] == "表 1　比べる" and d.blocks[6][3] == [TEXT_MM / 4, TEXT_MM * 3 / 4] and d.blocks[6][1][0][1] == [("中身 | 縦線", {})]
    assert d.blocks[7][3] == {"small": True} and d.blocks[8][3] == 100 and d.meta["template"] == "t" and not d.warnings
    c = canon_doc(d)
    assert "P 一文目です。二文目は **太字** と [リンク](https://a.b/c) と ***赤*** です。" in c and "UL2 二段目の続き" in c and "ROW a⏎b | " in c, c
    # 組んだ文書の JSON（必要なところだけ）から同じ形が作れるか
    run = lambda t, **st: {"textRun": {"content": t, "textStyle": st}}
    para = lambda els, **ps: {"paragraph": {"elements": els, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", **ps}}}
    doc = {"documentStyle": {"pageSize": {"width": {"magnitude": 595.3}, "height": {"magnitude": 841.9}}, "marginTop": {"magnitude": 70.87}, "marginLeft": {"magnitude": 85.04}},
           "namedStyles": {"styles": []}, "lists": {"L": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL"}]}}},
           "inlineObjects": {"i": {"inlineObjectProperties": {"embeddedObject": {"size": {"width": {"magnitude": 283.46}}}}}},
           "body": {"content": [para([run("1. 要旨\n")], namedStyleType="HEADING_1"),
                                para([run("二文目は "), run("太字", bold=True), run(" と "), run("リンク", link={"url": "https://a.b/c"}), run(" と "),
                                      run("赤", bold=True, foregroundColor=color(RED_TEXT)), run(" です。\n")]),
                                {"paragraph": {"elements": [run("番号\n")], "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "bullet": {"listId": "L"}}},
                                para([run("引用\v二行目\n")], borderLeft={"width": {"magnitude": 3}}),
                                para([run("表 1　比べる\n", fontSize={"magnitude": SMALL_PT})], alignment="CENTER"),
                                {"table": {"rows": 1, "columns": 2, "tableStyle": {"tableColumnProperties": [{"widthType": "FIXED_WIDTH", "width": {"magnitude": 106.3}}] * 2},
                                           "tableRows": [{"tableCells": [{"content": [para([run("項目\n", bold=True)])]}, {"content": [para([run("\n")])]}]}]}},
                                para([run("出典: ", fontSize={"magnitude": SMALL_PT}), run("docs", link={"url": "https://d"}, fontSize={"magnitude": SMALL_PT}), run("\n")]),
                                para([{"inlineObjectElement": {"inlineObjectId": "i"}}, run("\n")], alignment="CENTER"),
                                para([run("a = 1\n", weightedFontFamily={"fontFamily": MONO})], shading={"backgroundColor": {"color": {"rgbColor": {"red": 0.9}}}}),
                                para([{"pageBreak": {}}, run("\n")])]}}
    assert canon_json(doc)[len(STYLES) + 1:] == ["H1 1. 要旨", "P 二文目は **太字** と [リンク](https://a.b/c) と ***赤*** です。", "OL1 番号", "QUOTE 引用⏎二行目",
                                                 "CAPTION 表 1　比べる", "TABLE 1x2 106/106", "ROW 項目 | ", "SRC 出典: [docs](https://d)", "IMG 283pt", "CODE a = 1",
                                                 "BREAK"], canon_json(doc)
    assert canon_json(doc)[0] == "PAGE 210x297 余白 25/30" == canon_doc(d)[0]
    # 表紙: ロゴ（[brand] logo）がなければ、左の語は中央寄せの段落になる
    for logo, want in ((None, ["TITLE 題", "CAPTION Acme 株式会社", "BREAK"]), ("https://a.b/logo.png", ["TITLE 題", f"COVER Acme 株式会社 IMG {ptr(70)}pt", "BREAK"])):
        cv = Doc("c")
        cv.cover(["題"], "Acme 株式会社", logo=logo)
        assert canon_doc(cv)[len(STYLES) + 1:] == want, canon_doc(cv)
    # テンプレートとの照合: 節がない・表の列が違う・札と注記が残る、は要修正。札は列の照合では何にでも合う
    t = Doc("t")
    t.h1("1. 要旨")
    t.table([["[会社名] の担当", "状態"]])
    t.h1("2. 範囲")
    d2 = Doc("d")
    d2.h1("1. 要旨")
    d2.table([["Acme 様の担当", "状態"]])
    d2.quote("<担当: SA>")
    d2.p("[氏名] が書く")
    hard, soft = conform(d2, t)
    assert len(hard) == 3 and "2. 範囲" in hard[0] and "注記" in hard[1] and "[氏名]" in hard[2] and not soft, (hard, soft)
    d2.meta["omit"] = ["2. 範囲"]
    d2.blocks = d2.blocks[:2]
    assert conform(d2, t) == ([], ["テンプレートの節「2. 範囲」がない（omit: に書いてある）"])
    shutil.rmtree(tmp)


def mermaid_selftest():
    """```mermaid の読み取りと幅。描くところ（mermaid_png）は仮の PNG にする（selftest は Node.js なしで回る）。"""
    global mermaid_png
    tmp, real = tempfile.mkdtemp(), mermaid_png
    fake = lambda mm: (lambda code: (open(f := os.path.join(tmp, f"{mm}.png"), "wb").write(b"\x89PNG\r\n\x1a\n" + bytes(8) + round(mm / 25.4 * 96 * MERMAID_SCALE).to_bytes(4, "big")), f)[1])
    md = os.path.join(tmp, "doc.md")
    open(md, "w", encoding="utf-8").write("---\nname: 図\n---\n図: 流れ {width: 100}\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n```mermaid\nflowchart TB\n  A\n```\n\n図: 浮いた題\n\n本文\n")
    try:
        mermaid_png = fake(80)  # 文字を本文の大きさで描くと 80 mm の図
        d = from_md(md)
        assert [b[0] for b in d.blocks] == ["image", "image", "p", "p"] and d.blocks[0][2:] == ("図 1　流れ", 100) and d.blocks[1][2:] == (None, 80), d.blocks
        assert render(d.blocks[2][2]) == "図: 浮いた題" and not d.warnings  # 次が ```mermaid でない「図: 」は本文の行のまま（落とさない）
        assert [b[0] for b in from_md(md, apply_theme=False).blocks] == ["p", "p"]  # テンプレートとして照合に読むときは描かない
        mermaid_png = fake(200)  # 本文の幅より広い図は本文の幅に縮め、文字が 9pt 未満になるなら警告する
        d = Doc("w")
        d.mermaid("x")
        assert d.blocks[0][3] == TEXT_MM and "9pt 未満" in d.warnings[0]
    finally:
        mermaid_png = real
        shutil.rmtree(tmp)
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:  # 描いたものがあれば、mermaid-cli を呼ばない
        cfg = mermaid_config()
        out = os.path.join(MERMAID_DIR, hashlib.sha1(json.dumps(["A", cfg, MERMAID_SCALE, MERMAID_CLI], ensure_ascii=False).encode()).hexdigest()[:12] + ".png")
        os.makedirs(MERMAID_DIR)
        open(out, "wb").close()
        assert mermaid_png("A") == out
    finally:
        shutil.rmtree(os.getcwd())
        os.chdir(cwd)


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        return selftest()
    if a[:1] == ["check"] and len(a) == 2:
        return cmd_check(a[1])
    if a[:1] == ["export"] and len(a) == 3:
        return cmd_export(a[1], a[2])
    if a[:1] == ["init"] and len(a) == 2:
        return cmd_init(a[1])
    if a == ["themes"]:
        return cmd_themes()
    if not (a[:1] == ["build"] and len(a) >= 2 or a[:1] == ["new"] and len(a) == 3):
        sys.exit(__doc__)
    doc = load_doc()
    if a[0] == "build":
        return build(file_id(a[1]), doc, "--force" in a)
    need_brand()  # 作る前に止める（build でも止まる）
    need_theme(doc)
    did = new(a[1], a[2])
    try:
        build(did, doc, force=True)  # 作ったばかりなので、画面での直しもコメントもない
    except BaseException:  # 組めなかった文書を残さない。直してから new をやり直す
        trash(did)
        print(f"組めなかったので、作った文書 {did} をゴミ箱に移した", file=sys.stderr)
        raise


if __name__ == "__main__":
    run(main)
