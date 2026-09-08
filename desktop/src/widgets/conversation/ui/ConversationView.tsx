/**
 * The conversation, and what is happening because of it.
 *
 * A widget composes; it fetches nothing and decides nothing. The trail appears
 * only while something is running, because an interface that keeps a log panel
 * open at all times is a log viewer, which is the thing the local surface was
 * built to stop anybody needing.
 */

import { ActivityTrail, type ActivityEvent } from "../../../entities/activity";
import { MessageTurn, type Message } from "../../../entities/conversation";
import { Greeting } from "./Greeting";

interface Props {
  messages: Message[];
  activity: ActivityEvent[];
  busy: boolean;
}

export function ConversationView({ messages, activity, busy }: Props) {
  if (messages.length === 0) return <Greeting />;
  return (
    <>
      <ol className="thread">
        {messages.map((message) => (
          <MessageTurn key={message.id} message={message} />
        ))}
      </ol>
      {busy && <ActivityTrail events={activity} />}
    </>
  );
}
