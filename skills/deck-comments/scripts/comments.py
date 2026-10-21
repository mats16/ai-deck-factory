#!/usr/bin/env python3
"""Google Slides・Docs の未解決のコメントを取り、返信する・解決する。直すのは通常の修正の流れ（../SKILL.md）。
usage（資料のフォルダで）:
  comments.py <URL か ID>...          未解決のコメントを全部出す。前に取ったあとに書かれたか返信のあったものに「新」を付ける
  comments.py --new <URL か ID>...    前に取ったあとに書かれたか返信のあった未解決のコメントだけを出す。なければ標準出力に何も出さない（見張るときに回す）
  --src <フォルダ>                     付いた文を探す手元の正本（既定: 今いるフォルダの build/）
  comments.py reply <URL か ID> <コメントの ID> <文> [--resolve]   返信する。--resolve を付けると、返信と一緒に解決する
  comments.py watch <URL か ID>... [--hours <時間>] [--start]   --new を 90 秒ごとに回し、新しいコメントが出たら出して返る。出なければ 270 秒で
                                      「まだ」と返る（見張りの子が呼び直す。../prompt_watch.md）。最後のコメント（なければ見張り始め。--start で今にする）から
                                      --hours（既定は factory.toml の [feedback.google_comments] watch_hours）のあいだ新しいコメントがなければ、「見張りを終える」と返る。
                                      資料には、AI が見張っていることと終える時刻をコメントに書き（知らせ）、終える時刻が延びたら返信し、終えたら返信して解決する
  comments.py watch-prompt <URL か ID>... [--hours <時間>] [--folder <資料のフォルダ>]   見張りの子に渡す依頼文（../prompt_watch.md を埋めたもの）を出す。
                                      資料のフォルダの既定は今いるフォルダ。埋め残しの差し込み先があれば止める
  comments.py --selftest
前に取った時刻、reply で送った返信の ID（--new で新しいと数えない）、見張りの起点、知らせのコメントの ID と書いた終える時刻は、ワークスペースの .factory/comments.json に残す。"""
import contextlib, datetime, html, json, math, os, re, shlex, sys, time, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deck-build" / "scripts"))
import gapi
from gapi import DRIVE, SLIDES, file_id, run

PROMPT = Path(__file__).resolve().parents[1] / "prompt_watch.md"
WAIT, POLL = 270, 90  # 1 回の watch で待つ秒（呼び直す子のプロンプトのキャッシュが 5 分で切れる前に返る）と、そのあいだに Drive を見る間隔
FIELDS = ("nextPageToken,comments(id,content,author(displayName,me),createdTime,modifiedTime,resolved,anchor,quotedFileContent(value),"
          "replies(id,content,author(displayName,me),modifiedTime,deleted))")
NOTICE = ("AI がこの資料のコメントを見張っています。付いたコメントは自動で読み、直せるものは資料を直して反映し、返信して解決します。"
          "見張りを終える時刻: {}（新しいコメントが来たら延ばし、ここに返信します）")


def fetch(fid, since=None):
    """消していないコメント（解決済みも）。since（Drive の時刻）を渡すと、それより後に書かれたか返信のあったものだけを頼む（startModifiedTime。境目のものも返る）。"""
    out, page = [], None
    while True:
        q = f"pageSize=100&fields={FIELDS}" + (f"&startModifiedTime={urllib.parse.quote(since)}" if since else "") + (f"&pageToken={urllib.parse.quote(page)}" if page else "")
        r = gapi.request("GET", f"{DRIVE}/files/{fid}/comments?{q}")
        out += r.get("comments", [])
        if not (page := r.get("nextPageToken")):
            return out


def state_path():
    return gapi.factory_path().parent / ".factory" / "comments.json"


@contextlib.contextmanager
def state():
    """.factory/comments.json を読んで渡し、ブロックを抜けたら書く（途中で止まったら書かない）。見張りの子と親の reply が同時に動いても
    互いの書き込みを消さないよう、そのあいだ錠をかけ、仮のファイルから差し替える。"""
    p = state_path()
    p.parent.mkdir(exist_ok=True)
    with open(p.with_suffix(".lock"), "a") as lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except ImportError:  # Windows。錠はかけない（同時に動かすことはまれ）
            pass
        st = {"seen": {}, "sent": [], "watch": {}, "notice": {}} | (json.loads(p.read_text()) if p.is_file() else {})
        yield st
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1))
        os.replace(tmp, p)


