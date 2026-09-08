import type { Message } from "./types";

const WORKING: Record<string, string> = {
  RECEIVED: "Reading your request…",
  PLANNING: "Working out what this takes…",
  RUNNING: "Working on it…",
};

/**
 * What to say while a turn is unanswered.
 *
 * The status comes from the runtime; this only chooses the sentence for it. A
 * stage the runtime has not reached is never announced here - a window that
 * said "Planning…" before the manager had read the request would be narrating
 * a run it cannot see.
 */
export function statusLine(message: Message): string {
  if (message.answered) return "";
  return WORKING[message.status] ?? "Working on it…";
}
