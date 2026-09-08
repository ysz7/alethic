import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./app";
import { report, resolveBaseUrl } from "./shared/api";
import "./app/styles/global.css";

// A window that fails to draw must say so somewhere a person can read. Without
// this, a page that threw on its first render looks exactly like a page that is
// working and has nothing to show yet.
window.addEventListener("error", (event) => report(String(event.message)));
window.addEventListener("unhandledrejection", (event) => report(String(event.reason)));

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
