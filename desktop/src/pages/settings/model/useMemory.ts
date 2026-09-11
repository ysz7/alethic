/**
 * What this workspace remembers. Read, and nothing else.
 *
 * There is no forget button here on purpose: reading memory and forgetting it
 * are two contracts in the core (ADR 0009), and the window holds only the
 * first. Pruning is `prometheus memory --prune`, which is a deliberate act at a
 * terminal rather than one click away from a listing.
 */

import { useCallback, useEffect, useState } from "react";

import { memoryApi, type MemoryItem } from "../../../entities/memory";
import { report, type RuntimeClient } from "../../../shared/api";
import { describe } from "../../../shared/lib";

export function useMemory(client: RuntimeClient): {
  ready: boolean;
  items: MemoryItem[];
  reload: () => Promise<void>;
} {
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<MemoryItem[]>([]);

  const reload = useCallback(async () => {
    try {
      const body = await memoryApi.all(client);
      setItems(body.items ?? []);
    } catch (error) {
      report(describe(error));
    } finally {
      setReady(true);
    }
  }, [client]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { ready, items, reload };
}
