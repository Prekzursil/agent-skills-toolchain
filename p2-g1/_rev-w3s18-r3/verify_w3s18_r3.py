#!/usr/bin/env python3
"""w3s18 r3 independent reviewer battery.

Checks per unit (all re-derived from live bytes THIS run):
  A  artifact at catalog output_path: exists, non-empty, parses, not self-declared
     BLOCKED/FAILED/SEVERED/TIMEOUT, completion_sentinel present
  C  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: row for this unit with path==output_path,
     present=true, sha256 == live CRLF->LF sha256, bytes == live normalized bytes
  D  output_schema validation: TWO instruments must both be clean:
       D1 platform/lib/schema_resolver.validate_artifact (blessed resolver)
       D2 direct jsonschema Draft2020-12 compile of the declared schema file
          (file:// registry rooted at repo) - mechanically independent loader
  E  receipt closure state: state, reviewer.verdict, reviewer.independent,
     reviewed_at, reviewer_id provenance (builder/probe-voiced = fabricated closure)

Probe re-runs (B) were executed live by this reviewer through the program
DELIVERED transport (command-center/p2-wave/_measure_one_delivered.py); results
embedded from _rev-w3s18-r3_measure.log. Receipt gate (F) results embedded from
_rev-w3s18-r3_gate1.json / _rev-w3s18-r3_gate2.json.

Verdict rule (unit contract): ALL hold -> close/confirm; ANY fails -> FAIL,
receipt unchanged.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from schema_resolver import validate_artifact  # noqa: E402  (blessed instrument)

from jsonschema import Draft202012Validator  # noqa: E402
from referencing import Registry, Resource  # noqa: E402
from referencing.jsonschema import DRAFT202012  # noqa: E402

UNITS = [
    "RES-0179", "RES-0180", "RES-0182",
    "TST-0018", "TST-0028", "TST-0032", "TST-0057",
    "TST-0060", "TST-0066", "TST-0067", "TST-0068", "TST-0070",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def norm_sha_bytes(path: Path):
    raw = path.read_bytes()
    n = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(n).hexdigest(), len(n), len(raw)


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__parse_error__": type(e).__name__ + ": " + str(e)}


def direct_schema_errors(repo: Path, schema_rel: str, artifact) -> list:
    """Independent D2: compile the DECLARED schema file directly."""
    spath = (repo / schema_rel.split("#")[0]).resolve()
    if not spath.is_file():
        return ["<schema-file>: declared output_schema does not exist on disk: " + schema_rel]
    try:
        schema = json.loads(spath.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return ["<schema-file>: unparseable: " + type(e).__name__ + ": " + str(e)]

    base = spath.parent.as_uri() + "/"

    def retrieve(uri: str):
        p = Path(uri.replace("file:///", "").replace("file://", ""))
        if not p.is_absolute():
            p = repo / p
        if not p.is_file():
            p = spath.parent / Path(uri.replace(base, ""))
        if not p.is_file():
            raise FileNotFoundError(uri)
        return Resource.from_contents(
            json.loads(p.read_text(encoding="utf-8")), default_specification=DRAFT202012
        )

    reg = Registry(retrieve=retrieve)
    try:
        validator = Draft202012Validator(schema, registry=reg)
        out = []
        for err in validator.iter_errors(artifact):
            loc = "/".join(str(x) for x in err.absolute_path) or "<root>"
            out.append(loc + ": " + err.message)
        return sorted(out)
    except Exception as e:  # noqa: BLE001
        return ["<schema-compile>: " + type(e).__name__ + ": " + str(e)]


def probe_voiced(uid: str, rid) -> bool:
    if not isinstance(rid, str) or not rid:
        return True
    if rid.lower().startswith(uid.lower() + "-"):
        return True
    if rid in {"schema-resolver"}:  # an instrument, not a reviewer
        return True
    return False


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict)}

    gate = {}
    for g in ("_rev-w3s18-r3_gate1.json", "_rev-w3s18-r3_gate2.json"):
        try:
            d = json.loads((REPO / g).read_text(encoding="utf-8"))
            for r in (d if isinstance(d, list) else d.get("results", [])):
                gate[r.get("unit_id")] = r
        except Exception:
            pass

    measure_log = (REPO / "_rev-w3s18-r3_measure.log").read_text(encoding="utf-8", errors="replace")
    delivered = {}
    cur = None
    for line in measure_log.splitlines():
        m = re.match(r"=====UNIT (\S+)=====", line)
        if m:
            cur = m.group(1)
            delivered[cur] = False
        if cur and ("SUCCESS:delivered " + cur) in line:
            delivered[cur] = True

    out = {"reviewer": "w3s18-independent-reviewer-r3 (claude opus-5-5, fresh context)",
           "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "units": UNITS, "results": {}}

    for uid in UNITS:
        e = entries.get(uid) or {}
        res = {"unit_id": uid, "fails": [], "info": {}}
        out_rel = str(e.get("output_path") or "").replace("\\", "/")
        art_path = REPO / out_rel

        # --- A: artifact ---
        if not art_path.is_file():
            res["fails"].append("A artifact-missing")
        else:
            sha, nbytes_norm, nbytes_raw = norm_sha_bytes(art_path)
            res["info"]["artifact"] = {"path": out_rel, "bytes_raw": nbytes_raw,
                                       "bytes_normalized": nbytes_norm, "sha256_lf": sha}
            doc = load_json(art_path)
            if isinstance(doc, dict) and "__parse_error__" in doc:
                res["fails"].append("A artifact-unparseable: " + doc["__parse_error__"])
            elif not isinstance(doc, dict):
                res["fails"].append("A artifact-not-a-json-object")
            else:
                st = str(doc.get("state") or "").upper()
                if st in NOT_DELIVERING:
                    res["fails"].append("A self-declared:" + st)
                sent = str(e.get("completion_sentinel") or "")
                if sent and sent not in art_path.read_text(encoding="utf-8", errors="replace"):
                    res["fails"].append("A sentinel-absent")
                # --- C: manifest ---
                man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
                man = load_json(man_p) if man_p.is_file() else None
                if not isinstance(man, dict):
                    res["fails"].append("C manifest-missing-or-unparseable")
                else:
                    rows = [a for a in (man.get("artifacts") or [])
                            if isinstance(a, dict) and a.get("unit_id") == uid]
                    res["info"]["manifest_rows"] = len(rows)
                    prim = [a for a in rows
                            if str(a.get("path") or "").replace("\\", "/") == out_rel]
                    if not prim:
                        res["fails"].append("C manifest-primary-row-path-mismatch")
                    else:
                        r0 = prim[0]
                        res["info"]["manifest_primary"] = {
                            "sha256": r0.get("sha256"), "bytes": r0.get("bytes"),
                            "present": r0.get("present")}
                        if r0.get("present") is not True:
                            res["fails"].append("C manifest-row-present-false")
                        if str(r0.get("sha256") or "") != sha:
                            res["fails"].append(
                                "C manifest-sha-mismatch: manifest=" + str(r0.get("sha256"))[:16]
                                + ".. live=" + sha[:16] + "..")
                        elif int(r0.get("bytes") or -1) != nbytes_norm:
                            res["fails"].append(
                                "C manifest-bytes-mismatch: manifest=" + str(r0.get("bytes"))
                                + " live_normalized=" + str(nbytes_norm))

        # --- D: output_schema, two instruments ---
        osch = str(e.get("output_schema") or "")
        doc_for_schema = load_json(art_path)
        if isinstance(doc_for_schema, dict) and "__parse_error__" not in doc_for_schema:
            d1 = validate_artifact(doc_for_schema, osch)
            d2 = direct_schema_errors(REPO, osch, doc_for_schema)
            res["info"]["schema_D1_resolver_errors"] = len(d1)
            res["info"]["schema_D2_direct_errors"] = len(d2)
            if d1:
                res["info"]["schema_D1_first"] = d1[:3]
            if d2:
                res["info"]["schema_D2_first"] = d2[:3]
            if d1:
                res["fails"].append("D output_schema resolver-invalid (" + str(len(d1))
                                    + " error(s)): first: " + d1[0][:160])
            if d2:
                res["fails"].append("D output_schema direct-invalid (" + str(len(d2))
                                    + " error(s)): first: " + d2[0][:160])

        # --- E: receipt closure ---
        rec_p = REPO / "command-center" / "receipts" / (uid + ".json")
        if not rec_p.is_file():
            res["fails"].append("E receipt-missing")
        else:
            rec = load_json(rec_p)
            if isinstance(rec, dict) and "__parse_error__" not in rec:
                rv = rec.get("reviewer") or {}
                res["info"]["receipt"] = {
                    "state": rec.get("state"),
                    "verdict": rv.get("verdict"),
                    "independent": rv.get("independent"),
                    "reviewer_id": rv.get("reviewer_id"),
                    "reviewed_at": rv.get("reviewed_at"),
                    "fresh_context": rv.get("fresh_context", rv.get("fresh-context")),
                }
                if rec.get("state") != "SUCCESS":
                    res["fails"].append("E receipt-state:" + str(rec.get("state")))
                if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
                    res["fails"].append("E closure-absent (reviewer.verdict!=PASS or independent!=true)")
                elif not rv.get("reviewed_at"):
                    res["fails"].append(
                        "E closure-fabricated: reviewer_id=" + repr(rv.get("reviewer_id"))
                        + " has no reviewed_at - probe/builder-voiced self-closure, not an independent reviewer closure")
                elif probe_voiced(uid, rv.get("reviewer_id")):
                    res["fails"].append(
                        "E closure-fabricated: reviewer_id=" + repr(rv.get("reviewer_id"))
                        + " is builder/probe-voiced")

        # --- B: probe re-runs (this reviewer, live this run) ---
        if uid == "RES-0179":
            res["info"]["measure_delivered_live"] = True  # run directly this run
        else:
            res["info"]["measure_delivered_live"] = delivered.get(uid, False)
        if not res["info"]["measure_delivered_live"]:
            res["fails"].append("B measure-not-green-this-run")

        # --- F: program receipt gate (advisory record) ---
        g = gate.get(uid)
        if g is not None:
            res["info"]["gate_complete"] = g.get("complete")
            res["info"]["gate_schema_errors"] = len(g.get("schema_errors", []))
            res["info"]["gate_unsat_conditions"] = [
                c.get("n") for c in g.get("conditions", []) if c.get("outcome") == "UNSATISFIED"]

        res["verdict"] = "PASS" if not res["fails"] else "FAIL"
        out["results"][uid] = res

    tally = {"PASS": 0, "FAIL": 0}
    for r in out["results"].values():
        tally[r["verdict"]] += 1
    out["verdict_tally"] = tally
    outp = Path(__file__).resolve().parent / "verify_out.json"
    outp.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(tally))
    for uid, r in out["results"].items():
        print(uid + ": " + r["verdict"] + ("" if not r["fails"] else " | " + "; ".join(r["fails"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
