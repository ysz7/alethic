/**
 * What the runtime says about one thing this machine can do.
 *
 * Every field is read and none is derived. `requires_approval` in particular
 * arrives already decided - the policy engine answered it before this window
 * heard of the tool - and `used_by` is the runtime's reading of the employee
 * declarations, not a list this layer assembled.
 *
 * There is no `enabled`, because there is nothing to switch. A tool reaches an
 * employee by being listed in that employee's declaration file, so the honest
 * answer to "is this on?" is who lists it.
 */

export interface Tool {
  name: string;
  /** The first line of what the tool tells a model about itself. */
  description: string;
  effect: string;
  risk: string;
  /** Decided by the core. Never worked out here. */
  requires_approval: boolean;
  /** Which rung of the interface hierarchy it reaches the world at. */
  interface: string;
  reversible: boolean;
  capabilities: string[];
  /** The employees that listed it. Empty means it reaches nobody. */
  used_by: string[];
}

export interface ToolList {
  tools: Tool[];
}
