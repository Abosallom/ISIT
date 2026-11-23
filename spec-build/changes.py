"""
changes.py: the "What NPHIES changed" list, written to spec-build/changes.json (compiled into src/spec/changes.json).

For a reviewer, not a parser: every row a refresh changed, before and after, with the words it rests on; the value sets
added and changed; what is shown but not judged; and the changed pages that are NOT yet in the rules, with why.

    python3 -I spec-build/changes.py

"Before" is read from the 2026-09-15 copy of each page (spec-source/snapshots/2026-09-15), re-extracted with the same
driver that `extract_fields.py verify` proved rebuilds the first extraction exactly; "after" is fields.json as it is now.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _extract_lib as X  # noqa: E402
import extract_fields as E  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "spec-build")
SNAP = os.path.join(ROOT, "spec-source", "snapshots", "2026-09-15", "pages")
REFRESH = "2026-10"
SUMMARY_PAGE = "7766314"  # ADT "Segment Description": a table per segment, last edited 2025-06-02
Z_NOTE = ("Not applied to messages yet: this segment belongs to the A08 discharge update, which is not a structure of its "
          "own in ISIT yet.")
Z_NOTE_AR = "لا يُطبَّق على الرسائل بعد: هذا المقطع يخص تحديث الخروج A08، وليس له في ISIT هيكل خاص به بعد."
RULE = {"usage", "dataType", "length", "codeSet", "elementLocation", "role", "fixedValue"}

AR = {
    "a08": "رسالة تحديث الخروج A08 نوع جديد (يميّزه ZPV1.8 = \"UPDATE\")؛ وليس لها في ISIT هيكل خاص بها بعد، فقواعد ZPV1 وZDG1 وZPR1 الجديدة لا تُطبَّق على الرسائل.",
    "a08part": "جزء من نوع تحديث الخروج A08، وليس له في ISIT هيكل خاص به بعد.",
    "a08prose": "نص حالات الاستخدام؛ يذكر تحديث الخروج A08، وليس له هيكل خاص به بعد.",
    "bundle": "عدد الموارد التي يجب أن تحملها الحزمة لم يُقرأ في هيكل الحزمة بعد.",
    "errors": "دليل الأخطاء (فك رموز الأخطاء) لم يُقرأ بعد؛ من تغييراته حدّ حجم 1.5 ميغابايت.",
    "samples": "عينات رسمية جديدة (13 أكتوبر 2026)؛ ما زال ISIT يختبر نفسه على العينات السابقة.",
    "other": "تغيّرت منذ بناء القواعد؛ ولم تُقرأ فيها بعد.",
}
WHY_AR = {"873463809": "a08", "873660693": "a08part", "118063972": "a08prose", "351698947": "bundle", "387383323": "bundle",
          "414154754": "bundle", "414679041": "bundle", "58687511": "errors", "125206589": "samples", "358776855": "samples",
          "358514693": "samples", "387481602": "samples", "414089220": "samples", "927268883": "samples", "927432706": "samples"}

# Changed pages this refresh has not carried into the rules yet, and why (anything else changed is listed as "not read")
PENDING = {
    "873463809": "The A08 discharge-update message is a new variant (ZPV1.8 = \"UPDATE\" marks it); ISIT does not have it as a structure of its own yet, so the new ZPV1, ZDG1 and ZPR1 rules are not applied to messages.",
    "873660693": "Part of the A08 discharge-update variant, which is not a structure of its own in ISIT yet.",
    "118063972": "Use-case prose; it names the A08 discharge update, which is not a structure of its own yet.",
    "351698947": "Which resources a Laboratory Order bundle must carry (entry counts) is not re-read into the bundle structure yet.",
    "387383323": "Which resources a Radiology Order bundle must carry (entry counts) is not re-read into the bundle structure yet.",
    "414154754": "Which resources a structured Radiology Report bundle must carry is not re-read into the bundle structure yet.",
    "414679041": "Which resources an embedded-PDF Radiology Report bundle must carry is not re-read into the bundle structure yet.",
    "58687511": "The error catalogue (Error Decoder) is not re-read yet; one change is a 1.5 MiB size limit.",
    "125206589": "New official samples (13 Oct 2026); ISIT still checks itself against the earlier samples.",
    "358776855": "New official Laboratory Order samples (13 Oct 2026), not yet among ISIT's official samples.",
    "358514693": "New official Laboratory Results samples (13 Oct 2026), not yet among ISIT's official samples.",
    "387481602": "New official Radiology Order samples (13 Oct 2026), not yet among ISIT's official samples.",
    "414089220": "New official Radiology Report samples (13 Oct 2026), not yet among ISIT's official samples.",
    "927268883": "New official Raqeeb medication samples (13 Oct 2026), not yet among ISIT's official samples.",
    "927432706": "New official non-Raqeeb medication samples (13 Oct 2026), not yet among ISIT's official samples.",
}


def load(name):
    return json.load(open(os.path.join(B, name)))


def usage_text(entries):
    return E._usage_text(entries) if entries else None


def side(r, vs_titles):
    if r is None:
        return None
    out = {"usage": usage_text(r.get("usage"))}
    if r.get("length") and (r["length"].get("raw") or r["length"].get("max")):
        out["length"] = r["length"].get("raw")
    if r.get("dataType"):
        out["dataType"] = r["dataType"]
    if r.get("codeSet"):
        out["codeSet"] = r["codeSet"]
    if r.get("elementLocation"):
        out["location"] = " | ".join(x["path"] for x in r["elementLocation"])
    if r.get("role"):
        out["role"] = r["role"]
    if vs_titles:
        out["valueSets"] = vs_titles
    return out


def main():
    fields = load("fields.json")
    vs = load("valuesets.json")
    by_vs = {x["id"]: x for x in vs["valueSets"]}
    refresh = next(r for r in fields["generatedFrom"]["refreshes"] if r["note"].startswith("NPHIES changes published 20 Sep"))
    vsrec = next(r for r in vs["meta"]["refreshes"] if r["id"] == REFRESH)
    entries = {}
    for b in ("segments", "fhir", "cda", "xdsMetadata"):
        for pid, e in fields[b].items():
            entries.setdefault(pid, []).append(e)

    # value-set titles per (page, field) after and before
    def titles(ids):
        return sorted({by_vs[i]["title"] if i in by_vs else i for i in ids if i})
    after_vs, before_vs = {}, {}
    for b in vs["bindings"]:
        if b.get("refresh") == REFRESH:
            after_vs.setdefault((b["pageId"], b["fieldKey"].split(" / ")[0]), []).append(b.get("valueSetId") or b["referenceText"])
    for b in vsrec["bindingsRemoved"]:
        before_vs.setdefault((b["pageId"], b["fieldKey"].split(" / ")[0]), []).append(b.get("valueSetId") or b["referenceText"])

    # what the ADT summary page still says, per field
    summary = {}
    for t in fields["segments"][SUMMARY_PAGE]["tables"]:
        for r in t["rows"]:
            if r.get("field"):
                summary[r["field"]] = usage_text(r.get("usage"))

    pages = []
    counts = {"pages": 0, "ruleChanges": 0, "wordingChanges": 0, "rowsAdded": 0, "rowsRemoved": 0}
    for p in refresh["pages"]:
        pid = p["pageId"]
        old_id = p.get("replaces") or pid
        if os.path.exists(os.path.join(SNAP, old_id + ".json")):
            _, tables = E.page_entry(X.load_page(SNAP, old_id))
            old_rows = [r for t in tables for r in t["rows"]]
        else:
            old_rows = []
        new_entries = entries.get(pid, [])
        new_rows = [r for e in new_entries for t in e["tables"] for r in t["rows"]]
        head = new_entries[0] if new_entries else {}
        rows = []
        for ch in E.compare_rows(old_rows, new_rows):
            o, n = ch.get("old"), ch.get("new")
            r = n or o
            field = r.get("field")
            key_new, key_old = (pid, field), (old_id, field)
            vs_after = titles(after_vs.get(key_new, [])) if field else []
            vs_before = titles(before_vs.get(key_old, [])) if field else []
            what = list(ch.get("what", []))
            if field and vs_after != vs_before and ch["change"] == "changed":
                what.append("valueSets")
            kind = "rule" if ch["change"] != "changed" or (set(what) & (RULE | {"valueSets"})) else "wording"
            if ch["change"] == "changed" and kind == "wording" and set(what) <= {"guidance", "name"}:
                kind = "wording"
            row = {
                "change": ch["change"], "kind": kind, "what": what,
                "field": field, "name": r.get("fieldName") or r.get("name"), "num": r.get("num"),
                "before": side(o, vs_before), "after": side(n, vs_after),
                "quote": (n or o).get("quote"),
                "guidanceBefore": (o or {}).get("guidance") if "guidance" in what else None,
                "guidanceAfter": (n or {}).get("guidance") if "guidance" in what or ch["change"] == "added" else None,
            }
            if field and p.get("replaces") and summary.get(field) and n and summary[field] != usage_text(n.get("usage")):
                row["summaryStill"] = summary[field]
            rows.append(row)
            if ch["change"] == "added":
                counts["rowsAdded"] += 1
            elif ch["change"] == "removed":
                counts["rowsRemoved"] += 1
            elif kind == "rule":
                counts["ruleChanges"] += 1
            else:
                counts["wordingChanges"] += 1
        ancestors = head.get("ancestors") or []
        pages.append({
            "pageId": pid, "title": p["title"], "replaces": p.get("replaces"), "version": p.get("version"),
            "updatedAt": p.get("updatedAt"), "area": ancestors[3] if len(ancestors) > 3 else (ancestors[-1] if ancestors else None),
            "status": "new" if not old_rows else "changed", "rows": rows,
            **({"note": Z_NOTE, "noteAr": Z_NOTE_AR} if p["title"] in ("ZPV1", "ZDG1", "ZPR1") else {}),
        })
        counts["pages"] += 1

    # value sets
    added = [a for a in vsrec["valueSetsAdded"]]
    changed = []
    for c in vsrec["valueSetsChanged"]:
        changed.append({"id": c["id"], "pageId": c["pageId"], "before": c["before"], "after": c["after"],
                        "note": by_vs[c["id"]].get("note")})
    empty = [{"id": x["id"], "title": x["title"], "pageId": x["pageId"]} for x in vs["valueSets"]
             if x.get("refresh") == REFRESH and not x.get("concepts") and not x.get("external")]

    # changed pages not carried in
    all_pages = json.load(open(os.path.join(ROOT, "spec-source", "all_pages.json")))
    baseline = fields["generatedFrom"]["firstGeneratedAt"][:16]
    done = {p["pageId"] for p in refresh["pages"]} | {a["pageId"] for a in added} | {c["pageId"] for c in changed}
    pending = []
    for p in sorted(all_pages, key=lambda p: p["when"], reverse=True):
        pid = str(p["id"])
        if p["when"][:16] <= baseline or pid in done:
            continue
        pending.append({"pageId": pid, "title": p["title"], "updatedAt": p["when"], "version": p.get("version"),
                        "why": PENDING.get(pid, "Changed since the rules were compiled; not read into them yet."),
                        "whyAr": AR[WHY_AR.get(pid, "other")]})

    out = {
        "$schema": "isit/changes@1",
        "refresh": REFRESH,
        "title": "NPHIES changes published 20 Sep and 13 Oct 2026",
        "baseline": fields["generatedFrom"]["firstGeneratedAt"],
        "appliedAt": refresh["at"],
        "summaryPage": {"pageId": SUMMARY_PAGE, "title": "Segment Description", "updatedAt": "2025-06-02T08:57:21.338Z",
                        "note": "NPHIES moved PID, PV1, DG1 and PR1 to new pages on 2026-09-20 but left this summary page "
                                "as it was. Where the two disagree ISIT applies the milder reading and says so in the "
                                "finding, as it does whenever two published tables disagree.",
                        "noteAr": "نقلت NPHIES مقاطع PID وPV1 وDG1 وPR1 إلى صفحات جديدة في 2026-09-20 وتركت صفحة الملخّص "
                                  "هذه كما هي. حيث تختلف الصفحتان يطبّق ISIT القراءة الأخفّ ويذكر ذلك في النتيجة، كما يفعل "
                                  "كلما اختلف جدولان منشوران."},
        "counts": dict(counts, valueSetsAdded=len(added), valueSetsChanged=len(changed),
                       linksAdded=len(vsrec["bindingsAdded"]), linksRemoved=len(vsrec["bindingsRemoved"]),
                       pending=len(pending)),
        "pages": pages,
        "valueSets": {"added": added, "changed": changed, "empty": empty},
        "notJudged": [dict(x, why=x["why"][:1].upper() + x["why"][1:], whyAr="الرموز المذكورة تنطبق على تحديث الخروج A08 فقط؛ يبقى الفحص بمجموعة القيم، وتُعرض قائمة A08.")
                      for x in vsrec["notJudged"]] + [
            {"pageId": "873300011", "fieldKey": "ZPV1 / ZDG1 / ZPR1",
             "why": "New usage \"C\" (conditional): the condition is a sentence in the guidance, so it is never judged. These "
                    "three segments belong to the A08 discharge update, which is not a structure of its own in ISIT yet, so "
                    "for now their rules are listed here and not applied to messages.",
             "whyAr": "استخدام جديد \"C\" (مشروط): الشرط جملة في الإرشادات، فلا يُحكم عليه. وهذه المقاطع الثلاثة تخص "
                      "تحديث الخروج A08، وليس له في ISIT هيكل خاص به بعد، فقواعدها مذكورة هنا ولا تُطبَّق على الرسائل حاليًا."},
            {"pageId": "873300011", "fieldKey": "ZPV1.49 / Outpatient reason for visit (Subdomain)",
             "why": "The code must come from the subdomain of the domain in ZPV1.48; ISIT checks it is in one of the twelve, not which one.",
             "whyAr": "يجب أن يكون الرمز من المجال الفرعي للمجال المذكور في ZPV1.48؛ يتحقق ISIT أنه في إحدى المجموعات الاثنتي عشرة، لا في أيّها."},
        ],
        "checker": [
            {"change": "A field that cites several value sets takes a code from any of them",
             "why": "ZPV1.49 names twelve value sets (CS-Clinical-OPD1 to OPD12). Judging a code against each one reported "
                    "a valid code as wrong eleven times. A code is now reported only when it is in none of them, and not "
                    "at all when one of the cited sets cannot be checked.",
             "changeAr": "الحقل الذي يستشهد بعدة مجموعات قيم يقبل رمزًا من أيٍّ منها",
             "whyAr": "يذكر ZPV1.49 اثنتي عشرة مجموعة قيم (CS-Clinical-OPD1 إلى OPD12). الحكم على الرمز مقابل كل واحدة "
                      "على حدة كان يعدّ الرمز الصحيح خطأً إحدى عشرة مرة. الآن لا يُبلَّغ عن الرمز إلا إذا لم يكن في أيٍّ منها، "
                      "ولا يُبلَّغ إطلاقًا إذا تعذّر فحص إحدى المجموعات المذكورة."},
        ],
        "pending": pending,
    }
    with open(os.path.join(B, "changes.json"), "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    c = out["counts"]
    print(f"changes.json: {c['pages']} pages, {c['ruleChanges']} rule changes, {c['wordingChanges']} wording, "
          f"{c['rowsAdded']} rows added, {c['rowsRemoved']} removed; {c['valueSetsAdded']} value sets added, "
          f"{c['valueSetsChanged']} changed; {c['pending']} changed pages not in the rules yet")


if __name__ == "__main__":
    main()
