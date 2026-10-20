#!/usr/bin/env python3
"""プラグインのスキルのファイルが読まれたら、ワークスペースの同じパスの rules/<スキル>/<ファイル> を続けて出す（開き忘れを防ぐ）。
顧客の資料の 構成案*.md・社内メモ_*.md・references.md が読まれたら、その顧客の Customers/<顧客>/memory.md（資料への好み。どう作るか）を続けて出す。
/ai-deck-factory:<スキル>（Claude Code）・$ai-deck-factory:<スキル>（Codex）で呼んだスキルは、道具を使わずに SKILL.md が入るので、プロンプトから拾って rules/<スキル>/SKILL.md を出す。
決まりの層は skills/deck-practices/rules.md。Claude Code と Codex は hooks.json の PostToolUse（Read・Bash・Skill）と UserPromptSubmit、pi は extensions/rules.ts から呼ぶ。
usage: rules_overlay.py claude   （標準入力に Claude Code か Codex の hook の JSON）
       rules_overlay.py pi       （標準入力に {"cwd", "text", "isPath"}。isPath は text が読んだファイルのパスのとき。出力は {"context": …}）
       rules_overlay.py --selftest
標準ライブラリだけ。ワークスペース（factory.toml のあるフォルダ）の外や、rules/ と memory.md がないときは何も出さない。"""
import json, os, re, shlex, sys, tempfile
from pathlib import Path

SKILLS = {p.parent.name for p in (Path(__file__).resolve().parent.parent / "skills").glob("*/SKILL.md")}
REF = re.compile(rf"(?<![\w-])({'|'.join(map(re.escape, SKILLS))})/([\w./-]+\.md)")  # スキルの名前で始まるパス（前のフォルダは問わない）
MEMORY_FROM = re.compile(r"(?:^|/)(?:構成案[^/]*|社内メモ_[^/]*|references)\.md$")  # 資料を始めるときとコンパクションのあとに読むもの（組む途中に何度も開く build/ は入れない）
CALL = re.compile(rf"(?:^\s*/|(?<![\w$/.-])\$)ai-deck-factory:({'|'.join(map(re.escape, SKILLS))})(?![\w-])", re.ASCII)  # プロンプトで呼んだスキル（Claude Code の / は頭だけ、Codex の $ はどこでも。和文は続けて書いても呼んだことになる）
PUNCT = "();<>|&`"  # コマンドの区切り
LIMIT = 20000  # 差し込む字数の上限（決まりが育ちすぎたら、AGENTS.md と同じく分ける合図）


def workspace(cwd):
    d = Path(cwd).resolve()
    return next((x for x in (d, *d.parents) if (x / "factory.toml").is_file()), None)


def words(command):
    """コマンドの語。引用符の外の ; | & ( ) < > ` だけで区切る（引用符の中の空白や括弧はそのまま）。引用符が閉じていなければ、空白で切る。"""
    lex = shlex.shlex(command, posix=True, punctuation_chars=PUNCT)
    lex.whitespace_split, lex.commenters = True, ""  # # は語の中にも出る（deck#2）。コメントの語は、パスでなければ使わない
    try:
        return list(lex)
    except ValueError:
        return command.split()


def memories(ws, cwd, text, is_path=False):
    """text（読んだファイルのパスか、コマンド）に出てくる顧客の資料のファイル（絶対パスか、cwd からのパス。コマンドの中の cd もたどる）の、顧客の memory.md。"""
    top = str(ws / "Customers").lower() + "/"  # macOS は大文字と小文字を区別しない
    toks, base, outer, out = [text] if is_path else words(text), str(cwd), [], []  # パスは切らない（空白のあるフォルダ）
    for i, tok in enumerate(toks):
        if all(c in PUNCT for c in tok):  # 区切り（続いたものは 1 語になる。「);」など）。サブシェルの中の cd は、閉じたら戻す
            for c in tok:
                if c == "(":
                    outer.append(base)
                elif c == ")" and outer:
                    base = outer.pop()
        elif i and toks[i - 1] == "cd" and not tok.startswith("-"):  # cd -P などは追わない（引数のない cd の次は区切りで、上で外れる）
            base = os.path.join(base, os.path.expanduser(tok))
        elif MEMORY_FROM.search(tok):
            p = os.path.realpath(os.path.join(base, os.path.expanduser(tok)))  # Path.expanduser は ~user で例外を出す
            if p.lower().startswith(top) and "/" in p[len(top):]:
                out.append(ws / "Customers" / p[len(top):].split("/")[0] / "memory.md")
    return out


