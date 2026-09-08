/**
 * One screen: a conversation with Alethic, and what it is doing about it.
 *
 * Not a dashboard. It shows the thing the person came to do - say what they
 * need - and shows the work only while there is work. There is no settings
 * screen, because everything configurable is a file on this machine that the
 * runtime already reads.
 */

import { ApprovalCard } from "../../../entities/approval";
import { ApprovalDecision } from "../../../features/decide-approval";
import { RequestComposer } from "../../../features/send-request";
import { StopButton } from "../../../features/stop-run";
import { ConversationView } from "../../../widgets/conversation";
import { WorkforcePanel } from "../../../widgets/workforce";
import { useRuntime } from "../../../shared/api";
import { useWorkspace } from "../model/useWorkspace";

export function WorkspacePage() {
  const client = useRuntime();
  const { ready, problem, messages, activity, approvals, employees, busy, send, stop, decide } =
    useWorkspace(client);

  return (
    <div className="window">
      <main className={messages.length === 0 ? "stage empty" : "stage"}>
        <div className="scroll">
          <ConversationView messages={messages} activity={activity} busy={busy} />
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              actions={<ApprovalDecision approvalId={approval.id} onDecide={decide} />}
            />
          ))}
          {problem && (
            <p className="problem" role="alert">
              {problem}
            </p>
          )}
          {!ready && !problem && <p className="waking">Starting Alethic…</p>}
        </div>

        <footer className="entry">
          <RequestComposer onSend={send} disabled={!ready} />
          {busy && <StopButton onStop={stop} />}
        </footer>
      </main>

      <WorkforcePanel employees={employees} />
    </div>
  );
}
