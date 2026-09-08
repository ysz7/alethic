import type { Integration } from "../../../entities/integration";
import type { RuntimeClient } from "../../../shared/api";

export interface NewIntegration {
  name: string;
  /** The command and its arguments, as the transport wants them. */
  configuration: Record<string, unknown>;
  capabilities?: string[];
  secret_names?: string[];
}

/**
 * Write a service down. Starting it is a separate call on purpose: a command
 * that does not run should leave a record the person can correct, not a form
 * that empties itself.
 */
export async function addIntegration(
  client: RuntimeClient,
  integration: NewIntegration,
): Promise<Integration> {
  return client.post<Integration>("/api/integrations", integration);
}

/** Keep a credential. The value goes in and is never read back out. */
export async function storeCredential(
  client: RuntimeClient,
  name: string,
  value: string,
): Promise<void> {
  await client.post("/api/credentials", { name, value });
}
