#!/usr/bin/env python3
"""Google Slides のスピーカーノートを、Google Vids の voiceover の台本として取る・確かめる・書く（../SKILL.md）。スライドの本体は触らない。
台本は {"1": "…", "2": "…", …}（ページの番号 → そのページのノート）の JSON。
usage（資料の build/ で）:
  speaker_notes.py pull <URL か ID>              今のノートを台本の形で標準出力に出す。deck.json のページの speakerNotes と違うページを標準エラーに出す（画面でノートが直されている）
  speaker_notes.py lint <台本.json> [--lang ja|en]   台本を確かめる（要修正: 1 シーン 2,500 字を超える。要確認: 空のシーン、確かめていないタグ、続けて置いたタグ、
                                         1 シーンに 2 つ以上の感情のタグ、読み上げる記号、ページの参照、ja では英字。記号と参照は言語ごと〔既定は ja〕）。字数の合計も出す
  speaker_notes.py push <URL か ID> <台本.json>  ノートを台本に書き換え、deck.json のページの speakerNotes も書き換える。資料のフォルダ（build/ の上）の md に
                                         デッキの ID がなければ、何も書かずに止める（別の資料の build/ で回していないか）。初めての push では、今のノートを
                                         notes_before_<日付>.json に控える（控えがあれば控えない。元に戻すときは、控えを push する）。書いたあとに読み直して比べる
  speaker_notes.py --selftest
"""
import datetime, json, re, sys, unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deck-build" / "scripts"))
import gapi, lint
from gapi import SLIDES, batch, file_id, request, run
from slides import DECK_FIELDS, PAGE_KEY, STAMP, deck_font, page_key, revision

MAX = 2500  # Vids の 1 シーンの voiceover の上限
PAUSES = {"short pause", "medium pause", "long pause"}
EMOTIONS = {"determination", "enthusiasm", "curiosity"}
TAG = re.compile(r"\[([^\[\]]*)\]")
# 日本語の文字（かな・漢字）でない字と数字の続き。- . ' _（全角も）でつないだもの（deck-review・GPT-4o・v2.5）も 1 語
W = r"[^\W_ぁ-ヿㇰ-ㇿｦ-ﾟ㐀-䶿一-鿿豈-\uFAFF\U00020000-\U0003FFFF々〆〇〻]"
JOIN = re.compile(r"[-.'’_‐‑－．＇＿]")
WORD = re.compile(rf"{W}+(?:{JOIN.pattern}{W}+)*")
# 言語ごとの (voiceover が読み上げるか読み方の決まらない記号, ページの参照。動画にページ番号はない, カタカナにする英字)。../ja.md・../en.md
LANGS = {"ja": (re.compile(r"[/~#$「」『』【】（）()<>*`|]|https?:"), re.compile(r"\d+\s*ページ|\bp\.?\s?\d+", re.I), WORD),
         "en": (re.compile(r"[/~#*|()<>`]|https?:"), re.compile(r"\b(?:page|slide)s?\s+\d+|\bp\.\s?\d+", re.I), None)}
SCREEN = "前に組んだあとに画面で直されている"


def live(pid):
    """スライドの並び（ノートの枠まで）と、デッキの書体の要るマスター。"""
    return request("GET", f"{SLIDES}/{pid}?fields=slides(objectId,slideProperties(notesPage(notesProperties,pageElements(objectId,shape(text))))),{DECK_FIELDS}")


def notes_of(slides):
    return {str(i): lint.note_text(s).rstrip("\n") for i, s in enumerate(slides, 1)}


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{path}: 読めない（{e}）")


def page_files(deck=Path("deck.json")):
    """deck.json に並んだページのファイル（1 ファイル 1 ページ）を、デッキの順に。子が書いたデッキのファイル（pages_<担当>.json）の中も並べる。
    deck.json がないか、ファイルでないページがあれば None。"""
    if not deck.is_file() or not isinstance(d := read_json(deck), dict):
        return None
    out = []
    for f in d.get("pages", []):
        if not isinstance(f, str):
            return None
        path = deck.parent / f
        o = read_json(path)
        kind = o.get("kind") if isinstance(o, dict) else None
        if kind == "deck":
            if (sub := page_files(path)) is None:
                return None
            out += sub
        elif kind == "page":
            out.append(path)
        else:  # 部品 1 つのファイル（kind component）は、ノートを書く場所がない
            return None
    return out


def mine(pid):
    """今いる build/ が、このデッキの資料のものか。資料のフォルダの md（構成案に URL を書く）にデッキの ID があるかで見る。
    ページのファイル名（p05.json など）はどの資料でもそろうので、pair の印だけでは別の資料のファイルと取り違える。"""
    return any(pid in f.read_text(errors="ignore") for f in Path.cwd().parent.glob("*.md"))


