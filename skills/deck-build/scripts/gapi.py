#!/usr/bin/env python3
"""Google の API（Drive・Slides・Docs）を呼ぶ共通の部品。slides.py・template.py・gslides.py・docs.py・drive_put.py が使う（標準ライブラリだけ）。
認証は単独で動く（gcloud も、ほかの Google のスキルも要らない）。トークンは、環境変数 GOOGLE_OAUTH_ACCESS_TOKEN、なければ
authorized_user の認証情報の JSON（GOOGLE_APPLICATION_CREDENTIALS、なければ gcloud の ADC のファイル）の refresh_token で取る。401・403 や認証情報がないときは factory-doctor で確かめる。
usage: python3 gapi.py --selftest"""
import functools, json, os, re, sys, time, tomllib, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path

SLIDES = "https://slides.googleapis.com/v1/presentations"
DOCS = "https://docs.googleapis.com/v1/documents"
DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
GSLIDES = "application/vnd.google-apps.presentation"
GDOCS = "application/vnd.google-apps.document"
_TOK = None


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


def request(method, url, body=None, raw=None, ctype="application/json", binary=False):
    """JSON を辞書で返す（binary=True ならバイト列）。429 は待って取り直す（サムネイルは 1 分あたりの上限がある）。"""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Authorization": f"Bearer {token()}", "Content-Type": ctype}
    if qp := factory().get("google", {}).get("quota_project"):
        headers["x-goog-user-project"] = qp  # gcloud の既定の OAuth クライアントで取ったトークンは、これがないと 403
    for wait in (5, 15, 30, 60, None):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method)) as r:
                b = r.read()
                return b if binary else (json.loads(b) if b else {})
        except urllib.error.HTTPError as e:
            if e.code == 429 and wait:
                time.sleep(wait)
                continue
            raise ApiError(f"{e.code} {method} {url}\n{e.read().decode(errors='replace')[:2000]}") from None


def batch(pid, reqs):
    """presentations.batchUpdate。まとめて送った要求は、どれか 1 つが失敗すると全部が入らない。"""
    return request("POST", f"{SLIDES}/{pid}:batchUpdate", {"requests": reqs}) if reqs else {}


def file_id(s):  # Google Slides・Docs の URL か ID
    m = re.search(r"/d/([\w-]+)", s)
    return m.group(1) if m else s


def folder_id(s):  # Drive のフォルダの URL か ID
    m = re.search(r"/folders/([\w-]+)", s)
    return m.group(1) if m else s


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


def guard(fid, rev, key, src):
    """前に組んだあとに画面で直されていたら（rev が key に残した版か指紋と違う）、または未解決のコメントがあれば、止める。
    組み直すと画面での直しは消え、コメントは付け先を失う。src は直しを入れる先（pages.py・doc.md）。"""
    last = request("GET", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(key)
    comments = [c for c in request("GET", f"{DRIVE}/files/{fid}/comments?pageSize=100&fields=comments(resolved,deleted,content,quotedFileContent(value))")
                .get("comments", []) if not c.get("resolved") and not c.get("deleted")]
    for c in comments[:5]:  # どの文に付いた、どんなコメントか（直す先を探しやすいように）
        print(f"コメント: 「{c.get('quotedFileContent', {}).get('value', '')[:30]}」に「{c.get('content', '')[:60]}」", file=sys.stderr)
    why = (["前に組んだあとに画面で直されている"] if last and last != rev else []) + ([f"未解決のコメントが {len(comments)} 件ある"] if comments else [])
    if why:
        sys.exit("組み直すと、画面での直しが消え、コメントは付け先を失う: " + "、".join(why)
                 + f"。直しとコメントへの対応を {src} に入れてから、--force を付けて組み直す")


def stamp(fid, rev, key):  # 組んだときの版を、Drive のファイルの appProperties に残す（guard が比べる）
    request("PATCH", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=id", {"appProperties": {key: rev}})


def slide_ids(pid):
    return [s["objectId"] for s in request("GET", f"{SLIDES}/{pid}?fields=slides(objectId)").get("slides", [])]


def thumbnail(pid, obj):
    """Google が描いたページの画像（1600 × 900）の情報。contentUrl は 30 分で切れ、知っていれば誰でも開ける（人に見せない）。"""
    return request("GET", f"{SLIDES}/{pid}/pages/{obj}/thumbnail?thumbnailProperties.thumbnailSize=LARGE&thumbnailProperties.mimeType=PNG")


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
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else __doc__)
