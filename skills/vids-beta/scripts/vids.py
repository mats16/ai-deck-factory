# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets", "pillow"]
# ///
"""Google Slides から Google Vids を作る・更新する（../SKILL.md、呼び出しの一覧は ../internal_api.md）。
Slides のページをすべてシーンにし、ページごとのスピーカーノートを Conversational voice（既定は Elio）か AI avatar で読ませる。
空の Vids・MP4・元の Slides の控えは公式の Drive API、ノートは Slides API。中身は内部 API で書く。内部 API は、対象の Google アカウントに
ログイン済みの Chrome（--remote-debugging-port で起動したもの）のタブの中で vids_client.js が呼ぶ。Cookie と token はそのタブの外に出さない。

usage（ワークスペースの下で）:
  uv run vids.py create <Slides の URL か ID> [--name 名前] [--voice Elio | --avatar Oliver --layout <avatar_layout.json>] [--no-music]
      Slides と同じフォルダに Vids を作る。作ったあと読み直して、全シーンの音声（avatar）が台本と合っているかを確かめる。
      元の Slides の ID と声と avatar は、Vids の appProperties に残す（update が読む）。同じ Slides から前に作った Vids は、元の Slides の控えを外す
      （ページを足した・消した・並べ替えた・見た目を直したあとは、組み直さずに create で作り直す。前の Vids は消さずに残る）
  uv run vids.py layout <Slides の URL か ID> --pages 1,5|all [--out build/vids_avatar] [--reset]
      --pages のページに avatar を置く隅と大きさを、Google が描いたページの画像の空きから決め（表紙は大きいものから試す。ほかのページは音声だけ）、
      <out>/avatar_layout.json と、円を描いた一覧の画像 <out>/avatar_sheet*.png を作る。JSON があれば、その置き方のまま描き直す（--reset で決め直す）
  uv run vids.py update <Vids か元の Slides の URL か ID> [--voice 名前 | --avatar 名前|none] [--layout <avatar_layout.json>]
      ノートの変わったシーンだけ、台本と音声（avatar）を差し替える（声・avatar を替えると全シーン。--layout の置き方と違う avatar は動かす）。
      ページには追従しない（作ったときからページが変わっていれば止まる。ノートは比べない）
  uv run vids.py check <Vids か元の Slides の URL か ID> [<Slides の URL か ID>]    シーンの数と、各シーンの音声（avatar）が台本と合っているか
  uv run vids.py voices                                                 選べる声（Conversational voices の 30 種）
  uv run vids.py avatars                                                選べる AI avatar（Conversational voices で話す 30 体）
  uv run vids.py download <Vids の URL か ID> <出力.mp4>               公式の Drive API（files.download）で MP4 にする
  uv run vids.py --selftest
create・update・check は --browser <URL> を取る。--browser、環境変数 VIDS_BROWSER、factory.toml の [vids] browser の順で、なければ http://127.0.0.1:9222。
"""
import asyncio, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "vids_client.js"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[1] / "deck-build" / "scripts"))
import gapi, lint  # noqa: E402
from gapi import DRIVE, SLIDES, file_id, request  # noqa: E402

MAX = 2500  # Vids の 1 シーンの台本の上限（字。slides-speaker-notes の lint と同じ）
SLIDES_KEY, VOICE_KEY, AVATAR_KEY = "vidsSlides", "vidsVoice", "vidsAvatar"  # Vids の appProperties: 元の Slides の ID、声の表示名、avatar の表示名（音声だけならない）
PAGES_KEY = "vidsPages"  # Vids の appProperties: 作ったときのページの印（look）。update は、今のページの印と違えば止まる
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
# AI avatar のうち Conversational voices で話すもの（画面の Avatars の一覧で Classic と付かないもの）。表示名 → (avatar の ID, 声の表示名, 画面の分け方)。
# 声は avatar ごとに決まっている。編集画面の JS の avatar の表（actor24〜53。actor01〜23 は Classic）から写した（2026-10-22）。作って確かめたのは Oliver だけ
AVATARS = {
    "Sofia": ("actor24", "Lani", "Realistic"), "Jack": ("actor25", "Paz", "Realistic"), "Charlie": ("actor26", "Fira", "Realistic"),
    "Morgan": ("actor27", "Lora", "Realistic"), "Finley": ("actor28", "Nyla", "Realistic"), "Avery": ("actor29", "Peli", "3D Cartoon"),
    "Benjamin": ("actor30", "Zeno", "3D Cartoon"), "Scarlett": ("actor31", "Kaci", "3D Cartoon"), "Reynold": ("actor32", "Nyx", "3D Cartoon"),
    "Harper": ("actor33", "Tova", "3D Cartoon"), "Elijah": ("actor34", "Holt", "2D Cartoon"), "Eleanor": ("actor35", "Tyra", "Realistic"),
    "Amelia": ("actor36", "Lito", "2D Cartoon"), "Joseph": ("actor37", "Jett", "2D Cartoon"), "Sebastian": ("actor38", "Neo", "Realistic"),
    "Lux": ("actor39", "Iro", "2D Cartoon"), "Smith": ("actor40", "Knox", "2D Cartoon"), "River": ("actor41", "Vira", "2D Cartoon"),
    "Theodore": ("actor42", "Baya", "3D Cartoon"), "Winoa": ("actor43", "Sani", "3D Cartoon"), "Evelyn": ("actor44", "Saro", "3D Cartoon"),
    "Martin": ("actor45", "Dori", "2D Cartoon"), "Levi": ("actor46", "Jacy", "Realistic"), "Henry": ("actor47", "Umi", "3D Cartoon"),
    "William": ("actor48", "Cale", "Realistic"), "Liam": ("actor49", "Kero", "2D Cartoon"), "Oliver": ("actor50", "Elio", "Realistic"),
    "Mia": ("actor51", "Fola", "Realistic"), "Justice": ("actor52", "Orla", "Realistic"), "Jamal": ("actor53", "Yori", "Realistic"),
}


