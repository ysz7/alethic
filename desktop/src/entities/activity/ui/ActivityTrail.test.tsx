import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ActivityEvent } from "../model/types";
import { ActivityTrail } from "./ActivityTrail";

const event = (extra: Partial<ActivityEvent> = {}): ActivityEvent => ({
  task_id: "t1",
  objective_id: "o1",
  kind: "TOOL_CALL",
  message: "files.write",
  step: 1,
  payload: {},
  at: "2026-09-08T09:00:00+00:00",
  ...extra,
});

describe("ActivityTrail", () => {
  it("shows nothing at all when nothing has happened", () => {
    const { container } = render(<ActivityTrail events={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the action the runtime announced, unchanged", () => {
    render(<ActivityTrail events={[event()]} />);
    expect(screen.getByText("files.write")).toBeInTheDocument();
  });

  it("marks what is waiting on the person", () => {
    render(<ActivityTrail events={[event({ kind: "APPROVAL", message: "send an email" })]} />);
    expect(screen.getByText("Waiting for you")).toBeInTheDocument();
  });
});