def pair(slides):
    """スライドごとの、ページのファイル（分からなければ None）。スライドの ID に入れたファイル名の印（slides.py の PAGE_KEY）で結ぶ。
    並びの位置で結ぶと、手元で並べ替えたまま組んでいないときに、別のページのファイルに書く。"""
    by = {page_key(f.stem): f for f in page_files() or []}
    return [by.get(m.group(1)) if (m := PAGE_KEY.search(s["objectId"])) else None for s in slides]


def set_note(path, text):
    """ページのファイルの speakerNotes を text にする。手で整えた書き方を崩さないよう、その値だけを書き換える。決まらなければ全体を書き直す。"""
    src = path.read_text()
    o = json.loads(src)
    want = {**o, "speakerNotes": text} if text else {k: v for k, v in o.items() if k != "speakerNotes"}
    if want == o:
        return
    if text:
        for m in re.finditer(r'"speakerNotes":\s*"(?:[^"\\]|\\.)*"', src):  # 部品の文字に同じ並びがあっても、書き換えた結果がページの speakerNotes だけ変えたものかで選ぶ
            new = src[:m.start()] + '"speakerNotes": ' + json.dumps(text, ensure_ascii=False) + src[m.end():]
            if json.loads(new) == want:
                path.write_text(new)
                return
    path.write_text(json.dumps(want, ensure_ascii=False, indent=1) + "\n")


def load(path):
    """台本を読む。ページの番号 → 文字の JSON でなければ止める。末尾の改行は、Slides が読み返すときに落とすので、先に落とす（書いたあとに比べるため）。"""
    script = read_json(path)
    if not (isinstance(script, dict) and all(isinstance(v, str) for v in script.values())):
        sys.exit(f'{path}: 台本は {{"1": "…", "2": "…"}}（ページの番号 → そのページのノートの文字）')
    return {k: v.rstrip("\n") for k, v in script.items()}


def check(script, lang="ja"):
    """(要修正, 要確認) の行の並び。"""
    spoken, page_ref, latin = LANGS[lang]
    fix, ask = [], []
    for k, t in script.items():
        tags = TAG.findall(t)
        body = TAG.sub("", t)
        if not body.strip():  # 要確認にとどめる（前のノートの控えには、ノートのない表紙・扉がある。控えに戻す push を止めない）
            ask.append(f"p{k}: 空のシーン（扉でも話す）")
        if len(t) > MAX:
            fix.append(f"p{k}: {len(t)} 字（Vids の 1 シーンの上限は {MAX} 字）")
        if bad := sorted({x for x in tags if x not in PAUSES | EMOTIONS}):
            ask.append(f"p{k}: Vids で確かめていないタグ {'・'.join(f'[{x}]' for x in bad)}（Vids の [ のメニューで名前を確かめる）")
        if re.search(r"\]\s*\[", t):
            ask.append(f"p{k}: タグを続けて置いている")
        if sum(x in EMOTIONS for x in tags) > 1:
            ask.append(f"p{k}: 感情のタグが 2 つ以上")
        if m := spoken.search(body):
            ask.append(f"p{k}: 読み上げる記号「{m.group()}」（…{body[max(0, m.start() - 10):m.end() + 10]}…）")
        if m := page_ref.search(body):
            ask.append(f"p{k}: ページの参照「{m.group()}」")
        if latin and (words := [w for w in dict.fromkeys(latin.findall(unicodedata.normalize("NFC", body))) if not JOIN.sub("", w).isdigit()]):
            ask.append(f"p{k}: カタカナにする英語 {'・'.join(words)}（画面の表示を指すなら残す）")
    return fix, ask


def cmd_lint(path, lang):
    script = load(path)
    fix, ask = check(script, lang)
    for title, rows in (("要修正", fix), ("要確認", ask)):
        print(f"\n== {title}: {len(rows)} ==")
        if rows:
            print("\n".join(rows))
    n = [len(TAG.sub("", t)) for t in script.values()]
    print(f"\n{len(n)} シーン、タグを除いて {sum(n):,} 字（最長 {max(n, default=0)} 字）")
    sys.exit(1 if fix else 0)


def cmd_pull(pid):
    slides = live(pid)["slides"]
    s = notes_of(slides)
    for i, f in enumerate(pair(slides), 1):
        if f is None:
            print(f"p{i}: ページのファイルが分からない（ページの JSON と比べない）", file=sys.stderr)
        elif read_json(f).get("speakerNotes", "").strip() != s[str(i)].strip():
            print(f"p{i}: {f} の speakerNotes と違う（画面でノートが直されている。今のノートが正しいかを確かめる）", file=sys.stderr)
    print(json.dumps(s, ensure_ascii=False, indent=1))


