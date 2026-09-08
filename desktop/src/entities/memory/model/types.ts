/**
 * What the runtime says it remembers.
 *
 * Read-only here, and that is a property of the contract rather than of this
 * screen: reading memory and forgetting it are two contracts in the core, so a
 * window holding the first cannot do the second by accident.
 */

export interface MemoryItem {
  id: string;
  kind: string;
  /** WORKSPACE is true of this context; USER is true of the person. */
  scope: string;
  content: string;
  importance: number;
  created_at: string;
  expires_at: string;
}

export interface MemoryList {
  items: MemoryItem[];
}
