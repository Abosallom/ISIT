/**
 * The 2026-10 refresh: NPHIES's changes of 20 Sep and 13 Oct 2026, carried into the rules (spec-build/extract_fields.py,
 * refresh_2026_10.py, changes.py). What would be a silent defect if it broke:
 *
 *  1. No compiled rule cites a page NPHIES deleted. PID, PV1, DG1 and PR1 moved to new page ids; a value-set link or a
 *     component table still keyed to an old id would quietly stop applying (twelve value-set links did, before the
 *     refresh re-derived them).
 *  2. Every value-set link the refresh made reaches the compiled rule it names, and every set it names ships.
 *  3. A field that cites several value sets takes a code from ANY of them (ZPV1.49 names twelve); a code in none is
 *     reported once, not once per set.
 *  4. The "What NPHIES changed" list ships with the bundle and agrees with the rules it describes.
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { loadEngine, readGolden, ROOT, SPEC_DIR } from "./harness.mjs";

const { workbench, structure: S, check: C } = await loadEngine();
const OLD_ADT_PAGES = ["7766393", "7766425", "7766496", "7766519"];
const readSpec = (rel) => JSON.parse(fs.readFileSync(path.join(SPEC_DIR, rel), "utf8"));

function* nodesOf(bundle) {
  for (const page of Object.values(bundle.pages)) {
    for (const table of page.tables) {
      const stack = [...table.nodes];
      while (stack.length) {
        const n = stack.pop();
        yield { page, node: n };
        stack.push(...(n.children ?? []));
      }
    }
  }
}

test("no compiled HL7 rule or value-set link cites an ADT page NPHIES replaced", () => {
  const hl7 = readSpec("fields/hl7v2.json");
  for (const id of OLD_ADT_PAGES) assert.ok(!(id in hl7.pages), `page ${id} is still compiled`);
  const stale = [];
  for (const { node } of nodesOf(hl7)) {
    if (OLD_ADT_PAGES.includes(String(node.provenance?.pageId))) stale.push(node.id);
    for (const v of node.valueSets) if (OLD_ADT_PAGES.includes(String(v.provenance?.pageId))) stale.push(`${node.id} → ${v.valueSetId}`);
  }
  assert.deepEqual(stale, []);
});

test("every value-set link the refresh made reaches its rule, and every set it names ships", () => {
  const vs = JSON.parse(fs.readFileSync(path.join(ROOT, "spec-build", "valuesets.json"), "utf8"));
  const hl7 = readSpec("fields/hl7v2.json");
  const index = readSpec("valuesets/index.json");
  const byKey = new Map();
  for (const { page, node } of nodesOf(hl7)) byKey.set(`${page.pageId}::${node.locatorRaw}`, node);
  const missing = [];
  for (const b of vs.bindings.filter((x) => x.refresh === "2026-10")) {
    const node = byKey.get(`${b.pageId}::${b.fieldKey.split(" / ")[0]}`);
    if (!node) missing.push(`no rule for ${b.pageId} ${b.fieldKey}`);
    else if (b.valueSetId && !node.valueSets.some((v) => v.valueSetId === b.valueSetId)) missing.push(`${b.fieldKey} lost ${b.valueSetId}`);
    if (b.valueSetId && !index.valueSets[b.valueSetId]) missing.push(`value set ${b.valueSetId} not shipped`);
  }
  assert.deepEqual(missing, []);
  // the new subdomain field names all twelve outpatient sets
  const zpv149 = byKey.get("873300011::ZPV1.49");
  assert.equal(zpv149.valueSets.length, 12);
});

test("a field citing several value sets takes a code from any of them, and reports a code in none once", async () => {
  const useCaseId = "adt";
  const structures = await workbench.structuresFor(useCaseId);
  const golden = (await workbench.loadGoldenIndex()).get(useCaseId);
  const sample = golden.find((s) => s.fileName === "ADT_sample03.txt");
  const structure = workbench.structureForSample(structures, sample);
  const resolved = await workbench.resolve(useCaseId, structure.variant ?? structure.id);
  const base = await workbench.checkOptionsFor(structure, resolved);

  // PV1.2 is bound to CS-Adm-PatientClass; cite CS-Adm-Gender beside it, as a field citing two sets would.
  const gender = await S.loadValueSet("cs-adm-gender");
  const patientClass = await S.loadValueSet("cs-adm-patientclass");
  assert.ok(gender?.concepts.length && patientClass?.concepts.length);
  const tables = new Map();
  for (const [ref, table] of base.tables) {
    tables.set(ref, {
      ...table,
      nodes: table.nodes.map((n) =>
        n.locator?.kind === "hl7Field" && n.locator.segment === "PV1" && n.locator.field === 2 && n.valueSets.length
          ? { ...n, valueSets: [...n.valueSets, { ...n.valueSets[0], valueSetId: "cs-adm-gender", title: gender.title, referenceText: "CS-Adm-Gender" }] }
          : n,
      ),
    });
  }
  const valueSets = new Map(base.valueSets);
  valueSets.set("cs-adm-gender", gender);
  const opts = { ...base, tables, valueSets };

  const run = async (text) => {
    const parse = await workbench.parseMessage(text, structure, resolved);
    return C.check(parse.tree, structure, opts).filter((f) => f.code === "valueset-code-unknown" && /PV1/.test(f.path ?? ""));
  };
  const text = readGolden(sample.path);
  const pv1 = text.split(/\r\n|\r|\n/).find((l) => l.startsWith("PV1|"));
  const klass = pv1.split("|")[2];
  assert.ok(patientClass.concepts.some((c) => c.code === klass), `the sample's patient class ${klass} is a CS-Adm-PatientClass code`);
  assert.ok(!gender.concepts.some((c) => c.code === klass));
  assert.deepEqual(await run(text), [], "a code in one of the two sets is valid");

  const bad = text.replace(pv1, pv1.replace(`PV1|${pv1.split("|")[1]}|${klass}|`, `PV1|${pv1.split("|")[1]}|QQ|`));
  const found = await run(bad);
  assert.equal(found.length, 1, "one finding, not one per set");
  assert.match(found[0].title, /is not in any of the 2 value sets this field cites/);
});

test("the change list ships with the bundle and agrees with the rules it describes", async () => {
  const changes = await S.loadChanges();
  assert.ok(changes, "src/spec/changes.json is listed in the manifest");
  assert.equal(changes.refresh, "2026-10");
  const pid = changes.pages.find((p) => p.title === "PID");
  assert.equal(pid.replaces, "7766393");
  const pid8 = pid.rows.find((r) => r.field === "PID.8");
  assert.equal(pid8.kind, "rule");
  assert.match(pid8.before.usage, /^I /);
  assert.match(pid8.after.usage, /^R2 /);
  assert.deepEqual(pid8.after.valueSets, ["CS-Adm-Gender"]);
  assert.match(pid8.summaryStill, /^I /, "the summary page still says I, so the milder reading applies");
  const hl7 = readSpec("fields/hl7v2.json");
  const compiled = [...nodesOf(hl7)].find(({ page, node }) => page.pageId === "873496585" && node.locatorRaw === "PID.8").node;
  assert.equal(compiled.usage[0].usage, "R2");
  // what is not in the rules yet is listed, with why
  assert.ok(changes.pending.length >= 10);
  assert.ok(changes.pending.every((p) => p.why && p.whyAr));
  assert.ok(changes.pending.some((p) => p.title === "Error Handling Guide"));
});
