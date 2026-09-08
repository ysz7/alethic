/**
 * The settings screen's state: what is connected, and nothing derived from it.
 *
 * Every operation ends by taking the runtime's answer as the new truth rather
 * than by patching a local copy. An optimistic update here would be this window
 * having an opinion about whether a server started, which is the one thing it
 * cannot know.
 */

import { useCallback, useEffect, useState } from "react";

import { integrationApi, type Integration } from "../../../entities/integration";
import {
  addIntegration,
  storeCredential,
  type Submission,
} from "../../../features/add-integration";
import {
  connectIntegration,
  disableIntegration,
  enableIntegration,
  removeIntegration,
} from "../../../features/manage-integration";
import { report, type RuntimeClient } from "../../../shared/api";
import { describe } from "../../../shared/lib";

export interface IntegrationsState {
  ready: boolean;
  available: boolean;
  problem: string;
  integrations: Integration[];
  add: (submission: Submission) => Promise<void>;
  connect: (id: string) => Promise<void>;
  enable: (id: string) => Promise<void>;
  disable: (id: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
}

export function useIntegrations(client: RuntimeClient): IntegrationsState {
  const [ready, setReady] = useState(false);
  const [available, setAvailable] = useState(true);
  const [problem, setProblem] = useState("");
  const [integrations, setIntegrations] = useState<Integration[]>([]);

  const fail = useCallback((error: unknown) => {
    const said = describe(error);
    setProblem(said);
    report(said);
  }, []);

  const reload = useCallback(async () => {
    try {
      const body = await integrationApi.all(client);
      setAvailable(body.available);
      setIntegrations(body.integrations);
      setProblem("");
    } catch (error) {
      fail(error);
    } finally {
      setReady(true);
    }
  }, [client, fail]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const perform = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        setProblem("");
      } catch (error) {
        fail(error);
      }
      // Re-read either way: a failed operation may still have changed the
      // record - a connection that did not start leaves a status behind.
      await reload();
    },
    [fail, reload],
  );

  const add = useCallback(
    async (submission: Submission) =>
      perform(async () => {
        // The credential first, so the integration that names it can find one
        // the moment it connects.
        if (submission.secretName && submission.secretValue) {
          await storeCredential(client, submission.secretName, submission.secretValue);
        }
        const created = await addIntegration(client, {
          name: submission.name,
          configuration: { command: submission.command, args: submission.args },
          capabilities: submission.capabilities,
          secret_names: submission.secretName ? [submission.secretName] : [],
        });
        // Adding and connecting are two operations in the core, and the person
        // asked for one thing: connect straight away, and let whatever comes
        // back - including a failure - be the status they see.
        await connectIntegration(client, created.id);
      }),
    [client, perform],
  );

  return {
    ready,
    available,
    problem,
    integrations,
    add,
    connect: (id) => perform(() => connectIntegration(client, id)),
    enable: (id) => perform(() => enableIntegration(client, id)),
    disable: (id) => perform(() => disableIntegration(client, id)),
    remove: (id) => perform(() => removeIntegration(client, id)),
  };
}
