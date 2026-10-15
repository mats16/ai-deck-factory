#!/usr/bin/env python3
"""Google Slides の決まった操作（作るのは slides.py。ここは確かめると流用）。
usage:
  gslides.py check  <URL か ID> [--talk] [--all | --pages 3,5]   組んだあとの確認。JSON・テキスト・lint と、前に取ったときから変わったページの画像を /tmp/slides_<ID の頭 8 字>/ に出し、
                   画像で箱の下の余白を測る（box_pad.py）。取ったページと指摘を changed.json に書く。--all で全ページの画像（/deck-review の前などの区切り）
  gslides.py pages  <URL か ID>                    ページ番号・objectId・最初の文字を一覧にする
  gslides.py thumb  <URL か ID> <ページ番号> <出力.png>   Google が描いたページの画像（1600 × 900）を保存する
  gslides.py export <URL か ID> <出力.pptx>          pptx で書き出す（Drive に置かれた pptx はそのまま落とす）。名前と更新日も出す（references.md に書く）
  gslides.py keep   <URL か ID> <Drive のフォルダ> <Drive 上の名前> <ページ番号 ...>   複製して、指定したページだけをその順に残す（流用の段階 1）
  gslides.py jp     <URL か ID> [置き換え.json]     すべての文字を Noto Sans JP にし、置き換え（[["英語", "日本語"], …]）を入れる（keep で作った複製に使う）
python3 gslides.py --selftest で自己確認。
認証は gapi.py（環境変数 GOOGLE_OAUTH_ACCESS_TOKEN か、gcloud の ADC のファイル）。401・403 なら factory-doctor で確かめる。"""
import glob, json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True  # scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi, lint
from slides import STAMP
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


def reuse_shots(d, ids, prev):
    """前に取った画像（prev は p-NN.png ごとの、取ったときのページの objectId）のうち、今もあるページのものを今の番号に移し、古いものは消す。
    戻り: (取るページの番号, 前の画像を使ったページのうち番号の変わった数)。build は中身の変わったページを新しい ID で作るので、ID が同じなら中身も同じ。"""
    have = {o: f"{d}/p-{m:02d}.png" for m, o in enumerate(prev, 1) if o and os.path.exists(f"{d}/p-{m:02d}.png")}
    keep = {n: have[o] for n, o in enumerate(ids, 1) if o in have}
    for n, f in keep.items():
        os.replace(f, f"{d}/.p-{n:02d}.png")  # 番号がずれると、移す先がまだ移していない画像のことがあるので、いったん別の名前にする
    for f in glob.glob(f"{d}/p-*.png"):
        os.remove(f)
    for n in keep:
        os.replace(f"{d}/.p-{n:02d}.png", f"{d}/p-{n:02d}.png")
    return [n for n in range(1, len(ids) + 1) if n not in keep], sum(n != prev.index(ids[n - 1]) + 1 for n in keep)


def by_page(lines):
    """「p<番号>: …」「p<番号> の…」で始まる指摘を、ページの番号ごとに分ける。"""
    out = {}
    for k, h in lines:
        if (n := lint.hit_page(h)) is not None:
            out.setdefault(n, []).append(f"[{k}] {h}" + ("（見積もり）" if k in lint.ESTIMATE else ""))
    return out


