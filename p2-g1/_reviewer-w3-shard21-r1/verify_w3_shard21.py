#!/usr/bin/env python3
"""Wave-3 shard-21 INDEPENDENT REVIEWER - phase A (read-only verification).

12 units: TST-0151 0155 0158 0161 0162 0163 0164 0165 0166 0168 0169 0171.
Checks per unit:
  1 catalog_entry_present
  2 artifact_exists_nonempty_parses
  3 not_self_declared_BLOCKED_or_FAILED
  4 manifest_primary_sha_match (+bytes +path; ALL rows vs live disk)
  5 live_probes_exit0 (re-run from repo root, python -B; mutation diff)
  6 output_schema_valid (TWO transports: schema_resolver.validate_artifact;
    raw Draft202012 on independently-resolved physical fragment)
  7 closure facts (current state + reviewer block)
Writes phaseA-verdicts.json next to this script. No writes to reviewed artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

REPO = Path.home() / "p2-g1"
UNITS = ["TST-0151", "TST-0155", "TST-0158", "TST-0161", "TST-0162",
         "TST-0163", "TST-0164", "TST-0165", "TST-0166", "TST-0168",
         "TST-0169", "TST-0171"]
OUT = Path(__file__).resolve().parent / "phaseA-verdicts.json"
PY = sys.executable
sys.path.insert(0, str(REPO / "platform" / "lib"))


def digest_lf(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_raw(path):
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path):
    return json.loads(path.read_bytes().decode("utf-8"))


def check_not_self_blocked(rec, uid, raw_text):
    probs = []
    state = rec.get("state")
    if state in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT"):
        probs.append("state=" + str(state))
    for pat in (r"FAILED:" + re.escape(uid) + r"\b", r"BLOCKED:" + re.escape(uid) + r"\b"):
        m = re.search(pat, raw_text)
        if m:
            probs.append("sentinel-literal " + repr(m.group(0)) + " in receipt body")
    return probs


def independent_fragment_validator(declared, artifact):
    """Transport 2: my own disk-only ref walk (independent of schema_resolver)."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    m = re.search(r"(command-center/schema/.+?)(?:#(.+))?$", declared)
    shim_rel, frag = m.group(1), (m.group(2) or "")
    shim = load_json(REPO / shim_rel)

    def read_abs(p):
        return load_json(Path(p))

    def read_repo(rel):
        return load_json(REPO / rel)

    def deref_doc(doc, doc_loaded):
        ref = doc.get("$ref")
        if not ref:
            return doc
        if ref.startswith("#/"):
            node = doc_loaded
            for part in ref.lstrip("#/").split("/"):
                node = node[part]
            return deref_doc(node, doc_loaded)
        if "artifact-class-profiles.schema.json" in ref:
            d = read_repo("platform/schema/artifact-class-profiles.schema.json")
            if "#" in ref:
                node = d
                for part in ref.split("#", 1)[1].lstrip("#/").split("/"):
                    node = node[part]
                return deref_doc(node, d)
            return deref_doc(d, d)
        if ref.startswith("file:"):
            p = urlparse(ref).path
            if re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
            d = read_abs(unquote(p))
            if "#" in ref:
                node = d
                for part in ref.split("#", 1)[1].lstrip("#/").split("/"):
                    node = node[part]
                return deref_doc(node, d)
            return deref_doc(d, d)
        raise RuntimeError("unhandled ref " + repr(ref))

    node = shim
    if frag:
        for part in frag.lstrip("#/").split("/"):
            node = node[part]
    schema = deref_doc(node, shim)

    def retrieve(uri):
        raw = uri.split("#", 1)[0]
        if raw.startswith("file:"):
            p = urlparse(raw).path
            if re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
            return Resource.from_contents(load_json(Path(unquote(p))),
                                          default_specification=DRAFT202012)
        posix = raw.replace("\\", "/")
        mm = re.search(r"/(platform/schema/|command-center/schema/)(.+)$", posix)
        if mm:
            return Resource.from_contents(load_json(REPO / mm.group(1) / mm.group(2)),
                                          default_specification=DRAFT202012)
        raise RuntimeError("unhandled retrieval " + repr(uri))

    reg = Registry(retrieve=retrieve)
    v = Draft202012Validator(schema, registry=reg)
    errs = []
    for e in v.iter_errors(artifact):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(loc + ": " + e.message)
    return errs


def main():
    t0 = time.time()
    cat = load_json(REPO / "command-center/WORK-UNIT-CATALOG.json")
    catalog = {u["id"]: u for u in cat["work_units"]}

    from schema_resolver import validate_artifact as sr_validate
    from schema_resolver import resolve as sr_resolve

    results = {}
    for uid in UNITS:
        r = {"unit": uid}
        u = catalog.get(uid)
        r["catalog_entry_present"] = u is not None
        if u is None:
            results[uid] = r
            print("[" + uid + "] NO CATALOG ENTRY", flush=True)
            continue
        out_rel = u["output_path"].replace("\\", "/")
        r["output_path"] = out_rel
        r["output_schema"] = u["output_schema"]
        art_path = REPO / out_rel

        if not art_path.is_file():
            r["artifact_exists_nonempty_parses"] = False
            r["artifact_missing"] = True
            results[uid] = r
            print("[" + uid + "] ARTIFACT MISSING", flush=True)
            continue
        raw_bytes = art_path.read_bytes()
        ok = len(raw_bytes) > 0
        parse_err = None
        rec = None
        try:
            rec = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            ok = False
            parse_err = str(e)
        r["artifact_exists_nonempty_parses"] = ok
        r["artifact_parse_error"] = parse_err
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        r["self_blocked_problems"] = (check_not_self_blocked(rec, uid, raw_text)
                                      if rec is not None else ["unparsed"])

        man_rel = "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json"
        man_path = REPO / man_rel
        r["unit_manifest_present"] = man_path.is_file()
        row_checks = {"primary": None, "drift": []}
        if man_path.is_file():
            man = load_json(man_path)
            rows = man.get("artifacts") or []
            prim = [a for a in rows
                    if a.get("role") == "primary"
                    or a.get("path", "").replace("\\", "/") == out_rel]
            r["primary_row_present"] = bool(prim)
            if prim:
                a = prim[0]
                sha_lf, n_lf = digest_lf(art_path)
                sha_raw, n_raw = digest_raw(art_path)
                row_checks["primary"] = {
                    "manifest_sha": a.get("sha256"), "manifest_bytes": a.get("bytes"),
                    "live_sha_lf": sha_lf, "live_bytes_lf": n_lf,
                    "live_sha_raw": sha_raw, "live_bytes_raw": n_raw,
                    "sha_match": a.get("sha256") in (sha_lf, sha_raw),
                    "bytes_match_lf": a.get("bytes") == n_lf,
                    "bytes_match_raw": a.get("bytes") == n_raw,
                }
            for a in rows:
                rel = str(a.get("path") or "").replace("\\", "/")
                f = REPO / rel
                if not f.is_file():
                    row_checks["drift"].append({"path": rel, "problem": "absent"})
                    continue
                sha_lf, n_lf = digest_lf(f)
                sha_raw, n_raw = digest_raw(f)
                if a.get("sha256") not in (sha_lf, sha_raw):
                    row_checks["drift"].append({"path": rel, "problem": "sha-mismatch",
                                                "manifest": a.get("sha256"),
                                                "live_lf": sha_lf, "live_raw": sha_raw})
                elif a.get("bytes") not in (n_lf, n_raw):
                    row_checks["drift"].append({"path": rel, "problem": "bytes-mismatch",
                                                "manifest": a.get("bytes"),
                                                "live_lf": n_lf, "live_raw": n_raw})
        r["manifest_row_checks"] = row_checks

        probe_dir = REPO / ("command-center/p2-wave/probes/" + uid)
        scripts = []
        if probe_dir.is_dir():
            named = []
            ret_path = probe_dir / "SUBAGENT-RETURN.json"
            if ret_path.is_file():
                try:
                    named = [p.get("command", "") for p in load_json(ret_path).get("named_probes", [])]
                except Exception:
                    named = []
            named_files = []
            esc = re.escape(uid)
            for c in named:
                mm = re.search(r"(command-center/p2-wave/probes/" + esc + r"/[\w.\-]+\.py)", c)
                if mm:
                    named_files.append(mm.group(1))
            allp = sorted(probe_dir.glob("probe*.py")) + sorted(probe_dir.glob("run_probes.py"))
            rels = [str(p.relative_to(REPO)).replace("\\", "/") for p in allp]
            ordered = [x for x in named_files if x in rels] + [x for x in rels if x not in named_files]
            scripts = ordered
        pre_sha = digest_lf(art_path)[0]
        probe_results = {}
        for s in scripts:
            t1 = time.time()
            try:
                p = subprocess.run([PY, "-B", s], cwd=str(REPO), capture_output=True,
                                   text=True, timeout=900,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                probe_results[s] = {"exit": p.returncode, "secs": round(time.time() - t1, 1),
                                    "tail": (p.stdout or p.stderr or "")[-200:].replace("\n", " | ")}
            except subprocess.TimeoutExpired:
                probe_results[s] = {"exit": "TIMEOUT", "secs": round(time.time() - t1, 1)}
        post_sha = digest_lf(art_path)[0]
        r["live_probes"] = probe_results
        r["all_probes_exit0"] = bool(scripts) and all(v["exit"] == 0 for v in probe_results.values())
        r["receipt_mutated_by_battery"] = pre_sha != post_sha
        r["receipt_sha_before_battery"] = pre_sha
        r["receipt_sha_after_battery"] = post_sha

        if rec is not None:
            rec_now = load_json(art_path)
            try:
                errs1 = sr_validate(rec_now, u["output_schema"])
            except Exception as e:
                errs1 = ["transport1-exception: " + str(e)]
            try:
                errs2 = independent_fragment_validator(u["output_schema"], rec_now)
            except Exception as e:
                errs2 = ["transport2-exception: " + str(e)]
            r["schema_t1_errors"] = errs1[:6]
            r["schema_t1_error_count"] = len(errs1)
            r["schema_t2_errors"] = errs2[:6]
            r["schema_t2_error_count"] = len(errs2)
            r["output_schema_valid"] = (len(errs1) == 0 and len(errs2) == 0)
            try:
                rs = sr_resolve(u["output_schema"])
                r["resolved_physical"] = rs.as_dict()
            except Exception as e:
                r["resolved_physical"] = {"error": str(e)}
        else:
            r["output_schema_valid"] = False

        if rec is not None:
            rev = rec.get("reviewer")
            r["current_state"] = rec.get("state")
            r["current_reviewer"] = rev
            r["has_valid_pass_closure"] = bool(
                rec.get("state") == "SUCCESS" and isinstance(rev, dict)
                and rev.get("verdict") == "PASS" and rev.get("independent") is True)
        results[uid] = r
        print("[" + uid + "] probes=" + str(len(scripts)) +
              " t=" + str(round(time.time() - t0)) + "s" +
              " T1=" + str(r.get("schema_t1_error_count")) +
              " T2=" + str(r.get("schema_t2_error_count")) +
              " probes_ok=" + str(r.get("all_probes_exit0")) +
              " selfblock=" + json.dumps(r.get("self_blocked_problems")) +
              " rowdrift=" + str(len(row_checks["drift"])) +
              " mutated=" + str(r.get("receipt_mutated_by_battery")), flush=True)

    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("WROTE " + str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
