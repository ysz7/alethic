/**
 * The shapes the runtime sends for a conversation, mirrored once.
 *
 * Produced by `application/interface/views.py`. They are declared here so a
 * component can be type-checked - not so this layer can reinterpret them.
 * Nothing in the frontend derives a status, recomputes a cost or decides
 * whether work is finished; if a field the UI needs does not exist, it is added
 * to the projection in Python, where every interface gets it at once.
 */

export type ObjectiveStatus =
  | "RECEIVED"
  | "PLANNING"
  | "RUNNING"
  | "DONE"
  | "FAILED"
  | "ESCALATED";

/**
 * One turn: what was asked, and what came back.
 *
 * A turn is an objective - the unit the platform already records in full.
 * There is no separate assistant message anywhere in this application, because
 * a second record of the same answer is the one that goes stale.
 */
export interface Message {
  id: string;
  text: string;
  status: ObjectiveStatus;
  thinking: boolean;
  answer: string;
  missing: string[];
  answered: boolean;
  cost_usd: number;
  created_at: string;
  finished_at: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  messages: number;
  created_at: string;
  updated_at: string;
}

export interface Thread extends Omit<Conversation, "messages"> {
  messages: Message[];
}
