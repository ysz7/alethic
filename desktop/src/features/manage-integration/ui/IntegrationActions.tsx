/**
 * The buttons. Which ones make sense follows from the runtime's own status,
 * and nothing here decides whether an action is safe to offer beyond that.
 */

import { useState } from "react";

import type { Integration } from "../../../entities/integration";

interface Props {
  integration: Integration;
  onConnect: (id: string) => Promise<void>;
  onEnable: (id: string) => Promise<void>;
  onDisable: (id: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

export function IntegrationActions({
  integration,
  onConnect,
  onEnable,
  onDisable,
  onRemove,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const run = (action: (id: string) => Promise<void>) => async () => {
    setBusy(true);
    try {
      await action(integration.id);
    } finally {
      setBusy(false);
    }
  };

  if (confirming) {
    return (
      <div className="confirm">
        <p>
          Remove {integration.name}? Its capabilities stop being available and its
          configuration is forgotten. What it already did stays in the history.
        </p>
        <button type="button" onClick={run(onRemove)} disabled={busy}>
          Remove
        </button>
        <button type="button" onClick={() => setConfirming(false)} disabled={busy}>
          Keep it
        </button>
      </div>
    );
  }

  return (
    <>
      {integration.enabled ? (
        <>
          <button type="button" onClick={run(onConnect)} disabled={busy}>
            {integration.tool_count === 0 ? "Connect" : "Reconnect"}
          </button>
          <button type="button" onClick={run(onDisable)} disabled={busy}>
            Disable
          </button>
        </>
      ) : (
        <button type="button" onClick={run(onEnable)} disabled={busy}>
          Enable
        </button>
      )}
      <button type="button" className="danger" onClick={() => setConfirming(true)} disabled={busy}>
        Remove
      </button>
    </>
  );
}
