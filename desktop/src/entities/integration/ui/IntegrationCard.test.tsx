import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Capability, Integration } from "../model/types";
import { CapabilityList } from "./CapabilityList";
import { IntegrationCard } from "./IntegrationCard";

const capability = (extra: Partial<Capability> = {}): Capability => ({
  name: "search_notes",
  qualified_name: "notes.search_notes",
  description: "Search the notes.",
  effect: "READ",
  risk: "LOW",
  requires_approval: false,
  classified: true,
  ...extra,
});

const integration = (extra: Partial<Integration> = {}): Integration => ({
  id: "i1",
  name: "notes",
  kind: "MCP",
  status: "READY",
  enabled: true,
  usable: true,
  capabilities: ["EMAIL"],
  secrets: [],
  tool_count: 1,
  tools: [capability()],
  ...extra,
});

describe("IntegrationCard", () => {
  it("shows the status the runtime gave it, without restating it", () => {
    render(<IntegrationCard integration={integration()} />);

    expect(screen.getByText("notes")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText(/offers EMAIL/)).toBeInTheDocument();
  });

  it("names the credentials it needs and never a value", () => {
    render(<IntegrationCard integration={integration({ secrets: ["NOTES_TOKEN"] })} />);

    expect(screen.getByText("needs NOTES_TOKEN")).toBeInTheDocument();
  });

  it("has no actions until a feature hands it some", () => {
    render(<IntegrationCard integration={integration()} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("CapabilityList", () => {
  it("marks what asks first, as the runtime decided it", () => {
    render(
      <CapabilityList
        tools={[
          capability(),
          capability({
            name: "send_note",
            qualified_name: "notes.send_note",
            effect: "SEND",
            risk: "HIGH",
            requires_approval: true,
          }),
        ]}
      />,
    );

    expect(screen.getByText("asks first")).toBeInTheDocument();
    expect(screen.getByText("send_note")).toBeInTheDocument();
  });

  it("does not work out for itself whether something is dangerous", () => {
    // A SEND the runtime said does not need approval is rendered as not
    // needing approval. The window has no second opinion, on purpose: the
    // policy engine is the only thing that decides this.
    render(
      <CapabilityList
        tools={[capability({ effect: "SEND", risk: "LOW", requires_approval: false })]}
      />,
    );

    expect(screen.queryByText("asks first")).not.toBeInTheDocument();
  });

  it("says when nothing has been discovered yet", () => {
    render(<CapabilityList tools={[]} />);

    expect(screen.getByText(/Nothing discovered yet/)).toBeInTheDocument();
  });

  it("shows what has not been classified", () => {
    render(<CapabilityList tools={[capability({ classified: false })]} />);

    expect(screen.getByText("unclassified")).toBeInTheDocument();
  });
});
