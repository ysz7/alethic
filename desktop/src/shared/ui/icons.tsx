/**
 * The drawn marks the window uses, in one place.
 *
 * Inline SVG rather than an icon font or a package: a dozen strokes cost less
 * than a dependency, and a packaged window must not reach anywhere for them.
 * Every one takes `currentColor`, so its colour is the text's around it.
 */

import type { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement>;

const base = { fill: "none", "aria-hidden": true } as const;

export const LogoMark = (props: Props) => (
  <svg viewBox="0 0 24 24" {...base} {...props}>
    <circle cx="12" cy="12" r="9.4" stroke="currentColor" strokeWidth="1.6" />
    <ellipse cx="12" cy="12" rx="4.4" ry="9.4" stroke="currentColor" strokeWidth="1.6" />
    <path d="M2.6 12h18.8" stroke="currentColor" strokeWidth="1.6" />
  </svg>
);

export const PanelIcon = (props: Props) => (
  <svg viewBox="0 0 20 20" {...base} {...props}>
    <rect x="2.5" y="3.5" width="15" height="13" rx="3" stroke="currentColor" strokeWidth="1.5" />
    <path d="M8 3.5v13" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

export const PlusIcon = (props: Props) => (
  <svg viewBox="0 0 14 14" {...base} {...props}>
    <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);

export const SearchIcon = (props: Props) => (
  <svg viewBox="0 0 16 16" {...base} {...props}>
    <circle cx="7.2" cy="7.2" r="4.6" stroke="currentColor" strokeWidth="1.5" />
    <path d="M10.8 10.8 14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

export const ChevronDown = (props: Props) => (
  <svg viewBox="0 0 12 12" {...base} {...props}>
    <path
      d="M3 4.5 6 7.5l3-3"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const ChevronRight = (props: Props) => (
  <svg viewBox="0 0 12 12" {...base} {...props}>
    <path
      d="M4 2.5 8 6l-4 3.5"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const WarningIcon = (props: Props) => (
  <svg viewBox="0 0 14 14" {...base} {...props}>
    <path d="M7 1.6 12.6 12H1.4L7 1.6Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    <path d="M7 5.6v2.8M7 10.2v.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

export const ArrowUpIcon = (props: Props) => (
  <svg viewBox="0 0 16 16" {...base} {...props}>
    <path
      d="M8 13.2V3M8 3 3.6 7.4M8 3l4.4 4.4"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const CopyIcon = (props: Props) => (
  <svg viewBox="0 0 16 16" {...base} {...props}>
    <rect x="5" y="5" width="8.5" height="8.5" rx="2" stroke="currentColor" strokeWidth="1.4" />
    <path
      d="M11 5V4a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 4v5.5A1.5 1.5 0 0 0 4 11h1"
      stroke="currentColor"
      strokeWidth="1.4"
    />
  </svg>
);

export const CheckIcon = (props: Props) => (
  <svg viewBox="0 0 14 14" {...base} {...props}>
    <path
      d="M3 7.3 5.7 10 11 4.4"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const StopIcon = (props: Props) => (
  <svg viewBox="0 0 14 14" {...base} {...props}>
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.6" fill="currentColor" />
  </svg>
);

export const GearIcon = (props: Props) => (
  <svg viewBox="0 0 16 16" {...base} {...props}>
    <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4" />
    <path
      d="M8 1.8v1.6M8 12.6v1.6M14.2 8h-1.6M3.4 8H1.8M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1M12.4 12.4l-1.1-1.1M4.7 4.7 3.6 3.6"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
    />
  </svg>
);

export const PeopleIcon = (props: Props) => (
  <svg viewBox="0 0 14 14" {...base} {...props}>
    <circle cx="5.2" cy="4.8" r="2.1" stroke="currentColor" strokeWidth="1.3" />
    <path d="M1.6 11.6c.4-2 1.9-3.2 3.6-3.2s3.2 1.2 3.6 3.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    <path d="M9.4 3a2 2 0 0 1 0 3.8M10.4 8.6c1 .4 1.7 1.5 2 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
  </svg>
);