def post(fid, cid, text, resolve=False):  # 返信を送り、その ID を返す（resolve なら、返信と一緒に解決する。Drive は解決を返信の action で受ける）
    return gapi.request("POST", f"{DRIVE}/files/{fid}/comments/{cid}/replies?fields=id", {"content": text, **({"action": "resolve"} if resolve else {})})["id"]


def reply(fid, cid, text, resolve=False):
    """返信する。送った返信の ID を残し、--new で新しいと数えない。
    送るところから錠の中でする（送ってから ID を残すまでに見張りの子が取ると、自分の返信を新しいと数える）。"""
    with state() as st:
        st["sent"].append(post(fid, cid, text, resolve))


def bare(s):
    """突き合わせ用に、空白・記法（* ` <br>）・JSON の \\n と引用符を落とす。"""
    return re.sub(r'\\n|<br\s*/?>|[\s*`"]', "", s)


def where(quote, src):
    """付いた文がある手元のファイルと行（p05.json:12・doc.md:40）。付いた文のいちばん長い行で探し、3 つまで。"""
    key = bare(max(quote.splitlines() or [""], key=len))
    if len(key) < 2 or not src.is_dir():
        return []
    hits = [f"{f.name}:{i}" for f in sorted([*src.glob("p*.json"), *src.glob("*.md"), *src.glob("pages.py")])
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1) if key in bare(line)]
    return hits[:3]


def anchored(c):
    """Slides のコメントが付いたページの ID。anchor は、ページに付けると {"type": "page", "pages": ["<ページの ID>"]}、部品の文に付けると
    {"type": "shape", "subtype": "text", "page": "<ページの ID>", "targets": ["<部品の ID>"]}（2026-10-19 に画面で付けたコメントで確かめた）。Docs の anchor（kix.…）と、ないものは None。"""
    try:
        a = json.loads(c.get("anchor", ""))
    except ValueError:
        return None
    return (a.get("page") or (a.get("pages") or [None])[0]) if isinstance(a, dict) else None


def pager(fid, src):
    """ページの ID から「p.2（p02.json）」を返す関数。スライドの並びは、要るときに 1 回だけ取る。ファイルは build/deck.json の pages の並びから（数がスライドの枚数と合うときだけ）。"""
    got = {}

    def page(sid):
        if not got:
            got["ids"] = [s["objectId"] for s in gapi.request("GET", f"{SLIDES}/{fid}?fields=slides(objectId)").get("slides", [])]
            try:
                got["files"] = json.loads((src / "deck.json").read_text())["pages"]
            except (OSError, ValueError, KeyError):
                got["files"] = []
        ids, files = got["ids"], got["files"]
        if sid not in ids:
            return "消えたページ（組み直して作り直した）"
        n = ids.index(sid) + 1
        return f"p.{n}" + (f"（{files[n - 1]}）" if len(files) == len(ids) else "")
    return page


def one_line(s):
    return " / ".join(t.strip() for t in s.splitlines() if t.strip())


def who(a):
    return "自分" if a.get("me") else a.get("displayName", "?")


def latest(c, sent):
    """コメントの書き込みのいちばん新しい時刻。reply で送った返信と、消した返信は数えない（同じアカウントのユーザーのコメントと分けるため、書いた人では分けない）。
    コメントの modifiedTime は返信でも進むので、どの返信より新しいとき（本文を直した）だけ数える。"""
    replies = c.get("replies", [])
    acts = [c["createdTime"]] + [r["modifiedTime"] for r in replies if r.get("id") not in sent and not r.get("deleted")]
    if c["modifiedTime"] > max([c["createdTime"]] + [r["modifiedTime"] for r in replies]):
        acts.append(c["modifiedTime"])
    return max(acts)


