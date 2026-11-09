import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto grid min-h-[calc(100vh-56px)] max-w-[1440px] place-items-center px-4">
      <div className="rounded-card border border-line bg-surface p-8 text-center">
        <h1 className="text-lg font-semibold">页面不存在</h1>
        <p className="mt-2 text-sm text-muted">会话可能已删除，或地址不正确。</p>
        <Link href="/" className="mt-5 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white">
          新建会话
        </Link>
      </div>
    </main>
  );
}
