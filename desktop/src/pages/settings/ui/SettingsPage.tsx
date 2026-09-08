/**
 * Settings, which is currently one thing: the services Alethic can reach.
 *
 * Deliberately not an administration console. Everything else configurable is
 * a file on this machine that the runtime already reads, and a screen that
 * mirrored those files would be a second place to change them - the one that
 * goes stale.
 */

import {
  CapabilityList,
  IntegrationCard,
  type Integration,
} from "../../../entities/integration";
import { AddIntegrationForm } from "../../../features/add-integration";
import { IntegrationActions } from "../../../features/manage-integration";
import { useRuntime } from "../../../shared/api";
import { useIntegrations } from "../model/useIntegrations";

/** Offered when adding a service. The core refuses anything outside its own list. */
const CAPABILITIES = ["EMAIL", "WEB_BROWSING", "FILE_ACCESS", "CODE"];

export function SettingsPage() {
  const client = useRuntime();
  const { ready, available, problem, integrations, add, connect, enable, disable, remove } =
    useIntegrations(client);

  return (
    <section className="settings" aria-label="Settings">
      <h2>Integrations</h2>
      {!available && ready && (
        <p className="note">
          Integrations are switched off on this machine
          (ALETHIC_FLAGS__INTEGRATIONS=false).
        </p>
      )}
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {available && (
        <>
          {integrations.length === 0 && ready && (
            <p className="note">Nothing is connected yet.</p>
          )}
          {integrations.map((integration: Integration) => (
            <IntegrationCard
              key={integration.id}
              integration={integration}
              actions={
                <IntegrationActions
                  integration={integration}
                  onConnect={connect}
                  onEnable={enable}
                  onDisable={disable}
                  onRemove={remove}
                />
              }
            >
              <CapabilityList tools={integration.tools} />
            </IntegrationCard>
          ))}
          <AddIntegrationForm onAdd={add} disabled={!ready} known={CAPABILITIES} />
          <p className="note">
            A capability marked <strong>!</strong> waits for you before it runs. Alethic
            decides that, not this window.
          </p>
        </>
      )}
    </section>
  );
}
