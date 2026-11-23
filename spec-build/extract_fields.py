"""
extract_fields.py: the repeatable driver behind spec-build/fields.json.

The first extraction (2026-09-15) was run by hand with _extract_lib.py and left no driver. This module rebuilds one
page's entry of fields.json from its rendered Confluence body, in exactly the first extraction's shape, so a changed
page can be re-extracted and compared row by row with what ISIT compiled.

    python3 -I spec-build/extract_fields.py verify   # rebuild every page of the 2026-09-15 copy, compare with fields.json

    python3 -I spec-build/extract_fields.py diff <new pages dir> <out.json>
                                                     # re-extract changed pages, compare with fields.json row by row

`verify` is the proof the driver extracts the way the first pass did: a page whose rebuilt entry differs from the
committed one is printed with the first differing path. HL7, FHIR and CDA pages rebuild identically (269 of 269 on the
2026-09-15 copy). XDS fixed-value tables do not: the first pass judged their rows' roles by hand, so a changed XDS page
needs a person's look, and `diff` says so.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _extract_lib as X  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUCKET = {"hl7": "segments", "fhir": "fhir", "cda": "cda", "xds": "xdsMetadata"}
COLUMNS = ["num", "name", "usage", "maxRpt", "elementLocation", "guidance"]


def _t(cell):
    return cell.text if cell is not None else ""


# Word comment anchors pasted into Confluence with the text ("ZPV1.54[AA11]", "5[MA1]", "No max[MA5]"; first seen on the
# 2026-09-20 ADT pages). Stripped from identifier and number cells only; quotes and guidance stay verbatim.
_ANCHOR = re.compile(r"\[[A-Z]{1,3}\d{1,3}\]")


def _id(s):
    return _ANCHOR.sub("", s or "")


def _clean(s):
    s = (s or "").strip()
    return s or None


def _quote(row):
    return " | ".join(c.text.strip() for c in X.distinct_cells(row) if c.text.strip())


def _hl7_rows(pid, title, ti, grid, info):
    cm = info["colmap"]
    rows = []
    for ri in range(info["headerIndex"] + 1, len(grid)):
        row = grid[ri]
        field = _id(_t(row[cm["field"]])).strip() or None
        get = lambda k: _t(row[cm[k]]) if cm.get(k) is not None else ""
        name = (get("fieldName").strip() or None) if cm.get("fieldName") is not None else None
        if not field and not name:
            continue
        usage_raw, rpt_raw = _id(get("usage")), _id(get("maxRpt"))
        usage = X.parse_usage(usage_raw, rpt_raw, hl7=True)
        length_raw = _id(get("length")).strip()
        _, lmax = X.parse_cardinality(length_raw) if re.fullmatch(r"\d+", length_raw or "") else (None, None)
        rows.append({
            "rowId": f"{pid}:{ti}:{ri}",
            "kind": "field",
            "field": field,
            "fieldName": name,
            "dataType": _clean(get("dataType")),
            "usage": usage,
            "length": {"raw": length_raw or None, "max": lmax},
            "codeSet": _clean(get("codeSet")),
            "guidance": _clean(get("guidance")),
            "role": X.classify_role(family="hl7", name=name, usage_entries=usage, raw_usage=usage_raw),
            "raw": {"usage": usage_raw.strip() or None, "maxRpt": rpt_raw.strip() or None},
            "source": {"pageId": pid, "pageTitle": title, "row": field or f"table {ti} row {ri}", "quote": _quote(row)},
        })
    return rows


def _tree_rows(pid, title, ti, grid, info):
    fam, kind, cm = info["family"], info["kind"], info["colmap"]
    rows = []
    for ri in range(info["headerIndex"] + 1, len(grid)):
        row = grid[ri]
        note = X.note_row_text(row)
        if note is not None and note.strip():
            rows.append({"rowId": f"{pid}:{ti}:{ri}", "kind": "note", "text": note.strip(),
                         "source": {"pageId": pid, "pageTitle": title, "row": f"table {ti} row {ri}",
                                    "quote": note.strip()}})
            continue
        name = _t(row[cm["name"]]).strip() or None
        if not any(c.text.strip() for c in X.distinct_cells(row)):
            continue
        nums = []
        if cm.get("num") is not None:
            for c in X.distinct_cells(row[cm["num"]:cm["numEnd"] + 1]):
                n = X.parse_num(c.text)
                if n:
                    nums.append(n)
        num = nums[-1] if nums else None
        get = lambda k: _t(row[cm[k]]) if cm.get(k) is not None else ""
        usage_raw, rpt_raw = get("usage"), get("maxRpt")
        usage = X.parse_usage(usage_raw, rpt_raw) if (usage_raw.strip() or rpt_raw.strip()) else []
        usage_note = None
        ucell = row[cm["usage"]] if cm.get("usage") is not None else None
        if ucell is not None and not ucell.phantom and ucell.colspan >= 3 and usage_raw.strip():
            usage, usage_note = [], usage_raw.strip()   # a prose cell spanning usage..guidance, not a usage code
        loc_raw = get("location")
        paths = X.split_paths(loc_raw)
        guidance = _clean(get("guidance"))
        role = X.classify_role(family=fam, name=name, usage_entries=usage, location_paths=paths,
                               guidance=guidance or "", raw_usage=usage_raw)
        out = {
            "rowId": f"{pid}:{ti}:{ri}",
            "kind": "field",
            "num": num,
            "numPath": nums or None,
            "name": name,
            "usage": usage,
            "elementLocation": [{"path": p, "kind": X.classify_path(p)} for p in paths],
            "elementLocationRaw": _clean("\n".join(ln.strip() for ln in loc_raw.split("\n") if ln.strip())),
            "guidance": guidance,
            "role": role if (usage or paths) else None,
            "roleConfidence": "high" if usage else "low",
            "raw": {"usage": usage_raw.strip() or None, "maxRpt": rpt_raw.strip() or None},
            "source": {"pageId": pid, "pageTitle": title, "row": num or name or f"table {ti} row {ri}", "quote": _quote(row)},
        }
        if usage_note:
            out["usageNote"] = usage_note
        if kind in ("metadataValue", "queryParameter"):
            out["fixedValue"] = _clean(get("value"))
        if kind == "queryParameter" and cm.get("multiple") is not None:
            out["multipleAllowed"] = _clean(get("multiple"))
        rows.append(out)
    tree = X.build_tree([r for r in rows if r["kind"] == "field"])
    return rows, tree


def page_entry(page):
    pid, title = str(page["id"]), page["title"]
    tables = []
    for ti, t in enumerate(X.parse_tables(page["html"])):
        grid = X.table_to_grid(t)
        info = X.classify_table(grid, page)
        if not info:
            continue
        hdr = [c.text for c in grid[info["headerIndex"]]]
        if info["family"] == "hl7":
            rows = _hl7_rows(pid, title, ti, grid, info)
            seg = rows[0]["field"].split(".")[0].split("-")[0] if rows else None
            tables.append({"tableIndex": ti, "family": "hl7", "kind": info["kind"], "segment": seg, "header": hdr,
                           "columns": X.HL7_COLUMNS, "rows": rows})
        else:
            rows, tree = _tree_rows(pid, title, ti, grid, info)
            nums = [r.get("num") for r in rows if r["kind"] == "field" and r.get("num")]
            style = "none" if not nums else ("hierarchical" if any("." in n for n in nums) else "flat")
            tables.append({"tableIndex": ti, "family": info["family"], "kind": info["kind"], "header": hdr,
                           "numberingStyle": style, "columns": COLUMNS, "rows": rows, "tree": tree})
    return {"pageId": pid, "pageTitle": title, "ancestors": _list(page.get("ancestors")),
            "ancestorIds": _list(page.get("ancestor_ids"))}, tables


def _list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.startswith("["):
        import ast
        return ast.literal_eval(v)
    return []


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        for k in list(a.keys()) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                return f"{path}.{k}", a.get(k, "<missing>"), b.get(k, "<missing>")
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}[len]", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else (path, a, b)


def verify(pages_dir, fields_path, limit=40):
    fields = json.load(open(fields_path))
    ok = bad = 0
    shown = 0
    for bucket in ("segments", "fhir", "cda"):
        for pid, want in fields[bucket].items():
            page = X.load_page(pages_dir, pid)
            head, tables = page_entry(page)
            got = dict(head, tables=[t for t in tables if BUCKET[t["family"]] == bucket])
            d = first_diff(want, got)
            if d:
                bad += 1
                if shown < limit:
                    shown += 1
                    print(f"{bucket} {pid} {page['title'][:40]!r}: {d[0]}\n   want {str(d[1])[:300]!r}\n   got  {str(d[2])[:300]!r}")
            else:
                ok += 1
    print(f"{ok} pages identical, {bad} differ")
    return bad == 0


# ---------------------------------------------------------------------------
# diff: what a re-extracted page changes in the rules
# ---------------------------------------------------------------------------

def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _row_key(row):
    if "field" in row:  # HL7
        return row.get("field") or _norm(row.get("fieldName"))
    loc = row["elementLocation"][0]["path"] if row.get("elementLocation") else ""
    return _norm(row.get("name")) + " @ " + _norm(loc)


def _usage_text(entries):
    out = []
    for e in entries or []:
        card = f"[{'' if e['min'] is None else e['min']}..{'*' if e['max'] is None else e['max']}]"
        out.append((e.get("usage") or "-") + " " + card + (f" ({e['condition']})" if e.get("condition") else ""))
    return "; ".join(out) or "-"


RULE_FIELDS = ("usage", "dataType", "length", "codeSet", "elementLocation", "role", "fixedValue")


def compare_rows(old_rows, new_rows):
    old = {}
    for r in old_rows:
        if r["kind"] == "field":
            old.setdefault(_row_key(r), r)
    new = {}
    for r in new_rows:
        if r["kind"] == "field":
            new.setdefault(_row_key(r), r)
    # a renamed row at the same location (or the same HL7 field) still pairs up
    def loose(r):
        return r.get("field") or (r["elementLocation"][0]["path"] if r.get("elementLocation") else _norm(r.get("name")))
    out = []
    unmatched_old = {k: r for k, r in old.items() if k not in new}
    for k, n in new.items():
        o = old.get(k)
        if o is None:
            cand = [ok for ok, orow in unmatched_old.items() if loose(orow) == loose(n)]
            if len(cand) == 1:
                o = unmatched_old.pop(cand[0])
        if o is None:
            out.append({"change": "added", "new": n})
            continue
        what = [f for f in RULE_FIELDS if json.dumps(o.get(f), sort_keys=True) != json.dumps(n.get(f), sort_keys=True)]
        if _norm(o.get("name") or o.get("fieldName")) != _norm(n.get("name") or n.get("fieldName")):
            what.append("name")
        if _norm(o.get("guidance")) != _norm(n.get("guidance")):
            what.append("guidance")
        if what:
            out.append({"change": "changed", "what": what, "old": o, "new": n})
    for k, o in unmatched_old.items():
        out.append({"change": "removed", "old": o})
    return out


def diff(new_dir, out_path, replaced=None):
    fields = json.load(open(os.path.join(ROOT, "spec-build", "fields.json")))
    by_id = {}
    for bucket, pages in fields.items():
        if bucket in BUCKET.values():
            for pid, entry in pages.items():
                by_id[pid] = (bucket, entry)
    replaced = replaced or {}
    report = []
    for f in sorted(os.listdir(new_dir)):
        page = json.load(open(os.path.join(new_dir, f)))
        pid = str(page["id"])
        head, tables = page_entry(page)
        old_id = replaced.get(pid, pid)
        old_bucket, old_entry = by_id.get(old_id, (None, None))
        old_tables = old_entry["tables"] if old_entry else []
        if not tables and not old_tables:
            continue
        new_rows = [r for t in tables for r in t["rows"]]
        old_rows = [r for t in old_tables for r in t["rows"]]
        families = sorted({t["family"] for t in tables} | {t["family"] for t in old_tables})
        report.append({
            "pageId": pid, "replaces": old_id if old_id != pid else None, "title": page["title"],
            "version": page.get("version"), "updatedAt": page.get("when"), "families": families,
            "status": "new" if not old_entry else "changed",
            "needsPerson": "xds" in families,
            "entry": dict(head, tables=tables),
            "rows": compare_rows(old_rows, new_rows),
        })
    json.dump(report, open(out_path, "w"), indent=1, ensure_ascii=False)
    for p in report:
        n = len(p["rows"])
        print(f"{p['status']:7} {p['pageId']:>10} {p['title'][:50]:50} {','.join(p['families']):8} {n:3} row changes")
    return report


def apply(page_ids, replaced, at, note):
    """Re-extract `page_ids` from spec-source/pages into fields.json (a replaced page's old entry is dropped)."""
    path = os.path.join(ROOT, "spec-build", "fields.json")
    fields = json.load(open(path))
    pages_dir = os.path.join(ROOT, "spec-source", "pages")
    done = []
    for pid in page_ids:
        page = X.load_page(pages_dir, pid)
        head, tables = page_entry(page)
        old = replaced.get(pid)
        for bucket in BUCKET.values():
            mine = [t for t in tables if BUCKET[t["family"]] == bucket]
            entry = dict(head, tables=mine) if mine else None
            # keep the page where it stood (a replaced page takes its predecessor's place) so the diff stays readable
            rebuilt, placed = {}, False
            for k, v in fields[bucket].items():
                if k in (pid, old):
                    if entry is not None and not placed:
                        rebuilt[pid], placed = entry, True
                    continue
                rebuilt[k] = v
            if entry is not None and not placed:
                rebuilt[pid] = entry
            fields[bucket] = rebuilt
        done.append({"pageId": pid, "title": page["title"], "version": page.get("version"),
                     "updatedAt": page.get("when"), **({"replaces": old} if old else {})})
    gf = fields["generatedFrom"]
    gf.setdefault("firstGeneratedAt", gf.get("generatedAt"))
    gf["generatedAt"] = at
    gf.setdefault("refreshes", []).append({"at": at, "note": note, "pages": done})
    with open(path, "w") as fh:
        json.dump(fields, fh, ensure_ascii=False, indent=1)  # the first extraction's exact style
    print(f"{len(done)} pages re-extracted into fields.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "verify":
        sys.exit(0 if verify(os.path.join(ROOT, "spec-source", "pages"), os.path.join(ROOT, "spec-build", "fields.json"),
                             int(sys.argv[2]) if len(sys.argv) > 2 else 40) else 1)
    elif cmd == "apply":
        # apply <ids comma-separated> <replaced json> <at> <note>
        apply(sys.argv[2].split(","), json.loads(sys.argv[3]), sys.argv[4], sys.argv[5])
    elif cmd == "diff":
        replaced = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        diff(sys.argv[2], sys.argv[3], replaced)
