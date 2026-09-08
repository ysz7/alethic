/**
 * Which `fetch` this window uses, decided once.
 *
 * In a browser it is the browser's. Inside a packaged window it is the shell's:
 * the page is served from `tauri://localhost`, and a request from there to
 * `http://127.0.0.1` never leaves the process - WebKit refuses it before the
 * network, so the runtime's log stays empty and the window can only say "Load
 * failed". Routing through Rust is the supported way out, and it is also the
 * honest one: the shell owns this machine's network, the page owns the screen.
 *
 * The permission is loopback-only (`src-tauri/capabilities/default.json`), so
 * this buys the window a runtime on this machine and nothing else.
 */

import { isTauri } from "@tauri-apps/api/core";
import { fetch as shellFetch } from "@tauri-apps/plugin-http";

export type Fetch = typeof globalThis.fetch;

export function transport(): Fetch {
  return isTauri() ? (shellFetch as Fetch) : globalThis.fetch.bind(globalThis);
}
