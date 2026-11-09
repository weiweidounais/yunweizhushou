import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChangePlanCard } from "@/features/chat/components/ChangePlanCard";
import type { ChangePlan } from "@/lib/api/types";

const pending: ChangePlan = {
  plan_id: "chg-123",
  session_id: "s1",
  asset_id: "core-sw-01",
  action: "isolate_port",
  params: { port: "Gi1/0/24" },
  reason: "光模块劣化",
  impact: "业务瞬断",
  rollback: "no shutdown 恢复",
  plan_hash: "abcdef1234567890",
  status: "pending_approval",
};

describe("ChangePlanCard", () => {
  it("asks for approval and calls callbacks", () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(<ChangePlanCard plan={pending} busy={false} onApprove={onApprove} onReject={onReject} />);
    expect(screen.getByText("待审批")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /批准/ }));
    fireEvent.click(screen.getByRole("button", { name: /拒绝/ }));
    expect(onApprove).toHaveBeenCalledWith("chg-123");
    expect(onReject).toHaveBeenCalledWith("chg-123");
  });

  it("shows execution and verification after approval", () => {
    render(
      <ChangePlanCard
        plan={{
          ...pending,
          status: "verified",
          execution: { summary: "已隔离端口（模拟）" },
          verification: { summary: "回读验证通过（模拟）", checks: ["Gi1/0/24 状态 down"] },
        }}
        busy={false}
        onApprove={() => undefined}
        onReject={() => undefined}
      />,
    );
    expect(screen.getByText("已回读验证")).toBeInTheDocument();
    expect(screen.getByText(/已隔离端口/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /批准/ })).not.toBeInTheDocument();
  });
});
