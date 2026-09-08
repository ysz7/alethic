import type { RuntimeClient } from "../../../shared/api";
import type { DocumentList } from "../model/types";

export const documentApi = {
  async all(client: RuntimeClient): Promise<DocumentList> {
    return client.get<DocumentList>("/api/documents");
  },
};
