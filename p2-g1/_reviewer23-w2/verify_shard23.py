#!/usr/bin/env python3
"""Independent reviewer harness -- P2 wave 2 shard 23 (12 units, TST-0113..TST-0144).

Adversarially verifies each unit per the DELIVERED contract:
  1. receipt at catalog output_path exists / non-empty / parses / not self-declared BLOCKED|FAILED
  2. live probes re-run by THIS reviewer, exit 0 required
  3. probes/<id>/UNIT-ARTIFACT-MANIFEST.json sha256 rows recomputed (CRLF->LF) and matched
  4. receipt validated against the catalog output_schema
  5. closure shape: state=SUCCESS requires reviewer.verdict=PASS + independent=true
Fail-closed: any failed check -> unit verdict FAIL.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "TST-0113", "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137",
    "TST-0138", "TST-0139", "TST-0141", "TST-0142", "TST-0143", "TST-0144",
]
ENTRIES = REPO / "_p2shard23-w2-entries.json"
PROBES_ROOT = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 180


def lf_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_bytes(p: Path) -> int:
    return p.stat().st_size


def load_schema(ref: str):
    """output_schema: '<repo-rel path>' or '<repo-rel path>#/$defs/<name>'."""
    filepart, _, pointer = ref.partition("#")
    spath = REPO / filepart
    with open(spath, encoding="utf-8") as f:
        schema = json.load(f)
    if pointer:
        node = schema
        for tok in pointer.lstrip("#/").split("/"):
            tok = tok.replace("~1", "/").replace("~0", "~")
            node = node[tok]
        # keep root schema as resolution base so sibling $refs resolve
        schema = {**schema, **node} if "$ref" in node or "properties" in node else node
        if isinstance(node, dict) and "$ref" in node and "properties" not in node and "required" not in node and "type" not in node:
            # pure $ref passthrough: use node but resolve against root store
            merged = dict(schema)
            merged.pop("$ref", None)
            merged["$ref"] = node["$ref"]
            schema = merged
    return schema


def verify_unit(uid: str, entry: dict) -> dict:
    res = {"id": uid, "checks": [], "probe_runs": [], "verdict": "PASS"}

    def chk(name: str, ok: bool, detail: str = "") -> None:
        res["checks"].append({"check": name, "ok": bool(ok), "detail": detail[:400]})
        if not ok:
            res["verdict"] = "FAIL"

    # --- 1. receipt delivery predicate (reviewer's own, not the builder's) ---
    out_rel = str(entry.get("output_path") or "").replace("\\", "/")
    receipt = REPO / out_rel
    chk("receipt-exists", receipt.is_file(), out_rel)
    if not receipt.is_file():
        return res
    size = receipt.stat().st_size
    chk("receipt-nonempty", size > 0, "%d bytes" % size)
    try:
        with open(receipt, encoding="utf-8") as f:
            text = f.read()
        doc = json.loads(text)
        chk("receipt-parses", True, "%d bytes" % size)
    except Exception as exc:
        chk("receipt-parses", False, type(exc).__name__)
        return res
    state = str(doc.get("state") or "").upper()
    chk("not-self-blocked-failed", state not in NOT_DELIVERING, state)
    chk("state-success", state == "SUCCESS", state)
    uid_field = str(doc.get("unit_id") or doc.get("id") or "")
    chk("unit-id-matches", uid_field == uid, uid_field)
    chk("sentinel-present", ("SUCCESS:" + uid) in text, entry.get("completion_sentinel", ""))
    rev = doc.get("reviewer") or {}
    chk("closure-reviewer-pass", str(rev.get("verdict") or "").upper() in ("PASS",), json.dumps(rev.get("verdict")))
    chk("closure-independent", rev.get("independent") is True, json.dumps(rev.get("independent")))

    # --- 2. live probe re-run (this reviewer, fresh processes) ---
    pdir = PROBES_ROOT / uid
    probes = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
    chk("probe-scripts-present", len(probes) >= 2, "%d found" % len(probes))
    for probe in probes:
        t0 = time.monotonic()
        try:
            run = subprocess.run(
                [sys.executable, "-I", str(probe)],
                cwd=str(REPO), capture_output=True, text=True,
                errors="replace", timeout=PROBE_TIMEOUT,
            )
            out = (run.stdout or "") + (run.stderr or "")
            tail = out.strip().splitlines()[-1] if out.strip() else "<no output>"
            chk("probe-run-exit0:" + probe.name, run.returncode == 0,
                "rc=%d tail=%s" % (run.returncode, tail[:200]))
            res["probe_runs"].append({
                "probe": probe.name, "rc": run.returncode,
                "tail": tail[:300], "secs": round(time.monotonic() - t0, 1),
            })
        except subprocess.TimeoutExpired:
            chk("probe-run-exit0:" + probe.name, False, "timeout>%ds" % PROBE_TIMEOUT)
            res["probe_runs"].append({"probe": probe.name, "rc": "timeout"})

    # --- 3. manifest sha256 rows (CRLF->LF normalized) ---
    mpath = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    chk("manifest-exists", mpath.is_file(), str(mpath))
    if mpath.is_file():
        try:
            with open(mpath, encoding="utf-8") as f:
                man = json.load(f)
            rows = man.get("artifacts") or []
            chk("manifest-nonempty", len(rows) > 0, "%d rows" % len(rows))
            primary_seen = False
            for row in rows:
                rp = str(row.get("path") or "").replace("\\", "/")
                target = REPO / rp
                role = str(row.get("role") or "")
                if role == "primary":
                    primary_seen = True
                    chk("manifest-primary-is-receipt", rp == out_rel, rp)
                if not target.is_file():
                    chk("manifest-row-exists:" + role, False, rp)
                    continue
                live = lf_sha256(target)
                recd = str(row.get("sha256") or "").lower()
                chk("manifest-sha-match:%s:%s" % (role, Path(rp).name),
                    live == recd, "live=%s recd=%s" % (live[:16], recd[:16]))
            chk("manifest-has-primary", primary_seen, "")
        except Exception as exc:
            chk("manifest-parse", False, type(exc).__name__)

    # --- 4. output_schema validation ---
    schema_ref = str(entry.get("output_schema") or "")
    try:
        schema = load_schema(schema_ref)
        Draft202012Validator.check_schema(schema)
        errs = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
        chk("output-schema-valid", not errs,
            "; ".join("%s: %s" % ("/".join(map(str, e.absolute_path)) or "<root>", e.message) for e in errs[:5]))
    except Exception as exc:
        chk("output-schema-valid", False, "%s: %s" % (type(exc).__name__, str(exc)[:200]))

    return res


def main() -> int:
    with open(ENTRIES, encoding="utf-8") as f:
        entries = json.load(f)
    all_res = []
    for uid in UNITS:
        entry = entries.get(uid)
        if entry is None:
            all_res.append({"id": uid, "verdict": "FAIL",
                            "checks": [{"check": "catalog-entry", "ok": False, "detail": "absent from shard entries"}]})
            continue
        r = verify_unit(uid, entry)
        all_res.append(r)
        print("%s -> %s" % (uid, r["verdict"]))
        for c in r["checks"]:
            if not c["ok"]:
                print("   FAIL %s: %s" % (c["check"], c["detail"]))
        for p in r.get("probe_runs", []):
            print("   probe %s rc=%s %ss | %s" % (p["probe"], p["rc"], p.get("secs", "?"), p.get("tail", "")[:120]))
        sys.stdout.flush()
    outp = REPO / "_reviewer23-w2" / "verification-results.json"
    with open(outp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"reviewer": "independent-reviewer-w2-shard23", "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "results": all_res}, f, indent=1)
    passed = sum(1 for r in all_res if r["verdict"] == "PASS")
    print("SUMMARY: %d/%d PASS; results -> %s" % (passed, len(all_res), outp))
    return 0 if passed == len(all_res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
