#!/usr/bin/env python3
"""決まりの台帳。修正の指示（指摘）、決まりの変更の提案・適用・却下、判断待ち、レビューの結果を、ワークスペースの .factory/ledger.jsonl に 1 件 1 行で足していく。
決まりの本文には ID（slides-visual-<番号>・ws-slides-visual-<番号> を角括弧で囲む。接頭辞は何についての決まりか〔TOPICS〕で、置き場所が変わっても変えない）と短い理由だけを書き、日付・原文・どの資料か・ユーザーが決めたかは、ここに ID でつなぐ。
決まりの層と戻し方は ../rules.md。ワークスペース（今いるフォルダから上へ、最初の factory.toml のフォルダ）で回す。標準ライブラリだけ。
usage:
  ledger.py add --deck <資料のフォルダ> --quote <ユーザーの言葉> [--fix <直した箇所>] [--to <決まりの ID・ファイル・未・戻さない>] [--check lint|レビュー|なし] [--session <会話 ID>] [--at <言われた時刻（UTC）>] [--decided] [--plan AI|人] [--once]
                                                   --plan は構成の見逃し（方針のレビューのあとに、聞き手・問い・主張・順序を変えた指摘。値はその資料の方針のレビュー）
                                                   --at は会話の記録からあとで拾ったときの発言の時刻（再発の数に使う。既定は書いた時刻）
                                                   --once は前の形の構成案から取り込むときだけ（同じ資料・言葉・会話がもうあれば足さない）
  ledger.py route <c-ID> <戻し先>                 指摘の戻し先を決める・変える
  ledger.py plan <c-ID> AI|人|なし                 台帳にある指摘に、構成の見逃しの印をあとから付ける（なしは付け間違いを外す）
  ledger.py list [--deck <フォルダ>] [--open] [--to <戻し先>]   指摘の一覧（--open は戻し先が「未」のものだけ）
  ledger.py why <決まりの ID>                      その決まりの出典（指摘・日付・原文、再発か）と、資料・顧客の数、ユーザーが決めたか、レビューの結果
  ledger.py rules                                  決まりごとの数（指摘・再発・資料・顧客・レビューの結果）と、週ごとの取りこぼしと構成の見逃し
  ledger.py candidates                             決まりごとの次の一手（下ろす・書き直す・条件を足す・上げる・写しを消す・上書きを見直す）と、その決まりへの前の提案
  ledger.py next <接頭辞>                          次の決まりの ID（接頭辞は TOPICS の主題。ワークスペースの決まりは ws-slides-visual のように ws- を付ける）
  ledger.py where <決まりの ID>                    その決まりが書いてある場所（プラグインとワークスペースの [ID] のファイルと行）
  ledger.py topics                                 決まりの ID の主題の一覧
  ledger.py propose --file <ワークスペースのファイル> --new <新しい文> [--old <今の文>] [--rule <ID>] --why <要点> [--src c-1,c-2] [--kind <種類>] [--plugin] [--replaces ws-x-001,…] [--rec 適用|様子見|却下 [--rec-why <理由>]] [--auto]
                                                   --rec は出した側の推奨（ユーザーは「推奨どおり」と例外だけを返せる）
                                                   --auto は会話を出典にしない片付け（重なり・古い記述）で、ID の付いた決まりを丸ごと消すだけのものを、出してすぐ当てる。当ててよいかはここで見る
                                                   --plugin は変更先がプラグイン（--file は skills/ からのパス）。当てず、factory-kaizen で Issue にする
                                                   --replaces は、その Issue の直しが届いたら要らなくなるワークスペースの決まり（上書きなど。出典の指摘の決まりは書かなくてよい）
  ledger.py pending [--status 却下|適用済み|戻した|取り下げ|Issue にした|all]   提案と差分（既定は未適用。却下は理由も）
  ledger.py apply <P-ID ...|all>                   提案を当てる（今の文がそのまま 1 か所にあるときだけ。プラグインへの提案は当てない）
  ledger.py sent <P-ID> --issue <URL> [--rule <ID>]   プラグインへの提案を Issue にした（出典の指摘をその決まりにつなぐ。--rule は Issue で提案と違う ID にしたとき）
  ledger.py reject <P-ID> --reason <理由>           ユーザーが却下した（dreaming は同じ趣旨の提案をもう出さない）。Issue にしたものが断られたときも（出典の指摘は前の戻し先に戻る）
  ledger.py withdraw <P-ID か Q-ID> --reason <理由>   出した側が取り下げる（書き間違いの出し直しなど。却下には数えない）
  ledger.py undo <P-ID>                            当てた提案を逆向きに当てて戻す
  ledger.py drift                                  当てたあとに手で直された・消えた決まり（ユーザーが直したものとして扱う）
  ledger.py ask --q <ユーザーに聞くこと> [--rule <ID>] [--src c-1,c-2] [--rec <推奨の答え>]   判断待ち
  ledger.py answer <Q-ID> --a <ユーザーの言葉>      判断待ちへの答え
  ledger.py questions [--all]                      判断待ち（--all は答えたものと取り下げたものも）
  ledger.py review --deck <資料のフォルダ> --table <指摘の表のファイル>   deck-review の指摘の表から、決まりの列のある行の結果を取り込む（同じ行は 2 度数えず、ラウンドをまたぐ同じ行はあとのラウンドの結果）
  ledger.py --selftest
台帳の原文には顧客のことが入る。.factory/ から外（Issue・チャット）に写さない。"""
import argparse, difflib, hashlib, json, re, sys, tempfile, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # ponytail: Windows では鍵をかけない。同時に書く会話があれば番号が重なりうる
    fcntl = None

PLUGIN = Path(__file__).resolve().parents[2]  # プラグインの skills/
ID = r"(?:ws-)?[a-z][\w-]*?-\d{3}"  # 決まりの ID（slides-visual-012・ws-slides-visual-003）
RULE_ID = re.compile(rf"\[({ID})\]")
KEY = re.compile(rf"{ID}|lint:.+")  # レビューの表の「決まり」の列に書くもの（lint の規則は名前で lint:<名前>）
CITE = re.compile(rf"\[?({ID})\]?\s*「([^」]*)」")  # 決まりの列の ID に添えた、その決まりの文から写した語句（slides-visual-013「単語や文節の途中で折り返さない」）
RESULTS = ("直した", "残した（誤り）", "残した", "聞く")
NO_RULE = ("未", "戻さない")  # 決まりにつないでいない戻し先
TWICE = 2  # 2 本以上の資料・2 社以上の顧客に出たら、たまたまでないとみなす（dreaming の 4c・4i・5）
AUTO = ("重なり", "古い記述")  # 会話を出典にしない片付け。--auto で、出してすぐ当てる（dreaming の 3d）
RECS = ("適用", "様子見", "却下")
TOPICS = {  # 決まりの ID の主題（何についての決まりか）。ID は一度付けたら、ファイルを分けても移しても変えない（../rules.md の "Rule IDs"）
    "deck-flow": "1〜11 の工程と、どの工程でも守ること", "deck-agents": "子の起こし方と待ち方", "deck-content": "構成案と言葉",
    "deck-sources": "材料の集め方と出典の台帳", "deck-drive": "Drive への置き方", "deck-rules": "決まりの層と、修正の指示の戻し方",
    "deck-review": "返す前のレビューと、その観点", "deck-comments": "コメントから直す", "deck-profile": "顧客の profile", "deck-research": "調べ直し",
    "deck-lint": "スライドとドキュメントで共通の lint", "deck-google": "Google の API・認証・上限", "deck-brand": "書体・字幅・著作権表示",
    "slides-flow": "6〜8 の工程と、確かめの 3 層", "slides-command": "組むコマンドと、組むときのふるまい", "slides-pages": "ページの JSON の書き方",
    "slides-component": "部品の寸法と描き方", "slides-visual": "スライドの見た目", "slides-theme": "テーマとテンプレート", "slides-image": "画像・ロゴ・アイコン",
    "slides-api": "Slides API の落とし穴", "slides-legacy": "pages.py と pptx の古いデッキ", "slides-reuse": "社内のデッキの流用", "slides-lint": "スライドの lint と画像での測り",
    "docs-write": "doc.md の書き方と組み方", "docs-visual": "ドキュメントの見た目", "docs-lint": "ドキュメントの lint", "docs-api": "Docs API の落とし穴",
    "vids-voice": "動画の読み上げの台本（スピーカーノート）", "vids-voice-ja": "日本語の読み上げの台本", "vids-voice-en": "英語の読み上げの台本",
    "vids-video": "動画を作る・差し替える", "factory-dreaming": "定期の整理"}
WS_ONLY = {"agents": "ワークスペースの AGENTS.md", "memory": "顧客の memory"}  # ワークスペースだけの主題（ws-agents・ws-memory）
PLAN_RULE = "deck-flow-004"  # 構成案の AI レビューの頼み方。これを見直すかの判断待ちに答えたら、構成の見逃しをその答えのあとから数え直す
OVERRIDE = re.compile(rf"\[(ws-[\w-]+?-\d{{3}})\][^\n\[]*?[（(]([^（）()\n]*?)\s*より優先")  # [ws-slides-visual-003] …（slides-visual-012 より優先）。括弧の中の ID を全部取る
PLUGIN_ID = re.compile(r"(?<![\w-])(?!ws-)[a-z][\w-]*?-\d{3}")


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


def utc(s):
    """--at を ts と同じ UTC の形にする（文字のまま ts と比べるので）。時差のない時刻は UTC とみなす（sessions.py の時刻は UTC）。"""
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"--at は ISO 8601 の時刻（2026-10-12T09:30 など。時差がなければ UTC）: {s}")
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def when(c):
    return c.get("at") or c.get("date") or c["ts"]


def by(c):
    """誰が書いたか。作る会話（session）、あとで会話の記録から拾った dreaming（--at）、前の形からの取り込み（import）。
    by のない前の記録は、日付だけ（本文から移した出典）なら取り込み、--at があれば dreaming。前の --once の取り込みは見分けられず、作る会話に入る。"""
    if "by" in c:
        return c["by"]
    if "at" in c:
        return "dreaming"
    return "import" if "date" in c else "session"


def introduces(p):
    """提案が決まりの ID を新しく書き入れるか。今ある決まりを書き直す提案は、決まりを作らない。"""
    tag = f"[{p['rule']}]"
    return bool(p["rule"]) and tag in p["new"] and tag not in p["old"]


def ws_rules_arg(s):
    """--replaces はワークスペースの決まりの ID を , でつないだもの。"""
    ids = [x for x in s.split(",") if x]
    if not ids or not all(re.fullmatch(ID, x) and x.startswith("ws-") for x in ids):
        raise argparse.ArgumentTypeError(f"ワークスペースの決まりの ID を , でつなぐ（ws-slides-visual-003,ws-agents-001 など）: {s}")
    return ids


def rule_arg(s):
    """--rule は決まりの ID の形だけ（崩れた ID は next の番号を数えられない）。"""
    if not re.fullmatch(ID, s):
        raise argparse.ArgumentTypeError(f"決まりの ID の形でない（slides-visual-012・ws-slides-visual-003 など）: {s}")
    return s


