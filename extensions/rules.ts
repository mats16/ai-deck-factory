// pi の側のつなぎ: read・bash の結果に、ワークスペースの rules/ の同じパスのファイルを足す。中身は hooks/rules_overlay.py（Claude Code と共有）
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "..", "hooks", "rules_overlay.py");

export default function (pi: any) {
  pi.on("tool_result", (ev: any, ctx: any) => {
    if (ev.isError || !["read", "bash"].includes(ev.toolName)) return;
    const text = String(ev.input?.path ?? ev.input?.command ?? "");
    const r = spawnSync("python3", [SCRIPT, "pi"], { input: JSON.stringify({ cwd: ctx.cwd ?? process.cwd(), text }), encoding: "utf8", timeout: 5000 });
    let context = "";
    try { context = JSON.parse(r.stdout || "{}").context ?? ""; } catch { return; }
    if (context) return { content: [...ev.content, { type: "text", text: "\n\n" + context }] };
  });
}