def voice_of(name):
    """表示名か Gemini の名前（大文字小文字は問わない）→ 表示名。"""
    for label, (gemini, _) in VOICES.items():
        if name.lower() in (label.lower(), gemini.lower()):
            return label
    sys.exit(f"声 {name} がない。選べる声: uv run vids.py voices")


def avatar_of(name):
    """表示名か avatar の ID か、声の表示名・Gemini の名前（その声で話す avatar。大文字小文字は問わない）→ 表示名。"""
    for label, (aid, voice, _) in AVATARS.items():
        if name.lower() in (label.lower(), aid, voice.lower(), VOICES[voice][0].lower()):
            return label
    sys.exit(f"avatar {name} がない。選べる avatar: uv run vids.py avatars（Classic の avatar は使えない）")


def avatar_arg(label):
    """createFromSlides・updateScenes に渡す avatar（ID と、TTS に渡す声の名前。画面は小文字で送る）。"""
    aid, voice, _ = AVATARS[label]
    return {"id": aid, "voice": VOICES[voice][0].lower()}


# avatar の置き方。Vids のページは 960 × 540 に 381 を掛けた EMU（365760 × 205740）。avatar は丸く切り抜き、直径はページの高さに対する割合で持つ
PAGE_W, PAGE_H = 365760, 205740
MARGIN = 0.04  # 隅からの間（ページの高さに対する割合）
SIZES = (0.36, 0.30, 0.24, 0.18)  # 試す直径（大きい順）。どれも空かなければ、いちばん小さいものを右下に置き「要確認」にする
TITLE_SIZES = (0.6, 0.5, 0.42) + SIZES  # 表紙（1 ページ目）は大きく見せたいことがあるので、大きいものから試す
CORNERS = ("br", "bl", "tr", "tl")  # 右下・左下・右上・左上
BR_BONUS = 0.07  # 右下を、直径がこれだけ大きいものと同じに扱う（シーンごとに隅が変わりすぎないように）
INK, INK_FRAC = 8, 0.003  # 地の色から INK より離れた画素が、円の四角（と周りの間）の INK_FRAC 以上あれば空いていない（淡色のパネルと地の差は 10 ほど。box_pad.py の EDGE と同じ考え）


def place_tf(corner, size):
    """隅と直径 → avatar の要素の変換 [倍率, 0, 0, 倍率, x, y]（vids_client.js の avatarElement。要素の基準は 120000 EMU 四方）。"""
    d, m = size * PAGE_H, MARGIN * PAGE_H
    x = PAGE_W - m - d if corner[1] == "r" else m
    y = PAGE_H - m - d if corner[0] == "b" else m
    return [round(d / 120000, 6), 0, 0, round(d / 120000, 6), round(x), round(y)]


def box_px(corner, size, w, h, pad=0.0):
    """隅と直径 → 画像（w × h）の上の四角 (左, 上, 右, 下)。pad は周りに足す間（ページの高さに対する割合）。"""
    *_, x, y = place_tf(corner, size)
    k = w / PAGE_W
    d, p = size * PAGE_H * k, pad * PAGE_H * k
    return (max(0, round(x * k - p)), max(0, round(y * k - p)), min(w, round(x * k + d + p)), min(h, round(y * k + d + p)))


def is_free(img, box, bg):
    """画像の四角に、地の色 bg と違う画素（文字・図・写真）がほとんどないか。"""
    px = list(img.crop(box).convert("RGB").get_flattened_data())
    return sum(max(abs(a - b) for a, b in zip(c, bg)) > INK for c in px) < INK_FRAC * len(px)


def auto_place(img, sizes=SIZES):
    """1 ページの画像から、avatar を置く隅と直径と、要確認か。空いている隅と直径のうち、直径（右下は BR_BONUS を足す）のいちばん大きいもの。
    ponytail: 地の色はページ全体でいちばん多い色。全面の写真やグラデーションの地は空いていないと見る（要確認になり、一覧の画像で見て決める）"""
    w, h = img.size
    small = list(img.convert("RGB").resize((160, 90)).get_flattened_data())
    bg = max(set(small), key=small.count)
    free = [(c, s) for s in sizes for c in CORNERS if is_free(img, box_px(c, s, w, h, pad=0.02), bg)]
    if not free:
        return "br", sizes[-1], True
    c, s = max(free, key=lambda cs: cs[1] + (BR_BONUS if cs[0] == "br" else 0))
    return c, s, False


