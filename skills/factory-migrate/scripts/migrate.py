#!/usr/bin/env python3
"""usage: migrate.py [check]                         前の版のワークスペースで、変えるものを出す（何も変えない）
       migrate.py apply                         控えを .factory/migrate/<時刻>/ に取ってから、rules/ を移し、決まりの ID とパスを書き換える
       migrate.py relink <P-ID> <rules/ のファイル>|--split   分け直しで行き先が決まらない台帳の提案の、行き先を決める（apply の要判断に出る）
       migrate.py rename-id <前の ID> <今の ID>   ワークスペースの決まりの ID を 1 つ付け替える（rules/・AGENTS.md・memory.md・台帳）
       migrate.py --selftest
ワークスペース（factory.toml のあるフォルダ）を、2026-10-24 の版へ移す。この版で、スキルの名前を slides-・docs- で始め、
プラグインのファイルを読む場面ごとに分け、決まりの ID を主題で付け直した（ids_20261024.json）。ID の表は日付の順に当てる（あとの版で足すときは ids_<日付>.json を置く）。
何度回してもよい。標準ライブラリだけ。"""
import json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]  # プラグインの skills/
sys.path.insert(0, str(PLUGIN / "deck-practices" / "scripts"))
import ledger  # noqa: E402  台帳の提案の状態（state）
from ledger import TOPICS, WS_ONLY  # noqa: E402  決まりの ID の主題
MAPS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.glob("ids_*.json"))]  # 日付の順。ids: 前の ID → 今の ID、prefixes: 前の接頭辞 → 今の接頭辞（ws- と、もうない ID に使う）
MOVES = [  # rules/ の下の前のパス → 今のパス（上から当てる。フォルダはその下を全部）
    ("deck-practices/visual.md", "slides-build/visual.md"), ("deck-practices/reuse.md", "slides-build/reuse.md"),
    ("deck-practices/visual_doc.md", "docs-build/visual.md"), ("deck-build/slides.md", "slides-build/pages.md"),
    ("deck-build", "slides-build"), ("doc-build", "docs-build"), ("deck-template", "slides-template"),
    ("slides-speaker-notes", "vids-voice"), ("vids-beta", "vids-build")]
SPLIT = {  # 中身を場面ごとに分けたプラグインのファイル。ワークスペースの上書きも、どの節への足しかで分け直す
    "deck-practices/SKILL.md": "deck-practices/SKILL.md・start.md・agents.md・deliver.md・revise.md、slides-build/workflow.md",
    "slides-build/pages.md": "slides-build/pages.md・commands.md・themes.md・images.md・api.md・legacy.md（前の deck-build/slides.md）",
    "slides-build/SKILL.md": "slides-build/SKILL.md・lint.md、deck-practices/drive.md（前の deck-build/SKILL.md）",
    "docs-build/SKILL.md": "docs-build/SKILL.md・lint.md・api.md（前の doc-build/SKILL.md）",
    "deck-review/SKILL.md": "deck-review/SKILL.md、deck-practices/agents.md（子の起こし方）"}
B = "A-Za-z0-9_-"  # ID とスキルの名前の前後の区切り（和文は続けて書いてもよいので、英数字だけを見る）
PATHS = [  # 本文の中のパスとスキルの名前（決まりの ID は先に替えるので、deck-build-005 などはもう残っていない）
    (r"deck-practices/visual_doc\.md", "docs-build/visual.md"), (r"deck-practices/visual\.md", "slides-build/visual.md"),
    (r"deck-practices/reuse\.md", "slides-build/reuse.md"), (r"deck-build/slides\.md", "slides-build/pages.md"),
    (r"deck-build/scripts/(docs|doc_layout)\.py", r"docs-build/scripts/\1.py"), (r"deck-build/scripts/(gapi|sheet|drive_put)\.py", r"deck-practices/scripts/\1.py"),
    *((rf"(?<![{B}]){a}(?![{B}])", b) for a, b in (("deck-build", "slides-build"), ("doc-build", "docs-build"), ("deck-template", "slides-template"),
                                                    ("slides-speaker-notes", "vids-voice"), ("vids-beta", "vids-build")))]
OLD_IDS = [re.compile(rf"(?<![{B}])(ws-)?(" + "|".join(sorted(map(re.escape, m["prefixes"]), key=len, reverse=True)) + rf")-(\d{{3}})(?![{B}])") for m in MAPS]
WS_ID = re.compile(r"\[(ws-[\w-]+?-\d{3})\]")
WS_ANY = re.compile(rf"(?<![{B}])ws-[a-z][\w-]*?-\d{{3}}(?![{B}])")  # ワークスペースの決まりの ID（角括弧のあるなしによらない）
PLUGIN_ID = re.compile(rf"(?<![{B}])(?!ws-)([a-z][\w-]*?)-\d{{3}}(?![{B}])")


