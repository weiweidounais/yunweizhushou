import type { ToolCall } from "@/lib/api/types";
import { Wrench } from "lucide-react";

export function ToolCallList({ calls }: { calls: ToolCall[] }) {
  return (
    <section className="rounded-card border border-line bg-surface p-3">
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <Wrench className="h-3.5 w-3.5 text-muted" />
        <h2 className="text-xs font-semibold text-ink">工具调用</h2>
        <span className="ml-auto text-[10px] text-muted">{calls.length} 次</span>
      </div>
      {calls.length === 0 ? (
        <p className="py-6 text-center text-[11px] leading-5 text-muted">本轮还没有工具调用；<br />刷新后历史工具卡片不保留。</p>
      ) : (
        <div className="mt-2 space-y-2">
          {calls.map((call, i) => (
            <details key={`${call.name}-${i}`} className="rounded-md border border-line p-2">
              <summary className="cursor-pointer list-none">
                <div className="flex items-center gap-2">
                  <code className="text-[11px] font-medium text-ink">{call.name}</code>
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                      call.status === "ok" ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"
                    }`}
                  >
                    {call.status}
                  </span>
                  <span className="ml-auto text-[10px] text-muted">{call.duration_ms}ms</span>
                </div>
              </summary>
              <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-2 text-[10px] leading-4 text-slate-600">
                {JSON.stringify(call.args, null, 2)}
                {"\n\n"}
                {call.result_preview}
              </pre>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}
