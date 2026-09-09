/**
 * Adding a model, by picking one where that is possible.
 *
 * When the chosen connection is a runner that can be asked what it has, the
 * model becomes a list. A text field accepts `gemma3:27` and fails inside a
 * task hours later, which is the furthest possible point from the typo.
 */

import { useEffect, useState, type FormEvent } from "react";

import type { Connection } from "../../../entities/provider";

export interface ModelSubmission {
  name: string;
  model: string;
  connection: string;
  capabilities: string[];
}

interface Props {
  connections: Connection[];
  /** Asked of the runtime; empty where the provider cannot be asked. */
  installed: (connection: string) => Promise<string[]>;
  onAdd: (submission: ModelSubmission) => Promise<void>;
  known: string[];
  disabled?: boolean;
}

export function AddModelForm({ connections, installed, onAdd, known, disabled }: Props) {
  const [name, setName] = useState("");
  // As in the connection form: the list arrives after the first render, so the
  // choice falls back to the first one rather than being captured from nothing.
  const [chosen, setConnection] = useState("");
  const connection = chosen || connections[0]?.name || "";
  const [model, setModel] = useState("");
  const [choices, setChoices] = useState<string[]>([]);
  const [capabilities, setCapabilities] = useState<string[]>(["TEXT_REASONING", "TOOL_CALLING"]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    if (!connection) {
      setChoices([]);
      return;
    }
    installed(connection)
      .then((found) => {
        if (current) setChoices(found);
      })
      .catch(() => {
        // Not being able to ask is the ordinary case for a hosted provider.
        // The field stays a text field and nothing about the page breaks.
        if (current) setChoices([]);
      });
    return () => {
      current = false;
    };
  }, [connection, installed]);

  const toggle = (value: string) =>
    setCapabilities((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !model.trim() || busy) return;
    setBusy(true);
    try {
      await onAdd({
        name: name.trim(),
        model: model.trim(),
        connection,
        capabilities,
      });
      setName("");
      setModel("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="add-integration" onSubmit={submit} aria-label="Add a model">
      <label>
        Entry name
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="fast-local"
          disabled={disabled || busy}
        />
      </label>
      <label>
        Through
        <select
          value={connection}
          onChange={(event) => setConnection(event.target.value)}
          disabled={disabled || busy}
        >
          {connections.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Model
        {choices.length > 0 ? (
          <select
            value={model}
            onChange={(event) => setModel(event.target.value)}
            disabled={disabled || busy}
          >
            <option value="">Choose one…</option>
            {choices.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={model}
            onChange={(event) => setModel(event.target.value)}
            placeholder="the model's own name"
            disabled={disabled || busy}
          />
        )}
      </label>
      <fieldset>
        <legend>What it may be picked for</legend>
        {known.map((item) => (
          <label key={item} className="checkbox">
            <input
              type="checkbox"
              checked={capabilities.includes(item)}
              onChange={() => toggle(item)}
              disabled={disabled || busy}
            />
            {item.toLowerCase().replace(/_/g, " ")}
          </label>
        ))}
      </fieldset>
      <button type="submit" disabled={disabled || busy || !name.trim() || !model.trim()}>
        {busy ? "Adding…" : "Add model"}
      </button>
    </form>
  );
}