def workspace(start="."):
    d = Path(start).resolve()
    return next((x for x in (d, *d.parents) if (x / "factory.toml").is_file()), None)


def rewrite(text, paths=True, seen=None, ws_map=None):
    """前の ID とパスを今のものに。接頭辞だけで決める付け替えは、確かに ID だと言えるとき（ws- で始まる、[ID] と角括弧で囲む、
    台帳の値がまるごと ID）だけにする。前の接頭辞には content・assets・template などのふつうの語があり、memory.md の「assets-100」を替えないため。
    ws_map（ws_plan）は、ワークスペースの ID の付け替えを先に当てる（番号がぶつかったものの付け替えも入る）。seen を渡すと、替えた (前, 今) を足す。"""
    if ws_map:
        def mapped(x):
            if seen is not None and x.group(0) in ws_map:
                seen.add((x.group(0), ws_map[x.group(0)]))
            return ws_map.get(x.group(0), x.group(0))
        text = WS_ANY.sub(mapped, text)
    for pat, m in zip(OLD_IDS, MAPS):
        def new_id(x, ids=m["ids"], pre=m["prefixes"]):
            ws, p, num = x.group(1), x.group(2), x.group(3)
            old, t = x.group(0), x.string
            if not ws and f"{p}-{num}" in ids:
                new = ids[f"{p}-{num}"]
            elif ws or t[x.start() - 1:x.start()] == "[" and t[x.end():x.end() + 1] == "]" or (x.start(), x.end()) == (0, len(t)):
                new = f"{ws or ''}{pre[p]}-{num}"
            else:
                return old
            if seen is not None and new != old:
                seen.add((old, new))
            return new
        text = pat.sub(new_id, text)
    for a, b in PATHS if paths else ():
        text = re.sub(a, b, text)
    return text


def texts(ws):
    """ID とパスを書き換える、人と会話が書くファイル。"""
    return [p for p in [ws / "AGENTS.md", *sorted((ws / "rules").rglob("*.md")), *sorted((ws / "Customers").glob("*/memory.md"))] if p.is_file()]


VERBATIM = {"quote", "a", "reason"}  # 台帳の、人の言葉をそのまま持つ欄（修正の指示の原文、判断待ちの答え、却下の理由）。書き換えない


def ledger_lines(path, fn):
    """台帳の行ごとに、文字列の値を fn で書き換える（JSON の形は変えない。人の言葉の欄 VERBATIM はそのまま）。"""
    def walk(v):
        if isinstance(v, str):
            return fn(v)
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: x if k in VERBATIM else walk(x) for k, x in v.items()}
        return v
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        out.append(json.dumps(walk(json.loads(line)), ensure_ascii=False) if line.strip() else line)
    return "\n".join(out) + "\n"


def strings(ws):
    """ID を書き換える文字列: rules/ などの md の本文と、台帳の値（人の言葉の欄 VERBATIM は除く）。"""
    out = [p.read_text(encoding="utf-8") for p in texts(ws)]
    led = ws / ".factory" / "ledger.jsonl"
    if led.is_file():
        ledger_lines(led, lambda v: out.append(v) or v)
    return out


def ws_plan(ws):
    """ワークスペースの ws- の ID の、前 → 今。前に別の接頭辞だったものを 1 つの主題にまとめると番号がぶつかる
    （ws-prompt_doc-001 と ws-prompt_slides-001 がどちらも ws-deck-review-001）ので、あとのものを空いた番号へ移す。
    今の形の ID（付け替えても変わらないもの）は動かさず、その番号も使ったものに数える。定義と台帳に同じ対応を当てるので、履歴は混ざらない。"""
    found = {x for t in strings(ws) for x in WS_ANY.findall(t)}
    target = {x: rewrite(x, paths=False) for x in found}
    taken, out = {x for x in found if target[x] == x}, {}
    for x in sorted(found - taken):
        pre, num = target[x].rsplit("-", 1)
        n = int(num)
        while f"{pre}-{n:03d}" in taken:
            n += 1
        out[x] = f"{pre}-{n:03d}"
        taken.add(out[x])
    return out


