"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { DemoCase } from "@/lib/api/types";
import { FlaskConical } from "lucide-react";

export function SamplePanel({ onPick }: { onPick: (question: string) => void }) {
  const [cases, setCases] = useState<DemoCase[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .demoCases()
      .then((data) => setCases(data.cases ?? []))
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "示例加载失败"));
  }, []);

  return (
    <section className="rounded-card border border-line bg-surface p-3">
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <FlaskConical className="h-3.5 w-3.5 text-muted" />
        <h2 className="text-xs font-semibold text-ink">示例告警</h2>
      </div>
      {error ? <p className="py-5 text-[11px] text-bad">{error}</p> : null}
      {!error && cases.length === 0 ? <p className="py-5 text-[11px] text-muted">加载中…</p> : null}
      <div className="mt-2 space-y-1.5">
        {cases.slice(0, 4).map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onPick(item.question)}
            className="w-full rounded-md border border-line px-2.5 py-2 text-left text-[11px] leading-5 text-ink transition hover:border-accent hover:bg-accent-soft"
          >
            {item.question}
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onPick("帮我隔离 core-sw-01 的 Gi1/0/24 端口，理由：光模块劣化导致端口抖动")}
        className="mt-2 w-full rounded-md border border-accent/30 bg-accent-soft px-2.5 py-2 text-left text-[11px] leading-5 text-accent transition hover:border-accent"
      >
        变更演示：隔离 core-sw-01 的 Gi1/0/24
      </button>
      <p className="mt-3 text-[10px] leading-4 text-muted">演示数据是模拟的，不连接真实监控；不要把真实密钥/生产数据贴进来。</p>
    </section>
  );
}
