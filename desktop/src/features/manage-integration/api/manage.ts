import type { Integration } from "../../../entities/integration";
import type { RuntimeClient } from "../../../shared/api";

/**
 * The four things a person does to a service they already added.
 *
 * Each is one call and no logic. Whether connecting succeeded is the status
 * that comes back, not something judged here - a server that will not start is
 * a normal answer with a status on it, and a window that decided for itself
 * what "failed" means would disagree with the record the next time it loaded.
 */

export async function connectIntegration(
  client: RuntimeClient,
  id: string,
): Promise<Integration> {
  return client.post<Integration>(`/api/integrations/${id}/connect`);
}

export async function enableIntegration(
  client: RuntimeClient,
  id: string,
): Promise<Integration> {
  return client.post<Integration>(`/api/integrations/${id}/enable`);
}

export async function disableIntegration(
  client: RuntimeClient,
  id: string,
): Promise<Integration> {
  return client.post<Integration>(`/api/integrations/${id}/disable`);
}

export async function removeIntegration(client: RuntimeClient, id: string): Promise<boolean> {
  const body = await client.del<{ removed: boolean }>(`/api/integrations/${id}`);
  return body.removed;
}

/** Say what a capability does to the world. The risk follows; it is not sent. */
export async function classifyCapability(
  client: RuntimeClient,
  id: string,
  effects: Record<string, string>,
): Promise<Integration> {
  return client.post<Integration>(`/api/integrations/${id}/capabilities`, { effects });
}
