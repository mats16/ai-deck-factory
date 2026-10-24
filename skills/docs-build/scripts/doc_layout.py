# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""usage: uv run -q doc_layout.py <doc.json> <docs.py check のフォルダ>   （--selftest で自己確認）
Google が描いたページ（Drive の PDF の書き出し。p-N.png と、pdftotext -bbox-layout の行の位置 bbox.html）で、
JSON では分からないレイアウトの欠陥を測る（../visual.md の 4）。docs.py check が呼ぶ。
- ページの末尾に残った見出し（見出しは次の段落と同じページに置くスタイルにしてあるので、出たら書式が外れている）
- 行頭の約物（Google Docs は前の字ごと次の行に追い出すので、ふつうは出ない）
- 1〜2 字だけの最終行（見出し・図表の題・表のセルなど、短い段落だけ）
- 左右の余白に描かれたもの（幅を決めた表、大きな図、左の線）
- 下が大きく空いたページ（最後のページと、次のページが H1 で始まるページは除く）"""
import glob, json, re, sys
import xml.etree.ElementTree as ET

from PIL import Image

sys.dont_write_bytecode = True

INK = 235  # これより暗い画素を、描かれたものとみなす（罫線 DCE0E2 は数え、コードの地 EEEDE9 は数えない）
EDGE_PX = 6  # 余白へのはみ出しとみなす幅（px。110 dpi で 1.4 mm）
EMPTY_FRAC = 0.3  # 本文の領域の下がこれ以上空いたら出す
SHORT_MAX = 80  # 1〜2 字だけの最終行を見る段落の字数の上限
HEAD_PUNCT = "、。，．）」』】〕〉》：；？！"  # 行頭に置かない約物（JIS X 4051 の行頭禁則のうち、和文で出るもの）


def pages_of(path):
    """bbox.html を読む。戻り: ページごとに (幅, 高さ, ブロックの並び)。ブロックは行の並び、行は (上, 下, 文字)。位置は pt。"""
    root = ET.fromstring(re.sub(r'\sxmlns="[^"]+"', "", open(path, encoding="utf-8").read(), count=1))
    out = []
    for pg in root.iter("page"):
        blocks = [[(float(ln.get("yMin")), float(ln.get("yMax")), "".join(w.text or "" for w in ln.iter("word"))) for ln in b.iter("line")]
                  for b in pg.iter("block")]
        out.append((float(pg.get("width")), float(pg.get("height")), [b for b in blocks if b]))
    return out


def squash(s):
    return re.sub(r"\s+", "", s)


def text_checks(pages, heads, h1, foot_top):
    """位置で見るもの。heads は見出しの文字（空白を除く）、h1 はそのうち H1、foot_top はフッターの上端（pt）。"""
    hits = []
    for i, (w, h, blocks) in enumerate(pages, 1):
        body = [b for b in blocks if b[0][0] < foot_top]
        for b in body:
            for k, (_, _, t) in enumerate(b):
                if t and t[0] in HEAD_PUNCT:
                    hits.append(("行頭の約物", f"p{i}: 「{t[:16]}」"))
            # 見出し・図表の題・表のセルなど短い段落（2 行・80 字まで）だけを見る。本文の段落の最終行は直さない（../visual.md の 5）
            if 2 <= len(b) and len(squash("".join(t for _, _, t in b))) <= SHORT_MAX and 0 < len(squash(b[-1][2])) <= 2:
                hits.append(("1〜2 字だけの最終行", f"p{i}: 「…{b[-2][2][-10:]}／{b[-1][2]}」"))
        if i < len(pages) and body:
            last = squash("".join(t for _, _, t in body[-1]))
            if any(last == x or (len(x) >= 4 and last.startswith(x)) for x in heads):
                hits.append(("ページの末尾の見出し", f"p{i}: 「{body[-1][0][2][:20]}」。見出しの段落の「次の段落と分離しない」が外れていないか"))
    return hits


def ink_checks(img, margin, top, foot_top_px, empty_ok):
    """画像で見るもの。margin は左右の余白、top は上の余白、foot_top_px はフッターの上端（いずれも px）。empty_ok は下が空いてよいページ。"""
    g = img.convert("L").point(lambda v: 255 if v < INK else 0)
    body = g.crop((0, top, g.width, foot_top_px))
    hits = []
    sides = [x.getbbox() for x in (body.crop((0, 0, margin - EDGE_PX, body.height)), body.crop((g.width - margin + EDGE_PX, 0, g.width, body.height)))]
    if any(sides):
        y = min(x[1] for x in sides if x) + top
        hits.append(("余白へのはみ出し", f"上から {y * 25.4 / 110:.0f} mm のところ。表の列の幅か図の幅を本文の幅に収める"))
    bb = body.getbbox()
    if not empty_ok and bb and (body.height - bb[3]) / body.height > EMPTY_FRAC:
        hits.append(("下が空いたページ", f"下の {(body.height - bb[3]) / body.height:.0%} が空き。次のページに送られた表や図がないか"))
    return hits


def main(doc_path, d):
    doc = json.load(open(doc_path, encoding="utf-8"))
    st = doc["documentStyle"]
    m_pt, top_pt = st.get("marginLeft", {}).get("magnitude", 72), st.get("marginTop", {}).get("magnitude", 72)
    foot_pt = st["pageSize"]["height"]["magnitude"] - st.get("marginBottom", {}).get("magnitude", 72) + 2  # 本文の下端（ここから下はフッター）
    heads, h1 = [], []
    for e in doc["body"]["content"]:
        p = e.get("paragraph")
        if p and p["paragraphStyle"].get("namedStyleType", "").startswith(("HEADING_", "TITLE")):
            t = squash("".join(x.get("textRun", {}).get("content", "") for x in p["elements"]))
            heads.append(t)
            if p["paragraphStyle"]["namedStyleType"] == "HEADING_1":
                h1.append(t)
    pages = pages_of(f"{d}/bbox.html")
    hits = text_checks(pages, heads, h1, foot_pt)
    imgs = sorted(glob.glob(f"{d}/p-*.png"), key=lambda f: int(re.search(r"(\d+)\.png$", f).group(1)))
    for i, f in enumerate(imgs, 1):
        img = Image.open(f)
        k = img.width / pages[i - 1][0]  # pt → px
        nxt = pages[i][2] if i < len(pages) else []
        empty_ok = i == len(imgs) or bool(nxt and squash(nxt[0][0][2]) in h1)
        hits += [(n, f"p{i}: {msg}") for n, msg in ink_checks(img, round(m_pt * k), round(top_pt * k), round(foot_pt * k), empty_ok)]
    print(f"\n== 要確認（画像で測った）: {len(hits)} ==")
    for n, msg in hits:
        print(f"[{n}] {msg}")


def selftest():
    pages = [(595, 842, [[(70, 80, "本文の一行目です。"), (82, 92, "す。")], [(100, 110, "あ" * 90), (112, 122, "い")], [(780, 790, "2.1いまの構成")]]),
             (595, 842, [[(70, 80, "、で始まる行"), (82, 92, "続きの行で終わる")]])]
    hits = text_checks(pages, ["2.1いまの構成"], [], 800)
    assert [n for n, _ in hits] == ["1〜2 字だけの最終行", "ページの末尾の見出し", "行頭の約物"], hits
    img = Image.new("L", (200, 300), 255)
    for x in range(30, 170):
        img.putpixel((x, 40), 0)  # 本文の上のほうに 1 本だけ（下が空く）
    assert [n for n, _ in ink_checks(img, 20, 20, 280, False)] == ["下が空いたページ"]
    img.putpixel((198, 50), 0)  # 右の余白に描かれた点
    assert [n for n, _ in ink_checks(img, 20, 20, 280, True)] == ["余白へのはみ出し"]
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(selftest() if a == ["--selftest"] else main(*a) if len(a) == 2 else __doc__)
