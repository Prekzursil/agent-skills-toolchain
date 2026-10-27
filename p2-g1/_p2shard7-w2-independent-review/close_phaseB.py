#!/usr/bin/env python3
"""PHASE B - closure writes for the 10 PASS units of wave-2 shard 7.

Per PASS unit:
  1. receipt.reviewer := schema-conformant independent block (allowed keys only:
     reviewer_id/verdict/independent/fresh_context/vendor/notes/reviewed_at);
     prior reviewer block preserved under top-level 'prior_reviewers' (root
     additionalProperties=true, so this adds no new schema violation);
  2. state stays SUCCESS; sentinel untouched;
  3. UNIT-ARTIFACT-MANIFEST primary row refreshed (bytes=raw size,
     sha256=CRLF->LF normalized) so the registration describes the live bytes;
  4. atomic writes (tempfile + os.replace);
  5. post-write re-verification: parse, sha-vs-manifest, canonical schema
     validation re-run, ALL probes re-run (exit 0 required).
FAIL units (BLD-0044, BLD-0045) are NOT touched by this script.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import validate_artifact  # noqa: E402

PASS_UNITS = {
    "BLD-0043": "command-center/receipts/BLD-0043.json",
    "BLD-0049": "command-center/receipts/BLD-0049.json",
    "BLD-0050": "command-center/receipts/BLD-0050.json",
    "BLD-0058": "command-center/receipts/BLD-0058.json",
    "BLD-0059": "command-center/receipts/BLD-0059.json",
    "BLD-0061": "command-center/receipts/BLD-0061.json",
    "CC-0003": "command-center/receipts/CC-0003.json",
    "CC-0010": "command-center/receipts/CC-0010.json",
    "CC-0019": "command-center/receipts/CC-0019.json",
    "CNF-0070": "command-center/confirmation/CNF-0070-archival-corroboration.json",
}
REVIEWER_ID = "independent-reviewer-shard7-w2-claude-opus-fresh"
DRIFT_NOTE = {
    "BLD-0043": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; role 'schema' outside enum",
    "BLD-0049": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; role 'schema' outside enum",
    "BLD-0050": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; extra 'note' key in an artifacts row",
    "BLD-0058": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; role 'schema' outside enum",
    "BLD-0059": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; role 'schema' outside enum",
    "BLD-0061": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256 (reviewer extra-props cleared by this closure)",
    "CC-0003": "no residual drift: schema-clean before and after this closure",
    "CC-0010": "residual C2 drift: envelope keys absent; receipt self-artifact rows lack bytes/sha256; roles 'protocol'/'schema' outside enum",
    "CC-0019": "residual C2 drift: evidence[].confidence recorded as 0.9 (number) where the class demands the verbal band enum; otherwise envelope-complete",
    "CNF-0070": "residual C2 drift cleared by this closure (reviewer extra-prop removed); artifact envelope-complete",
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def atomic_write(path: Path, doc) -> None:
    raw = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "wb") as fh:
        fh.write(raw)
    os.replace(tmp, path)


def run_probe(script: Path):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cp = subprocess.run([sys.executable, "-B", str(script)], cwd=str(REPO),
                        capture_output=True, text=True, timeout=300, env=env)
    return cp.returncode


def close_unit(uid: str) -> dict:
    rep = {"unit_id": uid, "written": False, "post_write_ok": False, "problems": []}
    rpath = REPO / PASS_UNITS[uid]
    doc = json.loads(rpath.read_bytes().decode("utf-8"))

    prior = doc.get("reviewer")
    priors = doc.get("prior_reviewers") or []
    if isinstance(prior, dict) and prior:
        priors = priors + [dict(prior)]
    doc["prior_reviewers"] = priors
    doc["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "claude-code",
        "notes": ("Independent reviewer closure (wave-2 shard 7). Re-verified off disk, "
                  "trusting nothing from the builder runlog: artifact at the catalog "
                  "output_path exists/non-empty/parses-as-JSON/not-self-blocked; every "
                  "probe script under command-center/p2-wave/probes/" + uid + "/ re-executed "
                  "live by this reviewer, all exit 0; UNIT-ARTIFACT-MANIFEST sha256 "
                  "recomputed (CRLF->LF normalized) matches the live artifact and every "
                  "registered row matches live disk; canonical output_schema validation "
                  "re-run (schema_resolver.validate_artifact). " + DRIFT_NOTE[uid] +
                  ". C2 schema drift for a known catalog id is the receipt_gate census "
                  "class (admitted, visible, non-gating), recorded here rather than folded "
                  "into green. Reviewed " + now_iso() + "."),
        "reviewed_at": now_iso(),
    }
    atomic_write(rpath, doc)
    rep["written"] = True

    # refresh manifest primary row
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_bytes().decode("utf-8"))
    rel = PASS_UNITS[uid].replace("\\", "/")
    hit = False
    for row in man.get("artifacts") or []:
        if str(row.get("path") or "").replace("\\", "/") == rel:
            data = (REPO / rel).read_bytes()
            row["bytes"] = len(data)
            row["sha256"] = norm_sha(data)
            hit = True
    if not hit:
        rep["problems"].append("manifest had no row for " + rel)
        return rep
    atomic_write(man_path, man)

    # post-write re-verification
    doc2 = json.loads((REPO / rel).read_bytes().decode("utf-8"))
    if doc2.get("unit_id") != uid:
        rep["problems"].append("post-write unit_id mismatch")
    if doc2.get("reviewer", {}).get("reviewer_id") != REVIEWER_ID:
        rep["problems"].append("post-write reviewer block missing")
    man2 = json.loads(man_path.read_bytes().decode("utf-8"))
    live = norm_sha((REPO / rel).read_bytes())
    row2 = [r for r in man2["artifacts"] if str(r.get("path")).replace("\\", "/") == rel][0]
    if row2["sha256"] != live:
        rep["problems"].append("post-write manifest sha mismatch")
    errs = validate_artifact(doc2, self_schema(uid))
    rep["post_write_schema_errors"] = len(errs)
    probes = sorted(pdir.glob("probe*.py"))
    rcs = {p.name: run_probe(p) for p in probes}
    rep["post_write_probe_rcs"] = rcs
    if any(rc != 0 for rc in rcs.values()):
        rep["problems"].append("post-write probe failure: %s" % rcs)
    # every manifest row must still match disk after probe re-runs
    for row in man2["artifacts"]:
        ap = REPO / str(row["path"])
        if not ap.is_file() or norm_sha(ap.read_bytes()) != row["sha256"]:
            rep["problems"].append("row drifted post-probe: %s" % row["path"])
    rep["post_write_ok"] = not rep["problems"]
    return rep


def self_schema(uid: str) -> str:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat["work_units"]:
        if u["id"] == uid:
            return u["output_schema"]
    raise KeyError(uid)


def main():
    out = []
    for uid in PASS_UNITS:
        r = close_unit(uid)
        out.append(r)
        print(("OK  " if r["post_write_ok"] else "BAD ") + uid,
              "schema_errs=%s" % r.get("post_write_schema_errors"),
              r.get("problems") or "", flush=True)
    (REPO / "_p2shard7-w2-independent-review" / "close-phaseB.json").write_text(
        json.dumps({"generated_at": now_iso(), "reviewer": REVIEWER_ID, "results": out},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in out if r["post_write_ok"])
    print("PHASE-B: %d/%d post-write clean" % (ok, len(out)))


if __name__ == "__main__":
    main()
