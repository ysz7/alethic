import { useState, type FormEvent } from "react";

/**
 * A path, not a file picker upload. The runtime reads the file itself, so what
 * this collects is where it is - and a person who dragged a file onto the
 * window has exactly that.
 */
export function AddDocumentForm({
  onAdd,
  disabled,
}: {
  onAdd: (path: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!path.trim()) return;
    setBusy(true);
    try {
      await onAdd(path.trim());
      setPath("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="new-document" onSubmit={submit}>
      <input
        value={path}
        placeholder="/path/to/the/document.pdf"
        aria-label="Path to the document"
        onChange={(event) => setPath(event.target.value)}
      />
      <button type="submit" disabled={disabled || busy || !path.trim()}>
        Add document
      </button>
    </form>
  );
}
