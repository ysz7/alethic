import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RequestComposer } from "./RequestComposer";

describe("RequestComposer", () => {
  it("sends what was typed and clears the field", async () => {
    const onSend = vi.fn();
    render(<RequestComposer onSend={onSend} />);
    const field = screen.getByLabelText("Tell Prometheus what you need");

    await userEvent.type(field, "Find three papers on X{Enter}");

    expect(onSend).toHaveBeenCalledWith("Find three papers on X");
    expect(field).toHaveValue("");
  });

  it("breaks the line on shift-enter instead of sending", async () => {
    const onSend = vi.fn();
    render(<RequestComposer onSend={onSend} />);

    await userEvent.type(
      screen.getByLabelText("Tell Prometheus what you need"),
      "first{Shift>}{Enter}{/Shift}second",
    );

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not send an empty request", async () => {
    const onSend = vi.fn();
    render(<RequestComposer onSend={onSend} />);

    await userEvent.type(screen.getByLabelText("Tell Prometheus what you need"), "   {Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });
});