def show(url, cs, seen, src, only_new, sent=(), page=None):
    """未解決のコメントを 1 件 1 行で出し、出した件数を返す。seen（前に取った時刻）より後の書き込みがあれば新しい。"""
    unresolved = [c for c in cs if not c.get("resolved")]
    new = [c for c in unresolved if latest(c, sent) > seen]
    shown = new if only_new else unresolved
    if not shown:
        return 0
    print(f"{url}（" + (f"新しい未解決 {len(new)} 件" if only_new else f"未解決 {len(unresolved)} 件、うち新しい {len(new)} 件") + "）")
    for c in shown:
        t = unstamp(c["modifiedTime"]).astimezone().strftime("%m-%d %H:%M")
        q = html.unescape(c.get("quotedFileContent", {}).get("value", ""))  # 付いた文は text/html で来る
        loc = page(sid) if page and (sid := anchored(c)) else ""
        quoted = f"「{one_line(q)[:40]}」" if q else ""
        if loc and quoted:
            at = f"{loc}の{quoted}に"
        elif loc:
            at = f"{loc} に"
        elif quoted:
            at = f"{quoted}に"
        else:
            at = "（付いた先が分からない。画面で見る）"
        hits = where(q, src) if q else []
        print(f"- {'[新] ' if c in new else ''}{c['id']} {who(c.get('author', {}))}（{t}）{at}: {one_line(c.get('content', ''))}"
              + (f"  → {'、'.join(hits)}" if hits else ""))
        for r in c.get("replies", []):
            if r.get("content") and not r.get("deleted"):
                print(f"    返信 {who(r.get('author', {}))}: {one_line(r['content'])}")
    return len(shown)


def scan(urls, src, only_new):
    """コメントを取って出す。出した件数と、ファイルごとの最後の書き込みの時刻（reply で送った返信は除く）を返す。"""
    n, last = 0, {}
    with state() as st:
        sent, notice = set(st["sent"]), {n["id"] for n in st["notice"].values()}
        for u in urls:
            fid = file_id(u)
            seen = st["seen"].get(fid, "")
            cs = [c for c in fetch(fid, seen if only_new and seen else None) if c["id"] not in notice]  # 見張りの知らせは、直すコメントではない
            n += show(u, cs, seen, src, only_new, sent, pager(fid, src))
            if cs:
                st["seen"][fid] = max([seen] + [c["modifiedTime"] for c in cs])
                last[fid] = max(latest(c, sent) for c in cs)
    return n, last


def stamp(t):  # epoch 秒を Drive の時刻の形（2026-10-19T00:24:21.986Z）に。文字列のまま比べられる
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def unstamp(t):  # stamp の逆。Drive の時刻を datetime に
    return datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))


def when(t):  # Drive の時刻を、コメントに書く手元の時刻（10月23日 18:00（JST））に
    d = unstamp(t).astimezone()
    return f"{d.month}月{d.day}日 {d:%H:%M}（{d:%Z}）"


def alive(fid, cid):
    """知らせのコメントが Drive に残っていて、解決されていない。読む人が消したか解決した知らせには、返信しない。"""
    try:
        c = gapi.request("GET", f"{DRIVE}/files/{fid}/comments/{cid}?fields=resolved,deleted")
    except gapi.ApiError as e:
        if str(e).startswith("404 "):
            return False
        raise
    return not c.get("resolved") and not c.get("deleted")


def announce(fids, hours):
    """見張る資料に、AI が見張っていることと終える時刻（起点の最後 + hours）を知らせのコメントに書く。もう書いてあり、終える時刻が変わったら
    （コメントを直したあとの --start で延びる）、知らせに返信する（知らせが消されたか解決されていたら、書き直す）。
    資料ごとに書き残す（2 つ目の資料で止まっても、1 つ目に書いた知らせを忘れて、もう 1 件書くことがないように）。
    もう終える時刻を過ぎていたら書かない（終える途中で止まって呼び直したとき、終えた資料にまた知らせを書かず、そのまま終える）。"""
    for f in fids:
        with state() as st:
            until = stamp(unstamp(max(st["watch"][g] for g in fids)).timestamp() + hours * 3600)
            note = st["notice"].get(f)
            if until <= stamp(time.time()) or note and when(until) == when(note["until"]):
                continue
            if note and alive(f, note["id"]):
                post(f, note["id"], f"見張りを終える時刻を {when(until)} に{'延ばし' if until > note['until'] else '変え'}ます")
                note["until"] = until
            else:
                st["notice"][f] = {"id": gapi.request("POST", f"{DRIVE}/files/{f}/comments?fields=id", {"content": NOTICE.format(when(until))})["id"], "until": until}


