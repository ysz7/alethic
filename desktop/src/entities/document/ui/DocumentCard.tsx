import type { ReactNode } from "react";

import type { Document } from "../model/types";

/**
 * One document, with the one thing a person needs to know about it: whether it
 * can be found by meaning, or only by the words in it.
 */
export function DocumentCard({
  document,
  actions,
}: {
  document: Document;
  actions?: ReactNode;
}) {
  return (
    <article className="document">
      <header>
        <strong>{document.title}</strong>
        <span className={document.status === "INDEXED" ? "badge" : "badge quiet"}>
          {document.status.toLowerCase()}
        </span>
        {actions}
      </header>
      <p className="note">
        {document.chunks} passage(s)
        {document.status === "EXTRACTED" && " - found by words, not yet by meaning"}
      </p>
      {document.source && <p className="note">{document.source}</p>}
      {document.error && (
        <p className="problem" role="alert">
          {document.error}
        </p>
      )}
    </article>
  );
}
