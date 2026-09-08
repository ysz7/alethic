/**
 * One screen: a conversation with Alethic, and what it is doing about it.
 *
 * Not a dashboard. It shows the thing the person came to do - say what they
 * need - and shows the work only while there is work.
 *
 * Called `chat` since Phase 15, when the word "workspace" stopped meaning three
 * things at once. It is the conversation; a workspace is the context the
 * conversation happens in, and there is a selector for that in the frame
 * around this.
 */

import { ApprovalCard } from "../../../entities/approval";
import { ApprovalDecision } from "../../../features/decide-approval";
import { RequestComposer } from "../../../features/send-request";
import { StopButton } from "../../../features/stop-run";
import { ConversationView } from "../../../widgets/conversation";
import { WorkforcePanel } from "../../../widgets/workforce";
import { useRuntime } from "../../../shared/api";
import { useChat } from "../model/useChat";

export function ChatPage() {
  const client = useRuntime();
  const { ready, problem, messages, activity, approvals, employees, busy, send, stop, decide } =
    useChat(client);

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