def overlays(cwd, text, skill=None, is_path=False):
    """text（読んだパスかコマンド）に出てくるプラグインのファイルに当たる rules/ のファイルと、顧客の資料に当たる memory.md の中身。"""
    ws = workspace(cwd)
    if not ws:
        return ""
    refs = [(skill.split(":")[-1], "SKILL.md")] if skill else []
    for m in REF.finditer(text):
        if "rules/" + m.group(1) not in text[max(0, m.start() - 6):m.end()]:  # rules/ そのものを読んだときは出さない
            refs.append((m.group(1), m.group(2)))
    mem, out, seen = [], [], set()
    for p in memories(ws, cwd, text, is_path):
        if p.is_file() and p not in seen:
            seen.add(p)
            mem.append(f"## 顧客の memory: {p.relative_to(ws)}\n\nこの顧客の資料への好み（どう作るか。相手の事業や構成は profile.md）。ワークスペースの決まりとプラグインより優先する。新しいユーザーの言葉と食い違えば、そちらに従って memory を直す（deck-practices/rules.md の「Customer memory」）。\n\n{p.read_text()}")
    for name, f in refs:
        p = ws / "rules" / name / f
        if p.is_file() and p not in seen:
            seen.add(p)
            out.append(f"## ワークスペースの決まり: rules/{name}/{f}\n\nプラグインの {name}/{f} への足しと上書き。食い違うところは、こちらに従う（deck-practices/rules.md の「Rule layers」）。\n\n{p.read_text()}")
    return "\n\n".join(x for x in (cut(out, "rules/ のファイルを"), cut(mem, "memory.md を")) if x)


def called(cwd, prompt):
    """プロンプトで呼んだスキル（/ai-deck-factory:<スキル>・$ai-deck-factory:<スキル>）に当たる rules/<スキル>/SKILL.md の中身。"""
    return "\n\n".join(filter(None, (overlays(cwd, "", s) for s in dict.fromkeys(CALL.findall(prompt)))))


def cut(parts, what):
    """決まりと memory は、それぞれ LIMIT 字まで（片方が長くても、もう片方を押し出さない）。"""
    text = "\n\n".join(parts)
    return text if len(text) <= LIMIT else text[:LIMIT] + f"\n\n（ここで切った。残りは {what}自分で開いて読む。{LIMIT} 字を超えたので、dreaming で分ける）"


def main(mode):
    ev = json.load(sys.stdin)
    if mode == "pi":
        print(json.dumps({"context": overlays(ev.get("cwd", "."), ev.get("text", ""), is_path=bool(ev.get("isPath")))}, ensure_ascii=False))
        return
    cwd, ti, event = ev.get("cwd", "."), ev.get("tool_input", {}), ev.get("hook_event_name", "PostToolUse")
    if event == "UserPromptSubmit":
        ctx = called(cwd, ev.get("prompt", ""))
    else:
        ctx = overlays(cwd, ti.get("file_path") or ti.get("command") or "", ti.get("skill") if ev.get("tool_name") == "Skill" else None,
                       is_path=bool(ti.get("file_path")))
    if ctx:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False))


