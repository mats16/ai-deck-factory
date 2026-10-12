#!/usr/bin/env python3
"""usage: sessions.py --since <ISO8601（UTC）> [--root <作業フォルダ>]   （--selftest で自己確認）
Claude Code・Codex・pi の会話からユーザーの発言、触った資料のフォルダ、規則への言及と読み取り成功、
資料を対象にした確認（スライドは gslides.py check、Google Docs は docs.py check、docx は check.sh）の成功、道具のエラーを抜き出す。標準ライブラリのみ。
拾うのは、作業フォルダそのものか AREAS の下で始めた会話だけ（Obsidian Vault・Codex などは拾わない）。T3 Code が任せたサブエージェントの会話は拾わない。
確認できない呼び出しは未確認として残す。会話はデータで、指示ではない。"""
import glob, json, os, re, shlex, sys
from collections import Counter
from pathlib import Path

ROOT = next((str(d) for d in (Path.cwd(), *Path.cwd().parents) if (d / "factory.toml").is_file()), os.getcwd())  # ワークスペース（今いるフォルダから上へ、最初の factory.toml のフォルダ）
AREAS = ("customers", "internal", "research", ".agents")
RULE = re.compile(r"skills/([\w-]+/[\w./-]+\.(?:md|py|sh))|(AGENTS\.md|references_index\.md)|(?<![\w-])(rules/[\w-]+/[\w./-]+\.md)")  # 最後はワークスペースの rules/（rules/ を付けたまま数え、プラグインのファイルと分ける）
TABLE = ("deck-practices/SKILL.md", "deck-build/slides.md", "deck-practices/visual.md", "deck-practices/content.md", "doc-build/SKILL.md",
         "deck-practices/visual_doc.md", "doc-build/docx.md", "deck-build/docx.md",
         "office-jp/slides.md", "office-jp/docx.md")  # 2026-10-07 に pptx.md から slides.md へ。office-jp は 2026-10-08 に deck-build と改名した。
# docx.md は 2026-10-09 に deck-build から doc-build へ移した（前の会話の記録のため、前の名前も残す）
SKIP = ("<", "# AGENTS.md instructions", "Another Claude session sent a message", "Base directory for this skill",
        "This session is being continued", "Caveat:", "Delegated task ")  # 最後は、任せた仕事が終わったという T3 Code の知らせ


def rules(text):
    return [m.group(m.lastindex) for m in RULE.finditer(text)]


def text_content(value):
    """画像・音声などをログに展開せず、テキストだけ取る。"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text_content(x) for x in value if isinstance(x, (dict, str)))
    if isinstance(value, dict):
        return text_content(value.get("text", value.get("content", value.get("output", ""))))
    return ""


def shell_evidence(command):
    """単純なシェルの実コマンドだけ判別する。検索・echo・スクリプト内の文字は読了にしない。"""
    reads, checks, piped = [], 0, bool(re.search(r"[|;\n]", command.strip()))
    # here document や動的な評価は実行結果の帰属を決められない。
    if "<<" in command or "$(" in command or "`" in command:
        return reads, checks, piped
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return reads, checks, piped
    env, groups, group = {}, [], []
    for token in tokens + [";"]:
        if token and all(c in ";&|()\n" for c in token):
            if group:
                groups.append(group)
            group = []
        else:
            group.append(token)
    expand = lambda t: re.sub(r"\$(?:\{(\w+)\}|(\w+))", lambda m: env.get(m[1] or m[2], m[0]), t)
    for args in groups:
        while args and re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", args[0]):
            key, val = args.pop(0).split("=", 1)
            env[key] = expand(val)
        if not args:
            continue
        args = [expand(x) for x in args]
        executable = os.path.basename(args[0])
        if executable in ("cat", "sed", "head", "tail", "less", "more"):
            # sed の式などに含まれるパスをファイルの読み取りと誤認しない。
            candidates = args[1:] if executable != "sed" else args[2:]
            for token in candidates:
                if not token.startswith("-"):
                    reads.extend(rules(token))
        offset = 1 if executable in ("sh", "bash", "zsh", "python3", "python") else 0
        if len(args) > offset and os.path.basename(args[offset]) == "check.sh":
            if any(re.search(r"\.(?:pptx|docx)$", arg) for arg in args[offset + 1:]):
                checks += 1
        elif len(args) > offset + 2 and os.path.basename(args[offset]) in ("gslides.py", "docs.py") and args[offset + 1] == "check":
            checks += 1  # Google Slides の確認（2026-10-07 から）と Google Docs の確認（2026-10-09 から）
    # ; と || は途中の読み取り失敗を隠せるので、読了の帰属は保留する。
    if re.search(r";|\|\||\n", command.strip()):
        reads = []
    return reads, checks, piped


def words(text):
    """コマンドの語。引用符の外の ; | & ( ) < > ` と空白で区切る（引用符の中はそのまま。hooks/rules_overlay.py と同じ）。"""
    lex = shlex.shlex(text, posix=True, punctuation_chars="();<>|&`")
    lex.whitespace_split, lex.commenters = True, ""  # # は語の中にも出る（deck#2）
    try:
        return list(lex)
    except ValueError:
        return text.split()


