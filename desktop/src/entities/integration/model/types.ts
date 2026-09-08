/**
 * What the runtime says about a connected service.
 *
 * Every field here is read and none is derived. `requires_approval` in
 * particular arrives already decided: the policy engine answered it before this
 * window heard of the integration, and computing it here from `effect` would be
 * a second policy engine written in TypeScript, disagreeing quietly with the
 * real one.
 */

export interface Capability {
  name: string;
  qualified_name: string;
  description: string;
  effect: string;
  risk: string;
  /** Decided by the core. Never worked out here. */
  requires_approval: boolean;
  /** False means nobody has said what this does to the world yet. */
  classified: boolean;
}

export interface Integration {
  id: string;
  name: string;
  kind: string;
  status: string;
  enabled: boolean;
  usable: boolean;
  capabilities: string[];
  /** The names of the credentials it needs. Never a value. */
  secrets: string[];
  tool_count: number;
  tools: Capability[];
}

export interface IntegrationList {
  /** False where the machine has integrations switched off entirely. */
  available: boolean;
  integrations: Integration[];
}
