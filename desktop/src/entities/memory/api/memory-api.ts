import type { RuntimeClient } from "../../../shared/api";
import type { MemoryList } from "../model/types";

export const memoryApi = {
  async all(client: RuntimeClient): Promise<MemoryList> {
    return client.get<MemoryList>("/api/memory");
  },
};
