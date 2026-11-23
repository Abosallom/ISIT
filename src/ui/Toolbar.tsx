import type { ReactNode } from "react";
import { cx } from "./cx";

export interface ToolbarProps {
  /** Left cluster — usually a title and identity chips. */
  children?: ReactNode;
  /** Right cluster — usually actions. */
  end?: ReactNode;
  /** Renders as a section header inside a pane rather than a page bar. */
  dense?: boolean;
  /** Sticks to the top of its scroll container. */
  sticky?: boolean;
  className?: string;
  "aria-label"?: string;
}

/**
 * One-line horizontal bar. No shadow, single hairline, tight rhythm.
 */
export function Toolbar({
  children,
  end,
  dense,
  sticky,
  className,
  "aria-label": ariaLabel,
}: ToolbarProps) {
  return (
    <div
      role="toolbar"
      aria-label={ariaLabel}
      aria-orientation="horizontal"
      className={cx(
        // Wraps instead of overlapping when the space is narrow (a narrow window, a phone).
        "flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1 border-b border-line bg-surface px-2 py-0.5",
        dense ? "min-h-7" : "min-h-9 px-3",
        sticky && "sticky top-0 z-20",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{children}</div>
      {end ? <div className="ms-auto flex shrink-0 flex-wrap items-center gap-1.5">{end}</div> : null}
    </div>
  );
}

export function ToolbarTitle({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "truncate text-xs font-semibold uppercase tracking-wider text-ink-3",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ToolbarDivider() {
  return <span aria-hidden="true" className="mx-0.5 h-4 w-px bg-line" />;
}
