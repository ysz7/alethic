export interface Approval {
  id: string;
  task_id: string;
  action: string;
  risk: string;
  reason: string;
  payload: Record<string, unknown>;
  requested_at: string;
  /** Whether a tool call is actually parked on this, or the run has since died. */
  live: boolean;
  state?: string;
}
