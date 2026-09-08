/**
 * Who the window talks to, decided once at the top and read anywhere below it.
 *
 * A context rather than a module-level singleton: the client is the seam every
 * test substitutes at, and a global would make "which runtime is this window
 * pointed at" unanswerable from anywhere but the import graph. It lives on the
 * lowest layer because every layer above may read it and none of them may
 * choose it - choosing is the application's, one place, at startup.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";

import { RuntimeClient } from "./client";
import { DEFAULT_BASE_URL } from "./config";

const RuntimeContext = createContext<RuntimeClient | null>(null);

interface Props {
  client?: RuntimeClient;
  baseUrl?: string;
  children: ReactNode;
}

export function RuntimeProvider({ client, baseUrl, children }: Props) {
  const value = useMemo(
    () => client ?? new RuntimeClient(baseUrl ?? DEFAULT_BASE_URL),
    [client, baseUrl],
  );
  return <RuntimeContext.Provider value={value}>{children}</RuntimeContext.Provider>;
}

export function useRuntime(): RuntimeClient {
  const client = useContext(RuntimeContext);
  if (!client) {
    throw new Error("useRuntime was called outside RuntimeProvider.");
  }
  return client;
}