def state(ws):
    """台帳を読み直して、いまの指摘（戻し先は最後の route）、提案と判断待ち（状態は最後の出来事）、レビューの結果にする。
    指摘の recur（再発）は、初めてつないだ決まりの ID（first。ファイルは数えない）が、言われたときにあったか。つないだ時刻ではなく、言われた時刻で見る。
    台帳の提案で作った決まり（ID を書き入れた提案を当てた・Issue にした時から、戻した・断られた時まで）は、その間に言われたか（作り直したら、どの間でもよい）。
    台帳で作っていなければ、プラグインの決まりは前からある。ワークスペースの決まりは、初めてつないだ指摘のうち、いちばん早く言われたときにできたとみなす。
    あとで別の決まりに移しても（大元に上げたときなど）first は変えない。未・戻さないに戻したら決め直す。"""
    cs, ps, qs, rv = {}, {}, {}, {}
    life, made = {}, {}  # 台帳の提案で作った決まりの ID → あった間 [[できた時刻, なくなった時刻か None], …]・いまの決まりを作った提案

    def link(c, to):
        if not re.fullmatch(ID, to):  # 未・戻さない・ファイル（1 つのファイルには別々の決まりが入るので、再発を数えない）
            c.pop("first", None)
        elif "first" not in c:
            c["first"] = to

    for n, r in enumerate(records(ws)):
        k = r["kind"]
        if k == "correction":
            cs[r["id"]] = dict(r)
            link(cs[r["id"]], r["to"])
        elif k == "route" and r["ref"] in cs:
            cs[r["ref"]]["to"] = r["to"]
            link(cs[r["ref"]], r["to"])
        elif k == "plan" and r["ref"] in cs:
            if r["plan"] == "なし":
                cs[r["ref"]].pop("plan", None)
            else:
                cs[r["ref"]]["plan"] = r["plan"]
        elif k == "proposal":
            ps[r["id"]] = {**r, "status": "未適用", "proposed": r["rule"]}  # proposed は提案の文に書いた ID（Issue で替えたら rule が替わる）
        elif k in ("applied", "rejected", "withdrawn", "undone", "sent") and r["ref"] in ps:
            p = ps[r["ref"]]
            intro = introduces(p)  # Issue で別の ID にしたときも、もとの提案の文で見る
            p.update(status={"applied": "適用済み", "rejected": "却下", "withdrawn": "取り下げ", "undone": "戻した", "sent": "Issue にした"}[k], seq=n,
                     **{x: r[x] for x in ("appended", "reason", "prev", "pr", "rule") if x in r})
            if k in ("applied", "sent") and intro and p["rule"] not in made:
                life.setdefault(p["rule"], []).append([r["ts"], None])
                made[p["rule"]] = p["id"]
            elif k in ("undone", "rejected", "withdrawn") and made.get(p["rule"]) == p["id"]:  # 作った決まりがなくなった
                life[p["rule"]][-1][1] = r["ts"]
                del made[p["rule"]]
        elif k == "question":
            qs[r["id"]] = {**r, "status": "未回答"}
        elif k in ("answered", "withdrawn") and r["ref"] in qs:
            qs[r["ref"]].update(status="回答済み" if k == "answered" else "取り下げ", **{x: r[x] for x in ("a", "reason") if x in r},
                                **({"answered": r["ts"]} if k == "answered" else {}))
        elif k == "review":
            rv[r["key"]] = r  # 同じ行は、あとで取り込んだ結果にする
    first_said = {}
    for c in cs.values():
        if c.get("first", "").startswith("ws-") and c["first"] not in life:
            first_said[c["first"]] = min(first_said.get(c["first"], when(c)), when(c))
    for c in cs.values():
        if "first" not in c:
            continue
        t, f = when(c), c["first"]
        if "date" in c and "at" not in c:  # 前の形から移した、決まりを作った出典（日付だけ）
            c["recur"] = False
        elif f in life:
            c["recur"] = any(start < t and (end is None or t < end) for start, end in life[f])
        else:
            c["recur"] = t > first_said[f] if f.startswith("ws-") else True
    return cs, ps, qs, list(rv.values())


def rel(ws, p):
    p = (Path.cwd() / Path(p).expanduser()).resolve()  # 絶対パスなら cwd は効かない
    return str(p.relative_to(ws)) if p.is_relative_to(ws) else str(p)


def add(ws, a):
    deck = rel(ws, a.deck)
    same = a.once and next((c for c in state(ws)[0].values() if (c["deck"], c["quote"], c["session"]) == (deck, a.quote, a.session or "")), None)
    if same:  # 前の形の構成案の同じ行を、次の回でまた取り込んだとき。足し直さず、前の ID を返す（会話をまたぐくり返しは --once なしで足す）
        print(same["id"])
        return
    rec = write(ws, {"kind": "correction", "deck": deck, "quote": a.quote, "fix": a.fix or "", "to": a.to, "check": a.check,
                     "session": a.session or "", "decided": a.decided, "by": "import" if a.once else "dreaming" if a.at else "session",
                     **({"at": utc(a.at)} if a.at else {}), **({"plan": a.plan} if a.plan else {})}, ("correction", "c-", 4))
    print(rec["id"])


def show(c):
    d = " ユーザーが決めた" if c.get("decided") else ""
    d += "（再発）" if c.get("recur") else ""
    d += f"（構成の見逃し: {c['plan']}）" if c.get("plan") else ""
    return f"{c['id']} {when(c)[:10]} {c['deck'] or c.get('where') or '-'}「{c['quote'] or c.get('note', '')}」→ {c.get('fix') or '-'} [戻し先: {c['to']}][確かめ: {c.get('check', 'なし')}]{d}"


def customers(decks):
    return {d.split("/")[1] for d in decks if d.startswith("Customers/")}


def count(rows):
    """件数と、それが出た資料の数（dreaming は資料の数で決める）。"""
    return f"{len(rows)}（資料 {len({r['deck'] for r in rows} - {''})}）"


def why(ws, rid):
    all_cs, _, _, rv = state(ws)
    cs = [c for c in all_cs.values() if c["to"] == rid]
    for c in cs:
        print(show(c))
    decks = {c["deck"] for c in cs if c["deck"]}
    print(f"== {rid}: 指摘 {len(cs)} 件（再発 {count([c for c in cs if c.get('recur')])}）・資料 {len(decks)} 本・顧客 {len(customers(decks))} 社・"
          f"ユーザーが決めた: {'あり' if any(c.get('decided') for c in cs) else 'なし'}")
    mine = [r for r in rv if r["rule"] == rid]
    if mine:
        print("   レビュー: " + "・".join(f"{k} {count([r for r in mine if r['result'] == k])}" for k in RESULTS if any(r["result"] == k for r in mine)))
    return cs


def tally(ws):
    """決まりごとの数。再発と「直した」が続くなら、文の決まりでは止まっていない。「残した（誤り）」が多いなら、決まりの書き方が外れている。"""
    cs, _, _, rv = state(ws)
    rows = {}
    row = lambda k: rows.setdefault(k, {"指摘": [], "再発": [], "decks": set(), "決めた": False, **{x: [] for x in RESULTS}})
    for c in cs.values():
        if c["to"] not in NO_RULE:
            x = row(c["to"])
            x["指摘"].append(c)
            if c.get("recur"):
                x["再発"].append(c)
            x["決めた"] |= bool(c.get("decided"))
            x["decks"].add(c["deck"])
    for r in rv:
        x = row(r["rule"])
        x[r["result"]].append(r)
        x["decks"].add(r["deck"])
    signals = ("再発", *RESULTS)
    return {k: {**x, "顧客": len(customers(x["decks"])), "資料ごと": {f: len({r["deck"] for r in x[f]} - {""}) for f in signals}} for k, x in rows.items()}


def summary(ws):
    rows = tally(ws)
    out = sorted(rows.items(), key=lambda kv: (-len(kv[1]["再発"]) - len(kv[1]["直した"]), -len(kv[1]["残した（誤り）"]), kv[0]))
    print("再発とレビューの結果は「件数（出た資料の数）」。資料・顧客は、指摘かレビューの出た資料の数")
    print("決まり\t指摘\t再発\t資料\t顧客\t" + "\t".join(RESULTS) + "\tユーザーが決めた")
    for k, x in out:
        print("\t".join(map(str, [k, len(x["指摘"]), count(x["再発"]), len(x["decks"] - {""}), x["顧客"],
                                   *(count(x[r]) for r in RESULTS), "あり" if x["決めた"] else ""])))
    weekly(ws)
    cs, _, qs, _ = state(ws)
    misses = [c for c in cs.values() if c.get("plan")]
    by_mode = lambda xs: "・".join(f"{m} {count([c for c in xs if c['plan'] == m])}" for m in ("AI", "人"))
    print("\n構成の見逃し: " + by_mode(misses))
    done = [q for q in qs.values() if q["rule"] == PLAN_RULE and q.get("answered")]
    if done:  # 頼み方を見直すかに答えたあとは、そのあとに言われた見逃しで決める
        q = max(done, key=lambda q: q["answered"])
        print(f"  {q['id']} の答え（{q['answered']}）のあと: " + by_mode([c for c in misses if when(c) > q["answered"]]))
    return {k: {**x, "指摘": len(x["指摘"]), **{f: len(x[f]) for f in ("再発", *RESULTS)}} for k, x in rows.items()}


def weekly(ws, weeks=8):
    """週ごとに、誰が指摘を書いたか。dreaming が拾った分が取りこぼし（作る会話が台帳に書かなかった）。コンパクションの前に拾う hook を入れるかの材料。
    構成の見逃しは、方針のレビュー（AI・人）ごとの件数。構成案のレビューの頼み方を変えたあとに減ったかを見る。"""
    n = {}
    for c in state(ws)[0].values():
        y, w, _ = datetime.fromisoformat(when(c)[:10]).isocalendar()
        x = n.setdefault(f"{y}-W{w:02d}", Counter())
        x[by(c)] += 1
        if c.get("plan"):
            x["plan:" + c["plan"]] += 1
    if n:
        print("\n週\t作る会話\tdreaming（取りこぼし）\t取り込み\t取りこぼしの割合\t構成の見逃し（AI・人）")
    for k in sorted(n)[-weeks:]:
        x = n[k]
        print(f"{k}\t{x['session']}\t{x['dreaming']}\t{x['import']}\t{x['dreaming'] / max(1, x['session'] + x['dreaming']):.0%}\t{x['plan:AI']}・{x['plan:人']}")
    return n


def texts(roots, skip=()):
    files = [f for r in roots if r.exists() for f in ([r] if r.is_file() else r.rglob("*"))
             if f.suffix in (".md", ".py") and f.is_file() and f.resolve() not in skip]
    return [f.read_text(encoding="utf-8", errors="ignore") for f in files]


