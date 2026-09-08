import { WorkspacePage } from "../pages/workspace";
import { RuntimeProvider, type RuntimeClient } from "../shared/api";

/**
 * The application: one provider, one screen.
 *
 * The whole of the app layer. Everything a person can do is a feature, and
 * everything a feature does is one call into the runtime - so there is nothing
 * left here to grow into a place where decisions get made.
 */
export function App({ client, baseUrl }: { client?: RuntimeClient; baseUrl?: string }) {
  return (
    <RuntimeProvider client={client} baseUrl={baseUrl}>
      <WorkspacePage />
    </RuntimeProvider>
  );
}
