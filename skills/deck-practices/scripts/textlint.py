#!/usr/bin/env python3
"""スライドとドキュメントで同じ lint の部品: 本文の表記の決まり（HARD・WARN）、色のコントラスト、出典の表の照合、指摘の入れ物（Report）、
ワークスペースの点検（rules/<スキル>/checks.py）、要確認の記録（.factory/lint_runs.jsonl）。スライドは slides-build の lint.py、
ドキュメントは docs-build の doc_lint.py が読む。標準ライブラリだけ。
usage: python3 textlint.py --stats   要確認の残り方（規則ごと。dreaming の 5）
       python3 textlint.py --selftest"""
import hashlib, json, os, re, sys, time, unicodedata
from collections import defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi  # noqa: E402
from brand import FONT, MONO_DEFAULT  # noqa: E402

JA = r"぀-ゟァ-ヺー-ヿ㐀-鿿"  # かなと漢字（中黒「・」と全角の記号は含めない）

HARD = {
    "絵文字": re.compile("[\U0001F300-\U0001FAFF☀-⛿✅✨❌⭐️]"),
    "長いダッシュ": re.compile("[—―](?!$)|(?<!^)[—―]"),  # 「—」だけのセル（該当なし）は数えない
    "置き換え忘れ": re.compile(r"TODO|FIXME|XXX|lorem|ipsum|〇〇|○○|ここに.{0,6}(入|書)|\[insert", re.I),
    "差し替えの仮ページ": re.compile(r"差し替え："),  # 札の残り。人には Drive の URL で渡し、差し替える人はいない（2026-10-07）
}
WARN = {
    "空疎な言い回し": re.compile(r"(を|の)(実現|加速|最適化|効率化|高度化|強化|推進|促進|変革|最大化)(する|します|。|$)"
                          r"|革新的|次世代の|シームレス|ゲームチェンジ|新たな価値|可能性を広げ|解き放|圧倒的|劇的に|飛躍的"),
    "あおり": re.compile(r"乗り遅れ|取り残さ|このままでは|待ったなし|手遅れ"),
    "英語の大文字ラベル": re.compile(r"^(?![0-9A-F]{6}$)[A-Z][A-Z0-9 &/\-]{3,}$"),  # 6 桁の色の値（F9F7F4 など）は数えない
    "和欧間のスペース抜け": re.compile(rf"[{JA}][A-Za-z0-9]|[A-Za-z0-9][{JA}]"),
    "約物の前後のスペース": re.compile(r" [、。，．）」』]|[（「『] "),
    "要確認・TBD": re.compile(r"要確認|TBD"),
    "社外秘の表示": re.compile(r"Internal Only|Internal Use|Confidential|社外秘|社内限り", re.I),
}
NUM = re.compile(r"\d[\d,.]*\s?(%|％|倍|億|万|兆|円|ドル|USD|ms|TB|GB|PB|K\b|M\b)|[$＄]\s?\d")  # 統計らしい数字だけ（「2 時間」「3 社」は数えない）
URL = re.compile(r"https?://\S+")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


NO_LINK = "出典の行にリンクがない"
# [deck-lint-026] ページの数字は出典の表にあるものだけ。足すときは先に表へ足す（../content.md の deck-content-064）。表は refs.py が資料のフォルダから読む
NOT_IN_FACTS = "出典の表にない数字"
HEAD_PERIOD, BULLET_PERIOD = "見出しの句点", "箇条書きの句点の混在"  # content.md の 6。名前は Docs の規則と同じ（Docs は見出しのスタイル、箇条書きのリストごと）
# [deck-lint-023] 見出しは短い名詞句。言い切りは判断を頼むページと数字の結論のページの 2〜3 枚だけ（content.md の 4・6、docs-build/visual.md の 2）
HEAD_POLITE = "見出しが「ください・します」で終わる"
POLITE_END = re.compile(r"(ください|します|しましょう)$")
FONT_NG = f"書体が {FONT} でない"  # スライドはテンプレートの書体（deck_font）と比べる。Google Fonts にない書体は、API が受け付けても黙って別の書体で描かれる（api.md）。英数字だけの MONO（コード）は通す
MONO_NG = f"等幅の {MONO_DEFAULT} に和文"  # 名前は既定の書体のまま（台帳と lint_runs.jsonl が名前で数える）。テーマの mono なら指摘にその名前を出す。MONO に和文の字形はなく、Google が別の書体で描く。和文は FONT にする（slides.py の mono_reqs。visual.md の 2）
HARD_NAMES = set(HARD) | {HEAD_PERIOD, HEAD_POLITE, FONT_NG, MONO_NG}  # スライドとドキュメントで同じ要修正（それぞれの lint が足す）


