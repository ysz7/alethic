/**
 * Settings: the contexts of work, what they know, and the services Alethic can reach.
 *
 * Deliberately not an administration console. Everything else configurable is
 * a file on this machine that the runtime already reads, and a screen that
 * mirrored those files would be a second place to change them - the one that
 * goes stale. What is here is what has no file: a workspace, a document
 * somebody brought, and what the platform has remembered about working here.
 */

import { DocumentCard, type Document } from "../../../entities/document";
import {
  CapabilityList,
  IntegrationCard,
  type Integration,
} from "../../../entities/integration";
import { MemoryLine } from "../../../entities/memory";
import {
  ConnectionCard,
  ModelRow,
  type Connection,
  type ModelEntry,
} from "../../../entities/provider";
import { WorkspaceRow, type Workspace } from "../../../entities/workspace";
import { AddIntegrationForm } from "../../../features/add-integration";
import { IntegrationActions } from "../../../features/manage-integration";
import { AddDocumentForm, DocumentActions } from "../../../features/manage-documents";
import {
  AddConnectionForm,
  AddModelForm,
  WorkRouting,
} from "../../../features/manage-providers";
import { NewWorkspaceForm } from "../../../features/switch-workspace";
import { useRuntime } from "../../../shared/api";
import { useWorkspaces } from "../../../widgets/workspace-bar";
import { useDocuments } from "../model/useDocuments";
import { useIntegrations } from "../model/useIntegrations";
import { useMemory } from "../model/useMemory";
import { useProviders } from "../model/useProviders";

/** Offered when adding a service. The core refuses anything outside its own list. */
const CAPABILITIES = ["EMAIL", "WEB_BROWSING", "FILE_ACCESS", "CODE"];

/** What a model may be picked for. The router refuses anything outside its list. */
const MODEL_CAPABILITIES = [
  "TEXT_REASONING",
  "TOOL_CALLING",
  "STRUCTURED_OUTPUT",
  "LONG_CONTEXT",
  "CODE",
  "VISION",
  "EMBEDDING",
];

/**
 * The kinds of work a model can be given, in the order they happen in a run.
 * Named here only to lay the rows out; what each one means, and which model it
 * would otherwise reach, is the router's answer and arrives from the runtime.
 */
const TASK_KINDS = [
  "PLANNING",
  "EXECUTION",
  "VERIFICATION",
  "SYNTHESIS",
  "EXTRACTION",
  "CONVERSATION",
  "EMBEDDING",
];

export function SettingsPage({ onSwitched }: { onSwitched?: () => void } = {}) {
  const client = useRuntime();
  const { ready, available, problem, integrations, add, connect, enable, disable, remove } =
    useIntegrations(client);
  const workspaces = useWorkspaces(client, onSwitched);
  const documents = useDocuments(client);
  const memory = useMemory(client);
  const providers = useProviders(client);

  return (
    <section className="settings" aria-label="Settings">
      <h2>Workspaces</h2>
      <p className="note">
        A workspace separates one context of work from another: its own files,
        its own documents, its own history. Switching moves what the employees
        can see; work already running keeps the workspace it started in.
      </p>
      {workspaces.problem && (
        <p className="problem" role="alert">
          {workspaces.problem}
        </p>
      )}
      {workspaces.workspaces.map((workspace: Workspace) => (
        <WorkspaceRow
          key={workspace.id}
          workspace={workspace}
          actions={
            <span className="actions">
              {!workspace.active && (
                <button type="button" onClick={() => void workspaces.use(workspace.id)}>
                  Work here
                </button>
              )}
              {!workspace.is_default && (
                <button type="button" onClick={() => void workspaces.remove(workspace.id)}>
                  Remove
                </button>
              )}
            </span>
          }
        />
      ))}
      <NewWorkspaceForm onAdd={workspaces.add} disabled={!workspaces.ready} />

      <h2>Documents</h2>
      <p className="note">
        What this workspace knows because you put it here. Employees quote these
        with their source; they are not the platform's own notes.
      </p>
      {!documents.available && documents.ready && (
        <p className="note">
          Documents are switched off on this machine (ALETHIC_FLAGS__KNOWLEDGE=false).
        </p>
      )}
      {documents.problem && (
        <p className="problem" role="alert">
          {documents.problem}
        </p>
      )}
      {documents.available && (
        <>
          {documents.documents.length === 0 && documents.ready && (
            <p className="note">Nothing added yet.</p>
          )}
          {documents.documents.map((document: Document) => (
            <DocumentCard
              key={document.id}
              document={document}
              actions={
                <DocumentActions
                  document={document}
                  onReindex={documents.reindex}
                  onRemove={documents.remove}
                />
              }
            />
          ))}
          <AddDocumentForm onAdd={documents.add} disabled={!documents.ready} />
        </>
      )}

      <h2>What is remembered here</h2>
      <p className="note">
        Written by the platform about its own work, and shown rather than
        editable: forgetting is a separate thing to be able to do, and this
        window cannot.
      </p>
      {memory.items.length === 0 && memory.ready ? (
        <p className="note">Nothing remembered yet.</p>
      ) : (
        <ul className="memories">
          {memory.items.map((item) => (
            <MemoryLine key={item.id} item={item} />
          ))}
        </ul>
      )}

      <h2>Providers and models</h2>
      <p className="note">
        A provider is a kind; a connection is an account. Two keys to one vendor
        are two connections, and a model says which one it is reached through.
        A key is stored encrypted and never shown again - only replaced.
      </p>
      {providers.problem && (
        <p className="problem" role="alert">
          {providers.problem}
        </p>
      )}
      {providers.settings.connections.length === 0 && providers.ready && (
        <p className="note">
          Nothing added. The machine is using whatever key it was configured
          with and the models it shipped with.
        </p>
      )}
      {providers.settings.connections.map((connection: Connection) => (
        <ConnectionCard
          key={connection.id}
          connection={connection}
          actions={
            <div className="actions">
              <button type="button" onClick={() => void providers.dropProvider(connection.name)}>
                Remove
              </button>
            </div>
          }
        />
      ))}
      <AddConnectionForm kinds={providers.settings.kinds} onAdd={providers.addProvider} />

      <h3>Models</h3>
      {providers.settings.models.map((entry: ModelEntry) => (
        <ModelRow
          key={entry.name}
          entry={entry}
          actions={
            <div className="actions">
              <button type="button" onClick={() => void providers.dropEntry(entry.name)}>
                Remove
              </button>
            </div>
          }
        />
      ))}
      {providers.settings.connections.length > 0 && (
        <AddModelForm
          connections={providers.settings.connections}
          installed={providers.installed}
          onAdd={providers.addEntry}
          known={MODEL_CAPABILITIES}
        />
      )}

      <h3>Where work goes</h3>
      <p className="note">
        Each kind of work can be given to one model. Left to the router, it
        picks from what the work needs and what each model can do.
      </p>
      <WorkRouting
        kinds={TASK_KINDS}
        defaults={providers.settings.defaults}
        models={providers.settings.models}
        onRoute={providers.route}
      />

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
