"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ShieldCheck } from "lucide-react";

const links = [
  { href: "/", label: "工作台" },
  { href: "/audit", label: "审计" },
];

export function AppHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-brand-soft bg-brand text-white">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-xs font-extrabold tracking-tighter text-brand">
            FY
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-semibold">数据中心运维助理</span>
            <span className="block text-[11px] text-slate-400">诊断 · 变更审批 · 审计</span>
          </span>
        </Link>
        <nav className="ml-2 flex items-center gap-1">
          {links.map((link) => {
            const active = link.href === "/" ? pathname === "/" || pathname.startsWith("/sessions") : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-2.5 py-1.5 text-xs transition ${
                  active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto hidden items-center gap-3 text-[11px] text-slate-400 sm:flex">
          <span className="inline-flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-emerald-400" />
            本地 · 模拟数据
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-soft bg-brand-soft px-2.5 py-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            审批后执行
          </span>
        </div>
      </div>
    </header>
  );
}
