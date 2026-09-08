import type { RuntimeClient } from "../../../shared/api";
import type { WorkspaceList } from "../model/types";

/** Reading what exists. Switching and adding are features, not part of the entity. */
export const workspaceApi = {
  async all(client: RuntimeClient): Promise<WorkspaceList> {
    return client.get<WorkspaceList>("/api/workspaces");
  },
};