def note_reqs(slides, script, font):
    """ノートを script に書き換える要求。変わらないページは書かない。"""
    reqs, before = [], notes_of(slides)
    for i, s in enumerate(slides, 1):
        if (t := script[str(i)]) == before[str(i)]:
            continue
        nid = s["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]  # 枠がまだなくても、insertText が作る
        if before[str(i)]:
            reqs.append({"deleteText": {"objectId": nid, "textRange": {"type": "ALL"}}})
        if t:
            reqs += [{"insertText": {"objectId": nid, "insertionIndex": 0, "text": t}},
                     {"updateTextStyle": {"objectId": nid, "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}}]
    return reqs


def cmd_push(pid, path):
    script = load(path)
    p = live(pid)
    slides = p["slides"]
    if set(script) != {str(i) for i in range(1, len(slides) + 1)}:
        sys.exit(f"{path} のページ（{len(script)} 個）が、デッキの 1〜{len(slides)} ページと合わない")
    if not mine(pid):
        sys.exit(f"資料のフォルダ（{Path.cwd().parent}）の md（構成案など）に、このデッキの ID {pid} がない。"
                 "別の資料の build/ で回していないかを確かめる（この資料のデッキなら、構成案に URL を書いてから回す）")
    files = pair(slides)  # Slides に書く前に読む（読めないファイルがあれば、何も書かずに止まる）
    before = notes_of(slides)
    screen = SCREEN in (gapi.guard(pid, revision(pid), STAMP, "", stop=False) or [])
    if not list(Path().glob("notes_before_*.json")):
        bk = Path(f"notes_before_{datetime.date.today():%Y%m%d}.json")
        bk.write_text(json.dumps(before, ensure_ascii=False, indent=1) + "\n")
        print(f"今のノートを {bk} に控えた", file=sys.stderr)
    if reqs := note_reqs(slides, script, deck_font(p)):
        batch(pid, reqs)
    if bad := [k for k, t in notes_of(live(pid)["slides"]).items() if t != script[k]]:
        sys.exit(f"書いたあとのノートが台本と違う: p{', p'.join(bad)}")
    if not screen:  # 自分の書き込みを、次の build が画面での直しと取り違えないように。画面での直しがあったなら残さない（build はそれで止まる）
        gapi.stamp(pid, revision(pid), STAMP)
    for i, f in enumerate(files, 1):
        if f:
            set_note(f, script[str(i)])
    if miss := [i for i, f in enumerate(files, 1) if f is None]:
        print(f"p{', p'.join(map(str, miss))}: ページのファイルが分からない。そのページの speakerNotes（pages.py なら d.note）は手で台本にする", file=sys.stderr)
    print(json.dumps({"presentationId": pid, "slides": len(slides), "changed": [int(k) for k, t in before.items() if t != script[k]],
                      "screen_edits": screen}, ensure_ascii=False))


def selftest():
    import tempfile, os
    fix, ask = check({"1": "[short pause] はじめに。[enthusiasm] ようこそ。", "2": "", "3": "あ" * 2501,
                      "4": "[sigh] 12 ページを見てください。[short pause][medium pause] /path", "5": "[curiosity] なぜ。[determination] だから。"})
    assert fix == ["p3: 2501 字（Vids の 1 シーンの上限は 2500 字）"], fix
    assert [a.split(":")[0] for a in ask] == ["p2"] + ["p4"] * 5 + ["p5"] and "空のシーン" in ask[0] and "[sigh]" in ask[1] and "続けて" in ask[2] and "「/」" in ask[3] and "12 ページ" in ask[4], ask
    assert ask[5] == "p4: カタカナにする英語 path（画面の表示を指すなら残す）", ask  # タグの英字は見ない
    assert check({"1": "Cafe\u0301 と ＧＣＰ と S3、deck-review と Wi-Fi、GPT-4o の v2.5 を Việt で。32 ドル、3.5 倍、２０２６ 年、2026-10-21、２０２６－１０、々、ㇰ〻、my_var、Ｗｉ－Ｆｉ、Wi‐Fi。"})[1] == [
        "p1: カタカナにする英語 Café・ＧＣＰ・S3・deck-review・Wi-Fi・GPT-4o・v2.5・Việt・my_var・Ｗｉ－Ｆｉ・Wi‐Fi（画面の表示を指すなら残す）"]  # 書いたとおりの語を、出てきた順に。数字だけは出さない
    assert check({"1": "Pause the video (or not) on slide 5.", "2": "「引用」を p.5 で。"}, "en")[1] == [
        "p1: 読み上げる記号「(」（…the video (or not) on…）", "p1: ページの参照「slide 5」", "p2: ページの参照「p.5」"]  # 英語は「」を見ず、英語の参照を見る
    assert check({"1": "【ユーザー・2 分】話す。"})[1] == ["p1: 読み上げる記号「【」（…【ユーザー・2 分】話…）"]  # 【】の印も読み上げる
    note = lambda t: {"slideProperties": {"notesPage": {"notesProperties": {"speakerNotesObjectId": "n"},
                                                        "pageElements": [{"objectId": "n", "shape": {"text": {"textElements": [{"paragraphMarker": {}}, {"textRun": {"content": t}}]}}}] if t else []}}}
    slides = [note("前のノート\n"), note(""), note("同じ\n"), note("  \n")]
    assert notes_of(slides) == {"1": "前のノート", "2": "", "3": "同じ", "4": "  "}
    r = note_reqs(slides, {"1": "新しい", "2": "足す", "3": "同じ", "4": ""}, "Noto Sans JP")
    assert [next(iter(x)) for x in r] == ["deleteText", "insertText", "updateTextStyle", "insertText", "updateTextStyle", "deleteText"], r  # 空のページは消さず、同じページは書かない。空白だけのノートも消す
    with tempfile.TemporaryDirectory() as t:
        cwd = os.getcwd()
        Path(t, "build").mkdir()
        os.chdir(Path(t, "build"))  # 資料のフォルダの build/（mine が上の md を見る）
        try:
            src = '{"apiVersion": "slides/v1", "kind": "page",\n "title": "見出し", "speakerNotes": "古い \\"ノート\\"",\n "body": [{"type": "gantt", "rows": [{"head": "a", "note": "補足"}]}]}\n'
            Path("p1.json").write_text(src)
            Path("p2.json").write_text('{"apiVersion": "slides/v1", "kind": "page", "title": "t"}')
            Path("p0.json").write_text('{"apiVersion": "slides/v1", "kind": "page", "type": "cover", "title": "表紙", "kicker": "k"}')
            Path("pages_a.json").write_text('{"apiVersion": "slides/v1", "kind": "deck", "name": "a", "pages": ["p1.json", "p2.json"]}')
            Path("deck.json").write_text('{"apiVersion": "slides/v1", "kind": "deck", "pages": ["p0.json", "pages_a.json"]}')
            assert page_files() == [Path("p0.json"), Path("p1.json"), Path("p2.json")]  # 子のデッキのファイルの中も並べる
            Path("..", "構成案.md").write_text("- Google Slides: https://docs.google.com/presentation/d/1AbC_x/edit\n")
            assert mine("1AbC_x") and not mine("1Other")  # 別の資料の build/ では書かない
            sid = lambda name: f"r1_0001k{page_key(name)}h{'0' * 16}"
            assert pair([{"objectId": sid("p2")}, {"objectId": sid("p0")}, {"objectId": "g1"}]) == [Path("p2.json"), Path("p0.json"), None]  # 並びでなく印で結ぶ
            Path("part.json").write_text('{"apiVersion": "slides/v1", "kind": "component", "type": "text", "text": "t"}')
            Path("deck2.json").write_text('{"apiVersion": "slides/v1", "kind": "deck", "pages": ["p0.json", "part.json"]}')
            assert page_files(Path("deck2.json")) is None  # 部品のファイルには書かない
            Path("deck3.json").write_text('{"apiVersion": "slides/v1", "kind": "deck", "pages": ["nothing.json"]}')
            try:
                page_files(Path("deck3.json"))
                raise AssertionError("読めないページのファイルを通した")
            except SystemExit as e:
                assert "nothing.json: 読めない" in str(e)
            Path("s.json").write_text('{"1": "台本\\n", "2": "b"}')
            assert load("s.json") == {"1": "台本", "2": "b"}  # 末尾の改行は落とす（Slides が読み返すときに落とす）
            set_note(Path("p1.json"), "新しい\n台本")
            assert Path("p1.json").read_text() == src.replace('"古い \\"ノート\\""', '"新しい\\n台本"')  # 書き方は崩さず、gantt の行の note は残す
            set_note(Path("p2.json"), "足す")
            assert json.loads(Path("p2.json").read_text())["speakerNotes"] == "足す"
            set_note(Path("p2.json"), "")
            assert "speakerNotes" not in json.loads(Path("p2.json").read_text())
        finally:
            os.chdir(cwd)
    print("selftest ok")


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        return selftest()
    if len(a) == 2 and a[0] == "pull":
        return cmd_pull(file_id(a[1]))
    if len(a) == 2 and a[0] == "lint":
        return cmd_lint(a[1], "ja")
    if len(a) == 4 and a[0] == "lint" and a[2] == "--lang" and a[3] in LANGS:
        return cmd_lint(a[1], a[3])
    if len(a) == 3 and a[0] == "push":
        return cmd_push(file_id(a[1]), a[2])
    sys.exit(__doc__)


if __name__ == "__main__":
    run(main)
