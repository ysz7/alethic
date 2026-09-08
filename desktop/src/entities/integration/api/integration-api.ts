import type { RuntimeClient } from "../../../shared/api";
import type { Integration, IntegrationList } from "../model/types";

export const integrationApi = {
  async all(client: RuntimeClient): Promise<IntegrationList> {
    return client.get<IntegrationList>("/api/integrations");
  },

  async one(client: RuntimeClient, id: string): Promise<Integration> {
    return client.get<Integration>(`/api/integrations/${id}`);
  },
};
