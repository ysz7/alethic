import type { RuntimeClient } from "../../../shared/api";
import type { Employee } from "../model/types";

export const employeeApi = {
  async all(client: RuntimeClient): Promise<Employee[]> {
    const body = await client.get<{ employees: Employee[] }>("/api/employees");
    return body.employees;
  },
};
