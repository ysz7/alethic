/**
 * The selector in the frame: which context this machine is working in.
 *
 * A list of what exists and one call to switch. It shows no count of anything
 * and derives no state - a workspace is active because the runtime says so, and
 * a window that remembered its own answer would disagree with the next process
 * that opened the same database.
 */

import type { Workspace } from "../../../entities/workspace";

interface Props {
  workspaces: Workspace[];
  onUse: (id: string) => Promise<void>;
  disabled?: boolean;
}

export function WorkspaceSwitcher({ workspaces, onUse, disabled }: Props) {
  const active = workspaces.find((workspace) => workspace.active);
  if (workspaces.length === 0) return null;
  return (
    <label className="switcher">
      <span className="visually-hidden">Workspace</span>
      <select
        value={active?.id ?? ""}
        disabled={disabled || workspaces.length < 2}
        onChange={(event) => void onUse(event.target.value)}
      >
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.name}
          </option>
        ))}
      </select>
    </label>
  );
}
