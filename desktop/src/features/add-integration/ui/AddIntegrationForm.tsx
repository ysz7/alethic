/**
 * Adding any MCP server, without knowing anything about a particular one.
 *
 * The form asks for a name and a command, because that is what an stdio MCP
 * server is. There is nothing about Gmail or GitHub here, and there should
 * never be: a flow with a service baked into it is a flow that has to be
 * written again for the next service.
 *
 * The credential field is a convenience over two calls - store the secret,
 * then name it on the integration - and the value is sent and dropped. It is
 * never read back, never put in component state that outlives the submit, and
 * has nowhere to be shown.
 */

import { useState, type FormEvent } from "react";

interface Submission {
  name: string;
  command: string;
  args: string[];
  capabilities: string[];
  secretName: string;
  secretValue: string;
}

interface Props {
  onAdd: (submission: Submission) => Promise<void>;
  disabled?: boolean;
  /** The capability vocabulary, from the runtime. Closed on purpose. */
  known?: string[];
}

export function AddIntegrationForm({ onAdd, disabled, known = [] }: Props) {
  const [name, setName] = useState("");
  const [command, setCommand] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [secretName, setSecretName] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const [program, ...args] = command.trim().split(/\s+/).filter(Boolean);
    if (!name.trim() || !program || busy) return;
    setBusy(true);
    try {
      await onAdd({
        name: name.trim(),
        command: program,
        args,
        capabilities,
        secretName: secretName.trim(),
        secretValue,
      });
      setName("");
      setCommand("");
      setCapabilities([]);
      setSecretName("");
      setSecretValue("");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (capability: string) =>
    setCapabilities((chosen) =>
      chosen.includes(capability)
        ? chosen.filter((entry) => entry !== capability)
        : [...chosen, capability],
    );

  return (
    <form className="add-integration" onSubmit={submit}>
      <h3>Add MCP server</h3>
      <label>
        Name
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="notes"
          disabled={disabled || busy}
        />
      </label>
      <label>
        Command
        <input
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          placeholder="npx -y @some/mcp-server"
          disabled={disabled || busy}
        />
      </label>
      {known.length > 0 && (
        <fieldset className="capabilities-choice">
          <legend>What kind of work should reach it?</legend>
          {known.map((capability) => (
            <label key={capability}>
              <input
                type="checkbox"
                checked={capabilities.includes(capability)}
                onChange={() => toggle(capability)}
                disabled={disabled || busy}
              />
              {capability}
            </label>
          ))}
        </fieldset>
      )}
      <details className="credential">
        <summary>Needs a credential</summary>
        <label>
          Credential name
          <input
            value={secretName}
            onChange={(event) => setSecretName(event.target.value)}
            placeholder="NOTES_TOKEN"
            disabled={disabled || busy}
          />
        </label>
        <label>
          Credential value
          <input
            type="password"
            value={secretValue}
            onChange={(event) => setSecretValue(event.target.value)}
            disabled={disabled || busy}
            autoComplete="off"
          />
        </label>
        <p className="note">Kept on this machine and never shown again.</p>
      </details>
      <button type="submit" disabled={disabled || busy || !name.trim() || !command.trim()}>
        {busy ? "Adding…" : "Add"}
      </button>
    </form>
  );
}

export type { Submission };
