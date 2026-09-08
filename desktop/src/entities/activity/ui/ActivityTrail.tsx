/**
 * What Alethic is doing, while it does it.
 *
 * It renders the six kinds the runtime announces and translates nothing: no
 * friendlier verb for a tool name, and no decision that some steps are too
 * technical to show. A person watching their own machine act on their behalf is
 * entitled to see what it did, and a curated version is one they cannot check.
 *
 * What is absent is deliberate too. The employee's transcript - the model's own
 * working notes - is never sent to any interface, so there is nothing here to
 * render by accident. What is shown is actions and their results.
 */

import type { ActivityEvent } from "../model/types";

const LABEL: Record<ActivityEvent["kind"], string> = {
  STAGE: "",
  PLAN: "Planned",
  TOOL_CALL: "Did",
  OBSERVATION: "Saw",
  APPROVAL: "Waiting for you",
  RESULT: "Finished",
};

export function ActivityTrail({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section className="trail" aria-label="Activity">
      <ol>
        {events.map((event, index) => (
          <li key={`${event.task_id}-${index}`} className={event.kind.toLowerCase()}>
            {LABEL[event.kind] && <span className="kind">{LABEL[event.kind]}</span>}
            <span className="what">{event.message}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
