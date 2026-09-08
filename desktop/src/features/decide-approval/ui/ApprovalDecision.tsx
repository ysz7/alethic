/** The two buttons. Equal weight: neither answer is the easy one. */

interface Props {
  approvalId: string;
  onDecide: (approvalId: string, approved: boolean) => void | Promise<void>;
}

export function ApprovalDecision({ approvalId, onDecide }: Props) {
  return (
    <>
      <button type="button" className="reject" onClick={() => void onDecide(approvalId, false)}>
        Reject
      </button>
      <button type="button" className="approve" onClick={() => void onDecide(approvalId, true)}>
        Approve
      </button>
    </>
  );
}
