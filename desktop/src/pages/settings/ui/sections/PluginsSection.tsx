/**
 * Everything this machine can reach the world with, in one place.
 *
 * Two tabs, because there are two ways a capability gets here and only two:
 * the platform shipped with it, or somebody connected a server that offers it.
 * Below the tool boundary they are the same thing - an MCP server's tool is an
 * ordinary `Tool` in the ordinary registry (ADR 0015) - so the planner, the
 * gate and the audit already treat them alike, and this screen agrees.
 *
 * What is built in has no switch. A tool reaches an employee by being listed in
 * that employee's declaration, so the honest answer to "is it on?" is who lists
 * it, and a toggle here would be a second way to say the same thing - free to
 * disagree with the files that actually decide.
 */

import { useState } from "react";

import {
  CapabilityList,
  IntegrationCard,
  type Integration,
} from "../../../../entities/integration";
import { ToolRow, type Tool } from "../../../../entities/tool";
import { AddIntegrationForm } from "../../../../features/add-integration";
import { IntegrationActions } from "../../../../features/manage-integration";
import { useRuntime } from "../../../../shared/api";
import { Modal, PlusIcon } from "../../../../shared/ui";
import { useIntegrations } from "../../model/useIntegrations";
import { useTools } from "../../model/useTools";

/** Offered when connecting a service. The core refuses anything outside its own list. */
const CAPABILITIES = ["EMAIL", "WEB_BROWSING", "FILE_ACCESS", "CODE"];

export function PluginsSection() {
  const client = useRuntime();
  const tools = useTools(client);
  const { ready, available, problem, integrations, add, connect, enable, disable, remove } =
    useIntegrations(client);
  const [tab, setTab] = useState<"built-in" | "servers">("built-in");
  const [adding, setAdding] = useState(false);

  return (
    <>
      <p className="lede">
        A plugin is one thing the platform can do to the world. Some shipped with
        it; the rest arrive from a server you connected. Which employee may use
        any of them is that employee's own declaration, and what each one does to
        the world is classified here rather than by whoever wrote it.
      </p>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "built-in"}
          className={tab === "built-in" ? "tab on" : "tab"}
          onClick={() => setTab("built-in")}
        >
          Built in <span className="count">{tools.tools.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "servers"}
          className={tab === "servers" ? "tab on" : "tab"}
          onClick={() => setTab("servers")}
        >
          MCP servers <span className="count">{integrations.length}</span>
        </button>
      </div>

      {tab === "built-in" && (
        <>
          {tools.problem && (
            <p className="problem" role="alert">
              {tools.problem}
            </p>
          )}
          <section className="panel">
            <div className="card">
              {tools.tools.length === 0 && tools.ready && (
                <p className="card-empty">This machine offers nothing yet.</p>
              )}
              {tools.tools.map((tool: Tool) => (
                <ToolRow key={tool.name} tool={tool} />
              ))}
            </div>
          </section>
          <p className="note">
            A plugin marked <strong>asks first</strong> waits for you before it
            runs. The policy engine decides that, not this window - and it
            follows from what the plugin does to the world, so no declaration can
            lower it.
          </p>
        </>
      )}

      {tab === "servers" && (
        <>
          {!available && ready && (
            <p className="note">
              Connecting servers is switched off on this machine
              (PROMETHEUS_FLAGS__INTEGRATIONS=false).
            </p>
          )}
          {problem && (
            <p className="problem" role="alert">
              {problem}
            </p>
          )}
          {available && (
            <>
              <section className="panel">
                <div className="panel-head">
                  <h2>MCP servers</h2>
                  <button
                    type="button"
                    className="addbtn"
                    onClick={() => setAdding(true)}
                    disabled={!ready}
                  >
                    <PlusIcon />
                    Add server
                  </button>
                </div>
                <div className="card">
                  {integrations.length === 0 && ready && (
                    <p className="card-empty">Nothing is connected yet.</p>
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
                </div>
              </section>
              <p className="note">
                A capability marked <strong>!</strong> waits for you before it
                runs. Prometheus decides that, not this window.
              </p>

              {adding && (
                <Modal
                  title="Add MCP server"
                  note="A name and the command that starts it. Nothing here knows about a particular service."
                  onClose={() => setAdding(false)}
                >
                  <AddIntegrationForm
                    onAdd={async (submission) => {
                      await add(submission);
                      setAdding(false);
                    }}
                    disabled={!ready}
                    known={CAPABILITIES}
                  />
                </Modal>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
