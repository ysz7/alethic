/**
 * Where the request is typed. The one action the whole window exists for.
 *
 * Enter sends, Shift-Enter breaks the line - the convention people already
 * have. The field is never disabled while work is running: someone who has
 * thought of the next thing should be able to write it down, and nothing is
 * queued behind a disabled textarea.
 */

import { useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (request: string) => void | Promise<void>;
  disabled?: boolean;
  placeholder?: string;
}

export function RequestComposer({ onSend, disabled = false, placeholder }: Props) {
  const [text, setText] = useState("");

  const submit = async () => {
    const request = text.trim();
    if (!request || disabled) return;
    setText("");
    await onSend(request);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <textarea
        aria-label="Tell Alethic what you need"
        placeholder={placeholder ?? "Tell Alethic what you need…"}
        rows={1}
        value={text}
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" disabled={disabled || text.trim().length === 0}>
        Send
      </button>
    </form>
  );
}
