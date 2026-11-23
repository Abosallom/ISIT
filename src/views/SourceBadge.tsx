import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { eventOrigin } from "../ui/host";
import { loadChanges, type SpecChanges } from "../lib/structure";

/**
 * Where ISIT's rules come from. A static page reads nothing live: the rules were compiled from the public NPHIES
 * Confluence space, and the later NPHIES changes read in after review (spec-build/refresh_2026_10.py) are listed in the
 * NPHIES changes tab. Pages NPHIES published but not yet read in are listed there as pending: verdicts still cite the
 * version ISIT has.
 */
const SPACE = "https://nphies.atlassian.net/wiki/spaces/NPHIES";
const day = (iso?: string | null) => (iso ? iso.slice(0, 10) : "");

export function SourceBadge({ onOpenChanges }: { onOpenChanges?: () => void }) {
  const [changes, setChanges] = useState<SpecChanges | null>(null);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    loadChanges().then((c) => { if (live) setChanges(c); }).catch(() => {});
    return () => { live = false; };
  }, []);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(eventOrigin(e) as Node)) setOpen(false); };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  if (!changes) return null;
  const pending = changes.pending.length;
  const label = t("Rules from Confluence {d}", { d: day(changes.appliedAt) });
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="rounded-xs border border-line bg-raised px-1.5 py-0.5 text-2xs text-ink-2"
      >
        {label}
      </button>
      {open && (
        <div className="absolute start-0 top-full z-50 mt-1 w-[26rem] max-w-[90vw] rounded-sm border border-line bg-surface p-3 shadow-lg">
          <p className="text-xs text-ink-2">
            {t("The rules were compiled from the")}{" "}
            <a href={SPACE} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{t("NPHIES Confluence space")}</a>{" "}
            {t("on")}{" "}{day(changes.baseline)}{t(", and the changes NPHIES published since were read in on")}{" "}{day(changes.appliedAt)}.{" "}
            {pending > 0 && t("{n} pages are not in the rules yet: verdicts still cite the version ISIT has.", { n: pending })}
          </p>
          {onOpenChanges && (
            <button
              type="button"
              onClick={() => { setOpen(false); onOpenChanges(); }}
              className="mt-1.5 text-xs text-accent hover:underline"
            >
              {t("See what changed in the rules")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
