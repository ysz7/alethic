import { useState, type FormEvent } from "react";

/** Adding a context. Two fields, because a workspace is a name and a reason. */
export function NewWorkspaceForm({
  onAdd,
  disabled,
}: {
  onAdd: (name: string, description: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onAdd(name.trim(), description.trim());
      setName("");
      setDescription("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="new-workspace" onSubmit={submit}>
      <input
        value={name}
        placeholder="Name, such as Work or Client A"
        aria-label="Workspace name"
        onChange={(event) => setName(event.target.value)}
      />
      <input
        value={description}
        placeholder="What it is for (optional)"
        aria-label="What this workspace is for"
        onChange={(event) => setDescription(event.target.value)}
      />
      <button type="submit" disabled={disabled || busy || !name.trim()}>
        Add workspace
      </button>
    </form>
  );
}
