# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets"]
# ///
"""Google Slides から Google Vids を作る・更新する（../SKILL.md、呼び出しの一覧は ../internal_api.md）。
Slides のページをすべてシーンにし、ページごとのスピーカーノートを Conversational voice（既定は Elio）で読ませる。
空の Vids・MP4・元の Slides の控えは公式の Drive API、ノートは Slides API。中身は内部 API で書く。内部 API は、対象の Google アカウントに
ログイン済みの Chrome（--remote-debugging-port で起動したもの）のタブの中で vids_client.js が呼ぶ。Cookie と token はそのタブの外に出さない。

usage（ワークスペースの下で）:
  uv run vids.py create <Slides の URL か ID> [--name 名前] [--voice Elio] [--no-music]
      Slides と同じフォルダに Vids を作る。作ったあと読み直して、全シーンの音声が台本と合っているかを確かめる。
      元の Slides の ID と声は、Vids の appProperties に残す（update が読む）
  uv run vids.py update <Vids か元の Slides の URL か ID> [--voice 名前] [--rebuild]
      ノートの変わったシーンだけ、台本と音声を差し替える（--voice で声を替えると全シーン）。ページの数が変わったか、ページの見た目を
      直したときは --rebuild（同じ URL のまま、シーンと音声を作り直す）
  uv run vids.py check <Vids か元の Slides の URL か ID> [<Slides の URL か ID>]    シーンの数と、各シーンの音声が台本と合っているか
  uv run vids.py voices                                                 選べる声（Conversational voices の 30 種）
  uv run vids.py download <Vids の URL か ID> <出力.mp4>               公式の Drive API（files.download）で MP4 にする
  uv run vids.py --selftest
create・update・check は --browser <URL> を取る。--browser、環境変数 VIDS_BROWSER、factory.toml の [vids] browser の順で、なければ http://127.0.0.1:9222。
"""
import asyncio, json, os, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "vids_client.js"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[1] / "deck-build" / "scripts"))
import gapi, lint  # noqa: E402
from gapi import DRIVE, SLIDES, file_id, request  # noqa: E402

MAX = 2500  # Vids の 1 シーンの台本の上限（字。slides-speaker-notes の lint と同じ）
SLIDES_KEY, VOICE_KEY = "vidsSlides", "vidsVoice"  # Vids の appProperties: 元の Slides の ID、声の表示名
# Conversational voices（Gemini の TTS）。表示名 → (Gemini の声の名前, 画面の説明)。画面の「Select a voice」の並び（Gemini の名前の ABC 順）と、
# 試聴の音声のファイル名（…/voice_samples/gemini-v4s-tts/1.1/en/<名前>.wav）で対応を取った（2026-10-21）。音声を作って確かめたのは Elio だけ
VOICES = {
    "Nyla": ("Achernar", "soft, higher pitch"), "Elio": ("Achird", "friendly, lower middle pitch"), "Knox": ("Algieba", "smooth, low pitch"),
    "Jett": ("Algenib", "gravelly, low pitch"), "Zeno": ("Alnilam", "firm, lower middle pitch"), "Tova": ("Aoede", "breezy, medium pitch"),
    "Kaci": ("Autonoe", "bright, medium pitch"), "Lani": ("Callirrhoe", "easy-going, medium pitch"), "Holt": ("Charon", "informative, low pitch"),
    "Lora": ("Despina", "smooth, medium pitch"), "Paz": ("Enceladus", "breathy, low pitch"), "Tyra": ("Erinome", "clear, medium pitch"),
    "Kero": ("Fenrir", "excitable, lower middle pitch"), "Saro": ("Gacrux", "mature, medium pitch"), "Nyx": ("Iapetus", "clear, lower middle pitch"),
    "Lito": ("Kore", "firm, medium pitch"), "Peli": ("Laomedeia", "upbeat, higher pitch"), "Fira": ("Leda", "youthful, higher pitch"),
    "Cale": ("Orus", "firm, lower middle pitch"), "Neo": ("Puck", "upbeat, medium pitch"), "Vira": ("Pulcherrima", "forward, medium pitch"),
    "Iro": ("Rasalgethi", "informative, medium pitch"), "Dori": ("Sadachbia", "lively, low pitch"), "Umi": ("Sadaltager", "knowledgeable, medium pitch"),
    "Jacy": ("Schedar", "even, lower middle pitch"), "Fola": ("Sulafat", "warm, medium pitch"), "Baya": ("Umbriel", "easy-going, lower middle pitch"),
    "Orla": ("Vindemiatrix", "gentle, medium pitch"), "Sani": ("Zephyr", "bright, higher pitch"), "Yori": ("Zubenelgenubi", "casual, lower middle pitch"),
}
DEFAULT_VOICE = "Elio"  # 編集画面の既定の声


