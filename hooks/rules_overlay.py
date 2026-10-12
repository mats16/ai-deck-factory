#!/usr/bin/env python3
"""プラグインのスキルのファイルが読まれたら、ワークスペースの同じパスの rules/<スキル>/<ファイル> を続けて出す（開き忘れを防ぐ）。
決まりの層は skills/deck-practices/rules.md。Claude Code は hooks.json の PostToolUse（Read・Bash・Skill）、pi は extensions/rules.ts から呼ぶ。
usage: rules_overlay.py claude   （標準入力に Claude Code の hook の JSON）
       rules_overlay.py pi       （標準入力に {"cwd", "text"}。出力は {"context": …}）
       rules_overlay.py --selftest
標準ライブラリだけ。ワークスペース（factory.toml のあるフォルダ）の外や、rules/ がないときは何も出さない。"""
import json, re, sys, tempfile
from pathlib import Path

SKILLS = {p.parent.name for p in (Path(__file__).resolve().parent.parent / "skills").glob("*/SKILL.md")}
REF = re.compile(rf"(?<![\w-])({'|'.join(map(re.escape, SKILLS))})/([\w./-]+\.md)")  # スキルの名前で始まるパス（前のフォルダは問わない）
LIMIT = 20000  # 差し込む字数の上限（決まりが育ちすぎたら、AGENTS.md と同じく分ける合図）


def workspace(cwd):
    d = Path(cwd).resolve()
    return next((x for x in (d, *d.parents) if (x / "factory.toml").is_file()), None)


def overlays(cwd, text, skill=None):
    """text（読んだパスかコマンド）に出てくるプラグインのファイルに当たる、rules/ のファイルの中身。"""
    ws = workspace(cwd)
    if not ws or not (ws / "rules").is_dir():
        return ""
    refs = [(skill.split(":")[-1], "SKILL.md")] if skill else []
    for m in REF.finditer(text):
        if "rules/" + m.group(1) not in text[max(0, m.start() - 6):m.end()]:  # rules/ そのものを読んだときは出さない
            refs.append((m.group(1), m.group(2)))
    out, seen = [], set()
    for name, f in refs:
        p = ws / "rules" / name / f
        if p.is_file() and p not in seen:
            seen.add(p)
            out.append(f"## ワークスペースの決まり: rules/{name}/{f}\n\nプラグインの {name}/{f} への足しと上書き。食い違うところは、こちらに従う（deck-practices/rules.md の「決まりの層」）。\n\n{p.read_text()[:LIMIT]}")
    return "\n\n".join(out)[:LIMIT]


def main(mode):
    ev = json.load(sys.stdin)
    if mode == "pi":
        print(json.dumps({"context": overlays(ev.get("cwd", "."), ev.get("text", ""))}, ensure_ascii=False))
        return
    ti = ev.get("tool_input", {})
    ctx = overlays(ev.get("cwd", "."), ti.get("file_path") or ti.get("command") or "", ti.get("skill") if ev.get("tool_name") == "Skill" else None)
    if ctx:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}}, ensure_ascii=False))


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
        assert overlays("/", "/plug/skills/deck-practices/visual.md") == ""  # ワークスペースの外
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1] if sys.argv[1:] else "claude"))
