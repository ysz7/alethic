/**
 * A question the person has to answer, shown but not answered here.
 *
 * The card presents; deciding is a feature, and it arrives through `actions`.
 * The split is the architectural rule made structural: this layer cannot call
 * the runtime even if somebody later wanted it to, so the one place a decision
 * is sent stays the one place it is sent from.
 *
 * Whether this action needed asking was settled by the policy engine before the
 * window heard about it. Whether it now happens is settled by the person.
 * Nothing in the interface gets a vote - which is why the risk is printed in
 * the runtime's own word rather than turned into a colour this layer chose.
 */

import type { ReactNode } from "react";

import { WarningIcon } from "../../../shared/ui";
import type { Approval } from "../model/types";

interface Props {
  approval: Approval;
  actions?: ReactNode;
}

export function ApprovalCard({ approval, actions }: Props) {
  const details = Object.entries(approval.payload ?? {});
  return (
    <article
      className={approval.live ? "gate" : "gate ended"}
      aria-label={`Approval: ${approval.action}`}
    >
      <div className="gate-top">
        <WarningIcon />
        <b>
          Needs approval · <span className="risk">{approval.risk}</span>
        </b>
      </div>
      <h4>Prometheus wants to {approval.action}</h4>
      {approval.reason && <p>{approval.reason}</p>}
      {details.length > 0 && (
        <dl className="gate-details">
          {details.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {!approval.live && (
        <p className="stale">
          Nothing is waiting on this any more — the run that asked has ended. Answering it
          only closes the question.
        </p>
      )}
      {actions && <div className="gate-acts">{actions}</div>}
    </article>
  );
}
