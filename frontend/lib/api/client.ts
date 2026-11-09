import type {
  ApprovalResponse,
  AuditResponse,
  ChatResponse,
  DemoCase,
  SessionSummary,
  SessionView,
} from "@/lib/api/types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code = "UNKNOWN", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

type ErrorEnvelope = {
  error?: { code?: string; message?: string };
  detail?: string;
};

export function normalizeErrorPayload(payload: unknown, status: number): ApiError {
  if (payload && typeof payload === "object") {
    const env = payload as ErrorEnvelope;
    if (env.error?.message) {
      return new ApiError(env.error.message, env.error.code ?? "UNKNOWN", status);
    }
    if (typeof env.detail === "string") {
      return new ApiError(env.detail, "HTTP_ERROR", status);
    }
  }
  return new ApiError(`请求失败（HTTP ${status}）`, "HTTP_ERROR", status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("连不上后端，请确认 8020 服务已启动。", "NETWORK_ERROR", 0);
  }
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw normalizeErrorPayload(payload, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; model_configured: boolean; model: string }>("/api/health"),
  createSession: (title = "新会话") =>
    request<SessionView>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  listSessions: (limit = 10) =>
    request<{ sessions: SessionSummary[] }>(`/api/sessions?limit=${limit}`),
  getSession: (id: string) => request<SessionView>(`/api/sessions/${encodeURIComponent(id)}`),
  chat: (id: string, message: string, signal?: AbortSignal) =>
    request<ChatResponse>(`/api/sessions/${encodeURIComponent(id)}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
      signal,
    }),
  demoCases: () => request<{ cases: DemoCase[] }>("/api/demo/cases"),
  approveChange: (planId: string, comment = "界面批准") =>
    request<ApprovalResponse>(`/api/changes/${encodeURIComponent(planId)}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  rejectChange: (planId: string, reason = "界面拒绝") =>
    request<{ plan: unknown }>(`/api/changes/${encodeURIComponent(planId)}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  audit: (limit = 50) => request<AuditResponse>(`/api/audit?limit=${limit}`),
};
