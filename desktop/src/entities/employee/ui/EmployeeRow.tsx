/**
 * One member of the workforce, read-only.
 *
 * An employee is a directory of declarations on this machine. Editing one from
 * a window would give the interface a second way to define what an employee may
 * do, and the declaration - which the registry validates against the tools that
 * actually exist here - would stop being the only source of that.
 */

import type { Employee } from "../model/types";

export function EmployeeRow({ employee }: { employee: Employee }) {
  return (
    <li className="filerow person">
      <b>{employee.title || employee.name}</b>
      <span>{employee.description}</span>
    </li>
  );
}
