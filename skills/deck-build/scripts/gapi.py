#!/usr/bin/env python3
"""Google の API（Drive・Slides・Docs）を呼ぶ共通の部品。slides.py・template.py・gslides.py・docs.py・drive_put.py が使う（標準ライブラリだけ）。
認証は単独で動く（gcloud も、ほかの Google のスキルも要らない）。トークンは、環境変数 GOOGLE_OAUTH_ACCESS_TOKEN、なければ
authorized_user の認証情報の JSON（GOOGLE_APPLICATION_CREDENTIALS、なければ gcloud の ADC のファイル）の refresh_token で取る。401・403 や認証情報がないときは factory-doctor で確かめる。
usage: python3 gapi.py --selftest"""
import datetime, functools, getpass, json, os, re, sys, tempfile, threading, time, tomllib, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path

SLIDES = "https://slides.googleapis.com/v1/presentations"
DOCS = "https://docs.googleapis.com/v1/documents"
DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
GSLIDES = "application/vnd.google-apps.presentation"
GDOCS = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
_TOK = None
WAITED = []  # 429 で待った秒（request が足す。Clock が回数と秒を出す）
_HOLD = [0.0]  # 429 の分の枠が明ける時刻。並べて取るほかの取り手も、それまで送らない
_LOCK = threading.Lock()


def window_end(body, now=None):
    """429 の本文の ErrorInfo の window_start_time（分の枠の始まり。2026-10-15 の本文では epoch の秒の文字列。ISO 8601・ミリ秒も読む）から、枠が明ける時刻（epoch 秒）。なければ None。
    上限は 1 人 1 分（quota_unit 1/min/{project}/{user}）の枠で数えるので、枠が明ければ通る（2026-10-15 に 429 の本文で確かめた。枠の始まりは分の頭にそろっていない）。"""
    m = re.search(r'"window_start_time"\s*:\s*"?([^",}]+)', body)
    if not m:
        return None
    v = m.group(1).strip()
    try:
        if re.fullmatch(r"[\d.]+", v):  # epoch。ミリ秒なら秒にする
            t = float(v) / 1000 if float(v) > 1e11 else float(v)
        else:
            t = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
    end, now = t + 60 + 1, now or time.time()  # 1 秒の余裕（時計のずれ）
    return end if now - 60 < end <= now + 65 else None  # 古すぎる値と、1 分より先の値は読み違えとみなす（待ちすぎない）


class Clock:
    """工程ごとの秒を数え、標準エラーに 1 行で出す（slides.py build・gslides.py check。記録から長い回の原因を分けるため）。429 と上限を見越した待ちも出す。"""

    def __init__(self):
        self.t, self.parts = time.time(), []

    def lap(self, name):
        now = time.time()
        self.parts.append((name, now - self.t))
        self.t = now

    def show(self, what):
        waits = (f"・429 の待ち {len(WAITED)} 回・計 {sum(WAITED):.0f} 秒" if WAITED else "") + (f"・上限を見越した待ち {len(PACED)} 回・計 {sum(PACED):.0f} 秒" if PACED else "")
        print(f"{what}の時間（秒）: " + "・".join(f"{n} {s:.1f}" for n, s in self.parts) + f"・計 {sum(s for _, s in self.parts):.1f}{waits}"
              + ("（待ちは並べた取り手ごとの合計）" if waits else ""), file=sys.stderr)


CLOCK = Clock()  # 読み込んだときから数える


def locate():
    """factory.toml（人ごとに変わる設定値。ワークスペースの直下）を、今いるフォルダから上へ、次にこのスクリプトのフォルダから上へたどって探す。なければ None。
    結果を覚えない。import のときに読むもの（slides.py の [brand]）はこちらを使う（覚えると、あとで今いるフォルダを変える factory-doctor が古い結果を使う）。"""
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        for d in (base, *base.parents):
            if (d / "factory.toml").is_file():
                return d / "factory.toml"
    return None


@functools.cache
def find_factory():
    """locate の結果（最初に呼んだときのものを覚える）。"""
    return locate()


def factory_path():
    """find_factory の結果。なければ止まる。"""
    return find_factory() or sys.exit("factory.toml が見つからない（今いるフォルダとスクリプトのフォルダから上へ探した）。ワークスペース（資料のフォルダの上。例: ~/Documents/factory.toml）に置く。"
             "書き方は ../slides.md の 3")


@functools.cache
def factory():
    """factory.toml の設定値（[google]・[slides]・[drive]）。"""
    return tomllib.loads(factory_path().read_text())


class ApiError(Exception):
    """API がエラーを返した。メッセージは状態コード・URL・返ってきた本文。"""


ADC = "~/.config/gcloud/application_default_credentials.json"
SCOPES = ("https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/presentations",
          "https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/cloud-platform")  # cloud-platform は quota project のヘッダーに要る
