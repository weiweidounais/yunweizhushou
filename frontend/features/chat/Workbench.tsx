"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ClipboardList, LoaderCircle, Menu, Plus, ShieldCheck, Square, X } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import type { Assessment, ChangePlan, ChatResponse, SessionSummary, ToolCall, Usage } from "@/lib/api/types";
import { chatStateLabel, type UiState } from "@/lib/status";
import { formatSeconds, formatTokens } from "@/lib/format";
import { ChangePlanCard } from "@/features/chat/components/ChangePlanCard";
import { Composer } from "@/features/chat/components/Composer";
import { MessageBubble } from "@/features/chat/components/MessageBubble";
import { SamplePanel } from "@/features/chat/components/SamplePanel";
import { SessionList } from "@/features/chat/components/SessionList";
import { ToolCallList } from "@/features/chat/components/ToolCallList";

type UiMessage = {
  key: string;
  role: "user" | "assistant";
  content: string;
  assessment?: Assessment | null;
  plan?: ChangePlan | null;
  note?: string | null;
};

function statusClass(state: UiState): string {
  if (state === "failed") return "bg-bad-soft text-bad";
  if (state === "running" || state === "submitting") return "bg-warn-soft text-warn";
  if (state === "succeeded") return "bg-ok-soft text-ok";
  if (state === "cancelled") return "bg-slate-100 text-slate-500";
  return "bg-slate-100 text-slate-500";
}