def plan(ws):
    """(移すファイル [(前, 今)], 書き換えるファイル [パス], 分け直す上書き [(ファイル, 分けた先)], ワークスペースの ID の対応)。"""
    rules, moves, seen = ws / "rules", [], set()
    for old, new in MOVES:
        src = rules / old
        if src.is_file():
            pairs = [(src, rules / new)]
        elif src.is_dir():
            pairs = [(f, rules / new / f.relative_to(src)) for f in sorted(src.rglob("*")) if f.is_file()]
        else:
            continue
        for f, dst in pairs:
            if f not in seen:  # 上の行で移すと決めたものは、下の行で二度移さない
                seen.add(f)
                moves.append((f, dst))
    led, ws_map = ws / ".factory" / "ledger.jsonl", ws_plan(ws)
    fix = lambda t: rewrite(t, ws_map=ws_map)
    edit = [p for p in texts(ws) if (t := p.read_text(encoding="utf-8")) != fix(t)]
    if led.is_file() and ledger_lines(led, fix) != led.read_text(encoding="utf-8"):
        edit.append(led)
    after = {str(dst.relative_to(rules)) for _, dst in moves}  # 移したあとの rules/ の md
    if rules.is_dir():
        after |= {str(p.relative_to(rules)) for p in rules.rglob("*.md")}
    split = [(k, v) for k, v in SPLIT.items() if k in after]
    return moves, edit, split, ws_map


def relink_files(ws):
    """台帳を合わせる控え: 移行した時点で文がそのファイルにあった当て済みの提案（watch）と、エージェントが決めた行き先（done: 提案 → {"to": ファイルか "split", "from": 前の変更先}）。
    控えのフォルダ（消してよい）でなく .factory/migrate/ の直下に置く。"""
    d = ws / ".factory" / "migrate"
    load = lambda n, empty: json.loads((d / n).read_text(encoding="utf-8")) if (d / n).is_file() else empty
    return d, load("relink.json", []), load("relink_done.json", {})


def in_split(ws):
    """分け直す上書き（SPLIT）を変更先にする提案のうち、まだ当てていないものと当て済みのもの（却下・取り下げ・戻した・Issue にしたは見ない）。"""
    if not (ws / ".factory" / "ledger.jsonl").is_file():
        return []
    return [p for p in ledger.state(ws)[1].values() if p["file"].removeprefix("rules/") in SPLIT and p["status"] in ("未適用", "適用済み")]


def relinks(ws):
    """分け直しで、提案の変更先（file）と文の置き場所が合わなくなったもの: [(提案の ID, 前のファイル, 今のファイル, 決められない理由)]。
    文がほかの rules/ の 1 つのファイルにだけあれば、それが今のファイル（理由は None）。決められないもの（今のファイルは None）は、relink で決める。
    file が古いままだと、ledger.py の apply・undo・drift が文を見つけられない。決めたもの（relink_done.json）は見ない。"""
    rules = ws / "rules"
    _, watch, done = relink_files(ws)
    md = {str(f.relative_to(ws)): f.read_text(encoding="utf-8") for f in rules.rglob("*.md")} if rules.is_dir() else {}
    out = []
    for p in in_split(ws):
        f, i = p["file"], p["id"]
        if i in done:
            continue
        if p["status"] == "未適用" and not p["old"].strip():
            out.append((i, f, None, "まだ当てていない足す提案。分け直したので、足す先を決める"))
            continue
        if p["status"] == "適用済み" and i not in watch:  # 移行の前から文がない（手で直した）。ledger.py drift の受け持ち
            continue
        needle = (p["new"] if p["status"] == "適用済み" else p["old"]).strip()
        if not needle or needle in md.get(f, ""):
            continue
        hits = sorted(k for k, t in md.items() if k != f and needle in t)
        if len(hits) == 1:
            out.append((i, f, hits[0], None))
        else:
            out.append((i, f, None, "当てた文が、分けた先にまたがるか、書き直した" if p["status"] == "適用済み" else "置き換える文が、分けた先にまたがるか、書き直した"))
    return out


def set_file(ws, i, f):
    """台帳の提案 i の変更先を f にする（行の形は変えない）。"""
    led = ws / ".factory" / "ledger.jsonl"
    lines = [json.dumps({**r, "file": f}, ensure_ascii=False) if (r := json.loads(x) if x.strip() else {}).get("kind") == "proposal" and r.get("id") == i else x
             for x in led.read_text(encoding="utf-8").splitlines()]
    led.write_text("\n".join(lines) + "\n", encoding="utf-8")


