import React from "react";
import ReactDOM from "react-dom/client";
import { isTauri } from "@tauri-apps/api/core";

import "@fontsource/onest/400.css";
import "@fontsource/onest/500.css";
import "@fontsource/onest/600.css";
import "@fontsource/onest/700.css";

import { App } from "./app";
import { report, resolveBaseUrl } from "./shared/api";
import "./app/styles/global.css";

// Bundled rather than fetched: the window's content security policy allows
// nothing but itself, and a typeface that depends on a network is a typeface
// that falls back without a word on an aeroplane.

// A window that fails to draw must say so somewhere a person can read. Without
// this, a page that threw on its first render looks exactly like a page that is
// working and has nothing to show yet.
window.addEventListener("error", (event) => report(String(event.message)));
window.addEventListener("unhandledrejection", (event) => report(String(event.reason)));

// On macOS the shell draws the traffic lights over the page, and the stylesheet
// makes room for them only where they actually are.
if (isTauri() && /Mac/i.test(navigator.userAgent)) {
  document.documentElement.dataset.shell = "mac";
}

/**
 * Ask the shell where the runtime is, then draw.
 *
 * Resolved before the first render rather than after it: a window that started
 * against the default and switched would issue its first requests to a runtime
 * that may not be the one it was pointed at.
 */
void resolveBaseUrl()
  .then((baseUrl) => {
    ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
      <React.StrictMode>
        <App baseUrl={baseUrl} />
      </React.StrictMode>,
    );
  })
  .catch((error: unknown) => report(String(error)));
