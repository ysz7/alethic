import { invoke, isTauri } from "@tauri-apps/api/core";

/** Where the local runtime listens. The same default as `Settings.ui_host`/`ui_port`. */
export const DEFAULT_BASE_URL = "http://127.0.0.1:8765";

/**
 * What this interface tells the platform about where a request came from.
 *
 * Recorded by the core and never branched on - see
 * `application/interface/contracts.py`. It exists so a trace says which surface
 * a person used, not so the platform behaves differently for one of them.
 */
export const SOURCE = "desktop";

/**
 * Which runtime this window talks to. Asked once, at startup.
 *
 * The shell is the only one that knows: it is what reads `PROMETHEUS_BASE_URL`,
 * and what started the engine if none was already up. Hard-coding the default
 * here instead - which is what this did until it was tried against a runtime on
 * another port - makes the environment variable a lie that documents itself.
 *
 * Outside a Tauri window there is no shell to ask, and the default is right: a
 * browser opened on the runtime's own page is already talking to it.
 */
/** Tell the shell something went wrong here. Never throws: it is the last resort. */
export async function report(message: string): Promise<void> {
  try {
    if (isTauri()) await invoke("window_problem", { message });
    else console.error(message);
  } catch {
    /* nothing left to report to */
  }
}

export async function resolveBaseUrl(): Promise<string> {
  if (!isTauri()) return DEFAULT_BASE_URL;
  try {
    const status = await invoke<{ base_url: string }>("runtime_status");
    return status.base_url || DEFAULT_BASE_URL;
  } catch {
    // A shell that cannot answer is not a reason to refuse to open. The window
    // tries the default and says plainly if nothing is there.
    return DEFAULT_BASE_URL;
  }
}
