"""
refresh_2026_10.py: what NPHIES published on 20 Sep and 13 Oct 2026, carried into the hand-built artefacts.

fields.json is refreshed by extract_fields.py (`apply`). This script carries the same refresh into the artefacts the first
pass built by hand, and records every change it makes under meta.refreshes so the "What NPHIES changed" list can show it:

  valuesets.json   30 new CS-Clinical-* value sets; CS-Lab-SpecimenType (315 HL7 codes -> 1,819 SNOMED codes) and
                   CS-Rad-Procedure (was "Imaging Procedures") updated in place; the value-set links (bindings) of the
                   ADT segment pages re-derived from the new pages (PID, PV1, DG1 and PR1 moved to new page ids, ZPV1,
                   ZDG1 and ZPR1 are new), each with the verbatim words it rests on; inline code tables on DG1 and PR1
                   become page-local value sets.
  datatypes.json   the component tables of PV1, DG1 and PR1 cited on their new pages.
  constants.json   OID citations of the old ADT pages moved to the new ones.

    python3 -I spec-build/refresh_2026_10.py          # apply (refuses to run twice; restore the files from git first)

Never judged here: the A08-only code restrictions on PV1.4 and PV1.36 (a note in the guidance, for one message type).
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _extract_lib as X  # noqa: E402
import extract_valuesets as V  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "spec-build")
REFRESH = "2026-10"
AT = "2026-11-03T00:00:00+00:00"
NOTE = "NPHIES changes published 20 Sep and 13 Oct 2026"

OLD2NEW = {"7766393": "873496585", "7766425": "873496616", "7766496": "873496667", "7766519": "873824257"}
ADT_PAGES = ["873496585", "873496616", "873496667", "873824257", "873300011", "873038123", "873660638"]
# value-set pages published or changed since the 2026-09-15 copy
NEW_VS_PAGES = [
    "872611942", "872611952", "872611967", "872612017", "872612049", "872612110", "873037985", "873038009", "873038020",
    "873038032", "873038048", "873300043", "873300076", "873300088", "873300127", "873300270", "873332790", "873332855",
    "873332883", "873332942", "873660424", "873660547", "873660557", "873660572", "873660582", "873660625", "873725963",
    "873725996", "873726017",
]
CHANGED_VS = {"30736696": "laboratory-specimen-type", "23168870": "imaging-procedures"}
# rows whose inline code list applies to the A08 discharge update only: shown, never judged
A08_ONLY = {"PV1.4", "PV1.36"}


def load(name):
    return json.load(open(os.path.join(B, name)))


def save(name, data):
    # each file keeps the first pass's exact style: valuesets.json compact, the others indented by two
    with open(os.path.join(B, name), "w") as fh:
        if name == "valuesets.json":
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, fh, ensure_ascii=False, indent=2)


def already(meta):
    return any(r.get("id") == REFRESH for r in meta.get("refreshes", []))


def norm_alias(s):
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", (s or "").strip().lower())).strip()


def page(pid):
    return X.load_page(os.path.join(ROOT, "spec-source", "pages"), pid)


# ---------------------------------------------------------------------------------------------------------------------
# value sets
# ---------------------------------------------------------------------------------------------------------------------

def vs_entry(pid):
    p = page(pid)
    g = V.page_valueset(p)
    title = p["title"].strip()
    prev = g.get("previousName")
    prev = None if (prev or "").upper() in ("", "NA", "N/A") else prev
    concepts = g["concepts"]
    entry = {
        "id": title.lower(), "pageId": pid, "title": title, "previousName": prev,
        "aliases": [prev] if prev else [], "version": g.get("version"), "definition": g.get("definition"),
        "valueSetOid": g.get("valueSetOid"), "codeSystemOid": g.get("codeSystemOid"), "scope": "nphies-value-set",
        "external": False, "validation": "enumerated" if concepts else "format-only", "columns": g["columns"],
        "conceptSource": "confluence-table" if concepts else None, "conceptCount": len(concepts), "concepts": concepts,
        "source": {"pageId": pid, "pageTitle": title,
                   "row": "Previous valueSet name" if "previousName" in g else "page body",
                   "quote": (f"Previous valueSet name: {g['previousName']}" if "previousName" in g
                             else (title if concepts else "(the page is published empty)"))},
        "refresh": REFRESH,
    }
    if not concepts:
        entry["note"] = "The page lists no codes (published empty on 2026-09-20), so codes from it cannot be checked."
    return entry


def refresh_valuesets(fields):
    vs = load("valuesets.json")
    if already(vs["meta"]):
        sys.exit("valuesets.json already carries refresh " + REFRESH)
    sets = vs["valueSets"]
    by_id = {x["id"]: x for x in sets}
    by_title = {x["title"].lower(): x["id"] for x in sets}
    record = {"id": REFRESH, "at": AT, "note": NOTE, "valueSetsAdded": [], "valueSetsChanged": [], "bindingsRemoved": [],
              "bindingsAdded": [], "notJudged": []}

    # 1. new value-set pages
    for pid in NEW_VS_PAGES:
        e = vs_entry(pid)
        if e["id"] in by_id:
            sys.exit(f"value set {e['id']} already exists")
        sets.append(e)
        by_id[e["id"]] = e
        by_title[e["title"].lower()] = e["id"]
        record["valueSetsAdded"].append({"id": e["id"], "title": e["title"], "pageId": pid, "concepts": e["conceptCount"]})

    # 2. changed value-set pages, updated in place (ids kept: bindings and compiled files cite them)
    for pid, vid in CHANGED_VS.items():
        x = by_id[vid]
        new = vs_entry(pid)
        before = {k: x.get(k) for k in ("title", "previousName", "version", "definition", "valueSetOid", "codeSystemOid",
                                         "external", "validation", "conceptCount")}
        before["sampleCodes"] = [c["code"] for c in (x.get("concepts") or [])[:6]]
        x["supersedes"] = before
        x["title"] = new["title"]
        x["previousName"] = new["previousName"]
        x["version"] = new["version"]
        x["aliases"] = sorted({*(x.get("aliases") or []), before["title"], *( [new["previousName"]] if new["previousName"] else [])} - {new["title"]})
        if vid == "laboratory-specimen-type":
            # the new page states no definition or OIDs; the old OIDs named HL7 table 0487, which the codes no longer are
            x.update(definition=None, valueSetOid=None, codeSystemOid=None, columns=new["columns"],
                     concepts=new["concepts"], conceptCount=new["conceptCount"], conceptSource="confluence-table",
                     source=new["source"])
        else:
            # CS-Rad-Procedure: the page now carries only its previous name and version; still no codes, and no longer
            # the "refer to NHIC" note. Kept external (codes cannot be checked offline); OIDs as PR1.3 still cites them.
            x["source"] = new["source"]
            x["note"] = ("Renamed from \"Imaging Procedures\" on 2026-09-20. The page lists no codes and no longer says "
                         "where to obtain them; PR1.3 still names its code system 2.16.840.1.113883.3.3731.1.204.15.")
        x["refresh"] = REFRESH
        by_title[x["title"].lower()] = vid
        after = {k: x.get(k) for k in before if k != "sampleCodes"}
        after["sampleCodes"] = [c["code"] for c in (x.get("concepts") or [])[:6]]
        record["valueSetsChanged"].append({"id": vid, "pageId": pid, "before": before, "after": after})

    # aliases for everything added or renamed
    for x in sets:
        if x.get("refresh") != REFRESH:
            continue
        for name, origin in [(x["title"], "title"), *[(a, "previousName" if a == x.get("previousName") else "alias")
                                                       for a in x.get("aliases") or []]]:
            k = norm_alias(name)
            if k and k not in vs["aliasIndex"]:
                vs["aliasIndex"][k] = x["id"]
                vs["aliasOrigin"][k] = origin

    # 3. bindings of the ADT segment pages: the old pages' links go, the new pages' links are read from their words
    keep = []
    for b in vs["bindings"]:
        if str(b.get("pageId")) in OLD2NEW:
            record["bindingsRemoved"].append({"pageId": b["pageId"], "fieldKey": b["fieldKey"], "valueSetId": b.get("valueSetId"),
                                              "referenceText": b.get("referenceText")})
        else:
            keep.append(b)
    vs["bindings"] = keep

    seg = fields["segments"]
    # opening quotes only: a straight apostrophe ("Consultant's") must not open a reference
    quoted = re.compile(r"[“\"‘]([^”\"’\n]{3,80})[”\"’]\s*(?:value[- ]?set|Value Set)", re.I)
    listed = re.compile(r"\bCS-[A-Za-z]+-[A-Za-z0-9]+\b")
    local_n = {}
    for pid in ADT_PAGES:
        entry = seg[pid]
        title = entry["pageTitle"]
        tables = [V._rows(t) for t in X.parse_tables(page(pid)["html"])]
        for t in entry["tables"]:
            for r in t["rows"]:
                if r.get("kind") != "field" or not r.get("field"):
                    continue
                fk = f"{r['field']} / {r['fieldName']}"
                found = []  # (referenceText, column, extraction, quote)
                if r.get("codeSet"):
                    found.append((r["codeSet"].strip(), "codeSet", "codeset-bare", r["codeSet"].strip()))
                g = r.get("guidance") or ""
                lines = g.split("\n")
                for m in quoted.finditer(g):
                    line = next((ln for ln in lines if m.group(0) in ln), m.group(0))
                    found.append((m.group(1).strip(), "guidance", "quoted", line.strip()))
                for m in listed.finditer(g):
                    line = next((ln for ln in lines if m.group(0) in ln), m.group(0))
                    found.append((m.group(0), "guidance", "listed", line.strip()))
                if re.search(r"value out of ICD10-AM", g):
                    line = next(ln for ln in lines if "ICD10-AM" in ln)
                    found.append(("ICD10-AM", "guidance", "codeset-bare", line.strip()))
                seen = set()
                # a reference by the value set's exact title is the one kept when two name the same set
                found.sort(key=lambda f: f[0].lower() not in by_title)
                for ref, col, how, quote in found:
                    vid, via = None, None
                    if ref.lower() in by_title:
                        vid, via = by_title[ref.lower()], "exact-title"
                    elif norm_alias(ref) in vs["aliasIndex"]:
                        vid = vs["aliasIndex"][norm_alias(ref)]
                        via = "previousName-alias" if vs["aliasOrigin"].get(norm_alias(ref)) == "previousName" else "alias-index"
                    elif ref == "ICD10-AM":
                        via = "external-code-system"
                    if via is None:
                        record["notJudged"].append({"pageId": pid, "fieldKey": fk, "why": f"\"{ref}\" names no published value set",
                                                    "quote": quote})
                        continue
                    if (vid or ref) in seen:
                        continue
                    seen.add(vid or ref)
                    b = {"fieldKey": fk, "pageId": pid, "pageTitle": title, "column": col, "referenceText": ref,
                         "extraction": how, "valueSetId": vid, "resolvedVia": via, "confidence": "high",
                         "source": {"pageId": pid, "pageTitle": title, "row": fk, "quote": quote}, "refresh": REFRESH}
                    if via == "external-code-system":
                        b["externalSystem"] = "ICD-10-AM"
                    vs["bindings"].append(b)
                    record["bindingsAdded"].append({"pageId": pid, "fieldKey": fk, "valueSetId": vid, "referenceText": ref,
                                                    "resolvedVia": via})
                # an inline code table in the guidance ("Identifier | Text" or "Code | Display")
                if "\nIdentifier\nText\n" in g or "\nCode\nDisplay\n" in g:
                    tbl = next((rows for rows in tables if rows and rows[0][:2] in (["Identifier", "Text"], ["Code", "Display"])
                                and all(c[0] in g for c in rows[1:] if c and c[0]) and id(rows) not in local_n.get(pid, {})), None)
                    if tbl is None:
                        continue
                    local_n.setdefault(pid, {})[id(tbl)] = True
                    quote = next((ln for ln in lines if "A08" in ln and "restricted" in ln), None) if r["field"] in A08_ONLY else None
                    quote = (quote or next((ln for ln in lines if "following" in ln and ("codes" in ln or "values" in ln)),
                                           lines[0])).strip()
                    if r["field"] in A08_ONLY:
                        record["notJudged"].append({"pageId": pid, "fieldKey": fk, "quote": quote,
                                                    "why": "the listed codes apply to the A08 discharge update only; "
                                                           "the value set stays the check, the A08 list is shown"})
                        continue
                    n = len(local_n[pid])
                    lid = f"local-{pid}-{n}"
                    concepts = [{"code": c[0], "display": c[1] if len(c) > 1 else None} for c in tbl[1:] if c and c[0]]
                    sets.append({"id": lid, "pageId": pid, "title": f"{r['fieldName']} ({title})", "previousName": None,
                                 "aliases": [], "version": None, "definition": None, "valueSetOid": None,
                                 "codeSystemOid": None, "scope": "page-local-table", "external": False,
                                 "validation": "enumerated", "columns": tbl[0], "conceptSource": "inline-table-on-citing-page",
                                 "conceptCount": len(concepts), "concepts": concepts,
                                 "source": {"pageId": pid, "pageTitle": title, "row": f"inline table on {r['field']}", "quote": quote},
                                 "refresh": REFRESH})
                    vs["bindings"].append({"fieldKey": fk, "pageId": pid, "pageTitle": title, "column": "guidance",
                                           "referenceText": f"inline table on {r['field']}", "extraction": "inline-table",
                                           "valueSetId": lid, "resolvedVia": "page-local-table", "confidence": "high",
                                           "source": {"pageId": pid, "pageTitle": title, "row": fk, "quote": quote},
                                           "note": "the codes are listed in the field's own guidance", "refresh": REFRESH})
                    record["valueSetsAdded"].append({"id": lid, "title": f"{r['fieldName']} ({title})", "pageId": pid,
                                                     "concepts": len(concepts), "pageLocal": True})
                    record["bindingsAdded"].append({"pageId": pid, "fieldKey": fk, "valueSetId": lid,
                                                    "referenceText": f"inline table on {r['field']}", "resolvedVia": "page-local-table"})

    st = vs["stats"]
    st["valueSets"] = len(sets)
    st["valueSetPages"] = len({x["pageId"] for x in sets if x["scope"] == "nphies-value-set"})
    st["valueSetsWithConcepts"] = sum(1 for x in sets if x.get("concepts"))
    st["valueSetsPageLocal"] = sum(1 for x in sets if x["scope"] == "page-local-table")
    st["totalConcepts"] = sum(len(x.get("concepts") or []) for x in sets)
    st["aliasIndexSize"] = len(vs["aliasIndex"])
    st["bindings"] = len(vs["bindings"])
    vs["meta"].setdefault("refreshes", []).append(record)
    save("valuesets.json", vs)
    print(f"valuesets.json: +{len(record['valueSetsAdded'])} value sets, {len(record['valueSetsChanged'])} changed, "
          f"-{len(record['bindingsRemoved'])} / +{len(record['bindingsAdded'])} bindings, {len(record['notJudged'])} shown not judged")
    return record


# ---------------------------------------------------------------------------------------------------------------------
# datatypes + constants: citations of the old ADT pages
# ---------------------------------------------------------------------------------------------------------------------

def _repoint(n, changes, path=""):
    if isinstance(n, dict):
        for k in ("pageId",):
            if str(n.get(k)) in OLD2NEW:
                changes.append(path + "." + k)
                n[k] = OLD2NEW[str(n[k])]
        for k, v in list(n.items()):
            if k == "supersedes":
                continue
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v) and any(x in OLD2NEW for x in v):
                n[k] = list(dict.fromkeys(OLD2NEW.get(x, x) for x in v))  # same order, the new id where the old stood
                changes.append(path + "." + k)
            else:
                _repoint(v, changes, path + "." + k)
    elif isinstance(n, list):
        for i, v in enumerate(n):
            _repoint(v, changes, f"{path}[{i}]")


def _component_quote(pid, field, anchor=None):
    """'Field | Length\\n…' of the component table in `field`'s guidance on the new page."""
    f = load("fields.json")
    for t in f["segments"][pid]["tables"]:
        for r in t["rows"]:
            if r.get("field") == field:
                g = (r.get("guidance") or "").replace("\ufeff", "")
                lines = g.split("\n")
                if "Field" not in lines:
                    # PV1: the component table is a table of its own that the guidance points to ("Table 10.1")
                    own = [rows for rows in (V._rows(tb) for tb in X.parse_tables(page(pid)["html"]))
                           if rows and rows[0] == ["Field", "Length"]]
                    rows = own[int(anchor.split(".")[-1]) - 1 if anchor else 0]
                    return "\n".join(" | ".join(c.replace("\ufeff", "") for c in r2) for r2 in rows), g
                i = lines.index("Field")
                pairs = [f"{lines[j]} | {lines[j + 1]}" for j in range(i, len(lines) - 1, 2)
                         if not lines[j].startswith("Example")]
                out = []
                for p in pairs:
                    if p.startswith("Example"):
                        break
                    out.append(p)
                return "\n".join(out[:7]), g
    return None, None


