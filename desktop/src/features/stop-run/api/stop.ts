import type { RuntimeClient } from "../../../shared/api";

/**
 * Ask the manager to stop one objective.
 *
 * A request, not a kill: the runtime stops its tasks between steps so each
 * keeps what it had already done. Whether anything was actually stopped is the
 * runtime's answer, not this layer's assumption.
 */
export function stopObjective(client: RuntimeClient, objectiveId: string): Promise<unknown> {
  return client.post(`/api/objectives/${objectiveId}/cancel`);
}
