"""Google Vids の内部 API を呼ぶところ（vids.py の後ろ側。呼び出しの一覧は ../internal_api.md）。
Vids の編集には公開の API がないので、対象の Google アカウントにログイン済みの Chrome（--remote-debugging-port で起動したもの）に
Vids のタブを 1 つ開き、その中で vids_client.js の関数を呼ぶ（CDP）。Cookie と token はそのタブの外に出さない。
vids.py はここの関数（check_closed・build・fill_and_inspect・inspect と、つながりがなくなったときの Lost）だけを使う。
公開の API が出たら、同じ関数を持つ vids_api.py を書き、vids.py の import を差し替える。
usage: python3 vids_internal.py --selftest   （node が要る。vids_client.js の部品を確かめる。通信はしない）"""
import asyncio, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "vids_client.js"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[1] / "deck-practices" / "scripts"))  # gapi.py（factory.toml の [vids] browser）
import gapi  # noqa: E402


def browser_url(arg=None):
    return arg or os.environ.get("VIDS_BROWSER") or gapi.factory().get("vids", {}).get("browser") or "http://127.0.0.1:9222"



class Lost(Exception):
    """vids.py の開いたタブが、途中でほかの URL に移ったか閉じられた（ログインの入れ替え、人の操作、Chrome の整理など）。タブの中の作業は消える。"""


LOST = ("navigated or closed", "Execution context was destroyed", "Cannot find context", "No target with given id", "Session with given id not found", "Target closed")


def lost(error):
    """CDP のエラーが、タブがなくなったことによるものか。"""
    return any(w in str(error) for w in LOST)


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
        except (SystemExit, Lost):  # タブを閉じられなくても、元のエラーを隠さない
            pass
        finally:
            await self.ws.close()

    async def send(self, method, params=None, session=True):
        import websockets
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        mine = session and getattr(self, "sid", None)  # タブにつないだあとの呼び出し（タブを見張る）
        if mine:
            msg["sessionId"] = self.sid
        try:
            await self.ws.send(json.dumps(msg))
            while True:
                try:
                    m = json.loads(await asyncio.wait_for(self.ws.recv(), 30))
                except TimeoutError:  # タブが消えても、待っている応答が来ないことがある（2026-10-23、40 分止まった）。30 秒ごとにタブがあるかを見る
                    if mine and not self.alive():
                        raise Lost(self.where())
                    continue
                if m.get("id") == self.n:
                    break
                ev = m.get("method")
                if mine and (ev == "Target.detachedFromTarget" and m.get("params", {}).get("sessionId") == self.sid or ev == "Inspector.detached" and m.get("sessionId") == self.sid):
                    raise Lost(self.where())
        except websockets.ConnectionClosed as e:
            raise Lost(f"Chrome との接続が切れた（{e}）")
        if "error" in m:
            if lost(m["error"]):
                raise Lost(self.where())
            sys.exit(f"CDP {method}: {m['error']}")
        return m["result"]

    def now(self):
        """開いたタブの、Chrome の一覧の行（閉じられていれば {}、一覧を読めなければ None）。"""
        try:
            tabs = json.load(urllib.request.urlopen(f"{self.base}/json/list", timeout=5))
        except OSError:
            return None
        return next((t for t in tabs if t.get("id") == self.target), {})

    def alive(self):
        """開いたタブが、まだ Vids の画面にあるか（一覧を読めなければ、あるとみなす）。"""
        t = self.now()
        return t is None or "docs.google.com/videos" in t.get("url", "")

    def where(self):
        """タブがどうなったか（落ちた理由を出す。次から原因が分かるように）。"""
        t = self.now()
        return "タブがなくなった（Chrome の一覧を読めない）" if t is None else f"タブが {t['url'][:120]} に移った" if t else "タブが閉じられた"

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


def tabs_of(browser):
    try:
        return json.load(urllib.request.urlopen(f"{browser_url(browser)}/json/list", timeout=5))
    except OSError:
        return []  # つながらないときは Tab が理由を出す