def asks(todo):
    """決められない提案の要判断と、決め方（relink のコマンド）。"""
    out = []
    for i, a, b, why in todo:
        if b:
            continue
        how = (f"足す先を決めて migrate.py relink {i} <rules/ のファイル>（元のままでよければ {a}）" if why.startswith("まだ当てていない足す")
               else f"1 つのファイルにまとまっているなら migrate.py relink {i} <そのファイル>。分けたままにするなら migrate.py relink {i} --split"
                    "（分けたことを残す。この提案は ledger.py undo で戻せなくなり、ledger.py drift には当てた文がないとして出る。報告に書く）" if why.startswith("当てた")
               else f"置き換える文のあるファイルに migrate.py relink {i} <そのファイル>。要らなくなった提案なら ledger.py withdraw {i} --reason 分け直し")
        out.append(f"要判断: 台帳の {i} の変更先 {a}: {why}。{how}")
    return out


def relink(ws):
    """relinks の今のファイルが決まった提案の file を付け替え、決まらない提案を要判断にする。"""
    todo = relinks(ws)
    for i, a, b, _ in todo:
        if b:
            set_file(ws, i, b)
    return [f"台帳を合わせた: {i} の変更先 {a} → {b}" for i, a, b, _ in todo if b] + asks(todo)


def decide(ws, i, target):
    """エージェントが決めた、提案 i の行き先（rules/ のファイルか "split"）を台帳と relink_done.json に残す。"""
    p = ledger.state(ws)[1].get(i) or sys.exit(f"台帳に {i} がない")
    if target == "--split":
        p["status"] == "適用済み" or sys.exit(f"{i} は {p['status']}。--split は当て済みの提案だけ（まだ当てていないものは、行き先のファイルを渡すか ledger.py withdraw）")
        target = "split"
    else:
        t = (ws / target).resolve()
        t.is_relative_to((ws / "rules").resolve()) and t.suffix == ".md" or sys.exit(f"行き先は rules/ の下の .md: {target}")
        target = str(t.relative_to(ws.resolve()))
        set_file(ws, i, target)
    d, watch, done = relink_files(ws)
    d.mkdir(parents=True, exist_ok=True)  # 前の変更先も残す（台帳の file は書き換えるので）
    (d / "relink_done.json").write_text(json.dumps({**done, i: {"to": target, "from": p["file"]}}, ensure_ascii=False, indent=1), encoding="utf-8")
    return [f"決めた: {i} の行き先 {target}" + ("（分けたことを残した。この提案は undo で戻せない）" if target == "split" else "")]


def needs(ws):
    """前の版のまま残っているもの（factory-doctor が出す）。"""
    moves, edit, _, _ = plan(ws)
    return ([f"rules/{f.relative_to(ws / 'rules')}" for f, _ in moves] + [str(p.relative_to(ws)) for p in edit]
            + [f"台帳の {i} の変更先（{a} → {b or '要判断'}）" for i, a, b, _ in relinks(ws)])


def suggest(ws, rel):
    """分けたファイルへの上書きの、ws- の決まりごとの移し先の見込み（中で指すプラグインの ID の置き場所から）。"""
    out = []
    for line in (ws / "rules" / rel).read_text(encoding="utf-8").splitlines():
        if m := WS_ID.search(line):
            cited = [p.group(0) for p in PLUGIN_ID.finditer(line) if p.group(1) in TOPICS]
            to = sorted({str(f.relative_to(PLUGIN)) for c in cited for f in defined(c)})
            why = f"指す決まり（{'・'.join(cited)}）はプラグインにもうない" if cited else "プラグインの決まりを指していない"
            out.append(f"  {m.group(1)}: {'・'.join(to) if to else why + '。中身から決める'}")
    return out


def off_topic(ws):
    """書き換えたあとも、主題の表にない接頭辞の ID（もっと前の版や手で付けたもの）。台帳は書き換える欄だけを見る（人の言葉の欄の古い ID は、原文のまま残すもの）。"""
    found = set()
    for t in strings(ws):
        found |= {x for x in re.findall(rf"(?<![{B}])((?:ws-)?[a-z][\w-]*?)-\d{{3}}(?![{B}])", t)
                  if x.removeprefix("ws-") not in TOPICS and not (x.startswith("ws-") and x.removeprefix("ws-") in WS_ONLY) and x not in ("c", "p", "q")}
    return sorted(found)


