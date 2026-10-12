#!/usr/bin/env python3
"""Google Slides の決まった操作（作るのは slides.py。ここは確かめると流用）。
usage:
  gslides.py check  <URL か ID> [--talk] [--pages 3,5]   仕上げの確認。JSON・テキスト・lint・全ページの画像を /tmp/slides_<ID の頭 8 字>/ に出し、画像で箱の下の余白を測る（box_pad.py）
  gslides.py pages  <URL か ID>                    ページ番号・objectId・最初の文字を一覧にする
  gslides.py thumb  <URL か ID> <ページ番号> <出力.png>   Google が描いたページの画像（1600 × 900）を保存する
  gslides.py export <URL か ID> <出力.pptx>          pptx で書き出す（Drive に置かれた pptx はそのまま落とす）。名前と更新日も出す（references.md に書く）
  gslides.py keep   <URL か ID> <Drive のフォルダ> <Drive 上の名前> <ページ番号 ...>   複製して、指定したページだけをその順に残す（流用の段階 1）
  gslides.py jp     <URL か ID> [置き換え.json]     すべての文字を Noto Sans JP にし、置き換え（[["英語", "日本語"], …]）を入れる（keep で作った複製に使う）
認証は gapi.py（環境変数 GOOGLE_OAUTH_ACCESS_TOKEN か、gcloud の ADC のファイル）。401・403 なら factory-doctor で確かめる。"""
import glob, json, os, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True  # scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint
from gapi import DRIVE, PPTX, SLIDES, batch, file_id, folder_id, request, run, slide_ids, thumbnail, trash

THREADS = 6  # サムネイルを並べて取る数。12 枚で約 5 秒（2026-10-07 に測った。PDF に書き出して画像にするのと同じ）


def save_thumb(pid, obj, out):
    meta = thumbnail(pid, obj)
    with urllib.request.urlopen(meta["contentUrl"]) as r, open(out, "wb") as f:
        f.write(r.read())
    return meta


def text_of(p):
    """ページごとの文字とノート（レビューに渡すテキスト）。表は 1 行を「 | 」でつなぐ。"""
    out = []
    for i, s in enumerate(p.get("slides", []), 1):
        out.append(f"## p{i}")
        for e, _ in lint.flatten(s.get("pageElements", [])):
            if "image" in e:
                out.append("［画像］")
            elif "table" in e:
                out += [" | ".join("".join(lint.ptext(x) for x in lint.paras(c.get("text"))).strip() for c in row.get("tableCells", []))
                        for row in e["table"].get("tableRows", [])]
            else:
                t = "\n".join(lint.ptext(x) for text, _ in lint.cells(e) for x in lint.paras(text)).strip()
                if t:
                    out.append(t)
        out += ["", "### Notes:", lint.note_text(s).strip(), ""]
    return "\n".join(out)


def cmd_check(src, *opts):
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    d = f"/tmp/slides_{pid[:8]}"
    os.makedirs(d, exist_ok=True)
    json.dump(p, open(f"{d}/deck.json", "w", encoding="utf-8"), ensure_ascii=False)
    open(f"{d}/deck.md", "w", encoding="utf-8").write(text_of(p))
    print(f"{p['title']}（{len(p['slides'])} 枚）\n")
    hard = lint.lint_slides(p, r := lint.Report(), "差し替え用" in p["title"], "--talk" in opts)
    if not any(w in p["title"].lower() for w in ("tmp", "template", "作業用", "テンプレート")):  # 一時のデッキ・流用元の作業用の写し・テンプレートは、組み直して直すものでないので数えない
        lint.log_run(r, pid)  # 要確認の残り方を lint.py --stats で数える（dreaming の 5）
    ids = [s["objectId"] for s in p["slides"]]
    old = glob.glob(f"{d}/p-*.png")
    if "--pages" in opts and len(old) != len(ids):  # ページが増えたり減ったりしたあとは、番号がずれるので全部を取り直す
        print(f"ページの数が変わった（画像 {len(old)} 枚 → {len(ids)} 枚）ので、--pages を使わずに全ページを取り直す")
        opts = [o for o in opts if o != "--pages"]
    if "--pages" in opts:
        want = sorted({int(n) for n in opts[opts.index("--pages") + 1].split(",")})
    else:
        want = range(1, len(ids) + 1)
        for f in old:  # ページが減ったときに古い画像を残さない
            os.remove(f)
    with ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(lambda n: save_thumb(pid, ids[n - 1], f"{d}/p-{n:02d}.png"), want))
    pad = subprocess.run(["uv", "run", "-q", os.path.join(os.path.dirname(os.path.abspath(__file__)), "box_pad.py"), f"{d}/deck.json", d, *map(str, want)],
                         capture_output=True, text=True)  # 箱の下端と文字の間は、JSON では見積もれないので画像で測る（Pillow が要るので uv）
    print(pad.stdout.rstrip() if pad.returncode == 0 else f"\n（box_pad.py が止まった: {pad.stderr.strip()[-300:]}）")
    print(f"\nテキスト: {d}/deck.md\n画像: {d}/p-NN.png（{len(want)} 枚、1600 × 900）\nJSON: {d}/deck.json")
    if hard:
        sys.exit("lint の要修正が残っている（上の出力を直す）")