def refresh_datatypes():
    d = load("datatypes.json")
    meta = d.setdefault("refreshes", [])
    if any(r.get("id") == REFRESH for r in meta):
        sys.exit("datatypes.json already carries refresh " + REFRESH)
    changes = []
    for dt in d["datatypes"].values():
        for c in dt.get("nphiesConstraints") or []:
            old = c["id"].split("/")[0]
            if old in OLD2NEW:
                new = OLD2NEW[old]
                c["supersedes"] = {"id": c["id"], "source": dict(c["source"])}
                c["id"] = f"{new}/{c['id'].split('/', 1)[1]}"
                quote, guidance = _component_quote(new, c["parentField"], (c.get("anchor") or "").replace("#Table-", "") or None)
                c["source"] = {"pageId": new, "pageTitle": c["source"]["pageTitle"],
                               "row": f"{c['parentField']} component table", "quote": quote or c["source"]["quote"]}
                for comp in c["acceptedComponents"]:
                    if comp.get("maxLengthCellIsConstraint"):
                        # the coding-system cell now reads 100; the value it must carry moved into the field's guidance
                        comp["maxLengthCellIsConstraint"] = False
                        comp["maxLength"] = 100
                        line = next((ln for ln in (guidance or "").split("\n") if "Name of Coding System" in ln), None)
                        comp["constraintSource"] = "guidance"
                        if line:
                            comp["constraintQuote"] = line.strip()
                c["refresh"] = REFRESH
                changes.append(c["id"])
    _repoint(d["datatypes"], changes, "datatypes")
    _repoint(d.get("stats", {}), changes, "stats")
    meta.append({"id": REFRESH, "at": AT, "note": NOTE + ": PID, PV1, DG1 and PR1 moved to new page ids", "changed": changes})
    save("datatypes.json", d)
    print(f"datatypes.json: {len(changes)} citations moved")


