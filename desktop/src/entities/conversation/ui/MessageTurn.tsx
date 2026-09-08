/**
 * One turn of the conversation.
 *
 * What was asked, and either the answer or the fact that work is still
 * happening. What is *missing* from a finished answer is shown rather than
 * hidden: a run that did most of a job and says so is more useful than one that
 * reports success, and Phase 11 found the second failure mode is the expensive
 * one.
 */

import { statusLine } from "../model/status";
import type { Message } from "../model/types";

export function MessageTurn({ message }: { message: Message }) {
  return (
    <li className="turn">
      <p className="asked">{message.text}</p>
      {message.answered ? (
        <div className={`answer ${message.status.toLowerCase()}`}>
          <p>{message.answer}</p>
          {message.missing.length > 0 && (
            <ul className="missing">
              {message.missing.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="working" aria-live="polite">
          <span className="pulse" aria-hidden="true" />
          {statusLine(message)}
        </p>
      )}
    </li>
  );
}
