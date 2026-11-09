import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "@/features/chat/components/Composer";

describe("Composer", () => {
  it("submits on Enter and disables while busy", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <Composer value="core-sw-01 丢包" onChange={() => undefined} onSubmit={onSubmit} disabled={false} />,
    );
    fireEvent.keyDown(screen.getByPlaceholderText(/描述告警或问题/), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);

    rerender(<Composer value="core-sw-01 丢包" onChange={() => undefined} onSubmit={onSubmit} disabled />);
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });
});
