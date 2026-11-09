import { describe, expect, it } from "vitest";
import { actionLabel, formatSeconds, shortHash } from "@/lib/format";

describe("format helpers", () => {
  it("formats elapsed seconds", () => {
    expect(formatSeconds(6900)).toBe("6.9s");
    expect(formatSeconds(0)).toBe("0.0s");
  });

  it("formats action and hash", () => {
    expect(actionLabel("isolate_port")).toBe("隔离端口");
    expect(shortHash("1234567890abcdef")).toBe("1234567890abcd…");
  });
});
