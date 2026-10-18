# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""usage: uv run -q sheet.py <出力.png> <画像 ...> [--cols 2] [--width 800] [--per 16]   （--selftest で自己確認）
スライドの画像を何枚か 1 枚に並べる（まとめて見て確かめるとき）。素の python3 には Pillow がないので uv で動かす。
各ページの上に、ファイル名の番号（p-03.png なら p3）を入れる（見る人が格子の位置を数え間違えないように。ページに重ねない）。
--per を付けると、その枚数ごとに <出力>-1.png、<出力>-2.png … に分ける（全体のレビューの一覧は 4 列 × 400 px、16 枚ずつ。deck-review の SKILL.md）。
切り取りは sips でできる（../../deck-practices/reuse.md の段階 2）ので、ここには入れていない。"""
import os, re, sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # python3 で回すと、ここで落ちて 1 枚ずつ画像を開くほうへ流れていた（2026-10-16）
    sys.exit("Pillow がない。uv run -q sheet.py … で回す（頭の # /// script が Pillow を入れる）")

LABEL = (204, 43, 23)  # 赤の文字の色（visual.md の RED_TEXT）。濃紺の地でも Oat の地でも目立つ


def label(path):
    m = re.search(r"(\d+)\D*$", os.path.basename(path))
    return f"p{int(m.group(1))}" if m else os.path.splitext(os.path.basename(path))[0]


def sheet(paths, cols=2, width=800, gap=8):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((width, round(im.height * width / im.width))) for im in ims]
    size = max(14, width // 25)
    head = size + 6  # 番号の帯
    h, rows = max(im.height for im in ims) + head, -(-len(ims) // cols)
    out = Image.new("RGB", (cols * width + (cols - 1) * gap, rows * h + (rows - 1) * gap), "white")
    draw, font = ImageDraw.Draw(out), ImageFont.load_default(size=size)
    for i, (p, im) in enumerate(zip(paths, ims)):
        x, y = (i % cols) * (width + gap), (i // cols) * (h + gap)
        draw.text((x, y + 2), label(p), fill=LABEL, font=font)
        out.paste(im, (x, y + head))
    return out


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for i, c in enumerate(("red", "green", "blue")):
            paths.append(os.path.join(d, f"p-{i + 1:02d}.png"))
            Image.new("RGB", (1600, 900), c).save(paths[-1])
        out = sheet(paths, cols=2, width=400)
    assert out.size == (808, 502)  # 2 列・2 段、間は 8 px、各段の上に 22 px の番号の帯（幅 400 なら文字は 16 px）
    assert out.getpixel((0, 22)) == (255, 0, 0) and out.getpixel((408, 22)) == (0, 128, 0) and out.getpixel((0, 277)) == (0, 0, 255)
    assert out.getpixel((807, 501)) == (255, 255, 255)  # 足りないところは白
    assert LABEL in {c for _, c in out.crop((0, 0, 80, 22)).getcolors(10000)}  # ページの上の帯に番号
    assert label("/tmp/x/p-03.png") == "p3" and label("a.png") == "a"
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    opt = {"--cols": 2, "--width": 800, "--per": 0}
    for k in opt:
        if k in a:
            i = a.index(k)
            opt[k] = int(a[i + 1])
            del a[i:i + 2]
    if len(a) < 2:
        sys.exit(__doc__)
    out, paths = a[0], a[1:]
    per = opt["--per"] or len(paths)
    chunks = [paths[k:k + per] for k in range(0, len(paths), per)]
    stem, ext = os.path.splitext(out)
    for n, ch in enumerate(chunks, 1):
        name = out if len(chunks) == 1 else f"{stem}-{n}{ext}"
        sheet(ch, opt["--cols"], opt["--width"]).save(name)
        print(name)
