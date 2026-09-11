import type { RuntimeClient } from "../../../shared/api";
import type { Spend } from "../model/types";

/** Read, never computed here: the runtime meters every call and this shows the total. */
export const spendApi = {
  total(client: RuntimeClient): Promise<Spend> {
    return client.get<Spend>("/api/spend");
  },
};