def refresh_constants():
    c = load("constants.json")
    meta = c["meta"].setdefault("refreshes", [])
    if any(r.get("id") == REFRESH for r in meta):
        sys.exit("constants.json already carries refresh " + REFRESH)
    changes = []
    # the ACHI / ADA coding-system OIDs were quoted from PR1's old component table; PR1.3's guidance states them now
    _, g = _component_quote("873824257", "PR1.3")
    for item in c["oids"]["items"]:
        src = item.get("source") or {}
        if src.get("pageId") == "7766519" and src.get("row") == "Name of Coding System":
            oid = item.get("oid") or item.get("value")
            line = next((ln for ln in g.split("\n") if oid and oid in ln), None)
            item["source"] = {"pageId": "873824257", "pageTitle": "PR1", "row": "PR1.3", "quote": (line or src["quote"]).strip()}
            item["exampleQuote"] = item["source"]["quote"]
            changes.append(f"oid {oid}")
    _repoint(c, changes, "constants")
    meta.append({"id": REFRESH, "at": AT, "note": NOTE + ": PID, PV1, DG1 and PR1 moved to new page ids", "changed": changes})
    save("constants.json", c)
    print(f"constants.json: {len(changes)} citations moved")


if __name__ == "__main__":
    fields = load("fields.json")
    refresh_valuesets(fields)
    refresh_datatypes()
    refresh_constants()
