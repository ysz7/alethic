/**
 * What an integration offers, and what the platform will do about each one.
 *
 * The warning next to a capability is the runtime's answer, not this
 * component's opinion: `requires_approval` arrives on the wire. A component
 * that decided which actions look dangerous would be right until the day the
 * policy changed and nobody remembered this file existed.
 */

import type { Capability } from "../model/types";

export function CapabilityList({ tools }: { tools: Capability[] }) {
  if (tools.length === 0) {
    return <p className="note">Nothing discovered yet. Connect it to find out what it offers.</p>;
  }
  return (
    <ul className="capabilities">
      {tools.map((tool) => (
        <li key={tool.qualified_name}>
          <span className={tool.requires_approval ? "mark asks" : "mark"} aria-hidden="true">
            {tool.requires_approval ? "!" : "✓"}
          </span>
          <span className="name">{tool.name}</span>
          <span className="effect">{tool.effect.toLowerCase()}</span>
          {tool.requires_approval && <span className="asks-label">asks first</span>}
          {!tool.classified && <span className="unclassified">unclassified</span>}
          {tool.description && <p className="what">{tool.description}</p>}
        </li>
      ))}
    </ul>
  );
}
