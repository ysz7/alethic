/**
 * Which context this machine is working in, as a chip under the request.
 *
 * A list of what exists and one call to switch. It shows no count of anything
 * and derives no state - a workspace is active because the runtime says so, and
 * a window that remembered its own answer would disagree with the next process
 * that opened the same database.
 *
 * The chip is drawn and the native list sits invisibly over it: the operating
 * system's own menu is the accessible one, and the keyboard already knows it.
 */

import type { Workspace } from "../../../entities/workspace";
import { ChevronDown } from "../../../shared/ui";

interface Props {
  workspaces: Workspace[];
  onUse: (id: string) => Promise<void>;
  disabled?: boolean;
}

export function WorkspaceSwitcher({ workspaces, onUse, disabled }: Props) {
  const active = workspaces.find((workspace) => workspace.active);
  if (workspaces.length === 0) return null;
  return (
    <label className="dockchip switcher">
      Workspace <b>{active?.name ?? "—"}</b>
      <ChevronDown />
      <select
        aria-label="Workspace"
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
