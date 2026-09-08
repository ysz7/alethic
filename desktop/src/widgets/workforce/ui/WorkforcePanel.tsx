/** Who Alethic has to work with. A list of who exists, not a place to configure anybody. */

import { EmployeeRow, type Employee } from "../../../entities/employee";

export function WorkforcePanel({ employees }: { employees: Employee[] }) {
  return (
    <aside className="workforce" aria-label="Workforce">
      <h2>Workforce</h2>
      <ul>
        {employees.map((employee) => (
          <EmployeeRow key={employee.id} employee={employee} />
        ))}
      </ul>
      <p className="note">Alethic decides who takes what.</p>
    </aside>
  );
}
