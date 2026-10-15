#!/usr/bin/env python3
"""usage: doctor.py [<ワークスペース>] [--local]   （--selftest で自己確認）
AI Deck Factory を動かす前提を確かめる。--local は手元だけ見て、Google の API を呼ばない。
1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。標準ライブラリだけ。"""
import io, contextlib, os, shutil, subprocess, sys, tempfile, tomllib
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
        warn("顧客の memory", f"前の形の CLAUDE.md がある。Claude Code しか読まない（hook が Claude Code と pi で続けて出すのは memory.md）: {', '.join(map(how, old))}")
    if "人がレビューするかも選んでもらう" in ((root / "AGENTS.md").read_text() if (root / "AGENTS.md").is_file() else ""):  # 2026-10-13 までの雛形
        warn("AGENTS.md の方針のレビュー", "前の雛形の「人がレビューするかも選んでもらう」が残っている。ワークスペースの決まりが優先するので、factory.toml の [review] plan_reviewer が効かず、資料ごとに聞く。factory-init の雛形の今の文（plan_reviewer に従う）に替える")
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
    import slides  # 仮の著作権表示（PLACEHOLDER_COPYRIGHT。need_brand と同じ）と、組み込みのテーマの説明（THEME_NOTES）
    brand = cfg.get("brand", {})
    marks = [("brand.copyright", brand.get("copyright", ""))]  # テーマの copyright は、そのテーマのデッキで [brand] の代わりに書く（slides.py の use_theme）
    marks += [(f"slides.themes.{n}.copyright", t["copyright"]) for n, t in cfg.get("slides", {}).get("themes", {}).items()
              if isinstance(t.get("copyright"), str)]  # 文字列でない値は、下の theme_values が slides.themes.<名前> に出す（2 回出さない）
    for kind, validate in (("slides", lambda t: (slides.theme_values(t), slides.theme_font(t))), ("docs", lambda t: (slides.theme_font(t), slides.theme_mono(t)))):
        for n, t in cfg.get(kind, {}).get("themes", {}).items():  # 組むときに止まる値（色・copyright・書体）を、組む前に出す（slides.py・docs.py と同じ関数で見る）
            try:
                validate(t)
            except SystemExit as e:
                ng(f"{kind}.themes.{n}", str(e))
    for key, c in marks:
        if not (c := str(c).strip()):
            ng(key, "空。スライドもドキュメントも組めない（全ページの左下に書く著作権表示がない）。自分の会社の著作権表示を書く")
        elif c == slides.PLACEHOLDER_COPYRIGHT:
            ng(key, f"「{c}」は書いていないときの仮の値。スライドもドキュメントも組めない。自分の会社の著作権表示を書く")
        elif not COPYRIGHT_FOOTER.fullmatch(c):
            ng(key, f"「{c}」は「© <年> <社名> All rights reserved.」の形でない。lint が全ページの著作権表示を 11pt 未満として止める")
    if not brand.get("company"):
        warn("brand.company", "空。表紙の左下に社名を置かない")
    mine, docs = sl.get("themes", {}), cfg.get("docs", {})
    theme, temps = sl.get("default_theme", "visual"), {k: t["url"] for k, t in mine.items() if t.get("url")}
    if old := {k: v for k, v in sl.get("templates", {}).items() if not mine.get(k, {}).get("url")}:  # 2026-10-12 までの書き方
        ng("slides.templates", f"{', '.join(old)} のテンプレートの URL を [slides.themes.<名前>] の url に移す（[slides.templates] の visual = \"…\" → [slides.themes.visual] の url = \"…\"）")
    if stale := [f"slides.themes.{k}.base" for k, t in mine.items() if "base" in t] + ["slides.base_template"] * ("base_template" in sl):  # 2026-10-14 までの書き方
        ng("slides の base", f"{', '.join(stale)} を消す。元のテンプレートは factory.toml に持たず、template.py <テーマ> --from-base <元の URL> で渡す（渡さなければ白紙の pptx から作る）。残っていると template.py が止まる")
    if sl.get("template_folder"):  # 2026-10-12 までの書き方
        warn("slides.template_folder", "プラグインは読まない。新しく作るテンプレートは [drive] factory の下の Themes に作る（前の版のスクリプトで動かさなくなったら消す）")
    if sl.get("templates") and not old:
        warn("slides.templates", "プラグインは読まない（[slides.themes.<名前>] の url を読む）。前の版のスクリプト（.agents/skills/）で動かさなくなったら消す")
    (ok if temps.get(theme) else warn)("slides.themes の url", ", ".join(temps) if temps.get(theme) else
                                       f"既定のテーマ {theme} のテンプレートがない。template.py {theme} --from-base で作るか、共有のテーマ（slides.py themes）の url を書く")
    no_desc = [n for n in temps if not mine.get(n, {}).get("description") and n not in slides.THEME_NOTES]  # テンプレートの Drive の説明にあるかは、Google を見るところで
    desc_warn = lambda bad, note="": warn("slides.themes の説明", f"{', '.join(bad)} に description がない。エージェントが資料ごとにテーマを選べない"
                                                             f"（[slides.themes.<名前>] の description に、どの資料・聞き手に使うかを書く）{note}")
    if no_desc and local:
        desc_warn(no_desc, "。url のテンプレートの Drive の説明にあるかは --local なしで見る")
    if bad := [n for n, t in docs.get("themes", {}).items() if not t.get("description")]:
        warn("docs.themes の説明", f"{', '.join(bad)} に description がない。エージェントが資料ごとにテーマを選べない")
    if (d := docs.get("default_theme")) and d not in docs.get("themes", {}) and d != "standard":  # standard は組み込み（docs.py の STANDARD）
        ng("docs.default_theme", f"{d} が [docs.themes] にない。theme を書かない doc.md が組めない")
    review = cfg.get("review", {})  # 書いていなければ既定。読むのはエージェント（deck-practices の 5 と 6）
    if (p := review.get("plan_reviewer", "ai")) not in ("ai", "human"):
        ng("review.plan_reviewer", f"{p!r} は使えない。\"ai\" か \"human\" にする")
    if type(n := review.get("deck_review_max_rounds", 3)) is not int or not 1 <= n <= 3:  # bool は int の子なので type で見る
        ng("review.deck_review_max_rounds", f"{n!r} は使えない。1〜3 の整数にする（直すと欠陥が増えるので 3 より多くしない）")
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
        if no_desc:  # テンプレートの Drive の説明を見られないので、--local と同じに出す
            desc_warn(no_desc, "。url のテンプレートの Drive の説明にあるかは、Google の認証が通ってから見る")
        return out
    targets = [(f"slides.themes.{k}.url", v) for k, v in temps.items()] + [(f"docs.templates.{k}", v) for k, v in cfg.get("docs", {}).get("templates", {}).items()]
    targets += [(f"drive.{k}", v) for k, v in dr.items() if v]
    for name, url in targets:
        fid = gapi.folder_id(url) if "/folders/" in url else gapi.file_id(url)
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{fid}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except gapi.ApiError as e:
            ng(name, f"開けない（{str(e).split()[0]}）: {url}")
    if bad := [n for n in no_desc if not slides.theme_description(n)]:  # url だけを書いたテーマは、テンプレートの Drive の説明を使う
        desc_warn(bad)
    if dr.get("shared_themes"):  # 全社の共有テーマのフォルダ。探すときだけ読む（使うテーマは [slides.themes.<名前>] の url）
        try:
            files, have = slides.shared_files(), {gapi.file_id(u) for u in temps.values()}  # 自分の Themes は読まない（slides.py themes が出す）
            names, new = [f["properties"][slides.THEME_PROP] for f in files], [f["properties"][slides.THEME_PROP] for f in files if f["id"] not in have]
            bare = 0 if names else len(slides.theme_files(gapi.folder_id(dr["shared_themes"]), named=False))  # 名前のあるものが 1 つでもあれば数えない（base の写しのように、名前がなくて正しいものもある）
        except slides.READ_ERRORS:  # 開けないことは drive.shared_themes に出ている
            return out
        if dup := sorted({n for n in names if names.count(n) > 1}):
            warn("共有テーマ", f"同じ名前のテーマが 2 つ以上ある（どれを url で指すか迷う。古いほうをフォルダから外す）: {', '.join(dup)}")
        elif bare:  # テーマの名前を書く前（2026-10-14 より前）の template.py で作ったもの
            warn("共有テーマ", f"Google Slides が {bare} 個あるが、どれにもテーマの名前（{slides.THEME_PROP}）がない。持ち主が template.py <テーマ> で合わせ直すと書かれる")
        elif not names:
            warn("共有テーマ", "テーマがない。管理者が template.py で作ったテンプレートを置く（ほかのファイルは読まない）")
        else:
            ok("共有テーマ", ", ".join(names) + (f"（factory.toml にない: {', '.join(new)}。使うなら slides.py themes の url を書く）" if new else ""))
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
        assert k["AGENTS.md"] == "OK" and k["スキルの重なり"] == "要確認" and k["slides.themes の url"] == "要確認" and k["drive.customers"] == "要確認"
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
        toml = Path(tmp) / "factory.toml"
        assert kinds()["brand.copyright"] == "要修正" and kinds()["brand.company"] == "要確認"
        toml.write_text(toml.read_text().replace("[brand]", '[brand]\ncopyright = "© Acme 2026"', 1))
        assert kinds()["brand.copyright"] == "要修正"
        toml.write_text(toml.read_text().replace('"© Acme 2026"', '"© 2026 Example, Inc. All rights reserved."'))
        assert kinds()["brand.copyright"] == "要修正"  # 仮の値をそのまま書いた
        toml.write_text(toml.read_text().replace('"© 2026 Example, Inc. All rights reserved."', '"© 2026 Acme, Inc. All rights reserved."'))
        assert "brand.copyright" not in kinds()
        toml.write_text(toml.read_text() + '\n[slides.themes.mine]\ncopyright = "© Me 2026"\n')
        assert kinds()["slides.themes.mine.copyright"] == "要修正"  # テーマの copyright にも同じ確かめ
        toml.write_text(toml.read_text().replace('"© Me 2026"', '"© 2026 Me. All rights reserved."'))
        assert "slides.themes.mine.copyright" not in kinds()
        toml.write_text(toml.read_text() + 'TEXT = "red"\n\n[docs.themes.us2]\nmono = "Fira Code"\n')
        assert kinds()["slides.themes.mine"] == "要修正" and kinds()["docs.themes.us2"] == "要修正"  # 6 桁でない色、リガチャの出る等幅
        toml.write_text(toml.read_text().replace('\n[slides.themes.mine]\ncopyright = "© 2026 Me. All rights reserved."\nTEXT = "red"\n\n[docs.themes.us2]\nmono = "Fira Code"\n', ""))
        assert "slides.themes.mine" not in kinds() and "docs.themes.us2" not in kinds()
        toml.write_text(toml.read_text() + '\n[slides.themes.num]\ncopyright = 2026\n')
        assert kinds()["slides.themes.num"] == "要修正" and "slides.themes.num.copyright" not in kinds()  # 文字列でない copyright は 1 回だけ出す
        toml.write_text(toml.read_text().replace('\n[slides.themes.num]\ncopyright = 2026\n', ""))
        toml.write_text(toml.read_text() + '\n[slides.templates]\nvisual = "x"\n')
        assert kinds()["slides.templates"] == "要修正"  # 古い書き方だけ
        toml.write_text(toml.read_text().replace('[slides.templates]\nvisual = "x"\n', ""))
        assert "slides の base" not in kinds()  # 雛形には書いていない
        toml.write_text(toml.read_text().replace("[slides.themes.visual]", '[slides.themes.visual]\nbase = ""', 1))
        assert kinds()["slides の base"] == "要修正"  # 2026-10-14 までの書き方。空でも消す
        toml.write_text(toml.read_text().replace('[slides.themes.visual]\nbase = ""', "[slides.themes.visual]", 1))
        toml.write_text(toml.read_text() + '\n[docs]\ndefault_theme = "acme"\n\n[docs.themes.us]\npage = [215.9, 279.4]\n')
        assert kinds()["docs.default_theme"] == "要修正" and kinds()["docs.themes の説明"] == "要確認"  # 既定のテーマがない、説明がない
        toml.write_text(toml.read_text().replace('default_theme = "acme"', 'default_theme = "standard"'))
        assert "docs.default_theme" not in kinds()  # 組み込みの standard
        toml.write_text(toml.read_text().replace('default_theme = "standard"', 'default_theme = "us"').replace("[docs.themes.us]\n", '[docs.themes.us]\ndescription = "米国向け"\n'))
        assert "docs.default_theme" not in kinds() and "docs.themes の説明" not in kinds()
        assert "review.plan_reviewer" not in kinds() and "review.deck_review_max_rounds" not in kinds()  # 雛形の既定
        toml.write_text(toml.read_text().replace('plan_reviewer = "ai"', 'plan_reviewer = "AI"').replace("deck_review_max_rounds = 3", "deck_review_max_rounds = 5"))
        assert kinds()["review.plan_reviewer"] == "要修正" and kinds()["review.deck_review_max_rounds"] == "要修正"
        toml.write_text(toml.read_text().replace('plan_reviewer = "AI"', 'plan_reviewer = "human"').replace("deck_review_max_rounds = 5", "deck_review_max_rounds = true"))
        assert "review.plan_reviewer" not in kinds() and kinds()["review.deck_review_max_rounds"] == "要修正"
        toml.write_text(toml.read_text().replace("deck_review_max_rounds = true", "deck_review_max_rounds = 1"))
        assert "review.deck_review_max_rounds" not in kinds()
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
