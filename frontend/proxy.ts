import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL;

export async function proxy(request: NextRequest) {
  if (!BACKEND_URL) {
    return NextResponse.json(
      { error: { code: "proxy_unconfigured", message: "BACKEND_URL 未配置" } },
      { status: 503 },
    );
  }
  const url = new URL(request.url);
  const target = BACKEND_URL.replace(/\/+$/, "") + url.pathname + url.search;
  const headers = new Headers(request.headers);
  headers.delete("host");
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const init: RequestInit & { duplex?: "half" } = { method: request.method, headers };
  if (body !== undefined) {
    init.body = body;
    init.duplex = "half";
  }
  const upstream = await fetch(target, init);
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}

export const config = { matcher: "/api/:path*" };
