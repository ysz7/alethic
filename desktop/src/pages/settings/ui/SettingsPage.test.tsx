/**
 * The settings screen against a scripted runtime.
 *
 * The same shape as the workspace test: everything below the client is real,
 * and only the HTTP is replaced. What is being asserted is mostly what the
 * window does *not* do - it never decides whether a capability is safe, never
 * shows a credential, and never assumes an operation worked.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RuntimeClient, RuntimeProvider } from "../../../shared/api";
import { SettingsPage } from "./SettingsPage";

const BASE = "http://127.0.0.1:9999";

const TOOLS = [
  {
    name: "search_notes",
    qualified_name: "notes.search_notes",
    description: "Search the notes.",
    effect: "READ",
    risk: "LOW",
    requires_approval: false,
    classified: true,
  },
  {
    name: "send_note",
    qualified_name: "notes.send_note",
    description: "Send a note.",
    effect: "SEND",
    risk: "HIGH",
    requires_approval: true,
    classified: true,
  },
];

function scriptedRuntime({ available = true } = {}) {
  const state = {
    integrations: [] as Record<string, unknown>[],
    workspaces: [
      {
        id: "default",
        name: "Default",
        description: "",
        file_root: "/tmp/default",
        is_default: true,
        active: true,
        created_at: "2026-09-08T09:00:00+00:00",
      },
    ] as Record<string, unknown>[],
    documents: [] as Record<string, unknown>[],
    memory: [] as Record<string, unknown>[],
    posted: [] as { path: string; body: unknown }[],
    deleted: [] as string[],
  };

  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(BASE, "");
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;

    if (init?.method === "DELETE") {
      state.deleted.push(path);
      state.integrations = [];
      return json({ removed: true });
    }
    if (init?.method === "POST") {
      state.posted.push({ path, body });
      if (path === "/api/credentials") return json({ name: "NOTES_TOKEN", stored: true });
      if (path === "/api/integrations") {
        state.integrations = [
          {
            id: "i1",
            name: "notes",
            kind: "MCP",
            status: "CONFIGURING",
            enabled: true,
            usable: true,
            capabilities: ["EMAIL"],
            secrets: ["NOTES_TOKEN"],
            tool_count: 0,
            tools: [],
          },
        ];
        return json(state.integrations[0]);
      }
      if (path.endsWith("/connect")) {
        state.integrations = [
          { ...state.integrations[0], status: "READY", tool_count: 2, tools: TOOLS },
        ];
        return json(state.integrations[0]);
      }
      if (path.endsWith("/disable")) {
        state.integrations = [
          { ...state.integrations[0], enabled: false, usable: false, status: "DISABLED" },
        ];
        return json(state.integrations[0]);
      }
    }
    if (path === "/api/integrations") {
      return json({ available, integrations: state.integrations });
    }
    if (path === "/api/workspaces") return json({ workspaces: state.workspaces });
    if (path === "/api/documents") {
      return json({ available: true, documents: state.documents });
    }
    if (path.startsWith("/api/memory")) return json({ items: state.memory });
    return json({});
  });

  return { state, client: new RuntimeClient(BASE, fetchImpl as never) };
}

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function show(client: RuntimeClient) {
  return render(
    <RuntimeProvider client={client}>
      <SettingsPage />
    </RuntimeProvider>,
  );
}

describe("Settings → Integrations", () => {
  it("says when nothing is connected", async () => {
    const { client } = scriptedRuntime();
    show(client);

    expect(await screen.findByText("Nothing is connected yet.")).toBeInTheDocument();
  });

  it("adds any MCP server from a name and a command", async () => {
    const { state, client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");

    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx -y some-server");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.getByText("notes")).toBeInTheDocument());
    const added = state.posted.find((call) => call.path === "/api/integrations");
    expect(added?.body).toMatchObject({
      name: "notes",
      configuration: { command: "npx", args: ["-y", "some-server"] },
    });
  });

  it("connects straight after adding, because that is what was asked for", async () => {
    const { state, client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");

    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx server");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(state.posted.some((call) => call.path.endsWith("/connect"))).toBe(true),
    );
    expect(await screen.findByText("ready")).toBeInTheDocument();
  });

  it("shows which capabilities wait for the person, as the runtime said", async () => {
    const { client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");
    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx server");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("send_note")).toBeInTheDocument();
    expect(screen.getByText("asks first")).toBeInTheDocument();
    expect(screen.getAllByText("asks first")).toHaveLength(1);
  });

  it("sends a credential and never shows it again", async () => {
    const { state, client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");

    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx server");
    await userEvent.click(screen.getByText("Needs a credential"));
    await userEvent.type(screen.getByLabelText("Credential name"), "NOTES_TOKEN");
    await userEvent.type(screen.getByLabelText("Credential value"), "s3cret");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(state.posted.some((call) => call.path === "/api/credentials")).toBe(true),
    );
    expect(document.body.textContent).not.toContain("s3cret");
  });

  it("disables without forgetting the setup", async () => {
    const { client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");
    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx server");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByText("ready");

    await userEvent.click(screen.getByRole("button", { name: "Disable" }));

    expect(await screen.findByRole("button", { name: "Enable" })).toBeInTheDocument();
  });

  it("asks before removing, and says what removal keeps", async () => {
    const { state, client } = scriptedRuntime();
    show(client);
    await screen.findByText("Nothing is connected yet.");
    await userEvent.type(screen.getByLabelText("Name"), "notes");
    await userEvent.type(screen.getByLabelText("Command"), "npx server");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByText("ready");

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByText(/What it already did stays in the history/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => expect(state.deleted).toHaveLength(1));
  });

  it("says so when the machine has integrations switched off", async () => {
    const { client } = scriptedRuntime({ available: false });
    show(client);

    expect(await screen.findByText(/switched off on this machine/)).toBeInTheDocument();
  });

  it("shows the runtime's own words when something fails", async () => {
    const failing = new RuntimeClient(
      BASE,
      (async () =>
        new Response(JSON.stringify({ detail: "The local database has no schema yet." }), {
          status: 503,
        })) as never,
    );
    show(failing);

    // Every section on this screen reads the runtime, so a database with no
    // schema is reported by each of them. What is asserted is the words, not
    // how many places say them.
    const said = await screen.findAllByRole("alert");
    expect(said[0]).toHaveTextContent("no schema yet");
  });
});
