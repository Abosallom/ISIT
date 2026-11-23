import { useMemo, useState } from "react";
import { isArabic, t } from "../i18n";
import { Badge, EmptyState, Tabs, Toolbar, ToolbarTitle, Tooltip } from "../ui";
import { loadChanges, type SpecChangeSide, type SpecChanges } from "../lib/structure";
import { useAsyncValue } from "./useAsyncValue";

/* ========================================================================== *
 * NPHIES changes — what the last refresh of the published specification changed in ISIT's rules.
 *
 * For the person who reviews a refresh before it is published: the changed Confluence pages go into the rules only
 * through a visible list. Every row says what NPHIES's page said before (the 2026-09-15 copy) and
 * what it says now, with the words it rests on; value sets added and changed; what is shown but never judged; and the
 * changed pages NOT in the rules yet, each with why. Nothing here is a verdict: it is a list of what the verdicts now
 * rest on. Built by spec-build/changes.py.
 * ========================================================================== */

type Pane = "rules" | "valuesets" | "notjudged" | "pending";
type Page = SpecChanges["pages"][number];
type Row = Page["rows"][number];

export interface ChangesViewProps {
  baseUrl: string;
}

const day = (iso?: string | null) => (iso ? iso.slice(0, 10) : "");
const href = (base: string, id: string) =>
  base.includes("{pageId}") ? base.replace("{pageId}", encodeURIComponent(id)) : `${base.replace(/\/$/, "")}/${id}`;
const pick = (en: string, ar?: string) => (isArabic() && ar ? ar : en);

/** Which parts of a row changed, in the reviewer's words. */
const WHAT: Record<string, string> = {
  usage: "usage",
  length: "length",
  dataType: "data type",
  codeSet: "code set",
  elementLocation: "location",
  role: "role",
  fixedValue: "fixed value",
  valueSets: "value set",
  guidance: "wording",
  name: "name",
};

