/**
 * The window's state, and the only place that holds any.
 *
 * Thin on purpose: a thread of turns, the activity of the run currently
 * happening, the questions waiting on the person, and who is available. Every
 * one of those is *read* from the runtime rather than derived here - there is
 * no local model of a task's lifecycle, no optimistic status and no rule about
 * when work is finished. The runtime says; this remembers what it last said.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { watchObjective, type ActivityEvent } from "../../../entities/activity";
import { approvalApi, type Approval } from "../../../entities/approval";
import { conversationApi, type Message, type Thread } from "../../../entities/conversation";
import { employeeApi, type Employee } from "../../../entities/employee";
import { decideApproval } from "../../../features/decide-approval";
import { stopObjective } from "../../../features/stop-run";
import type { RuntimeClient } from "../../../shared/api";
import { report } from "../../../shared/api";
import { describe } from "../../../shared/lib";

/** How often the questions waiting on a person are re-read. */
const APPROVAL_POLL_MS = 3000;
/** How often a thread is re-read while something in it is still running. */
const THREAD_POLL_MS = 2000;

export interface WorkspaceState {
  ready: boolean;
  problem: string;
  thread: Thread | null;
  messages: Message[];
  activity: ActivityEvent[];
  approvals: Approval[];
  employees: Employee[];
  busy: boolean;
  send: (request: string) => Promise<void>;
  stop: () => Promise<void>;
  decide: (approvalId: string, approved: boolean) => Promise<void>;
}

export function useWorkspace(client: RuntimeClient): WorkspaceState {
  const [ready, setReady] = useState(false);
  const [problem, setProblem] = useState("");
  const [thread, setThread] = useState<Thread | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const watching = useRef<string | null>(null);
  const unwatch = useRef<(() => void) | null>(null);

  const running = useMemo(
    () => thread?.messages.find((message) => !message.answered) ?? null,
    [thread],
  );
  const busy = running !== null;

  // Shown to the person, and told to the shell. A window is often started from
  // a terminal, and a failure only the window knows about is one nobody can
  // diagnose without taking a photograph of the screen.
  const fail = useCallback((error: unknown) => {
    const text = describe(error);
    setProblem(text);
    void report(text);
  }, []);

  const reread = useCallback(
    async (conversationId: string) => {
      try {
        setThread(await conversationApi.thread(client, conversationId));
      } catch (error) {
        fail(error);
      }
    },
    [client, fail],
  );

  // A thread is opened as soon as the engine answers. Greeting somebody before
  // the runtime is up would take a request the window cannot deliver.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const opened = await conversationApi.open(client);
        const workforce = await employeeApi.all(client);
        if (cancelled) return;
        setThread({ ...opened, messages: [] });
        setEmployees(workforce);
        setReady(true);
      } catch (error) {
        if (!cancelled) fail(error);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, fail]);

  // Follow whatever is running. One subscription at a time: the trace shown is
  // the trace of the request the person is waiting on.
  useEffect(() => {
    const objectiveId = running?.id;
    const conversationId = thread?.id;
    if (!objectiveId || !conversationId || watching.current === objectiveId) return;
    unwatch.current?.();
    setActivity([]);
    watching.current = objectiveId;
    unwatch.current = watchObjective(client, objectiveId, (event) => {
      setActivity((seen) => [...seen, event]);
      // The answer is written to the store by the runtime, not carried in the
      // stream. The final event says when it is worth reading again.
      if (event.kind === "RESULT" && event.objective_id === objectiveId) {
        void reread(conversationId);
      }
    });
    return () => {
      unwatch.current?.();
      unwatch.current = null;
      watching.current = null;
    };
  }, [client, running?.id, thread?.id, reread]);

  // While something is running the thread is re-read as well as watched. A
  // stream is lossy by design - a dropped connection must not be the difference
  // between seeing the answer and not seeing it.
  useEffect(() => {
    const conversationId = thread?.id;
    if (!conversationId || !busy) return;
    const timer = setInterval(() => void reread(conversationId), THREAD_POLL_MS);
    return () => clearInterval(timer);
  }, [thread?.id, busy, reread]);

  useEffect(() => {
    if (!ready) return;
    const read = async () => {
      try {
        setApprovals(await approvalApi.pending(client));
      } catch {
        // A failed poll is not worth a message on screen: the next one is
        // three seconds away, and an approval nobody answers is refused.
      }
    };
    void read();
    const timer = setInterval(() => void read(), APPROVAL_POLL_MS);
    return () => clearInterval(timer);
  }, [client, ready]);

  const send = useCallback(
    async (request: string) => {
      if (!thread) return;
      setProblem("");
      try {
        const message = await conversationApi.send(client, thread.id, request);
        setThread((current) =>
          current ? { ...current, messages: [...current.messages, message] } : current,
        );
      } catch (error) {
        fail(error);
      }
    },
    [client, thread, fail],
  );

  const stop = useCallback(async () => {
    if (!running || !thread) return;
    try {
      await stopObjective(client, running.id);
      await reread(thread.id);
    } catch (error) {
      fail(error);
    }
  }, [client, running, thread, reread, fail]);

  const decide = useCallback(
    async (approvalId: string, approved: boolean) => {
      try {
        await decideApproval(client, approvalId, approved);
        setApprovals((waiting) => waiting.filter((item) => item.id !== approvalId));
      } catch (error) {
        fail(error);
      }
    },
    [client, fail],
  );

  return {
    ready,
    problem,
    thread,
    messages: thread?.messages ?? [],
    activity,
    approvals,
    employees,
    busy,
    send,
    stop,
    decide,
  };
}