PATH_KEYS, COMMAND_KEYS = ("file_path", "path", "notebook_path"), ("command", "cmd")  # 資料のフォルダを見る引数（書く本文や prompt の文は見ない）


def deck_words(kind, args):
    """道具の引数のうち、資料のフォルダを指すかもしれない語。パスの引数は切らない（空白のあるフォルダ）。コマンドは語に区切る。"""
    if isinstance(args, dict):
        found = [args[k] for k in PATH_KEYS if isinstance(args.get(k), str)]
        found += [w for k in COMMAND_KEYS if isinstance(args.get(k), str) for w in words(args[k])]
    elif kind in ("exec", "functions.exec") and isinstance(args, str):  # Codex の code mode の JS（call_evidence と同じ名前）。コマンドは JS の引用符の中にあるので、もう一度区切る
        found = [v.strip("\"'{}(),;") for w in words(args) for v in words(w)]
    else:
        found = []
    return [w for w in found if w and w[0] not in "-;|&()<>`"]  # 資料のフォルダかは md() が、会話を始めたフォルダからたどって決める


def deck_of(path, root):
    """絶対パスから資料のフォルダ（Customers/<顧客>/<資料>・Internal/<資料>）。ワークスペースの直下のものだけ（URL やほかのフォルダの中の customers/ は資料でない）。"""
    p, top = os.path.normpath(path), root.rstrip("/") + "/"  # .. を畳む
    if not p.lower().startswith(top.lower()):  # macOS は大文字と小文字を区別しない
        return None
    parts = p[len(top):].split("/")
    n = {"customers": 3, "internal": 2}.get(parts[0].lower(), 0)
    if not n or len(parts) < n:  # ファイル（memory.md など）は md() がフォルダでないので外す
        return None
    return "/".join(["Customers" if n == 3 else "Internal", *parts[1:n]])


def call_evidence(name, args):
    raw = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            pass
    kind = name.rsplit("__", 1)[-1].lower()
    info = {"decks": deck_words(kind, args), "mentions": rules(raw), "check_mention": any(x in raw for x in ("check.sh", "gslides.py check", "docs.py check")),
            "reads": [], "checks": 0, "piped": False, "nested": False, "read_tool": kind == "read"}
    if kind == "read" and isinstance(args, dict):
        info["reads"] = rules(args.get("file_path", args.get("path", "")))
    elif kind == "skill" and isinstance(args, dict) and args.get("skill"):  # Claude Code の Skill ツールは SKILL.md を読ませる（2026-10-08 から、作業の始め方は deck-practices/SKILL.md）
        info["reads"] = [args["skill"].split(":")[-1] + "/SKILL.md"]
        info["mentions"] += info["reads"]
        info["read_tool"] = True
    elif kind in ("bash", "exec_command", "shell_command") and isinstance(args, dict):
        info["reads"], info["checks"], info["piped"] = shell_evidence(args.get("command", args.get("cmd", "")))
    elif kind in ("exec", "functions.exec") and isinstance(args, str):
        # Codex code mode: 引数が固定の exec_command が 1 つのときだけ結果を帰属させる。
        commands = re.findall(r'\btools\.exec_command\(\s*\{\s*cmd\s*:\s*("(?:\\.|[^"\\])*")', args)
        if len(commands) == 1 and args.count("tools.exec_command(") == 1:
            try:
                command = json.loads(commands[0])
            except ValueError:
                return info
            info["reads"], info["checks"], info["piped"] = shell_evidence(command)
            info["nested"] = True
    return info


