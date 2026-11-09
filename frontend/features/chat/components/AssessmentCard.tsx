import type { Assessment } from "@/lib/api/types";

const confidenceLabel: Record<string, string> = { high: "高", medium: "中", low: "低" };
const riskLabel: Record<string, string> = { high: "高", medium: "中", low: "低" };

function confidenceClass(value: string): string {
  if (value === "high") return "bg-ok-soft text-ok";
  if (value === "low") return "bg-slate-100 text-slate-500";
  return "bg-warn-soft text-warn";
}

export function AssessmentCard({ assessment }: { assessment: Assessment }) {
  const hypotheses = assessment.hypotheses ?? [];
  const recommendations = assessment.recommendations ?? [];
  const unknowns = assessment.unknowns ?? [];
  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-line bg-white p-3.5">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">结论</h3>
        <p className="mt-1.5 text-sm leading-6 text-ink">{assessment.summary}</p>
        {assessment.impact ? <p className="mt-2 text-xs leading-5 text-muted">影响面：{assessment.impact}</p> : null}
      </section>

      <details className="group rounded-lg border border-line bg-white p-3.5">
        <summary className="cursor-pointer list-none text-xs font-medium text-muted marker:hidden">
          <span className="group-open:hidden">
            展开根因、证据与处置建议（{hypotheses.length} 条假设 / {recommendations.length} 条建议）
          </span>
          <span className="hidden group-open:inline">收起详情</span>
        </summary>
        <div className="mt-3 space-y-3">
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">根因假设</h3>
            <div className="mt-2 space-y-2.5">
              {hypotheses.map((h, i) => (
                <div key={`${h.cause}-${i}`} className="rounded-md border border-line p-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="text-xs font-semibold text-ink">
                      {i + 1}. {h.cause}
                    </b>
                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${confidenceClass(h.confidence)}`}>
                      置信度 {confidenceLabel[h.confidence] ?? h.confidence}
                    </span>
                  </div>
                  {h.evidence.length ? (
                    <ul className="mt-1.5 list-disc space-y-1 pl-4 text-[11px] leading-5 text-muted">
                      {h.evidence.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-[11px] text-muted">（未给证据）</p>
                  )}
                  {h.falsification ? <p className="mt-1.5 text-[11px] text-muted">反证/排除：{h.falsification}</p> : null}
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">处置建议</h3>
            <div className="mt-2 space-y-2.5">
              {recommendations.map((r, i) => (
                <div key={`${r.step}-${i}`} className="rounded-md border border-line p-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="text-xs font-semibold text-ink">
                      {i + 1}. {r.step}
                    </b>
                    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                      风险 {riskLabel[r.risk] ?? r.risk}
                    </span>
                    {r.requires_change ? <span className="text-[10px] text-warn">需审批后执行</span> : null}
                  </div>
                  {r.rollback ? <p className="mt-1 text-[11px] text-muted">回滚：{r.rollback}</p> : null}
                </div>
              ))}
            </div>
          </div>

          {unknowns.length ? (
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">不确定项 / 还需要的数据</h3>
              <ul className="mt-1.5 list-disc space-y-1 pl-4 text-[11px] leading-5 text-muted">
                {unknowns.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </details>
    </div>
  );
}
