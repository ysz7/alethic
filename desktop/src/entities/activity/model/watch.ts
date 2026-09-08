import type { RuntimeClient } from "../../../shared/api";
import type { ActivityEvent } from "./types";

/**
 * Follow one objective and every task it delegates. Returns the unsubscribe.
 *
 * The stream ends on its own when the work does - the runtime closes it - so a
 * caller that only unsubscribes on unmount is correct.
 */
export function watchObjective(
  client: RuntimeClient,
  objectiveId: string,
  onEvent: (event: ActivityEvent) => void,
): () => void {
  return client.stream<ActivityEvent>(`/api/events?objective=${objectiveId}`, onEvent);
}
