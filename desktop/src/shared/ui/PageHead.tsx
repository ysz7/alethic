/**
 * The bar across the top of every page: what this is, which context it is in,
 * and the one or two things that act on it.
 *
 * It is a drag region, because the window has no title bar of its own - the
 * shell draws the traffic lights over the content (`titleBarStyle: Overlay`),
 * and a window that can only be moved by its sidebar reads as broken the moment
 * the sidebar is closed.
 */

import type { ReactNode } from "react";

import { PanelIcon } from "./icons";

interface Props {
  title: string;
  chip?: ReactNode;
  children?: ReactNode;
  railOpen?: boolean;
  onOpenRail?: () => void;
}

export function PageHead({ title, chip, children, railOpen = true, onOpenRail }: Props) {
  return (
    <header className="head" data-tauri-drag-region>
      {!railOpen && onOpenRail && (
        <button type="button" className="icobtn" aria-label="Open sidebar" onClick={onOpenRail}>
          <PanelIcon />
        </button>
      )}
      <h1 data-tauri-drag-region>{title}</h1>
      {chip && <span className="head-chip">{chip}</span>}
      {children && <div className="head-right">{children}</div>}
    </header>
  );
}
