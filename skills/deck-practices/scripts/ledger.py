#!/usr/bin/env python3
"""決まりの台帳。修正の指示（指摘）と、決まりの変更の提案・適用・却下を、ワークスペースの .factory/ledger.jsonl に 1 件 1 行で足していく。
決まりの本文には ID（visual-<番号>・ws-visual-<番号> を角括弧で囲む）と短い理由だけを書き、日付・原文・どの資料か・ユーザーが決めたかは、ここに ID でつなぐ。
決まりの層と戻し方は ../rules.md。ワークスペース（今いるフォルダから上へ、最初の factory.toml のフォルダ）で回す。標準ライブラリだけ。
usage:
  ledger.py add --deck <資料のフォルダ> --quote <ユーザーの言葉> [--fix <直した箇所>] [--to <決まりの ID・ファイル・未・戻さない>] [--check lint|レビュー|なし] [--session <会話 ID>] [--decided] [--once]
                                                   --once は前の形の構成案から取り込むときだけ（同じ資料・言葉・会話がもうあれば足さない）
  ledger.py route <c-ID> <戻し先>                 指摘の戻し先を決める・変える
  ledger.py list [--deck <フォルダ>] [--open] [--to <戻し先>]   指摘の一覧（--open は戻し先が「未」のものだけ）
  ledger.py why <決まりの ID>                      その決まりの出典（指摘・日付・原文）と、資料・顧客の数、ユーザーが決めたか
  ledger.py next <接頭辞>                          次の決まりの ID（ワークスペースの決まりは ws-visual のように ws- を付ける）
  ledger.py propose --file <ワークスペースのファイル> --new <新しい文> [--old <今の文>] [--rule <ID>] --why <要点> [--src c-1,c-2] [--kind <種類>]
  ledger.py pending [--status 却下|適用済み|戻した|all]   提案と差分（既定は未適用。却下は理由も）
  ledger.py apply <P-ID ...|all>                   提案を当てる（今の文がそのまま 1 か所にあるときだけ）
  ledger.py reject <P-ID> --reason <理由>           ユーザーが却下した（dreaming は同じ趣旨の提案をもう出さない）
  ledger.py withdraw <P-ID> --reason <理由>         出した側が取り下げる（書き間違いの出し直しなど。却下には数えない）
  ledger.py undo <P-ID>                            当てた提案を逆向きに当てて戻す
  ledger.py drift                                  当てたあとに手で直された・消えた決まり（ユーザーが直したものとして扱う）
  ledger.py --selftest
台帳の原文には顧客のことが入る。.factory/ から外（PR・チャット）に写さない。"""
import argparse, difflib, json, re, sys, tempfile, time
from pathlib import Path

try:
    import fcntl
except ImportError:  # ponytail: Windows では鍵をかけない。同時に書く会話があれば番号が重なりうる
    fcntl = None

PLUGIN = Path(__file__).resolve().parents[2]  # プラグインの skills/
RULE_ID = re.compile(r"\[((?:ws-)?[a-z][\w-]*?-\d{3})\]")


def workspace():
    d = Path.cwd().resolve()
    return next((x for x in (d, *d.parents) if (x / "factory.toml").is_file()), None) or sys.exit("factory.toml が見つからない。ワークスペースで回す")


def path(ws):
    return ws / ".factory" / "ledger.jsonl"


