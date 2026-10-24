#!/usr/bin/env python3
"""仕上げたファイル（html・csv など）を Google Drive のフォルダに上げる（deck-practices/drive.md）。スライドは slides.py が Drive に直接作る。
同じ名前のファイルがフォルダにあれば中身だけ上書きする（ID・URL・共有の設定は変わらない）。なければ作る。Google Docs に変換するのは research だけ。
usage: drive_put.py <ファイル> <フォルダの URL か ID> <Drive 上の名前（YYYYMMDD_ で始める。拡張子は省くと付ける）>
       drive_put.py research <Research/<内容>_<YYYYMMDD>.md>   調べものを Google Docs に変換して、[drive] factory の下の Research（なければ作る）に
                                                              <YYYYMMDD>_<内容> の名前で上げる（ワークスペースの AGENTS.md の「調べもの」）
出力: 上書きか作ったかと、名前・URL（社内メモに書き、報告に付ける）。"""
import mimetypes, os, re, sys, urllib.parse

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gapi import DRIVE, GDOCS, factory, folder_id, request, run, subfolder, upload

FIELDS = "id,name,webViewLink,modifiedTime"
RESEARCH_DIR = "Research"  # 調べものの写しを置く Drive のフォルダ。[drive] factory の下（Themes と同じ。なければ作る）


def main(path, folder, name, doc=False):
    if not re.match(r"\d{8}_", name):
        sys.exit("Drive 上の名前は YYYYMMDD_ で始める: " + name)
    ext = os.path.splitext(path)[1]
    name += "" if doc or name.endswith(ext) else ext  # 拡張子を付け忘れると、同じ名前と見なされず別のファイルができる（2026-10-07）
    folder = folder_id(folder)
    data, mime = open(path, "rb").read(), "text/markdown" if doc else mimetypes.guess_type(path)[0] or "application/octet-stream"
    q = "name = '%s' and '%s' in parents and trashed = false" % (name.replace("\\", "\\\\").replace("'", "\\'"), folder)
    q += f" and mimeType = '{GDOCS}'" if doc else ""  # 拡張子のない名前なので、同じ名前のフォルダや手で上げたファイルに上書きしない
    hits = request("GET", f"{DRIVE}/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id)", "supportsAllDrives": "true",
                                                                      "includeItemsFromAllDrives": "true", "corpora": "allDrives"}))["files"]
    if len(hits) > 1:
        sys.exit(f"同じ名前が {len(hits)} 個ある。どれに上書きするか決めてから上げる")
    f = upload(data, mime, name, folder, convert=GDOCS if doc else None, fid=hits[0]["id"] if hits else None, fields=FIELDS)
    print(f"{'上書き' if hits else '作成'}: {f['name']}\n{f['webViewLink']}\n更新: {f['modifiedTime']}")


def research(path):
    if not (m := re.fullmatch(r"(.+)_(\d{8})\.md", os.path.basename(path))):
        sys.exit("調べものの名前は <内容>_<YYYYMMDD>.md: " + path)
    if not (root := factory().get("drive", {}).get("factory")):
        sys.exit(f"factory.toml の [drive] factory（個人の資料の根元）がない。調べものはその下の {RESEARCH_DIR} に上げる")
    main(path, subfolder(root, RESEARCH_DIR, create=True), f"{m[2]}_{m[1]}", doc=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["research"] and len(sys.argv) == 3:
        run(lambda: research(sys.argv[2]))
    elif len(sys.argv) == 4:
        run(lambda: main(*sys.argv[1:]))
    else:
        sys.exit(__doc__)
