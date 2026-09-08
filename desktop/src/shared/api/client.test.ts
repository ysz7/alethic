/**
 * The client is the only thing in the frontend that knows the transport, so it
 * is the only thing worth testing on its own: what it sends, and what it does
 * with an error the runtime explains in words.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { RuntimeClient, RuntimeRequestError } from "./client";

const BASE = "http://127.0.0.1:9999";

function answering(body: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: "Error",
    json: async () => body,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("RuntimeClient", () => {
  it("posts what it was given, as JSON, to the path it was given", async () => {
    const fetchMock = answering({ id: "1" });

    await new RuntimeClient(BASE).post("/api/conversations", { title: "" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/api/conversations`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ title: "" });
  });

  it("reports the runtime's own explanation rather than a status code", async () => {
    answering({ detail: "Unknown employee: nobody" }, false, 400);

    await expect(new RuntimeClient(BASE).get("/api/employees")).rejects.toThrow(
      "Unknown employee: nobody",
    );
  });

  it("keeps the status, so a caller can tell 404 from 503", async () => {
    answering({ detail: "The local database has no schema yet." }, false, 503);

    const failure = await new RuntimeClient(BASE).get("/api/approvals").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(RuntimeRequestError);
    expect((failure as RuntimeRequestError).status).toBe(503);
  });

  it("falls back to the status text when the runtime says nothing readable", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(new RuntimeClient(BASE).get("/api/spend")).rejects.toThrow(
      "Internal Server Error",
    );
  });
});
