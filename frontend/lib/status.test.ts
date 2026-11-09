import { describe, expect, it } from "vitest";
import { chatStateLabel, planStatusLabel, planUiState } from "@/lib/status";

describe("status mapping", () => {
  it("maps pending approval to waiting_user", () => {
    expect(planUiState("pending_approval")).toBe("waiting_user");
    expect(planStatusLabel("pending_approval")).toBe("待审批");
  });

  it("maps verified to succeeded and executing to running", () => {
    expect(planUiState("verified")).toBe("succeeded");
    expect(planUiState("executing")).toBe("running");
  });

  it("keeps unknown status safe", () => {
    expect(planUiState("something_new")).toBe("unknown");
    expect(planStatusLabel(undefined)).toBe("状态未知");
    expect(chatStateLabel("failed")).toBe("失败");
  });
});
