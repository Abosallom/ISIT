#!/usr/bin/env node
// One pass that routes the screens' English through t() (src/i18n.ts) for ISIT in Arabic: JSX text,
// the wording attributes (title, placeholder, aria-label, label, content, hint, description), and label/title/hint/
// description values in object literals. Found with TypeScript's own parser, never by pattern. Run again after adding
// screens: it skips what is already wrapped. `node scripts/i18n-wrap.mjs --list` prints every key in use.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIRS = ['src/views', 'src/ui', 'src/ui/charts'];
const ATTRS = new Set(['title', 'placeholder', 'aria-label', 'label', 'content', 'hint', 'description', 'emptyLabel', 'heading', 'alt']);
const PROPS = new Set(['label', 'title', 'hint', 'description', 'heading', 'placeholder', 'empty']);
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', mdash: '—', ndash: '–', rarr: '→', larr: '←', hellip: '…', times: '×', middot: '·', rsquo: '’', lsquo: '‘', ldquo: '“', rdquo: '”' };
const decode = (s) => s.replace(/&(#\d+|[a-z]+);/gi, (m, e) => (e[0] === '#' ? String.fromCharCode(Number(e.slice(1))) : ENT[e.toLowerCase()] ?? null) ?? m);
const wordy = (s) => /[A-Za-z]{2,}/.test(s);

// Human words, not a class list, a code or a key: a capital letter then lower case, and no Tailwind-like tokens.
const prose = (n) => /^[A-Z“"(—][\s\S]*[a-z]{2}/.test(n.text) && !/(^|\s)[a-z]+-[a-z0-9]/.test(n.text) && n.text.length < 400;
// The literal is a branch of a condition (or an ?? / || default) that sits in a JSX expression or attribute, and is not
// compared, passed to another function, or used as a key.
function insideJsx(n) {
  const p = n.parent;
  const branch = (ts.isConditionalExpression(p) && (p.whenTrue === n || p.whenFalse === n)) ||
    (ts.isBinaryExpression(p) && p.right === n && [ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(p.operatorToken.kind)) ||
    ts.isJsxExpression(p);
  if (!branch) return false;
  for (let a = p; a; a = a.parent) {
    if (ts.isJsxExpression(a) || ts.isJsxAttribute(a)) return true;
    if (ts.isCallExpression(a) || ts.isFunctionLike(a) || ts.isVariableDeclaration(a) || ts.isPropertyAssignment(a) && a.parent?.parent && !ts.isJsxExpression(a.parent.parent)) return false;
  }
  return false;
}
const keys = new Set();
const files = DIRS.flatMap((d) => fs.readdirSync(path.join(ROOT, d)).filter((f) => f.endsWith('.tsx')).map((f) => path.join(ROOT, d, f)));
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const edits = [];
  const visit = (node) => {
    if (ts.isJsxText(node)) {
      const raw = node.getFullText();
      const core = decode(raw.trim().replace(/\s+/g, ' '));
      if (core && wordy(core) && !/[&]/.test(core)) {
        const lead = raw.match(/^\s*/)[0], trail = raw.match(/\s*$/)[0];
        const side = (w) => (w.includes('\n') ? w : w ? '{" "}' : '');
        edits.push([node.getFullStart(), node.getEnd(), side(lead) + `{t(${JSON.stringify(core)})}` + side(trail)]);
        keys.add(core);
      }
    } else if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer) && ATTRS.has(node.name.getText()) && wordy(node.initializer.text)) {
      edits.push([node.initializer.getStart(), node.initializer.getEnd(), `{t(${JSON.stringify(node.initializer.text)})}`]);
      keys.add(node.initializer.text);
    } else if (ts.isPropertyAssignment(node) && PROPS.has(node.name.getText()) && ts.isStringLiteral(node.initializer) && /^[A-Z]/.test(node.initializer.text) && wordy(node.initializer.text)) {
      edits.push([node.initializer.getStart(), node.initializer.getEnd(), `t(${JSON.stringify(node.initializer.text)})`]);
      keys.add(node.initializer.text);
    } else if (ts.isStringLiteral(node) && prose(node) && insideJsx(node)) {
      // Words chosen by a condition inside the markup: {busy ? "Checking…" : "Check structure"}, {x ?? "None"}.
      edits.push([node.getStart(), node.getEnd(), `t(${JSON.stringify(node.text)})`]);
      keys.add(node.text);
    } else if (ts.isCallExpression(node) && node.expression.getText() === 't' && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) {
      keys.add(node.arguments[0].text);
      return;
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  if (process.argv.includes('--list') || !edits.length) continue;
  let out = text;
  for (const [a, b, rep] of edits.sort((x, y) => y[0] - x[0])) out = out.slice(0, a) + rep + out.slice(b);
  if (!/from "(\.\.\/)+i18n"|from "\.\.\/\.\.\/i18n"/.test(out)) {
    const rel = path.relative(path.dirname(file), path.join(ROOT, 'src', 'i18n')).replace(/\\/g, '/');
    const spec = rel.startsWith('.') ? rel : './' + rel;
    const at = out.indexOf('\nimport ');
    out = at >= 0 ? out.slice(0, at) + `\nimport { t } from "${spec}";` + out.slice(at) : `import { t } from "${spec}";\n` + out;
  }
  fs.writeFileSync(file, out);
}
if (process.argv.includes('--list')) for (const k of [...keys].sort()) console.log(k);
else console.error(keys.size, 'keys');
