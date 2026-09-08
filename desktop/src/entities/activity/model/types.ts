/**
 * The six kinds the runtime announces.
 *
 * Deliberately not fifteen. `ProgressKind` is small so an interface that
 * understands six kinds understands every tool that will ever be added; a
 * vocabulary with an entry per tool would move the coupling into the frontend
 * rather than remove it. See `application/interface/activity.py`.
 */
export type ActivityKind =
  | "STAGE"
  | "PLAN"
  | "TOOL_CALL"
  | "OBSERVATION"
  | "APPROVAL"
  | "RESULT";

export interface ActivityEvent {
  task_id: string;
  objective_id: string | null;
  kind: ActivityKind;
  message: string;
  step: number;
  payload: Record<string, unknown>;
  at: string | null;
}