def result_status(value, is_error=None, nested=False):
    """ツールの終了コードを優先する。ラッパーの完了を内部コマンド成功と取り違えない。"""
    text = text_content(value)
    objects = []
    if isinstance(value, dict):
        objects.append(value)
    for piece in ([value] if isinstance(value, str) else value if isinstance(value, list) else []):
        try:
            obj = json.loads(text_content(piece))
            if isinstance(obj, dict):
                objects.append(obj)
        except (ValueError, TypeError):
            pass
    codes = [x["exit_code"] for x in objects if "exit_code" in x and x["exit_code"] is not None]
    codes += [int(x) for x in re.findall(r"(?:Process exited with code|Exit code|exited with status)\s*:?\s*(\d+)", text)]
    running = next((x["session_id"] for x in objects if x.get("session_id") is not None and x.get("exit_code") is None), None)
    if is_error is True or any(c != 0 for c in codes):
        return False, text, None
    if running is not None:
        return None, text, running
    if codes:
        return True, text, None
    if nested:
        return None, text, None
    if is_error is False:
        return True, text, None
    return None, text, None


class Session:
    def __init__(self, kind, sid, path):
        self.kind, self.sid, self.path = kind, sid, path
        self.cwd, self.title, self.start = "", "", ""
        self.said, self.opened, self.mentioned, self.errors = [], Counter(), Counter(), []
        self.decks = []  # 道具の呼び出しごとの、資料のフォルダを指すかもしれない語。md() で資料のフォルダにする（dreaming が ledger.py add --deck に使う）
        self.built, self.check_mentioned, self.check_calls = False, False, 0
        self.built_at = ""  # 確認が初めて通った時刻。これより後のユーザーの発言は、確認で拾えなかった直しの候補（dreaming の 5）
        self.pending, self.running = {}, {}

    def tool_input(self, name, args, tool_id):
        info = call_evidence(name, args)
        self.mentioned.update(info["mentions"])
        if info["decks"]:
            self.decks.append(info["decks"])
        self.check_mentioned |= info["check_mention"]
        self.check_calls += info["checks"]
        if name.rsplit("__", 1)[-1] == "write_stdin":
            try:
                data = json.loads(args) if isinstance(args, str) else args
                info = self.running.get(data.get("session_id"), info)
            except (ValueError, AttributeError):
                pass
        if tool_id:
            self.pending[tool_id] = info

    def tool_result(self, tool_id, value, is_error=None, ts=""):
        info = self.pending.pop(tool_id, None)
        status, text, running = result_status(value, is_error, bool(info and info["nested"]))
        if status is False:
            self.errors.append(re.sub(r"\s+", " ", text)[:160])
        if not info:
            return
        if running is not None:
            self.running[running] = info
        if status is not True:
            return
        # シェルの出力だけを失敗の言葉で見る。Read の結果はファイルの中身なので、規則に「Permission denied」と書いてあっても読めている
        read_failed = not info.get("read_tool") and re.search(r"No such file|cannot open|Permission denied|Operation not permitted|Traceback", text, re.I)
        if text.strip() and not read_failed:
            self.opened.update(info["reads"])
        failed = re.search(r"validate\.py (?:か lint の要修正が残っている|が失敗)|lint の要修正が残っている|Traceback|Operation not permitted|要修正:\s*[1-9]\d*", text)
        # pipeline の終了コードは最終コマンドのもの。check.sh・gslides.py check・docs.py check の完走の出力も確認する。
        complete = ("All validations PASSED" in text and "テキスト:" in text and "和文の書体" in text) or \
            ("テキスト:" in text and "画像:" in text and "JSON:" in text)
        if info["checks"] and not failed and (not info["piped"] or complete):
            self.built, self.built_at = True, self.built_at or ts

    def user_text(self, ts, text):
        text = text.strip()
        if text and not text.startswith(SKIP):
            self.said.append((ts, re.sub(r"\s+", " ", text)[:500]))

    def md(self, root):
        where = os.path.relpath(self.cwd, root) if self.cwd else "?"
        state = "、確認の成功確認" if self.built else "、確認（gslides.py check・docs.py check・check.sh）への言及あり（成功未確認）" if self.check_mentioned else ""
        out = [f"## {self.kind} {self.sid[:8]} {self.start[:16]} {self.title} （{where}{state}）", f"- ファイル: {self.path}"]
        decks = Counter()
        for call in [*self.decks, *([[self.cwd]] if self.cwd else [])]:  # 呼び出しごとに 1 回。資料のフォルダで始めた会話は、そのフォルダも数える
            found = dict.fromkeys(deck_of(os.path.join(self.cwd or root, os.path.expanduser(w)), root) for w in call)  # 重ねず、出た順に
            decks.update(d for d in found if d and os.path.isdir(os.path.join(root, d)))  # ワークスペースにあるフォルダだけ（コマンドで書いた本文の中の語は資料でない）
        if decks:
            out.append("- 資料: " + ", ".join(f"{k} ×{v}" for k, v in decks.most_common()))
        if self.mentioned:
            out.append("- 規則への言及: " + ", ".join(f"{k} ×{v}" for k, v in self.mentioned.most_common()))
        if self.opened:
            out.append("- 読み取り成功（一部を含む）: " + ", ".join(f"{k} ×{v}" for k, v in self.opened.most_common()))
        unknown = [k for k in self.mentioned if k not in self.opened]
        if unknown:
            out.append("- 読んだか未確認: " + ", ".join(unknown))
        out += [f"- ユーザー {ts}{'（確認のあと）' if self.built_at and ts > self.built_at else ''}: 「{t}」" for ts, t in self.said]
        out += [f"- エラー: {e}" for e in self.errors[:5]]
        return "\n".join(out)


