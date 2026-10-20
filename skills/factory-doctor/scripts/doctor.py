#!/usr/bin/env python3
"""usage: doctor.py [<ワークスペース>] [--local]   （--selftest で自己確認）
AI Deck Factory を動かす前提を確かめる。--local は手元だけ見て、Google の API を呼ばない。
1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。標準ライブラリだけ。"""
import io, contextlib, json, math, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]  # プラグインの skills/
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILLS / "deck-build" / "scripts"))


def find_ws(start):
    return next((d for d in (start, *start.parents) if (d / "factory.toml").is_file()), None)


def check(ws, local=False):
    """(区分, 項目, 詳しく) の並び。区分は OK・要修正・要確認。"""
    out = []
    ok = lambda name, detail="": out.append(("OK", name, detail))
    ng = lambda name, detail: out.append(("要修正", name, detail))
    warn = lambda name, detail: out.append(("要確認", name, detail))

    (ok if sys.version_info >= (3, 11) else ng)("Python 3.11 以上", sys.version.split()[0])
    (ok if shutil.which("uv") else ng)("uv", shutil.which("uv") or "ない。画像での測り（box_pad.py・doc_layout.py・sheet.py）が動かない。https://docs.astral.sh/uv/ で入れる")
    npx = shutil.which("npx")  # docs.py の mermaid_png が mermaid-cli を取ってくる
    (ok if npx else warn)("mermaid の図", npx or "Node.js（npx）がない。doc.md の ```mermaid を組めない（ほかは組める）。https://nodejs.org/ で入れる")
    root = find_ws(ws)
    if not root:
        ng("factory.toml", f"{ws} から上にない。factory-init で作る")
        return out
    ok("ワークスペース", str(root))
    try:
        cfg = tomllib.loads((root / "factory.toml").read_text())
    except tomllib.TOMLDecodeError as e:
        ng("factory.toml の書き方", str(e))
        return out
    for name, need in (("AGENTS.md", ng), ("CLAUDE.md", warn), ("references_index.md", warn)):
        (ok if (root / name).is_file() else need)(name, "" if (root / name).is_file() else "ない。factory-init で置く")
    if old := sorted((root / "Customers").glob("*/CLAUDE.md")):
        how = lambda p: f"{p.relative_to(root)}（{'memory.md に中身を移して消す' if (p.parent / 'memory.md').exists() else 'memory.md に名前を変える'}）"
        warn("顧客の memory", f"前の形の CLAUDE.md がある。Claude Code しか読まない（hook が Claude Code・Codex・pi で続けて出すのは memory.md）: {', '.join(map(how, old))}")
    agents = (root / "AGENTS.md").read_text() if (root / "AGENTS.md").is_file() else ""
    if "人がレビューするかも選んでもらう" in agents:  # 2026-10-13 までの雛形
        warn("AGENTS.md の方針のレビュー", "前の雛形の「人がレビューするかも選んでもらう」が残っている。ワークスペースの決まりが優先するので、factory.toml の [review] plan_reviewer が効かず、資料ごとに聞く。factory-init の雛形の今の文（plan_reviewer に従う）に替える")
    if "- ユーザーに返す前に、スキル `deck-review` で全体をレビューする。" in agents:  # 2026-10-19 までの雛形
        warn("AGENTS.md の返したあとの直し", "前の雛形の「ユーザーに返す前に、スキル deck-review で全体をレビューする」が残っている。ワークスペースの決まりが優先するので、返したあとの小さな直しや問いでも全体のレビューを回す。factory-init の雛形の今の文（新しく作った資料は deck-review、返したあとは deck-practices の「Requests after delivery」）に替える")
    if cfg.get("factory", {}).get("source"):  # 2026-10-14 まで、factory-kaizen が worktree を作る checkout
        warn("factory.source", "使わなくなった（factory-kaizen は .factory/kaizen/ に自分で clone する）。factory.toml から消す")
    names = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    found = {}  # 実体ごとに 1 回（.claude/skills は .agents/skills へのリンクのことが多い）
    for d in (".agents/skills", ".claude/skills"):
        for name in names:
            if (root / d / name / "SKILL.md").is_file():
                found.setdefault((root / d / name).resolve(), f"{d}/{name}")
    dup = list(found.values())
    (warn if dup else ok)("スキルの重なり", f"ワークスペースにも同じ名前のスキルがある（プラグインと二重に読まれる）: {', '.join(dup)}" if dup else "")
    g, sl, dr = cfg.get("google", {}), cfg.get("slides", {}), cfg.get("drive", {})
    if not g.get("quota_project"):
        warn("google.quota_project", "空。gcloud の既定の OAuth クライアントで取ったトークンなら、Slides・Docs が 403 になる")
    from lint import COPYRIGHT_FOOTER  # 9pt で通す著作権表示の形（slides.py が全ページに書く）
    import slides  # 仮の著作権表示（PLACEHOLDER_COPYRIGHT。need_brand と同じ）と、テーマのファイルの読み方（read_theme）
    brand = cfg.get("brand", {})
    marks = [("brand.copyright", brand.get("copyright", ""))]  # テーマの copyright は、そのテーマのデッキで [brand] の代わりに書く（slides.py の use_theme）
    mine = {}  # ワークスペースのテーマのファイル（themes/slides/<名前>.json）。組むときに止まる値（形・色・copyright・書体）を、組む前に出す（slides.py と同じ read_theme で見る）
    for f in sorted(root.joinpath(*slides.WS_THEMES).glob("*.json")):
        try:
            mine[f.stem] = slides.read_theme(f)
        except SystemExit as e:
            ng(f"themes/slides/{f.name}", str(e).replace(f"{f}: ", ""))
    marks += [(f"themes/slides/{n}.json の copyright", t["copyright"]) for n, t in mine.items() if "copyright" in t]
    import docs as docs_py  # ドキュメントのテーマのファイル（themes/docs/<名前>.json）も、docs.py と同じ read_theme で見る
    doc_themes = {}
    for f in sorted(root.joinpath(*docs_py.WS_THEMES).glob("*.json")):
        try:
            doc_themes[f.stem] = docs_py.read_theme(f)
        except SystemExit as e:
            ng(f"themes/docs/{f.name}", str(e).replace(f"{f}: ", ""))
    for key, c in marks:
        if not (c := str(c).strip()):
            ng(key, "空。スライドもドキュメントも組めない（全ページの左下に書く著作権表示がない）。自分の会社の著作権表示を書く")
        elif c == slides.PLACEHOLDER_COPYRIGHT:
            ng(key, f"「{c}」は書いていないときの仮の値。スライドもドキュメントも組めない。自分の会社の著作権表示を書く")
        elif not COPYRIGHT_FOOTER.fullmatch(c):
            ng(key, f"「{c}」は「© <年> <社名> All rights reserved.」の形でない。lint が全ページの著作権表示を 11pt 未満として止める")
    if not brand.get("company"):
        warn("brand.company", "空。表紙の左下に社名を置かない")
    docs = cfg.get("docs", {})
    files = {**{f.stem: t for f in slides.BUILTIN_THEMES.glob("*.json") for t in [slides.read_theme(f)]}, **mine}  # ワークスペースのものが勝つ
    theme, temps = sl.get("default_theme", "visual"), {k: v for k, v in sl.get("templates", {}).items() if v}
    if old := sl.get("themes"):  # 2026-10-16 までの書き方
        ng("slides.themes", f"{', '.join(old)} はプラグインが読まない。テーマはワークスペースの themes/slides/<名前>.json（kind theme。色は colors の下に同じ名前で書く）に、"
                            "テンプレートの url は [slides.templates] の「<名前> = \"<url>\"」に移して消す（テンプレートのある名前は slides.py theme <url> でも写せる。../../deck-build/slides.md の 3）")
    if "base_template" in sl:  # 2026-10-14 までの書き方
        ng("slides の base", "slides.base_template を消す。元のテンプレートは factory.toml に持たず、template.py <テーマ> --from-base <元の URL> で渡す（渡さなければ白紙の pptx から作る）")
    if sl.get("template_folder"):  # 2026-10-12 までの書き方
        warn("slides.template_folder", "プラグインは読まない。新しく作るテンプレートは [drive] factory の下の Themes に作る（前の版のスクリプトで動かさなくなったら消す）")
    (ok if temps.get(theme) else warn)("slides.templates", ", ".join(temps) if temps.get(theme) else
                                       f"既定のテーマ {theme} のテンプレートがない。template.py {theme} --from-base で作るか、共有のテーマ（slides.py themes）を slides.py theme <url> で写す")
    if bare := [n for n in temps if n not in files]:
        ng("テーマのファイル", f"{', '.join(bare)} のテンプレートはあるが、themes/slides/<名前>.json がない。組めない。slides.py theme <[slides.templates] の URL> で写す")
    if theme not in files:
        ng("slides.default_theme", f"{theme} のテーマのファイルがない（themes/slides/{theme}.json）。テーマを書かない資料が組めない")
    if no_desc := [n for n in temps if n in files and not files[n].get("description")]:
        warn("テーマの説明", f"{', '.join(no_desc)} に description がない。エージェントが資料ごとにテーマを選べない（themes/slides/<名前>.json の description に、どの資料・聞き手に使うかを書く）")
    if old := docs.get("themes"):  # 2026-10-19 までの書き方
        ng("docs.themes", f"{', '.join(old)} はプラグインが読まない。ワークスペースの themes/docs/<名前>.json（kind theme。見出しの大きさは styles、色は colors）に移して消す"
                          "（../../doc-build/SKILL.md の doc-build-010）")
    if bad := [n for n, t in doc_themes.items() if not t.get("description")]:
        warn("ドキュメントのテーマの説明", f"{', '.join(bad)} に description がない。エージェントが資料ごとにテーマを選べない（themes/docs/<名前>.json の description に書く）")
    if (d := docs.get("default_theme")) and d not in doc_themes and d != "standard":  # standard は組み込み（docs.py の STANDARD）
        ng("docs.default_theme", f"{d} のテーマのファイルがない（themes/docs/{d}.json）。theme を書かない doc.md が組めない")
    review = cfg.get("review", {})  # 書いていなければ既定。読むのはエージェント（deck-practices の 5 と 9）
    if (p := review.get("plan_reviewer", "ai")) not in ("ai", "human"):
        ng("review.plan_reviewer", f"{p!r} は使えない。\"ai\" か \"human\" にする")
    if type(n := review.get("deck_review_max_rounds", 3)) is not int or not 1 <= n <= 3:  # bool は int の子なので type で見る
        ng("review.deck_review_max_rounds", f"{n!r} は使えない。1〜3 の整数にする（直すと欠陥が増えるので 3 より多くしない）")
    if type(h := cfg.get("feedback", {}).get("google_comments", {}).get("watch_hours", 0)) not in (int, float) or not math.isfinite(h) or h < 0:  # 0 か書いていなければ、頼まれたときだけ見張る（deck-comments）
        ng("feedback.google_comments.watch_hours", f"{h!r} は使えない。時間の数にする（見張らないなら 0）")
    for k in ("customers", "internal", "docs", "factory"):
        if not dr.get(k):
            warn(f"drive.{k}", "空。資料の置き場所が決まらない")
    if local:
        return out

    os.chdir(root)  # gapi は今いるフォルダから factory.toml を探す
    import gapi
    try:
        who = gapi.request("GET", f"{gapi.DRIVE}/about?fields=user(emailAddress)")["user"]["emailAddress"]
        ok("Google の認証", who)
    except gapi.ApiError as e:
        how = "GOOGLE_OAUTH_ACCESS_TOKEN" if os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") else str(gapi.credentials_path())  # gapi.token() と同じ順
        first = str(e).splitlines()[0]
        fix = "google.quota_project を書く（空だと gcloud の既定の OAuth クライアントのトークンは 403）" if first.startswith("403") and not g.get("quota_project") else f"作り直す: {gapi.LOGIN}"
        ng("Google の認証", f"{how} で通らない: {first}。{fix}")
        return out
    targets = [(f"slides.templates.{k}", v) for k, v in temps.items()] + [(f"docs.templates.{k}", v) for k, v in cfg.get("docs", {}).get("templates", {}).items()]
    targets += [(f"drive.{k}", v) for k, v in dr.items() if v]
    for name, url in targets:
        fid = gapi.folder_id(url) if "/folders/" in url else gapi.file_id(url)
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{fid}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except gapi.ApiError as e:
            ng(name, f"開けない（{str(e).split()[0]}）: {url}")
    if dr.get("shared_themes"):  # 全社の共有テーマのフォルダ。探すときだけ読む（使うテーマは slides.py theme <url> で写す）
        try:
            files, have = slides.shared_files(), {gapi.file_id(u) for u in temps.values()}  # 自分の Themes は読まない（slides.py themes が出す）
            names, new = [f["properties"][slides.THEME_PROP] for f in files], [f["properties"][slides.THEME_PROP] for f in files if f["id"] not in have]
            bare = 0 if names else len(slides.theme_files(gapi.folder_id(dr["shared_themes"]), named=False))  # 名前のあるものが 1 つでもあれば数えない（base の写しのように、名前がなくて正しいものもある）
        except slides.READ_ERRORS:  # 開けないことは drive.shared_themes に出ている
            return out
        if dup := sorted({n for n in names if names.count(n) > 1}):
            warn("共有テーマ", f"同じ名前のテーマが 2 つ以上ある（どれを写すか迷う。古いほうをフォルダから外す）: {', '.join(dup)}")
        elif bare:  # テーマの名前を書く前（2026-10-14 より前）の template.py で作ったもの
            warn("共有テーマ", f"Google Slides が {bare} 個あるが、どれにもテーマの名前（{slides.THEME_PROP}）がない。持ち主が template.py <テーマ> で合わせ直すと書かれる")
        elif not names:
            warn("共有テーマ", "テーマがない。管理者が template.py で作ったテンプレートを置く（ほかのファイルは読まない）")
        else:
            ok("共有テーマ", ", ".join(names) + (f"（[slides.templates] にない: {', '.join(new)}。使うなら slides.py theme <url> で写す）" if new else ""))
    return out