def load_facts(folder=".."):
    """資料のフォルダ（build/ の親）の出典の表の文字（同じフォルダの refs.py の facts_text）。slides.py lint・docs.py check が build/ で呼び、
    lint_slides・lint_gdoc の facts に渡す。refs.py はパスで読む（build/ に同じ名前のファイルがあっても取り違えない）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("refs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "refs.py"))
    refs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refs)
    return refs.facts_text(folder)


DIGITS = re.compile(r"\d+(?:\.\d+)?")
NUMBER = re.compile(r"(?<![A-Za-z\d.])" + DIGITS.pattern)  # 表の数の読み方。英字の後ろ（v2、H100）と、小数点の後ろ（1.2.3 の 3）は数えない


def not_in_facts(texts, facts):
    """texts の統計らしい数字（NUM。NO_SOURCE と同じもの）のうち、数の字が出典の表の文字 facts（refs.py の facts_text）にないもの。全角と桁区切りはそろえて、数の字だけを比べる。
    丸めた値は、ページの書き方のまま表の「言うこと」に書く（deck-sources-007。表 3.24 倍だけならページの 3.2 倍は出す）。
    ponytail: 単位と意味（15% と 15 社、範囲の下の値、NUM が数えない数）は見ない。それは照合の子の 2 回目（deck-review/prompt_sources.md の "Pages"）が見る"""
    norm = lambda t: re.sub(r"(?<=\d),(?=\d{3})", "", unicodedata.normalize("NFKC", t))
    have, out = set(NUMBER.findall(norm(facts or ""))), []
    for t in texts:
        t, end = norm(URL.sub("", t)), 0
        for m in NUM.finditer(t):
            if m.start() < end:  # 前の数の続き（$12M の 2M）
                continue
            n = DIGITS.match(t, m.start() + re.search(r"\d", m.group()).start())  # NUM の $ の形は 1 字だけを取るので、数の終わりまで読む
            end = n.end()
            if n.group() not in have and (shown := t[m.start():max(m.end(), n.end())].strip()) not in out:
                out.append(shown)
    return out


def facts_hit(where, miss, facts):
    """出典の表にない数字の指摘の 1 行（スライドはページ、ドキュメントは段落の場所）。"""
    return f"{where}: 「" + "」「".join(miss[:4]) + "」" + ("（出典の表がない）" if not facts else "。先に出典の表へ足すか、表の値にする")


class Report:
    """指摘の入れ物。hard は記録（log_run）に残さない要修正の名前、estimate は見積もりから出す指摘の名前（スライドの lint.py と docs-build の doc_lint.py が足す）。"""
    hard, estimate = HARD_NAMES, frozenset()

    def __init__(self):
        self.hits = defaultdict(list)
        self.extra_hard = set()  # ワークスペースの点検（checks.py の HARD）の要修正の名前（workspace_checks が足す）
        self.where = lambda hit: ""  # 指摘の後ろに付ける、作ったものの中の場所（slides.py lint が JSON のページの部品の場所を引く）

    def scan(self, where, text, rules):
        text = URL.sub("", text).strip()
        for name, rx in rules.items():
            m = rx.search(text)
            if m:
                self.hits[name].append(f"{where}: 「{text[max(0, m.start() - 12):m.end() + 12].strip()}」")

    def show(self, names, title):
        n, est = sum(len(self.hits[k]) for k in names), sum(len(self.hits[k]) for k in names if k in self.estimate)
        print(f"\n== {title}: {n}" + (f"（うち見積もり {est}。画像で確定する）" if est else "") + " ==")
        for k in names:
            for line in self.hits[k][:6]:
                print(f"[{k}] {line}" + self.where(line) + ("（見積もり）" if k in self.estimate else ""))
            if len(self.hits[k]) > 6:
                print(f"[{k}] ほか {len(self.hits[k]) - 6} 件")
        return n


CHECKS = {"slides": "slides-build", "doc": "docs-build"}  # 点検の関数の名前 → ワークスペースの rules/<スキル>/checks.py


def workspace_checks(kind, data, r):
    """ワークスペースの点検。スライドは rules/slides-build/checks.py の slides(p, r)、ドキュメントは rules/docs-build/checks.py の doc(doc, r) を呼ぶ
    （修正の指示から育てる、そのワークスペースだけの点検。deck-practices/rules.md の「Rule layers」）。足された指摘のうち、checks.py の HARD にある名前は要修正、ほかは要確認。"""
    import importlib.util
    try:
        path = gapi.factory_path().parent / "rules" / CHECKS[kind] / "checks.py"
    except SystemExit:  # factory.toml がない
        return 0
    if not path.is_file():
        return 0
    spec = importlib.util.spec_from_file_location("workspace_checks", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not (fn := getattr(mod, kind, None)):
        return 0
    before = {k for k, v in r.hits.items() if v}
    fn(data, r)
    new = [k for k, v in r.hits.items() if v and k not in before]
    hard = [k for k in new if k in getattr(mod, "HARD", ())]
    r.extra_hard |= set(hard)
    n = r.show(hard, f"要修正（ワークスペースの点検 {path}）")
    r.show([k for k in new if k not in hard], "要確認（ワークスペースの点検）")
    return n


def log_path():
    """要確認の記録。ワークスペース（factory.toml のあるフォルダ）の .factory/ に置く（プラグインのフォルダは入れ直すと消える）。
    ponytail: 足すだけで消さない（1 回 1 行）。重くなったら古い行を落とす"""
    return str(gapi.factory_path().parent / ".factory" / "lint_runs.jsonl")


def log_run(r, deck, path=None):
    """要確認を 1 行で残す（--stats が、組み直しても残った指摘を規則ごとに数える。dreaming の 5）。要修正（r.hard と点検の HARD）は残さない。
    資料の文は残さず、場所（p3・段落 12）を除いた指摘のハッシュだけにする（ページが増えても同じ指摘と分かる）。"""
    warn = {k: sorted({hashlib.sha1(re.sub(r"^(p\d+|段落 \d+)", "", h).encode()).hexdigest()[:8] for h in v})
            for k, v in r.hits.items() if v and k not in r.hard}
    if os.environ.get("FACTORY_VERIFY"):  # factory-kaizen の検証で組んだ仮の資料は数えない
        return
    path = path or log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deck": deck, "warn": warn}, ensure_ascii=False) + "\n")


def stats(path=None):
    """規則ごとに、出た指摘の数と、その資料の最後の確認まで残った数。残ったものが、残す理由のある指摘か外れかは、ここからは分からない。"""
    runs, path = defaultdict(list), path or log_path()
    for line in open(path, encoding="utf-8") if os.path.exists(path) else []:
        d = json.loads(line)
        runs[d["deck"]].append(d["warn"])
    rows = defaultdict(lambda: [set(), 0, 0])  # 資料、出た、残った
    for deck, ws in runs.items():
        for k in {k for w in ws for k in w}:
            seen = {h for w in ws for h in w.get(k, [])}
            rows[k][0].add(deck)
            rows[k][1] += len(seen)
            rows[k][2] += len(seen & set(ws[-1].get(k, [])))
    out = sorted(((k, len(a), b, c) for k, (a, b, c) in rows.items()), key=lambda x: (-x[3] / x[2], -x[2]))
    print(f"確認 {sum(map(len, runs.values()))} 回・資料 {len(runs)} 本\n規則\t資料\t出た\t残った（最後の確認まで）")
    for x in out:
        print("\t".join(map(str, x)))
    return out


def selftest():
    import contextlib, io, tempfile
    from pathlib import Path
    assert abs(contrast("FFFFFF", "000000") - 21) < 0.01
    assert abs(contrast("7D8E95", "F5F7F8") - 3.16) < 0.02
    assert WARN["和欧間のスペース抜け"].search("2026年") and not WARN["和欧間のスペース抜け"].search("2026 年")
    assert WARN["空疎な言い回し"].search("業務効率化を実現する") and not WARN["空疎な言い回し"].search("実現の条件")
    assert HARD["絵文字"].search("完了 ✅") and not HARD["絵文字"].search("○ × △")
    assert HARD["長いダッシュ"].search("— 売っていない") and not HARD["長いダッシュ"].search("—")
    assert not WARN["和欧間のスペース抜け"].search("Apps・Lakebase")
    assert WARN["英語の大文字ラベル"].search("KEY POINTS") and not WARN["英語の大文字ラベル"].search("F9F7F4")  # 色の値はラベルでない
    assert HARD["差し替えの仮ページ"].search("差し替え：紹介資料 p.10") and "差し替えの仮ページ" not in WARN
    # 記録と集計: ページがずれても同じ指摘は同じもの。最後の確認で消えたものは残ったに数えない。要修正は記録しない
    with tempfile.TemporaryDirectory() as tmp:
        log, a, b = os.path.join(tmp, "runs.jsonl"), Report(), Report()
        a.hits["あおり"] += ["p3: 「このままでは」", "p5: 「乗り遅れ」"]
        a.hits["絵文字"] += ["p2: 「✅」"]
        b.hits["あおり"] += ["p4: 「このままでは」"]
        log_run(a, "d1", log), log_run(b, "d1", log), log_run(b, "d2", log)
        with contextlib.redirect_stdout(io.StringIO()):
            assert stats(log) == [("あおり", 2, 3, 2)]
    with tempfile.TemporaryDirectory() as tmp:  # load_facts はプラグインの refs.py をパスで読む
        Path(tmp, "構成案.md").write_text("## 出典の表\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n| F1 | 40% | 数字 | S1 | 済 |\n")
        assert load_facts(tmp) == "40%" and load_facts(os.path.join(tmp, "nothing")) is None  # 資料のフォルダの出典の表を読み、構成案も台帳もなければ None
    assert not_in_facts(["売上は 1,200 億円", "３．２倍", "12%"], "1200 億円、3.2 倍") == ["12%"]  # 桁区切り・全角はそろえ、表にない値だけを出す
    # ワークスペースの点検: HARD の名前だけ要修正になる。スライドとドキュメントは、それぞれのスキルの checks.py
    with tempfile.TemporaryDirectory() as ws, contextlib.chdir(ws), contextlib.redirect_stdout(io.StringIO()):
        Path(ws, "factory.toml").write_text("")
        Path(ws, "rules", "slides-build").mkdir(parents=True)
        Path(ws, "rules", "slides-build", "checks.py").write_text(
            'HARD = {"禁止の語"}\ndef slides(p, r):\n    r.hits["禁止の語"].append("p1")\n    r.hits["気になる語"].append("p2")\n')
        gapi.find_factory.cache_clear()
        r = Report()
        assert workspace_checks("slides", {}, r) == 1 and r.hits["気になる語"] and workspace_checks("doc", {}, Report()) == 0
        Path(ws, "rules", "docs-build").mkdir()
        Path(ws, "rules", "docs-build", "checks.py").write_text('def doc(doc, r):\n    r.hits["文書の語"].append("段落 1")\n')
        assert workspace_checks("doc", {}, r := Report()) == 0 and r.hits["文書の語"]  # HARD がなければ要確認
    gapi.find_factory.cache_clear()
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if a == ["--stats"]:
        stats()
        sys.exit(0)
    sys.exit(__doc__)