def in_scope(cwd, root):
    """macOS は大文字と小文字を区別しないので、そろえて比べる（名前を変える前の customers/ の会話も拾う）。"""
    rel = os.path.relpath(cwd.lower(), root.lower()) if cwd else ".."
    return rel == "." or rel.split(os.sep)[0] in AREAS


def claude_sessions(root, since, session_home=None):
    enc = re.sub(r"[/._]", "-", root)
    home = session_home or os.path.expanduser("~")
    for f in glob.glob(f"{home}/.claude/projects/{enc}*/*.jsonl"):
        if os.path.getmtime(f) < since_epoch(since):
            continue
        s = Session("claude", os.path.basename(f)[:-6], f)
        with open(f, encoding="utf-8") as source:
            for line in source:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t, ts = d.get("type"), d.get("timestamp", "")
                if t == "ai-title":
                    s.title = d.get("aiTitle") or d.get("title") or s.title
                if d.get("isSidechain") or t not in ("user", "assistant") or ts < since:
                    continue
                s.cwd, s.start = s.cwd or d.get("cwd", ""), s.start or ts
                c = d.get("message", {}).get("content", [])
                if t == "assistant":
                    for x in c if isinstance(c, list) else []:
                        if x.get("type") == "tool_use":
                            s.tool_input(x.get("name", ""), x.get("input", {}), x.get("id"))
                elif isinstance(c, str):
                    if not (d.get("isMeta") or d.get("isCompactSummary")):
                        s.user_text(ts, c)
                else:
                    for x in c:
                        if x.get("type") == "text" and not (d.get("isMeta") or d.get("isCompactSummary")):
                            s.user_text(ts, x.get("text", ""))
                        elif x.get("type") == "tool_result":
                            s.tool_result(x.get("tool_use_id"), x.get("content"), x.get("is_error", False), ts)
        if in_scope(s.cwd, root):
            yield s


def codex_sessions(root, since, session_home=None):
    home = session_home or os.path.expanduser("~")
    for f in glob.glob(f"{home}/.codex/sessions/*/*/*/rollout-*.jsonl"):
        if os.path.getmtime(f) < since_epoch(since):
            continue
        s = None
        with open(f, encoding="utf-8") as source:
            for line in source:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                p, ts = d.get("payload") or {}, d.get("timestamp", "")
                if d.get("type") == "session_meta":
                    if not in_scope(p.get("cwd", ""), root) or p.get("thread_source") in ("subagent", "guardian_review"):  # guardian_review は Codex の承認の審査（ユーザーの発言でない）
                        break
                    s = Session("codex", p.get("id", ""), f)
                    s.cwd = p["cwd"]
                    continue
                if s is None or ts < since or d.get("type") != "response_item":
                    continue
                s.start = s.start or ts
                typ = p.get("type")
                if typ == "message" and p.get("role") == "user":
                    for x in p.get("content") or []:
                        s.user_text(ts, x.get("text", ""))
                elif typ in ("function_call", "custom_tool_call"):
                    s.tool_input(p.get("name", ""), p.get("arguments") or p.get("input") or "", p.get("call_id"))
                elif typ in ("function_call_output", "custom_tool_call_output"):
                    s.tool_result(p.get("call_id"), p.get("output"), p.get("is_error"), ts)
        if s:
            yield s