def watch(urls, src, hours, start=False):
    """新しいコメントが出るか、WAIT 秒たつか、期限が来るまで、POLL 秒ごとに見る。起点は .factory/comments.json の watch（ファイルごと）。"""
    fids = [file_id(u) for u in urls]
    with state() as st:
        for f in fids:
            if start or f not in st["watch"]:
                st["watch"][f] = stamp(time.time())
    announce(fids, hours)
    end = time.time() + WAIT
    while True:
        n, last = scan(urls, src, True)
        with state() as st:
            for f, t in last.items():
                st["watch"][f] = max(st["watch"].get(f, ""), t)
            expired = not n and max(st["watch"].get(f, "") for f in fids) < stamp(time.time() - hours * 3600)
        closed = 0
        for f in fids if expired else []:
            with state() as st:  # 資料ごとに書き残す（2 つ目で止まっても、1 つ目の知らせにもう一度返信しない）
                if (note := st["notice"].pop(f, None)) and alive(f, note["id"]):
                    post(f, note["id"], f"コメントの見張りを終えます（{hours:g} 時間、新しいコメントがありませんでした）。このあとのコメントは、自動では直しません。", resolve=True)
                    closed += 1
        if expired:
            with state() as st:  # 起点は、全部の知らせを閉じてから消す（途中で止まって呼び直すと、起点が残っているので、続きから終える）
                for f in fids:
                    st["watch"].pop(f, None)
        if n:
            return
        if expired:
            return print(f"見張りを終える: 最後のコメント（なければ見張り始め）から {hours:g} 時間、新しいコメントがない" + ("（知らせのコメントに返信して解決した）" if closed else ""))
        if time.time() + POLL > end:
            return print("まだ新しいコメントはない。同じ watch をもう一度呼ぶ（--start は付けない）")
        time.sleep(POLL)


def opt(a, name):
    """a から name とその値を外して、値を返す。なければ None。値がなければ usage で止める。"""
    if name not in a:
        return None
    i = a.index(name)
    if i + 1 == len(a):
        sys.exit(__doc__)
    v = a.pop(i + 1)
    del a[i]
    return v


def watch_hours(given):
    """見張る時間（正の数）。--hours の値（文字から読む）か、factory.toml の [feedback.google_comments] watch_hours（factory-doctor と同じく、数の型だけ受ける。
    true や "48" は受けない）。0 か、ないか、数でなければ止める。"""
    if given is None:
        h = gapi.factory().get("feedback", {}).get("google_comments", {}).get("watch_hours", 0)
        hours = float(h) if type(h) in (int, float) else -1.0  # bool は int の子なので type で見る
    else:
        h = given
        try:
            hours = float(given)
        except ValueError:
            hours = -1.0
    if not (math.isfinite(hours) and hours > 0):
        sys.exit(f"見張る時間が {h!r}。正の時間の数を --hours <時間> で渡すか、factory.toml の [feedback.google_comments] watch_hours に書く（0 か、なければ見張らない）")
    return hours


def watch_prompt(urls, hours, folder):
    """PROMPT の差し込み先を埋めた依頼文。呼ぶ側に置き換えさせると、差し込み先の名前が変わったときに埋まらないまま子に渡るので、ここで埋めて、埋め残しがあれば止める。
    1 行目は埋め残しを見つけた子が止まる決まりなので、差し込み先として見ない。"""
    if not urls:
        sys.exit(__doc__)
    folder = Path(folder or ".").resolve()
    if not folder.is_dir():
        sys.exit(f"資料のフォルダがない: {folder}")
    os.chdir(folder)  # factory.toml は、子が watch を回す資料のフォルダから上へたどる
    gapi.factory_path()
    watch_hours(hours)  # 見張る時間が決まらなければ、子を起こす前に止める
    head, body = PROMPT.read_text().split("\n", 1)
    for k, v in {"<material folder>": shlex.quote(str(folder)), "<path to comments.py>": shlex.quote(str(Path(__file__).resolve())),
                 "<arguments>": shlex.join([*urls, *(["--hours", hours] if hours else [])])}.items():
        body = body.replace(k, v)
    if left := re.findall(r"<[^<>\n]+>", body):
        sys.exit(f"依頼文の差し込み先が埋まっていない: {'、'.join(dict.fromkeys(left))}（{PROMPT}）")
    print(f"{head}\n{body}", end="")