def voice_of(name):
    """表示名か Gemini の名前（大文字小文字は問わない）→ 表示名。"""
    for label, (gemini, _) in VOICES.items():
        if name.lower() in (label.lower(), gemini.lower()):
            return label
    sys.exit(f"声 {name} がない。選べる声: uv run vids.py voices")


def browser_url(arg=None):
    return arg or os.environ.get("VIDS_BROWSER") or gapi.factory().get("vids", {}).get("browser") or "http://127.0.0.1:9222"


def scenes_of(slides_id):
    """Slides のページの objectId とノート（台本）を、ページの順に。"""
    d = request("GET", f"{SLIDES}/{slides_id}?fields=slides(objectId,slideProperties(notesPage(notesProperties,pageElements(objectId,shape(text)))))")
    out = [{"pageId": s["objectId"], "script": lint.note_text(s).strip()} for s in d.get("slides", [])]  # ページがないと slides のキーがない
    if not out:
        sys.exit("Slides にページがない")
    long = [i for i, s in enumerate(out, 1) if len(s["script"]) > MAX]
    if long:
        sys.exit(f"台本が {MAX} 字を超えるページ: {long}（slides-speaker-notes の lint で直す）")
    return out


def stamp(vid, props):
    """Vids の appProperties に書く。空の Vids を作るときに付けたら最初の保存が 550 になった（2026-10-21、1 回）ので、組んだあとに書く。
    書けないと、組み終えた Vids を update が扱えないので、3 回まで送り直す。"""
    for wait in (5, 30, None):
        try:
            return request("PATCH", f"{DRIVE}/files/{vid}?supportsAllDrives=true&fields=id", {"appProperties": props})
        except gapi.ApiError:
            if wait is None:
                raise
            time.sleep(wait)


