"""
extract_valuesets.py: the repeatable driver behind the value sets in spec-build/valuesets.json.

Like fields.json, the first value-set pass (2026-09-15) was run by hand. This module rebuilds one value-set page's entry
(metadata + concepts) from its rendered Confluence body, so a changed or new value-set page can be added the way the
first pass added the others.

    python3 -I spec-build/extract_valuesets.py verify
        rebuild every enumerated value set of the 2026-09-15 copy and compare with valuesets.json

    python3 -I spec-build/extract_valuesets.py show <pageId>
        print what the driver reads from spec-source/pages/<pageId>.json

Bindings (which field cites which value set) are not made here; see refresh_2026_10.py for the bindings this refresh
re-derived, each with the verbatim quote it rests on.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _extract_lib as X  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "spec-source", "snapshots", "2026-09-15", "pages")
PAGES = os.path.join(ROOT, "spec-source", "pages")


def _ws(s):
    return re.sub(r"\s+", " ", (s or "").replace("﻿", "")).strip()


def _key(h):
    return re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_") or "group"


def _cells(row):
    # cell text as published, trimmed; line breaks inside a cell are kept (the first pass kept them in extra columns)
    return [(c.text or "").replace("\ufeff", "").strip() for c in X.distinct_cells(row)]


def _rows(table):
    return [_cells(r) for r in X.table_to_grid(table)]


CODE_HDR = re.compile(r"code|^ucum", re.I)
NAME_HDR = re.compile(r"name|description|display|concrpt", re.I)


def _meta(rows):
    out = {}
    for r in rows:
        if len(r) >= 2 and r[0]:
            k = r[0].rstrip(":").strip().lower()
            if k.startswith("previous valueset name"):
                out["previousName"] = r[1] or None
            elif k.startswith("version"):
                out["version"] = r[1] or None
    # the "Definition | Value Set Identifier (OID) | Code System Identifier" layout (a header row, then values)
    if rows and len(rows) >= 2 and rows[0] and rows[0][0].lower() == "definition":
        hdr, val = rows[0], rows[1]
        for h, v in zip(hdr, val):
            hl = h.lower()
            if hl == "definition":
                out["definition"] = v or None
            elif "value set" in hl and "oid" in hl:
                out["valueSetOid"] = v or None
            elif "code system" in hl:
                out["codeSystemOid"] = v or None
    return out


def _is_meta(rows):
    if not rows:
        return False
    first = rows[0][0].lower() if rows[0] else ""
    return first.startswith("previous valueset name") or first.startswith("version") or first == "definition"


def _concept_table(tables):
    """The first concept table, with the rows of any later concept tables appended (a page may split its list)."""
    found = None
    for rows in tables:
        if _is_meta(rows) or not rows:
            continue
        hdr = [_ws(h) for h in rows[0]]
        if any(CODE_HDR.search(h) for h in hdr) or any(NAME_HDR.search(h) for h in hdr):
            if found is None:
                found = [hdr] + rows[1:]
            else:
                found += rows[1:]
    return found


def page_valueset(page):
    """{meta..., columns, concepts, external, quote} for one value-set page."""
    tables = [_rows(t) for t in X.parse_tables(page["html"])]
    meta = {}
    for rows in tables:
        if _is_meta(rows):
            meta.update(_meta([[_ws(c) for c in r] for r in rows]))
    text = _ws(re.sub(r"<[^>]+>", " ", page["html"]))
    ext = re.search(r"To obtain [^.]*? value set,? refer to [^.]*\.", text, re.I)
    rows = _concept_table(tables)
    out = dict(meta)
    if rows is None:
        out.update(columns=[], concepts=[], external=bool(ext), quote=ext.group(0) if ext else None)
        return out
    hdr = rows[0]
    ci = next((i for i, h in enumerate(hdr) if CODE_HDR.search(h)), None)
    di = next((i for i, h in enumerate(hdr) if i != ci and NAME_HDR.search(h)), None)
    if ci is None:  # a one-column "Concept Name" list: the name is the code
        ci = di
        di = None
    concepts = []
    for r in rows[1:]:
        r = r + [""] * (len(hdr) - len(r))
        code = _ws(r[ci])
        if not code or code.lower() in ("code", "concept code"):
            continue
        c = {"code": code, "display": (_ws(r[di]) or None) if di is not None else None}
        extra = {_key(hdr[i]): r[i] for i in range(len(hdr)) if i not in (ci, di) and r[i] != ""}
        if extra:
            c["extra"] = extra
        concepts.append(c)
    out.update(columns=hdr, concepts=concepts, external=bool(ext) and not concepts,
               quote=ext.group(0) if ext and not concepts else None)
    return out


def verify(limit=30):
    vs = json.load(open(os.path.join(ROOT, "spec-build", "valuesets.json")))
    ok = bad = 0
    for x in vs["valueSets"]:
        if x.get("conceptSource") != "confluence-table":
            continue
        got = page_valueset(X.load_page(SNAPSHOT, x["pageId"]))
        diffs = []
        for k in ("previousName", "version"):
            if (got.get(k) or None) != (x.get(k) or None) and not (x.get(k) is None and got.get(k) in ("NA", None)):
                diffs.append((k, x.get(k), got.get(k)))
        if got["columns"] != x["columns"]:
            diffs.append(("columns", x["columns"], got["columns"]))
        if got["concepts"] != x["concepts"]:
            n = next((i for i, (a, b) in enumerate(zip(x["concepts"], got["concepts"])) if a != b),
                     min(len(x["concepts"]), len(got["concepts"])))
            diffs.append((f"concepts[{n}] of {len(x['concepts'])}/{len(got['concepts'])}",
                          x["concepts"][n] if n < len(x["concepts"]) else None,
                          got["concepts"][n] if n < len(got["concepts"]) else None))
        if diffs:
            bad += 1
            if bad <= limit:
                print(x["id"], x["pageId"])
                for d in diffs:
                    print("   ", d[0], "\n      want", str(d[1])[:240], "\n      got ", str(d[2])[:240])
        else:
            ok += 1
    print(f"{ok} value sets identical, {bad} differ")
    return bad == 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "verify":
        sys.exit(0 if verify() else 1)
    elif cmd == "show":
        r = page_valueset(X.load_page(PAGES, sys.argv[2]))
        print(json.dumps(dict(r, concepts=r["concepts"][:8], conceptCount=len(r["concepts"])), ensure_ascii=False, indent=1))
