/**
 * What the platform noted about working here.
 *
 * Shown and not editable. Reading memory and forgetting it are two contracts in
 * the core (ADR 0009) and this window holds only the first, so there is no
 * button here that would put "delete" one click from "show me".
 */

import { MemoryLine } from "../../../../entities/memory";
import { useRuntime } from "../../../../shared/api";
import { useMemory } from "../../model/useMemory";

export function MemorySection() {
  const client = useRuntime();
  const memory = useMemory(client);

  return (
    <>
      <p className="lede">
        Written by the platform about its own work, and shown rather than
        editable: forgetting is a separate thing to be able to do, and this
        window cannot. Pruning is <code>prometheus memory --prune</code>.
      </p>

      <section className="panel">
        <div className="panel-head">
          <h2>What is remembered here</h2>
        </div>
        <div className="card">
          {memory.items.length === 0 && memory.ready ? (
            <p className="card-empty">Nothing remembered yet.</p>
          ) : (
            <ul className="memories">
              {memory.items.map((item) => (
                <MemoryLine key={item.id} item={item} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