export function ChangesView({ baseUrl }: ChangesViewProps) {
  const changes = useAsyncValue(loadChanges);
  const [pane, setPane] = useState<Pane>("rules");
  const [wording, setWording] = useState(false);
  const data = changes.data;

  const pages = useMemo(() => {
    if (!data) return [];
    return data.pages
      .map((p) => ({ ...p, rows: p.rows.filter((r) => wording || r.kind === "rule") }))
      .filter((p) => p.rows.length > 0);
  }, [data, wording]);

  if (changes.loading) return <EmptyState fill title={t("Loading…")} />;
  if (!data)
    return (
      <EmptyState
        fill
        title={t("No changes recorded")}
        description={t("These rules were compiled straight from the published pages; no refresh has been applied since.")}
      />
    );
  const c = data.counts;

  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas">
      <Toolbar
        dense
        aria-label={t("NPHIES changes")}
        end={
          <Tabs
            aria-label={t("Changes pane")}
            activeId={pane}
            onChange={(id) => setPane(id as Pane)}
            items={[
              { id: "rules", label: t("Rules ({n})", { n: c.ruleChanges + c.rowsAdded + c.rowsRemoved }) },
              { id: "valuesets", label: t("Value sets ({n})", { n: c.valueSetsAdded + c.valueSetsChanged }) },
              { id: "notjudged", label: t("Shown, not judged ({n})", { n: data.notJudged.length }) },
              { id: "pending", label: t("Not in the rules yet ({n})", { n: c.pending }) },
            ]}
          />
        }
      >
        <ToolbarTitle>{t("NPHIES changes")}</ToolbarTitle>
        <Badge mono>{t("{n} pages", { n: c.pages })}</Badge>
        <Badge mono>{t("since {d}", { d: day(data.baseline) })}</Badge>
      </Toolbar>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {pane === "rules" ? (
          <section className="space-y-3">
            <Intro>
              {t("What NPHIES changed on its pages on 20 Sep and 13 Oct 2026, now in ISIT's rules. Each row shows the page as it was on")}{" "}
              {day(data.baseline)}{" "}{t("and as it is now, with the words it rests on. Rows whose only change is wording are hidden unless you ask for them.")}
            </Intro>
            <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              <Stat label={t("Rule changes")} value={c.ruleChanges} />
              <Stat label={t("New rows (new fields)")} value={c.rowsAdded} />
              <Stat label={t("Wording only")} value={c.wordingChanges} />
              <Stat label={t("Value-set links added / removed")} value={`${c.linksAdded} / ${c.linksRemoved}`} />
            </div>
            {data.checker.map((k) => (
              <Card key={k.change} title={t("How ISIT checks changed")}>
                <p className="font-medium text-ink">{pick(k.change, k.changeAr)}</p>
                <p className="mt-0.5 text-ink-2">{pick(k.why, k.whyAr)}</p>
              </Card>
            ))}
            <label className="flex w-fit cursor-pointer items-center gap-1.5 text-xs text-ink-2">
              <input type="checkbox" checked={wording} onChange={(e) => setWording(e.target.checked)} />
              {t("Show wording-only changes too")}
            </label>
            {pages.map((p) => (
              <PageCard key={p.pageId} page={p} baseUrl={baseUrl} summary={data.summaryPage} />
            ))}
          </section>
        ) : pane === "valuesets" ? (
          <section className="space-y-3">
            <Intro>
              {t("Value sets are the code lists a field's value must come from. A changed list changes which codes ISIT accepts.")}
            </Intro>
            {data.valueSets.changed.length > 0 && (
              <Card title={t("Changed ({n})", { n: data.valueSets.changed.length })}>
                <ul className="space-y-2">
                  {data.valueSets.changed.map((v) => (
                    <li key={v.id}>
                      <p className="text-ink">
                        <a href={href(baseUrl, v.pageId)} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">
                          {String(v.after.title)}
                        </a>
                        {v.before.title !== v.after.title && (
                          <span className="text-ink-3">{" "}{t("(was")}{" "}{String(v.before.title)}{")"}</span>
                        )}
                      </p>
                      <p className="mt-0.5 font-mono text-2xs text-ink-2">
                        {t("{a} codes → {b} codes", { a: Number(v.before.conceptCount ?? 0), b: Number(v.after.conceptCount ?? 0) })}
                        {v.before.sampleCodes?.length ? <> · {t("before")} {v.before.sampleCodes.join(", ")}…</> : null}
                        {v.after.sampleCodes?.length ? <> · {t("now")} {v.after.sampleCodes.join(", ")}…</> : null}
                      </p>
                      {v.note && <p className="mt-0.5 text-2xs text-ink-3">{v.note}</p>}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            <Card title={t("Added ({n})", { n: data.valueSets.added.length })}>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line text-start text-2xs text-ink-3">
                    <th className="py-1 text-start font-medium">{t("Value set")}</th>
                    <th className="py-1 text-end font-medium">{t("Codes")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.valueSets.added.map((v) => (
                    <tr key={v.id} className="border-b border-line/60">
                      <td className="py-1">
                        <a href={href(baseUrl, v.pageId)} target="_blank" rel="noopener noreferrer" className="hover:underline">{v.title}</a>
                        {v.pageLocal && <span className="text-2xs text-ink-3">{" "}{t("· listed on the field's own page")}</span>}
                      </td>
                      <td className="py-1 text-end font-mono tabular-nums text-ink-2">{v.concepts || t("none published")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            {data.valueSets.empty.length > 0 && (
              <Intro>
                {t("Published with no codes, so codes from it cannot be checked:")}{" "}
                {data.valueSets.empty.map((v) => v.title).join(", ")}.
              </Intro>
            )}
          </section>
        ) : pane === "notjudged" ? (
          <section className="space-y-3">
            <Intro>
              {t("Rules ISIT shows in Explain but never turns into a verdict, because the condition is a sentence it cannot test, or the page leaves the choice open.")}
            </Intro>
            <ul className="space-y-2">
              {data.notJudged.map((n, i) => (
                <li key={i} className="rounded-sm border border-line bg-surface p-2.5 text-xs">
                  <p className="font-mono text-ink">{n.fieldKey}</p>
                  <p className="mt-0.5 text-ink-2">{pick(n.why, n.whyAr)}</p>
                  {n.quote && <p className="mt-1 border-s-2 border-line ps-2 text-2xs text-ink-3">{n.quote}</p>}
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <section className="space-y-3">
            <Intro>
              {t("Pages NPHIES changed that are not in ISIT's rules yet. Until they are, the verdicts rest on the earlier version of each, and say so.")}
            </Intro>
            <ul className="space-y-1.5">
              {data.pending.map((p) => (
                <li key={p.pageId} className="rounded-sm border border-line bg-surface px-2.5 py-2 text-xs">
                  <p className="flex flex-wrap items-baseline justify-between gap-2">
                    <a href={href(baseUrl, p.pageId)} target="_blank" rel="noopener noreferrer" className="font-medium text-ink hover:underline">{p.title}</a>
                    <span className="font-mono text-2xs text-ink-3">{day(p.updatedAt)}</span>
                  </p>
                  <p className="mt-0.5 text-ink-2">{pick(p.why, p.whyAr)}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

function PageCard({ page, baseUrl, summary }: { page: Page; baseUrl: string; summary: SpecChanges["summaryPage"] }) {
  const added = page.rows.filter((r) => r.change === "added");
  const rest = page.rows.filter((r) => r.change !== "added");
  return (
    <article className="rounded-sm border border-line bg-surface text-xs">
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-line px-2.5 py-1.5">
        {page.area && <span className="text-2xs uppercase tracking-wide text-ink-3">{page.area}</span>}
        <a href={href(baseUrl, page.pageId)} target="_blank" rel="noopener noreferrer" className="font-semibold text-ink hover:underline">
          {page.title}
        </a>
        <span className="font-mono text-2xs text-ink-3">{day(page.updatedAt)}</span>
        {page.status === "new" && <Badge>{t("new page")}</Badge>}
        {page.replaces && (
          <span className="text-2xs text-ink-3">{t("replaces page {id}", { id: page.replaces })}</span>
        )}
      </header>
      {page.note && <p className="border-b border-line px-2.5 py-1.5 text-2xs text-ink-2">{pick(page.note, page.noteAr)}</p>}
      {rest.length > 0 && (
        <table className="w-full">
          <thead>
            <tr className="border-b border-line text-2xs text-ink-3">
              <th className="px-2.5 py-1 text-start font-medium">{t("Field")}</th>
              <th className="px-2.5 py-1 text-start font-medium">{t("What changed")}</th>
              <th className="px-2.5 py-1 text-start font-medium">{t("Before")}</th>
              <th className="px-2.5 py-1 text-start font-medium">{t("Now")}</th>
            </tr>
          </thead>
          <tbody>
            {rest.map((r, i) => (
              <ChangedRow key={i} row={r} summary={summary} />
            ))}
          </tbody>
        </table>
      )}
      {added.length > 0 && (
        <div className="px-2.5 py-1.5">
          <p className="mb-1 text-2xs font-semibold uppercase tracking-wide text-ink-3">
            {t("New rows ({n})", { n: added.length })}
          </p>
          <ul className="grid gap-x-4 gap-y-0.5 sm:grid-cols-2">
            {added.map((r, i) => (
              <li key={i} className="flex items-baseline gap-1.5">
                <span className="shrink-0 font-mono text-ink">{r.field ?? r.num}</span>
                <span className="min-w-0 truncate text-ink-2" title={r.name ?? ""}>{r.name}</span>
                <span className="ms-auto shrink-0 font-mono text-2xs text-ink-3">{r.after?.usage}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function ChangedRow({ row, summary }: { row: Row; summary: SpecChanges["summaryPage"] }) {
  const [open, setOpen] = useState(false);
  const wordingText = row.guidanceBefore !== null || row.guidanceAfter !== null;
  return (
    <>
      <tr className="border-b border-line/60 align-top">
        <td className="px-2.5 py-1">
          <span className="font-mono text-ink">{row.field ?? row.num}</span>
          {row.name && <span className="block text-2xs text-ink-2">{row.name}</span>}
        </td>
        <td className="px-2.5 py-1">
          <span className="flex flex-wrap gap-1">
            {row.change === "removed" ? <Badge>{t("removed")}</Badge> : null}
            {row.what.map((w) => (
              <Badge key={w}>{t(WHAT[w] ?? w)}</Badge>
            ))}
          </span>
          {wordingText && (
            <button type="button" onClick={() => setOpen(!open)} className="mt-0.5 text-2xs text-accent hover:underline">
              {open ? t("Hide the wording") : t("Show the wording")}
            </button>
          )}
        </td>
        <td className="px-2.5 py-1"><Side side={row.before} /></td>
        <td className="px-2.5 py-1">
          <Side side={row.after} />
          {row.summaryStill && (
            <Tooltip wide content={pick(summary.note, summary.noteAr)}>
              <span className="mt-0.5 block cursor-help text-2xs text-ink-3">
                {t("{page} still says {u}; the milder of the two applies", { page: summary.title, u: row.summaryStill })}
              </span>
            </Tooltip>
          )}
        </td>
      </tr>
      {open && (
        <tr className="border-b border-line/60">
          <td />
          <td colSpan={3} className="px-2.5 pb-2">
            <div className="grid gap-2 md:grid-cols-2">
              <Wording label={t("Before")} text={row.guidanceBefore} />
              <Wording label={t("Now")} text={row.guidanceAfter} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Side({ side }: { side: SpecChangeSide | null }) {
  if (!side) return <span className="text-ink-3">—</span>;
  return (
    <span className="block font-mono text-2xs leading-relaxed text-ink">
      {side.usage && <span className="block">{side.usage}</span>}
      {side.length && <span className="block text-ink-2">{t("length")} {side.length}</span>}
      {side.location && <span className="block break-all text-ink-2">{side.location}</span>}
      {side.valueSets && side.valueSets.length > 0 && (
        <span className="block text-ink-2" title={side.valueSets.join(", ")}>
          {side.valueSets.length > 3 ? t("{n} value sets", { n: side.valueSets.length }) : side.valueSets.join(", ")}
        </span>
      )}
    </span>
  );
}

function Wording({ label, text }: { label: string; text: string | null }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-ink-3">{label}</p>
      <p className="mt-0.5 whitespace-pre-line text-2xs leading-relaxed text-ink-2" dir="ltr">{text ?? "—"}</p>
    </div>
  );
}

function Intro({ children }: { children: React.ReactNode }) {
  return (
    <p className="max-w-prose rounded-sm border border-line bg-surface p-2.5 text-xs leading-relaxed text-ink-2">{children}</p>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-sm border border-line bg-surface px-2.5 py-2">
      <div className="font-mono text-xl tabular-nums text-ink">{value}</div>
      <div className="mt-0.5 text-2xs text-ink-3">{label}</div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-sm border border-line bg-surface p-2.5 text-xs">
      <h3 className="mb-1.5 font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}
