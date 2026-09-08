import { useState } from "react";

import { SettingsPage } from "../pages/settings";
import { WorkspacePage } from "../pages/workspace";
import { RuntimeProvider, type RuntimeClient } from "../shared/api";

/**
 * The application: one provider, two screens.
 *
 * The second screen is settings, and the switch between them is the only state
 * the app layer holds - a page is either shown or it is not, which is as much
 * as this layer is allowed to know. Everything a person can do is still a
 * feature, and everything a feature does is still one call into the runtime.
 */
export function App({ client, baseUrl }: { client?: RuntimeClient; baseUrl?: string }) {
  const [showing, setShowing] = useState<"work" | "settings">("work");
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
      </nav>
      {showing === "work" ? <WorkspacePage /> : <SettingsPage />}
    </RuntimeProvider>
  );
}