def candidates(ws, plugin=PLUGIN):
    """決まりごとの次の一手。境目はここで決め、dreaming は趣旨（その人の好みか、顧客の事情か）と提案の文だけを考える。"""
    _, ps, _, _ = state(ws)
    plug = "\n".join(texts([plugin], {Path(__file__).resolve()}))
    mine = "\n".join(texts([ws / "AGENTS.md", ws / "rules", *(ws / "Customers").glob("*/memory.md")]))  # ワークスペースの決まりと顧客の memory
    sent = [p for p in ps.values() if p["status"] == "Issue にした"]
    promoted = {t: p for p in sent for t in [*p.get("prev", {}).values(), *p.get("replaces", [])] if t.startswith("ws-")}  # Issue の直しが届いたら要らなくなるワークスペースの決まり（出典の指摘の前の戻し先と --replaces）→ その提案
    out = []
    for k, x in tally(ws).items():
        if not k.startswith("lint:") and f"[{k}]" not in (mine if k.startswith("ws-") else plug):
            continue  # 消した・移した決まり（写しを消したあとも、レビューの結果はもとの ID に残る）
        d, layer = x["資料ごと"], "ワークスペース" if k.startswith("ws-") else "lint" if k.startswith("lint:") else "プラグイン"
        if max(d["再発"], d["直した"]) >= TWICE:
            out.append(("下ろす", k, f"{layer}。再発 {d['再発']} 本・直した {d['直した']} 本の資料（文の決まりでは止まっていない。点検か作る手順に）"))
        if d["残した（誤り）"] >= TWICE:
            out.append(("書き直す", k, f"{layer}。残した（誤り）{d['残した（誤り）']} 本の資料（拾う範囲が外れている。消す・緩めるは判断待ち）"))
        if d["聞く"] >= TWICE:
            out.append(("条件を足す", k, f"{layer}。聞く {d['聞く']} 本の資料（決まりからは決めきれない）"))
        if k.startswith("ws-") and not k.startswith("ws-memory-") and x["顧客"] >= TWICE and k not in promoted:  # Issue にしたものは出し直さない
            out.append(("上げる", k, f"顧客 {x['顧客']} 社・資料 {len(x['decks'] - {''})} 本（その人の好みや顧客の事情でなければ、プラグインに）"))
    gone = {t: p for t, p in promoted.items() if f"[{t}]" in mine and landed(p, plugin)}  # Issue の直しが入っているプラグインに届いたら、ワークスペースの写しは要らない
    for w, p in sorted(gone.items()):
        out.append(("写しを消す", w, f"{p['rule']} がプラグインに入った（{p['id']}、{p.get('pr', '')}）"))
    for w, base in ((w, b) for w, clause in OVERRIDE.findall(mine) for b in PLUGIN_ID.findall(clause) if w not in gone):
        if f"[{base}]" in plug:
            out.append(("上書きを見直す", base, f"{w} が上書きしている（プラグインの決まりが合っていない合図。その人の好みなら、そのまま）"))
        else:
            out.append(("古い上書き", w, f"上書きしている {base} がプラグインにない（入れ直して消えたか、ID が変わった）"))
    last = {p["rule"]: p for p in sorted(ps.values(), key=lambda p: p["id"])}  # 決まりごとに、いちばん新しい提案
    print("次の一手\t決まり\t根拠\t前の提案")
    for act, k, why in out:
        p = last.get(k) or promoted.get(k)
        before = f"{p['id']} {p['status']}{'（' + p['reason'] + '）' if p.get('reason') else ''}" if p else "-"
        print(f"{act}\t{k}\t{why}\t{before}")
    return out


def landed(p, plugin):
    """プラグインへの提案の文（Issue で ID を替えたなら、替えた ID にした文）が、入っているプラグインの行き先のファイルにあるか。
    ID だけでは見ない（今ある決まりを書き直す提案は、ID が前からある）。Issue で文を変えたら届いたとは分からないので、写しを消す案を出さない（重なりは dreaming の 4e で見る）。"""
    tag = f"[{p['proposed']}]"
    want = [x.replace(tag, f"[{p['rule']}]").strip() for x in p["new"].splitlines() if p["proposed"] and tag in x]
    f = plugin / p["file"]
    return bool(want) and f.is_file() and all(x in f.read_text(encoding="utf-8") for x in want)


def next_id(ws, prefix):
    found = texts([PLUGIN, ws / "rules", ws / "AGENTS.md", ws / "Customers"], {Path(__file__).resolve(), (PLUGIN / "factory-migrate" / "scripts" / "migrate.py").resolve()})  # selftest の試しの ID は数えない
    num = re.compile(rf"{re.escape(prefix)}-(\d{{3}})")
    ids = [m.group(1) for t in found for m in RULE_ID.finditer(t)]
    ids += [r.get("rule", "") for r in records(ws) if r["kind"] in ("proposal", "sent")]  # 提案だけで、まだ当てていない ID と、Issue で替えた ID も使ったものにする
    used = [int(m.group(1)) for x in ids if (m := num.fullmatch(x))]
    return f"{prefix}-{max(used, default=0) + 1:03d}"


def known(ws, prefix):
    """新しい ID を出してよい接頭辞か（TOPICS の主題か、ワークスペースでもう使っているもの）。打ち間違いと主題の増えすぎを止める。"""
    topic = prefix.removeprefix("ws-")
    if topic in TOPICS or prefix.startswith("ws-") and topic in WS_ONLY:
        return True
    return any(re.search(rf"\[{re.escape(prefix)}-\d{{3}}\]", t) for t in texts([ws / "rules", ws / "AGENTS.md", ws / "Customers"]))


def where(ws, rid):
    """[rid] が書いてあるファイルと行（プラグインは skills/ から、ワークスペースは rules/ などから）。"""
    out = []
    for root, base in ((PLUGIN, PLUGIN), (ws / "rules", ws), (ws / "AGENTS.md", ws), (ws / "Customers", ws)):
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = sorted(root.rglob("*"))
        else:
            continue
        for f in files:
            if f.suffix in (".md", ".py") and f.is_file() and f.resolve() != Path(__file__).resolve():
                for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if f"[{rid}]" in line:
                        out.append(f"{f.relative_to(base)}:{n}")
    return out


def target(ws, f):
    p = (ws / f).resolve()
    if not p.is_relative_to(ws) or p.is_relative_to(PLUGIN):
        sys.exit(f"変更先はワークスペースの中のファイルだけ（プラグインは factory-kaizen で Issue にする）: {f}")
    return p


def propose(ws, a):
    a.replaces and not a.plugin and sys.exit("--replaces はプラグインへの提案（--plugin）だけ")
    if a.plugin:  # 当てないので、skills/ の中を指していることだけ見る
        (PLUGIN / a.file).resolve().is_relative_to(PLUGIN) or sys.exit(f"--plugin の --file は skills/ からのパス（slides-build/visual.md など）: {a.file}")
    else:
        target(ws, a.file)
    a.rec_why and not a.rec and sys.exit("--rec-why は --rec と一緒に付ける")
    auto = a.auto and auto_ok(ws, a)
    rec = write(ws, {"kind": "proposal", "file": a.file, "old": a.old or "", "new": a.new, "rule": a.rule or "", "why": a.why,
                     "src": [x for x in (a.src or "").split(",") if x], "type": a.kind or "", **({"plugin": True} if a.plugin else {}),
                     **({"replaces": a.replaces} if a.replaces else {}), **({"rec": a.rec, "rec_why": a.rec_why or ""} if a.rec else {}),
                     **({"auto": True} if a.auto else {})}, ("proposal", "P", 4))
    if not auto:
        print(rec["id"])
        return
    f, text, out = auto
    try:
        print(rec["id"])
        apply(ws, [rec["id"]])
    except BaseException:  # 確かめたあとでファイルが変わった・書けなかった。人の見ていない提案を、未適用のまま残さない
        try:
            if f.exists() and f.read_text(encoding="utf-8") == out:  # ファイルに書いたあとで止まったなら、消した行を戻す
                f.write_text(text, encoding="utf-8")
        finally:
            write(ws, {"kind": "withdrawn", "ref": rec["id"], "reason": "--auto で当てられなかった"})
        raise


def auto_ok(ws, a):
    """--auto で当ててよいか。会話の指摘を出典にせず、AGENTS.md・rules/ の .md で、ID の付いた決まりを丸ごと（続きの行も）消すだけで
    （ほかの行は持ち主の決まりごと並びどおりに残り、ID のない見出し・前置き・空行は 1 行も消さない）、残る決まりの文が変わらず、
    ユーザーが決めた・当てたあとに手で直した決まりに触れないもの。
    人を通さずに新しい文が決まりに入らないようにする（factory-dreaming-001）。--new には前か後ろの行を残す（undo の目印。空の --new は戻せない）。
    よければ (ファイル, 前の文, 当てたあとの文) を返す。"""
    def no(why):
        sys.exit(f"--auto にできない（{why}）。--auto を外して提案にする")
    a.kind in AUTO or no(f"種類が {'・'.join(AUTO)} でない")
    a.src and no("出典が会話の指摘")
    a.plugin and no("プラグインへの提案")
    a.old or no("--old がない。足す提案は人が見る")
    a.new.strip() or no("--new が空。戻せるように、前か後ろの行を --old と --new の両方に入れる")
    "ユーザーが決めた" in a.old and no("ユーザーが決めたと書いた文")
    f = target(ws, a.file)
    f == ws / "AGENTS.md" or f.is_relative_to(ws / "rules") and f.suffix == ".md" or no("変更先が AGENTS.md・rules/ の .md でない")
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    text.count(a.old) == 1 or no(f"今の文が {a.file} に 1 か所でない")
    out = text.replace(a.old, a.new)
    out != text or no("消す行がない")
    out.count(a.new) == 1 or no(f"--new が当てたあとの {a.file} に 1 か所でない（undo の目印にならない）")
    was, now = [], []
    before, after = bodies(text, {}, was), bodies(out, {}, now)
    left, plain = iter(zip(text.splitlines(), was)), iter(text.split("\n"))  # \n のほかの改行の字で行をつながせない
    all(x in left for x in zip(out.splitlines(), now)) and all(x in plain for x in out.split("\n")) or no("行を消すだけでない（書き換える・行の途中で切る・行がつながる・決まりの続きの行だけが残る）。書き換える提案は人が見る")
    def fixed(s, own):  # 消してはいけない行の数。消してよいのは、[ID] のある行と、決まりの字下げした続きの行だけ
        return sum(not (o and (RULE_ID.search(x) or x.startswith((" ", "\t")))) for x, o in zip(s.splitlines(), own))
    fixed(text, was) == fixed(out, now) or no("ID のない行（見出し・前置き・空行）を消す。下の決まりの効く範囲が変わるので人が見る")
    lines = lambda own, r: sum(r in o for o in own)  # 決まりの持つ行の数。flat() は記号だけの行（``` など）を消すので、文の比べだけでは見落とす
    changed = sorted(r for r in after if after[r] != before[r] or lines(now, r) != lines(was, r))
    changed and no(f"残る決まり {','.join(changed)} の文が変わる")  # 決まりの頭の行だけを消し、続きの行が上の決まりに付くときも
    cs, ps, qs, _ = state(ws)
    decided = [c["to"] for c in cs.values() if c.get("decided")]  # 戻し先は「<ファイル> <ID>」のようにも書かれる
    keep = {r for to in decided for r in re.findall(rf"(?<![\w-]){ID}", to)}
    for q in ps.values():  # ユーザーが戻した・却下した提案が消そうとした決まりは、残すと決めたものとみなす
        if q["status"] in ("戻した", "却下"):
            keep |= {q["rule"]} | set(RULE_ID.findall(q["old"])) - set(RULE_ID.findall(q["new"]))
    keep |= {q["rule"] for q in qs.values() if q["status"] == "回答済み"}  # 答えた判断待ちの決まり
    mine = sorted(keep & (before.keys() - after.keys()))
    mine and no(f"ユーザーが決めた・戻した・却下した決まり {','.join(mine)}")
    same = lambda x: (ws / x).resolve() == f  # ./rules/a.md と rules/a.md を同じファイルにする
    any(not re.search(ID, to) and any(map(same, filter(None, re.split(r"[\s（）()#、,]+", to)))) for to in decided) and no(f"ユーザーが決めた指摘が、ID なしで {a.file} を戻し先にしている")
    any(same(ps[k]["file"]) for k in drift(ws, quiet=True)) and no(f"{a.file} は当てたあとに手で直された")
    return f, text, out