def main(args):
    local = "--local" in args
    rest = [a for a in args if a != "--local"]
    rows = check(Path(rest[0] if rest else ".").expanduser().resolve(), local)
    for kind, name, detail in rows:
        print(f"{kind}\t{name}\t{detail}")
    n = sum(k == "要修正" for k, _, _ in rows)
    print(f"\n要修正 {n}・要確認 {sum(k == '要確認' for k, _, _ in rows)}" + ("（--local: Google の API は見ていない）" if local else ""))
    return 1 if n else 0


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        kinds = lambda: {n: k for k, n, _ in check(Path(tmp), local=True)}
        assert kinds()["factory.toml"] == "要修正"
        subprocess.run([sys.executable, str(SKILLS / "factory-init" / "scripts" / "init.py"), tmp], check=True, capture_output=True)
        (Path(tmp) / ".agents" / "skills" / "deck-build").mkdir(parents=True)
        (Path(tmp) / ".agents" / "skills" / "deck-build" / "SKILL.md").write_text("x")
        k = kinds()
        assert k["AGENTS.md"] == "OK" and k["スキルの重なり"] == "要確認" and k["slides.templates"] == "要確認" and k["drive.customers"] == "要確認"
        (Path(tmp) / "Customers" / "acme").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").write_text("x")
        assert kinds()["顧客の memory"] == "要確認"
        (Path(tmp) / "Customers" / "acme" / "memory.md").write_text("y")
        assert "中身を移して消す" in next(d for _, n, d in check(Path(tmp), local=True) if n == "顧客の memory")  # 名前を変えると memory.md を上書きする
        (Path(tmp) / "Customers" / "acme" / "memory.md").unlink()
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").rename(Path(tmp) / "Customers" / "acme" / "memory.md")
        assert "顧客の memory" not in kinds()
        agents = Path(tmp) / "AGENTS.md"
        assert "AGENTS.md の方針のレビュー" not in kinds()  # 今の雛形
        agents.write_text(agents.read_text() + "\n同じ問いで、方針を決めたあとを AI のレビューでそのまま作るか、人がレビューするかも選んでもらう。\n")
        assert kinds()["AGENTS.md の方針のレビュー"] == "要確認"
        assert "AGENTS.md の返したあとの直し" not in kinds()  # 今の雛形
        agents.write_text(agents.read_text().replace("- 新しく作った資料は、ユーザーに返す前に、", "- ユーザーに返す前に、"))
        assert kinds()["AGENTS.md の返したあとの直し"] == "要確認"
        toml = Path(tmp) / "factory.toml"
        assert kinds()["brand.copyright"] == "要修正" and kinds()["brand.company"] == "要確認"
        toml.write_text(toml.read_text().replace("[brand]", '[brand]\ncopyright = "© Acme 2026"', 1))
        assert kinds()["brand.copyright"] == "要修正"
        toml.write_text(toml.read_text().replace('"© Acme 2026"', '"© 2026 Example, Inc. All rights reserved."'))
        assert kinds()["brand.copyright"] == "要修正"  # 仮の値をそのまま書いた
        toml.write_text(toml.read_text().replace('"© 2026 Example, Inc. All rights reserved."', '"© 2026 Acme, Inc. All rights reserved."'))
        assert "brand.copyright" not in kinds()
        themes = Path(tmp, "themes", "slides")
        themes.mkdir(parents=True)
        put = lambda n, o: (themes / f"{n}.json").write_text(json.dumps({"apiVersion": "slides/v1", "kind": "theme", **o}))
        put("mine", {"copyright": "© Me 2026"})
        assert kinds()["themes/slides/mine.json の copyright"] == "要修正"  # テーマの copyright にも同じ確かめ
        put("mine", {"copyright": "© 2026 Me. All rights reserved.", "colors": {"TEXT": "red"}})
        dthemes = Path(tmp, "themes", "docs")
        dthemes.mkdir(parents=True)
        dput = lambda n, o: (dthemes / f"{n}.json").write_text(json.dumps({"apiVersion": "docs/v1", "kind": "theme", **o}))
        dput("us2", {"mono": "Fira Code"})
        assert kinds()["themes/slides/mine.json"] == "要修正" and kinds()["themes/docs/us2.json"] == "要修正"  # 6 桁でない色、リガチャの出る等幅
        (dthemes / "us2.json").unlink()
        assert "themes/slides/mine.json の copyright" not in kinds()
        put("mine", {"copyright": 2026})
        assert kinds()["themes/slides/mine.json"] == "要修正" and "themes/slides/mine.json の copyright" not in kinds()  # 文字列でない copyright は 1 回だけ出す
        put("mine", {})
        assert "themes/slides/mine.json" not in kinds() and "slides.themes" not in kinds()
        toml.write_text(toml.read_text().replace("\n[slides.templates]", '\n[slides.templates]\nmine = "x"\nacme = "y"', 1))
        k = kinds()
        assert k["テーマのファイル"] == "要修正" and "acme" in next(d for _, n, d in check(Path(tmp), local=True) if n == "テーマのファイル")  # テンプレートだけで、テーマのファイルがない
        assert k["テーマの説明"] == "要確認"  # mine に description がない
        put("mine", {"description": "自分の"})
        toml.write_text(toml.read_text().replace('mine = "x"\nacme = "y"', 'mine = "x"', 1))
        assert "テーマのファイル" not in kinds() and "テーマの説明" not in kinds()
        toml.write_text(toml.read_text() + '\n[slides.themes.visual]\nurl = "x"\n')
        assert kinds()["slides.themes"] == "要修正"  # 2026-10-16 までの書き方
        toml.write_text(toml.read_text().replace('\n[slides.themes.visual]\nurl = "x"\n', ""))
        assert "slides の base" not in kinds() and "slides.default_theme" not in kinds()  # 雛形には書いていない。既定の visual は組み込み
        toml.write_text(toml.read_text().replace('default_theme = "visual"', 'default_theme = "nope"\nbase_template = ""', 1))
        assert kinds()["slides の base"] == "要修正" and kinds()["slides.default_theme"] == "要修正"  # 2026-10-14 までの書き方（空でも消す）、ファイルのない既定のテーマ
        toml.write_text(toml.read_text().replace('default_theme = "nope"\nbase_template = ""', 'default_theme = "visual"', 1))
        toml.write_text(toml.read_text() + '\n[docs]\ndefault_theme = "acme"\n\n[docs.themes.us]\npage = [215.9, 279.4]\n')
        dput("us", {"page": [215.9, 279.4]})
        k = kinds()
        assert k["docs.default_theme"] == "要修正" and k["ドキュメントのテーマの説明"] == "要確認" and k["docs.themes"] == "要修正"  # 既定のテーマがない、説明がない、前の書き方
        toml.write_text(toml.read_text().replace("\n[docs.themes.us]\npage = [215.9, 279.4]\n", ""))
        toml.write_text(toml.read_text().replace('default_theme = "acme"', 'default_theme = "standard"'))
        assert "docs.default_theme" not in kinds()  # 組み込みの standard
        toml.write_text(toml.read_text().replace('default_theme = "standard"', 'default_theme = "us"'))
        dput("us", {"description": "米国向け", "page": [215.9, 279.4]})
        assert "docs.default_theme" not in kinds() and "ドキュメントのテーマの説明" not in kinds() and "docs.themes" not in kinds()
        assert "review.plan_reviewer" not in kinds() and "review.deck_review_max_rounds" not in kinds()  # 雛形の既定
        toml.write_text(toml.read_text().replace('plan_reviewer = "ai"', 'plan_reviewer = "AI"').replace("deck_review_max_rounds = 3", "deck_review_max_rounds = 5"))
        assert kinds()["review.plan_reviewer"] == "要修正" and kinds()["review.deck_review_max_rounds"] == "要修正"
        toml.write_text(toml.read_text().replace('plan_reviewer = "AI"', 'plan_reviewer = "human"').replace("deck_review_max_rounds = 5", "deck_review_max_rounds = true"))
        assert "review.plan_reviewer" not in kinds() and kinds()["review.deck_review_max_rounds"] == "要修正"
        toml.write_text(toml.read_text().replace("deck_review_max_rounds = true", "deck_review_max_rounds = 1"))
        assert "review.deck_review_max_rounds" not in kinds()
        assert "feedback.google_comments.watch_hours" not in kinds()  # 雛形の 0（見張らない）
        for v, ok in (('"48h"', False), ("-1", False), ("true", False), ("inf", False), ("nan", False), ("48", True), ("1.5", True), ("0", True)):
            toml.write_text(re.sub(r"(?m)^watch_hours = .*$", f"watch_hours = {v}", toml.read_text(), count=1))
            assert ("feedback.google_comments.watch_hours" not in kinds()) == ok, v
        with contextlib.redirect_stdout(io.StringIO()):
            assert main([tmp, "--local"]) == (0 if shutil.which("uv") else 1)
        toml.write_text(toml.read_text().replace('shared_themes = ""', 'shared_themes = "shared"'))
        import gapi, slides
        cwd, saved = os.getcwd(), (gapi.request, slides.shared_files, slides.theme_files)
        gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else {"name": "x"}
        shared = lambda: next(d for _, n, d in check(Path(tmp)) if n == "共有テーマ")

        def unreadable(folder, named=True):
            raise gapi.ApiError("404")
        try:
            slides.shared_files, slides.theme_files = lambda: [], lambda folder, named=True: [{"id": "a"}, {"id": "b"}]
            assert "2 個あるが" in shared()  # 名前のない Slides だけ
            slides.theme_files = lambda folder, named=True: []
            assert shared().startswith("テーマがない")
            slides.shared_files = lambda: [{"id": "a", "properties": {slides.THEME_PROP: "acme"}}]
            slides.theme_files = lambda folder, named=True: 1 / 0  # 名前のあるものがあれば、もう 1 回は読まない
            assert shared().startswith("acme")
            slides.shared_files, slides.theme_files = lambda: [], unreadable
            assert "共有テーマ" not in {n for _, n, _ in check(Path(tmp))}  # 読めなければ出さない（止まらない）
        finally:
            gapi.request, slides.shared_files, slides.theme_files = saved
            os.chdir(cwd)
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