def pi_sessions(root, since, session_home=None):
    home = session_home or os.path.expanduser("~")
    for f in glob.glob(f"{home}/.pi/agent/sessions/*/*.jsonl") + glob.glob(f"{home}/.ucode/pi-home/.pi/agent/sessions/*/*.jsonl"):  # 後ろは T3 Code が動かす pi
        if os.path.getmtime(f) < since_epoch(since):
            continue
        s, start = None, since
        with open(f, encoding="utf-8") as source:
            for line in source:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t, ts = d.get("type"), d.get("timestamp", "")
                if t == "session":
                    if not in_scope(d.get("cwd", ""), root):
                        break
                    s, start = Session("pi", d.get("id", ""), f), max(since, ts)  # /fork・/clone の会話は元の会話の行を写して始まるので、作った時刻より前の行は数えない
                    s.cwd = d["cwd"]
                    continue
                if s is None:
                    continue
                if t == "session_info":
                    s.title = d.get("name") or s.title
                if t != "message" or ts < start:
                    continue
                s.start = s.start or ts
                m = d.get("message") or {}
                role, c = m.get("role"), m.get("content")
                if role == "user":
                    s.user_text(ts, text_content(c))
                elif role == "assistant":
                    for x in c if isinstance(c, list) else []:
                        if x.get("type") == "toolCall":
                            s.tool_input(x.get("name", ""), x.get("arguments") or {}, x.get("id"))
                elif role == "toolResult":
                    s.tool_result(m.get("toolCallId"), c, m.get("isError"), ts)
        if s:
            yield s


def is_delegated(said):  # T3 Code が任せたサブエージェントの会話。最初の発言は任せたエージェントの文で、ユーザーの発言でない
    return bool(said) and re.match(r"Act as the [\w-]+ sub-agent for this task", said[0][1]) is not None


DREAMING = re.compile(r"[/:]dreaming\b|スキル dreaming|dreaming/SKILL\.md|dreaming ?(して|を回|の P\d)|提案を適用", re.I)


def is_dreaming(said):  # 整理を回す会話と、提案を適用する会話。最初の発言で、dreaming を呼んだものだけ（dreaming を説明する資料を作る会話は残す）
    return bool(said) and DREAMING.search(said[0][1]) is not None


def since_epoch(since):
    from datetime import datetime
    return datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()


def report(root, since):
    ss = [s for s in [*claude_sessions(root, since), *codex_sessions(root, since), *pi_sessions(root, since)]
          if s.said and not is_dreaming(s.said) and not is_delegated(s.said)]
    ss.sort(key=lambda s: s.start)
    built = [s for s in ss if s.built]
    unknown = [s for s in built if not any(k in s.opened for k in TABLE)]
    print(f"# 会話の抜き出し（{since} から。{len(ss)} 本）\n")
    print(f"- 確認（gslides.py check・docs.py check・check.sh）への言及あり: {sum(s.check_mentioned for s in ss)} 本。資料を対象にした実行の呼び出し: {sum(s.check_calls for s in ss)} 件")
    print(f"- 資料を仕上げた会話（確認の成功確認）: {len(built)} 本。うち作り方の表の読み取りを確認できないもの: {len(unknown)} 本"
          + (f"（{', '.join(s.sid[:8] for s in unknown)}）" if unknown else ""))
    print("- 未確認は未読や失敗の断定ではない。複雑なシェル・複数コマンドの code mode は結果を帰属できなければ成功に数えない。")
    opened = Counter()
    for s in ss:
        opened.update(s.opened.keys())
    print("- 規則の読み取りを確認できた会話: " + (", ".join(f"{k} {v}" for k, v in opened.most_common()) or "なし") + "\n")
    for s in ss:
        print(s.md(root) + "\n")


