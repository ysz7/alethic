/**
 * One way in to a provider, shown as it is.
 *
 * The word for its state comes from the runtime's own `usable`, and the key is
 * described rather than shown - there is nothing a person does with a key they
 * have already typed except replace it.
 */

import type { ReactNode } from "react";

import type { Connection } from "../model/types";

interface Props {
  connection: Connection;
  actions?: ReactNode;
  children?: ReactNode;
}

export function ConnectionCard({ connection, actions, children }: Props) {
  const state = connection.usable ? "good" : "bad";
  const key = !connection.needs_credential
    ? "no key needed"
    : connection.has_key
      ? "key stored"
      : "no key yet";
  return (
    <article className="integration" aria-label={`Connection: ${connection.name}`}>
      <header>
        <h3>{connection.name}</h3>
        <span className={`state ${state}`}>{connection.usable ? "ready" : "not usable"}</span>
      </header>
      <p className="meta">
        {connection.kind} · {key}
        {connection.base_url && ` · ${connection.base_url}`}
      </p>
      {connection.description && <p className="note">{connection.description}</p>}
      {children}
      {actions}
    </article>
  );
}
