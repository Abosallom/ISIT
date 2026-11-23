/**
 * ISIT in Arabic as well. The language comes from `?lang=ar|en`, else the last one chosen with the header's language
 * button (localStorage `isit.lang`). `t(english)` is the Arabic of a
 * screen string when the language is Arabic, else the English itself, so English stays the source and the key; `{name}`
 * placeholders are filled from `vars`. `tr(text)` translates a sentence the checking engine wrote (src/lib), by the
 * sentence patterns in src/i18n-ar.ts; the engine and its tests stay English. The specification's own words (field
 * names, codes, Confluence quotes) are never translated.
 */
import { AR, PATTERNS, WORDS } from "./i18n-ar";

export type Lang = "en" | "ar";
let lang: Lang = "en";
export function setLang(l: string | null | undefined) { lang = l === "ar" ? "ar" : "en"; }
export function getLang(): Lang { return lang; }
export const isArabic = () => lang === "ar";

export function t(en: string, vars?: Record<string, string | number>): string {
  let s = lang === "ar" ? AR[en] ?? en : en;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

/** An engine sentence in the person's language: the first pattern that matches it, its parts put in place (and the
 *  parts that are plain English words translated too); unchanged when none matches or the language is English. */
export function tr(text: string | null | undefined): string {
  if (!text || lang !== "ar") return text ?? "";
  for (const [re, ar] of PATTERNS) {
    const m = re.exec(text);
    if (m) return ar.replace(/\$(\d)/g, (_, i) => { const part = m[Number(i)] ?? ""; return WORDS[part] ?? part; });
  }
  return AR[text] ?? text;
}
