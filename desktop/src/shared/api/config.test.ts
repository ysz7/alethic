/**
 * Which runtime the window talks to.
 *
 * The case that matters is the one that was wrong: a window told to use another
 * port must use it. Outside a shell there is nobody to ask, and the default is
 * correct - so both paths are checked, because getting the fallback wrong is a
 * window that opens on nothing.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => mocked.inTauri,
  invoke: async () => mocked.answer(),
}));

const mocked = {
  inTauri: false,
  answer: (): unknown => ({ base_url: "http://127.0.0.1:8792" }),
};

afterEach(() => {
  mocked.inTauri = false;
  mocked.answer = () => ({ base_url: "http://127.0.0.1:8792" });
});

describe("resolveBaseUrl", () => {
  it("uses the default in a browser, where there is no shell to ask", async () => {
    const { resolveBaseUrl, DEFAULT_BASE_URL } = await import("./config");
    expect(await resolveBaseUrl()).toBe(DEFAULT_BASE_URL);
  });

  it("uses the address the shell resolved, not the one compiled in", async () => {
    mocked.inTauri = true;
    const { resolveBaseUrl } = await import("./config");
    expect(await resolveBaseUrl()).toBe("http://127.0.0.1:8792");
  });

  it("opens on the default rather than refusing when the shell cannot answer", async () => {
    mocked.inTauri = true;
    mocked.answer = () => {
      throw new Error("no such command");
    };
    const { resolveBaseUrl, DEFAULT_BASE_URL } = await import("./config");
    expect(await resolveBaseUrl()).toBe(DEFAULT_BASE_URL);
  });
});
