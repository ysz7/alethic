import type { RuntimeClient } from "../../../shared/api";
import type { ProviderSettings } from "../model/types";

export const providerApi = {
  /** Everything the settings screen shows, in one request. */
  async all(client: RuntimeClient): Promise<ProviderSettings> {
    return client.get<ProviderSettings>("/api/providers");
  },

  /** What a runner already has. Empty where it cannot be asked. */
  async installed(client: RuntimeClient, connection: string): Promise<string[]> {
    const body = await client.get<{ models: string[] }>(
      `/api/providers/connections/${encodeURIComponent(connection)}/installed`,
    );
    return body.models;
  },
};
