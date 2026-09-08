import type { MemoryItem } from "../model/types";

/** One remembered thing, with what it is true of and when it was written. */
export function MemoryLine({ item }: { item: MemoryItem }) {
  return (
    <li className="memory">
      <span className="badge quiet">{item.scope === "USER" ? "you" : "here"}</span>
      <span>{item.content}</span>
      <span className="note">{item.created_at.slice(0, 10)}</span>
    </li>
  );
}