LOGIN = f'gcloud auth application-default login --scopes="{",".join(SCOPES)}"'  # 認証情報の JSON を作るとき（1 回だけ）


def credentials_path():
    """authorized_user の認証情報の JSON。GOOGLE_APPLICATION_CREDENTIALS があればそれ、なければ gcloud の ADC のファイル。"""
    return Path(os.path.expanduser(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or ADC))


def refresh(creds):
    """authorized_user の refresh_token で、アクセストークンを取る（標準ライブラリだけ）。"""
    if creds.get("type") != "authorized_user":
        raise ApiError(f"認証情報の type が {creds.get('type')}。authorized_user だけ扱う（サービスアカウントはトークンを GOOGLE_OAUTH_ACCESS_TOKEN で渡す）")
    body = urllib.parse.urlencode({k: creds[k] for k in ("client_id", "client_secret", "refresh_token")} | {"grant_type": "refresh_token"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST")) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        raise ApiError(f"トークンを取れない（{e.code}）。認証情報を作り直す: {LOGIN}\n{e.read().decode(errors='replace')[:500]}") from None


def file_token():
    """認証情報の JSON（credentials_path）から取る。"""
    p = credentials_path()
    if not p.is_file():
        raise ApiError(f"Google の認証情報がない: {p}。作る: {LOGIN}")
    return refresh(json.loads(p.read_text()))


def token():
    """アクセストークン。環境変数 GOOGLE_OAUTH_ACCESS_TOKEN があればそれ、なければ認証情報の JSON から取る。"""
    global _TOK
    if not _TOK:
        _TOK = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") or file_token()
    return _TOK


def request(method, url, body=None, raw=None, ctype="application/json", binary=False, paced=False):
    """JSON を辞書で返す（binary=True ならバイト列）。429 は待って取り直す（サムネイルは 1 分あたりの上限がある）。
    paced=True（ページの画像）なら、送るたびに（429 の取り直しも）上限を見越して待つ（pace）。待った秒は WAITED・PACED に足す。"""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Authorization": f"Bearer {token()}", "Content-Type": ctype}
    if qp := factory().get("google", {}).get("quota_project"):
        headers["x-goog-user-project"] = qp  # gcloud の既定の OAuth クライアントで取ったトークンは、これがないと 403
    for wait in (5, 15, 30, 60, None):
        if (hold := _HOLD[0] - time.time()) > 0:  # ほかの取り手が 429 を受け、分の枠が明けるのを待っている
            WAITED.append(hold)
            time.sleep(hold)
        if paced:
            pace()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method)) as r:
                b = r.read()
                return b if binary else (json.loads(b) if b else {})
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 429 and wait:
                with _LOCK:  # 枠が分かれば、明けるまで待つ（取り手がそろって 5・15・30 秒待つより短い）。分からないか、もう明けている（時計のずれ）なら、5・15・30・60 秒
                    end = window_end(body)
                    if end and end > time.time():
                        _HOLD[0] = max(_HOLD[0], end)
                        w = _HOLD[0] - time.time()
                    else:
                        w = wait
                WAITED.append(w)
                time.sleep(w)
                continue
            raise ApiError(f"{e.code} {method} {url}\n{body[:2000]}") from None


def batch(pid, reqs):
    """presentations.batchUpdate。まとめて送った要求は、どれか 1 つが失敗すると全部が入らない。"""
    return request("POST", f"{SLIDES}/{pid}:batchUpdate", {"requests": reqs}) if reqs else {}


def file_id(s):  # Google Slides・Docs の URL か ID
    m = re.search(r"/d/([\w-]+)", s)
    return m.group(1) if m else s


def folder_id(s):  # Drive のフォルダの URL か ID
    m = re.search(r"/folders/([\w-]+)", s)
    return m.group(1) if m else s


def subfolder(root, name, create=False):
    """root（フォルダの URL か ID）の下の name のフォルダの ID。なければ None（create なら作る）。2 つあれば古いほう（作るのと探すのとで同じものを選ぶ）。"""
    q = urllib.parse.quote(f"name = '{name}' and '{folder_id(root)}' in parents and mimeType = '{FOLDER}' and trashed = false")
    found = request("GET", f"{DRIVE}/files?q={q}&orderBy=createdTime&fields=files(id)&supportsAllDrives=true&includeItemsFromAllDrives=true")["files"]
    if found:
        return found[0]["id"]
    if not create:
        return None
    return request("POST", f"{DRIVE}/files?supportsAllDrives=true&fields=id", {"name": name, "mimeType": FOLDER, "parents": [folder_id(root)]})["id"]


