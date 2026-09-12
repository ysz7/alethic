/**
 * The contexts of work, and which one this machine is in.
 *
 * Adding one is behind a button rather than a form standing open: a screen that
 * shows what exists is read far more often than it is added to.
 */

import { useState } from "react";

import { WorkspaceRow, type Workspace } from "../../../../entities/workspace";
import { NewWorkspaceForm } from "../../../../features/switch-workspace";
import { useRuntime } from "../../../../shared/api";
import { Modal, PlusIcon } from "../../../../shared/ui";
import { useWorkspaces } from "../../../../widgets/workspace-bar";

export function WorkspacesSection({ onSwitched }: { onSwitched?: () => void }) {
  const client = useRuntime();
  const workspaces = useWorkspaces(client, onSwitched);
  const [adding, setAdding] = useState(false);

  return (
    <>
      <p className="lede">
        A workspace separates one context of work from another: its own files,
        its own documents, its own history. Switching moves what the employees
        can see; work already running keeps the workspace it started in.
      </p>

      {workspaces.problem && (
        <p className="problem" role="alert">
          {workspaces.problem}
        </p>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Workspaces</h2>
          <button
            type="button"
            className="addbtn"
            onClick={() => setAdding(true)}
            disabled={!workspaces.ready}
          >
            <PlusIcon />
            New workspace
          </button>
        </div>
        <div className="card">
          {workspaces.workspaces.length === 0 && workspaces.ready && (
            <p className="card-empty">Nothing here yet.</p>
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
        </div>
      </section>

      {adding && (
        <Modal
          title="New workspace"
          note="Its own files, its own documents, its own history."
          onClose={() => setAdding(false)}
        >
          <NewWorkspaceForm
            // Closed once the operation returns, whether or not it worked: the
            // hook reports a refusal on the section behind this, and a dialog
            // that stayed open would hide the sentence explaining why.
            onAdd={async (name, description) => {
              await workspaces.add(name, description);
              setAdding(false);
            }}
            disabled={!workspaces.ready}
          />
        </Modal>
      )}
    </>
  );
}
