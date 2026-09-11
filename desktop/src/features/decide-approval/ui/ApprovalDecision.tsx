/**
 * The two buttons. Neither answer is the quiet one: Approve carries the colour
 * of the card it sits on and Reject a full outline, so a person scanning the
 * card sees two choices rather than one choice and a way out.
 */

interface Props {
  approvalId: string;
  onDecide: (approvalId: string, approved: boolean) => void | Promise<void>;
}

export function ApprovalDecision({ approvalId, onDecide }: Props) {
  return (
    <>
      <button
        type="button"
        className="btn btn-wait"
        onClick={() => void onDecide(approvalId, true)}
      >
        Approve
      </button>
      <button
        type="button"
        className="btn btn-line"
        onClick={() => void onDecide(approvalId, false)}
      >
        Reject
      </button>
    </>
  );
}