def not_open(browser, vid):
    """同じ Vids を開いているタブがあれば止める（保存が 550 になる。2026-10-21）。"""
    if open_in(tabs_of(browser), vid):
        sys.exit("この Vids をブラウザーのタブで開いている。閉じてから回す（開いたままだと保存が 550 で失敗する）")


def in_tab(browser, *calls):
    """1 つのタブで VidsClient の関数を順に呼び、結果の並びを返す。"""
    not_open(browser, calls[0][1]["vidsId"])

    async def go():
        async with Tab(browser_url(browser)) as tab:
            return [await tab.call(fn, arg) for fn, arg in calls]
    return asyncio.run(go())


def again(browser, *calls, tries=3, wait=600):
    """in_tab を、タブが落ちたら新しいタブで回し直す（tries 回まで）。calls は何度回しても同じ結果になるもの（updateScenes・inspect は、
    Vids の文書を読み直して、まだのシーンだけ作る）。同じ Vids を開いたタブがあれば、閉じられるまで wait 秒待つ（開いたままだと保存が 550 になる）。"""
    vid = calls[0][1]["vidsId"]
    for n in range(1, tries + 1):
        try:
            return in_tab(browser, *calls)
        except Lost as e:
            if n == tries:
                sys.exit(f"{e}。{tries} 回とも途中でタブがなくなった")
            print(f"{e}。新しいタブで続きから回し直す（{n}/{tries - 1}）", file=sys.stderr, flush=True)
        for waited_s in range(0, wait, 5):
            if not open_in(tabs_of(browser), vid):
                break
            if not waited_s:
                print(f"この Vids を開いたタブがある。閉じるまで待つ（{wait // 60} 分まで）: https://docs.google.com/videos/d/{vid}/edit", file=sys.stderr, flush=True)
            time.sleep(5)


def check_closed(browser, vid):
    """同じ Vids を画面で開いていたら止める（開いたままだと保存が 550 で失敗する）。書く前に、よくある止まり方を先に見る。"""
    not_open(browser, vid)


def build(browser, vid, slides_id, scenes, music):
    """空の Vids に、Slides のページ（scenes の pageId）をシーンにして、台本（script）・画像・BGM（music が真なら）を保存する。音声と avatar は作らない。
    前からあるシーン（空の Vids の空シーン）は、組んだあとに消える。1 回だけ回す（途中でつながりがなくなれば Lost。作りかけの Vids の始末は呼んだ側）。
    戻り: {"scenes", "musicMs", "waited", …}"""
    r, = in_tab(browser, ("createFromSlides", {"vidsId": vid, "slidesId": slides_id, "music": music,
                                              "scenes": [{"pageId": s["pageId"], "script": s["script"]} for s in scenes]}))
    return r


def fill_and_inspect(browser, vid, scripts, voice, label, avatar=None, places=None):
    """台本・音声・avatar が scripts と声に合わないシーンだけ作り直し、そのあと読み直す。何度回しても、まだのシーンだけ作るので、
    つながりがなくなれば新しいタブで続きから回し直す（3 回まで）。voice は TTS の声の名前、label は音声に付ける声の表示名、
    avatar は {"id", "voice"}（None なら音声だけ）、places はシーンごとの avatar の変換（None のシーンは音声。places が None なら今の場所のまま）。
    戻り: (更新の結果 {"updated", "moved", "sceneCount", "waited", "quota"}, 読み直した結果。inspect と同じ形)"""
    r, c = again(browser, ("updateScenes", {"vidsId": vid, "scripts": scripts, "voice": voice, "label": label, "avatar": avatar, "places": places}),
                 ("inspect", {"vidsId": vid, "scripts": scripts}))
    return r, c


def inspect(browser, vid, scripts):
    """Vids を読み直し、シーンごとに台本・音声（avatar）が scripts と合うかと、読むのが誰かを返す。
    戻り: {"scenes", "textMatch", "voiceMatch", "who", "both", "ms"}（who は音声の声の表示名か avatar の ID、なければ None）"""
    return in_tab(browser, ("inspect", {"vidsId": vid, "scripts": scripts}))[0]


