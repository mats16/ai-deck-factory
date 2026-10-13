#!/usr/bin/env python3
"""プラグインの改善を、過去の資料で確かめてから PR にする（手順は ../SKILL.md）。ワークスペース（factory.toml のあるフォルダ）で回す。
usage:
  kaizen.py start   <名前>                          元のリポジトリ（[factory] source）に kaizen/<名前> の worktree を作る。前の版（origin/main）も写す
  kaizen.py lint    <名前> <資料の URL ...>          いまの資料の JSON に、前の版と変えた版の lint をかけて比べる
  kaizen.py rebuild <名前> <資料のフォルダ ...> [--pages 2,5] [--keep]   build/ の正本（pages.py・doc.md）を前の版と変えた版で仮に組み、ページの画像を並べて比べる
  kaizen.py open    <名前> --title <題> --body <本文.md> [--draft]   本文と検証の記録をまとめて PR を作る（commit は先に済ませる。PR があれば本文を書き換える）
  kaizen.py clean   <名前>                          worktree と検証の記録を消す（PR がマージか却下されたあと）
  kaizen.py --selftest
置き場所は <ワークスペース>/.factory/kaizen/<名前>/（repo/ 変える版、base/ 前の版、verify/ 検証の記録）。資料の名前・URL・本文は verify/detail.md にだけ書き、
PR には「資料 1」のような番号と、規則ごとの数の変化と、選んだ画像だけを出す。"""
import json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deck-build" / "scripts"))
import gapi

SECTIONS = ("## 変えること", "## 理由", "## 背景", "## 過去資料での検証")
DESIGN = re.compile(r"skills/(deck-practices/visual(_doc)?\.md|deck-build/(scripts/(slides|template|docs|box_pad|doc_layout)\.py|assets/))")  # 見た目が変わりうるファイル
URL_ID = re.compile(r"https://docs\.google\.com/(?:presentation|document)/d/([\w-]+)")
COUNT = re.compile(r"^== (要修正|要確認)[^:]*: (\d+) ==$", re.M)
HIT = re.compile(r"^\[(.+?)\] (.*)$", re.M)