def upload(data, mime, name=None, parent=None, convert=None, fid=None, fields="id"):
    """Drive にファイルを上げる。fid を渡すと中身だけ上書きする（ID・URL・共有の設定は変わらない）。
    convert に Google の形式（GSLIDES など）を渡すと変換して作る。"""
    q = f"supportsAllDrives=true&fields={fields}"
    if fid:
        return request("PATCH", f"{UPLOAD}/{fid}?uploadType=media&{q}", raw=data, ctype=mime)
    b = uuid.uuid4().hex
    meta = json.dumps({"name": name, **({"parents": [parent]} if parent else {}), **({"mimeType": convert} if convert else {})})  # parent を省くと My Drive の直下
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{b}\r\nContent-Type: {mime}\r\n\r\n".encode()
            + data + f"\r\n--{b}--".encode())
    return request("POST", f"{UPLOAD}?uploadType=multipart&{q}", raw=body, ctype=f"multipart/related; boundary={b}")


def delete(fid):  # ゴミ箱を通さずに消す。作った仮のファイルを片付けるときだけ使う
    request("DELETE", f"{DRIVE}/files/{fid}?supportsAllDrives=true")


def trash(fid):  # ゴミ箱に移す（30 日は戻せる）。共有ドライブの資料のフォルダに作ったものを片付けるときに使う
    request("PATCH", f"{DRIVE}/files/{fid}?supportsAllDrives=true", {"trashed": True})