def cmd_pages(src):
    p = request("GET", f"{SLIDES}/{file_id(src)}?fields=slides(objectId,pageElements(shape(text(textElements(textRun(content))))))")
    for n, s in enumerate(p["slides"], 1):
        t = "".join(r.get("textRun", {}).get("content", "") for e in s.get("pageElements", [])
                    for r in e.get("shape", {}).get("text", {}).get("textElements", []))
        print(f"p{n}\t{s['objectId']}\t{' '.join(t.split())[:60]}")


def cmd_thumb(src, page, out):
    pid = file_id(src)
    meta = save_thumb(pid, slide_ids(pid)[int(page) - 1], out)
    print(out, meta["width"], "x", meta["height"])


def cmd_export(src, out):
    fid = file_id(src)
    meta = request("GET", f"{DRIVE}/files/{fid}?fields=mimeType,name,modifiedTime,exportLinks&supportsAllDrives=true")
    # files.export は 10 MB で止まる。exportLinks からは 65 枚の社内テンプレート（14.6 MB）も書き出せた（2026-10-07）
    url = f"{DRIVE}/files/{fid}?alt=media&supportsAllDrives=true" if meta["mimeType"] == PPTX else meta["exportLinks"][PPTX]
    open(out, "wb").write(request("GET", url, binary=True))
    print(f"{out}\t{os.path.getsize(out)} bytes\t{meta['name']}\t更新 {meta['modifiedTime'][:10]}")


def cmd_keep(src, folder, name, *pages):
    sid = file_id(src)
    n = len(slide_ids(sid))
    if not pages or any(not x.isdigit() or not 1 <= int(x) <= n for x in pages):  # 複製を作る前に確かめる（作ってから失敗すると、空の複製が残る）
        sys.exit(f"ページ番号は 1〜{n} で 1 つ以上: {' '.join(pages) or '（なし）'}")
    pid = request("POST", f"{DRIVE}/files/{sid}/copy?supportsAllDrives=true&fields=id", {"name": name, "parents": [folder_id(folder)]})["id"]
    try:
        ids = slide_ids(pid)
        keep = [ids[int(x) - 1] for x in pages]
        reqs = [{"deleteObject": {"objectId": o}} for o in ids if o not in keep]
        reqs += [{"updateSlidesPosition": {"slideObjectIds": [o], "insertionIndex": k}} for k, o in enumerate(keep)]  # 並べ替えは 1 枚ずつ（まとめると元の順に限られる）
        batch(pid, reqs)
    except BaseException:
        trash(pid)
        raise
    print(f"https://docs.google.com/presentation/d/{pid}/edit\tpages: {' '.join(pages)}")


def cmd_jp(src, pairs=None):
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    reqs = [{"replaceAllText": {"containsText": {"text": a, "matchCase": True}, "replaceText": b}}
            for a, b in (json.load(open(pairs, encoding="utf-8")) if pairs else [])]
    font = {"style": {"fontFamily": lint.FONT}, "fields": "fontFamily", "textRange": {"type": "ALL"}}
    for s in p["slides"]:
        for e, _ in lint.flatten(s.get("pageElements", [])):
            if e.get("shape", {}).get("text"):
                reqs.append({"updateTextStyle": {"objectId": e["objectId"], **font}})
            for r, row in enumerate(e.get("table", {}).get("tableRows", [])):
                for c, cell in enumerate(row.get("tableCells", [])):
                    if cell.get("text"):
                        reqs.append({"updateTextStyle": {"objectId": e["objectId"], "cellLocation": {"rowIndex": r, "columnIndex": c}, **font}})
    batch(pid, reqs)
    print(f"{len(reqs)} 件（置き換えと書体）")


def main():
    if len(sys.argv) < 3 or "cmd_" + sys.argv[1] not in globals():
        sys.exit(__doc__)
    globals()["cmd_" + sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    run(main)
