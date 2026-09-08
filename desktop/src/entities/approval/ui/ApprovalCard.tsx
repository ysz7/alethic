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
 * Nothing in the interface gets a vote.
 */

import type { ReactNode } from "react";

import type { Approval } from "../model/types";

interface Props {
  approval: Approval;
  actions?: ReactNode;
}

export function ApprovalCard({ approval, actions }: Props) {
  const details = Object.entries(approval.payload ?? {});
  return (
    <article className="approval" aria-label={`Approval: ${approval.action}`}>
      <header>
        <h3>Alethic wants to {approval.action}</h3>
        <span className={`risk ${approval.risk.toLowerCase()}`}>{approval.risk}</span>
      </header>
      {approval.reason && <p className="why">{approval.reason}</p>}
      {details.length > 0 && (
        <dl>
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
      {actions && <footer>{actions}</footer>}
    </article>
  );
}