def sh(*cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if check and r.returncode:
        sys.exit(f"止まった（exit {r.returncode}）: {' '.join(map(str, cmd))}\n{r.stderr.strip()[-1500:]}")
    return r


class Work:
    def __init__(self, name):
        self.ws = gapi.factory_path().parent
        self.name, self.branch = name, f"kaizen/{name}"
        self.dir = self.ws / ".factory" / "kaizen" / name
        self.repo, self.base, self.verify = self.dir / "repo", self.dir / "base", self.dir / "verify"
        src = gapi.factory().get("factory", {}).get("source")
        self.src = Path(src).expanduser() if src else None

    def need(self):
        if not self.repo.is_dir():
            sys.exit(f"{self.repo} がない。先に kaizen.py start {self.name}")

    def label(self, key):
        """資料の番号（PR には資料の名前を出さない）。"""
        self.verify.mkdir(parents=True, exist_ok=True)
        f = self.verify / "labels.json"
        labels = json.loads(f.read_text()) if f.is_file() else {}
        labels.setdefault(key, f"資料 {len(labels) + 1}")
        f.write_text(json.dumps(labels, ensure_ascii=False, indent=1))
        return labels[key]

    def scripts(self, side):
        return (self.base if side == "base" else self.repo) / "skills" / "deck-build" / "scripts"

    def log(self, detail, public):
        self.verify.mkdir(parents=True, exist_ok=True)
        for f, text in (("detail.md", detail), ("pr.md", public)):
            with open(self.verify / f, "a", encoding="utf-8") as fh:
                fh.write(text.rstrip() + "\n\n")


def compare(before, after):
    """lint の出力 2 つから、数と、規則ごとの指摘の増減。"""
    counts = lambda out: {k: sum(int(n) for kk, n in COUNT.findall(out) if kk == k) for k in ("要修正", "要確認")}
    hits = lambda out: {(k, v) for k, v in HIT.findall(out)}
    b, a = hits(before), hits(after)
    rules = sorted({k for k, _ in b ^ a})
    delta = {k: (sum(x == k for x, _ in b), sum(x == k for x, _ in a)) for k in rules}
    return counts(before), counts(after), delta, sorted(b - a), sorted(a - b)


def report(label, kind, cb, ca, delta, gone, new, title=""):
    head = f"#### {label}（{kind}）\n\n| | 前の版 | 変えた版 |\n|---|---|---|\n" + "".join(f"| {k} | {cb[k]} | {ca[k]} |\n" for k in cb)
    rules = "".join(f"- {k}: {x} → {y}\n" for k, (x, y) in delta.items()) or "- 指摘の変化なし\n"
    detail = f"{head}\n{title}\n\n{rules}\n消えた指摘:\n" + "".join(f"- [{k}] {v}\n" for k, v in gone[:20]) + "\n増えた指摘:\n" + "".join(f"- [{k}] {v}\n" for k, v in new[:20])
    return detail, f"{head}\n規則ごとの指摘の数:\n\n{rules}"


def start(w):
    if not w.src or not (w.src / ".git").exists():
        sys.exit("factory.toml の [factory] source に、プラグインのリポジトリの git の checkout（持ち主でなければ fork）を書く")
    if w.dir.exists():
        sys.exit(f"{w.dir} がもうある（続けるならそのまま使う。やり直すなら kaizen.py clean {w.name}）")
    sh("git", "-C", w.src, "fetch", "-q", "origin")
    sh("git", "-C", w.src, "worktree", "add", "-q", "-b", w.branch, w.repo, "origin/main")
    w.base.mkdir(parents=True)
    arch = subprocess.run(["git", "-C", str(w.src), "archive", "origin/main"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(w.base)], input=arch, check=True)
    print(f"変える版: {w.repo}（ブランチ {w.branch}）\n前の版: {w.base}（origin/main）\n変えたら commit し、kaizen.py lint・rebuild で確かめる")


def lint_cmd(w, urls):
    w.need()
    for url in urls:
        fid = gapi.file_id(url)
        kind, data = ("ドキュメント", gapi.request("GET", f"{gapi.DOCS}/{fid}")) if "/document/" in url else ("スライド", gapi.request("GET", f"{gapi.SLIDES}/{fid}"))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
        outs = [sh(sys.executable, w.scripts(side) / "lint.py", f.name, cwd=w.ws, env={"FACTORY_VERIFY": "1"}, check=False).stdout for side in ("base", "head")]
        os.unlink(f.name)
        detail, public = report(w.label(url), kind, *compare(*outs), title=f"{data.get('title', '')} {url}")
        w.log("### lint\n\n" + detail, "### lint\n\n" + public)
        print(detail)


def rebuild(w, folders, pages=None, keep=False):
    w.need()
    out_dir = gapi.factory().get("drive", {}).get("factory") or sys.exit("factory.toml の drive.factory（仮に組む Drive のフォルダ）がない")
    img = w.verify / "img"
    img.mkdir(parents=True, exist_ok=True)
    for folder in map(Path, folders):
        build = folder.resolve() / "build"
        slides = (build / "pages.py").is_file()
        if not slides and not (build / "doc.md").is_file():
            sys.exit(f"{build} に pages.py も doc.md もない")
        label = w.label(str(folder.resolve().relative_to(w.ws)))
        made, outs, shots = [], [], {}
        try:
            for side in ("base", "head"):
                s = w.scripts(side)
                r = sh(sys.executable, s / ("slides.py" if slides else "docs.py"), "new", out_dir, f"{time.strftime('%Y%m%d')}_検証_{w.name}_{label.replace(' ', '')}_{side}", cwd=build, env={"FACTORY_VERIFY": "1"})
                fid = URL_ID.findall(r.stdout)[-1]
                made.append(fid)
                cmd = [sys.executable, s / ("gslides.py" if slides else "docs.py"), "check", fid] + (["--pages", pages] if pages and slides else [])
                outs.append(sh(*cmd, cwd=build, env={"FACTORY_VERIFY": "1"}, check=False).stdout)
                shots[side] = {p.name: p for p in sorted(Path(f"/tmp/{'slides' if slides else 'docs'}_{fid[:8]}").glob("p-*.png"))}
        finally:
            for fid in made if not keep else []:
                gapi.trash(fid)
        changed, want = [], {int(x) for x in pages.split(",")} if pages else None
        for n in sorted(set(shots["base"]) & set(shots["head"]), key=lambda x: int(re.sub(r"\D", "", x))):
            page = int(re.sub(r"\D", "", n))
            if want and page not in want or shots["base"][n].read_bytes() == shots["head"][n].read_bytes():
                continue  # 選んでいないページと、前後で同じ画像のページ
            num = re.sub(r"\D", "", label)  # f-string の中の \ は Python 3.12 から
            out = img / f"deck{num}_p{page}.png"  # エージェントが読み書きするファイルは英数字の名前
            sh("uv", "run", "-q", w.scripts("head") / "sheet.py", out, shots["base"][n], shots["head"][n], "--cols", "2", "--width", "800")
            changed.append((page, out))
        detail, public = report(label, "スライド" if slides else "ドキュメント", *compare(*outs), title=str(folder))
        pics = "変わったページ: " + (", ".join(f"p{p}" for p, _ in changed) or "なし") + "（左が前の版、右が変えた版）\n\n" + "".join(f"<!-- img:{o.name} -->\n" for _, o in changed)
        w.log("### 組み直し\n\n" + detail + "\n" + pics, "### 組み直し\n\n" + public + "\n" + pics)
        print(detail + "\n" + pics + (f"\n画像: {img}" if changed else "") + ("" if not keep else f"\n仮の資料（--keep）: {', '.join(made)}"))


def upload_images(w, files):
    """画像を pr-assets ブランチ（main とは別の、画像だけのブランチ）に置き、PR から見える URL を返す。"""
    repo = str(w.repo)
    sh("git", "-C", repo, "fetch", "-q", "origin", "pr-assets", check=False)
    parent = sh("git", "-C", repo, "rev-parse", "-q", "--verify", "origin/pr-assets", check=False).stdout.strip()
    env = {"GIT_INDEX_FILE": str(w.dir / "assets.index")}
    Path(env["GIT_INDEX_FILE"]).unlink(missing_ok=True)
    if parent:
        sh("git", "-C", repo, "read-tree", parent, env=env)
    for f in files:
        blob = sh("git", "-C", repo, "hash-object", "-w", f).stdout.strip()
        sh("git", "-C", repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{w.branch}/{f.name}", env=env)
    tree = sh("git", "-C", repo, "write-tree", env=env).stdout.strip()
    commit = sh("git", "-C", repo, "commit-tree", tree, *(["-p", parent] if parent else []), "-m", f"{w.branch} の画像").stdout.strip()
    sh("git", "-C", repo, "push", "-q", "origin", f"{commit}:refs/heads/pr-assets")
    slug = sh("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner", cwd=repo).stdout.strip()
    return {f.name: f"https://github.com/{slug}/blob/pr-assets/{w.branch}/{f.name}?raw=true" for f in files}


def private_words(ws, extra=()):
    """PR に出してはいけない語: Customers/ の顧客の名前、Customers/<顧客>/ と Internal/ の資料のフォルダの名前（年の 4 桁の数字が入ったもの。
    決まりでは <内容>_<日付>。review_2026q3 のような形も入る）、factory.toml の [factory] private（日本語の社名・製品名、日付のないフォルダの名前など）。
    日付のないフォルダ（assets・drafts など）は、ありふれた語で関係のない PR を止めるので、名前だけでは入れない（要るなら private に書く）。"""
    names = {p.name for p in (ws / "Customers").glob("*") if p.is_dir()}
    names |= {p.name for p in [*(ws / "Customers").glob("*/*"), *(ws / "Internal").glob("*")] if p.is_dir() and re.search(r"\d{4}", p.name)}
    extra = [extra] if isinstance(extra, str) else list(extra)  # private = "アクメ" と書いても 1 語（1 字ずつに分けない）
    return sorted(names | {str(x).strip() for x in extra if str(x).strip()})  # 空の語は何にでも合うので外す


def leaks(text, words):
    """text に出てくる words（大文字と小文字は区別しない。前後が英数字のときは別の語とみなす）。"""
    return [x for x in words if re.search(rf"(?<![A-Za-z0-9]){re.escape(x)}(?![A-Za-z0-9])", text, re.I)]


def outgoing(title, body, branch, messages, patches, changed):
    """PR と push で外に出る文字。open が leaks で確かめる。push はブランチのコミットを全部送るので、差し引きの差分ではなく、コミットごとに見る:
    題、本文、ブランチの名前（push と pr-assets のコミット）、すべてのコミットメッセージ、各コミットの足した行とファイルの名前（+++ b/…・diff --git）、
    本文の「変えたファイル」に入る名前。消した行は、もとから公開されている版か、前のコミットで足した行（そちらで見る）なので見ない。"""
    added = [x for x in patches.splitlines() if x.startswith(("+", "diff --git"))]
    return "\n".join([title, body, branch, messages, *changed, *added])


def check_body(body, changed, verify_text, images):
    """足りないものの一覧（空なら出せる）。"""
    miss = [f"本文に「{s}」の節がない" for s in SECTIONS if s not in body]
    if not verify_text and "検証しない理由" not in body:
        miss.append("過去資料での検証がない（kaizen.py lint か rebuild を回す。回せないなら「過去資料での検証」の節に「検証しない理由:」を書く）")
    if any(DESIGN.search(f) for f in changed) and not images:
        miss.append("見た目に関わるファイルを変えたのに、前後の画像がない（kaizen.py rebuild で、変わるページのある資料を組み直す）")
    return miss


def place_images(verify_text, urls):
    """目印（<!-- img:<ファイル名> -->、rebuild が変わったページに付ける）を画像に替える。目印のない画像（verify/img/ に手で置いたもの）は、黙って落とさず末尾にまとめて載せる。"""
    marked = set(re.findall(r"<!-- img:(.+?) -->", verify_text))
    text = re.sub(r"<!-- img:(.+?) -->", lambda m: f"![{m.group(1)}]({urls[m.group(1)]})" if m.group(1) in urls else "", verify_text)
    rest = [n for n in urls if n not in marked]
    return text.rstrip() + "\n\n### ほかの画像（verify/img/ に手で置いたもの）\n\n" + "".join(f"![{n}]({urls[n]})\n" for n in rest) if rest else text


def open_pr(w, title, body_file, draft=False):
    w.need()
    if sh("git", "-C", w.repo, "status", "--porcelain").stdout.strip():
        sys.exit("変える版に commit していない変更がある。commit してから open する")
    git = lambda *a: sh("git", "-c", "core.quotepath=false", "-C", w.repo, *a).stdout  # 日本語のファイルの名前を \343… に書き換えさせない（確かめで見えなくなる）
    changed = git("diff", "--name-only", "origin/main...HEAD").splitlines()
    if not changed:
        sys.exit("origin/main からの変更がない")
    body = Path(body_file).read_text()
    pr_md = w.verify / "pr.md"
    verify_text = pr_md.read_text() if pr_md.is_file() else ""
    images = sorted((w.verify / "img").glob("*.png")) if (w.verify / "img").is_dir() else []
    if miss := check_body(body, changed, verify_text, images):
        sys.exit("PR にできない:\n" + "\n".join(f"- {m}" for m in miss))
    # 外に出す前に（画像を上げる前、push の前に）、外に出るものを全部確かめる。本文は、足す検証の記録（ワークスペースの点検の規則の名前も入る）と画像の名前まで含める
    messages = git("log", "origin/main..HEAD", "--format=%B")
    patches = git("log", "-p", "--cc", "--format=", "origin/main..HEAD")  # 途中のコミットで足して消した行も、push で出る。--cc はマージで衝突を解いたときの変更も出す
    text = outgoing(title, "\n".join([body, verify_text, *(f.name for f in images)]), w.branch, messages, patches, changed)
    if hit := leaks(text, private_words(w.ws, gapi.factory().get("factory", {}).get("private", []))):
        sys.exit("PR にできない: 題・本文（検証の記録を含む）・コミットメッセージ・ファイルの名前・足した行に、顧客や社内の資料の名前がある: " + "、".join(hit)
                 + "。「顧客向けの資料」「（顧客）」のような一般の形にして commit し直す（コミットメッセージは git commit --amend か rebase で直す）")
    urls = upload_images(w, images) if images else {}
    verify_text = place_images(verify_text, urls)
    final = body.rstrip() + "\n\n## 検証の記録（factory-kaizen）\n\n変えたファイル: " + ", ".join(f"`{f}`" for f in changed) + "\n\n" + verify_text
    (w.dir / "pr_body.md").write_text(final)
    sh("git", "-C", w.repo, "push", "-q", "-u", "origin", w.branch)
    url = sh("gh", "pr", "view", w.branch, "--json", "url", "-q", ".url", cwd=w.repo, check=False).stdout.strip()
    if url:  # 2 回目からは、同じ PR の題と本文を書き換える（検証をやり直したとき）
        sh("gh", "pr", "edit", url, "--title", title, "--body-file", w.dir / "pr_body.md", cwd=w.repo)
    else:
        url = sh("gh", "pr", "create", "--base", "main", "--head", w.branch, "--title", title, "--body-file", w.dir / "pr_body.md", *(["--draft"] if draft else []), cwd=w.repo).stdout.strip()
    print(url)


def clean(w):
    if w.repo.is_dir() and w.src:
        sh("git", "-C", w.src, "worktree", "remove", "--force", w.repo, check=False)
    shutil.rmtree(w.dir, ignore_errors=True)
    print(f"消した: {w.dir}")


def selftest():
    before = "== 要修正: 1 ==\n[絵文字] p1: 「✅」\n\n== 要確認: 2 ==\n[あおり] p2: 「このままでは」\n[空疎な言い回し] p3: 「実現する」\n"
    after = "== 要修正: 0 ==\n\n== 要確認: 2 ==\n[あおり] p2: 「このままでは」\n[空疎な言い回し] p3: 「実現する」\n\n== 要確認（ワークスペースの点検）: 1 ==\n[気になる語] p4\n"
    cb, ca, delta, gone, new = compare(before, after)
    assert cb == {"要修正": 1, "要確認": 2} and ca == {"要修正": 0, "要確認": 3}
    assert delta == {"気になる語": (0, 1), "絵文字": (1, 0)} and gone == [("絵文字", "p1: 「✅」")] and new == [("気になる語", "p4")]
    detail, public = report("資料 1", "スライド", cb, ca, delta, gone, new, title="Acme様_秘密の資料")
    assert "Acme" in detail and "Acme" not in public and "✅" not in public  # PR には資料の名前も本文も出さない
    body = "\n".join(SECTIONS)
    assert check_body(body, ["skills/deck-build/scripts/lint.py"], "x", []) == []
    assert len(check_body(body, ["skills/deck-practices/visual.md"], "x", [])) == 1  # 見た目なのに画像がない
    assert len(check_body("## 理由", ["skills/deck-build/scripts/lint.py"], "", [])) == 4  # 節が 3 つと、検証がない
    assert check_body(body + "\n検証しない理由: 文の直しだけ", ["skills/dreaming/SKILL.md"], "", []) == []
    urls = {"deck1_p2.png": "u1", "sample_p1.png": "u2"}
    placed = place_images("### 組み直し\n\n<!-- img:deck1_p2.png -->\n", urls)
    assert placed.index("![deck1_p2.png](u1)") < placed.index("### ほかの画像") < placed.index("![sample_p1.png](u2)") and placed.count("](u1)") == 1  # 目印のない画像も落とさず、末尾に 1 回だけ
    assert place_images("x\n<!-- img:deck1_p2.png -->\n", {"deck1_p2.png": "u1"}) == "x\n![deck1_p2.png](u1)\n"  # みな目印があれば、末尾には足さない
    with tempfile.TemporaryDirectory() as d:  # 顧客と資料のフォルダの名前、[factory] private の語が PR に入ったら止める
        for x in ("Customers/Acme/sample_briefing_202610", "Customers/Acme/review_2026q3", "Customers/Acme/assets", "Internal/grok_study_202610", "Internal/drafts"):
            (Path(d) / x).mkdir(parents=True)
        words = private_words(Path(d), ["アクメ"])
        assert words == ["Acme", "grok_study_202610", "review_2026q3", "sample_briefing_202610", "アクメ"], words  # 年の数字の入ったフォルダは見る。日付のないフォルダ（assets・drafts）は普通の語なので見ない
        assert leaks("+（2026-10-09、`Customers/ACME/sample_briefing_202610` p.2 でアクメの）", words) == ["Acme", "sample_briefing_202610", "アクメ"]
        assert leaks("+顧客向けの資料の p.2（AcmeCorp ではない）", words) == []
        clean = "diff --git a/skills/x.md b/skills/x.md\n--- a/skills/x.md\n+++ b/skills/x.md\n-Acme の古い行（もとの版）\n+顧客向けの資料\n"
        out = lambda messages="", patches=clean, changed=("skills/x.md",), branch="kaizen/lint": leaks(outgoing("題", "本文", branch, messages, patches, list(changed)), words)
        assert out() == []  # 消した行（もとの版）は見ない
        assert out(messages="- sample_briefing_202610 の指摘を入れる\n") == ["sample_briefing_202610"]  # コミットメッセージ（箇条書きの行も）
        assert out(patches=clean.replace("skills/x.md", "skills/acme_rules.md")) == ["Acme"]  # 各コミットのファイルの名前
        assert out(patches="+Customers/Acme/sample_briefing_202610 p.2\n" + clean.replace("+顧客", "-Customers/Acme/sample_briefing_202610 p.2\n+顧客")) == ["Acme", "sample_briefing_202610"]  # 途中のコミットで足して、あとで消した行
        assert out(branch="kaizen/acme-fix") == ["Acme"]  # ブランチの名前
        assert private_words(Path(d), "アクメ")[-1] == "アクメ" and "" not in private_words(Path(d), ["", " "])  # 文字列でも 1 語、空の語は外す
    print("selftest ok")


def main(a):
    if a == ["--selftest"]:
        return selftest()
    if len(a) < 2 or a[0] not in ("start", "lint", "rebuild", "open", "clean"):
        sys.exit(__doc__)
    w, rest = Work(a[1]), a[2:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    plain = [x for i, x in enumerate(rest) if not x.startswith("--") and (i == 0 or rest[i - 1] not in ("--pages", "--title", "--body"))]
    if a[0] == "start":
        start(w)
    elif a[0] == "lint":
        lint_cmd(w, plain)
    elif a[0] == "rebuild":
        rebuild(w, plain, opt("--pages"), "--keep" in rest)
    elif a[0] == "open":
        open_pr(w, opt("--title") or sys.exit("--title が要る"), opt("--body") or sys.exit("--body が要る"), "--draft" in rest)
    else:
        clean(w)


if __name__ == "__main__":
    gapi.run(lambda: main(sys.argv[1:]))
