/**
 * The window, end to end against a scripted runtime.
 *
 * Everything below the client is real - the provider, the page's state, the
 * widgets, the features - and the only thing replaced is the HTTP the runtime
 * would have answered. That is the frontend half of Phase 13's integration
 * test; the other half runs the same flow through FastAPI, the application
 * boundary and the employee runtime in `tests/e2e/test_the_desktop_interface.py`.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../app";
import { RuntimeClient } from "../../../shared/api";

const BASE = "http://127.0.0.1:9999";

/** A runtime that answers, and can be told to finish the work it was given. */
function scriptedRuntime() {
  const state = {
    answered: false,
    approvals: [] as unknown[],
    asked: [] as string[],
  };

  const respond = (path: string, init?: RequestInit) => {
    if (path.endsWith("/api/employees")) {
      return {
        employees: [
          {
            id: "e1",
            name: "researcher",
            title: "Researcher",
            description: "Finds things out.",
            tools: [],
            limits: { max_steps: 1, max_cost_usd: 1, max_wall_time_seconds: 1 },
          },
        ],
      };
    }
    if (path.endsWith("/api/approvals")) return { approvals: state.approvals };
    if (path.endsWith("/api/workspaces")) {
      return { workspaces: [workspace("default", "Default", true)] };
    }
    if (path.endsWith("/api/conversations") && init?.method === "POST") {
      return {
        id: "c1",
        title: "",
        messages: 0,
        created_at: "2026-09-08T09:00:00+00:00",
        updated_at: "2026-09-08T09:00:00+00:00",
      };
    }
    if (path.endsWith("/messages")) {
      state.asked.push(JSON.parse(String(init?.body)).request);
      return message(false);
    }
    if (path.includes("/api/conversations/c1")) {
      return {
        id: "c1",
        title: "Sort these files",
        created_at: "2026-09-08T09:00:00+00:00",
        updated_at: "2026-09-08T09:00:00+00:00",
        messages: state.asked.map(() => message(state.answered)),
      };
    }
    return {};
  };

  const workspace = (id: string, name: string, active: boolean) => ({
    id,
    name,
    description: "",
    file_root: `/tmp/${id}`,
    is_default: id === "default",
    active,
    created_at: "2026-09-08T09:00:00+00:00",
  });

  const message = (answered: boolean) => ({
    id: "o1",
    text: "Sort these files",
    status: answered ? "DONE" : "RUNNING",
    thinking: !answered,
    answer: answered ? "Sorted into four folders." : "",
    missing: [],
    answered,
    cost_usd: 0.01,
    created_at: "2026-09-08T09:00:00+00:00",
    finished_at: answered ? "2026-09-08T09:01:00+00:00" : null,
  });

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => respond(url, init),
  }));

  return { state, fetchMock };
}

class SilentEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

let runtime: ReturnType<typeof scriptedRuntime>;

beforeEach(() => {
  runtime = scriptedRuntime();
  vi.stubGlobal("fetch", runtime.fetchMock);
  vi.stubGlobal("EventSource", SilentEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("the desktop window", () => {
  it("greets, takes a request, and shows the answer the runtime produced", async () => {
    const user = userEvent.setup();
    render(<App client={new RuntimeClient(BASE)} />);

    expect(await screen.findByText("What would you like me to do?")).toBeInTheDocument();

    await user.type(
      screen.getByLabelText("Tell Alethic what you need"),
      "Sort these files{Enter}",
    );

    expect(await screen.findByText("Sort these files")).toBeInTheDocument();
    expect(screen.getByText("Working on it…")).toBeInTheDocument();
    expect(runtime.state.asked).toEqual(["Sort these files"]);

    // The runtime finishes. The window learns it by re-reading the thread,
    // never by deciding for itself that enough time has passed.
    runtime.state.answered = true;
    await waitFor(
      () => expect(screen.getByText("Sorted into four folders.")).toBeInTheDocument(),
      { timeout: 4000 },
    );
  });

  it("shows the workforce it was told about, and nothing it was not", async () => {
    render(<App client={new RuntimeClient(BASE)} />);

    expect(await screen.findByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Alethic decides who takes what.")).toBeInTheDocument();
  });

  it("puts a question waiting on the person in front of them", async () => {
    runtime.state.approvals = [
      {
        id: "a1",
        task_id: "t1",
        action: "send an email",
        risk: "HIGH",
        reason: "Sending cannot be undone.",
        payload: { to: "client@example.com" },
        requested_at: "2026-09-08T09:00:00+00:00",
        live: true,
      },
    ];

    render(<App client={new RuntimeClient(BASE)} />);

    expect(await screen.findByText("Alethic wants to send an email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("says so, in the runtime's own words, when the engine is not answering", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({ detail: "The local database has no schema yet." }),
      }),
    );

    render(<App client={new RuntimeClient(BASE)} />);

    expect(
      await screen.findByText("The local database has no schema yet."),
    ).toBeInTheDocument();
  });
});
