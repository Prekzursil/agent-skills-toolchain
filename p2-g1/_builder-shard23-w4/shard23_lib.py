"""Shard 23 wave-4 builder library: resume/complete WFA-0003..WFA-0056 units.

Contract per unit: catalog entry -> artifact at output_path satisfying the
blessed receipt_core envelope (schema_resolver-resolved) -> live probes
exit 0 -> UNIT-ARTIFACT-MANIFEST.json LF sha256 row -> SUBAGENT-RETURN.json
-> receipt BLOCKED / reviewer-absent (only the independent reviewer closes).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
BUILDER = "shard23 wave-4 builder (resume) 2026-10-26"
PRIOR_NOTE = ("prior builder attempt died mid-flight (host session ended); "
              "artifact content verified against the live contract, not rebuilt")

UNITS = ["WFA-0003", "WFA-0004", "WFA-0005", "WFA-0011", "WFA-0029", "WFA-0030",
         "WFA-0042", "WFA-0048", "WFA-0051", "WFA-0052", "WFA-0053", "WFA-0056"]


def lf_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def lf_sha(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_entry(cat: dict, uid: str) -> dict:
    for u in cat["work_units"]:
        if u.get("id") == uid:
            return u
    raise SystemExit("catalog-missing " + uid)


def dump_json(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def run(cmd: str, timeout: int = 900) -> tuple[int, str]:
    import re
    env = {"PYTHONDONTWRITEBYTECODE": "1", "AST_INTEGRATE_ROOT": str(REPO),
           "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
           "PATH": os.environ.get("PATH", ""),
           "PYTHONPATH": str(REPO)}
    # cmd.exe cannot execute POSIX "VAR=value command" prefixes; move them into
    # the child env so recorded named-probe commands run verbatim (same
    # adaptation as _measure_one_delivered.py).
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    exe = sys.executable.replace("\\", "/")
    if "python3" in cmd:
        cmd = cmd.replace("python3", '"' + exe + '"', 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def fp_of(method: str, command: str) -> str:
    return hashlib.sha256((method + "\x00" + command).encode("utf-8")).hexdigest()[:16]


def probe_cmd(uid: str, script: str) -> str:
    return "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/" + uid + "/" + script


def lr_of(doc: dict) -> dict:
    """Rich content root: extensions.legacy_root when enveloped, else the doc."""
    return doc.get("extensions", {}).get("legacy_root", doc)


# ---------------------------------------------------------------- probes ----

PROBE1_TMPL = '''#!/usr/bin/env python3
"""@@UID@@ probe1 -- builder-side delivery predicate (live, fail-closed).

Checks the measured DELIVERED bar: artifact exists >= min bytes, parses, not
self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, unit_id + completion sentinel
present, schema-valid under the blessed schema_resolver (receipt_core
envelope), evidence pair legal (source+verifier, distinct fingerprints,
confidence on decisive rows), negative controls both-states true, tests PASS,
reviewer block present (probe2 independent recheck), manifest registered with
a live row, downstream consumer executed, report block present. The
receipt_core SUCCESS battery at the RECEIPT level (wave independent reviewer
closure) remains the reviewer's job: the receipt stays BLOCKED/reviewer-absent
(program contract). Fails closed on any builder-side gap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "@@OUT_REL@@"
SENTINEL = @@SENTINEL_JSON@@
UNIT = "@@UID@@"

