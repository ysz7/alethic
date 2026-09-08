import type { RuntimeClient } from "../../../shared/api";
import type { Approval } from "../model/types";

export const approvalApi = {
  async pending(client: RuntimeClient): Promise<Approval[]> {
    const body = await client.get<{ approvals: Approval[] }>("/api/approvals");
    return body.approvals;
  },
};
