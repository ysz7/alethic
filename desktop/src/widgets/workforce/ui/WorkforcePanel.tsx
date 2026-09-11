/**
 * Who Prometheus has to work with. A list of who exists, not a place to configure
 * anybody - and shown where a person is deciding what to ask, not beside every
 * answer, because once a request is made who takes it is not theirs to choose.
 */

import { EmployeeRow, type Employee } from "../../../entities/employee";
import { PeopleIcon } from "../../../shared/ui";

export function WorkforcePanel({ employees }: { employees: Employee[] }) {
  if (employees.length === 0) return null;
  return (
    <section className="rescard workforce" aria-label="Workforce">
      <div className="res-top">
        <span className="res-ico">
          <PeopleIcon />
        </span>
        <span className="res-meta">
          <b>Workforce</b>
          <span>Prometheus decides who takes what.</span>
        </span>
      </div>
      <ul>
        {employees.map((employee) => (
          <EmployeeRow key={employee.id} employee={employee} />
        ))}
      </ul>
    </section>
  );
}