def props_of(vid):
    return request("GET", f"{DRIVE}/files/{vid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {})


def vids_of(fid):
    """Vids の ID。Slides を渡したら、それから create した Vids（appProperties の vidsSlides）を Drive で探す。なければ止める。2 つ以上なら止める。"""
    if request("GET", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=mimeType")["mimeType"] != gapi.GSLIDES:
        return fid
    q = urllib.parse.quote(f"appProperties has {{ key='{SLIDES_KEY}' and value='{fid}' }} and trashed = false")
    found = request("GET", f"{DRIVE}/files?q={q}&corpora=allDrives&includeItemsFromAllDrives=true&supportsAllDrives=true&fields=files(id,name)")["files"]
    if len(found) != 1:
        sys.exit(f"この Slides から作った Vids が {len(found)} 個ある（{'、'.join(f['name'] + ' ' + f['id'] for f in found) or 'vids.py create で作る'}）。Vids の URL を渡す")
    print(f"Vids: {found[0]['name']}", flush=True)
    return found[0]["id"]


class Tab:
    """ブラウザーに docs.google.com のタブを 1 つ開き、そこで JS を動かす（CDP）。閉じるまでが 1 回。"""

    def __init__(self, base):
        self.base, self.n = base, 0

    async def __aenter__(self):
        import websockets
        try:
            ver = json.load(urllib.request.urlopen(f"{self.base}/json/version", timeout=5))
        except OSError as e:
            sys.exit(f"{self.base} の Chrome につながらない（{e}）。対象の Google アカウントにログイン済みの Chrome を --remote-debugging-port で起動する（../SKILL.md の \"Setup\"）")
        self.ws = await websockets.connect(ver["webSocketDebuggerUrl"], max_size=None)
        self.target = (await self.send("Target.createTarget", {"url": "https://docs.google.com/videos/u/0/", "background": True}))["targetId"]
        try:  # ここで止まっても、開いたタブを残さない（async with は __aenter__ が止まると __aexit__ を呼ばない）
            self.sid = (await self.send("Target.attachToTarget", {"targetId": self.target, "flatten": True}))["sessionId"]
            loc = None
            for _ in range(60):
                loc = await self.eval("document.readyState === 'complete' && location.host + location.pathname")
                if loc and "google.com" in loc:  # 開いた直後は about:blank
                    break
                await asyncio.sleep(0.5)
            if not str(loc).startswith("docs.google.com/videos"):
                sys.exit(f"Vids を開けない（{loc}）。その Chrome で対象の Google アカウントにログインする")
            await self.eval(JS.read_text())
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *a):
        try:
            await self.send("Target.closeTarget", {"targetId": self.target}, session=False)
        except SystemExit:  # タブを閉じられなくても、元のエラーを隠さない
            pass
        finally:
            await self.ws.close()

    async def send(self, method, params=None, session=True):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session and getattr(self, "sid", None):
            msg["sessionId"] = self.sid
        await self.ws.send(json.dumps(msg))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    sys.exit(f"CDP {method}: {m['error']}")
                return m["result"]

    async def eval(self, expr):
        r = await self.send("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
        if "exceptionDetails" in r:
            e = r["exceptionDetails"]
            sys.exit(f"Vids の内部 API: {e.get('exception', {}).get('description') or e.get('text')}"[:1500])
        return r["result"].get("value")

    async def call(self, fn, arg):
        return await self.eval(f"VidsClient.{fn}({json.dumps(arg, ensure_ascii=False)})")


def open_in(tabs, vid):
    """CDP の /json/list のタブに、この Vids の画面（/videos/d/<id>、/videos/u/0/d/<id>）があるか。"""
    return any("/videos/" in t.get("url", "") and f"/d/{vid}" in t["url"] for t in tabs)


def not_open(browser, vid):
    """同じ Vids を開いているタブがあれば止める（保存が 550 になる。2026-10-21）。"""
    try:
        tabs = json.load(urllib.request.urlopen(f"{browser_url(browser)}/json/list", timeout=5))
    except OSError:
        tabs = []  # つながらないときは Tab が理由を出す
    if open_in(tabs, vid):
        sys.exit("この Vids をブラウザーのタブで開いている。閉じてから回す（開いたままだと保存が 550 で失敗する）")


def in_tab(browser, *calls):
    """1 つのタブで VidsClient の関数を順に呼び、結果の並びを返す。"""
    not_open(browser, calls[0][1]["vidsId"])

    async def go():
        async with Tab(browser_url(browser)) as tab:
            return [await tab.call(fn, arg) for fn, arg in calls]
    return asyncio.run(go())


def build_call(vid, slides_id, scenes, label, music):
    """createFromSlides の呼び出し。前からあるシーン（空の Vids の空シーン、--rebuild の古いシーン）は、組んだあとに消える。"""
    return "createFromSlides", {"vidsId": vid, "slidesId": slides_id, "scenes": scenes, "voice": VOICES[label][0], "label": label, "music": music}


def inspect_call(vid, scenes, label):
    """inspect の呼び出し（読み直して、シーンの数・台本・音声を Slides のノートと、音声の声を label と比べる）。"""
    return "inspect", {"vidsId": vid, "scripts": [s["script"] for s in scenes], "label": label}


def report(c, scenes):
    """inspect の結果を出す。シーンの数、台本の文字、音声のどれかが Slides のノートと合わないか（台本があるのに音声がないのも）、声が違えば止める。"""
    n = len(scenes)
    text = [i for i, ok in enumerate(c["textMatch"], 1) if not ok]
    bad = [i for i, ok in enumerate(c["voiceMatch"], 1) if ok is False or (ok is None and i <= n and scenes[i - 1]["script"])]
    other = [i for i, ok in enumerate(c["labelMatch"], 1) if ok is False]
    print(f"確認: シーン {c['scenes']}/{n}、音声が台本と合う {sum(1 for x in c['voiceMatch'] if x)}、音声がない {sum(1 for x in c['voiceMatch'] if x is None)}、"
          f"音声が台本と合わないかない {bad or 'なし'}、台本がノートと違う {text or 'なし'}、声が違う {other or 'なし'}")
    if c["scenes"] != n or bad or text or other:
        sys.exit("要修正: シーンの数・台本・音声・声のどれかが合わない（vids.py update で直す）")


def waited(r):
    if r.get("waited"):
        print(f"保存が 550 で断られ、待って送り直した: {len(r['waited'])} 回、{sum(r['waited'])} 秒")


def summary(r, label):
    waited(r)
    total = sum(d or 0 for d in r["durationsMs"]) / 1000
    print(f"シーン {r['scenes']}・音声 {r['voiced']}（{label}）・BGM {'あり' if r['music'] else 'なし'}・音声の合計 {total:.1f} 秒")


def create(args):
    slides_id, label = file_id(args.slides), voice_of(args.voice)
    meta = request("GET", f"{DRIVE}/files/{slides_id}?fields=name,parents&supportsAllDrives=true")
    scenes = scenes_of(slides_id)
    vid = request("POST", f"{DRIVE}/files?fields=id&supportsAllDrives=true",
                  {"name": args.name or f"{meta['name']}_動画", "mimeType": "application/vnd.google-apps.vid", "parents": meta.get("parents", [])[:1]})["id"]
    print(f"空の Vids を作った: https://docs.google.com/videos/d/{vid}/edit", flush=True)
    try:
        r, c = in_tab(args.browser, build_call(vid, slides_id, scenes, label, not args.no_music), inspect_call(vid, scenes, label))
        stamp(vid, {SLIDES_KEY: slides_id, VOICE_KEY: label})
        report(c, scenes)
    except BaseException:  # Ctrl-C・接続の切れ・ブラウザーの落ちも
        try:
            gapi.trash(vid)  # 作りかけを残さない（控えのない Vids は update できず、同じフォルダに名前の同じものが溜まる）
            print("作りかけの Vids をゴミ箱に移した", file=sys.stderr)
        except BaseException:  # ゴミ箱に移せなくても、元のエラーを隠さない
            print(f"作りかけの Vids をゴミ箱に移せなかった。手で移す: https://docs.google.com/videos/d/{vid}/edit", file=sys.stderr)
        raise
    summary(r, label)
    print(f"https://docs.google.com/videos/d/{vid}/edit")


def update(args):
    if args.no_music and not args.rebuild:
        sys.exit("--no-music は --rebuild と一緒に使う（--rebuild なしの update は音楽に触らない）")
    vid = vids_of(file_id(args.vids))
    p = props_of(vid)
    if SLIDES_KEY not in p:
        sys.exit("この Vids には元の Slides の控えがない（vids.py create で作ったものだけ更新できる）")
    slides_id, old = p[SLIDES_KEY], p.get(VOICE_KEY, DEFAULT_VOICE)
    label = voice_of(args.voice) if args.voice else old
    scenes = scenes_of(slides_id)
    not_open(args.browser, vid)  # 声の控えを書く前に、よくある止まり方を先に見る
    if label != old:  # 書く前に残す。途中で止まっても、次の update が同じ声で残りのシーンを差し替える（シーンの声は音声の名札で見る）
        stamp(vid, {VOICE_KEY: label})
    if args.rebuild:
        r, c = in_tab(args.browser, build_call(vid, slides_id, scenes, label, not args.no_music), inspect_call(vid, scenes, label))
        summary(r, label)
    else:
        r, c = in_tab(args.browser, ("updateVoiceovers", {"vidsId": vid, "scripts": [s["script"] for s in scenes], "voice": VOICES[label][0],
                                                          "label": label}), inspect_call(vid, scenes, label))
        if r.get("sceneCount") != len(scenes):
            if label != old:
                stamp(vid, {VOICE_KEY: old})  # どのシーンも替えていないので、声の控えを戻す
            sys.exit(f"要修正: Vids のシーンは {r.get('sceneCount')}、Slides のページは {len(scenes)}。ページの数が変わったら --rebuild で組み直す")
        waited(r)
        print(f"台本と音声を差し替えたシーン: {r['updated'] or 'なし'}（{label}）")
    report(c, scenes)
    print(f"https://docs.google.com/videos/d/{vid}/edit")


def check(args):
    vid = vids_of(file_id(args.vids))
    p = props_of(vid)
    slides_id = file_id(args.slides) if args.slides else p.get(SLIDES_KEY) or sys.exit("元の Slides の控えがない。Slides の URL も渡す")
    scenes = scenes_of(slides_id)
    report(in_tab(args.browser, inspect_call(vid, scenes, p.get(VOICE_KEY, DEFAULT_VOICE)))[0], scenes)


def voices(_):
    for label, (gemini, desc) in VOICES.items():
        print(f"{label}\t{gemini}\t{desc}" + ("\t（既定）" if label == DEFAULT_VOICE else ""))


def download(args):
    vid = file_id(args.vids)
    op = request("POST", f"{DRIVE}/files/{vid}/download?mimeType=video/mp4")
    for _ in range(120):  # 長い動画は書き出しに時間がかかる（operation を 5 秒ごとに見る）
        if op.get("done"):
            break
        time.sleep(5)
        op = request("GET", f"{DRIVE}/operations/{op['name'].removeprefix('operations/')}")
    if not op.get("done") or "error" in op:
        sys.exit(f"MP4 にできない: {op.get('error') or 'まだ終わらない'}")
    Path(args.out).write_bytes(request("GET", op["response"]["downloadUri"], binary=True))
    probe = shutil.which("ffprobe") and subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", args.out], capture_output=True, text=True)
    sec = probe.stdout.strip() if probe and probe.returncode == 0 else ""
    print(f"{args.out}: {Path(args.out).stat().st_size:,} bytes" + (f"、{float(sec):.1f} 秒" if sec.replace(".", "", 1).isdigit() else ""))  # N/A なら出さない


def selftest():
    assert len(VOICES) == 30 and len({g for g, _ in VOICES.values()}) == 30
    assert voice_of("elio") == "Elio" and voice_of("Achernar") == "Nyla"
    import contextlib, io
    ok = {"scenes": 2, "textMatch": [True, True], "voiceMatch": [True, None], "labelMatch": [True, None]}
    with contextlib.redirect_stdout(io.StringIO()):
        report(ok, [{"script": "a"}, {"script": ""}])  # 台本のないシーンに音声がないのはよい
        try:
            report(ok, [{"script": "a"}, {"script": "b"}])  # 台本があるのに音声がない
            raise AssertionError("音声のないシーンを通した")
        except SystemExit:
            pass
    assert open_in([{"url": "https://docs.google.com/videos/u/0/d/V1/edit"}], "V1") and open_in([{"url": "https://docs.google.com/videos/d/V1/edit?scene=x"}], "V1")
    assert not open_in([{"url": "https://docs.google.com/videos/d/V2/edit"}, {"url": "https://docs.google.com/presentation/d/V1/edit"}, {}], "V1")
    # JS の部品（MD5 と要求の組み立て）を node で確かめる。通信はしない
    test = r"""
globalThis.window = {}; globalThis.location = {origin: "https://docs.google.com"};
eval(require("fs").readFileSync(process.argv[1], "utf8"));
const t = window.VidsClient._test, crypto = require("crypto");
for (const s of ["", "abc", "[enthusiasm] 日本語の台本です。".repeat(40)])
  if (t.md5b64(s) !== crypto.createHash("md5").update(s).digest("base64")) throw new Error("md5 " + s.slice(0, 10));
const d = t.draftBody("V", "S", [{pageId: "p1", script: "台本"}], "docs-preset-voice-achird");
if (d[0][0] !== 33 || d[0][2][25][0][0][0][0] !== "S" || d[0][2][8][3][0][0][7][2][0][0] !== "V") throw new Error("draft ids");
if (d[0][3][28][1][3][0][0][8][1][0][1][13][2][2] !== "台本" || d[0][4][3][0][8][0] !== "docs-preset-voice-achird") throw new Error("draft scene");
const s = t.ttsBody("台本", "Achird");
if (s[0] !== 254 || s[2][11][0] !== 16 || s[2][19] !== 1 || s[2].length !== 41 || s[3][2] !== "台本" || s[4][25][0] !== "Achird") throw new Error("tts");
// 文書のモデルの読み方: シーンの追加と削除、台本の文字の挿入と削除、音声の追加と削除（画面の保存の形、2026-10-21）
const m = [[12, "p", null, 0], [12, "a", null, 0], [12, "b", null, 0], [13, 0, 0, null, "p"],
  [15, "a:notes_text", null, 0, "では\n"], [15, "a:notes_text", null, 0, "さて、"], [16, "a:notes_text", null, 0, 3],
  [58, "a_vo", [177, 3, 184, "a", 194, "x", 181, "では - Nyla"]], [58, "a_bgm", [177, 2, 184, "a"]], [58, "b_vo", [177, 3, 184, "b", 194, "y"]], [59, "b_vo"]];
const st = t.state(m);
if (st.scenes.join() !== "a,b" || st.script("a") !== "では" || st.script("b") !== "") throw new Error("state scenes/text");
if (st.voice.a?.md5 !== "x" || st.voice.a.label !== "では - Nyla" || "b" in st.voice || Object.keys(st.media).join() !== "a_vo,a_bgm") throw new Error("state media");
console.log("ok");
"""
    if not shutil.which("node"):
        sys.exit("selftest には node が要る（vids_client.js を確かめる）")
    r = subprocess.run(["node", "-e", test, str(JS)], capture_output=True, text=True)
    assert r.stdout.strip() == "ok", r.stderr or r.stdout
    print("selftest ok")


def main():
    import argparse
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("slides"); c.add_argument("--name"); c.add_argument("--voice", default=DEFAULT_VOICE)
    u = sub.add_parser("update"); u.add_argument("vids"); u.add_argument("--voice"); u.add_argument("--rebuild", action="store_true")
    k = sub.add_parser("check"); k.add_argument("vids"); k.add_argument("slides", nargs="?")
    sub.add_parser("voices")
    dl = sub.add_parser("download"); dl.add_argument("vids"); dl.add_argument("out")
    for x in (c, u):
        x.add_argument("--no-music", action="store_true")
    for x in (c, u, k):
        x.add_argument("--browser")
    a = p.parse_args()
    {"create": create, "update": update, "check": check, "voices": voices, "download": download}[a.cmd](a)


if __name__ == "__main__":
    gapi.run(main)
