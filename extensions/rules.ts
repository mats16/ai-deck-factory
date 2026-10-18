// pi の側のつなぎ: read・bash の結果に、ワークスペースの rules/ の同じパスのファイルと、顧客の memory.md を足す。中身は hooks/rules_overlay.py（Claude Code と共有）
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "..", "hooks", "rules_overlay.py");

// 30 秒以上の sleep を止める（deck-practices-013）。子が終わっても、sleep が明けるまで親は通知を受け取れない。Claude Code は Bash の sleep を自分で止める
const SLEEP = /(?:^|[;&|(){}]|\bthen\b|\bdo\b)\s*sleep\s+(\d+(?:\.\d+)?)([smhd]?)\b/gm;  // 行の頭か区切りのあとの sleep。前に語のあるもの（nohup sleep・env sleep）と sleep $N は数えない。裏で回す sleep 60 & とヒアドキュメントの中の行も止める（見分けを簡単にするため）
const UNIT: Record<string, number> = { "": 1, s: 1, m: 60, h: 3600, d: 86400 };
const longestSleep = (cmd: string) => Math.max(0, ...[...cmd.matchAll(SLEEP)].map((m) => Number(m[1]) * UNIT[m[2]]));

export default function (pi: any) {
  pi.on("tool_call", (ev: any) => {
    if (ev.toolName === "bash" && longestSleep(String(ev.input?.command ?? "")) >= 30)
      return { block: true, reason: "sleep で待たない（deck-practices-013）。T3 Code の子を待つなら、子の結果によらない作業を進め、することがなくなったら t3_thread_wait で待つ（threadId・runId は delegate_task が返した childThreadId・childRunId、timeoutMs は 270000）。子が終わればすぐ返り、timedOut なら呼び直す。返ったら task_status で結果を読む。T3 を使っていなければ、子の道具が返るのを待つ" };
  });
  pi.on("tool_result", (ev: any, ctx: any) => {
    if (ev.isError || !["read", "bash"].includes(ev.toolName)) return;
    const text = String(ev.input?.path ?? ev.input?.command ?? "");
    const r = spawnSync("python3", [SCRIPT, "pi"], { input: JSON.stringify({ cwd: ctx.cwd ?? process.cwd(), text, isPath: ev.toolName === "read" }), encoding: "utf8", timeout: 5000 });
    let context = "";
    try { context = JSON.parse(r.stdout || "{}").context ?? ""; } catch { return; }
    if (context) return { content: [...ev.content, { type: "text", text: "\n\n" + context }] };
  });
}