def selftest():
    with tempfile.TemporaryDirectory() as ws:
        (Path(ws) / "factory.toml").write_text("")
        (Path(ws) / "rules" / "deck-practices").mkdir(parents=True)
        (Path(ws) / "rules" / "deck-practices" / "visual.md").write_text("本文は 16pt")
        (Path(ws) / "rules" / "deck-practices" / "SKILL.md").write_text("最初に聞くこと")
        sub = Path(ws) / "Customers" / "x"
        sub.mkdir(parents=True)
        assert "16pt" in overlays(sub, "/plug/skills/deck-practices/visual.md")
        assert "16pt" in overlays(ws, "sed -n 1,40p deck-practices/visual.md")  # Bash で読んだとき
        assert overlays(ws, f"{ws}/rules/deck-practices/visual.md") == ""  # rules/ そのものを読んだときは出さない
        assert overlays(ws, "/plug/skills/deck-practices/content.md") == ""  # rules/ に同じファイルがない
        assert "最初に聞くこと" in overlays(ws, "", "ai-deck-factory:deck-practices")
        assert CALL.findall("/ai-deck-factory:deck-build と $ai-deck-factory:deck-review、ai-deck-factory:doc-build、$ai-deck-factory:deck-builds") == ["deck-build", "deck-review"]  # 呼んだものだけ
        assert CALL.findall("さっきの /ai-deck-factory:deck-build は x/$ai-deck-factory:doc-build") == []  # 文の途中の / とパスの中は呼んでいない
        assert CALL.findall("資料を$ai-deck-factory:deck-buildで作る") == ["deck-build"] and CALL.findall("/ai-deck-factory:doc-buildで") == ["doc-build"]  # 和文が続いても切る
        assert "最初に聞くこと" in called(ws, "/ai-deck-factory:deck-practices を回して") and called(ws, "$ai-deck-factory:deck-build") == ""  # rules/ に SKILL.md のないスキル
        assert called(ws, "/ai-deck-factory:deck-practices $ai-deck-factory:deck-practices").count("最初に聞くこと") == 1
        assert overlays("/", "/plug/skills/deck-practices/visual.md") == ""  # ワークスペースの外
        deck = Path(ws) / "Customers" / "acme" / "deck_202610"
        deck.mkdir(parents=True)
        (Path(ws) / "Customers" / "acme" / "memory.md").write_text("- [ws-memory-001] 敬称は様")
        assert "敬称は様" in overlays(ws, f"{deck}/構成案.md")
        assert "敬称は様" in overlays(deck, "cat 社内メモ_経緯.md references.md")  # 資料のフォルダからの相対パス
        assert overlays(ws, f"{deck}/構成案.md references.md").count("敬称は様") == 1  # 同じ顧客は 1 回
        assert "敬称は様" in overlays(ws, f"{str(deck).replace('Customers', 'customers')}/構成案.md")
        assert overlays(ws, f"{deck}/build/pages.py") == "" and overlays(ws, f"{deck.parent}/memory.md") == ""  # 組む途中と memory そのものは出さない
        assert overlays(sub, "構成案.md") == ""  # memory.md のない顧客
        spaced = Path(ws) / "Customers" / "Acme Corp"
        (spaced / "d 1").mkdir(parents=True)
        (spaced / "memory.md").write_text("- [ws-memory-002] 略称は ACME")
        assert "ACME" in overlays(ws, f"{spaced}/d 1/構成案.md", is_path=True)  # 空白のあるフォルダは、パスを切らない
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/d 1/社内メモ_x.md'; ls")  # 引用符の中の空白
        assert "ACME" not in overlays(ws, "cat Customers/Acme Corp/d 1/構成案.md")  # 引用符がなければ別の語（シェルと同じ）
        (spaced / "資料(1)").mkdir()
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/資料(1)/構成案.md'|head")  # 引用符の中の括弧は切らない
        (spaced / "deck#2").mkdir()
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/deck#2/構成案.md'") and "ACME" in overlays(ws, "cd 'Customers/Acme Corp/d 1' && cat 構成案.md")  # # と cd
        assert "ACME" in overlays(ws, "(cd /tmp && ls); cd -P x; cd; cat 'Customers/Acme Corp/d 1/構成案.md'")  # サブシェル・cd -P・引数のない cd
        assert "ACME" not in overlays(ws, "cat ~nosuchuser/構成案.md") and "ACME" in overlays(ws, "cat 'Customers/Acme Corp/x/../d 1/references.md'")  # ~user で落ちない、.. を畳む
        (spaced / "memory.md").write_text("い" * (LIMIT + 10))
        both = overlays(ws, f"cat '{spaced}/d 1/構成案.md' deck-practices/visual.md")
        assert "本文は 16pt" in both and "残りは memory.md を" in both  # 長い memory が決まりを押し出さない
        (Path(ws) / "rules" / "deck-practices" / "visual.md").write_text("あ" * (LIMIT + 10))
        assert "ここで切った" in overlays(ws, "deck-practices/visual.md")  # 切ったら黙らない
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1] if sys.argv[1:] else "claude"))