def guard(fid, rev, key, src, stop=True):
    """前に組んだあとに画面で直されていたら（rev が key に残した版か指紋と違う）、または未解決のコメントがあれば、止める。
    組み直すと画面での直しは消え、コメントは付け先を失う。src は直しを入れる先（pages.py・doc.md）。stop=False なら止めずに理由の並びを返す（slides.py plan）。"""
    last = request("GET", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(key)
    st = factory_path().parent / ".factory" / "comments.json"  # 見張りの知らせ（deck-comments の comments.py watch）は、直すコメントでないので数えない
    notice = {n["id"] for n in json.loads(st.read_text()).get("notice", {}).values()} if st.is_file() else set()
    comments = [c for c in request("GET", f"{DRIVE}/files/{fid}/comments?pageSize=100&fields=comments(id,resolved,deleted,content,quotedFileContent(value))")
                .get("comments", []) if not c.get("resolved") and not c.get("deleted") and c.get("id") not in notice]
    for c in comments[:5]:  # どの文に付いた、どんなコメントか（直す先を探しやすいように）
        print(f"コメント: 「{c.get('quotedFileContent', {}).get('value', '')[:30]}」に「{c.get('content', '')[:60]}」", file=sys.stderr)
    why = (["前に組んだあとに画面で直されている"] if last and last != rev else []) + ([f"未解決のコメントが {len(comments)} 件ある"] if comments else [])
    if why and not stop:
        return why
    if why:
        sys.exit("組み直すと、画面での直しが消え、コメントは付け先を失う: " + "、".join(why)
                 + f"。直しとコメントへの対応を {src} に入れてから、--force を付けて組み直す（コメントを全部見るのは deck-comments の comments.py）")


def stamp(fid, rev, key):  # 組んだときの版を、Drive のファイルの appProperties に残す（guard が比べる）
    request("PATCH", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=id", {"appProperties": {key: rev}})


def slide_ids(pid):
    return [s["objectId"] for s in request("GET", f"{SLIDES}/{pid}?fields=slides(objectId)").get("slides", [])]


def user():
    """この機械の使っている人の名前。手元の記録のファイルを人ごとに分ける（Linux の /tmp は人で共有する）。取れなければ "user"。"""
    try:
        return getpass.getuser()
    except Exception:  # 環境変数も passwd もない（コンテナなど）。getpass は版によって OSError か KeyError を出す
        return "user"


THUMB_PER_MIN = 60  # ページの画像は 1 人 1 分 60 回まで（Slides API の expensive read。https://developers.google.com/workspace/slides/api/limits）
THUMB_LOG = os.path.join(tempfile.gettempdir(), f"gapi_thumbnails_{user()}")  # この機械で画像を取った時刻。ほかの会話・子の確かめと上限を分け合う（上限は人ごとなので、ファイルも人ごと）
PACED = []  # 上限を見越して待った秒（pace が足す）


def pace(path=THUMB_LOG, limit=THUMB_PER_MIN, window=61):
    """ページの画像を取る前に呼ぶ。この機械で直前の window 秒に limit 回取っていたら、空くまで待つ（超えると 429 で、分の枠が明けるまで止まる。
    前の版の 5・15・30 秒の取り直しでは、2026-10-15 に 53 枚で測ると、最後の 6 枚が 52 秒ずつ待った）。ponytail: ほかの機械（CI など）で同じ人が取った分は数えない（429 の取り直しが拾う）"""
    try:
        import fcntl
    except ImportError:  # Windows。見越さない（429 の取り直しが拾う）
        return
    while True:
        try:
            with open(path, "a+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # 同じ機械の会話・子が同じファイルを読み書きする
                f.seek(0)
                now = time.time()
                ts = sorted(float(t) for t in re.findall(r"\d+(?:\.\d+)?", f.read()) if now - float(t) < window)  # 数でないものは読み飛ばす
                if len(ts) < limit:
                    f.seek(0)
                    f.truncate()
                    f.write(" ".join(map(str, ts + [now])))
                    return
        except OSError:  # 読み書きできなければ見越さない（429 の取り直しが拾う）
            return
        PACED.append(w := ts[len(ts) - limit] + window - now)
        time.sleep(w)


def thumbnail(pid, obj):
    """Google が描いたページの画像（1600 × 900）の情報。contentUrl は 30 分で切れ、知っていれば誰でも開ける（人に見せない）。上限を見越して待つ（pace）。"""
    return request("GET", f"{SLIDES}/{pid}/pages/{obj}/thumbnail?thumbnailProperties.thumbnailSize=LARGE&thumbnailProperties.mimeType=PNG", paced=True)


def run(main):
    """CLI の入り口。API のエラーは、返ってきた本文を見せて終える（トレースバックにしない）。"""
    try:
        main()
    except ApiError as e:
        sys.exit(str(e))


def selftest():
    assert file_id("https://docs.google.com/presentation/d/1AbC-_x/edit#slide=id.p") == "1AbC-_x" and file_id("1AbC") == "1AbC"
    assert folder_id("https://drive.google.com/drive/folders/1Xy_z-9?usp=sharing") == "1Xy_z-9" and folder_id("1Xy") == "1Xy"
    try:
        refresh({"type": "service_account"})
        raise AssertionError("サービスアカウントを通した")
    except ApiError as e:
        assert "authorized_user" in str(e)
    t0 = 1_760_000_000
    assert window_end('{"metadata": {"window_start_time": "2025-10-09T08:53:20Z"}}', t0) == t0 + 61
    body = '"quota_limit": "ExpensiveReadRequestsPerMinutePerUser",\n          "window_start_time": "1760000000",\n          "service": "slides.googleapis.com"'  # 429 の本文の形（2026-10-15）
    assert window_end(body, t0) == t0 + 61
    assert window_end('"window_start_time": "1760000000000"', t0) == t0 + 61 and window_end('"window_start_time": 1760000000', t0) == t0 + 61
    assert window_end('"window_start_time": "%d"' % (t0 + 3600), t0) is None  # 1 時間先は読み違え（そこまで待たない）
    assert window_end("{}", t0) is None and window_end('"window_start_time": "x"', t0) is None and window_end('"window_start_time": "1"', t0) is None
    import io
    real = urllib.request.urlopen, time.sleep, factory, globals()["_TOK"], globals()["pace"]
    calls, slept, paced = [], [], []

    def fake(req, *a, **k):  # 1 回目は、もう明けた枠の 429。2 回目は通す
        calls.append(req)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "x", {}, io.BytesIO(b'"window_start_time": "%d"' % (time.time() - 70)))
        return io.BytesIO(b"{}")

    globals().update(factory=lambda: {}, _TOK="t", pace=lambda: paced.append(1))
    urllib.request.urlopen, time.sleep = fake, slept.append
    try:
        assert request("GET", "https://example.invalid", paced=True) == {} and slept == [5]  # 明けた枠なら、0.5 秒でなく前の 5 秒で取り直す
        assert len(paced) == 2  # 取り直しも、上限を見越して数える
        calls.clear()
        _HOLD[0] = time.time() + 30  # ほかの取り手が 429 で枠を待っている
        calls.append(0)  # 1 回目を 429 にしない
        assert request("GET", "https://example.invalid") == {} and 25 < slept[-1] <= 30 and len(WAITED) == 2  # 枠を待った秒も数える
    finally:
        urllib.request.urlopen, time.sleep = real[0], real[1]
        globals().update(factory=real[2], _TOK=real[3], pace=real[4])
        WAITED.clear()
        _HOLD[0] = 0.0
    with tempfile.TemporaryDirectory() as d:  # 上限に届いたら、いちばん古い 1 回が窓を出るまで待つ
        log = os.path.join(d, "t")
        open(log, "w").write(f"{time.time() - 0.6} {time.time() - 0.5}")
        t0 = time.time()
        pace(log, limit=3, window=0.8)
        assert time.time() - t0 < 0.1 and not PACED
        pace(log, limit=3, window=0.8)
        assert 0.1 < time.time() - t0 < 0.5 and len(PACED) == 1 and len(open(log).read().split()) <= 3
        open(log, "w").write("x 1.5.6")  # 壊れた中身は読み飛ばす
        pace(log, limit=3, window=0.8)
        assert len(PACED) == 1
        pace(os.path.join(d, "no", "such"), limit=3)  # 書けないところでも止まらない
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else __doc__)
