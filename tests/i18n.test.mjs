// ISIT in Arabic: every screen string the views route through t()
// has its Arabic, the engine's sentences come out in Arabic, and English stays exactly the English.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { withApp } from "./render.mjs";

test("every screen string has its Arabic", async () => {
  const keys = execFileSync("node", ["scripts/i18n-wrap.mjs", "--list"], { encoding: "utf8" }).split("\n").filter(Boolean);
  assert.ok(keys.length > 300, "the screens' strings are routed through t()");
  await withApp(async ({ load }) => {
    const { AR } = await load("/src/i18n-ar.ts");
    const missing = keys.filter((k) => !(k in AR));
    assert.deepEqual(missing, [], "strings with no Arabic");
  });
});

test("t() and tr(): Arabic when asked, the English untouched otherwise, values put in place", async () => {
  await withApp(async ({ load }) => {
    const { t, tr, setLang } = await load("/src/i18n.ts");
    setLang("en");
    assert.equal(t("Check"), "Check");
    assert.equal(tr("PID.3 is required but missing"), "PID.3 is required but missing");
    setLang("ar");
    assert.equal(t("Check"), "الفحص");
    assert.equal(t("{a} of {b}", { a: 3, b: 26 }), "3 من 26");
    assert.equal(tr("PID.3 is required but missing"), "PID.3 مطلوب لكنه غير موجود");
    assert.equal(tr("PV1.19 is recommended but empty"), "PV1.19 مستحسن لكنه فارغ");
    assert.equal(tr('Bundle.type must be "message"'), 'يجب أن يكون Bundle.type هو "message"');
    assert.equal(tr("12 of 14 required element(s) present"), "12 من 14 عنصرًا مطلوبًا موجودة");
    assert.equal(tr("An English sentence nobody wrote a pattern for"), "An English sentence nobody wrote a pattern for", "unknown sentences stay as they are");
    setLang("en");
  });
});
