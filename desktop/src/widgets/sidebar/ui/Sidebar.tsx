/**
 * The sidebar: a new task, the threads of this workspace, and the way to
 * everything that is not a conversation.
 *
 * It lists and navigates; it opens nothing itself. Which thread is shown and
 * which page is up are the frame's state, told to it and told back through the
 * callbacks, so the list and the page cannot disagree about where the person is.
 *
 * A thread nobody has said anything in is not listed. Those exist - a window
 * used to open one every time it started - and a list of blank rows is a list
 * that teaches a person to stop reading it.
 */

import { useMemo, useState } from "react";

import { useRuntime } from "../../../shared/api";
import { GearIcon, LogoMark, PanelIcon, PlusIcon, SearchIcon } from "../../../shared/ui";
import { groupByDay, markFor } from "../model/presentation";
import { useThreads } from "../model/useThreads";

interface Props {
  selected: string | null;
  settingsOpen: boolean;
  /** Changes when the page did something the list should show at once. */
  refresh: number;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  onSettings: () => void;
  onClose: () => void;
}

export function Sidebar({
  selected,
  settingsOpen,
  refresh,
  onSelect,
  onNew,
  onSettings,
  onClose,
}: Props) {
  const client = useRuntime();
  const { threads, workspace, spent } = useThreads(client, refresh);
  const [search, setSearch] = useState("");

  const groups = useMemo(() => {
    const wanted = search.trim().toLowerCase();
    const shown = threads
      .filter((thread) => thread.messages > 0)
      .filter((thread) => !wanted || thread.title.toLowerCase().includes(wanted));
    return groupByDay(shown);
  }, [threads, search]);

  return (
    <aside className="rail" aria-label="Tasks">
      <div className="rail-top" data-tauri-drag-region>
        <span className="logo" data-tauri-drag-region>
          <LogoMark width={16} height={16} />
          Prometheus
        </span>
        <button type="button" className="icobtn" aria-label="Collapse sidebar" onClick={onClose}>
          <PanelIcon />
        </button>
      </div>

      <button type="button" className="newbtn" onClick={onNew}>
        <PlusIcon />
        New task
      </button>

      <label className="search">
        <SearchIcon />
        <input
          value={search}
          placeholder="Search tasks"
          aria-label="Search tasks"
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>

      <nav className="threads" aria-label="Threads">
        {groups.length === 0 && (
          <p className="tempty">{search ? "Nothing by that name." : "Nothing asked here yet."}</p>
        )}
        {groups.map((group) => (
          <div key={group.label}>
            <p className="tgroup">{group.label}</p>
            {group.threads.map((thread) => {
              const mark = markFor(thread.status);
              return (
                <button
                  key={thread.id}
                  type="button"
                  className={thread.id === selected ? "thread on" : "thread"}
                  aria-current={thread.id === selected ? "page" : undefined}
                  onClick={() => onSelect(thread.id)}
                >
                  <span className="thread-title">{thread.title || "Untitled"}</span>
                  <span className="thread-meta">
                    <i className={`pip ${mark.tone}`} aria-hidden="true" />
                    {mark.label}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="rail-foot">
        <button
          type="button"
          className={settingsOpen ? "acct on" : "acct"}
          aria-label="Settings"
          onClick={onSettings}
        >
          <span className="avatar" aria-hidden="true">
            {(workspace || "P").slice(0, 1).toUpperCase()}
          </span>
          <span className="acct-meta">
            <b>{workspace || "Workspace"}</b>
            <span>
              Settings
              {spent !== null && ` · $${spent.toFixed(2)} spent`}
            </span>
          </span>
          <GearIcon className="acct-gear" />
        </button>
      </div>
    </aside>
  );
}