def cmd_check(src, *opts):
    """[gslides-001] 画像は、前に取ったときから変わったページだけを取る（テストの e2e。ページの objectId で見る。build が中身の変わったページだけを新しい ID で作る）。
    前に組んだあとに画面で直されていたら（組んだときの版と今の版が違う）、全ページを取る。--all で全ページ、--pages 3,5 でそのページだけ。
    取ったページの番号・画像・そのページの lint と box_pad の指摘を changed.json に書く（親がページ担当の子に渡す。../SKILL.md の「結果の見方」）。"""
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    gapi.CLOCK.lap("GET")
    d = f"/tmp/slides_{pid[:8]}"
    os.makedirs(d, exist_ok=True)
    json.dump(p, open(f"{d}/deck.json", "w", encoding="utf-8"), ensure_ascii=False)
    open(f"{d}/deck.md", "w", encoding="utf-8").write(text_of(p))
    print(f"{p['title']}（{len(p['slides'])} 枚）\n")
    hard = lint.lint_slides(p, r := lint.Report(), "差し替え用" in p["title"], "--talk" in opts)
    if not any(w in p["title"].lower() for w in ("tmp", "template", "作業用", "テンプレート")):  # 一時のデッキ・流用元の作業用の写し・テンプレートは、組み直して直すものでないので数えない
        lint.log_run(r, pid)  # 要確認の残り方を lint.py --stats で数える（dreaming の 5）
    gapi.CLOCK.lap("lint")
    ids = [s["objectId"] for s in p["slides"]]
    shots = f"{d}/shots.json"  # p-NN.png ごとの、取ったときのページの objectId
    prev = json.load(open(shots)) if os.path.exists(shots) else []
    old = glob.glob(f"{d}/p-*.png")
    if "--pages" in opts and len(old) != len(ids):  # ページが増えたり減ったりしたあとは、番号がずれるので全部を取り直す
        print(f"ページの数が変わった（画像 {len(old)} 枚 → {len(ids)} 枚）ので、--pages を使わずに全ページを取り直す")
        opts = [o for o in opts if o != "--pages"]
    moved, why = 0, None
    if "--pages" in opts:
        want = sorted({int(n) for n in opts[opts.index("--pages") + 1].split(",")})
        man = [o if n in want else prev[n - 1] if len(prev) == len(ids) else None for n, o in enumerate(ids, 1)]
    else:
        stamp = request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(STAMP)
        if "--all" in opts:
            why = "--all"
        elif not prev:
            why = "前に取った画像の記録がない"
        elif p.get("revisionId") != stamp:
            why = "slides.py build で組んだ版でない（画面で直されたか、ほかの道具で変えた）"
        if why:
            want = list(range(1, len(ids) + 1))
            for f in old:  # ページが減ったときに古い画像を残さない
                os.remove(f)
        else:
            want, moved = reuse_shots(d, ids, prev)
        man = ids
    gapi.CLOCK.lap("版の確かめ")
    with ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(lambda n: save_thumb(pid, ids[n - 1], f"{d}/p-{n:02d}.png"), want))
    gapi.CLOCK.lap(f"画像 {len(want)} 枚")
    json.dump(man, open(shots, "w"))
    pad = subprocess.run(["uv", "run", "-q", os.path.join(os.path.dirname(os.path.abspath(__file__)), "box_pad.py"), f"{d}/deck.json", d, *map(str, want)],
                         capture_output=True, text=True) if want else None  # 箱の下端と文字の間は、JSON では見積もれないので画像で測る（Pillow が要るので uv）
    gapi.CLOCK.lap("box_pad")
    if pad:
        print(pad.stdout.rstrip() if pad.returncode == 0 else f"\n（box_pad.py が止まった: {pad.stderr.strip()[-300:]}）")
    if why:
        shown = f"全ページ（{why}）"
    else:
        shown = f"{len(want)} 枚（{'指定したページ' if '--pages' in opts else '前に取ったときから変わったページ'}）"
        if len(want) < len(ids):
            shown += f"。ほかの {len(ids) - len(want)} 枚は前の画像" + (f"（うち {moved} 枚は番号が変わったので、右下のページ番号だけ古い）" if moved else "")
    print(f"\nテキスト: {d}/deck.md\n画像: {d}/p-NN.png。取ったのは {shown}: {', '.join(f'p{n}' for n in want) or 'なし'}\nJSON: {d}/deck.json\n変えたページ: {d}/changed.json")
    hits, pads = by_page((k, h) for k, hs in r.hits.items() for h in hs), by_page(re.findall(r"^\[(.+?)\] (.*)$", pad.stdout if pad else "", re.M))
    json.dump({"url": f"https://docs.google.com/presentation/d/{pid}/edit", "by": "check", "slides": len(ids), "lint_hard": hard, "deck_md": f"{d}/deck.md",
               "pages": [{"page": n, "objectId": ids[n - 1], "image": f"{d}/p-{n:02d}.png", "lint": hits.get(n, []), "box_pad": pads.get(n, [])} for n in want]},
              open(f"{d}/changed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    gapi.CLOCK.show("check ")
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


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for n, o in enumerate("abc", 1):
            open(f"{d}/p-{n:02d}.png", "w").write(o)
        want, moved = reuse_shots(d, ["c", "x", "a"], ["a", "b", "c"])  # c を先頭に、b を消して x を足した
        assert want == [2] and moved == 2 and sorted(os.listdir(d)) == ["p-01.png", "p-03.png"]
        assert open(f"{d}/p-01.png").read() == "c" and open(f"{d}/p-03.png").read() == "a"
    hits = by_page([(lint.TWO_LINES, "p3 の見出し: 「x」"), ("絵文字", "p12: 「✅」"), ("扉", "13 枚。…")])
    assert hits == {3: [f"[{lint.TWO_LINES}] p3 の見出し: 「x」（見積もり）"], 12: ["[絵文字] p12: 「✅」"]}
    print("selftest ok")


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if len(sys.argv) < 3 or "cmd_" + sys.argv[1] not in globals():
        sys.exit(__doc__)
    globals()["cmd_" + sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    run(main)
