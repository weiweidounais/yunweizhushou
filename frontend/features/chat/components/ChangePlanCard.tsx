import Link from "next/link";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import type { ChangePlan } from "@/lib/api/types";
import { actionLabel, shortHash } from "@/lib/format";
import { planStatusLabel } from "@/lib/status";

function statusClass(status: string): string {
  if (status === "verified") return "bg-ok-soft text-ok";
  if (status === "succeeded" || status === "approved") return "bg-accent-soft text-accent";
  if (status === "pending_approval") return "bg-warn-soft text-warn";
  if (status === "rejected" || status === "failed" || status === "unknown") return "bg-bad-soft text-bad";
  return "bg-slate-100 text-slate-500";
}

export function ChangePlanCard({
  plan,
  busy,
  onApprove,
  onReject,
}: {
  plan: ChangePlan;
  busy: boolean;
  onApprove: (planId: string) => void;
  onReject: (planId: string) => void;
}) {
  const pending = plan.status === "pending_approval";
  return (
    <section className="rounded-lg border border-accent/30 bg-accent-soft/40 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-accent" />
        <h3 className="text-xs font-semibold text-ink">变更计划</h3>
        <span className={`rounded-full px-2 py-0.5 text-[10px] ${statusClass(plan.status)}`}>
          {planStatusLabel(plan.status)}
        </span>
        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-muted">模拟执行</span>
      </div>

      <div className="mt-2.5 grid gap-x-4 gap-y-1 text-[11px] leading-5 sm:grid-cols-2">
        <p><span className="text-muted">资产：</span>{plan.asset_id}</p>
        <p><span className="text-muted">动作：</span>{actionLabel(plan.action)}</p>
        <p className="sm:col-span-2"><span className="text-muted">参数：</span><code className="break-all">{JSON.stringify(plan.params)}</code></p>
        <p className="sm:col-span-2"><span className="text-muted">理由：</span>{plan.reason}</p>
        <p className="sm:col-span-2"><span className="text-muted">影响面：</span>{plan.impact || "-"}</p>
        <p className="sm:col-span-2"><span className="text-muted">回滚：</span>{plan.rollback || "-"}</p>
      </div>
      <p className="mt-2 text-[10px] text-muted">
        plan_hash {shortHash(plan.plan_hash)} · {plan.plan_id}
      </p>

      {pending ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onApprove(plan.plan_id)}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            <CheckCircle2 className="h-3.5 w-3.5" /> {busy ? "批准中…" : "批准"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onReject(plan.plan_id)}
            className="inline-flex items-center gap-1.5 rounded-md border border-bad/30 bg-white px-3 py-1.5 text-xs font-medium text-bad disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" /> 拒绝
          </button>
          <span className="self-center text-[10px] text-muted">批准后由确定性代码执行，不交给模型</span>
        </div>
      ) : null}

      {plan.execution?.summary || plan.verification?.summary ? (
        <div className="mt-3 space-y-1 rounded-md border border-line bg-white p-2.5 text-[11px] leading-5">
          {plan.execution?.summary ? <p><span className="text-muted">执行：</span>{plan.execution.summary}</p> : null}
          {plan.verification?.summary ? <p><span className="text-muted">回读：</span>{plan.verification.summary}</p> : null}
          {plan.verification?.checks?.length ? (
            <ul className="list-disc pl-4 text-muted">
              {plan.verification.checks.map((check) => <li key={check}>{check}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}

      {plan.status === "rejected" ? <p className="mt-2 text-[11px] text-bad">已拒绝，不会执行。</p> : null}
      <Link href="/audit" className="mt-2 inline-block text-[10px] text-accent underline-offset-2 hover:underline">
        查看审计记录
      </Link>
    </section>
  );
}