def diff(p):
    return "".join(difflib.unified_diff((p["old"] + "\n").splitlines(True) if p["old"] else [], (p["new"] + "\n").splitlines(True), p["file"], p["file"]))


def pending(ws, status="未適用"):
    out = [p for p in state(ws)[1].values() if status in ("all", p["status"])]
    for p in out:
        why = f"、理由: {p['reason']}" if p.get("reason") else ""
        where = f"プラグインの skills/{p['file']}" if p.get("plugin") else p["file"]
        pr = f"、{p['pr']}" if p.get("pr") else ""
        rec = (f"、推奨: {p['rec']}" + (f"（{p['rec_why']}）" if p.get("rec_why") else "")) if p.get("rec") else ""
        rec += "、出してすぐ当てた" if p.get("auto") else ""
        print(f"### {p['id']} {p['why']}（{p['status']}、{p['type'] or '-'}、{where}{'、' + p['rule'] if p['rule'] else ''}、出典 {','.join(p['src']) or '-'}{why}{pr}{rec}）\n{diff(p)}")
    return out


def apply(ws, ids):
    ps = state(ws)[1]
    ids = [i for i, p in ps.items() if p["status"] == "未適用" and not p.get("plugin")] if ids == ["all"] else ids
    for i in ids:
        p = ps.get(i) or sys.exit(f"提案がない: {i}")
        if p["status"] != "未適用":
            sys.exit(f"{i} は {p['status']}")
        if p.get("plugin"):
            print(f"{i}: プラグインへの提案なので当てない（factory-kaizen で Issue にし、ledger.py sent {i} --issue <URL> で残す）")
            continue
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
        close(ws, p, "applied", appended=not p["old"])
        print(f"{i}: {p['file']} に当てた")


def close(ws, p, kind, **extra):
    """提案を当てた・Issue にした出来事を書き、出典の指摘をその決まりにつなぐ。戻すときのために、前の戻し先を残す。"""
    cs = state(ws)[0]
    write(ws, {"kind": kind, "ref": p["id"], "prev": {c: cs[c]["to"] for c in p["src"] if c in cs}, **extra})
    for c in p["src"]:
        write(ws, {"kind": "route", "ref": c, "to": p["rule"] or p["file"]})


def reopen(ws, p):
    """close でつないだ出典の指摘を、前の戻し先に戻す（あとで別の決まりに移したものは、そのまま）。"""
    cs = state(ws)[0]
    for c, to in p.get("prev", {}).items():
        if cs.get(c, {}).get("to") == (p["rule"] or p["file"]):
            write(ws, {"kind": "route", "ref": c, "to": to})


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
    reopen(ws, p)
    print(f"{i}: 戻した")


def effective(p, done):
    """p の文に、あとで同じファイルに当てた置き換えを順に当てた、いまあるはずの文。あとの提案がまるごと含んだなら None（そちらで見る）。"""
    text = p["new"]
    for q in sorted((q for q in done if q["file"] == p["file"] and q["seq"] > p["seq"] and q["old"]), key=lambda q: q["seq"]):
        if text in q["old"]:
            return None
        text = text.replace(q["old"], q["new"])
    return text


def drift(ws, quiet=False):
    out, done = [], [p for p in state(ws)[1].values() if p["status"] == "適用済み"]
    for p in done:
        f, want = ws / p["file"], effective(p, done)
        if want and (not f.exists() or want not in f.read_text(encoding="utf-8")):
            out.append(p["id"])
            quiet or print(f"{p['id']} {p['file']}{' ' + p['rule'] if p['rule'] else ''}: 当てた文がない（手で直されたか消えた。ユーザーが直したものとして扱い、覆さない）")
    return out


def questions(ws, everything=False):
    out = [q for q in state(ws)[2].values() if everything or q["status"] == "未回答"]
    for q in out:
        tail = ""
        if q.get("a"):
            tail = f" → 「{q['a']}」（{q['answered']}）"
        elif q.get("reason"):
            tail = f"（{q['reason']}）"
        elif q.get("rec"):
            tail = f" 推奨: {q['rec']}"
        print(f"{q['id']} [{q['status']}] {q['q']}（{q['rule'] or '-'}、出典 {','.join(q['src']) or '-'}）{tail}")
    return out


def result_of(cell):
    if cell.startswith("残した（誤り"):
        return "残した（誤り）"
    return next((k for k in ("直した", "聞く", "残した") if cell.startswith(k)), None)


def flat(s):
    return re.sub(r"\]\([^)]*\)|[\s*`「」『』（）()\[\]、。・]", "", s)  # 太字の印や句読点、リンク先の違いで外れないように


def rule_texts(ws):
    """決まりの ID → その決まりの文（同じ行の次の [ID] まで。行の最初の決まりは行の頭から、最後の決まりは続く字下げの行も）を flat にしたもの。
    行の頭に立つ決まり（[deck-content-001] **どの種類でも**）は、空行までの ID のない行も。箇条書きの決まりには、隣の ID のない項目をつなげない（その項の語句を近くの ID に付けたら止める）。
    プラグインとワークスペースの決まりと顧客の memory から。[ID] は決まりを書いたところにだけ付け、ほかから指すときは角括弧を付けない（rules.md の「Rule IDs」）。"""
    out = {}
    for t in texts([PLUGIN, ws / "AGENTS.md", ws / "rules", *(ws / "Customers").glob("*/memory.md")], {Path(__file__).resolve()}):
        bodies(t, out)
    return out


def bodies(t, out, own=None):
    """1 つのファイルの文 t から、rule_texts の決まりの ID → 文を out に足す。own に list を渡すと、行ごとの持ち主の決まりの ID の集合も入れる。"""
    lines = t.splitlines()
    own = [] if own is None else own
    own[:] = [set() for _ in lines]
    for i, l in enumerate(lines):
        ms = list(RULE_ID.finditer(l))
        for j, (m, n) in enumerate(zip(ms, ms[1:] + [None])):
            body = l[m.end() if j else 0:n.start() if n else None]  # 行の頭から: 1. 話の筋: [ID] …・MID = "…"  # [ID]
            own[i].add(m.group(1))
            if not n:
                group = l.lstrip().startswith("[")
                for k, x in enumerate(lines[i + 1:], i + 1):
                    if RULE_ID.search(x):
                        if group and not x.lstrip().startswith("["):  # まとまりの中の箇条書きの決まりは飛ばす。次に行の頭に立つ決まりで終わる
                            continue
                        break
                    if not (x.startswith((" ", "\t")) or group and x.strip()):
                        break
                    body += x
                    own[k].add(m.group(1))
            out[m.group(1)] = out.get(m.group(1), "") + "\n" + flat(body)
    return out


