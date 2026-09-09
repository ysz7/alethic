/**
 * What the runtime says about providers, models and where work goes.
 *
 * `has_key` and never the key. The core does not return a credential from any
 * endpoint, so there is nothing here to accidentally render: a window that can
 * display a key is a window that puts one in a screenshot.
 *
 * `used_for` and `usable` arrive already decided, like `requires_approval` on
 * an integration. Working out here which model a kind of work would go to would
 * be a second router written in TypeScript, disagreeing quietly with the real one.
 */

export interface ProviderKind {
  name: string;
  label: string;
  needs_credential: boolean;
  default_base_url: string;
}

export interface Connection {
  id: string;
  name: string;
  kind: string;
  base_url: string;
  description: string;
  needs_credential: boolean;
  /** Whether a credential is stored. Never the credential. */
  has_key: boolean;
  /** Decided by the core: whether a client could be built from this at all. */
  usable: boolean;
}

export interface ModelEntry {
  name: string;
  provider: string;
  model: string;
  connection: string;
  capabilities: string[];
  context_tokens: number;
  input_cost_per_1k_usd: number;
  output_cost_per_1k_usd: number;
  quality: number;
  dimensions: number;
  /** Kinds of work currently routed here, decided by the core. */
  used_for: string[];
}

export interface ProviderSettings {
  kinds: ProviderKind[];
  connections: Connection[];
  models: ModelEntry[];
  /** Kind of work -> catalog entry name. */
  defaults: Record<string, string>;
}
