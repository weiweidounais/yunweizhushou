"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, LoaderCircle, RefreshCw, ShieldCheck, ShieldX } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import type { AuditResponse } from "@/lib/api/types";

export function AuditView() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.audit(100));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "审计加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    api
      .audit(100)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : "审计加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto max-w-[1440px] px-3 py-4 sm:px-6">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Link href="/" className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs text-muted hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> 工作台
        </Link>
        <div>
          <h1 className="text-base font-semibold">审计记录</h1>
          <p className="text-[11px] text-muted">变更、审批、执行、回读的追加记录与哈希链校验。</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs text-muted hover:text-ink disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
        </button>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center gap-2 rounded-card border border-line bg-surface py-16 text-sm text-muted">
          <LoaderCircle className="h-4 w-4 animate-spin" /> 正在读取审计…
        </div>
      ) : null}

      {error ? (
        <div className="rounded-card border border-bad/30 bg-bad-soft p-4 text-sm text-bad">
          {error}
          <button type="button" onClick={() => void load()} className="ml-2 underline">重试</button>
        </div>
      ) : null}

      {data ? (
        <>
          <div className={`mb-3 flex flex-wrap items-center gap-2 rounded-card border p-3 text-xs ${
            data.chain.valid ? "border-ok/30 bg-ok-soft text-ok" : "border-bad/30 bg-bad-soft text-bad"
          }`}>
            {data.chain.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
            {data.chain.valid ? "哈希链校验通过" : `哈希链断在 #${data.chain.broken_at}`}
            <span className="text-muted">共 {data.chain.checked} 条</span>
          </div>

          {data.records.length === 0 ? (
            <div className="rounded-card border border-dashed border-line bg-surface py-16 text-center text-sm text-muted">
              还没有审计记录。先在工作台完成一次变更。
            </div>
          ) : (
            <div className="overflow-x-auto rounded-card border border-line bg-surface">
              <table className="w-full min-w-[900px] border-collapse text-left text-[11px]">
                <thead className="bg-slate-50 text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">时间</th>
                    <th className="px-3 py-2 font-medium">动作</th>
                    <th className="px-3 py-2 font-medium">对象</th>
                    <th className="px-3 py-2 font-medium">结果</th>
                    <th className="px-3 py-2 font-medium">plan_hash</th>
                    <th className="px-3 py-2 font-medium">approval</th>
                    <th className="px-3 py-2 font-medium">hash</th>
                  </tr>
                </thead>
                <tbody>
                  {data.records.map((record) => (
                    <tr key={record.id} className="border-t border-line">
                      <td className="whitespace-nowrap px-3 py-2 text-muted">{record.ts}</td>
                      <td className="whitespace-nowrap px-3 py-2 font-medium">{record.action}</td>
                      <td className="px-3 py-2">{record.target_id || "-"}</td>
                      <td className="px-3 py-2">{record.result}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-muted">{record.plan_hash ? `${record.plan_hash.slice(0, 12)}…` : "-"}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-muted">{record.approval_id || "-"}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-muted">{record.hash}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </main>
  );
}