def changed(p, ws_map):
    """書き換える ID の (前 → 今) を、5 つまで添える（check で、ID でないものを替えていないかを見られるように）。"""
    seen = set()
    if p.suffix == ".jsonl":
        ledger_lines(p, lambda v: rewrite(v, seen=seen, ws_map=ws_map))
    else:
        rewrite(p.read_text(encoding="utf-8"), seen=seen, ws_map=ws_map)
    pairs = [f"{a} → {b}" for a, b in sorted(seen)]
    return f"（{'、'.join(pairs[:5])}{f' ほか {len(pairs) - 5}' if len(pairs) > 5 else ''}）" if pairs else "（パスだけ）"


def doc_imports(text):
    """ドキュメントの点検の import を、今のモジュールに。前の版の lint はスライドとドキュメントの部品を 1 つに持っていたが、
    今のドキュメントの lint（docs.py check）からは、スライドの lint.py は読めない。ドキュメントの部品（gdoc_paras など）は doc_lint にある。"""
    text = re.sub(r"(?m)^(\s*)import lint\b(?! as)", r"\1import doc_lint as lint", text)
    return re.sub(r"(?m)^(\s*)from lint import ", r"\1from doc_lint import ", text)


def defined(rid):
    """プラグインで [rid] を書いてあるファイル。"""
    return [f for f in PLUGIN.rglob("*.md") if f"[{rid}]" in f.read_text(encoding="utf-8")]