def records(ws):
    p = path(ws)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def write(ws, rec, number=None):
    """1 行足す。number=("correction", "c-", 4) なら、鍵をかけたまま次の番号を rec["id"] にする（同時に書く会話で番号が重ならないように）。"""
    p = path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **rec}
    with p.open("a", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        if number:
            kind, head, width = number
            rec = {**rec, "id": f"{head}{sum(r['kind'] == kind for r in records(ws)) + 1:0{width}d}"}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def state(ws):
    """台帳を読み直して、いまの指摘（戻し先は最後の route）と提案（状態は最後の出来事）にする。"""
    cs, ps = {}, {}
    for n, r in enumerate(records(ws)):
        k = r["kind"]
        if k == "correction":
            cs[r["id"]] = dict(r)
        elif k == "route" and r["ref"] in cs:
            cs[r["ref"]]["to"] = r["to"]
        elif k == "proposal":
            ps[r["id"]] = {**r, "status": "未適用"}
        elif k in ("applied", "rejected", "withdrawn", "undone") and r["ref"] in ps:
            ps[r["ref"]].update(status={"applied": "適用済み", "rejected": "却下", "withdrawn": "取り下げ", "undone": "戻した"}[k], seq=n,
                                **{x: r[x] for x in ("appended", "reason", "prev") if x in r})
    return cs, ps


def rel(ws, p):
    p = (Path.cwd() / Path(p).expanduser()).resolve()  # 絶対パスなら cwd は効かない
    return str(p.relative_to(ws)) if p.is_relative_to(ws) else str(p)


def add(ws, a):
    deck = rel(ws, a.deck)
    same = a.once and next((c for c in state(ws)[0].values() if (c["deck"], c["quote"], c["session"]) == (deck, a.quote, a.session or "")), None)
    if same:  # 前の形の構成案の同じ行を、次の回でまた取り込んだとき。足し直さず、前の ID を返す（会話をまたぐくり返しは --once なしで足す）
        print(same["id"])
        return
    rec = write(ws, {"kind": "correction", "deck": deck, "quote": a.quote, "fix": a.fix or "",
                     "to": a.to, "check": a.check, "session": a.session or "", "decided": a.decided}, ("correction", "c-", 4))
    print(rec["id"])


def show(c):
    d = " ユーザーが決めた" if c.get("decided") else ""
    return f"{c['id']} {c.get('date') or c['ts'][:10]} {c['deck'] or c.get('where') or '-'}「{c['quote'] or c.get('note', '')}」→ {c.get('fix') or '-'} [戻し先: {c['to']}][確かめ: {c.get('check', 'なし')}]{d}"


def why(ws, rid):
    cs = [c for c in state(ws)[0].values() if c["to"] == rid]
    for c in cs:
        print(show(c))
    decks = {c["deck"] for c in cs if c["deck"]}
    custs = {c["deck"].split("/")[1] for c in cs if c["deck"].startswith("Customers/")}
    print(f"== {rid}: 指摘 {len(cs)} 件・資料 {len(decks)} 本・顧客 {len(custs)} 社・ユーザーが決めた: {'あり' if any(c.get('decided') for c in cs) else 'なし'}")
    return cs


def next_id(ws, prefix):
    roots = [PLUGIN, ws / "rules", ws / "AGENTS.md", ws / "Customers"]
    files = [f for r in roots if r.exists() for f in ([r] if r.is_file() else r.rglob("*"))
             if f.suffix in (".md", ".py") and f.is_file() and f.resolve() != Path(__file__).resolve()]  # このファイルの selftest の ID は数えない
    used = [int(m.group(1)[len(prefix) + 1:]) for f in files for m in RULE_ID.finditer(f.read_text(encoding="utf-8", errors="ignore"))
            if m.group(1).rsplit("-", 1)[0] == prefix]
    used += [int(r["rule"].rsplit("-", 1)[1]) for r in records(ws) if r.get("rule", "").rsplit("-", 1)[0] == prefix]  # 提案だけで、まだ当てていない ID も使ったものにする
    return f"{prefix}-{max(used, default=0) + 1:03d}"


def target(ws, f):
    p = (ws / f).resolve()
    if not p.is_relative_to(ws) or p.is_relative_to(PLUGIN):
        sys.exit(f"変更先はワークスペースの中のファイルだけ（プラグインは factory-kaizen で PR にする）: {f}")
    return p


def propose(ws, a):
    target(ws, a.file)
    rec = write(ws, {"kind": "proposal", "file": a.file, "old": a.old or "", "new": a.new, "rule": a.rule or "",
                     "why": a.why, "src": [x for x in (a.src or "").split(",") if x], "type": a.kind or ""}, ("proposal", "P", 4))
    print(rec["id"])


def diff(p):
    return "".join(difflib.unified_diff((p["old"] + "\n").splitlines(True) if p["old"] else [], (p["new"] + "\n").splitlines(True), p["file"], p["file"]))


def pending(ws, status="未適用"):
    out = [p for p in state(ws)[1].values() if status in ("all", p["status"])]
    for p in out:
        why = f"、理由: {p['reason']}" if p.get("reason") else ""
        print(f"### {p['id']} {p['why']}（{p['status']}、{p['type'] or '-'}、{p['file']}{'、' + p['rule'] if p['rule'] else ''}、出典 {','.join(p['src']) or '-'}{why}）\n{diff(p)}")
    return out


def apply(ws, ids):
    ps = state(ws)[1]
    ids = [i for i, p in ps.items() if p["status"] == "未適用"] if ids == ["all"] else ids
    for i in ids:
        p = ps.get(i) or sys.exit(f"提案がない: {i}")
        if p["status"] != "未適用":
            sys.exit(f"{i} は {p['status']}")
        f = target(ws, p["file"])
        text = f.read_text(encoding="utf-8") if f.exists() else ""
        if p["old"]:
            if text.count(p["old"]) != 1:
                sys.exit(f"{i}: 今の文が {p['file']} に {text.count(p['old'])} か所ある（1 か所のときだけ当てる）。提案のあとで変わったので、合わせた文を見せて聞く")
            text = text.replace(p["old"], p["new"])
        else:
            text = text + ("" if not text or text.endswith("\n") else "\n") + p["new"] + "\n"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        cs = state(ws)[0]
        write(ws, {"kind": "applied", "ref": i, "appended": not p["old"], "prev": {c: cs[c]["to"] for c in p["src"] if c in cs}})
        for c in p["src"]:
            write(ws, {"kind": "route", "ref": c, "to": p["rule"] or p["file"]})
        print(f"{i}: {p['file']} に当てた")


def undo(ws, i):
    p = state(ws)[1].get(i) or sys.exit(f"提案がない: {i}")
    if p["status"] != "適用済み" or not p["new"]:
        sys.exit(f"{i} は戻せない（{p['status']}。消す提案は、前後の行も old と new に入れて出す）")
    f = target(ws, p["file"])
    text = f.read_text(encoding="utf-8")
    new = p["new"] + "\n" if p.get("appended") else p["new"]
    if text.count(new) != 1:
        sys.exit(f"{i}: 当てた文が {p['file']} に {text.count(new)} か所ある。手で直されたので、snapshot.sh restore か手で戻す")
    f.write_text(text.replace(new, p["old"], 1), encoding="utf-8")
    write(ws, {"kind": "undone", "ref": i})
    cs = state(ws)[0]
    for c, to in p.get("prev", {}).items():
        if cs.get(c, {}).get("to") == (p["rule"] or p["file"]):
            write(ws, {"kind": "route", "ref": c, "to": to})
    print(f"{i}: 戻した")


def effective(p, done):
    """p の文に、あとで同じファイルに当てた置き換えを順に当てた、いまあるはずの文。あとの提案がまるごと含んだなら None（そちらで見る）。"""
    text = p["new"]
    for q in sorted((q for q in done if q["file"] == p["file"] and q["seq"] > p["seq"] and q["old"]), key=lambda q: q["seq"]):
        if text in q["old"]:
            return None
        text = text.replace(q["old"], q["new"])
    return text


def drift(ws):
    out, done = [], [p for p in state(ws)[1].values() if p["status"] == "適用済み"]
    for p in done:
        f, want = ws / p["file"], effective(p, done)
        if want and (not f.exists() or want not in f.read_text(encoding="utf-8")):
            out.append(p["id"])
            print(f"{p['id']} {p['file']}{' ' + p['rule'] if p['rule'] else ''}: 当てた文がない（手で直されたか消えた。ユーザーが直したものとして扱い、覆さない）")
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--deck", required=True); s.add_argument("--quote", required=True); s.add_argument("--fix")
    s.add_argument("--to", default="未"); s.add_argument("--check", default="なし"); s.add_argument("--session"); s.add_argument("--decided", action="store_true"); s.add_argument("--once", action="store_true")
    s = sub.add_parser("route"); s.add_argument("id"); s.add_argument("to")
    s = sub.add_parser("list"); s.add_argument("--deck"); s.add_argument("--open", action="store_true"); s.add_argument("--to")
    s = sub.add_parser("why"); s.add_argument("id")
    s = sub.add_parser("next"); s.add_argument("prefix")
    s = sub.add_parser("propose")
    s.add_argument("--file", required=True); s.add_argument("--new", required=True); s.add_argument("--old"); s.add_argument("--rule")
    s.add_argument("--why", required=True); s.add_argument("--src"); s.add_argument("--kind")
    s = sub.add_parser("pending"); s.add_argument("--status", default="未適用")
    s = sub.add_parser("apply"); s.add_argument("ids", nargs="+")
    s = sub.add_parser("reject"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("withdraw"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("undo"); s.add_argument("id")
    sub.add_parser("drift")
    a = ap.parse_args(argv)
    ws = workspace()
    if a.cmd == "add":
        add(ws, a)
    elif a.cmd == "route":
        state(ws)[0].get(a.id) or sys.exit(f"指摘がない: {a.id}")
        write(ws, {"kind": "route", "ref": a.id, "to": a.to})
    elif a.cmd == "list":
        deck = rel(ws, a.deck) if a.deck else None
        for c in state(ws)[0].values():
            if (not deck or c["deck"] == deck) and (not a.open or c["to"] == "未") and (not a.to or c["to"] == a.to):
                print(show(c))
    elif a.cmd == "why":
        why(ws, a.id)
    elif a.cmd == "next":
        print(next_id(ws, a.prefix))
    elif a.cmd == "propose":
        propose(ws, a)
    elif a.cmd == "pending":
        pending(ws, a.status)
    elif a.cmd == "apply":
        apply(ws, a.ids)
    elif a.cmd in ("reject", "withdraw"):
        p = state(ws)[1].get(a.id) or sys.exit(f"提案がない: {a.id}")
        p["status"] == "未適用" or sys.exit(f"{a.id} は {p['status']}")
        write(ws, {"kind": {"reject": "rejected", "withdraw": "withdrawn"}[a.cmd], "ref": a.id, "reason": a.reason})
    elif a.cmd == "undo":
        undo(ws, a.id)
    elif a.cmd == "drift":
        drift(ws)


def selftest():
    import contextlib, io, os
    quiet = lambda *a: contextlib.redirect_stdout(io.StringIO())
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d).resolve()
        (ws / "factory.toml").write_text("")
        (ws / "Customers" / "acme" / "deck_202610").mkdir(parents=True)
        (ws / "rules" / "deck-practices").mkdir(parents=True)
        (ws / "rules" / "deck-practices" / "visual.md").write_text("`deck-practices/visual.md` に足す。\n\n- [ws-visual-001] 本文は 16pt。\n")
        cwd = os.getcwd()
        os.chdir(ws / "Customers" / "acme" / "deck_202610")
        try:
            with quiet():
                main(["add", "--deck", ".", "--quote", "表は 2 枚に分けて", "--fix", "p4"])
                main(["add", "--deck", ".", "--quote", "このページの数字を直して", "--to", "戻さない"])
            from concurrent.futures import ThreadPoolExecutor  # 同時に足しても番号が重ならない
            with ThreadPoolExecutor(8) as ex:
                ids = list(ex.map(lambda i: write(ws, {"kind": "note"}, ("note", "n-", 2))["id"], range(16)))
            assert len(set(ids)) == 16
            cs = state(ws)[0]
            assert cs["c-0001"]["deck"] == "Customers/acme/deck_202610" and cs["c-0001"]["to"] == "未"
            assert next_id(ws, "ws-visual") == "ws-visual-002" and next_id(ws, "nothing") == "nothing-001"
            assert next_id(ws, "visual") != "visual-001"  # プラグインの ID も数える
            # 足す提案を当て、出典の指摘を決まりにつなぐ
            with quiet():
                main(["propose", "--file", "rules/deck-practices/visual.md", "--new", "- [ws-visual-002] 収まらない表は 2 枚に分ける。", "--rule", "ws-visual-002", "--why", "表の分け方", "--src", "c-0001"])
            assert next_id(ws, "ws-visual") == "ws-visual-003"  # 提案だけの ID も使ったもの
            with quiet():
                assert len(pending(ws)) == 1
                main(["apply", "all"])
            v = ws / "rules" / "deck-practices" / "visual.md"
            assert "[ws-visual-002]" in v.read_text() and state(ws)[0]["c-0001"]["to"] == "ws-visual-002"
            with quiet():
                assert len(why(ws, "ws-visual-002")) == 1 and drift(ws) == []
            # 置き換える提案。今の文が変わっていたら当てない
            with quiet():
                main(["propose", "--file", "rules/deck-practices/visual.md", "--old", "本文は 16pt。", "--new", "本文は 18pt。", "--why", "大きさ"])
                main(["propose", "--file", "rules/deck-practices/visual.md", "--old", "ない文", "--new", "x", "--why", "合わない"])
                main(["apply", "P0002"])
            assert "18pt" in v.read_text()
            try:
                with quiet():
                    main(["apply", "P0003"])
                raise AssertionError("合わない提案を当てた")
            except SystemExit as e:
                assert "0 か所" in str(e)
            with quiet():
                main(["reject", "P0003", "--reason", "いらない"])
                main(["propose", "--file", "rules/deck-practices/visual.md", "--new", "x", "--why", "書き間違い"])
                main(["withdraw", "P0004", "--reason", "出し直す"])
                main(["undo", "P0002"])
            assert "16pt" in v.read_text() and state(ws)[1]["P0003"]["status"] == "却下"
            with quiet():
                assert [p["id"] for p in pending(ws, "却下")] == ["P0003"] and [p["id"] for p in pending(ws, "取り下げ")] == ["P0004"]
            # 手で直されたら drift に出る
            v.write_text(v.read_text().replace("2 枚に分ける", "分ける"))
            with quiet():
                assert drift(ws) == ["P0001"]
            # 足した文をあとの提案で置き換えても、手の直しに数えない。置き換えたほうを手で直せば出る
            with quiet():
                main(["propose", "--file", "rules/x.md", "--new", "A です", "--why", "足す"])
                main(["propose", "--file", "rules/x.md", "--old", "A です", "--new", "B です", "--why", "替える"])
                main(["apply", "P0005", "P0006"])
                assert drift(ws) == ["P0001"]
            x = ws / "rules" / "x.md"
            x.write_text("C です\n")
            with quiet():
                assert drift(ws) == ["P0001", "P0006"]  # A をまるごと置き換えた P0006 で見る
            x.write_text("B です\n")
            # 一部だけを置き換えたあと、残りの部分を手で直しても出る
            with quiet():
                main(["propose", "--file", "rules/z.md", "--new", "16pt にする。出典はリンクする。", "--why", "足す"])
                main(["apply", "P0007"])
                main(["propose", "--file", "rules/z.md", "--old", "16pt", "--new", "18pt", "--why", "大きく"])
                main(["apply", "P0008"])
                assert "P0007" not in drift(ws)
            (ws / "rules" / "z.md").write_text("18pt にする。出典はリンクしない。\n")
            with quiet():
                assert "P0007" in drift(ws) and "P0008" not in drift(ws)
            # 戻すと、出典の指摘の戻し先も前に戻る
            with quiet():
                main(["add", "--deck", ".", "--quote", "見出しは短く"])
                main(["propose", "--file", "rules/y.md", "--new", "- [ws-y-001] 見出しは短く。", "--rule", "ws-y-001", "--why", "短く", "--src", "c-0003"])
                main(["apply", "P0009"])
            assert state(ws)[0]["c-0003"]["to"] == "ws-y-001"
            with quiet():
                main(["undo", "P0009"])
            assert state(ws)[0]["c-0003"]["to"] == "未" and (ws / "rules" / "y.md").read_text() == ""
            # 前の形の取り込み（--once）は足し直さない。ほかの会話のくり返しは別の 1 件にする
            with quiet():
                main(["add", "--deck", ".", "--quote", "古い行", "--once"])
                main(["add", "--deck", ".", "--quote", "古い行", "--once"])
                main(["add", "--deck", ".", "--quote", "見出しは短く", "--session", "s2", "--decided"])
            cs = state(ws)[0].values()
            assert sum(c["quote"] == "古い行" for c in cs) == 1 and sum(c["quote"] == "見出しは短く" for c in cs) == 2
            # プラグインのファイルは変更先にしない
            try:
                target(ws, str(PLUGIN / "skills" / "deck-practices" / "visual.md"))
                raise AssertionError("プラグインを変更先にした")
            except SystemExit:
                pass
        finally:
            os.chdir(cwd)
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
