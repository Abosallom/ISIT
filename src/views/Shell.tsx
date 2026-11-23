import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getLang, t } from "../i18n";
import { eventOrigin } from "../ui/host";
import { SourceBadge } from "./SourceBadge";
import {
  Badge,
  Button,
  DensityToggle,
  EmptyState,
  KeyDialog,
  Tabs,
  ThemeToggle,
  Tooltip,
  UseCaseRail,
  maskKey,
  useApiKey,
  useDensity,
  useTheme,
  type TabItem,
  type UseCase,
  type UseCaseRailHandle,
} from "../ui";
import { loadGoldenIndex, structureForSample, type GoldenSample } from "../lib/workbench";
import { BuildView } from "./BuildView";
import { CheckView } from "./CheckView";
import { CoverageView } from "./CoverageView";
import { ChangesView } from "./ChangesView";
import { DecoderView } from "./DecoderView";
import { ExplainView } from "./ExplainView";
import { IngestView } from "./IngestView";
import { ReadinessView, type SessionResult } from "./ReadinessView";
import { Welcome, useWelcome } from "./Welcome";
import { CONFLUENCE_BASE } from "./constants";
import { useGolden, useRegistry, useResolved } from "./useSpec";

/* ========================================================================== *
 * The shell: use-case rail, workflow tabs, and the three global surfaces.
 *
 * It owns one thing of substance — the per-use-case working state (which variant, what the
 * analyst pasted, what the last check found) — so switching tabs or use cases never discards
 * work, and the Readiness matrix can report what has actually been checked in this session.
 * ========================================================================== */

type ActiveTab = "build" | "check" | "explain" | "ingest" | "readiness" | "decoder" | "coverage" | "changes";

const GLOBAL_TABS = new Set<ActiveTab>(["readiness", "decoder", "coverage", "changes"]);

/**
 * Where "Check an official sample" lands. ADT is the message every hospital sends first and
 * the use case with official samples for every variant, so a first check there is the least
 * likely to end in "no sample for this shape".
 */
const SAMPLE_USE_CASE_ID = "adt";

interface UseCaseState {
  structureId: string | null;
  text: string;
}