def draw_place(img, row):
    """一覧の画像のページに、avatar の円を描く（置かないページはそのまま）。"""
    from PIL import ImageDraw
    import sheet
    if row["corner"] != "none":
        ImageDraw.Draw(img).ellipse(box_px(row["corner"], float(row["size"]), *img.size), outline=sheet.LABEL, width=8)
    return img


def layout_row(old, i, pid, want, place):
    """1 ページの置き方。want（avatar にするページの番号の集合）がなければ JSON の行のまま（JSON にないページは none）。
    want にないページは none。want にあって JSON で none か JSON にないページは place()（隅・直径・要確認）で決める。"""
    row = (old or {"corner": "none", "size": SIZES[0], "check": False}) | {"page": i + 1, "pageId": pid}
    if want is None:
        return row
    if i + 1 not in want:
        return row | {"corner": "none", "check": False}
    if row["corner"] == "none":
        c, s, check = place()
        row |= {"corner": c, "size": s, "check": check}
    return row


def layout(args):
    """ページの画像を取り、avatar の置き方の JSON と、円を描いた一覧の画像を作る。avatar を置くのは --pages のページだけ（ほかは none で音声だけ）。
    JSON があれば置き方はそのまま（--pages で avatar にするページを替える。--reset で全部決め直す）。"""
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    import sheet
    slides_id, out = file_id(args.slides), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = [s["pageId"] for s in scenes_of(slides_id)]
    js = out / "avatar_layout.json"
    old = {} if args.reset or not js.exists() else {p["pageId"]: p for p in json.loads(js.read_text())["pages"]}
    if not old and not args.pages:
        sys.exit("--pages で avatar にするページを渡す（例: --pages 1,5、全ページなら all。avatar は 1 シーンごとに月の回数を使う）")
    want = None  # avatar にするページ（None なら JSON のまま）
    if args.pages == "all":
        want = set(range(1, len(pages) + 1))
    elif args.pages:
        want = {int(x) for x in args.pages.split(",") if x.strip().isdigit()}
        if len(want) != len(args.pages.split(",")) or not want <= set(range(1, len(pages) + 1)):
            sys.exit(f"--pages は 1〜{len(pages)} のページの番号をカンマで並べる（例: --pages 1,5）か all: {args.pages}")
    for stale in out.glob("avatar_sheet-*.png"):  # 前のページの多い回の一覧を残さない
        stale.unlink()

    def fetch(i):
        path = out / f"p-{i + 1:02d}.png"
        path.write_bytes(urllib.request.urlopen(gapi.thumbnail(slides_id, pages[i])["contentUrl"]).read())
        return path
    with ThreadPoolExecutor(6) as ex:  # gslides.py の THREADS と同じ
        paths = list(ex.map(fetch, range(len(pages))))
    rows = []
    for i, (pid, path) in enumerate(zip(pages, paths)):
        img = Image.open(path).convert("RGB")
        row = layout_row(old.get(pid), i, pid, want, lambda: auto_place(img, TITLE_SIZES if i == 0 else SIZES))
        rows.append(row)
        draw_place(img, row).save(path)
    js.write_text(json.dumps({"slides": slides_id, "pages": rows}, ensure_ascii=False, indent=1) + "\n")
    for n, k in enumerate(range(0, len(paths), 16), 1):  # deck-review の一覧と同じ 4 列 × 400 px、16 枚ずつ
        sheet.sheet([str(x) for x in paths[k:k + 16]], cols=4, width=400).save(out / f"avatar_sheet-{n}.png")
        print(out / f"avatar_sheet-{n}.png")
    print(f"{js}: {len(rows)} ページ、avatar {[r['page'] for r in rows if r['corner'] != 'none'] or 'なし'}、"
          f"要確認（空いた隅がなく、右下に小さく置いた） {[r['page'] for r in rows if r.get('check')] or 'なし'}")


def places_of(path, scenes):
    """avatar_layout.json → シーンごとの変換（corner が none のページは None）。ページが Slides と合わなければ止める。"""
    pages = json.loads(Path(path).read_text())["pages"]
    if [p["pageId"] for p in pages] != [s["pageId"] for s in scenes]:
        sys.exit(f"{path} のページが Slides と合わない（ページを足した・消した・並べ替えた）。vids.py layout --reset で作り直す")
    bad = [p["page"] for p in pages if p["corner"] not in (*CORNERS, "none") or not 0.05 <= float(p["size"]) <= 0.9]
    if bad:
        sys.exit(f"{path} の corner（br・bl・tr・tl・none）か size（0.05〜0.9）が違うページ: {bad}")
    return [None if p["corner"] == "none" else place_tf(p["corner"], float(p["size"])) for p in pages]


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