def selftest():
    import contextlib, io
    # タブが落ちたら新しいタブで回し直す。何度も落ちたら止める。タブの消え方は CDP のエラーの文で見分ける
    assert lost({"code": -32000, "message": "Inspected target navigated or closed"}) and not lost({"message": "Invalid parameters"})
    global in_tab, tabs_of
    real = in_tab, tabs_of
    tries = []

    def flaky(browser, *calls):
        tries.append(calls)
        if len(tries) < 3:
            raise Lost("タブが閉じられた")
        return ["r", "c"]
    in_tab, tabs_of = flaky, lambda browser: []
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            assert again(None, ("updateScenes", {"vidsId": "V"})) == ["r", "c"] and len(tries) == 3
            tries.clear()
            try:
                again(None, ("updateScenes", {"vidsId": "V"}), tries=2)
                raise AssertionError("落ち続けるタブで回し続けた")
            except SystemExit as e:
                assert "2 回とも" in str(e) and len(tries) == 2
    finally:
        in_tab, tabs_of = real
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
// updateScenes: 新しい音声は SAVE_EVERY シーンずつ保存し、途中で止まっても、できたシーンは保存してから止まる。回し直すと残りだけ作る
// （タブが落ちたときの続き。通信は fetch の差し替えで、Vids の文書のモデルに保存を足していく）
async function resumes() {
  const n = t.SAVE_EVERY + 2, model = [], saves = [];
  let tts = 0, failAt = n;
  for (let i = 0; i < n; i++) model.push([12, `s${i}`, null, 0], [15, `s${i}:notes_text`, null, 0, `台本${i}`]);
  globalThis.document = { cookie: "SAPISID=x" };
  const ok = (o) => ({ ok: true, text: async () => (typeof o === "string" ? o : JSON.stringify(o)) });
  globalThis.fetch = async (url, opt = {}) => {
    if (url.endsWith("/edit")) return ok(`"info_params":{"token":"t","ouid":"o"} "espresso_api_key":"k" var modelChunk = ${JSON.stringify({ chunk: model, revision: 1 })}; var modelChunkParseEnd`);
    if (url.includes("/genai/generate")) return ++tts === failAt ? { ok: false, status: 500, text: async () => "x" } : ok([[`K${tts}`, "bard_storage", null, "lookup_temp_data"]]);
    if (url.includes("/insertmedia")) return ok({ [Object.keys(JSON.parse(new URLSearchParams(opt.body).get("insert_media_requests")))[0]]: { ms: "OK", ni: "N", sb: "4844" } });
    if (url.includes("/save")) {
      const cmds = JSON.parse(new URLSearchParams(opt.body).get("bundles"))[0].commands.flatMap((c) => (c[0] === 4 ? c[1] : [c]));
      saves.push(cmds.filter((c) => c[0] === 58).length); model.push(...cmds);
      return ok({ revisionRanges: [[1, 2]] });
    }
    throw new Error("fetch " + url);
  };
  const run = () => window.VidsClient.updateScenes({ vidsId: "V", scripts: Array.from({ length: n }, (_, i) => `台本${i}`) });
  const err = await run().then(() => null, (e) => e);
  if (!err || saves.join() !== `${t.SAVE_EVERY},${n - 1 - t.SAVE_EVERY}`) throw new Error(`updateScenes の途中の保存: ${saves} ${err}`);
  failAt = 0; saves.length = 0;
  const r = await run();
  if (saves.join() !== "1" || r.updated.join() !== String(n)) throw new Error(`updateScenes の続き: ${saves} ${JSON.stringify(r.updated)}`);
}
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
      return resumes();
    }).then(() => console.log("ok"));
  }).catch((e) => { console.error(e.message); process.exit(1); });
"""
    if not shutil.which("node"):
        sys.exit("selftest には node が要る（vids_client.js を確かめる）")
    r = subprocess.run(["node", "-e", test, str(JS)], capture_output=True, text=True)
    assert r.stdout.strip() == "ok", r.stderr or r.stdout
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else __doc__)
