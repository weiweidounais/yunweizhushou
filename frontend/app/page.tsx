"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { LoaderCircle, TriangleAlert } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api
      .createSession()
      .then((session) => router.replace(`/sessions/${session.id}`))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "创建会话失败，请重试。");
      });
  }, [router]);

  return (
    <main className="mx-auto grid min-h-[calc(100vh-56px)] max-w-[1440px] place-items-center px-4">
      <div className="w-full max-w-md rounded-card border border-line bg-surface p-8 text-center shadow-sm">
        {error ? (
          <>
            <TriangleAlert className="mx-auto h-6 w-6 text-bad" />
            <h1 className="mt-3 text-base font-semibold">工作台没起来</h1>
            <p className="mt-2 text-sm text-muted">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              重试
            </button>
          </>
        ) : (
          <>
            <LoaderCircle className="mx-auto h-6 w-6 animate-spin text-accent" />
            <h1 className="mt-3 text-base font-semibold">正在创建会话</h1>
            <p className="mt-2 text-sm text-muted">连上后端后会自动进入工作台。</p>
          </>
        )}
      </div>
    </main>
  );
}
