"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto grid min-h-[calc(100vh-56px)] max-w-[1440px] place-items-center px-4">
      <div className="rounded-card border border-line bg-surface p-8 text-center">
        <h1 className="text-lg font-semibold">页面加载失败</h1>
        <p className="mt-2 text-sm text-muted">请检查后端 8020 是否启动，然后重试。错误编号：{error.digest ?? "未知"}</p>
        <button
          type="button"
          onClick={reset}
          className="mt-5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white"
        >
          重试
        </button>
      </div>
    </main>
  );
}