def review(ws, deck, table):
    """deck-review の指摘の表（1 件 1 行。`p3 | 出所 | 観点 | 重さ | 何が | 案 | 結果 | 決まり`）から、決まりの列のある行を取り込む。
    資料の文は残さず、同じ行を見分けるハッシュだけにする。ラウンドをまたいで同じ行があれば、表の後ろ（あとのラウンド）の結果にする。
    決まりの列の ID に「」で添えた語句が、その ID の決まりの文にないときは、その ID だけ取り込まずに知らせる（ID の付け違い）。"""
    deck, last = rel(ws, deck), {r["key"]: r["result"] for r in state(ws)[3]}
    rows, skip, wrong, bare, known = {}, 0, [], set(), rule_texts(ws)
    for line in Path(table).read_text(encoding="utf-8").splitlines():
        cells = [x.strip() for x in re.sub(r"^[-*]\s+", "", line.strip()).strip("|").split("|")]
        if len(cells) < 8 or not re.match(r"p\d|全体", cells[0]):
            continue
        res = result_of(cells[-2])
        if not res:
            skip += 1
            continue
        cited, bad = CITE.findall(cells[-1]), set()  # 同じ ID に語句を 2 つ添えたら、どちらも確かめる
        for k, q in cited:
            if not (flat(q) and flat(q) in known.get(k, "")):
                bad.add(k)
                wrong.append(f"{cells[0]} {k}「{q}」は、{'その決まりの文にない' if k in known else 'その ID の決まりが見つからない'}")
        keys = [k for k in (x.strip(" []") for x in re.split(r"[,、]", CITE.sub(r"\1", cells[-1]))) if KEY.fullmatch(k) and k not in bad]
        if not keys:
            skip += 1
            continue
        for k in keys:
            key = hashlib.sha1(f"{deck}|{cells[0]}|{cells[4]}|{k}".encode()).hexdigest()[:12]
            if k.startswith("lint:") or k in dict(cited):  # ラウンドをまたぐ同じ行は、あとのラウンドの書き方で数える
                bare.discard(key)
            else:
                bare.add(key)
            rows.pop(key, None)  # あとの行を後ろに置き直す
            rows[key] = {"kind": "review", "deck": deck, "rule": k, "page": cells[0], "from": cells[1], "result": res, "key": key}
    new = [r for key, r in rows.items() if last.get(key) != r["result"]]
    for r in new:
        write(ws, r)
    print(f"取り込んだ {len(new)} 件（決まりか結果のない行 {skip}、取り込み済み {len(rows) - len(new)}）")
    for w in wrong:
        print(f"取り込まなかった: {w}（ID の付け違い。当たる決まりを引き直すか、- にする）")
    if bare:
        print(f"決まりの文の語句のない ID が {len(bare)} 件（決まりの列は <ID>「<決まりの文から写した語句>」。deck-review の指摘の表）")
    return len(new)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--deck", required=True); s.add_argument("--quote", required=True); s.add_argument("--fix")
    s.add_argument("--to", default="未"); s.add_argument("--check", default="なし"); s.add_argument("--session"); s.add_argument("--at"); s.add_argument("--decided", action="store_true"); s.add_argument("--plan", choices=("AI", "人")); s.add_argument("--once", action="store_true")
    s = sub.add_parser("route"); s.add_argument("id"); s.add_argument("to")
    s = sub.add_parser("plan"); s.add_argument("id"); s.add_argument("mode", choices=("AI", "人", "なし"))
    s = sub.add_parser("list"); s.add_argument("--deck"); s.add_argument("--open", action="store_true"); s.add_argument("--to")
    s = sub.add_parser("why"); s.add_argument("id")
    sub.add_parser("rules")
    sub.add_parser("candidates")
    s = sub.add_parser("next"); s.add_argument("prefix")
    s = sub.add_parser("where"); s.add_argument("id")
    sub.add_parser("topics")
    s = sub.add_parser("propose")
    s.add_argument("--file", required=True); s.add_argument("--new", required=True); s.add_argument("--old"); s.add_argument("--rule", type=rule_arg)
    s.add_argument("--why", required=True); s.add_argument("--src"); s.add_argument("--kind"); s.add_argument("--plugin", action="store_true"); s.add_argument("--replaces", type=ws_rules_arg)
    s.add_argument("--rec", choices=RECS); s.add_argument("--rec-why"); s.add_argument("--auto", action="store_true")
    s = sub.add_parser("pending"); s.add_argument("--status", default="未適用")
    s = sub.add_parser("apply"); s.add_argument("ids", nargs="+")
    s = sub.add_parser("reject"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("withdraw"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("undo"); s.add_argument("id")
    sub.add_parser("drift")
    s = sub.add_parser("sent"); s.add_argument("id"); s.add_argument("--issue", dest="pr", required=True); s.add_argument("--rule", type=rule_arg)
    s = sub.add_parser("ask"); s.add_argument("--q", required=True); s.add_argument("--rule", type=rule_arg); s.add_argument("--src"); s.add_argument("--rec")
    s = sub.add_parser("answer"); s.add_argument("id"); s.add_argument("--a", required=True)
    s = sub.add_parser("questions"); s.add_argument("--all", action="store_true")
    s = sub.add_parser("review"); s.add_argument("--deck", required=True); s.add_argument("--table", required=True)
    a = ap.parse_args(argv)
    ws = workspace()
    if a.cmd == "add":
        add(ws, a)
    elif a.cmd == "route":
        state(ws)[0].get(a.id) or sys.exit(f"指摘がない: {a.id}")
        write(ws, {"kind": "route", "ref": a.id, "to": a.to})
    elif a.cmd == "plan":
        state(ws)[0].get(a.id) or sys.exit(f"指摘がない: {a.id}")
        write(ws, {"kind": "plan", "ref": a.id, "plan": a.mode})
    elif a.cmd == "list":
        deck = rel(ws, a.deck) if a.deck else None
        for c in state(ws)[0].values():
            if (not deck or c["deck"] == deck) and (not a.open or c["to"] == "未") and (not a.to or c["to"] == a.to):
                print(show(c))
    elif a.cmd == "why":
        why(ws, a.id)
    elif a.cmd == "rules":
        summary(ws)
    elif a.cmd == "candidates":
        candidates(ws)
    elif a.cmd == "next":
        known(ws, a.prefix) or sys.exit(f"主題の表にない接頭辞: {a.prefix}。TOPICS（ledger.py topics）から選ぶ。新しい主題が要るなら、先に TOPICS に足す（../rules.md の「Rule IDs」）")
        print(next_id(ws, a.prefix))
    elif a.cmd == "where":
        print("\n".join(where(ws, a.id)) or f"{a.id} はどこにもない（消した決まりなら why で経緯を見る）")
    elif a.cmd == "topics":
        print("\n".join(f"{k}\t{v}" for k, v in {**TOPICS, **{f"ws-{k}": v for k, v in WS_ONLY.items()}}.items()))
    elif a.cmd == "propose":
        propose(ws, a)
    elif a.cmd == "pending":
        pending(ws, a.status)
    elif a.cmd == "apply":
        apply(ws, a.ids)
    elif a.cmd in ("reject", "withdraw", "sent"):
        _, ps, qs, _ = state(ws)
        p = ps.get(a.id) or (qs.get(a.id) if a.cmd == "withdraw" else None) or sys.exit(f"提案がない: {a.id}")
        sent = p["status"] == "Issue にした"  # Issue が断られた・取り下げたときは閉じられる
        p["status"] in ("未適用", "未回答") or (sent and a.cmd != "sent") or sys.exit(f"{a.id} は {p['status']}")
        if a.cmd == "sent":
            p.get("plugin") or sys.exit(f"{a.id} はワークスペースへの提案。apply で当てる")
            renamed = {"rule": a.rule} if a.rule else {}  # Issue で提案と違う ID にした
            close(ws, {**p, **renamed}, "sent", pr=a.pr, **renamed)
        else:
            write(ws, {"kind": {"reject": "rejected", "withdraw": "withdrawn"}[a.cmd], "ref": a.id, "reason": a.reason})
            if sent:
                reopen(ws, p)
    elif a.cmd == "ask":
        print(write(ws, {"kind": "question", "q": a.q, "rule": a.rule or "", "src": [x for x in (a.src or "").split(",") if x], **({"rec": a.rec} if a.rec else {})}, ("question", "Q", 4))["id"])
    elif a.cmd == "answer":
        q = state(ws)[2].get(a.id) or sys.exit(f"判断待ちがない: {a.id}")
        q["status"] == "未回答" or sys.exit(f"{a.id} は {q['status']}")
        write(ws, {"kind": "answered", "ref": a.id, "a": a.a})
    elif a.cmd == "questions":
        questions(ws, a.all)
    elif a.cmd == "review":
        review(ws, a.deck, a.table)
    elif a.cmd == "undo":
        undo(ws, a.id)
    elif a.cmd == "drift":
        drift(ws)


def selftest_topics():
    """プラグインのどの [ID] も、TOPICS の主題を使い、1 つのファイルにだけ書く（ファイルを分けたり、新しい決まりを足したりしたときに、表から外れた ID を止める）。"""
    bad, seen = [], {}
    for f in sorted(PLUGIN.rglob("*")):
        if f.suffix in (".md", ".py") and f.is_file() and "factory-migrate" not in f.parts and "templates" not in f.parts and f.resolve() != Path(__file__).resolve():
            for m in RULE_ID.finditer(f.read_text(encoding="utf-8")):
                rid = m.group(1)
                if rid.startswith("ws-"):
                    continue
                if rid.rsplit("-", 1)[0] not in TOPICS:
                    bad.append(f"主題の表にない {f.relative_to(PLUGIN)}: {rid}")
                if rid in seen and seen[rid] != f:
                    bad.append(f"2 か所に書いた {rid}: {seen[rid].relative_to(PLUGIN)}・{f.relative_to(PLUGIN)}（角括弧の ID は書いてある場所。ほかは角括弧なしで指す）")
                seen.setdefault(rid, f)
    assert not bad, "; ".join(bad)
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "rules").mkdir()
        (ws / "rules" / "a.md").write_text("- [ws-mine-001] x\n")
        assert known(ws, "slides-visual") and known(ws, "ws-slides-visual") and known(ws, "ws-memory") and known(ws, "ws-mine")
        assert not known(ws, "visual") and not known(ws, "slides-visuals") and not known(ws, "ws-nothing")
        assert where(ws, "ws-mine-001") == ["rules/a.md:1"] and where(ws, "ws-none-001") == []
        assert where(ws, "slides-visual-012")[0].startswith("slides-build/visual.md:")


def selftest():
    import contextlib, io, os
    selftest_topics()
    quiet = lambda *a: contextlib.redirect_stdout(io.StringIO())
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d).resolve()
        (ws / "factory.toml").write_text("")
        (ws / "Customers" / "acme" / "deck_202610").mkdir(parents=True)
        (ws / "rules" / "slides-build").mkdir(parents=True)
        (ws / "rules" / "slides-build" / "visual.md").write_text("`slides-build/visual.md` に足す。\n\n- [ws-slides-visual-001] 本文は 16pt。\n")
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
            assert next_id(ws, "ws-slides-visual") == "ws-slides-visual-002" and next_id(ws, "nothing") == "nothing-001"
            assert next_id(ws, "slides-visual") != "slides-visual-001"  # プラグインの ID も数える
            # 足す提案を当て、出典の指摘を決まりにつなぐ
            with quiet():
                main(["propose", "--file", "rules/slides-build/visual.md", "--new", "- [ws-slides-visual-002] 収まらない表は 2 枚に分ける。", "--rule", "ws-slides-visual-002", "--why", "表の分け方", "--src", "c-0001"])
            assert next_id(ws, "ws-slides-visual") == "ws-slides-visual-003"  # 提案だけの ID も使ったもの
            with quiet():
                assert len(pending(ws)) == 1
                main(["apply", "all"])
            v = ws / "rules" / "slides-build" / "visual.md"
            assert "[ws-slides-visual-002]" in v.read_text() and state(ws)[0]["c-0001"]["to"] == "ws-slides-visual-002"
            with quiet():
                assert len(why(ws, "ws-slides-visual-002")) == 1 and drift(ws) == []
            # 置き換える提案。今の文が変わっていたら当てない
            with quiet():
                main(["propose", "--file", "rules/slides-build/visual.md", "--old", "本文は 16pt。", "--new", "本文は 18pt。", "--why", "大きさ"])
                main(["propose", "--file", "rules/slides-build/visual.md", "--old", "ない文", "--new", "x", "--why", "合わない"])
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
                main(["propose", "--file", "rules/slides-build/visual.md", "--new", "x", "--why", "書き間違い"])
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
            # 再発: 決まりができたあとに言われた指摘だけ。前に言われてあとで拾ったもの（--at）と、決まりを作った指摘は数えない
            with quiet():
                main(["add", "--deck", ".", "--quote", "表はまた 2 枚に", "--to", "ws-slides-visual-002", "--at", "2999-01-01T00:00"])
                main(["add", "--deck", ".", "--quote", "前の会話でも表を分けてと", "--to", "ws-slides-visual-002", "--at", "2000-01-01T00:00"])
                main(["add", "--deck", ".", "--quote", "出典は 1 行に", "--to", "slides-visual-012"])  # プラグインの決まりは前からある
            cs = state(ws)[0]
            assert [cs[i].get("recur") for i in ("c-0001", "c-0006", "c-0007", "c-0008")] == [False, True, False, True]
            with quiet():
                main(["route", "c-0001", "slides-visual-099"])  # 大元に上げて移しても、決まりを作った指摘のまま
                assert state(ws)[0]["c-0001"]["recur"] is False and summary(ws)["ws-slides-visual-002"]["再発"] == 1
            try:
                main(["add", "--deck", ".", "--quote", "x", "--at", "きのう"])
                raise AssertionError("時刻でない --at を通した")
            except SystemExit:
                pass
            # プラグインへの提案は当てず、Issue にしたか却下で閉じる。Issue にしたら出典の指摘をつなぎ、断られたら前の戻し先に戻す
            with quiet():
                main(["add", "--deck", ".", "--quote", "表は分けて（別の会話）", "--at", "2000-01-01T09:00+09:00"])
            assert state(ws)[0]["c-0009"]["at"] == "2000-01-01T00:00:00Z"  # --at は UTC にそろえる
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-099] 表は分ける。", "--rule", "slides-visual-099", "--why", "上げる", "--kind", "プラグインに上げる", "--src", "c-0009"])
                main(["propose", "--plugin", "--file", "deck-practices/content.md", "--new", "x", "--why", "上げる"])
                main(["propose", "--file", "rules/w.md", "--new", "- [ws-w-001] 1 つ", "--rule", "ws-w-001", "--why", "足す"])
                main(["apply", "P0010", "P0012"])  # 並びにプラグインへの提案があっても、残りは当てる
                main(["apply", "all"])
            ps = state(ws)[1]
            assert [ps[i]["status"] for i in ("P0010", "P0011", "P0012")] == ["未適用", "未適用", "適用済み"]
            for argv in (["sent", "P0012", "--issue", "u"], ["propose", "--plugin", "--file", "../../x.md", "--new", "x", "--why", "y"]):
                try:
                    with quiet():
                        main(argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
            with quiet():
                main(["sent", "P0010", "--issue", "https://github.com/o/r/issues/1"])
                main(["reject", "P0011", "--reason", "この人だけの好み"])
                assert [p["id"] for p in pending(ws, "Issue にした")] == ["P0010"] and "P0011" in [p["id"] for p in pending(ws, "却下")]
            c = state(ws)[0]["c-0009"]
            assert c["to"] == "slides-visual-099" and c["recur"] is False  # Issue にした決まりを作った指摘で、再発ではない
            try:
                main(["sent", "P0010", "--issue", "u"])
                raise AssertionError("Issue にしたものをもう一度 Issue にした")
            except SystemExit:
                pass
            with quiet():
                main(["reject", "P0010", "--reason", "入れずに閉じられた"])
            assert state(ws)[1]["P0010"]["status"] == "却下" and state(ws)[0]["c-0009"]["to"] == "未"
            # 決まりができた時刻は、その ID を書き入れた提案だけで決める。今ある決まりの書き直しは作らず、戻したら消す。Issue で ID を変えたら追う
            cid = lambda q: next(c["id"] for c in state(ws)[0].values() if c["quote"] == q)
            pid = lambda w: next(p["id"] for p in state(ws)[1].values() if p["why"] == w)
            with quiet():
                main(["add", "--deck", ".", "--quote", "既存の決まりなのに", "--at", "2000-01-01T00:00"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-050] a", "--new", "- [slides-visual-050] b", "--rule", "slides-visual-050", "--why", "書き直す", "--src", cid("既存の決まりなのに")])
                main(["sent", pid("書き直す"), "--issue", "u"])
            assert state(ws)[0][cid("既存の決まりなのに")]["recur"] is True  # slides-visual-050 は前からプラグインにある
            with quiet():  # 当てる → 戻す → その間に言われる → 作り直す。時刻を離すため、出来事の行は ts を書いて足す
                main(["propose", "--file", "rules/u.md", "--new", "- [ws-u-001] u", "--rule", "ws-u-001", "--why", "作って戻す"])
                main(["propose", "--file", "rules/u.md", "--new", "- [ws-u-001] u", "--rule", "ws-u-001", "--why", "作り直す"])
                write(ws, {"ts": "2001-01-01T00:00:00Z", "kind": "applied", "ref": pid("作って戻す"), "appended": True, "prev": {}})
                write(ws, {"ts": "2002-01-01T00:00:00Z", "kind": "undone", "ref": pid("作って戻す")})
                main(["add", "--deck", ".", "--quote", "戻したあとに言われた", "--at", "2003-01-01T00:00"])
                write(ws, {"ts": "2004-01-01T00:00:00Z", "kind": "applied", "ref": pid("作り直す"), "appended": True, "prev": {}})
                write(ws, {"ts": "2004-01-01T00:00:00Z", "kind": "route", "ref": cid("戻したあとに言われた"), "to": "ws-u-001"})
            assert state(ws)[0][cid("戻したあとに言われた")]["recur"] is False  # 作り直した決まりの出典で、戻す前の決まりの再発ではない
            with quiet():  # 前の決まりがあった間に言われ、作り直したあとでつないだものは再発。同じ分の中でも秒で比べる
                main(["propose", "--file", "rules/v.md", "--new", "- [ws-v-001] v", "--rule", "ws-v-001", "--why", "v を作る"])
                main(["propose", "--file", "rules/v.md", "--new", "- [ws-v-001] v", "--rule", "ws-v-001", "--why", "v を作り直す"])
                write(ws, {"ts": "2005-01-01T09:30:20Z", "kind": "applied", "ref": pid("v を作る"), "appended": True, "prev": {}})
                main(["add", "--deck", ".", "--quote", "前の v のあいだに", "--at", "2005-01-02T00:00"])
                main(["add", "--deck", ".", "--quote", "同じ分のあとの秒", "--at", "2005-01-01T09:30:45.123Z"])
                main(["add", "--deck", ".", "--quote", "同じ分の前の秒", "--at", "2005-01-01T09:30:05Z"])
                write(ws, {"ts": "2005-01-03T00:00:00Z", "kind": "undone", "ref": pid("v を作る")})
                write(ws, {"ts": "2005-01-04T00:00:00Z", "kind": "applied", "ref": pid("v を作り直す"), "appended": True, "prev": {}})
                for q in ("前の v のあいだに", "同じ分のあとの秒", "同じ分の前の秒"):
                    main(["route", cid(q), "ws-v-001"])
            cs = state(ws)[0]
            assert [cs[cid(q)]["recur"] for q in ("前の v のあいだに", "同じ分のあとの秒", "同じ分の前の秒")] == [True, True, False]
            with quiet():
                main(["add", "--deck", ".", "--quote", "ID が変わる", "--at", "2000-01-01T00:00"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-060] x", "--rule", "slides-visual-060", "--why", "ID を変える", "--src", cid("ID が変わる")])
                main(["sent", pid("ID を変える"), "--issue", "u", "--rule", "slides-visual-061"])
            c = state(ws)[0][cid("ID が変わる")]
            assert (c["to"], c["recur"], state(ws)[1][pid("ID を変える")]["rule"]) == ("slides-visual-061", False, "slides-visual-061")
            with quiet():  # Issue で替えた ID も、次の ID の取り置きに入る
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [zz-900] x", "--rule", "zz-900", "--why", "zz"])
                main(["sent", pid("zz"), "--issue", "u", "--rule", "zz-901"])
            assert next_id(ws, "zz") == "zz-902"
            # 台帳の外で書かれた決まりに、あとから 3 件まとめてつなぐと、いちばん早く言われたものだけが再発でない
            with quiet():
                for q, at in (("手書き 3", "2026-09-09T00:00"), ("手書き 1", "2026-09-01T00:00"), ("手書き 2", "2026-09-05T00:00")):
                    main(["add", "--deck", ".", "--quote", q, "--to", "ws-h-001", "--at", at])
            cs = state(ws)[0]
            assert [cs[cid(f"手書き {i}")]["recur"] for i in (1, 2, 3)] == [False, True, True]
            # 戻さないにしたら、前の決まりの再発を持ち越さない
            with quiet():
                main(["add", "--deck", ".", "--quote", "つなぎ違い", "--to", "slides-visual-012"])
                main(["route", cid("つなぎ違い"), "戻さない"])
                main(["route", cid("つなぎ違い"), "ws-h-002"])
            assert state(ws)[0][cid("つなぎ違い")]["recur"] is False
            # ファイルにつないだ指摘は再発に数えない（1 つのファイルに別々の決まりが入る）
            with quiet():
                for q in ("敬称は様", "ロゴは右上"):
                    main(["add", "--deck", ".", "--quote", q, "--to", "Customers/acme/memory.md"])
                main(["add", "--deck", ".", "--quote", "プラグインのファイルへ", "--to", "deck-practices/content.md"])
            cs = state(ws)[0]
            assert not any(cs[cid(q)].get("recur") for q in ("敬称は様", "ロゴは右上", "プラグインのファイルへ"))
            # 前の形から移した出典（日付だけ）は、プラグインの決まりを作ったもので再発でない。そのあと言われたものは再発
            write(ws, {"kind": "correction", "id": "c-m001", "deck": "", "where": "前の本文", "note": "移した", "quote": "", "date": "2026-10-07", "to": "deck-content-002"})
            with quiet():
                main(["add", "--deck", ".", "--quote", "移したあとに", "--to", "deck-content-002"])
            cs = state(ws)[0]
            assert (cs["c-m001"]["recur"], cs[cid("移したあとに")]["recur"]) == (False, True)
            # 崩れた ID は --rule で止め、台帳に前からあっても next は数えられる
            for argv in (["propose", "--file", "rules/x.md", "--new", "x", "--why", "y", "--rule", "visual-new"], ["ask", "--q", "x", "--rule", "ws visual 1"]):
                try:
                    with quiet(), contextlib.redirect_stderr(io.StringIO()):
                        main(argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
            write(ws, {"kind": "proposal", "id": "P9999", "file": "rules/x.md", "old": "", "new": "x", "rule": "visual-new", "why": "前の台帳", "src": [], "type": ""})
            assert next_id(ws, "slides-visual").startswith("slides-visual-")
            # 判断待ち: 答えたものは、もう未回答に出ない
            with quiet():
                main(["ask", "--q", "見出しは 1 行か 2 行か", "--rule", "ws-slides-visual-002", "--src", "c-0007"])
                main(["ask", "--q", "書き間違い"])
                main(["answer", "Q0001", "--a", "1 行にする"])
                main(["withdraw", "Q0002", "--reason", "出し直す"])
                assert questions(ws) == [] and [q["status"] for q in questions(ws, True)] == ["回答済み", "取り下げ"]
            # 推奨: 提案と判断待ちに残し、一覧に出す
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main(["propose", "--file", "rules/r.md", "--new", "x", "--why", "推奨", "--rec", "様子見", "--rec-why", "1 本の資料だけ"])
                main(["ask", "--q", "残すか", "--rec", "残す"])
                pending(ws)
                questions(ws)
            assert "推奨: 様子見（1 本の資料だけ）" in out.getvalue() and "推奨: 残す" in out.getvalue(), out.getvalue()
            # --auto: 会話を出典にしない片付けだけを、出してすぐ当てる。ほかは台帳に書かずに止める
            (ws / "rules").mkdir(exist_ok=True)
            a = ws / "rules" / "a.md"
            a.write_text("- [ws-a-001] 本文は 16pt。\n- [ws-a-002] 本文は 16pt。\n- [ws-a-003] 決めた行。\n  決めた続き。\n", encoding="utf-8")
            with quiet():
                main(["add", "--deck", ".", "--quote", "決めた", "--decided", "--to", "rules/a.md ws-a-003"])
            dup = ["--old", "- [ws-a-001] 本文は 16pt。\n- [ws-a-002] 本文は 16pt。", "--new", "- [ws-a-001] 本文は 16pt。"]
            base = ["propose", "--auto", "--file", "rules/a.md", "--why", "片付け"]
            n = len(state(ws)[1])
            for argv in (base + dup + ["--kind", "くり返し"], base + dup + ["--kind", "重なり", "--src", "c-0001"],
                         base + ["--kind", "重なり", "--new", "- [ws-a-004] 足す"], base + ["--kind", "重なり", "--old", "- [ws-a-001] 本文は 16pt。", "--new", "- [ws-a-001] 紛れ込んだ指示。"],
                         base + ["--kind", "重なり", "--old", "本文は 16pt。\n- [ws-a-002] 本文は 16pt。", "--new", ""],
                         base + ["--kind", "重なり", "--old", "- [ws-a-003] 決めた行。\n  決めた続き。", "--new", "  決めた続き。"],
                         base + ["--kind", "重なり", "--old", "- [ws-a-002] 本文は 16pt。", "--new", ""], base + dup + ["--kind", "重なり", "--rec-why", "x"],
                         base + dup[:2] + ["--new", dup[1], "--kind", "重なり"],
                         base + ["--kind", "古い記述", "--old", "- [ws-a-002] 本文は 16pt。\n- [ws-a-003] 決めた行。\n  決めた続き。", "--new", "- [ws-a-002] 本文は 16pt。"], base + ["--kind", "重なり", "--old", "ない文", "--new", "x"]):
                try:
                    with quiet(), contextlib.redirect_stderr(io.StringIO()):
                        main(argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
            (ws / "rules" / "b.md").write_text("注: x\n注: x\n表は左から読む。\n", encoding="utf-8")
            try:  # ID のない行でも、--old の末尾の改行を --new で落として次の行とつなげない
                with quiet(), contextlib.redirect_stderr(io.StringIO()):
                    main(["propose", "--auto", "--file", "rules/b.md", "--why", "片付け", "--kind", "重なり", "--old", "注: x\n注: x\n", "--new", "注: x"])
                raise AssertionError("行をつなげた")
            except SystemExit:
                pass
            assert len(state(ws)[1]) == n and (ws / "rules" / "b.md").read_text(encoding="utf-8") == "注: x\n注: x\n表は左から読む。\n"
            for argv in (["--file", "rules/b.md", "--old", "注: x\n注: x", "--new", "注: x"],  # ID のない行
                         ["--file", "rules/a.md", "--old", "- [ws-a-001] 本文は 16pt。\n- [ws-a-002]", "--new", "- [ws-a-001] 本文は 16pt。\x1e- [ws-a-002]"]):  # \n でない改行の字でつなぐ
                try:
                    with quiet(), contextlib.redirect_stderr(io.StringIO()):
                        main(["propose", "--auto", "--why", "片付け", "--kind", "重なり"] + argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
            (ws / "rules" / "f.md").write_text("- [ws-f-001] 例:\n  ```\n  コマンド\n  ```\n- [ws-f-002] 残す。\n", encoding="utf-8")
            try:  # 記号だけの続きの行（コードの囲みの閉じ）も、決まりの一部だけを消さない
                with quiet(), contextlib.redirect_stderr(io.StringIO()):
                    main(["propose", "--auto", "--why", "片付け", "--kind", "重なり", "--file", "rules/f.md", "--old", "  ```\n- [ws-f-002] 残す。", "--new", "- [ws-f-002] 残す。"])
                raise AssertionError("決まりの一部を消した")
            except SystemExit:
                pass
            (ws / "rules" / "e.md").write_text("## 色\n[ws-e-001] 赤を使う。\n## 表\n表は左から読む。\n\n[ws-e-002] 表は 3 列まで。\n", encoding="utf-8")
            try:  # 行の頭の決まりが持つ、字下げしていない見出し・前置きも消さない
                with quiet(), contextlib.redirect_stderr(io.StringIO()):
                    main(["propose", "--auto", "--why", "片付け", "--kind", "重なり", "--file", "rules/e.md", "--old", "## 色\n[ws-e-001] 赤を使う。\n## 表\n表は左から読む。\n", "--new", "## 色\n"])
                raise AssertionError("見出しを消した")
            except SystemExit:
                pass
            (ws / "rules" / "c.md").write_text("## 見出し\n- [ws-c-001] 次は使わない:\n  - 赤い文字\n- [ws-c-002] 本文は 16pt。\n", encoding="utf-8")
            for argv in (["--file", "rules/c.md", "--old", "## 見出し\n- [ws-c-001] 次は使わない:", "--new", "## 見出し"],  # 続きの行だけが残る
                         ["--file", ".factory/ledger.jsonl", "--old", path(ws).read_text(encoding="utf-8").splitlines()[0] + "\n", "--new", "x"]):  # 決まりのファイルでない
                try:
                    with quiet(), contextlib.redirect_stderr(io.StringIO()):
                        main(["propose", "--auto", "--why", "片付け", "--kind", "重なり"] + argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
            assert len(state(ws)[1]) == n
            def stop(*x, **k):  # ファイルに書いたあとで、台帳に書けずに止まる
                raise OSError("書けない")
            g, real = globals(), close
            g["close"] = stop
            try:
                with quiet():
                    main(base + dup + ["--kind", "重なり"])
                raise AssertionError("止まらなかった")
            except OSError:
                pass
            finally:
                g["close"] = real
            assert "ws-a-002" in a.read_text(encoding="utf-8") and list(state(ws)[1].values())[-1]["status"] == "取り下げ"
            with quiet():
                main(base + dup + ["--kind", "重なり"])
            pid = list(state(ws)[1])[-1]
            assert state(ws)[1][pid]["status"] == "適用済み" and a.read_text(encoding="utf-8") == "- [ws-a-001] 本文は 16pt。\n- [ws-a-003] 決めた行。\n  決めた続き。\n"
            with quiet():
                main(["undo", pid])
            assert "ws-a-002" in a.read_text(encoding="utf-8")
            try:  # ユーザーが戻した片付けは、次の回にもう一度当てない
                with quiet(), contextlib.redirect_stderr(io.StringIO()):
                    main(base + dup + ["--kind", "重なり"])
                raise AssertionError("戻した片付けをまた当てた")
            except SystemExit:
                pass
            with quiet():  # ID なしでこのファイルに戻した、ユーザーが決めた指摘があれば、どこに触れるか分からないので止める
                main(["add", "--deck", ".", "--quote", "ファイルで決めた", "--decided", "--to", "rules/a.md（見出しの下）"])
            try:
                with quiet(), contextlib.redirect_stderr(io.StringIO()):
                    main(["propose", "--auto", "--file", "./rules/a.md", "--why", "片付け", "--kind", "重なり", "--old", dup[1], "--new", "- [ws-a-002] 本文は 16pt。"])  # 戻した ws-a-002 でなく ws-a-001 を消す
                raise AssertionError("ID なしで決めたファイルに、パスの書き方を変えて当てた")
            except SystemExit:
                pass
            # レビューの表: 決まりの列のある行だけ。2 度取り込んでも数えず、ラウンドをまたぐ同じ行はあとのラウンドの結果
            t = ws / "review.md"
            t.write_text("p<ページ> | 出所 | 観点 | 重さ | 何 | 案 | 結果 | 決まり\n"
                         "- p3 | 画像 | 5 | 直す | 表がはみ出す | 2 枚に | 直した | ws-slides-visual-002\n"
                         "| p4 | lint | 4 | 見直す | あおり | 言い換え | 残した（誤り。引用） | lint:あおり, [slides-visual-012] |\n"
                         "p5 | テキスト | 1 | 聞く | 筋 | 案 | 聞く | -\n"
                         "p6 | 画像 | 5 | 直す | ずれ | 直す | まだ | ws-slides-visual-002\n"
                         "p7 | 画像 | 5 | 直す | 余白 | 詰める | 聞く | ws-slides-visual-002\n"
                         "p7 | 画像 | 5 | 直す | 余白 | 詰める | 直した | ws-slides-visual-002\n"
                         "p8 | テキスト | 2 | 直す | 数字 | 直す | 直した（数字の誤りを直した） | slides-visual-012\n")
            with quiet():
                assert review(ws, ".", t) == 5 and review(ws, ".", t) == 0
                s = summary(ws)
            assert (s["ws-slides-visual-002"]["直した"], s["ws-slides-visual-002"]["聞く"]) == (2, 0)
            assert s["lint:あおり"]["残した（誤り）"] == 1 and (s["slides-visual-012"]["残した（誤り）"], s["slides-visual-012"]["直した"]) == (1, 1)
            t.write_text("p3 | 画像 | 5 | 直す | 表がはみ出す | 2 枚に | 残した（3 ラウンドで打ち切り） | ws-slides-visual-002\n")
            with quiet():
                assert review(ws, ".", t) == 1
                s = summary(ws)
            assert (s["ws-slides-visual-002"]["直した"], s["ws-slides-visual-002"]["残した"]) == (1, 1)  # あとで取り込んだ結果に替わる
            # 決まりの列に添えた語句: その ID の決まりの文（[ID] から次の [ID] まで、行の途中の [ID] も）になければ、その ID だけ取り込まない
            (ws / "rules" / "deck-practices").mkdir(parents=True, exist_ok=True)
            (ws / "rules" / "deck-practices" / "quote.md").write_text(
                "- [ws-q-001] **見出し**は、短い名詞句にする。\n  言い切りは 2〜3 枚。\n"
                "- 出典の書き方。[ws-q-002] 出典には、[リンク](https://example.com)を付ける。\n本文から指すときは ws-q-003 と書く。\n\n"
                "[ws-q-004] **話す資料のとき**\n- 1 枚に 1 つ。\n- [ws-q-005] 細部はノートに。\n- 読む資料には当てはめない。\n[ws-q-006] **次のまとまり**\n- 次のまとまりの項。\n\n- 空行のあとは別。\n")
            q = ws / "review_q.md"
            q.write_text("p1 | 画像 | 5 | 直す | 見出しが文 | 名詞句に | 直した | ws-q-001「見出しは、短い名詞句」\n"
                         "p2 | 画像 | 5 | 直す | 言い切りが多い | 減らす | 直した | [ws-q-001]「言い切りは 2〜3 枚」\n"
                         "p3 | lint | 4 | 直す | 帯が短い | 伸ばす | 直した | ws-q-002「見出しは、短い名詞句」, lint:あおり\n"
                         "p4 | 画像 | 5 | 直す | 参照 | 直す | 直した | ws-q-003「参照」\n"
                         "p5 | 画像 | 5 | 直す | 句読点 | 直す | 直した | ws-q-001「、。」\n"
                         "p6 | 画像 | 5 | 直す | 出典 | 足す | 直した | ws-q-002「リンクを付ける」、ws-q-001\n"
                         "p7 | 画像 | 5 | 直す | 二重 | 直す | 直した | ws-q-001「出典の書き方」, ws-q-001\n"
                         "p7 | 画像 | 5 | 直す | 二重 | 直す | 直した | ws-q-002「出典の書き方」\n"
                         "p6 | 画像 | 5 | 直す | 出典 | 足す | 直した | ws-q-002「リンクを付ける」、ws-q-001\n"
                         "p8 | 画像 | 5 | 直す | 話す | 直す | 直した | ws-q-004「読む資料には当てはめない」, ws-q-005「1 枚に 1 つ」\n"
                         "p9 | 画像 | 5 | 直す | 別 | 直す | 直した | ws-q-004「空行のあとは別」\n"
                         "p10 | 画像 | 5 | 直す | 次 | 直す | 直した | ws-q-004「次のまとまりの項」, ws-q-006「次のまとまりの項」\n")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                assert review(ws, ".", q) == 8
            assert out.getvalue().count("取り込まなかった") == 7 and "語句のない ID が 1 件" in out.getvalue(), out.getvalue()
            s = summary(ws)
            assert (s["ws-q-001"]["直した"], s["ws-q-002"]["直した"], s["lint:あおり"]["直した"]) == (3, 2, 1) and "ws-q-003" not in s and (s["ws-q-004"]["直した"], s["ws-q-006"]["直した"]) == (1, 1) and "ws-q-005" not in s
            q.write_text("p1 | 画像 | 5 | 直す | 見出しが文 | 名詞句に | 直した | ws-q-001\n"
                         "p2 | 画像 | 5 | 直す | 言い切りが多い | 減らす | 残した（誤り） | ws-q-001「言い切りは 2〜3 枚」\n")
            with quiet():
                assert review(ws, ".", q) == 1  # 語句の有無では別の行にならず、あとのラウンドの結果に替わる
            assert (summary(ws)["ws-q-001"]["直した"], summary(ws)["ws-q-001"]["残した（誤り）"]) == (2, 1)
            # 結果ごとに、出た資料の数を数える（1 本の資料の 3 件は、2 本の資料に出たことにならない）
            t.write_text("".join(f"p{i} | 画像 | 5 | 直す | 字 {i} | 直す | 直した | ws-r-001\n" for i in (1, 2, 3)))
            with quiet():
                review(ws, ".", t)
                t.write_text("p1 | 画像 | 5 | 直す | 字 | 直す | 残した（誤り） | ws-r-001\n")
                review(ws, "../../beta/deck_x", t)
                r = summary(ws)["ws-r-001"]
            assert (r["直した"], r["資料ごと"]["直した"], r["資料ごと"]["残した（誤り）"], len(r["decks"])) == (3, 1, 1, 2)
            assert next_id(ws, "slides-visual") != "slides-visual-099"  # プラグインへの提案の ID も使ったもの
            # プラグインのファイルは変更先にしない
            try:
                target(ws, str(PLUGIN / "skills" / "slides-build" / "visual.md"))
                raise AssertionError("プラグインを変更先にした")
            except SystemExit:
                pass
        finally:
            os.chdir(cwd)
    selftest_candidates(quiet)
    print("selftest ok")


def selftest_candidates(quiet):
    import contextlib, io, os
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as plug:
        ws, plug = Path(d).resolve(), Path(plug)
        (ws / "factory.toml").write_text("")
        (ws / "rules" / "slides-build").mkdir(parents=True)
        (ws / "rules" / "slides-build" / "visual.md").write_text(
            "- [ws-slides-visual-001] 表は分ける。\n- [ws-slides-visual-002] 本文は 18pt（slides-visual-012 より優先。読みやすさ）。\n- [ws-slides-visual-003] 見出しは左（slides-visual-777 より優先）。\n"
            "- [ws-slides-visual-004] 表は分ける。[ws-slides-visual-005] 線は細く（slides-visual-013 と slides-visual-012より優先）。deck-flow-001 と同じ\n")
        (plug / "slides-build").mkdir()
        (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 16pt。\n- [slides-visual-013] 線は 1pt。\n")
        for x in ("a/d1", "a/d3", "b/d2"):
            (ws / "Customers" / x).mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            with quiet():
                main(["add", "--deck", "Customers/a/d1", "--quote", "表を分けて", "--to", "ws-slides-visual-001"])  # 作る会話
                main(["add", "--deck", "Customers/b/d2", "--quote", "また表", "--to", "ws-slides-visual-001", "--at", "2999-01-01T00:00"])  # dreaming
                main(["add", "--deck", "Customers/a/d3", "--quote", "また表", "--to", "ws-slides-visual-001", "--at", "2999-01-02T00:00"])
                main(["add", "--deck", "Customers/a/d3", "--quote", "結論を先に", "--to", "戻さない", "--plan", "AI"])  # 構成の見逃し
                main(["add", "--deck", "Customers/b/d2", "--quote", "順序を逆に", "--to", "戻さない"])
                main(["plan", next(c["id"] for c in state(ws)[0].values() if c["quote"] == "順序を逆に"), "AI"])  # 作る会話が付け忘れた印を、あとから付ける
                main(["add", "--deck", "Customers/a/d1", "--quote", "古い行", "--once"])  # 取り込み
                for deck in ("Customers/a/d1", "Customers/b/d2"):
                    main(["add", "--deck", deck, "--quote", "敬称は様", "--to", "ws-memory-001"])
                n = weekly(ws)
            assert sum(x["plan:AI"] for x in n.values()) == 2 and sum(x["plan:人"] for x in n.values()) == 0
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                summary(ws)
            assert "構成の見逃し: AI 2（資料 2）・人 0（資料 0）" in out.getvalue()
            with quiet():
                main(["plan", next(c["id"] for c in state(ws)[0].values() if c["quote"] == "順序を逆に"), "なし"])  # 付け間違いを外す
            assert sum(bool(c.get("plan")) for c in state(ws)[0].values()) == 1
            assert "構成の見逃し: AI" in show(next(c for c in state(ws)[0].values() if c.get("plan")))
            # 頼み方を見直すかに答えたら、答えのあとの見逃しだけを数える（同じ日の前とあとも分ける）
            with quiet():
                main(["ask", "--q", "構成案のレビューの頼み方を見直すか", "--rule", PLAN_RULE])
            qid = next(q["id"] for q in state(ws)[2].values() if q["rule"] == PLAN_RULE)
            write(ws, {"ts": "2030-01-01T12:00:00Z", "kind": "answered", "ref": qid, "a": "見直す"})
            with quiet():
                main(["add", "--deck", "Customers/b/d2", "--quote", "答えの前", "--to", "戻さない", "--plan", "AI", "--at", "2030-01-01T09:00"])
                main(["add", "--deck", "Customers/a/d1", "--quote", "答えのあと", "--to", "戻さない", "--plan", "AI", "--at", "2030-01-01T15:00"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                summary(ws)
                questions(ws, True)
            assert "構成の見逃し: AI 3（資料 3）" in out.getvalue() and f"{qid} の答え（2030-01-01T12:00:00Z）のあと: AI 1（資料 1）・人 0（資料 0）" in out.getvalue()
            assert "→ 「見直す」（2030-01-01T12:00:00Z）" in out.getvalue()
            assert sum(x["session"] for x in n.values()) == 5 and sum(x["dreaming"] for x in n.values()) == 2 and sum(x["import"] for x in n.values()) == 1
            assert [by(c) for c in ({"date": "2026-10-07"}, {"at": "x"}, {"ts": "x"})] == ["import", "dreaming", "session"]  # by のない前の記録
            with quiet():
                out = candidates(ws, plug)
            acts = {(a, k) for a, k, _ in out}
            assert {("下ろす", "ws-slides-visual-001"), ("上げる", "ws-slides-visual-001"), ("上書きを見直す", "slides-visual-012"), ("古い上書き", "ws-slides-visual-003")} <= acts
            over = [(k, w) for a, k, w in out if a == "上書きを見直す"]
            assert sorted(k for k, _ in over) == ["slides-visual-012", "slides-visual-012", "slides-visual-013"] and all("ws-slides-visual-004" not in w for _, w in over)  # 1 行に 2 つの決まり、2 つの ID、空白なし
            assert not any(k == "ws-memory-001" for _, k in acts)  # 顧客の memory は、ほかの顧客に上げない（趣旨が同じなら dreaming が rules/ に寄せる）
            # 上げた決まりがプラグインに届くまでは、写しを残す
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-099] 表は分ける。", "--rule", "slides-visual-099", "--why", "上げる", "--src", "c-0001,c-0002"])
                main(["sent", "P0001", "--issue", "https://github.com/o/r/issues/1"])
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 16pt。\n- [slides-visual-013] 線は 1pt。\n- [slides-visual-099] 表は分ける。\n")
            with quiet():
                assert ("写しを消す", "ws-slides-visual-001") in {(a, k) for a, k, _ in candidates(ws, plug)}
            (ws / "rules" / "slides-build" / "visual.md").write_text("- [ws-slides-visual-002] 本文は 18pt（slides-visual-012 より優先）。\n")
            with quiet():
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))  # 消したら出ない
            # 今ある決まりを書き直す提案は、ID が前からあるので、文が届くまで写しを残す。Issue で ID を替えたら、替えた ID の文で見る
            (ws / "rules" / "slides-build" / "visual.md").write_text("- [ws-slides-visual-002] 本文は 18pt。\n- [ws-slides-visual-006] 線は 2pt。\n")
            with quiet():
                main(["add", "--deck", "Customers/a/d1", "--quote", "18pt に", "--to", "ws-slides-visual-002"])
                main(["add", "--deck", "Customers/a/d1", "--quote", "線を太く", "--to", "ws-slides-visual-006"])
                c18, c2 = (next(c["id"] for c in state(ws)[0].values() if c["quote"] == q) for q in ("18pt に", "線を太く"))
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-012] 本文は 16pt。", "--new", "- [slides-visual-012] 本文は 18pt。", "--rule", "slides-visual-012", "--why", "書き直す", "--src", c18])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-098] 線は 2pt。", "--rule", "slides-visual-098", "--why", "ID を替える", "--src", c2])
                pids = [p["id"] for p in state(ws)[1].values() if p["why"] in ("書き直す", "ID を替える")]
                main(["sent", pids[0], "--issue", "u"])
                main(["sent", pids[1], "--issue", "u", "--rule", "slides-visual-100"])
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))  # まだ 16pt で、slides-visual-100 もない
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 18pt。\n- [slides-visual-013] 線は 1pt。\n- [slides-visual-099] 表は分ける。\n- [slides-visual-100] 線は 2pt。\n")
            with quiet():
                assert {k for a, k, _ in candidates(ws, plug) if a == "写しを消す"} == {"ws-slides-visual-002", "ws-slides-visual-006"}
            # Issue にした出典の決まりは「上げる」を出し直さない。消した決まりは、レビューの結果が残っても出さない
            (ws / "rules" / "slides-build" / "visual.md").write_text("- [ws-slides-visual-007] 図は左から。\n- [ws-slides-visual-008] 扉は使わない（slides-visual-012 より優先）。\n")
            t = ws / "review.md"
            t.write_text("p1 | 画像 | 5 | 直す | 図 | 直す | 直した | ws-slides-visual-007\n")
            with quiet():
                for deck in ("Customers/a/d1", "Customers/b/d2"):
                    review(ws, deck, t)
                main(["add", "--deck", "Customers/a/d1", "--quote", "図は左から", "--to", "ws-slides-visual-007"])
                assert ("上げる", "ws-slides-visual-007") in {(a, k) for a, k, _ in candidates(ws, plug)}
                cz = next(c["id"] for c in state(ws)[0].values() if c["quote"] == "図は左から")
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-101] 図は左から。", "--rule", "slides-visual-101", "--why", "図", "--src", cz])
                main(["sent", next(p["id"] for p in state(ws)[1].values() if p["why"] == "図"), "--issue", "u"])
                out = candidates(ws, plug)
            assert ("上げる", "ws-slides-visual-007") not in {(a, k) for a, k, _ in out} and ("下ろす", "ws-slides-visual-007") in {(a, k) for a, k, _ in out}
            (ws / "rules" / "slides-build" / "visual.md").write_text("- [ws-slides-visual-008] 扉は使わない（slides-visual-012 より優先）。\n")
            with quiet():
                assert not any(k == "ws-slides-visual-007" for _, k, _ in candidates(ws, plug))  # 写しを消したあとは出さない
            # 上書きしている先を直す Issue の直しが届いたら、上書きの写しを消す
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-012] 本文は 18pt。", "--new", "- [slides-visual-012] 扉は使わない。", "--rule", "slides-visual-012", "--why", "扉", "--replaces", "ws-slides-visual-008"])
                main(["sent", next(p["id"] for p in state(ws)[1].values() if p["why"] == "扉"), "--issue", "u"])
                assert ("上書きを見直す", "slides-visual-012") in {(a, k) for a, k, _ in candidates(ws, plug)}  # まだ届いていない（前に届いた slides-visual-012 の別の Issue の直しでは消さない）
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 扉は使わない。\n- [slides-visual-013] 線は 1pt。\n")
            with quiet():
                acts = {(a, k) for a, k, _ in candidates(ws, plug)}
            assert ("写しを消す", "ws-slides-visual-008") in acts and ("上書きを見直す", "slides-visual-012") not in acts
            for argv in (["propose", "--file", "rules/x.md", "--new", "x", "--why", "y", "--replaces", "ws-x-001"], ["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "x", "--why", "y", "--replaces", "slides-visual-012"]):
                try:
                    with quiet(), contextlib.redirect_stderr(io.StringIO()):
                        main(argv)
                    raise AssertionError(f"通した: {argv}")
                except SystemExit:
                    pass
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
