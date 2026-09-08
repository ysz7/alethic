import { useState } from "react";

import { ChatPage } from "../pages/chat";
import { SettingsPage } from "../pages/settings";
import { RuntimeProvider, type RuntimeClient } from "../shared/api";
import { WorkspaceBar } from "../widgets/workspace-bar";

/**
 * The application: one provider, two screens, and which workspace they are of.
 *
 * The app layer holds two pieces of state and no rules: which page is shown,
 * and a number that changes when the workspace does. The second one remounts
 * the page, because everything on it - the thread, the history, the documents -
 * belongs to a workspace, and a screen left over from the previous one would be
 * showing another context's work under the new context's name.
 */
export function App({ client, baseUrl }: { client?: RuntimeClient; baseUrl?: string }) {
  const [showing, setShowing] = useState<"work" | "settings">("work");
  const [workspace, setWorkspace] = useState(0);
  const switched = () => setWorkspace((count) => count + 1);
  return (
    <RuntimeProvider client={client} baseUrl={baseUrl}>
      <nav className="places">
        <button
          type="button"
          className={showing === "work" ? "here" : ""}
          onClick={() => setShowing("work")}
        >
          Work
        </button>
        <button
          type="button"
          className={showing === "settings" ? "here" : ""}
          onClick={() => setShowing("settings")}
        >
          Settings
        </button>
        <WorkspaceBar onSwitched={switched} />
      </nav>
      {showing === "work" ? (
        <ChatPage key={workspace} />
      ) : (
        <SettingsPage key={workspace} onSwitched={switched} />
      )}
    </RuntimeProvider>
  );
}