export function Shell() {
  const registry = useRegistry();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<ActiveTab>("check");
  const [states, setStates] = useState<Record<string, UseCaseState>>({});
  const [results, setResults] = useState<Record<string, SessionResult>>({});

  const { theme, setTheme } = useTheme();
  /* The one useDensity instance: it stamps <html data-density>, which the CSS scale reads,
   * and its value goes down as a prop only to the views whose virtualised row heights are
   * JavaScript constants — those are the sole places a token cannot reach. */
  const { density, setDensity } = useDensity();
  const [keyOpen, setKeyOpen] = useState(false);
  const { key, setKey } = useApiKey();
  const welcome = useWelcome();
  const railRef = useRef<UseCaseRailHandle>(null);

  const useCases: UseCase[] = useMemo(
    () => (registry.data?.entries ?? []).map((e) => e.ui as UseCase),
    [registry.data],
  );

  useEffect(() => {
    if (!selectedId && useCases.length) setSelectedId(useCases[0].id);
  }, [useCases, selectedId]);

  const state = selectedId ? (states[selectedId] ?? { structureId: null, text: "" }) : { structureId: null, text: "" };
  const resolved = useResolved(selectedId, state.structureId);
  const golden = useGolden(selectedId);

  const entry = selectedId ? (registry.data?.byId.get(selectedId) ?? null) : null;
  const structures = resolved.data?.structures ?? [];
  const structure = resolved.data?.structure ?? null;

  const patch = useCallback(
    (id: string, next: Partial<UseCaseState>) => {
      setStates((prev) => ({ ...prev, [id]: { ...(prev[id] ?? { structureId: null, text: "" }), ...next } }));
    },
    [],
  );

  const { dismiss: dismissWelcome, open: welcomeOpen } = welcome;

  const onSelectUseCase = useCallback(
    (uc: UseCase) => {
      setSelectedId(uc.id);
      setTab((t) => (GLOBAL_TABS.has(t) ? "check" : t));
      // Picking a use case is already the choice the welcome asks for.
      if (welcomeOpen) dismissWelcome();
    },
    [welcomeOpen, dismissWelcome],
  );

  /**
   * Check's "this looks like a different use case" action. The paste is carried across so
   * the person is never asked to find it again; the target's own variant choice survives
   * unless Check named one. It only ever fires from an explicit click — the shell never
   * re-homes a message on its own, because a wrong guess here would silently judge the
   * message against the wrong rules.
   */
  const onSwitchUseCase = useCallback(
    (useCaseId: string, structureId: string | null) => {
      setStates((prev) => {
        const text = selectedId ? (prev[selectedId]?.text ?? "") : "";
        const current = prev[useCaseId] ?? { structureId: null, text: "" };
        return { ...prev, [useCaseId]: { structureId: structureId ?? current.structureId, text } };
      });
      setSelectedId(useCaseId);
      setTab("check");
    },
    [selectedId],
  );

  const onWelcomeSample = useCallback(() => {
    const target = useCases.find((u) => u.id === SAMPLE_USE_CASE_ID) ?? useCases[0];
    if (target) setSelectedId(target.id);
    setTab("check");
    dismissWelcome();
  }, [useCases, dismissWelcome]);

  const onWelcomeStart = useCallback(() => {
    setTab("check");
    dismissWelcome();
  }, [dismissWelcome]);

  const onStructureChange = useCallback(
    (structureId: string) => {
      if (selectedId) patch(selectedId, { structureId });
    },
    [selectedId, patch],
  );

  const onTextChange = useCallback(
    (text: string) => {
      if (selectedId) patch(selectedId, { text });
    },
    [selectedId, patch],
  );

  /** Build hands a sample to Check, which is where a reference message is useful. */
  const openSample = useCallback(
    async (sample: GoldenSample) => {
      if (!selectedId) return;
      const index = await loadGoldenIndex();
      void index;
      const target = structureForSample(structures, sample);
      const res = await fetch(sample.url);
      if (!res.ok) return;
      const body = await res.text();
      patch(selectedId, { text: body, ...(target ? { structureId: target.id } : {}) });
      setTab("check");
    },
    [selectedId, structures, patch],
  );

  /**
   * Ingest's hand-off. The generated text lands in the CURRENT use case's paste box and Check
   * opens on it — the same state a manual paste would set, so the checker judges it exactly as
   * it would judge anything else. Nothing about the generator's own report travels with it.
   */
  const onOpenInCheck = useCallback(
    (text: string) => {
      if (!selectedId) return;
      patch(selectedId, { text });
      setTab("check");
    },
    [selectedId, patch],
  );

  const recordResult = useCallback((useCaseId: string, result: SessionResult) => {
    setResults((prev) => (prev[useCaseId]?.at === result.at ? prev : { ...prev, [useCaseId]: result }));
  }, []);

  /* "/" focuses the rail filter from anywhere outside a text field. */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = eventOrigin(e) as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      e.preventDefault();
      railRef.current?.focusFilter();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const result = selectedId ? results[selectedId] : undefined;
  const openChanges = () => {
    setTab("changes");
    if (welcomeOpen) dismissWelcome();
  };

  const tabs: TabItem[] = [
    { id: "build", label: t("Build"), title: t("What this message type requires — and what NPHIES ignores") },
    {
      id: "check",
      label: t("Check"),
      title: t("Validate a message against the compiled structural rules"),
      badge:
        result && result.errors + result.warns > 0 ? (
          <span className="font-mono text-2xs">
            {result.errors ? `${result.errors}E` : ""}
            {result.errors && result.warns ? " " : ""}
            {result.warns ? `${result.warns}W` : ""}
          </span>
        ) : undefined,
    },
    { id: "explain", label: t("Explain"), title: t("Walk the compiled rules for this message type") },
    { id: "ingest", label: t("Ingest"), title: t("Map a HIS spreadsheet onto this message type and generate a message from one row") },
    { id: "readiness", label: t("Readiness"), startsGroup: true, title: t("Global: which use cases have been checked") },
    { id: "decoder", label: t("Error Decoder"), title: t("Global: decode an NPHIES rejection") },
    { id: "coverage", label: t("Coverage"), title: t("Global: what the workbench does not know") },
    { id: "changes", label: t("NPHIES changes"), title: t("Global: what NPHIES changed in the rules, and what is not in them yet") },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas text-ink">
      <header className="flex h-9 shrink-0 items-center gap-2 border-b border-line bg-surface px-2.5">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-flex h-4 w-4 items-center justify-center rounded-xs bg-accent font-mono text-2xs font-bold text-accent-ink"
          >
            N
          </span>
          <span className="text-xs font-semibold tracking-tight">{t("ISIT")}</span>
        </span>
        <Badge mono className="shrink-0">
          {t("NPHIES message structure")}
        </Badge>
        <span className="hidden text-2xs text-ink-3 sm:inline">
          {t("Nothing you paste leaves this browser.")}
        </span>
        <SourceBadge onOpenChanges={openChanges} />

        <div className="ms-auto flex items-center gap-1.5">
          <Tooltip
            wide
            content={
              key
                ? `${t("Anthropic key stored in this browser")} (${maskKey(key)}). ${t("Used only when you ask for an explanation.")}`
                : t("No Anthropic key stored. Every structural check works without one.")
            }
          >
            <Button variant="ai" onClick={() => setKeyOpen(true)}>{key ? t("API key set") : t("Set API key")}</Button>
          </Tooltip>
          <Button
            onClick={() => {
              const next = getLang() === "ar" ? "en" : "ar";
              try { localStorage.setItem("isit.lang", next); } catch { /* storage blocked */ }
              const u = new URL(location.href);
              u.searchParams.set("lang", next);
              location.href = u.toString();
            }}
            lang={getLang() === "ar" ? "en" : "ar"}
          >
            {getLang() === "ar" ? "English" : "عربي"}
          </Button>
          <Tooltip content={t("About ISIT — what it is for and what it promises.")}>
            <Button aria-label={t("About ISIT")} onClick={welcome.reopen} className="font-mono">
              ?
            </Button>
          </Tooltip>
          <DensityToggle density={density} onChange={setDensity} />
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <UseCaseRail ref={railRef} useCases={useCases} selectedId={selectedId} onSelect={onSelectUseCase} />

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-9 shrink-0 items-center gap-3 border-b border-line bg-surface px-2.5">
            <span className="flex min-w-0 shrink items-center gap-1.5">
              {entry ? (
                <>
                  <code className="shrink-0 font-mono text-xs text-ink">{entry.ui.code}</code>
                  <span className="truncate text-xs text-ink-2">{entry.ui.label}</span>
                </>
              ) : (
                <span className="text-xs text-ink-3">
                  {registry.loading ? t("Loading the compiled spec…") : t("No use case selected")}
                </span>
              )}
            </span>
            <Tabs
              aria-label={t("Workflow")}
              items={tabs}
              activeId={tab}
              onChange={(id) => {
                setTab(id as ActiveTab);
                // Choosing a tab is choosing to work; the welcome has done its job.
                if (welcomeOpen) dismissWelcome();
              }}
              className="ms-auto"
            />
          </div>

          <div className="min-h-0 flex-1">
            {registry.error ? (
              /* A broken bundle outranks the welcome: nothing may stand in front of that. */
              <EmptyState
                fill
                title={t("The compiled spec bundle could not be loaded")}
                description={registry.error}
              />
            ) : welcomeOpen ? (
              <Welcome
                firstRun={!welcome.welcomed}
                onCheckSample={onWelcomeSample}
                onStart={onWelcomeStart}
                onDismiss={dismissWelcome}
              />
            ) : tab === "readiness" ? (
              <ReadinessView
                registry={registry.data}
                results={results}
                onOpen={(id) => {
                  setSelectedId(id);
                  setTab("check");
                }}
              />
            ) : tab === "decoder" ? (
              <DecoderView baseUrl={CONFLUENCE_BASE} />
            ) : tab === "changes" ? (
              <ChangesView baseUrl={CONFLUENCE_BASE} />
            ) : tab === "coverage" ? (
              <CoverageView registry={registry.data} baseUrl={CONFLUENCE_BASE} density={density} />
            ) : tab === "build" ? (
              <BuildView
                structure={structure}
                structures={structures}
                resolved={resolved.data?.resolved ?? null}
                samples={golden.data ?? []}
                onStructureChange={onStructureChange}
                onOpenSample={openSample}
                baseUrl={CONFLUENCE_BASE}
                density={density}
              />
            ) : tab === "explain" ? (
              <ExplainView
                structure={structure}
                structures={structures}
                resolved={resolved.data?.resolved ?? null}
                onStructureChange={onStructureChange}
                baseUrl={CONFLUENCE_BASE}
                density={density}
              />
            ) : tab === "ingest" ? (
              <IngestView
                key={selectedId ?? "none"}
                structure={structure}
                structures={structures}
                resolved={resolved.data?.resolved ?? null}
                samples={golden.data ?? []}
                density={density}
                onOpenInCheck={onOpenInCheck}
                onStructureChange={onStructureChange}
              />
            ) : (
              <CheckView
                key={selectedId ?? "none"}
                structure={structure}
                structures={structures}
                resolved={resolved.data?.resolved ?? null}
                samples={golden.data ?? []}
                text={state.text}
                onTextChange={onTextChange}
                onStructureChange={onStructureChange}
                onSwitchUseCase={onSwitchUseCase}
                structureIdForSample={(sample) => structureForSample(structures, sample)?.id ?? null}
                onResult={(r) => selectedId && recordResult(selectedId, r)}
                baseUrl={CONFLUENCE_BASE}
                useCaseCode={entry?.ui.code}
                density={density}
              />
            )}
          </div>
        </main>
      </div>

      <footer className="flex h-6 shrink-0 items-center gap-3 border-t border-line bg-surface px-2.5 text-2xs text-ink-3">
        <span className="font-mono">{structure ? structure.id : (selectedId ?? "—")}</span>
        {registry.data ? (
          <span>
            {registry.data.entries.length}{" "}{t("use cases ·")}{" "}
            {Number(registry.data.manifest.counts.specNodes ?? 0).toLocaleString()}{" "}{t("compiled rules ·")}{" "}
            {Number(registry.data.manifest.counts.goldenSamples ?? 0)}{" "}{t("official samples")}
          </span>
        ) : null}
        <span className="ms-auto">
          {t("Press")}{" "}<kbd className="rounded-xs border border-line px-1 font-mono">/</kbd>{" "}{t("to filter use cases")}
        </span>
      </footer>

      <KeyDialog open={keyOpen} onClose={() => setKeyOpen(false)} value={key} onSave={setKey} />
    </div>
  );
}