export function Workbench({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [title, setTitle] = useState("新会话");
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<UiState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [tools, setTools] = useState<ToolCall[]>([]);
  const [usage, setUsage] = useState<Usage>({});
  const [elapsed, setElapsed] = useState(0);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);
  const [samplesOpen, setSamplesOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [restoredPlan, setRestoredPlan] = useState<ChangePlan | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getSession(sessionId)
      .then((session) => {
        if (!alive) return;
        setTitle(session.title || "新会话");
        setMessages(
          (session.messages ?? []).map((m) => ({
            key: `history-${m.id}`,
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
            assessment: m.assessment ?? null,
            plan: null,
          })),
        );
        setRestoredPlan(session.latest_change_plan ?? null);
        setState(session.messages?.length ? "succeeded" : "idle");
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof ApiError ? err.message : "会话加载失败");
        setState("failed");
      });
    return () => {
      alive = false;
    };
  }, [sessionId]);

  useEffect(() => {
    let alive = true;
    api
      .listSessions(8)
      .then((data) => {
        if (alive) setSessions(data.sessions ?? []);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, busy, restoredPlan]);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || busy) return;
      const question = text.trim();
      setInput("");
      setLastQuestion(question);
      if (title === "新会话") setTitle(question.slice(0, 40));
      setError(null);
      setBusy(true);
      setState("running");
      setTools([]);
      setUsage({});
      setElapsed(0);
      setMessages((current) => [...current, { key: `user-${Date.now()}`, role: "user", content: question }]);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const response: ChatResponse = await api.chat(sessionId, question, controller.signal);
        if (response.change_plan) setRestoredPlan(null);
        const note = response.warnings?.length ? `注意：${response.warnings.join("；")}` : null;
        setMessages((current) => [
          ...current,
          {
            key: `assistant-${Date.now()}`,
            role: "assistant",
            content: response.reply,
            assessment: response.assessment ?? null,
            plan: response.change_plan ?? null,
            note,
          },
        ]);
        setTools(response.tool_calls ?? []);
        setUsage(response.usage ?? {});
        setElapsed(response.elapsed_ms ?? 0);
        setState("succeeded");
      } catch (err: unknown) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        if (aborted) {
          setState("cancelled");
          setMessages((current) => [
            ...current,
            {
              key: `assistant-cancelled-${Date.now()}`,
              role: "assistant",
              content: "已停止等待。后端可能仍在执行，刷新会话可查看最新结果。",
              plan: null,
            },
          ]);
        } else {
          const message = err instanceof ApiError ? err.message : "请求失败，请重试。";
          setError(message);
          setState("failed");
          setMessages((current) => [
            ...current,
            { key: `assistant-error-${Date.now()}`, role: "assistant", content: `这次没查成：${message}`, plan: null },
          ]);
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [busy, sessionId, title],
  );

  const handleApprove = useCallback(
    async (planId: string) => {
      if (busy || busyPlanId) return;
      setBusyPlanId(planId);
      setError(null);
      try {
        await api.approveChange(planId);
        setMessages((current) =>
          current.map((message) =>
            message.plan?.plan_id === planId && message.plan
              ? { ...message, plan: { ...message.plan, status: "approved" } }
              : message,
          ),
        );
        setRestoredPlan((current) =>
          current?.plan_id === planId ? { ...current, status: "approved" } : current,
        );
        await send(`已批准 plan_id=${planId}，请执行并回读验证。`);
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : "批准失败，请重试。");
      } finally {
        setBusyPlanId(null);
      }
    },
    [busy, busyPlanId, send],
  );

  const handleReject = useCallback(
    async (planId: string) => {
      if (busy || busyPlanId) return;
      setBusyPlanId(planId);
      setError(null);
      try {
        await api.rejectChange(planId);
        setMessages((current) =>
          current.map((message) =>
            message.plan?.plan_id === planId && message.plan
              ? { ...message, plan: { ...message.plan, status: "rejected" } }
              : message,
          ),
        );
        setRestoredPlan((current) =>
          current?.plan_id === planId ? { ...current, status: "rejected" } : current,
        );
        setMessages((current) => [
          ...current,
          { key: `reject-${Date.now()}`, role: "assistant", content: `已拒绝变更计划 ${planId}，不会执行。`, plan: null },
        ]);
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : "拒绝失败，请重试。");
      } finally {
        setBusyPlanId(null);
      }
    },
    [busy, busyPlanId],
  );

  const handlePick = (question: string) => {
    setInput(question);
    setSamplesOpen(false);
  };

  return (
    <main className="mx-auto flex h-[calc(100vh-56px)] max-w-[1440px] gap-3 px-3 py-3 sm:px-4">
      <aside className="hidden w-56 shrink-0 space-y-3 overflow-y-auto lg:block">
        <SessionList sessions={sessions} currentId={sessionId} />
        <SamplePanel onPick={handlePick} />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-line bg-surface">
        <header className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-2.5 sm:px-4">
          <button
            type="button"
            onClick={() => setSamplesOpen(true)}
            className="grid h-8 w-8 place-items-center rounded-md border border-line text-muted lg:hidden"
            aria-label="打开示例"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold">{title}</h1>
            <p className="text-[10px] text-muted">会话 {sessionId.slice(0, 8)} · 诊断 · 变更审批</p>
          </div>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] ${statusClass(state)}`}>{chatStateLabel(state)}</span>
          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <Link
              href="/audit"
              className="hidden items-center gap-1 rounded-md border border-line px-2 py-1.5 text-[11px] text-muted hover:text-ink sm:inline-flex"
            >
              <ClipboardList className="h-3.5 w-3.5" /> 审计
            </Link>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1.5 text-[11px] text-muted hover:text-ink"
            >
              <Plus className="h-3.5 w-3.5" /> 新会话
            </button>
          </div>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-4 sm:px-5">
          {messages.length === 0 && !busy && !restoredPlan ? (
            <div className="mx-auto mt-10 max-w-md rounded-card border border-dashed border-line bg-slate-50 p-6 text-center">
              <ShieldCheck className="mx-auto h-6 w-6 text-accent" />
              <h2 className="mt-2 text-sm font-semibold">从一个告警或变更开始</h2>
              <p className="mt-1.5 text-xs leading-5 text-muted">
                描述现象、设备或时间范围；我会查资产、指标、告警、拓扑和 runbook，再给结论与证据。需要变更时先出计划，由你批准后执行。
              </p>
              <button
                type="button"
                onClick={() =>
                  handlePick("core-sw-01 昨晚 22:00 开始丢包，什么原因？")
                }
                className="mt-4 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white"
              >
                试一条示例
              </button>
            </div>
          ) : null}

          {messages.map((message) => (
            <MessageBubble
              key={message.key}
              role={message.role}
              content={message.content}
              assessment={message.assessment}
              plan={message.plan}
              note={message.note}
              planBusy={busyPlanId === message.plan?.plan_id}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}

          {restoredPlan ? (
            <div className="pl-9">
              <ChangePlanCard
                plan={restoredPlan}
                busy={busyPlanId === restoredPlan.plan_id}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            </div>
          ) : null}

          {busy ? (
            <div className="flex gap-2">
              <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent-soft text-[10px] font-semibold text-accent">
                AI
              </span>
              <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-line bg-slate-50 px-3 py-2 text-xs text-muted">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                正在查指标、告警、拓扑和 runbook…
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="ml-1 inline-flex items-center gap-1 rounded border border-line bg-white px-1.5 py-0.5 text-[10px] text-muted hover:text-ink"
                  aria-label="停止等待"
                >
                  <Square className="h-2.5 w-2.5" /> 停止
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="flex shrink-0 items-center gap-2 border-t border-bad/20 bg-bad-soft px-4 py-2 text-xs text-bad">
            <span className="min-w-0 flex-1">{error}</span>
            <button
              type="button"
              onClick={() => {
                if (lastQuestion) void send(lastQuestion);
                else window.location.reload();
              }}
              className="shrink-0 rounded border border-bad/30 bg-white px-2 py-1 text-[10px]"
            >
              重试
            </button>
          </div>
        ) : null}
        <Composer value={input} onChange={setInput} onSubmit={() => send(input)} disabled={busy} />
        {(usage.total_tokens ?? 0) > 0 ? (
          <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-1.5 text-[10px] text-muted sm:px-4">
            <span>模型 {usage.model || "-"}</span>
            <span>用时 {formatSeconds(elapsed)}</span>
            <span>tokens {formatTokens(usage.total_tokens)}</span>
            <span className="hidden sm:inline">模拟数据 · 不碰真实设备</span>
          </div>
        ) : null}
      </section>

      <aside className="hidden w-72 shrink-0 xl:block">
        <ToolCallList calls={tools} />
      </aside>

      {samplesOpen ? (
        <div className="fixed inset-0 z-40 bg-slate-900/35 lg:hidden" onClick={() => setSamplesOpen(false)}>
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-bg p-3 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={() => setSamplesOpen(false)}
                className="grid h-8 w-8 place-items-center rounded-md border border-line bg-white text-muted"
                aria-label="关闭示例"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <SessionList sessions={sessions} currentId={sessionId} />
            <div className="mt-3">
              <SamplePanel onPick={handlePick} />
            </div>
          </div>
        </div>
      ) : null}

    </main>
  );
}
