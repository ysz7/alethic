import type { RuntimeClient } from "../../../shared/api";
import type { ToolList } from "../model/types";

/**
 * Reading only. There is no route that switches a tool on or off, because a
 * grant is a line in an employee's declaration - an endpoint here would be a
 * second way to say the same thing, and the two would disagree.
 */
export const toolApi = {
  async all(client: RuntimeClient): Promise<ToolList> {
    return client.get<ToolList>("/api/tools");
  },
};