def look(slides):
    """ページの見た目の印（ノートを除く）。ID（…ObjectId）と URL（画像の一時 URL など）は外して比べる。deck-build の build は、ノートだけを直しても
    ページを新しい ID で作り直すので、ID の並びでは、ノートの直しとページの直しを見分けられない。"""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if not re.search(r"(?i)(objectids?|url)$", k)}
        return [strip(v) for v in x] if isinstance(x, list) else x
    return hashlib.sha256(json.dumps(strip(slides), sort_keys=True).encode()).hexdigest()[:16]


def look_of(slides_id):
    return look(request("GET", f"{SLIDES}/{slides_id}?fields=slides(pageElements,pageProperties)").get("slides", []))


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


def made_from(slides_id):
    """その Slides から create した Vids（appProperties の vidsSlides）。"""
    q = urllib.parse.quote(f"appProperties has {{ key='{SLIDES_KEY}' and value='{slides_id}' }} and trashed = false")
    return request("GET", f"{DRIVE}/files?q={q}&corpora=allDrives&includeItemsFromAllDrives=true&supportsAllDrives=true&fields=files(id,name)")["files"]


def vids_of(fid):
    """Vids の ID。Slides を渡したら、それから create した Vids を Drive で探す。なければ止める。2 つ以上なら止める。"""
    if request("GET", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=mimeType")["mimeType"] != gapi.GSLIDES:
        return fid
    found = made_from(fid)
    if not found:
        sys.exit("この Slides から作った Vids はない（動画は、頼まれたときだけ vids.py create で作る）")
    if len(found) > 1:
        sys.exit(f"この Slides から作った Vids が {len(found)} 個ある（{'、'.join(f['name'] + ' ' + f['id'] for f in found)}）。Vids の URL を渡す")
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


def build_call(vid, slides_id, scenes, label, music, avatar=None, places=None):
    """createFromSlides の呼び出し。前からあるシーン（空の Vids の空シーン）は、組んだあとに消える。
    avatar（表示名）があれば、places（シーンごとの変換、None はそのシーンだけ音声）のシーンを AI avatar が読む。"""
    return "createFromSlides", {"vidsId": vid, "slidesId": slides_id, "voice": VOICES[label][0], "label": label, "music": music,
                                "scenes": [s | {"place": places[i] if places else None} for i, s in enumerate(scenes)],
                                "avatar": avatar_arg(avatar) if avatar else None}


def inspect_call(vid, scenes):
    """inspect の呼び出し（読み直して、シーンの数・台本・音声（avatar）を Slides のノートと比べ、読むのが誰かを返す）。"""
    return "inspect", {"vidsId": vid, "scripts": [s["script"] for s in scenes]}


def readers(label, avatar):
    """シーンを読んでよいもの: 音声の声の表示名と、avatar の ID（avatar のときも、corner が none のシーンは avatar の声の音声）。"""
    return {label} | ({AVATARS[avatar][0]} if avatar else set())


def report(c, scenes, ok_readers):
    """inspect の結果を出す。シーンの数、台本の文字、音声（avatar）のどれかが Slides のノートと合わないか（台本があるのに読むものがないのも）、
    読むのが ok_readers のほかか、avatar と音声が両方あれば止める。"""
    n = len(scenes)
    text = [i for i, ok in enumerate(c["textMatch"], 1) if not ok]
    bad = [i for i, ok in enumerate(c["voiceMatch"], 1) if ok is False or (ok is None and i <= n and scenes[i - 1]["script"])]
    other = [i for i, w in enumerate(c["who"], 1) if w is not None and w not in ok_readers]
    av = {a for a in ok_readers if a.startswith("actor")}
    print(f"確認: シーン {c['scenes']}/{n}、" + (f"avatar {sum(1 for w in c['who'] if w in av)}、" if av else "")
          + f"音声（avatar）が台本と合う {sum(1 for x in c['voiceMatch'] if x)}、音声がない {sum(1 for x in c['voiceMatch'] if x is None)}、"
          f"音声が台本と合わないかない {bad or 'なし'}、台本がノートと違う {text or 'なし'}、声（avatar）が違う {other or 'なし'}、"
          f"avatar と音声が両方ある {c['both'] or 'なし'}")
    if c["scenes"] != n or bad or text or other or c["both"]:
        sys.exit("要修正: シーンの数・台本・音声・声のどれかが合わない（vids.py update で直す）")


def waited(r):
    if r.get("waited"):
        print(f"保存が 550 で断られ、待って送り直した: {len(r['waited'])} 回、{sum(r['waited'])} 秒")
    q = r.get("quota") or {}
    if "left" in q:
        print(f"avatar の今月の残り: {q['left']} 回（上限 {q['limit']}）")


def summary(r, label, avatar=None):
    waited(r)
    total = sum(d or 0 for d in r["durationsMs"]) / 1000
    print(f"シーン {r['scenes']}・音声 {r['voiced']}（{label}）" + (f"・うち avatar {r['avatars']}（{avatar}）" if avatar else "")
          + f"・BGM {'あり' if r['music'] else 'なし'}・音声の合計 {total:.1f} 秒")


def mode_of(args, voice_default, avatar_default=None):
    """--voice と --avatar から (声の表示名, avatar の表示名か None)。avatar の声は avatar ごとに決まっていて、avatar を置かないシーンもその声で読む
    （シーンごとに avatar と音声が交ざっても声がそろう）。--voice も渡したら、その声の avatar でなければ止める。
    avatar_default（update の今の avatar）は、--avatar none でなければ外さない（--voice だけで avatar を黙って消さない。avatar は 1 つずつ月の回数を使う）。"""
    voice = voice_of(args.voice) if args.voice else None
    if args.avatar == "none":
        return voice or voice_default, None
    avatar = avatar_of(args.avatar) if args.avatar else avatar_default
    if not avatar:
        return voice or voice_default, None
    if voice and voice != AVATARS[avatar][1]:
        same = next(a for a, (_, v, _) in AVATARS.items() if v == voice)
        sys.exit(f"avatar {avatar} の声は {AVATARS[avatar][1]}。声 {voice} にそろえるなら --avatar {same}、avatar を外すなら --avatar none（uv run vids.py avatars）")
    return AVATARS[avatar][1], avatar


def create(args):
    slides_id = file_id(args.slides)
    label, avatar = mode_of(args, DEFAULT_VOICE)
    if avatar and not args.layout:
        sys.exit("--avatar には --layout が要る（vids.py layout で置き方を決め、一覧の画像で見てから渡す）")
    if args.layout and not avatar:
        sys.exit("--layout は --avatar と一緒に使う（avatar を選ばないと、置き方は使わない）")
    meta = request("GET", f"{DRIVE}/files/{slides_id}?fields=name,parents&supportsAllDrives=true")
    scenes, pages = scenes_of(slides_id), look_of(slides_id)
    places = places_of(args.layout, scenes) if avatar else None
    vid = request("POST", f"{DRIVE}/files?fields=id&supportsAllDrives=true",
                  {"name": args.name or f"{meta['name']}_動画", "mimeType": "application/vnd.google-apps.vid", "parents": meta.get("parents", [])[:1]})["id"]
    print(f"空の Vids を作った: https://docs.google.com/videos/d/{vid}/edit", flush=True)
    try:
        r, c = in_tab(args.browser, build_call(vid, slides_id, scenes, label, not args.no_music, avatar, places), inspect_call(vid, scenes))
        stamp(vid, {SLIDES_KEY: slides_id, PAGES_KEY: pages, VOICE_KEY: label, AVATAR_KEY: avatar})
        report(c, scenes, readers(label, avatar))
    except BaseException:  # Ctrl-C・接続の切れ・ブラウザーの落ちも
        try:
            gapi.trash(vid)  # 作りかけを残さない（控えのない Vids は update できず、同じフォルダに名前の同じものが溜まる）
            print("作りかけの Vids をゴミ箱に移した", file=sys.stderr)
        except BaseException:  # ゴミ箱に移せなくても、元のエラーを隠さない
            print(f"作りかけの Vids をゴミ箱に移せなかった。手で移す: https://docs.google.com/videos/d/{vid}/edit", file=sys.stderr)
        raise
    summary(r, label, avatar)
    # 新しい Vids だけを update が探すように。組んだあとに探す（組む間に別の create が作ったものも外す）。前の Vids は消さない（共有した URL かもしれない）
    try:
        for f in (f for f in made_from(slides_id) if f["id"] != vid):
            stamp(f["id"], {SLIDES_KEY: None})
            print(f"前の Vids の控えを外した（もう update しない）: {f['name']} https://docs.google.com/videos/d/{f['id']}/edit")
    except BaseException as e:  # 回線の切れ・Ctrl-C も。新しい Vids はできているので、どれを update に渡すかを残す
        sys.exit(f"新しい Vids はできた: https://docs.google.com/videos/d/{vid}/edit 。前の Vids の控えを外し終えなかった（{e!r}）。"
                 "update にはこの Slides でなく新しい Vids の URL を渡す")
    print(f"https://docs.google.com/videos/d/{vid}/edit")


def has_avatar(c):
    """inspect の結果に、avatar の読むシーンがあるか。"""
    return any(w and w.startswith("actor") for w in c["who"])


def sync_avatar(vid, c, avatar):
    """update のあと、Vids の控えの avatar を、Vids に実際に avatar があるかに合わせる（控えだけ avatar のままだと、次の update が
    置き場所を求めて止まる。PR #91 の指摘）。avatar が 1 つもなければ外す。声の控えは触らない（音声はもう新しい声で、途中で止まっても
    次の update が同じ声で残りを仕上げる）。"""
    if avatar and not has_avatar(c):
        stamp(vid, {AVATAR_KEY: None})
        print("Vids に avatar が 1 つもないので、控えを音声だけにした（avatar を足すなら --avatar と --layout を渡す）")


def update(args):
    vid = vids_of(file_id(args.vids))
    p = props_of(vid)
    if SLIDES_KEY not in p:
        sys.exit("この Vids には元の Slides の控えがない（vids.py create で作ったものだけ更新できる。同じ Slides から create で作り直したら、前の Vids の控えは外してある）")
    slides_id, old = p[SLIDES_KEY], (p.get(VOICE_KEY, DEFAULT_VOICE), p.get(AVATAR_KEY))
    if PAGES_KEY in p and look_of(slides_id) != p[PAGES_KEY]:  # 印のない Vids（この印を残す前に作ったもの）は見ない
        sys.exit("要修正: 動画を作ったあと、ページが変わった（足した・消した・並べ替えた・見た目を直した。前の会話での直しも）。"
                 "動画はページに追従しないので、update しない。頼まれたら vids.py create で作り直す")
    label, avatar = mode_of(args, *old)
    scenes = scenes_of(slides_id)
    if avatar and not old[1] and not args.layout:  # 音声だけの Vids には置き場所がない（--layout なしでは声だけ替わって終わる）
        sys.exit("音声だけの Vids に avatar を足すには --layout が要る（vids.py layout --pages … で決め、一覧の画像で見てから渡す）")
    if args.layout and not avatar:
        sys.exit("--layout は avatar の Vids で使う（音声だけの Vids に足すなら --avatar も渡す）")
    places = places_of(args.layout, scenes) if avatar and args.layout else None
    not_open(args.browser, vid)  # 声の控えを書く前に、よくある止まり方を先に見る
    if (label, avatar) != old:  # 書く前に残す。途中で止まっても、次の update が同じ声で残りのシーンを差し替える（シーンの声は音声の名札と avatar の ID で見る）
        stamp(vid, {VOICE_KEY: label, AVATAR_KEY: avatar})
    work = ("updateScenes", {"vidsId": vid, "scripts": [s["script"] for s in scenes], "voice": VOICES[label][0], "label": label,
                             "avatar": avatar_arg(avatar) if avatar else None, "places": places})
    try:
        r, c = in_tab(args.browser, work, inspect_call(vid, scenes))
    except BaseException:
        if avatar:  # 止まっても、控えを Vids の実際に合わせる（読み直せなければそのまま）
            try:
                sync_avatar(vid, in_tab(args.browser, inspect_call(vid, scenes))[0], avatar)
            except BaseException:
                pass
        raise
    sync_avatar(vid, c, avatar)
    if r.get("sceneCount") != len(scenes):
        if (label, avatar) != old:
            stamp(vid, {VOICE_KEY: old[0], AVATAR_KEY: old[1]})  # どのシーンも替えていないので、声の控えを戻す
        sys.exit(f"要修正: Vids のシーンは {r.get('sceneCount')}、Slides のページは {len(scenes)}。動画はページに追従しない（頼まれたら vids.py create で作り直す）")
    waited(r)
    print(f"台本と音声（avatar）を差し替えたシーン: {r['updated'] or 'なし'}（{avatar or label}）" + (f"、avatar を動かしたシーン: {r['moved']}" if r.get("moved") else ""))
    report(c, scenes, readers(label, avatar))
    print(f"https://docs.google.com/videos/d/{vid}/edit")


def check(args):
    vid = vids_of(file_id(args.vids))
    p = props_of(vid)
    slides_id = file_id(args.slides) if args.slides else p.get(SLIDES_KEY) or sys.exit("元の Slides の控えがない。Slides の URL も渡す")
    scenes = scenes_of(slides_id)
    report(in_tab(args.browser, inspect_call(vid, scenes))[0], scenes, readers(p.get(VOICE_KEY, DEFAULT_VOICE), p.get(AVATAR_KEY)))


def voices(_):
    for label, (gemini, desc) in VOICES.items():
        print(f"{label}\t{gemini}\t{desc}" + ("\t（既定）" if label == DEFAULT_VOICE else ""))


def avatars(_):
    for label, (aid, voice, style) in AVATARS.items():
        print(f"{label}\t{aid}\t{style}\t声 {voice}（{VOICES[voice][1]}）")


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
    assert len(AVATARS) == 30 and {v for _, v, _ in AVATARS.values()} == set(VOICES) and {a for a, _, _ in AVATARS.values()} == {f"actor{n}" for n in range(24, 54)}
    assert avatar_of("oliver") == "Oliver" and avatar_of("actor28") == "Finley" and avatar_arg("Oliver") == {"id": "actor50", "voice": "achird"}
    assert avatar_of("Elio") == "Oliver" and avatar_of("achernar") == "Finley"  # 声から、その声で話す avatar
    import types
    assert mode_of(types.SimpleNamespace(voice="Elio", avatar="Oliver"), "Elio") == ("Elio", "Oliver")
    assert mode_of(types.SimpleNamespace(voice=None, avatar="Nyla"), "Elio") == ("Nyla", "Finley")
    try:
        mode_of(types.SimpleNamespace(voice="Nyla", avatar="Oliver"), "Elio")
        raise AssertionError("声の違う avatar を通した")
    except SystemExit as e:
        assert "--avatar Finley" in str(e)
    ns = lambda voice=None, avatar=None: types.SimpleNamespace(voice=voice, avatar=avatar)
    assert mode_of(ns(), "Elio", "Oliver") == ("Elio", "Oliver") and mode_of(ns("Elio"), "Elio", "Oliver") == ("Elio", "Oliver")  # update: avatar のまま
    assert mode_of(ns("Nyla", "none"), "Elio", "Oliver") == ("Nyla", None) and mode_of(ns("Nyla"), "Elio") == ("Nyla", None)
    try:
        mode_of(ns("Nyla"), "Elio", "Oliver")  # avatar の動画で声だけ替えると、avatar が消える
        raise AssertionError("--voice だけで avatar を外した")
    except SystemExit as e:
        assert "--avatar none" in str(e)
    import contextlib, io

    def stops(*a):
        try:
            report(*a)
        except SystemExit:
            return True
    ok = {"scenes": 2, "textMatch": [True, True], "voiceMatch": [True, None], "who": ["Elio", None], "both": []}
    with contextlib.redirect_stdout(io.StringIO()):
        report(ok, [{"script": "a"}, {"script": ""}], readers("Elio", None))  # 台本のないシーンに音声がないのはよい
        assert stops(ok, [{"script": "a"}, {"script": "b"}], readers("Elio", None))  # 台本があるのに音声がない
        assert stops(ok, [{"script": "a"}, {"script": ""}], readers("Nyla", None))  # 声が違う
        av = ok | {"who": ["actor50", None]}
        report(av, [{"script": "a"}, {"script": ""}], readers("Elio", "Oliver"))
        assert stops(av, [{"script": "a"}, {"script": ""}], readers("Elio", None))  # 音声だけのはずが avatar
        assert stops(av | {"both": [1]}, [{"script": "a"}, {"script": ""}], readers("Elio", "Oliver"))  # avatar と音声の両方
    # update のあと控えを実際に合わせる: avatar が残っていれば何もしない。なくなれば avatar だけ外す（声の控えは触らない）
    stamps = []
    global stamp
    real_stamp, stamp = stamp, lambda vid, props: stamps.append(props)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            sync_avatar("V", {"who": ["actor50", "Elio"]}, "Oliver")
            sync_avatar("V", {"who": ["Elio", None]}, "Oliver")  # 最後の avatar のノートを空にした・全ページ none で Nyla から替えた
            sync_avatar("V", {"who": ["Elio"]}, None)
    finally:
        stamp = real_stamp
    assert stamps == [{AVATAR_KEY: None}], stamps  # 声の控え（avatar の声）は残す
    # ページの印: ID と URL が変わっても同じ。文字・位置が変われば、並べ替えても変わる
    pg = lambda t, oid="a": {"objectId": oid, "pageElements": [{"objectId": oid + "_1", "shape": {"text": t}, "image": {"contentUrl": oid}}]}
    assert look([pg("x"), pg("y")]) == look([pg("x", "b"), pg("y", "c")])
    assert look([pg("x"), pg("y")]) != look([pg("y"), pg("x")]) and look([pg("x")]) != look([pg("z")])
    # 置き方: 隅と直径 → 変換。右下の 0.3 は、右と下から高さの 4% 空ける
    assert place_tf("br", 0.3) == [0.51435, 0, 0, 0.51435, 295808, 135788] and place_tf("tl", 0.3)[4:] == [8230, 8230]
    assert box_px("br", 0.3, 1600, 900) == (1294, 594, 1564, 864)
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1600, 900), "white")
    ImageDraw.Draw(img).rectangle((1100, 500, 1600, 900), fill="black")  # 右下に図
    assert auto_place(img) == ("bl", 0.36, False)
    for y in range(0, 900, 30):  # 全面に文字の行
        ImageDraw.Draw(img).rectangle((0, y, 1600, y + 3), fill="black")
    assert auto_place(img) == ("br", 0.18, True)
    assert auto_place(Image.new("RGB", (1600, 900), (12, 34, 56))) == ("br", 0.36, False)  # 濃い地でも、空いていれば右下に大きく
    assert auto_place(Image.new("RGB", (1600, 900), "white"), TITLE_SIZES) == ("br", 0.6, False)  # 表紙は大きいものから
    # layout の行: --pages なしは JSON のまま（none のページに avatar を足さない）、--pages は外したページを none、足したページだけ決める
    auto = lambda: ("tr", 0.24, False)
    placed, none = {"corner": "br", "size": 0.3, "check": False}, {"corner": "none", "size": 0.36, "check": False}
    assert layout_row(none, 1, "b", None, auto)["corner"] == "none" and layout_row(placed, 0, "a", None, auto)["corner"] == "br"
    assert layout_row(None, 2, "c", None, auto)["corner"] == "none"  # JSON にないページ（足したページ）も none
    assert layout_row(placed, 0, "a", {2}, auto)["corner"] == "none" and layout_row(none, 1, "b", {2}, auto)["corner"] == "tr"
    assert layout_row(placed, 0, "a", {1}, auto)["corner"] == "br"  # 置いてあるページは JSON のまま
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
// avatar: 生成の要求（画面の Generate の形、2026-10-22）と、置く要素、モデルの読み方（[3] で置き、[6] で動き、[36]・[0] で消える）
const g = t.avatarBody("V", "KEY", "actor50");
if (g[0][0] !== 124 || g[0][2].length !== 46 || g[0][2][11][0] !== 27 || g[0][2][8][3][0][0][7][2][0][0] !== "V" || g[0][2][45][0] !== 1) throw new Error("avatar ctx");
if (g[0][3][3][0][0][29][0][19][2] !== "KEY" || g[0][3][3][0][0][29][2][0] !== "audio/mpeg" || g[0][4][13][0] !== "actor50" || g[1].join() !== "0,,0") throw new Error("avatar body");
const [el, tm, len] = t.avatarElement("a_av_actor50_s", "a", [0.5, 0, 0, 0.5, 10, 20], "PH", 3166, "m");
if (el[0] !== 3 || el[2] !== 8 || el[5] !== "a" || tm[0] !== 35 || tm[4] !== "a" || len[3][1] !== 3166) throw new Error("avatar element");
const am = [[12, "a", null, 0], [35, "x", 0, [], "a"], el, tm, [6, "a_av_actor50_s", [0.3, 0, 0, 0.3, 1, 2]]];
const as = t.state(am);
if (as.avatar.a?.actor !== "actor50" || as.avatar.a.md5 !== "m" || as.avatar.a.tf[0] !== 0.3 || as.timing.a.join() !== "a_av_actor50_s,x") throw new Error("state avatar");
if (JSON.stringify(t.unplace(as, "a")) !== '[[36,0,"a"],[0,["a_av_actor50_s"]]]' || t.unplace(as, "b").length) throw new Error("unplace");
// 画面で直した形と属性（Mask video の [19]、枠や切り抜きの [5]）を読み、作り直すときに引き継ぐ（動画・長さ・台本の印だけ替える）
const ed = t.state([...am, [19, ["a_av_actor50_s"], 1], [5, ["a_av_actor50_s"], [84], [84, -0.3, 300, 9]]]).avatar.a;
const [re] = t.avatarElement("a_av_actor50_t", "a", ed.tf, "PH2", 5000, "m2", ed);
const rp = new Map(); for (let k = 0; k < re[4].length; k += 2) rp.set(re[4][k], re[4][k + 1]);
if (re[2] !== 1 || rp.get(84) !== -0.3 || rp.get(300) !== 9 || rp.get(58) !== "PH2" || rp.get(176) !== 5000 || rp.get(194) !== "m2" || rp.get(202) !== 2) throw new Error("avatar look");
const gone = t.state([...am, [36, 0, "a"], [0, ["a_av_actor50_s"]]]);
if ("a" in gone.avatar || gone.timing.a.join() !== "x") throw new Error("state avatar removed");
// pool: 1 つ失敗したら、ほかの手は新しく始めない（avatar の回数を捨てる結果に使わない）
// できたものは残して、失敗を out.stopped で返す（呼んだ側が置いてから投げる）
const started = [];
t.pool([1, 2, 3, 4, 5, 6, 7, 8], 3, async (x) => { started.push(x); await new Promise((r) => setTimeout(r, 10)); if (x === 2) throw new Error("x"); return x; })
  .then((o) => {
    if (started.length > 4) throw new Error("pool kept starting after a failure: " + started);
    if (o.stopped?.message !== "x" || o[0] !== 1 || o[2] !== 3 || o[3] !== 4 || 1 in o) throw new Error("pool failure results: " + JSON.stringify(o));
    // first が理由を返したら、最初の 1 つだけ回して返す（呼んだ側が置いてから止める）
    return t.pool([1, 2, 3], 2, async (x) => x, () => "足りない").then((o) => {
      if (o.length !== 1 || o[0] !== 1 || o.stopped?.message !== "足りない") throw new Error("pool stop: " + JSON.stringify(o));
      console.log("ok");
    });
  }).catch((e) => { console.error(e.message); process.exit(1); });
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
    c = sub.add_parser("create"); c.add_argument("slides"); c.add_argument("--name"); c.add_argument("--no-music", action="store_true")
    u = sub.add_parser("update"); u.add_argument("vids")
    k = sub.add_parser("check"); k.add_argument("vids"); k.add_argument("slides", nargs="?")
    lo = sub.add_parser("layout"); lo.add_argument("slides"); lo.add_argument("--out", default="build/vids_avatar"); lo.add_argument("--reset", action="store_true"); lo.add_argument("--pages")
    sub.add_parser("voices"); sub.add_parser("avatars")
    dl = sub.add_parser("download"); dl.add_argument("vids"); dl.add_argument("out")
    for x in (c, u):
        x.add_argument("--voice"); x.add_argument("--avatar"); x.add_argument("--layout")
    for x in (c, u, k):
        x.add_argument("--browser")
    a = p.parse_args()
    {"create": create, "update": update, "check": check, "layout": layout, "voices": voices, "avatars": avatars, "download": download}[a.cmd](a)


if __name__ == "__main__":
    gapi.run(main)
