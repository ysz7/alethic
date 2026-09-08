/**
 * The selector that says which context the window is showing.
 *
 * A widget rather than part of the frame, because it needs the runtime and the
 * app layer holds no data. It shows nothing at all while there is one
 * workspace: a selector with a single option is a control that teaches the user
 * it does nothing.
 */

import { WorkspaceSwitcher } from "../../../features/switch-workspace";
import { useRuntime } from "../../../shared/api";
import { useWorkspaces } from "../model/useWorkspaces";

export function WorkspaceBar({ onSwitched }: { onSwitched?: () => void }) {
  const client = useRuntime();
  const { ready, workspaces, use } = useWorkspaces(client, onSwitched);
  if (!ready || workspaces.length < 2) return null;
  return <WorkspaceSwitcher workspaces={workspaces} onUse={use} />;
}
