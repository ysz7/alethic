/**
 * One capability of this machine, shown as it is.
 *
 * The warning is the runtime's answer rather than this component's opinion, for
 * the same reason an integration's capability row carries one: a component that
 * decided which actions look dangerous would be right until the day the policy
 * changed and nobody remembered this file existed.
 */

import type { Tool } from "../model/types";

export function ToolRow({ tool }: { tool: Tool }) {
  return (
    <article className="plugin" aria-label={`Tool: ${tool.name}`}>
      <header>
        <span className="plugin-name">{tool.name}</span>
        {tool.requires_approval && <span className="state waiting">asks first</span>}
      </header>
      {tool.description && <p className="note">{tool.description}</p>}
      <p className="meta">
        {tool.effect.toLowerCase()} · {tool.interface.toLowerCase().replace(/_/g, " ")} ·{" "}
        {tool.used_by.length > 0
          ? `listed by ${tool.used_by.join(", ")}`
          : "listed by nobody"}
      </p>
    </article>
  );
}
