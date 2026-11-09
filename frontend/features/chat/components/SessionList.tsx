"use client";

import Link from "next/link";
import { History } from "lucide-react";
import type { SessionSummary } from "@/lib/api/types";

function when(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function SessionList({
  sessions,
  currentId,
}: {
  sessions: SessionSummary[];
  currentId: string;
}) {
  return (
    <section className="rounded-card border border-line bg-surface p-3">
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <History className="h-3.5 w-3.5 text-muted" />
        <h2 className="text-xs font-semibold text-ink">最近会话</h2>
        <span className="ml-auto text-[10px] text-muted">{sessions.length}</span>
      </div>
      {sessions.length === 0 ? (
        <p className="py-4 text-[11px] text-muted">还没有历史会话</p>
      ) : (
        <div className="mt-2 space-y-1">
          {sessions.map((session) => {
            const active = session.id === currentId;
            return (
              <Link
                key={session.id}
                href={`/sessions/${session.id}`}
                className={`block rounded-md px-2.5 py-2 text-[11px] leading-4 transition ${
                  active ? "bg-accent-soft text-accent" : "text-ink hover:bg-slate-50"
                }`}
              >
                <span className="block truncate font-medium">{session.title || "新会话"}</span>
                <span className="mt-0.5 block text-[10px] text-muted">
                  {when(session.updated_at)} · {session.message_count} 条
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
