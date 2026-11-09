export type UiState = "idle" | "submitting" | "running" | "succeeded" | "failed" | "cancelled";

export type PlanUiState = "waiting_user" | "approved" | "running" | "succeeded" | "failed" | "rejected" | "unknown";

export function planUiState(status: string | undefined | null): PlanUiState {
  switch (status) {
    case "pending_approval":
      return "waiting_user";
    case "approved":
      return "approved";
    case "executing":
      return "running";
    case "succeeded":
    case "verified":
      return "succeeded";
    case "rejected":
      return "rejected";
    case "failed":
    case "unknown":
      return status === "failed" ? "failed" : "unknown";
    default:
      return "unknown";
  }
}

export function planStatusLabel(status: string | undefined | null): string {
  const map: Record<string, string> = {
    pending_approval: "待审批",
    approved: "已批准",
    executing: "执行中",
    succeeded: "已执行，待回读",
    verified: "已回读验证",
    rejected: "已拒绝",
    failed: "失败",
    unknown: "状态未知",
  };
  return status ? map[status] ?? "状态未知" : "状态未知";
}

export function chatStateLabel(state: UiState): string {
  const map: Record<UiState, string> = {
    idle: "待开始",
    submitting: "提交中",
    running: "诊断中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已停止",
  };
  return map[state];
}