def selftest_decks():
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        root = os.path.realpath(root)
        for x in ("Customers/acme/deck_202610", "Internal/meetup_202610", "Customers/acme/d1", "Internal/m1", "Customers/Acme Inc./d 2", "Customers/acme/v1.2", "Customers/acme/deck#2"):
            os.makedirs(os.path.join(root, x))
        d = Session("claude", "deck", "test")
        d.tool_input("Read", {"file_path": root + "/Customers/acme/deck_202610/構成案.md"}, "a")
        d.tool_input("Bash", {"command": "python3 build/pages.py; cat customers/acme/deck_202610/references.md Customers/acme/memory.md Internal/meetup_202610/build/doc.md"}, "b")
        d.tool_input("WebFetch", {"url": "https://example.com/customers/acme/story", "prompt": "x"}, "c")
        d.tool_input("Bash", {"command": f"ls /tmp/x/Customers/acme/d1 {root}/vendor/internal/m1 ~/Customers/acme/d1"}, "d")
        assert "- 資料: Customers/acme/deck_202610 ×2, Internal/meetup_202610 ×1" in d.md(root), d.md(root)  # URL、ワークスペースの外、ほかのフォルダの中は拾わない
        home = os.environ.get("HOME")
        os.environ["HOME"] = root
        try:
            assert "Customers/acme/d1 ×1" in d.md(root)  # ~ はホームにして比べる
        finally:
            os.environ["HOME"] = home
        e = Session("claude", "deck2", "test")
        e.tool_input("Bash", {"command": "cd Customers/acme/d1; python3 build/pages.py|head"}, "a")
        e.tool_input("Bash", {"command": "cd /tmp\nCustomers/acme/d1/x.md && echo $(ls Internal/m1)"}, "b")
        e.tool_input("Read", {"file_path": root + "/Customers/Acme Inc./d 2/構成案.md"}, "c")
        e.tool_input("exec", 'text(await tools.exec_command({cmd:"cat Customers/acme/d1/references.md"}));', "d")
        e.tool_input("Write", {"file_path": "/tmp/notes.md", "content": "Internal/m1 は `x` → [it's](y)"}, "e")  # 書く本文は見ない
        e.tool_input("Bash", {"command": "cat > a.md <<'EOF'\nInternal/m2 → [it's](y) と Customers/acme/d9 のこと\nEOF"}, "f")  # コマンドで書く本文の語は、ないフォルダなら出さない
        assert "- 資料: Customers/acme/d1 ×3, Internal/m1 ×1, Customers/Acme Inc./d 2 ×1" in e.md(root), e.md(root)  # 区切り・改行・空白・. のある名前
        f = Session("codex", "deck3", "test")
        f.tool_input("Bash", {"command": "cd Customers/acme/v1.2 && cat Customers/acme/deck#2/x.md Customers/acme/../acme/d1/y.md Customers/acme/../../etc/z"}, "a")
        f.tool_input("functions.exec", 'tools.exec_command({cmd:"ls Internal/m1"})', "b")
        f.tool_input("Bash", {"command": "cat Customers/acme/memory.md"}, "c")
        g = Session("pi", "deck4", "test")
        g.cwd = os.path.join(root, "Customers/acme")
        g.tool_input("bash", {"command": "cat d1/構成案.md && cd d1 && python3 build/pages.py"}, "a")
        h = Session("codex", "deck5", "test")
        h.cwd = os.path.join(root, "Customers/acme/d1")
        h.tool_input("exec_command", {"cmd": "sed -n 1,80p 構成案.md"}, "a")
        assert "- 資料: Customers/acme/d1 ×1" in g.md(root) and "- 資料: Customers/acme/d1 ×2" in h.md(root), (g.md(root), h.md(root))  # 顧客・資料のフォルダで始めた会話の相対パス
        assert "- 資料: Customers/acme/v1.2 ×1, Customers/acme/deck#2 ×1, Customers/acme/d1 ×1, Internal/m1 ×1\n" in f.md(root) + "\n", f.md(root)  # . と # のある名前、.. を畳む、functions.exec、ファイルは外す


