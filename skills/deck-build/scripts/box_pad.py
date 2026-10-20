# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""usage: uv run -q box_pad.py <deck.json> <画像のフォルダ> [ページ ...]   （--selftest で自己確認）
箱の中の文字と、箱の下端の間を、Google が描いたページの画像（gslides.py check の p-NN.png）で測る。
1 字分（その枠でいちばん小さい文字の大きさ）より狭いものを出す（visual.md の 4「枠と文字の間は 1 字分」）。
[box_pad-001] JSON の行の高さの見積もりは ±0.4 in ずれるので、画像で測る。
見るのは、塗りの箱の中にある、上寄せの 2 行以上の文字の枠と、白いカードの下端の真上にある 1 行の文字の枠。gslides.py check が呼ぶ。
もう 1 つ、1 つだけで置く淡色のパネル（白いカード・濃紺の箱・横に同じ高さの箱が並ぶものを除く）の上寄せの文字で、
下の空きが上の空きより SLACK_MIN 以上大きいものを出す（visual.md の 4。中央に置くか縮める。2026-10-10）。"""
import json, os, sys

from PIL import Image

sys.dont_write_bytecode = True  # scripts/ に __pycache__ を残さない（gslides.py と同じ）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint  # noqa: E402
import slides  # noqa: E402
from lint import EMU, INSET, flatten, paras, ptext, size_of, solid, text_lines  # noqa: E402

INK, EDGE, EDGE_FRAC = 60, 6, 0.85  # 淡色のパネル（EEEDE9）と地（F9F7F4）の差は 10 ほど。文字とみなす濃さの差、箱の端とみなす差と、行の中でその差がある画素の割合


def measure(img, x0, x1, y0, y1, y_max, margin=0, top=False, full=False):
    """列 x0〜x1 で、枠の上端 y0 から下へ、文字の最後の行と箱の端（ほぼ全部の画素が地と違う行）を探し、その間（px）を返す。
    top=True なら、(その間, 文字の最初の行の y（px）) を返す（上寄せの文字の上と下の空きを比べるため）。
    地の色は、枠の上 4 割の画素でいちばん多い値（枠が箱の下からはみ出していても、上は箱の中にある）。"""
    w = x1 - x0
    off = max(0, y0 - 200)
    rows = [list(img.crop((x0, y, x1, y + 1)).get_flattened_data()) for y in range(off, min(img.height, y_max))]
    sample = [v for r in rows[y0 - off: y0 - off + max(1, int((y1 - y0) * 0.4))] for v in r[:: max(1, w // 40)]]
    bg = max(set(sample), key=sample.count)
    edge = lambda r: sum(abs(v - bg) > EDGE for v in r) >= EDGE_FRAC * w
    ink = lambda r: any(abs(v - bg) > INK for v in r)
    k0 = y0 - off
    first = next((k for k in range(k0, len(rows)) if ink(rows[k]) and not edge(rows[k])), None)
    if first is None:
        return None
    bottom = next((k for k in range(first, len(rows)) if edge(rows[k])), None)
    if bottom is None:
        return None
    # この枠の文字は、枠の中と、そこから行間より狭い空きで続く行（枠からはみ出した行）。行間より広く空いてから出る文字は別の要素で、
    # そのときは箱の端との間ではないので測らない
    last = first
    for k in range(first, bottom):
        if ink(rows[k]):
            if k > y1 - off and k - last > 1.25 * margin:
                return None
            last = k
    if full:  # 箱の端の y（px）も返す（白いカードの下端との間かを見るため。表の罫線で止まったものを除く）
        return bottom - last - 1, first + off, bottom + off
    return (bottom - last - 1, first + off) if top else bottom - last - 1


def top_gap(img, x0, x1, first, y_lo):
    """文字の最初の行（first、px）から上へ、箱の端（ほぼ全部の画素が地と違う行）までの間（px）。地は文字のすぐ上の行の色。"""
    w = x1 - x0
    row = lambda y: list(img.crop((x0, y, x1, y + 1)).get_flattened_data())
    above = row(max(y_lo, first - 2))
    bg = max(set(above), key=above.count)
    edge = lambda r: sum(abs(v - bg) > EDGE for v in r) >= EDGE_FRAC * w
    for y in range(first - 1, y_lo - 1, -1):
        if edge(row(y)):
            return first - y - 1
    return None


MID = "中央寄せの文字と箱の上下の端の間が 1 字分より狭い"  # [box_pad-002] visual.md の 4
SLACK = "上寄せの文字の下が、上より大きく空いている"  # [box_pad-003] visual.md の 4。淡色のパネルの文字は上下の中央に置く
SLACK_MIN = 0.25  # in。下の空きが上の空きをこれ以上超えたら出す（1 行ぶんほど）
CARD = "白いカードの最終行と下端が近い"  # [box_pad-004] visual.md の 4
CARD_MIN = 0.28  # in。2 字分ほど。slides.py のカードは、見出しの上もこれと同じ見た目にする（中身を上下の中央に置く）


PARALLEL = 4  # これより多くのページは、ページごとにプロセスを分けて並べて測る（53 枚で 6.7 秒、1 枚 0.1 秒ほど）


def check(p, folder, pages=None, workers=None):
    """戻りは [(見出し, 1 件), …]（ページの順）。"""
    rule, card = slides.theme_fixed(slides.mark_values(p))["RULE"], slides.deck_card(p)  # カードの地と枠線の色。デッキのテーマの値
    todo = [i for i in range(1, len(p["slides"]) + 1) if (not pages or i in pages) and os.path.exists(f"{folder}/p-{i:02d}.png")]
    if len(todo) <= PARALLEL and not workers:
        return [h for i in todo for h in page_hits(p, folder, i, rule, card)]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(workers or min(8, os.cpu_count() or 1), initializer=_init, initargs=(p, folder, rule, card)) as ex:
        return [h for hs in ex.map(_page, todo) for h in hs]


_DECK = None


def _init(*args):  # 並べて測るプロセスに、デッキの JSON を 1 回だけ渡す
    global _DECK
    _DECK = args


def _page(i):
    p, folder, rule, card = _DECK
    return page_hits(p, folder, i, rule, card)


def page_hits(p, folder, i, rule, card):
    """i ページ目（1 から）の画像で測った指摘。"""
    out, s = [], p["slides"][i - 1]
    page_w = p["pageSize"]["width"]["magnitude"]
    img = Image.open(f"{folder}/p-{i:02d}.png").convert("L")
    px = img.width / page_w  # EMU あたりの画素
    scheme = lint.scheme_of(p, s.get("slideProperties", {}).get("masterObjectId"))
    els = list(flatten(s.get("pageElements", [])))
    fills = [(b, solid(e["shape"].get("shapeProperties", {}).get("shapeBackgroundFill"), scheme)) for e, b in els
             if e.get("shape") and solid(e["shape"].get("shapeProperties", {}).get("shapeBackgroundFill"), scheme) and min(b[2], b[3]) >= 0.05 * EMU]
    for e, b in els:
        sh = e.get("shape")
        align = sh.get("shapeProperties", {}).get("contentAlignment") if sh else None
        if not sh or not sh.get("text") or align == "BOTTOM":
            continue
        if align == "MIDDLE":
            out += middle(img, px, i, sh, b, fills)
            continue
        cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
        inside = [(f, c) for f, c in fills if f[0] <= cx <= f[0] + f[2] and f[1] <= cy <= f[1] + f[3]]
        lines = text_lines(sh, b[2]) or 0
        if not inside or lines < 1:
            continue
        if any(c in (card, rule) for f, c in inside):  # 白いカード（枠線は RULE の角丸に CARD を重ねて描く）は、列で高さをそろえるので見ない
            panel = []
        else:
            panel = [f for f, c in inside if c != scheme.get("DARK1", "1B3139")]  # 濃紺の箱（コード・結論バンド）も見ない
            tol = 0.03 * EMU
            row = lambda f: any(g is not f and (g[0] >= f[0] + f[2] or g[0] + g[2] <= f[0]) and abs(g[1] - f[1]) < tol
                                and abs(g[1] + g[3] - f[1] - f[3]) < tol for g, _ in fills)
            panel = [f for f in panel if not row(f)]  # 横に同じ高さの箱が並ぶ列は、見出しの高さをそろえるので上寄せでよい（visual.md の 4）
        x0, x1 = int((b[0] + INSET * EMU) * px), int((b[0] + b[2] - INSET * EMU) * px)
        sz = min(((size_of(st) or 99) for x in paras(sh["text"]) for c, st in x[1] if c.strip()), default=99)
        if sz == 99:
            continue
        got = measure(img, x0, x1, int(b[1] * px), int((b[1] + b[3]) * px), int((b[1] + b[3] + 1.0 * EMU) * px), int(sz / 72 * EMU * px), full=True)
        if got is None:
            continue
        head = ptext(paras(sh["text"])[0])[:20]
        gap, first, edge_y = got
        gap, need = gap / px / EMU, sz / 72
        in_card = any(c == card and abs(edge_y - (f[1] + f[3]) * px) <= 0.05 * EMU * px for f, c in inside)  # 白いカードの下端の真上の文字
        if (lines >= 2 or in_card) and gap < need - 0.01:  # 白いカードの下の 1 行の札（「2 回まで」など）も見る（2026-10-14、資料 1 で 0.08 in）
            out.append(("箱の下端と文字の間が 1 字分より狭い", f"p{i}: {gap:.2f} in（{sz:g}pt の 1 字は {need:.2f} in）「{head}」"))
        elif lines >= 2 and gap < CARD_MIN and in_card:  # 0.28 in は見出しと本文のあるカードの決まり。1 行の札は 1 字分だけを見る（1 行にも当てると、小さな入れ子のカードで外れた）
            out.append((CARD, f"p{i}: {gap:.2f} in（{CARD_MIN} in まで空ける）「{head}」。カードを高くするか、文を短くする"))
        if panel:
            above = (first - min(f[1] for f in panel) * px) / px / EMU
            if gap - above >= SLACK_MIN:
                out.append((SLACK, f"p{i}: 上 {above:.2f} in・下 {gap:.2f} in「{head}」。valign=\"MIDDLE\" にするか、箱を中身に合わせて縮める"))
    return out


def middle(img, px, i, sh, b, fills):
    """塗りの箱の中の、中央寄せの 2 行以上の文字。箱の上の端と最初の行、最後の行と下の端の間が、どちらも 1 字分あるか。"""
    cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
    inside = [(f, c) for f, c in fills if f[0] <= cx <= f[0] + f[2] and f[1] <= cy <= f[1] + f[3]]
    if not inside or (text_lines(sh, b[2]) or 0) < 2:
        return []
    f0, c0 = min(inside, key=lambda g: g[0][2] * g[0][3])  # いちばん内側の箱
    # 角丸は四角と円を重ねて描くので、同じ色で重なる図形をまとめて 1 つの箱にする（slides.md の 5）
    same = [g for g, c in fills if c == c0 and g[0] < f0[0] + f0[2] and f0[0] < g[0] + g[2] and g[1] < f0[1] + f0[3] and f0[1] < g[1] + g[3]]
    top_, bot_ = min(g[1] for g in same), max(g[1] + g[3] for g in same)
    f = (f0[0], top_, f0[2], bot_ - top_)
    sz = min(((size_of(st) or 99) for x in paras(sh["text"]) for c, st in x[1] if c.strip()), default=99)
    if sz == 99:
        return []
    x0, x1 = int((b[0] + INSET * EMU) * px), int((b[0] + b[2] - INSET * EMU) * px)
    y0, y1 = int(f[1] * px), int((f[1] + f[3]) * px)
    got = measure(img, x0, x1, y0 + 2, y1, y1 + int(0.3 * EMU * px), int(sz / 72 * EMU * px), top=True)
    if got is None:
        return []
    bottom, first = got
    top = top_gap(img, x0, x1, first, max(0, y0 - 3))
    if top is None:
        return []
    need = sz / 72
    t, bt = top / px / EMU, bottom / px / EMU
    if min(t, bt) < need - 0.01:
        return [(MID, f"p{i}: 上 {t:.2f} in・下 {bt:.2f} in（{sz:g}pt の 1 字は {need:.2f} in）「{ptext(paras(sh['text'])[0])[:20]}」。箱を高くするか、文を短くする")]
    return []


def selftest():
    import tempfile
    from PIL import ImageDraw
    with tempfile.TemporaryDirectory() as d:
        for n, card_bottom in ((1, 280), (2, 340), (4, 296)):  # 文字の最終行の下端は 270 px（120 px/in）。p1 は 9 px（0.08 in）で 11pt の 1 字に足りず、p2 は 69 px で足りる。p4 は 25 px（0.21 in）で 1 字は足りるが白いカードの CARD_MIN に足りない
            im = Image.new("L", (1600, 900), 245)
            dr = ImageDraw.Draw(im)
            dr.rectangle((100, 100, 700, card_bottom), fill=255, outline=220)
            for y in (150, 190, 230, 255):
                dr.rectangle((130, y, 600, y + 15), fill=60)
            im.save(f"{d}/p-{n:02d}.png")
        emu = lambda v: {"magnitude": v * 914400 / 120, "unit": "EMU"}
        frame = {"size": {"width": emu(600), "height": emu(160)}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 100 * 914400 / 120,
                                                                              "translateY": 120 * 914400 / 120, "unit": "EMU"},
                 "shape": {"shapeType": "TEXT_BOX", "text": {"textElements": [{"paragraphMarker": {"style": {}}},
                                                                             {"textRun": {"content": "あ" * 60 + "\n", "style": {"fontSize": {"magnitude": 11, "unit": "PT"}}}}]},
                           "shapeProperties": {}}}
        card = {"size": {"width": emu(600), "height": emu(200)}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 100 * 914400 / 120,
                                                                             "translateY": 100 * 914400 / 120, "unit": "EMU"},
                "shape": {"shapeType": "RECTANGLE", "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": {"red": 1, "green": 1, "blue": 1}}}}}}}
        slide = {"pageElements": [card, frame], "slideProperties": {"masterObjectId": "m"}}
        p = {"pageSize": {"width": {"magnitude": 1600 * 914400 / 120}}, "masters": [{"objectId": "m", "pageProperties": {"colorScheme": {"colors": []}}}],
             "layouts": [], "slides": [slide, slide]}
        im = Image.new("L", (1600, 900), 245)
        dr = ImageDraw.Draw(im)
        dr.rectangle((100, 100, 700, 420), fill=255, outline=220)
        for y in (150, 190, 230, 255, 400):  # 400 px の行は、枠（120〜280 px）の外の別の要素
            dr.rectangle((130, y, 600, y + 15), fill=60)
        im.save(f"{d}/p-03.png")
        p["slides"] += [slide, slide]
        hits = check(p, d)
        assert len(hits) == 2 and hits[0][1].startswith("p1: 0.07") and hits[1][0] == CARD and hits[1][1].startswith("p4:"), hits
        # 白いカードの下端の真上の 1 行の札: 最終行の下端 277 px、カードの下端 288 px（間 10 px = 0.08 in で 11pt の 1 字に足りない）。1 行でも見る
        # p2 は下端 300 px（間 22 px = 0.18 in）で、1 字分は足りるので CARD_MIN（2 行以上だけ）は当てない
        for n, bottom in ((1, 288), (2, 300)):
            im = Image.new("L", (1600, 900), 245)
            dr = ImageDraw.Draw(im)
            dr.rectangle((100, 100, 700, bottom), fill=255, outline=220)
            dr.rectangle((130, 262, 300, 277), fill=60)
            im.save(f"{d}/p-{n:02d}.png")
        one = json.loads(json.dumps(frame))
        one["shape"]["text"]["textElements"][1]["textRun"]["content"] = "あ" * 10 + "\n"
        lows = []
        for h in (188, 200):
            low = json.loads(json.dumps(card))
            low["size"]["height"] = emu(h)
            lows.append({"pageElements": [low, one], "slideProperties": {"masterObjectId": "m"}})
        hits = check(dict(p, slides=lows), d)
        assert [k for k, _ in hits] == ["箱の下端と文字の間が 1 字分より狭い"] and hits[0][1].startswith("p1: 0.08"), hits
        # 淡色のパネルの上寄せの文字: 上の空き 0.42 in（150-100 px）に対して、下が 1.2 in 以上空く（p.7 の形）
        im = Image.new("L", (1600, 900), 245)
        dr = ImageDraw.Draw(im)
        dr.rectangle((100, 100, 700, 420), fill=238)
        for y in (150, 190):
            dr.rectangle((130, y, 600, y + 15), fill=60)
        im.save(f"{d}/p-01.png")
        panel = json.loads(json.dumps(card))
        panel["size"]["height"] = emu(320)
        panel["shape"]["shapeProperties"]["shapeBackgroundFill"]["solidFill"]["color"]["rgbColor"] = {"red": 238 / 255, "green": 237 / 255, "blue": 233 / 255}
        tall = json.loads(json.dumps(frame))
        tall["size"]["height"] = emu(300)
        tall["transform"]["translateY"] = 110 * 914400 / 120
        p["slides"] = [{"pageElements": [panel, tall], "slideProperties": {"masterObjectId": "m"}}]
        hits = check(p, d)
        assert [k for k, _ in hits] == [SLACK], hits
        # 中央寄せの 2 行の帯: p1 は箱の高さが 2 行ぶんしかなく（上下 3〜4 px）、p2 は上下に 0.25 in 空く
        for n, top, bot, ys in ((1, 100, 160, (104, 141)), (2, 100, 220, (130, 175))):
            im = Image.new("L", (1600, 900), 245)
            dr = ImageDraw.Draw(im)
            dr.rectangle((100, top, 700, bot), fill=238)
            for y in ys:
                dr.rectangle((130, y, 600, y + 15), fill=60)
            im.save(f"{d}/p-{n:02d}.png")
        band = json.loads(json.dumps(panel))
        mid = json.loads(json.dumps(frame))
        mid["shape"]["shapeProperties"]["contentAlignment"] = "MIDDLE"
        slides = []
        for h in (60, 120):
            b2, m2 = json.loads(json.dumps(band)), json.loads(json.dumps(mid))
            b2["size"]["height"] = m2["size"]["height"] = emu(h)
            b2["transform"]["translateY"] = m2["transform"]["translateY"] = 100 * 914400 / 120
            slides.append({"pageElements": [b2, m2], "slideProperties": {"masterObjectId": "m"}})
        p["slides"] = slides
        hits = check(p, d)
        assert [k for k, _ in hits] == [MID] and hits[0][1].startswith("p1:"), hits
        assert check(p, d, workers=2) == hits  # ページごとに並べて測っても同じ
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        hits = check(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], {int(n) for n in sys.argv[3:]} or None)
        print(f"\n== 要確認（画像で測った）: {len(hits)} ==")
        for k, h in hits:
            print(f"[{k}] {h}")
