#!/usr/bin/env python3
"""JSON のページの見本（skills/slides-build/samples/json/）をすべて Google Slides に組み、Google が描いた全ページの画像を、ページごとの見るところ（expect.json）と並べる。
usage（sandbox のようなワークスペースの中で回す。factory.toml の [drive] internal に一時のデッキを作る）:
  python3 <リポジトリ>/tests/render/run.py [--keep] [--judge]
  --keep   組んだデッキを残す（既定は、画像を取ったらゴミ箱に移す）
  --judge  claude -p に report.md と画像を読ませ、ページごとに OK・NG を出させる（judge.md）。NG があれば終わりの状態を 1 にする
  --selftest  見本のどのページにも expect.json の見るところがあるかだけを見る（Google を読まない）
出すもの: <ワークスペース>/.factory/render/（build/ に組んだページ、png/ に画像、report.md、judge.md）。
lint（手元と組んだあと）の要修正が 1 つでもあれば、終わりの状態を 1 にする。"""
import json, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
K = ROOT / "skills" / "slides-build" / "scripts"
SAMPLES = ROOT / "skills" / "slides-build" / "samples" / "json"
sys.path.insert(0, str(K))
sys.path.insert(0, str(ROOT / "skills" / "deck-practices" / "scripts"))  # gapi.py
sys.dont_write_bytecode = True
import gapi  # noqa: E402

COMMON = "文字のはみ出し・重なり・切れがなく、本文がフッターと結論バンドに重ならず、矢印が箱から外れていない"  # どのページにも見るところ
JUDGE = """{report} を読み、ページごとに画像（png の行のパス）を Read で開いて、「見るところ」と「どのページにも」をすべて満たすかを確かめる。
答えは次の形だけにする（前置きを書かない）。どのページも 1 行ずつ、番号とファイル名は report.md の見出しのとおり。
- p<番号> <ファイル>: OK
- p<番号> <ファイル>: NG — <満たさない見るところと、画像で見えたこと>"""


def judged(answer, files):
    """claude -p の答えの NG のページの数。どのページにも、番号とファイル名の合う OK か NG が 1 つずつなければ、判定の抜けとして止める。"""
    got = re.findall(r"^- p(\d+) (\S+): (OK|NG)(?: — .*)?$", answer, re.M)
    want = [(str(i), f) for i, f in enumerate(files, 1)]
    seen = [(n, f) for n, f, _ in got]
    if sorted(seen) != sorted(want):
        miss = [f"p{n} {f}" for n, f in want if (n, f) not in seen]
        extra = [f"p{n} {f}" for n, f in dict.fromkeys(seen) if seen.count((n, f)) > 1 or (n, f) not in want]
        sys.exit(f"claude -p の答えに、判定のないページか重なったページがある（ない: {', '.join(miss) or 'なし'}。重なり・知らない: {', '.join(extra) or 'なし'}）")
    return sum(v == "NG" for *_, v in got)


def pages():
    """組む順のページのファイル（見本のデッキの順に、部品 1 つの component.json を最後に足す）。"""
    return json.loads((SAMPLES / "deck.json").read_text())["pages"] + ["component.json"]


def expect():
    e = json.loads((HERE / "expect.json").read_text())
    if miss := [p for p in pages() if not e.get(p)]:
        sys.exit(f"expect.json に見るところがないページ: {', '.join(miss)}")
    if extra := sorted(set(e) - set(pages()) - {"_"}):
        sys.exit(f"expect.json にあって見本にないページ: {', '.join(extra)}")
    return e


def sh(*args, cwd):
    """スクリプトを回して、出力（標準出力と標準エラー）を見せる。戻り: (出力, 終わりの状態)。lint は要修正があると 0 でない状態で終わる。"""
    r = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True)
    print(r.stdout + r.stderr, end="")
    return r.stdout + r.stderr, r.returncode


