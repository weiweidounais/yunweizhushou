import { describe, expect, it } from "vitest";
import { ApiError, normalizeErrorPayload } from "@/lib/api/client";

describe("error normalization", () => {
  it("uses backend error envelope", () => {
    const err = normalizeErrorPayload({ error: { code: "POLICY_DENIED", message: "禁止动作" } }, 403);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("POLICY_DENIED");
    expect(err.message).toBe("禁止动作");
    expect(err.status).toBe(403);
  });

  it("falls back to generic message", () => {
    const err = normalizeErrorPayload(null, 500);
    expect(err.code).toBe("HTTP_ERROR");
    expect(err.message).toContain("500");
  });
});