sys.path.insert(0, str(REPO / "platform" / "lib"))

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:@@UID@@-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 1024, "artifact-under-min-bytes", str(OUT.stat().st_size))
    st = str(doc.get("state") or "").upper()
    chk(st == "SUCCESS", "state-not-success", st)
    chk(str(doc.get("unit_id") or "") == UNIT, "unit-id", str(doc.get("unit_id")))
    chk(SENTINEL in text, "completion-sentinel-absent")
    chk(str(doc.get("sentinel") or "").startswith("SUCCESS:" + UNIT), "sentinel-shape",
        str(doc.get("sentinel"))[:40])
    for req in ("schema_version", "spec_anchor", "min_bytes_threshold", "timestamps", "retry"):
        chk(req in doc, "envelope-field-absent", req)

    from schema_resolver import validator_for
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entry = next(u for u in cat["work_units"] if u.get("id") == UNIT)
    v = validator_for(entry["output_schema"])
    errs = sorted(v.iter_errors(doc), key=lambda e: str(list(e.path)))
    chk(not errs, "schema-invalid", "; ".join(
        str(list(e.path)[:3]) + " " + e.message[:110] for e in errs[:4]))

    ev = doc.get("evidence") or []
    chk(len(ev) >= 2, "evidence-under-minimum", str(len(ev)))
    for i, item in enumerate(ev):
        vv = str(item.get("verdict") or "")
        chk(vv in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"},
            "evidence-verdict-illegal", "[%d]=%r" % (i, vv))
        probes = item.get("probes") or []
        chk(len(probes) >= 1, "evidence[%d]-probes-absent" % i)
        if vv in ("CONFIRMED", "REFUTED"):
            roles = {p.get("role") for p in probes}
            chk("source" in roles and "verifier" in roles,
                "evidence[%d]-role-pair-absent" % i, str(sorted(roles)))
            chk("confidence" in item, "evidence[%d]-confidence-absent" % i)
            ifps = [p.get("fingerprint") for p in probes]
            chk(len(set(ifps)) == len(ifps), "evidence[%d]-fingerprints-not-distinct" % i)

    ncs = doc.get("negative_controls") or []
    chk(len(ncs) >= 1, "controls-absent")
    for i, nc in enumerate(ncs):
        chk(nc.get("fired_on_bad_state") is True, "control[%d]-not-fired-on-bad" % i)
        chk(nc.get("silent_on_good_state") is True, "control[%d]-not-silent-on-good" % i)

    tests = doc.get("tests") or []
    chk(len(tests) >= 2, "tests-under-minimum", str(len(tests)))
    chk(all(t.get("result") == "PASS" for t in tests), "tests-not-all-pass")

    rv = doc.get("reviewer") or {}
    chk(rv.get("verdict") == "PASS", "reviewer-verdict", str(rv.get("verdict")))
    chk(rv.get("independent") is True, "reviewer-not-independent")
    chk(UNIT in str(rv.get("reviewer_id") or ""), "reviewer-id-unanchored")

    man = REPO / "command-center" / "p2-wave" / "probes" / UNIT / "UNIT-ARTIFACT-MANIFEST.json"
    chk(man.is_file(), "manifest-file-absent")
    if man.is_file():
        man_doc = json.loads(man.read_text(encoding="utf-8"))
        rows = [a for a in man_doc.get("artifacts") or []
                if a.get("unit_id") == UNIT
                and str(a.get("path", "")).replace("\\\\", "/") == "@@OUT_REL@@"]
        chk(bool(rows) and rows[0].get("present") is True, "manifest-row-absent")

    dcs = doc.get("downstream_consumers") or []
    chk(len(dcs) >= 1 and all(d.get("executed") and d.get("read_ok") for d in dcs),
        "downstream-consumers-not-executed")

    rep = doc.get("report") or {}
    chk(rep.get("kind") == "@@CLS@@", "report-kind", str(rep.get("kind")))
    chk(len(rep.get("observations") or []) >= 1, "observations-absent")
    chk(len(rep.get("control_ids") or []) >= 1, "control-ids-absent")

    if fails:
        for f in fails[:12]:
            print("FAILED:@@UID@@-probe1 " + f)
        return 1
    print("SUCCESS:@@UID@@-probe1 delivery predicate: parses, state=SUCCESS, schema-valid (blessed resolver), sentinel present, evidence pair legal, controls recorded, manifest row live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

PROBE2_TMPL = '''#!/usr/bin/env python3
"""@@UID@@ probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's headline claims from its own raw rows on a separate
code path (never re-running the original builder logic), runs the live
both-states mutation control, and byte-compares the per-unit manifest
registration against the live artifact (LF-normalized sha256, matching
_measure_one_delivered.py). Fixtures from the prior Linux build are absent on
this worktree; where inputs are absent the re-derivation is from recorded raw
rows only and says so. Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "@@OUT_REL@@"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "@@UID@@" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "@@UID@@"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()


@@REDERIVE_SRC@@


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:@@UID@@-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    L = lr(doc)

    rederive(doc, chk, L)

    # live both-states mutation control: the re-derivation must stay silent on
    # the intact artifact and fire on a mutated headline number.
    good_fails = []
    rederive(doc, lambda ok, label, detail="": None if ok else good_fails.append(label), L)
    chk(not good_fails, "live-control-silent-on-good-failed", ";".join(good_fails[:3]))
    mutant = copy.deepcopy(doc)
    mutate(mutant, L)
    mutant_fails = []
    rederive(mutant, lambda ok, label, detail="": None if ok else mutant_fails.append(label), L)
    chk(bool(mutant_fails), "live-control-did-not-fire-on-bad")

    # claimed control booleans in the artifact must match this live run
    for nc in doc.get("negative_controls") or []:
        if str(nc.get("id", "")).endswith("LIVE-MUTANT"):
            chk(nc.get("fired_on_bad_state") is True, "claimed-live-control-false-fire")
            chk(nc.get("silent_on_good_state") is True, "claimed-live-control-false-silent")

    # manifest byte-compare (LF-normalized, matching _measure_one_delivered.py)
    chk(MANIFEST.is_file(), "manifest-absent")
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live = lf_sha(OUT)
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
        chk(bool(rows), "manifest-row-absent")
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\\\", "/") == "@@OUT_REL@@"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:@@UID@@-probe2 " + f)
        return 1
    print("SUCCESS:@@UID@@-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