def selftest():
    assert rules("cat ~/ws/rules/deck-practices/visual.md ~/p/skills/deck-practices/visual.md AGENTS.md") == ["rules/deck-practices/visual.md", "deck-practices/visual.md", "AGENTS.md"]
    import tempfile
    from pathlib import Path
    root = "/x/Documents"
    rule = root + "/.agents/skills/deck-practices/visual.md"
    check = root + "/.agents/skills/deck-build/scripts/check.sh"
    selftest_decks()
    s = Session("claude", "abc", "test")
    s.tool_input("Bash", {"command": f'rg check.sh notes.md; echo "{rule}"'}, "mention")
    s.tool_result("mention", "found", False)
    assert s.check_mentioned and not s.built and not s.opened
    s.tool_input("Read", {"file_path": rule}, "failed-read")
    s.tool_result("failed-read", "403 Forbidden", True)
    assert not s.opened
    s.tool_input("Read", {"file_path": rule}, "read")
    s.tool_result("read", "rules", False)
    assert s.opened["deck-practices/visual.md"] == 1
    s.tool_input("Read", {"file_path": rule}, "read2")
    s.tool_result("read2", "403 Permission denied のときは…（規則の本文）", False)
    assert s.opened["deck-practices/visual.md"] == 2  # 中身に失敗の言葉があっても、Read の成功は読めたと数える
    s.tool_input("Skill", {"skill": "deck-practices"}, "skill")
    s.tool_result("skill", "Launching skill: deck-practices", False)
    assert s.opened["deck-practices/SKILL.md"] == 1  # スキルとして呼んだものも読んだと数える
    s.tool_input("Bash", {"command": f'sh {check} a.pptx'}, "bad")
    s.tool_result("bad", "Exit code 1", True)
    assert not s.built
    s.tool_input("Bash", {"command": f'sh {check} a.pptx'}, "ok")
    s.tool_result("ok", "All validations PASSED!", False)
    assert s.built
    assert shell_evidence(f'cat {check} | head -40')[1] == 0
    assert shell_evidence(f'rg {rule} {check} a.pptx')[0:2] == ([], 0)
    assert shell_evidence(f'K={root}/.agents/skills/deck-build/scripts; F="a.pptx"; $K/check.sh "$F"')[1] == 1
    assert shell_evidence("python3 ~/Documents/.agents/skills/deck-build/scripts/docs.py check https://docs.google.com/document/d/x/edit")[1] == 1
    assert shell_evidence(f'python3 - <<EOF\nprint("cat {rule}")\nEOF')[0] == []
    gs = root + "/.agents/skills/deck-build/scripts/gslides.py"
    assert shell_evidence(f'python3 {gs} check https://docs.google.com/presentation/d/x/edit')[1] == 1
    assert shell_evidence(f'python3 {gs} pages https://docs.google.com/presentation/d/x/edit')[1] == 0
    pipe = Session("claude", "pipeline", "test")
    pipe.tool_input("Bash", {"command": f'{check} a.pptx | tail'}, "pipe")
    pipe.tool_result("pipe", "some output", False)
    assert not pipe.built
    pipe.tool_input("Bash", {"command": f'{check} a.pptx | tail'}, "pipe2")
    pipe.tool_result("pipe2", "All validations PASSED!\n和文の書体: 1\nテキスト: /tmp/a.md\n要修正: 1", False)
    assert not pipe.built
    pipe.tool_input("Bash", {"command": f'{check} a.pptx; echo done'}, "masked")
    pipe.tool_result("masked", "done", False)
    assert not pipe.built
    assert shell_evidence(f'cat {rule} || echo done')[0] == []
    # code mode のラッパー完了だけでは内部コマンドの成功を断定しない。
    c = Session("codex", "c", "test")
    js = 'text(await tools.exec_command({cmd:' + json.dumps('cat ' + rule) + '}));'
    c.tool_input("exec", js, "nested")
    c.tool_result("nested", [{"text": "Script completed"}], None)
    assert not c.opened
    c.tool_input("exec", js, "nested2")
    c.tool_result("nested2", [{"text": json.dumps({"exit_code": 0, "output": "rule"})}], None)
    assert c.opened["deck-practices/visual.md"] == 1
    c.tool_input("exec_command", {"cmd": check + " a.docx"}, "running")
    c.tool_result("running", json.dumps({"session_id": 123, "exit_code": None, "output": "running"}))
    assert not c.built
    c.tool_input("write_stdin", {"session_id": 123}, "poll")
    c.tool_result("poll", json.dumps({"exit_code": 0, "output": "done"}))
    assert c.built
    # ログの tool_use_id / call_id が結果と対応することを両形式で確認する。
    with tempfile.TemporaryDirectory() as home:
        folder = Path(home) / '.claude/projects/-x-Documents-Obsidian-Vault'
        folder.mkdir(parents=True)
        ts = '2026-10-06T01:00:00Z'
        (folder / 'out.jsonl').write_text(json.dumps({"type": "user", "timestamp": ts, "cwd": root + "/Obsidian Vault", "message": {"content": "要約して"}}))
        assert in_scope(root, root) and in_scope(root + "/customers/Acme", root) and not in_scope("/x/DocumentsX", root)
        folder = Path(home) / '.claude/projects/-x-Documents-Customers-Acme'
        folder.mkdir(parents=True)
        rows = [
            {"type": "ai-title", "aiTitle": "見本"},
            {"type": "user", "timestamp": ts, "cwd": root, "message": {"content": "文字をもっと大きく"}},
            {"type": "user", "timestamp": ts, "cwd": root, "isMeta": True, "message": {"content": "Base directory for this skill: x"}},
            {"type": "assistant", "timestamp": ts, "cwd": root, "message": {"content": [
                {"type": "tool_use", "id": "r", "name": "Read", "input": {"file_path": rule}},
                {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": check + ' a.pptx'}}]}},
            {"type": "user", "timestamp": ts, "cwd": root, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "r", "content": "rules", "is_error": False},
                {"type": "tool_result", "tool_use_id": "b", "content": "done", "is_error": False}]}},
            {"type": "user", "timestamp": "2026-10-06T02:00:00Z", "cwd": root, "message": {"content": "矢印がずれている"}},
        ]
        (folder / 'abc.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in rows))
        [a] = list(claude_sessions(root, '2026-10-06T00:00:00Z', home))
        assert a.built and a.opened['deck-practices/visual.md'] == 1 and a.title == '見本'
        assert [t for _, t in a.said] == ['文字をもっと大きく', '矢印がずれている']
        assert a.md(root).count("（確認のあと）") == 1 and "（確認のあと）: 「矢印がずれている」" in a.md(root)  # 確認が通ったあとの発言だけに印
        assert "- ユーザー 2026-10-06T02:00:00Z（確認のあと）" in a.md(root)  # 時刻は秒まで出す（--at に渡す）
        assert not is_dreaming(a.said) and is_dreaming([(ts, '…/skills/dreaming/SKILL.md を読み')])
        assert not is_dreaming([(ts, '資料を作って'), (ts, 'dreaming でこの指示を拾って')])
        assert not is_dreaming([(ts, '決まりの台帳と dreaming の流れを紹介する資料を作って')])
        assert all(is_dreaming([(ts, x)]) for x in ("スキル dreaming（Claude Code は /ai-deck-factory:dreaming）を読み", "/skill:dreaming", "dreaming の P0001 を適用して", "dreaming して"))
        folder = Path(home) / '.codex/sessions/2026/10/06'
        folder.mkdir(parents=True)
        rows = [{"type": "session_meta", "payload": {"id": "c", "cwd": root}}]
        for payload in [
            {"type": "message", "role": "user", "content": [{"text": "資料を作って"}]},
            {"type": "function_call", "name": "exec_command", "call_id": "r", "arguments": json.dumps({"cmd": 'cat ' + rule})},
            {"type": "function_call_output", "call_id": "r", "output": json.dumps({"exit_code": 0, "output": "rule"})},
            {"type": "function_call", "name": "exec_command", "call_id": "b", "arguments": json.dumps({"cmd": check + ' a.docx'})},
            {"type": "function_call_output", "call_id": "b", "output": json.dumps({"exit_code": 1, "output": "failed"})},
        ]:
            rows.append({"type": "response_item", "timestamp": ts, "payload": payload})
        (folder / 'rollout-test.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
        [a] = list(codex_sessions(root, '2026-10-06T00:00:00Z', home))
        assert not a.built and a.opened['deck-practices/visual.md'] == 1 and a.errors
        rows[0]["payload"]["thread_source"] = "guardian_review"
        (folder / 'rollout-guardian.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
        assert len(list(codex_sessions(root, '2026-10-06T00:00:00Z', home))) == 1  # 承認の審査の会話は数えない
        folder = Path(home) / '.ucode/pi-home/.pi/agent/sessions/--x-Documents--'
        folder.mkdir(parents=True)
        say = lambda role, content, at=ts: {"type": "message", "timestamp": at, "message": {"role": role, "content": content}}
        rows = [{"type": "session", "id": "p", "timestamp": ts, "cwd": root}, {"type": "session_info", "name": "見本"},
                say("user", [{"type": "text", "text": "資料を作って"}]),
                say("assistant", [{"type": "toolCall", "id": "r", "name": "read", "arguments": {"path": rule}},
                                  {"type": "toolCall", "id": "b", "name": "bash", "arguments": {"command": f'python3 {gs} check https://docs.google.com/presentation/d/x/edit'}}]),
                {"type": "message", "timestamp": ts, "message": {"role": "toolResult", "toolCallId": "r", "content": [{"type": "text", "text": "rules"}], "isError": False}},
                {"type": "message", "timestamp": ts, "message": {"role": "toolResult", "toolCallId": "b", "content": [{"type": "text", "text": "テキスト: a\n画像: b\nJSON: c"}], "isError": False}},
                say("user", "Delegated task node:x reached a terminal state.")]
        (folder / 'p.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in rows))
        rows[0] = {"type": "session", "id": "q", "timestamp": "2026-10-06T03:00:00Z", "cwd": root, "parentSession": str(folder / 'p.jsonl')}
        (folder / 'q.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in rows + [say("user", "続き", "2026-10-06T03:00:01Z")]))
        p, q = sorted(pi_sessions(root, '2026-10-06T00:00:00Z', home), key=lambda x: x.sid)
        assert p.built and p.opened['deck-practices/visual.md'] == 1 and p.title == '見本' and [t for _, t in p.said] == ['資料を作って']
        assert [t for _, t in q.said] == ['続き'] and not q.opened  # /fork の会話は、元の会話から写した行を数えない
        assert is_delegated([(ts, 'Act as the review sub-agent for this task. 日本語で')]) and not is_delegated(p.said)
    print("selftest ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--selftest"]:
        sys.exit(selftest())
    if "--since" not in args:
        sys.exit(__doc__)
    report(args[args.index("--root") + 1] if "--root" in args else ROOT, args[args.index("--since") + 1])