def main():
    a = sys.argv[1:]
    if bad := [x for x in a if x not in ("--keep", "--judge", "--selftest")]:
        sys.exit(__doc__ + f"\n知らない引数: {' '.join(bad)}")
    e = expect()
    if "--selftest" in a:
        fs = ["a.json", "b.json"]
        assert judged("- p1 a.json: OK\n- p2 b.json: NG — 矢印が外れている\n", fs) == 1 and judged("- p1 a.json: OK\n- p2 b.json: OK\n", fs) == 0
        for bad in ("NG: 0\n", "- p1 a.json: OK\n", "- p1 a.json: OK\n- p1 a.json: OK\n- p2 b.json: OK\n",
                    "- p1 a.json: OK\n- p2 c.json: OK\n", "- p1 a.json: OK\n- p2 b.json: **NG**\n"):  # 集計だけ、一部だけ、重なり、知らないファイル、崩れた書き方
            try:
                judged(bad, fs)
                raise AssertionError(bad)
            except SystemExit:
                pass
        return print("selftest ok")
    ws = gapi.factory_path().parent
    folder = gapi.factory().get("drive", {}).get("internal") or sys.exit("factory.toml の [drive] internal が空。一時のデッキを置く Drive のフォルダ（検証用）を書く")
    out = ws / ".factory" / "render"
    shutil.rmtree(out, ignore_errors=True)
    (build := out / "build").mkdir(parents=True)
    (png := out / "png").mkdir()
    for f in SAMPLES.glob("*.json"):
        shutil.copy(f, build)
    c = json.loads((SAMPLES / "component.json").read_text())  # 部品 1 つのファイルはデッキに並べられないので、型のないページに置く
    body = {k: v for k, v in c.items() if k not in ("apiVersion", "kind")}
    (build / "component_page.json").write_text(json.dumps({"apiVersion": "slides/v1", "kind": "page", "type": "slide", "body": [body]}, ensure_ascii=False))
    deck = json.loads((SAMPLES / "deck.json").read_text())
    deck["pages"].append("component_page.json")
    (build / "deck.json").write_text(json.dumps(deck, ensure_ascii=False))

    print("== 手元の lint ==")
    _, local = sh(K / "slides.py", "lint", "--all", cwd=build)  # 要修正があっても組んで画像を見る
    print("\n== 組む ==")
    made, failed = sh(K / "slides.py", "new", folder, time.strftime("%Y%m%d_tmp_render"), cwd=build)  # 組めなければ、new が複製をゴミ箱に移す
    if failed:
        sys.exit("slides.py new で止まった（上の出力）")
    pid = re.search(r'"presentationId": "([^"]+)"', made).group(1)
    try:
        print("\n== 画像を取る ==")
        _, check = sh(K / "gslides.py", "check", pid, "--all", cwd=build)  # 要修正があっても、画像は取ってある
        shots = sorted(Path(f"/tmp/slides_{pid[:8]}").glob("p-*.png"))
        if len(shots) != len(pages()):
            sys.exit(f"画像が {len(shots)} 枚（ページは {len(pages())} 枚）")
        for s in shots:
            shutil.copy(s, png)
    finally:
        if "--keep" in a:
            print(f"\nデッキを残した: https://docs.google.com/presentation/d/{pid}/edit")
        else:
            gapi.trash(pid)
            print(f"\nデッキ {pid} をゴミ箱に移した（--keep で残す）")

    n = bool(local) + bool(check)
    said = lambda rc: "要修正あり（出力の「== 要修正」）" if rc else "要修正なし"
    lines = [f"# 見本を組んだ画像の確かめ（{time.strftime('%Y-%m-%d %H:%M')}）", "",
             f"- 手元の lint: {said(local)}、組んだあとの lint（gslides.py check）: {said(check)}。要確認は画像で見る", ""]
    for i, p in enumerate(pages(), 1):
        lines += [f"## p{i} {p}", f"png: {png / f'p-{i:02d}.png'}", "", *[f"- {x}" for x in e[p]], ""]
    lines += ["## どのページにも", "", f"- {COMMON}", ""]
    (report := out / "report.md").write_text("\n".join(lines))
    print(f"\n見るところと画像: {report}")

    if "--judge" in a:
        print("\n== claude -p が画像を見る ==")
        r = subprocess.run(["claude", "-p", JUDGE.format(report=report), "--allowedTools", "Read"], cwd=out, capture_output=True, text=True)
        (out / "judge.md").write_text(r.stdout)
        print(r.stdout + r.stderr, end="")
        if r.returncode:
            sys.exit("claude -p が止まった（上の出力）")
        n += judged(r.stdout, pages())
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    gapi.run(main)
