import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssessmentCard } from "@/features/chat/components/AssessmentCard";
import type { Assessment } from "@/lib/api/types";

const sample: Assessment = {
  summary: "端口光模块劣化导致丢包",
  impact: "单条链路业务受影响",
  hypotheses: [
    {
      cause: "Gi1/0/24 光模块 RX 功率劣化",
      confidence: "high",
      evidence: ["RX -12.8 dBm，低于 -8 dBm 阈值"],
      falsification: "若更换后 RX 恢复则不成立",
    },
  ],
  recommendations: [
    { step: "隔离端口并更换光模块", risk: "high", requires_change: true, rollback: "no shutdown 恢复端口" },
  ],
  unknowns: ["对端端口光功率未采集"],
};

describe("AssessmentCard", () => {
  it("shows summary and expandable details", () => {
    render(<AssessmentCard assessment={sample} />);
    expect(screen.getByText("端口光模块劣化导致丢包")).toBeInTheDocument();
    expect(screen.getByText(/展开根因、证据与处置建议/)).toBeInTheDocument();
    expect(screen.getByText(/Gi1\/0\/24 光模块 RX 功率劣化/)).toBeInTheDocument();
    expect(screen.getByText(/需审批后执行/)).toBeInTheDocument();
  });
});
