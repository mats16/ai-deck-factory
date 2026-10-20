#!/usr/bin/env python3
"""仕上げたファイル（html・csv など）を Google Drive のフォルダに上げる（deck-build/SKILL.md の「Placing files on Drive」）。スライドは slides.py が Drive に直接作る。
同じ名前のファイルがフォルダにあれば中身だけ上書きする（ID・URL・共有の設定は変わらない）。なければ作る。Google Docs には変換しない。
usage: drive_put.py <ファイル> <フォルダの URL か ID> <Drive 上の名前（YYYYMMDD_ で始める。拡張子は省くと付ける）>
出力: 上書きか作ったかと、名前・URL（社内メモに書き、報告に付ける）。"""
import mimetypes, os, re, sys, urllib.parse

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gapi import DRIVE, folder_id, request, run, upload

FIELDS = "id,name,webViewLink,modifiedTime"


def main(path, folder, name):
    if not re.match(r"\d{8}_", name):
        sys.exit("Drive 上の名前は YYYYMMDD_ で始める: " + name)
    ext = os.path.splitext(path)[1]
    name += "" if name.endswith(ext) else ext  # 拡張子を付け忘れると、同じ名前と見なされず別のファイルができる（2026-10-07）
    folder = folder_id(folder)
    data, mime = open(path, "rb").read(), mimetypes.guess_type(path)[0] or "application/octet-stream"
    q = "name = '%s' and '%s' in parents and trashed = false" % (name.replace("\\", "\\\\").replace("'", "\\'"), folder)
    hits = request("GET", f"{DRIVE}/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id)", "supportsAllDrives": "true",
                                                                      "includeItemsFromAllDrives": "true", "corpora": "allDrives"}))["files"]
    if len(hits) > 1:
        sys.exit(f"同じ名前が {len(hits)} 個ある。どれに上書きするか決めてから上げる")
    f = upload(data, mime, name, folder, fid=hits[0]["id"] if hits else None, fields=FIELDS)
    print(f"{'上書き' if hits else '作成'}: {f['name']}\n{f['webViewLink']}\n更新: {f['modifiedTime']}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    run(lambda: main(*sys.argv[1:]))