def main():
    a = sys.argv[1:]
    if a[:1] == ["watch-prompt"]:
        hours, folder = opt(a, "--hours"), opt(a, "--folder")
        return watch_prompt(a[1:], hours, folder)
    if a[:1] == ["reply"] and len(a) in (4, 5) and a[4:] in ([], ["--resolve"]):
        reply(file_id(a[1]), a[2], a[3], a[4:] == ["--resolve"])
        return print(f"{a[2]} に返信" + ("して解決した" if a[4:] else "した"))
    src = Path(opt(a, "--src") or "build")
    if a[:1] == ["watch"]:
        hours = watch_hours(opt(a, "--hours"))
        urls = [x for x in a[1:] if x != "--start"]
        if not urls:
            sys.exit(__doc__)
        return watch(urls, src, hours, "--start" in a)
    only_new = "--new" in a
    urls = [x for x in a if x != "--new"]
    if not urls or urls[0] == "reply":
        sys.exit(__doc__)
    if not scan(urls, src, only_new)[0]:
        print("新しいコメントはない" if only_new else "未解決のコメントはない", file=sys.stderr)


def selftest():
    import contextlib, io, tempfile
    assert bare('"text": "**売上**は<br>前年の 2 倍\\nです"') == "text:売上は前年の2倍です"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "factory.toml").write_text("")
        b = root / "build"
        b.mkdir()
        (b / "p05.json").write_text('{\n  "title": "売上は **前年の 2 倍**",\n  "body": "ほか"\n}\n')
        (b / "doc.md").write_text("# 要旨\n\n売上は前年の 2 倍になった。\n")
        (b / "deck.json").write_text('{"apiVersion": "slides/v1", "kind": "deck", "name": "x", "pages": ["p01.json", "p05.json"]}')
        assert where("売上は前年の 2 倍", b) == ["doc.md:3", "p05.json:2"]
        assert where("ない文", b) == [] and where("x", b) == [] and where("売上", root / "no") == []
        T = lambda h: f"2026-10-19T{h:02d}:00:00.000Z"
        cs = [{"id": "A", "content": "出典は？\n要確認", "author": {"displayName": "相手"}, "createdTime": T(1), "modifiedTime": T(1),
               "quotedFileContent": {"value": "売上は前年の 2 倍"}, "anchor": '{"type":"shape","subtype":"text","page":"s1","targets":["s1_9"]}', "replies": [{"id": "r1", "content": "直します", "author": {"me": True}, "modifiedTime": T(1)},
                                                                       {"id": "r2", "content": "", "author": {}, "modifiedTime": T(1)}]},
              {"id": "B", "content": "済み", "author": {}, "createdTime": T(2), "modifiedTime": T(2), "resolved": True},
              {"id": "C", "content": "図を大きく", "author": {"displayName": "相手"}, "createdTime": T(3), "modifiedTime": T(3),
               "anchor": '{"type":"page","uid":1,"pages":["s2"]}'},  # 画面でページに付けたコメントの形（2026-10-19）
              {"id": "D", "content": "色", "author": {}, "createdTime": T(3), "modifiedTime": T(3), "anchor": '{"type":"page","pages":["gone"]}'},
              {"id": "E", "content": "語", "author": {}, "createdTime": T(2), "modifiedTime": T(2), "anchor": "kix.abc"}]
        pages, asked = [{"comments": cs[:2], "nextPageToken": "t+1"}, {"comments": cs[2:]}], []
        notes, fail = {}, set()  # 知らせのコメントを 1 件取ったときの答え（なければ未解決で残っている）と、書くと 500 になる資料

        def fake(m, url, body=None, **k):
            asked.append((m, url, body))
            if m == "GET" and (one := re.search(r"/comments/(\w+)\?fields=resolved", url)):
                if isinstance(v := notes.get(one[1], {}), Exception):
                    raise v
                return v
            if m == "POST":
                if any(f"/files/{f}/" in url for f in fail):
                    raise gapi.ApiError(f"500 POST {url}")
                return {"id": "r9"}
            if url.startswith(SLIDES):
                return {"slides": [{"objectId": "s1"}, {"objectId": "s2"}]}
            return pages.pop(0) if pages else {"comments": []}

        def call(*argv):
            out, err = io.StringIO(), io.StringIO()
            sys.argv = ["comments.py", *argv]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                main()
            return out.getvalue(), err.getvalue()

        real = gapi.request, gapi.factory_path, sys.argv, gapi.factory, time.sleep, time.time
        conf, clock = {"feedback": {"google_comments": {"watch_hours": 48}}}, [time.time()]  # sleep で進む時計
        gapi.request, gapi.factory_path, gapi.factory = fake, lambda: root / "factory.toml", lambda: conf
        time.sleep, time.time = lambda s: clock.__setitem__(0, clock[0] + s), lambda: clock[0]
        saved = lambda: json.loads((root / ".factory" / "comments.json").read_text())
        try:
            s, _ = call("--src", str(b), "https://docs.google.com/presentation/d/X1/edit")
            assert "未解決 4 件、うち新しい 4 件" in s and "[新] A 相手" in s and "p.1（p01.json）の「売上は前年の 2 倍」に: 出典は？ / 要確認" in s and "→ doc.md:3、p05.json:2" in s, s
            assert "    返信 自分: 直します" in s and " B " not in s and "[新] C 相手（10-19 " in s and "）p.2（p05.json） に: 図を大きく" in s, s
            assert "消えたページ（組み直して作り直した） に: 色" in s and "（付いた先が分からない。画面で見る）: 語" in s, s
            assert "pageToken=t%2B1" in asked[1][1] and "startModifiedTime" not in asked[0][1]  # 初めては全部を頼む
            assert sum(u.startswith(SLIDES) for _, u, _ in asked) == 1  # スライドの並びは 1 回だけ取る
            assert saved() == {"seen": {"X1": T(3)}, "sent": [], "watch": {}, "notice": {}}  # 解決済みも含めた最後の時刻
            cs[0]["replies"].append({"id": "r3", "content": "やはり図に", "author": {}, "modifiedTime": T(4)})  # A に返信があった
            cs[0]["modifiedTime"] = T(4)
            pages[:], asked[:] = [{"comments": [cs[0], cs[2]]}], []  # C は境目なので Drive からまた返る
            s, _ = call("--new", "--src", str(b), "X1")
            assert "startModifiedTime=2026-10-19T03%3A00%3A00.000Z" in asked[0][1] and "新しい未解決 1 件" in s and "[新] A" in s and " C " not in s, s
            assert sum(u.startswith(SLIDES) for _, u, _ in asked) == 1  # 回ごとに 1 回だけ取る
            asked[:] = []
            s, _ = call("reply", "X1", "C", "p05 の図を大きくしました", "--resolve")
            assert asked == [("POST", f"{DRIVE}/files/X1/comments/C/replies?fields=id", {"content": "p05 の図を大きくしました", "action": "resolve"})] and s == "C に返信して解決した\n"
            call("reply", "X1", "A", "出典を足しました")
            assert asked[-1][2] == {"content": "出典を足しました"} and saved()["sent"] == ["r9", "r9"]
            cs[0]["replies"].append({"id": "r9", "content": "出典を足しました", "author": {"me": True}, "modifiedTime": T(5)})  # 送った返信だけでは新しくない
            cs[0]["modifiedTime"] = T(5)
            pages[:], asked[:] = [{"comments": [cs[0]]}], []
            s, err = call("--new", "X1")
            assert s == "" and "新しいコメントはない" in err  # 見張りの回は、出力がなければ終える
            try:
                call("reply", "X1", "A")
                raise AssertionError("文のない reply を通した")
            except SystemExit as e:
                assert "usage" in str(e)
            # watch: 新しいコメントがなければ、WAIT 秒で「まだ」と返る。起点は初めて見張った時刻
            t0, asked[:] = clock[0], []
            s, _ = call("watch", "X1")
            assert s.startswith("まだ新しいコメントはない") and saved()["watch"]["X1"] == stamp(t0), s
            assert sum(m == "GET" and "/comments?" in u for m, u, _ in asked) == 4 and clock[0] - t0 == WAIT  # 0・90・180・270 秒に見て、270 秒で返る
            m, u, body = asked[0]  # 見張り始めに、資料へ知らせのコメントを書く（終える時刻は起点の 48 時間あと）
            assert (m, u) == ("POST", f"{DRIVE}/files/X1/comments?fields=id") and body["content"] == NOTICE.format(when(stamp(t0 + 48 * 3600))), asked[0]
            assert saved()["notice"] == {"X1": {"id": "r9", "until": stamp(t0 + 48 * 3600)}}
            pages[:], asked[:] = [{"comments": [{"id": "r9", "content": "AI が", "author": {"me": True}, "createdTime": T(23), "modifiedTime": T(23)}]}], []
            s, _ = call("watch", "X1")
            assert s.startswith("まだ") and not any(m == "POST" for m, _, _ in asked), (s, asked)  # 知らせは新しいコメントと数えず、終える時刻も変わらない
            with state() as st:
                st["watch"]["X1"] = "2026-01-01T00:00:00.000Z"  # 最後のコメントから 48 時間を過ぎた
            asked[:] = []
            s, _ = call("watch", "X1")
            assert s.startswith("見張りを終える: 最後のコメント（なければ見張り始め）から 48 時間") and s.rstrip().endswith("（知らせのコメントに返信して解決した）") and "X1" not in saved()["watch"], s
            assert [b for m, _, b in asked if m == "POST"][-1] == {"content": "コメントの見張りを終えます（48 時間、新しいコメントがありませんでした）。このあとのコメントは、自動では直しません。",
                                                                    "action": "resolve"} and saved()["notice"] == {}  # 知らせに返信して解決する
            with state() as st:
                st["watch"]["X1"] = "2026-01-01T00:00:00.000Z"
            s, _ = call("watch", "--start", "--hours", "1", "X1")  # --start なら起点を今にする
            assert s.startswith("まだ") and saved()["watch"]["X1"] > "2026-01-01T00:00:00.000Z" and "X1" in saved()["notice"], s
            asked[:] = []
            s, _ = call("watch", "--start", "--hours", "1", "X1")  # 直したあとに --start で呼び直すと、終える時刻が延びる
            until = saved()["notice"]["X1"]["until"]
            posts = [a for a in asked if a[0] == "POST"]
            assert posts == [("POST", f"{DRIVE}/files/X1/comments/r9/replies?fields=id", {"content": f"見張りを終える時刻を {when(until)} に延ばします"})], posts
            pages[:] = [{}, {"comments": [{"id": "r9", "content": "AI が", "author": {"me": True}, "createdTime": T(23), "modifiedTime": T(23)}]}]  # 版、コメントの順に取る
            assert gapi.guard("X1", "v", "k", "build", stop=False) is None and not pages  # 組むときも、知らせは未解決のコメントと数えない
            notes["r9"], asked[:] = {"resolved": True}, []  # 読む人が知らせを解決した
            call("watch", "--start", "--hours", "1", "X1")
            assert [u for m, u, _ in asked if m == "POST"] == [f"{DRIVE}/files/X1/comments?fields=id"], asked  # 閉じた知らせに返信せず、書き直す
            notes["r9"] = gapi.ApiError("404 GET x")  # 読む人が知らせを消した
            with state() as st:
                st["watch"]["X1"] = "2026-01-01T00:00:00.000Z"
            asked[:] = []
            s, _ = call("watch", "--hours", "1", "X1")
            assert s.startswith("見張りを終える") and "知らせ" not in s and not any("/replies" in u for _, u, _ in asked) and saved()["notice"] == {}, (s, asked)  # 消えた知らせで止まらない
            notes.clear()
            fail.add("X2")
            try:
                call("watch", "--start", "--hours", "1", "X1", "X2")
                raise AssertionError("X2 に書けないのに通した")
            except gapi.ApiError:
                pass
            assert list(saved()["notice"]) == ["X1"]  # 1 つ目の資料に書いた知らせは残す
            fail.clear()
            asked[:] = []
            call("watch", "--hours", "1", "X1", "X2")
            assert [u for m, u, _ in asked if m == "POST"] == [f"{DRIVE}/files/X2/comments?fields=id"], asked  # X1 にもう 1 件書かない
            with state() as st:  # 終える時刻を過ぎた。X1 の知らせは閉じられ、X2 の知らせへの返信が 500 になる
                st["watch"].update(X1="2026-01-01T00:00:00.000Z", X2="2026-01-01T00:00:00.000Z")
            fail.add("X2")
            try:
                call("watch", "--hours", "1", "X1", "X2")
                raise AssertionError("X2 に返せないのに通した")
            except gapi.ApiError:
                pass
            assert list(saved()["notice"]) == ["X2"] and {"X1", "X2"} <= saved()["watch"].keys()  # X1 は閉じた。起点は残す
            fail.clear()
            asked[:] = []
            s, _ = call("watch", "--hours", "1", "X1", "X2")  # 呼び直すと、X1 にまた知らせを書かず、X2 を閉じて終える
            assert [u for m, u, _ in asked if m == "POST"] == [f"{DRIVE}/files/X2/comments/r9/replies?fields=id"] and s.startswith("見張りを終える"), (s, asked)
            assert saved()["notice"] == {} and not {"X1", "X2"} & saved()["watch"].keys()
            cs.append({"id": "F", "content": "表を足して", "author": {"displayName": "相手"}, "createdTime": T(23), "modifiedTime": T(23)})
            pages[:] = [{"comments": [cs[-1]]}]
            s, _ = call("watch", "X1")
            assert "新しい未解決 1 件" in s and "[新] F 相手" in s and saved()["watch"]["X1"] >= T(23), s  # 起点は最後のコメントに進む
            cs[-1]["replies"] = [{"id": "r8", "content": "", "author": {}, "modifiedTime": "2026-10-19T23:30:00.000Z", "deleted": True}]
            cs[-1]["modifiedTime"] = cs[-1]["replies"][0]["modifiedTime"]
            pages[:] = [{"comments": [cs[-1]]}]
            s, _ = call("watch", "--hours", "1", "X1")
            assert s.startswith("まだ"), s  # 消した返信だけなら、新しくない
            cs[-1]["modifiedTime"] = "2026-10-19T23:45:00.000Z"  # 書いた人が本文を直した（どの返信より新しい）
            pages[:] = [{"comments": [cs[-1]]}]
            s, _ = call("watch", "--hours", "1", "X1")
            assert "[新] F 相手" in s, s
            for argv, why in ((["watch", "X1"], "0"), (["watch", "--hours", "48h", "X1"], "'48h'"), (["watch", "--hours", "-1", "X1"], "'-1'"),
                              (["watch", "--hours", "inf", "X1"], "'inf'"), (["watch", "X1", "--hours"], "usage"), (["--src"], "usage")):
                conf["feedback"]["google_comments"]["watch_hours"] = 0
                try:
                    call(*argv)
                    raise AssertionError(f"{argv} を通した")
                except SystemExit as e:
                    assert why in str(e) and ("watch_hours" in str(e) or why == "usage"), (argv, e)
            for v in (True, "48", float("nan")):  # factory.toml は doctor と同じく数の型だけ（true も文字も受けない）
                conf["feedback"]["google_comments"]["watch_hours"] = v
                try:
                    watch_hours(None)
                    raise AssertionError(f"{v!r} を通した")
                except SystemExit as e:
                    assert "watch_hours" in str(e)
            conf["feedback"]["google_comments"]["watch_hours"] = 1.5
            assert watch_hours(None) == 1.5 and watch_hours("2") == 2
            # watch-prompt: 依頼文を埋めて出す。埋め残しの差し込み先と、URL がないときは止める
            cwd, me = os.getcwd(), Path(__file__).resolve()
            try:
                s, _ = call("watch-prompt", "--folder", str(root), "--hours", "2", "https://docs.google.com/presentation/d/X1/edit#slide=id.p", "X2")
                assert Path.cwd() == root.resolve()  # factory.toml は資料のフォルダから上へたどる
            finally:
                os.chdir(cwd)
            head, body = s.split("\n", 1)
            assert head == PROMPT.read_text().split("\n", 1)[0] and not re.findall(r"<[^<>\n]+>", body), s
            assert f"cd {shlex.quote(str(root.resolve()))} && python3 {shlex.quote(str(me))} watch --start 'https://docs.google.com/presentation/d/X1/edit#slide=id.p' X2 --hours 2\n" in body, s
            real_prompt = PROMPT
            globals()["PROMPT"] = root / "prompt.md"
            PROMPT.write_text("1 行目の <名前> は見ない\nIn <資料のフォルダ>, run <path to comments.py>.\n")  # 名前の変わった差し込み先
            try:
                for argv, why in ((["watch-prompt", "X1"], "依頼文の差し込み先が埋まっていない: <資料のフォルダ>（"), (["watch-prompt", "--hours", "1"], "usage")):
                    try:
                        call(*argv)
                        raise AssertionError(f"{argv} を通した")
                    except SystemExit as e:
                        assert why in str(e) and "<名前>" not in str(e), (argv, e)
            finally:
                globals()["PROMPT"] = real_prompt
                os.chdir(cwd)
            before = (root / ".factory" / "comments.json").read_text()
            try:
                with state() as st:
                    st["sent"].append("x")
                    raise gapi.ApiError("途中で止まった")
            except gapi.ApiError:
                pass
            assert (root / ".factory" / "comments.json").read_text() == before and not (root / ".factory" / "comments.tmp").exists()  # 止まったら書かない
        finally:
            gapi.request, gapi.factory_path, sys.argv, gapi.factory, time.sleep, time.time = real
    print("selftest ok")

if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        run(main)
