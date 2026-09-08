import { useState } from "react";

import type { Document } from "../../../entities/document";

/**
 * Two buttons. Re-index is offered for every document rather than only for the
 * ones missing vectors: changing the embedding model is exactly when a document
 * that says INDEXED needs doing again, and the window does not know which model
 * wrote what.
 */
export function DocumentActions({
  document,
  onReindex,
  onRemove,
}: {
  document: Document;
  onReindex: (id: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const run = (action: (id: string) => Promise<void>) => async () => {
    setBusy(true);
    try {
      await action(document.id);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <span className="actions">
      <button type="button" disabled={busy} onClick={run(onReindex)}>
        Re-index
      </button>
      {confirming ? (
        <button type="button" disabled={busy} onClick={run(onRemove)}>
          Remove for good
        </button>
      ) : (
        <button type="button" disabled={busy} onClick={() => setConfirming(true)}>
          Remove
        </button>
      )}
    </span>
  );
}