def apply(ws):
    moves, edit, split, ws_map = plan(ws)
    if not moves and not edit:
        return relink(ws) or ["移すものはない（今の版）"]
    backup = ws / ".factory" / "migrate" / time.strftime("%Y%m%d-%H%M%S")
    n = 1
    while backup.exists():  # 同じ秒に回し直しても、前の控え（前の版の中身）を上書きしない
        n += 1
        backup = backup.with_name(f"{backup.name.split('_')[0]}_{n}")
    for p in [ws / "AGENTS.md", ws / "rules", ws / ".factory" / "ledger.jsonl", *sorted((ws / "Customers").glob("*/memory.md"))]:
        if p.exists():
            dst = backup / p.relative_to(ws)
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst)
    out = [f"控え: {backup}"]
    for src, dst in moves:
        if dst.exists():
            out.append(f"移していない（移す先がもうある。中身を寄せて前のほうを消す）: {src} → {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        out.append(f"移した: {src.relative_to(ws)} → {dst.relative_to(ws)}")
    for old, _ in MOVES:  # 空になったフォルダを、深いほうから消す
        d = ws / "rules" / old
        if not d.is_dir():
            continue
        for x in sorted((p for p in [d, *d.rglob("*")] if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(x.iterdir()):
                x.rmdir()
    checks, doc_checks = ws / "rules" / "slides-build" / "checks.py", ws / "rules" / "docs-build" / "checks.py"
    if checks.is_file() and "def doc(" in checks.read_text(encoding="utf-8") and not doc_checks.exists():  # ドキュメントの点検は docs-build が読む
        doc_checks.parent.mkdir(parents=True, exist_ok=True)
        doc_checks.write_text(doc_imports(checks.read_text(encoding="utf-8")), encoding="utf-8")
        out.append(f"写した: {checks.relative_to(ws)} → {doc_checks.relative_to(ws)}（ドキュメントの lint は doc() をこちらから読む。"
                   "こちらの import lint は import doc_lint as lint にした。それぞれ使わない関数は消してよい）")
    for p in texts(ws):
        t = p.read_text(encoding="utf-8")
        if (n := rewrite(t, ws_map=ws_map)) != t:
            p.write_text(n, encoding="utf-8")
            out.append(f"書き換えた: {p.relative_to(ws)}")
    led = ws / ".factory" / "ledger.jsonl"
    if led.is_file() and (n := ledger_lines(led, lambda v: rewrite(v, ws_map=ws_map))) != led.read_text(encoding="utf-8"):
        led.write_text(n, encoding="utf-8")
        out.append(f"書き換えた: {led.relative_to(ws)}")
    out += [f"番号を替えた（前の別々の決まりが同じ ID になるため）: {a} → {b}" for a, b in sorted(ws_map.items()) if b != rewrite(a, paths=False)]
    for rel, where in plan(ws)[2]:
        out += [f"要判断: rules/{rel} は、プラグインで {where} に分けた。決まりごとに、足しているプラグインの節のファイルへ移す（ID はそのまま）"] + suggest(ws, rel)
    d, watch, _ = relink_files(ws)  # 当て済みで、いま文がそのファイルにある提案を見張る（移行の前から文のないものは、drift の受け持ち）
    now = {p["id"] for p in in_split(ws) if p["status"] == "適用済み" and p["new"].strip() and (ws / p["file"]).is_file() and p["new"].strip() in (ws / p["file"]).read_text(encoding="utf-8")}
    (d / "relink.json").write_text(json.dumps(sorted(set(watch) | now)), encoding="utf-8")
    out += asks(relinks(ws))
    if off := off_topic(ws):
        mine, plug = [x for x in off if x.startswith("ws-")], [x for x in off if not x.startswith("ws-")]
        if mine:
            out.append(f"要判断: 主題の表にない接頭辞のワークスペースの ID がある（{'・'.join(mine)}）。ledger.py topics から主題を選び、rename-id で付け替える")
        if plug:
            out.append(f"要判断: 角括弧なしで書いた、もうプラグインにない前の ID がある（{'・'.join(plug)}）。ids_20261024.json の prefixes で今の主題を見て、"
                       "その文を直すか、要らなければ消す（ID だと言い切れないので、ここでは替えない）")
    return out


def rename_id(ws, old, new):
    if not re.fullmatch(r"ws-[\w-]+?-\d{3}", old) or not re.fullmatch(r"ws-[\w-]+?-\d{3}", new):
        sys.exit("ワークスペースの決まりの ID（ws-<接頭辞>-<3 桁>）を渡す")
    pat = re.compile(rf"(?<![{B}]){re.escape(old)}(?![{B}])")
    out = []
    for p in [*texts(ws), ws / ".factory" / "ledger.jsonl"]:
        if p.is_file() and pat.search(t := p.read_text(encoding="utf-8")):
            p.write_text(ledger_lines(p, lambda v: pat.sub(new, v)) if p.suffix == ".jsonl" else pat.sub(new, t), encoding="utf-8")
            out.append(f"書き換えた: {p.relative_to(ws)}")
    return out or [f"{old} はどこにもない"]


def selftest():
    assert all(m["ids"].get(n, n) == n for m in MAPS for n in m["ids"].values())  # 今の ID は、前の ID として読んでも替わらない（何度回してもよい）
    IDS = {k: rewrite(k, paths=False) for m in MAPS[:1] for k in m["ids"]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "factory.toml").write_text("")
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("rules/deck-practices/visual.md", "`deck-practices/visual.md` に足す。\n\n- [ws-visual-001] 本文は 16pt（visual-012より優先）。\n")
        put("rules/deck-practices/SKILL.md", "- [ws-deck-practices-001] 代表の 3 枚は 4 枚にする（deck-practices-007 より優先）。\n")
        put("rules/deck-build/checks.py", "import lint  # 前の雛形のとおり\n\ndef slides(p, r):\n    pass\n\ndef doc(doc, r):\n    r.hits[\"段落\"].append(str(len(lint.gdoc_paras(doc))))\n")
        put("rules/doc-build/templates/a/doc.md", "t")
        put("rules/slides-template/SKILL.md", "mine")
        put("rules/deck-template/SKILL.md", "x")
        put("rules/deck-review/SKILL.md", "- [ws-deck-review-001] 今の形の ID\n")
        put("rules/deck-review/prompt_doc.md", "- [ws-prompt_doc-001] 文書の観点\n")
        put("rules/deck-review/prompt_slides.md", "- [ws-prompt_slides-001] スライドの観点\n")
        put("rules/slides-speaker-notes/ja.md", "- [ws-slides-speaker-notes-ja-001] 間を長く（slides-speaker-notes-ja-002 より優先）。\n")
        put("AGENTS.md", "スキル deck-build の deck-build-005 と、doc-build-010。スキルdeck-templateの手順。")
        put("rules/vids-voice/en.md", "- [ws-speaker-notes-en-001] x\n- [ws-odd-001] y\n")
        put("Customers/acme/memory.md", "- [ws-memory-001] 品番の assets-100 と template-777 は顧客の言葉のまま。[visual-777] は前の決まり\n")
        put(".factory/ledger.jsonl", json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0001", "to": "ws-visual-001", "file": "rules/deck-practices/visual.md", "rule": "visual-012"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0009", "file": "rules/a.md", "old": "", "new": "x", "rule": "sessions-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0001", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-001] 代表の 3 枚は 4 枚にする（deck-practices-007 より優先）。"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "applied", "ref": "P0001", "prev": {}}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0002", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-009] 却下した案"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "rejected", "ref": "P0002", "reason": "要らない"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0003", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-010] まだ当てていない案"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0002", "to": "ws-prompt_doc-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0003", "to": "ws-prompt_slides-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0004", "quote": "deck-build の visual-012 を直して", "to": "visual-012"}, ensure_ascii=False) + "\n")
        assert "visual-012 → slides-visual-012" in changed(ws / "rules" / "deck-practices" / "visual.md", ws_plan(ws)) and "assets-100" not in changed(ws / "Customers" / "acme" / "memory.md", ws_plan(ws))
        assert needs(ws)
        out = apply(ws)
        r = ws / "rules"
        assert (r / "slides-build" / "visual.md").read_text().startswith("`slides-build/visual.md` に足す。") and "[ws-slides-visual-001]" in (r / "slides-build" / "visual.md").read_text()
        assert "slides-visual-012" in (r / "slides-build" / "visual.md").read_text() and (r / "docs-build" / "templates" / "a" / "doc.md").is_file()
        assert (r / "slides-build" / "checks.py").is_file() and (r / "docs-build" / "checks.py").is_file() and not (r / "deck-build").exists() and not (r / "doc-build").exists()
        assert (r / "slides-build" / "checks.py").read_text().startswith("import lint ") and (r / "docs-build" / "checks.py").read_text().startswith("import doc_lint as lint ")
        run = subprocess.run([sys.executable, "-c", "import sys; sys.path[:0] = sys.argv[1:3]; import doc_lint, textlint; r = textlint.Report(); "
                              "doc_lint.workspace_checks('doc', {'body': {'content': []}}, r); print(r.hits['段落'])",
                              str(PLUGIN / "docs-build" / "scripts"), str(PLUGIN / "deck-practices" / "scripts")], cwd=ws, capture_output=True, text=True)
        assert run.returncode == 0 and "['0']" in run.stdout, run.stderr  # 写したドキュメントの点検が、ドキュメントの lint から読めて動く
        assert "[ws-vids-voice-en-001]" in (r / "vids-voice" / "en.md").read_text() and any("主題の表にない接頭辞のワークスペースの ID" in o and "ws-odd" in o for o in out)
        assert not any("主題の表にない" in o and "visual-012" in o for o in out)  # 原文の中の古い ID は、主題の表にない ID として出さない
        assert (r / "vids-voice" / "ja.md").read_text() == "- [ws-vids-voice-ja-001] 間を長く（vids-voice-ja-002 より優先）。\n"
        assert (r / "deck-template" / "SKILL.md").is_file() and any("移していない" in o for o in out)  # 移す先にあるものは上書きしない
        assert (ws / "AGENTS.md").read_text() == f"スキル slides-build の {IDS['deck-build-005']} と、{IDS['doc-build-010']}。スキルslides-templateの手順。"  # 和文が続いても替える
        led = [json.loads(x) for x in (ws / ".factory" / "ledger.jsonl").read_text().splitlines()]
        assert led == [{"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0001", "to": "ws-slides-visual-001", "file": "rules/slides-build/visual.md", "rule": "slides-visual-012"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0009", "file": "rules/a.md", "old": "", "new": "x", "rule": "factory-dreaming-001"},  # 台帳の値がまるごと ID なら、もうない ID も接頭辞で替える
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0001", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": (r / "deck-practices" / "SKILL.md").read_text().strip()},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "applied", "ref": "P0001", "prev": {}},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0002", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-flow-009] 却下した案"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "rejected", "ref": "P0002", "reason": "要らない"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0003", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-flow-010] まだ当てていない案"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0002", "to": "ws-deck-review-002"}, {"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0003", "to": "ws-deck-review-003"},  # ぶつかる番号は替え、定義と台帳で同じ
                       {"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0004", "quote": "deck-build の visual-012 を直して", "to": "slides-visual-012"}]  # ユーザーの言葉の原文は替えない
        assert (r / "deck-review" / "SKILL.md").read_text().startswith("- [ws-deck-review-001]")  # 今の形の ID は動かさない
        assert (r / "deck-review" / "prompt_doc.md").read_text().startswith("- [ws-deck-review-002]") and (r / "deck-review" / "prompt_slides.md").read_text().startswith("- [ws-deck-review-003]")
        assert any(o.startswith("番号を替えた") and "ws-prompt_slides-001 → ws-deck-review-003" in o for o in out)
        mem = (ws / "Customers" / "acme" / "memory.md").read_text()
        assert "assets-100" in mem and "template-777" in mem and "[slides-visual-777]" in mem  # 角括弧のない ID でないものは替えない
        assert not any("P0002" in o for o in out) and [x[0] for x in relinks(ws)] == ["P0003"]  # 却下した提案は見ない。まだ当てていない足す提案は、足す先を決める
        assert any(o.startswith("要判断: 台帳の P0003") and "migrate.py relink P0003" in o for o in out)
        assert decide(ws, "P0003", "rules/slides-build/workflow.md")[0].startswith("決めた: P0003") and relinks(ws) == []
        assert any(o.startswith("要判断: rules/deck-practices/SKILL.md") for o in out) and any(IDS["deck-practices-007"].rsplit("-", 1)[0] in o or "workflow" in o for o in out)
        assert any(o.startswith("控え: ") for o in out) and list((ws / ".factory" / "migrate").glob("*/rules/deck-practices/visual.md"))
        first = next(x for x in sorted((ws / ".factory" / "migrate").iterdir()) if x.is_dir())
        put("rules/deck-build/x.md", "y")
        assert apply(ws)[0] != f"控え: {first}" and (first / "rules" / "deck-practices" / "visual.md").is_file()  # 同じ秒に回しても、前の控えを残す
        (r / "slides-build" / "x.md").unlink()
        (r / "deck-template" / "SKILL.md").unlink()
        moved = (r / "deck-practices" / "SKILL.md").read_text()  # 分け直しで、決まりを workflow.md への上書きに移したとする
        put("rules/slides-build/workflow.md", moved)
        (r / "deck-practices" / "SKILL.md").write_text("")
        assert any(x.startswith("台帳の P0001") for x in needs(ws)) and [(i, b) for i, _, b, _ in relinks(ws)] == [("P0001", "rules/slides-build/workflow.md")]
        assert apply(ws) == ["台帳を合わせた: P0001 の変更先 rules/deck-practices/SKILL.md → rules/slides-build/workflow.md"]
        assert next(json.loads(x) for x in (ws / ".factory" / "ledger.jsonl").read_text().splitlines() if '"P0001"' in x)["file"] == "rules/slides-build/workflow.md"
        put("rules/slides-build/workflow.md", "")  # 決まりを分けた先にまたがって書き直し、どこにも元の文がない
        put(".factory/ledger.jsonl", (ws / ".factory" / "ledger.jsonl").read_text().replace("rules/slides-build/workflow.md", "rules/deck-practices/SKILL.md"))
        assert apply(ws)[0].startswith("要判断: 台帳の P0001") and "--split" in apply(ws)[0] and needs(ws)  # 当てた文が分かれたら、決めるまで前の版
        try:
            decide(ws, "P0002", "--split")
            raise AssertionError("却下した提案に --split")
        except SystemExit:
            pass
        assert decide(ws, "P0001", "--split")[0].endswith("undo で戻せない）") and needs(ws) == [] and relinks(ws) == []  # 決めたら、もう出さない
        assert relink_files(ws)[2]["P0003"] == {"to": "rules/slides-build/workflow.md", "from": "rules/deck-practices/SKILL.md"}
        put("rules/slides-build/workflow.md", moved)
        assert needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]  # 2 回目は何もしない
        assert rename_id(ws, "ws-slides-visual-001", "ws-slides-pages-001") and "ws-slides-pages-001" in (ws / ".factory" / "ledger.jsonl").read_text()
        assert "[ws-slides-pages-001]" in (r / "slides-build" / "visual.md").read_text()
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    ws = workspace()
    if not ws:
        sys.exit("factory.toml が見つからない。ワークスペースの中で回す")
    if a in ([], ["check"]):
        moves, edit, split, ws_map = plan(ws)
        print("\n".join([f"移す: {s.relative_to(ws)} → {d.relative_to(ws)}" for s, d in moves] + [f"書き換える: {p.relative_to(ws)}{changed(p, ws_map)}" for p in edit]
                        + [f"要判断（apply のあと）: rules/{k} は {v} に分けた" for k, v in split if moves or edit]
                        + [f"台帳を合わせる: {i} の変更先 {a} → {b}" for i, a, b, _ in relinks(ws) if b] + asks(relinks(ws))) or "移すものはない（今の版）")
    elif a == ["apply"]:
        print("\n".join(apply(ws)))
    elif len(a) == 3 and a[0] == "relink":
        print("\n".join(decide(ws, a[1], a[2])))
    elif len(a) == 3 and a[0] == "rename-id":
        print("\n".join(rename_id(ws, a[1], a[2])))
    else:
        sys.exit(__doc__)
