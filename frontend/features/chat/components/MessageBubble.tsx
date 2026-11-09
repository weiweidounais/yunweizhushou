import type { Assessment, ChangePlan } from "@/lib/api/types";
import { AssessmentCard } from "@/features/chat/components/AssessmentCard";
import { ChangePlanCard } from "@/features/chat/components/ChangePlanCard";

export function MessageBubble({
  role,
  content,
  assessment,
  plan,
  note,
  planBusy = false,
  onApprove,
  onReject,
}: {
  role: "user" | "assistant";
  content: string;
  assessment?: Assessment | null;
  plan?: ChangePlan | null;
  note?: string | null;
  planBusy?: boolean;
  onApprove?: (planId: string) => void;
  onReject?: (planId: string) => void;
}) {
  if (role === "user") {
    return (
      <div className="flex justify-end gap-2">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-3.5 py-2.5 text-sm leading-6 text-white">
          {content}
        </div>
        <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-200 text-[10px] font-semibold text-slate-600">
          我
        </span>
      </div>
    );
  }
  return (
    <div className="flex gap-2">
      <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent-soft text-[10px] font-semibold text-accent">
        AI
      </span>
      <div className="min-w-0 max-w-[92%] space-y-2">
        {assessment ? <AssessmentCard assessment={assessment} /> : <p className="whitespace-pre-wrap text-sm leading-6">{content}</p>}
        {plan ? (
          <ChangePlanCard
            plan={plan}
            busy={planBusy}
            onApprove={onApprove ?? (() => undefined)}
            onReject={onReject ?? (() => undefined)}
          />
        ) : null}
        {note ? (
          <div className="rounded-lg border border-warn/30 bg-warn-soft p-3 text-xs leading-5 text-warn">
            {note}
          </div>
        ) : null}
      </div>
    </div>
  );
}
