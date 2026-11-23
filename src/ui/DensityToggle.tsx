import { cx } from "./cx";
import { t } from "../i18n";
import type { DensityChoice } from "./useDensity";

const OPTIONS: Array<{ id: DensityChoice; label: string; glyph: string }> = [
  { id: "dense", get label() { return t("Dense layout"); }, glyph: "▤" },
  { id: "roomy", get label() { return t("Presentation layout"); }, glyph: "▣" },
];

export interface DensityToggleProps {
  density: DensityChoice;
  onChange: (d: DensityChoice) => void;
  className?: string;
}

/** Two-way segmented control: dense / presentation. */
export function DensityToggle({
  density,
  onChange,
  className,
}: DensityToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label={t("Layout density")}
      className={cx(
        "inline-flex items-center rounded-sm border border-line bg-surface p-px",
        className,
      )}
    >
      {OPTIONS.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={density === o.id}
          aria-label={o.label}
          title={o.label}
          onClick={() => onChange(o.id)}
          className={cx(
            "inline-flex h-5 w-6 items-center justify-center rounded-xs text-xs transition-colors",
            density === o.id
              ? "bg-accent-soft text-accent"
              : "text-ink-3 hover:text-ink",
          )}
        >
          <span aria-hidden="true">{o.glyph}</span>
        </button>
      ))}
    </div>
  );
}
