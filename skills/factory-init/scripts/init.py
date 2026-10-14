#!/usr/bin/env python3
"""usage: init.py [<ワークスペース>]   （--selftest で自己確認）
ワークスペースに、決まり（AGENTS.md・CLAUDE.md・rules/）、設定（factory.toml）、索引（references_index.md）の雛形と、資料のフォルダを置く。
あるファイルは上書きしない（置いたもの・残したものを出す）。標準ライブラリだけ。ワークスペースを省くと、今いるフォルダ。"""
import sys, tempfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
DIRS = ("Customers", "Internal", "Research", ".factory")  # 雛形のないフォルダ（雛形のある rules/ は写すときにできる）


def init(ws):
    ws = Path(ws).expanduser().resolve()
    out = []
    for d in DIRS:
        (ws / d).mkdir(parents=True, exist_ok=True)
    for t in sorted(p for p in TEMPLATES.rglob("*") if p.is_file()):
        dst = ws / t.relative_to(TEMPLATES)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(dst, "x", encoding="utf-8") as f:  # "x": あれば上書きせずに止まる
                f.write(t.read_text(encoding="utf-8"))
            out.append(f"置いた: {dst}")
        except FileExistsError:
            out.append(f"残した（もうある）: {dst}")
    return out


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "AGENTS.md").write_text("mine")
        out = init(tmp)
        assert (Path(tmp) / "AGENTS.md").read_text() == "mine" and any("残した" in o and "AGENTS.md" in o for o in out)
        assert (Path(tmp) / "factory.toml").is_file() and (Path(tmp) / "rules" / "README.md").is_file() and (Path(tmp) / "Customers").is_dir()
        assert all("残した" in o for o in init(tmp))  # 2 回目は何も上書きしない
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if len(a) > 1 or a and a[0].startswith("-"):  # 前の版の --source などを、フォルダの名前と取り違えない
        sys.exit(__doc__)
    print("\n".join(init(a[0] if a else ".")))
