/**
 * What the sidebar lists: the threads of this workspace, which workspace that
 * is, and what the work here has cost.
 *
 * All three are read and none is kept: the list is re-read on a timer and
 * whenever the page says something changed, because a thread started from the
 * terminal or by a schedule belongs in it as much as one started here. A failed
 * read leaves the last answer on screen - the list is a way back to old work,
 * and the page already says plainly when the runtime is down.
 */

import { useEffect, useState } from "react";

import { conversationApi, type Conversation } from "../../../entities/conversation";
import { spendApi } from "../../../entities/spend";
import { workspaceApi } from "../../../entities/workspace";
import type { RuntimeClient } from "../../../shared/api";

/** How often the list is re-read while nothing here asked for it. */
const LIST_POLL_MS = 4000;

export interface ThreadsState {
  threads: Conversation[];
  workspace: string;
  spent: number | null;
}

export function useThreads(client: RuntimeClient, refresh: number): ThreadsState {
  const [threads, setThreads] = useState<Conversation[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [spent, setSpent] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const read = async () => {
      try {
        const body = await conversationApi.list(client);
        if (!cancelled) setThreads(body.conversations ?? []);
      } catch {
        /* the page reports a runtime that is not answering; this does not repeat it */
      }
      try {
        const body = await workspaceApi.all(client);
        const active = (body.workspaces ?? []).find((item) => item.active);
        if (!cancelled) setWorkspace(active?.name ?? "");
      } catch {
        /* as above */
      }
      try {
        const body = await spendApi.total(client);
        if (!cancelled) setSpent(typeof body.cost_usd === "number" ? body.cost_usd : null);
      } catch {
        /* as above */
      }
    };
    void read();
    const timer = setInterval(() => void read(), LIST_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [client, refresh]);

  return { threads, workspace, spent };
}
