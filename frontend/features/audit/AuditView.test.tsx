import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuditView } from "@/features/audit/AuditView";
import { api } from "@/lib/api/client";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AuditView", () => {
  it("shows chain status and records", async () => {
    vi.spyOn(api, "audit").mockResolvedValue({
      chain: { valid: true, checked: 1, broken_at: null },
      records: [
        {
          id: 1,
          ts: "2026-11-09 18:00:00",
          action: "change.proposed",
          target_type: "asset",
          target_id: "core-sw-01",
          plan_hash: "abcdef1234567890",
          approval_id: "",
          result: "ok",
          hash: "1234567890abcdef…",
        },
      ],
    });
    render(<AuditView />);
    expect(await screen.findByText("哈希链校验通过")).toBeInTheDocument();
    expect(screen.getByText("change.proposed")).toBeInTheDocument();
    expect(screen.getByText("core-sw-01")).toBeInTheDocument();
  });
});
