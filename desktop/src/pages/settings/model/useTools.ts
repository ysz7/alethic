/**
 * What this machine can do. Read, and nothing else.
 *
 * There is no operation here on purpose. Which tools exist is the registry's
 * answer and which employee may call one is that employee's declaration; a
 * window that could change either would be a second place to say it, and the
 * second place is the one that goes stale.
 */

import { useCallback, useEffect, useState } from "react";

import { toolApi, type Tool } from "../../../entities/tool";
import { report, type RuntimeClient } from "../../../shared/api";
import { describe } from "../../../shared/lib";

export interface ToolsState {
  ready: boolean;
  problem: string;
  tools: Tool[];
}

export function useTools(client: RuntimeClient): ToolsState {
  const [ready, setReady] = useState(false);
  const [problem, setProblem] = useState("");
  const [tools, setTools] = useState<Tool[]>([]);

  const reload = useCallback(async () => {
    try {
      const body = await toolApi.all(client);
      setTools(body?.tools ?? []);
      setProblem("");
    } catch (error) {
      const said = describe(error);
      setProblem(said);
      report(said);
    } finally {
      setReady(true);
    }
  }, [client]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { ready, problem, tools };
}
