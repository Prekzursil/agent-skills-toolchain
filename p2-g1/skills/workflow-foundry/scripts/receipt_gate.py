#!/usr/bin/env python3
"""Fan-in RECEIPT gate for a multi-agent fan-out (workflow-foundry L2/L3/L6).

Why this is a script and not a checklist
----------------------------------------
workflow-foundry L7: if a question is answerable by an exact algorithm, WRITE THE
ALGORITHM. "Does every contracted artifact exist, clear its byte floor, and carry its
completion trailer?" is exactly that question. Measured on this estate: 3/3 agents once
returned plausible digests for files that DO NOT EXIST
(rules/common/fan-out-contract.md:70-71). A digest is a claim; only the artifact is a
receipt.

Typed silence is law
--------------------
Every unit gets exactly ONE verdict from this enumerated set (never a bare tag):

    DELIVERED          artifact exists, >= min_bytes, trailer present in the tail
    MISSING            no artifact at the contracted path
    UNDERSIZE          artifact exists but is below the byte floor
    NO-TRAILER         artifact clears the floor but has no completion trailer
    BACKGROUND-RECEIPT the returned digest is a job-id / "check status later" receipt
    NOT-CHECKED        the gate COULD NOT TELL (unreadable, is-a-directory, decode error)

NOT-CHECKED is a first-class outcome. It is never folded into DELIVERED and never
silently dropped. A check that cannot prove it executed says so.

Precedence, highest first (a unit can match several shapes):
    NOT-CHECKED > BACKGROUND-RECEIPT > MISSING > UNDERSIZE > NO-TRAILER > DELIVERED

What a DELIVERED verdict does NOT mean (L3)
-------------------------------------------
The trailer is a string the unit writes ABOUT ITSELF. DELIVERED proves the unit reached
its own writer. It does NOT prove the content is correct. That is rung 3 of 5 on the
L3 ladder; only an independent postcondition probe reaches rung 5. Do not report a
DELIVERED result in rung-5 language.

Advisory by default
-------------------
Exit code is 0 unless --strict is passed. This gate SURFACES; it does not block.

Both-states control (L6)
------------------------
    python receipt_gate.py --self-test

builds throwaway fixtures for every broken shape AND a good one, then asserts the gate
FIRES on the broken states and is SILENT on the good one. It prints both states. A probe
that is silent in the broken state measures nothing
(rules/common/single-signal-verification.md:40). If either half fails it prints
CONTROL-BROKEN and exits 1 -- this gate's verdicts are then uncitable.

Manifest format (JSON)
----------------------
    {
      "defaults": {"min_bytes": 1024, "trailer_template": "UNIT-COMPLETE: {id}"},
      "units": [
        {"id": "u1", "path": "C:/.../artifacts/u1.md"},
        {"id": "u2", "path": "C:/.../artifacts/u2.md", "min_bytes": 4096},
        {"id": "u3", "path": "C:/.../artifacts/u3.md", "trailer": "DONE-u3",
         "digest": "<the text the agent returned, optional>"}
      ]
    }

`digest` is optional. When present it is scanned for the background-receipt phrases that
mark a silently-lost work unit (rules/common/fan-out-contract.md:72,
rules/common/cross-vendor-dispatch.md:12).

Stdlib only. No third-party imports. Windows-safe paths.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Tuple

# --- enumerated vocabularies (never ship a bare tag name -- fan-out-contract.md:12) ----

V_DELIVERED = "DELIVERED"
V_MISSING = "MISSING"
V_UNDERSIZE = "UNDERSIZE"
V_NO_TRAILER = "NO-TRAILER"
V_BACKGROUND = "BACKGROUND-RECEIPT"
V_NOT_CHECKED = "NOT-CHECKED"

UNIT_VERDICTS = (
    V_DELIVERED,
    V_MISSING,
    V_UNDERSIZE,
    V_NO_TRAILER,
    V_BACKGROUND,
    V_NOT_CHECKED,
)

# overall run verdict, in the estate's typed-silence vocabulary
R_CLEAN = "CLEAN"
R_FINDING = "FINDING"
R_NOT_CHECKED = "NOT-CHECKED"
R_DEGRADED = "DEGRADED"

DEFAULT_MIN_BYTES = 1024
DEFAULT_TRAILER_TEMPLATE = "UNIT-COMPLETE: {id}"
DEFAULT_TAIL_BYTES = 4096

# Cheap regex-free rejects that kill the whole fire-and-forget class outright.
BACKGROUND_PHRASES = (
    "started in the background",
    "check /codex:status",
)


def _read_tail(path: str, tail_bytes: int) -> Tuple[str, bool]:
    """Read the last `tail_bytes` of a file as text.

    Returns (text, ok). ok=False means the read FAILED -- distinct from a successful read
    that found nothing. Bounded so a multi-megabyte artifact costs O(tail_bytes), never a
    full forward scan.
    """
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            start = max(0, size - tail_bytes)
            fh.seek(start)
            blob = fh.read()
        return blob.decode("utf-8", errors="replace"), True
    except Exception:
        return "", False


def _has_trailer(text: str, trailer: str) -> bool:
    """The trailer must appear as its own stripped line, not as a substring.

    Substring matching is how a guard matches its own name (workflow-foundry L8: a hook
    matched "todo" inside "todo-surfacer", 3 recorded false fires).
    """
    needle = trailer.strip()
    if not needle:
        return False
    return any(line.strip() == needle for line in text.splitlines())


def classify_unit(unit: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Return one typed verdict for one unit. Never raises."""
    uid = str(unit.get("id", "<no-id>"))
    path = unit.get("path")
    min_bytes = int(unit.get("min_bytes", defaults.get("min_bytes", DEFAULT_MIN_BYTES)))
    trailer_tpl = defaults.get("trailer_template", DEFAULT_TRAILER_TEMPLATE)
    trailer = unit.get("trailer") or trailer_tpl.format(id=uid)
    tail_bytes = int(defaults.get("tail_bytes", DEFAULT_TAIL_BYTES))

    out: Dict[str, Any] = {
        "id": uid,
        "path": path,
        "bytes": 0,
        "min_bytes": min_bytes,
        "trailer": trailer,
    }

    # A unit with no contracted path cannot be judged. Say so; do not assume delivered.
    if not path:
        out["verdict"] = V_NOT_CHECKED
        out["reason"] = "no contracted path in manifest"
        return out

    # Highest precedence after unjudgeable: a background receipt means the real result is
    # unreachable, regardless of what is on disk.
    digest = unit.get("digest")
    if isinstance(digest, str) and digest:
        low = digest.lower()
        hit = next((p for p in BACKGROUND_PHRASES if p in low), None)
        if hit:
            out["verdict"] = V_BACKGROUND
            out["reason"] = "digest contains background-receipt phrase: " + hit
            return out

    try:
        exists = os.path.exists(path)
    except Exception:
        out["verdict"] = V_NOT_CHECKED
        out["reason"] = "path could not be probed"
        return out

    if not exists:
        out["verdict"] = V_MISSING
        out["reason"] = "no artifact at contracted path"
        return out

    if os.path.isdir(path):
        out["verdict"] = V_NOT_CHECKED
        out["reason"] = "contracted path is a directory, not an artifact"
        return out

    try:
        size = os.path.getsize(path)
    except Exception:
        out["verdict"] = V_NOT_CHECKED
        out["reason"] = "size could not be read"
        return out
    out["bytes"] = size

    if size < min_bytes:
        out["verdict"] = V_UNDERSIZE
        out["reason"] = "%d bytes < floor %d" % (size, min_bytes)
        return out

    text, ok = _read_tail(path, tail_bytes)
    if not ok:
        out["verdict"] = V_NOT_CHECKED
        out["reason"] = "artifact tail could not be read"
        return out

    if not _has_trailer(text, trailer):
        out["verdict"] = V_NO_TRAILER
        out["reason"] = "no line equal to %r in last %d bytes" % (trailer, tail_bytes)
        return out

    out["verdict"] = V_DELIVERED
    out["reason"] = "exists, >= floor, trailer present (rung 3 of 5 -- self-declared)"
    return out


def run_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    defaults = manifest.get("defaults") or {}
    units = manifest.get("units") or []
    results = [classify_unit(u, defaults) for u in units]
    counts = {v: 0 for v in UNIT_VERDICTS}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    bad = sum(counts[v] for v in (V_MISSING, V_UNDERSIZE, V_NO_TRAILER, V_BACKGROUND))
    if not units:
        overall = R_NOT_CHECKED  # an empty manifest measures nothing; it is not CLEAN
    elif bad:
        overall = R_FINDING
    elif counts[V_NOT_CHECKED]:
        overall = R_NOT_CHECKED
    else:
        overall = R_CLEAN

    return {"overall": overall, "counts": counts, "units": results}


def _print_report(report: Dict[str, Any]) -> None:
    print("RECEIPT-GATE %s" % report["overall"])
    c = report["counts"]
    print(
        "  units=%d delivered=%d missing=%d undersize=%d no-trailer=%d background=%d not-checked=%d"
        % (
            len(report["units"]),
            c[V_DELIVERED],
            c[V_MISSING],
            c[V_UNDERSIZE],
            c[V_NO_TRAILER],
            c[V_BACKGROUND],
            c[V_NOT_CHECKED],
        )
    )
    for r in report["units"]:
        if r["verdict"] == V_DELIVERED:
            continue
        print("  %-18s %-24s %s" % (r["verdict"], r["id"], r["reason"]))
    if report["overall"] == R_CLEAN:
        print("  all contracted artifacts present at rung 3 of 5 (self-declared).")
        print(
            "  L3: this does NOT prove content. Run an independent postcondition probe."
        )


# --------------------------- both-states control (L6) ---------------------------------


def _write(path: str, body: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)


def self_test() -> int:
    """Prove the gate FIRES in the broken state and is SILENT in the good state.

    A probe that is silent in both states measures nothing. If this prints
    CONTROL-BROKEN, no verdict from this gate may be cited.
    """
    filler = "x" * 2000
    expectations: List[Tuple[str, str]] = []
    ok = True

    with tempfile.TemporaryDirectory(prefix="receipt-gate-selftest-") as tmp:
        good = os.path.join(tmp, "good.md")
        _write(good, filler + "\nUNIT-COMPLETE: good\n")

        undersize = os.path.join(tmp, "undersize.md")
        _write(undersize, "tiny\nUNIT-COMPLETE: undersize\n")

        notrailer = os.path.join(tmp, "notrailer.md")
        _write(notrailer, filler + "\nfinished I promise\n")

        # substring-but-not-a-line: proves _has_trailer is not a naive `in` test (L8)
        substring = os.path.join(tmp, "substring.md")
        _write(substring, filler + "\nsee UNIT-COMPLETE: substring for details\n")

        isdir = os.path.join(tmp, "isdir")
        os.makedirs(isdir)

        manifest = {
            "defaults": {"min_bytes": 1024, "trailer_template": "UNIT-COMPLETE: {id}"},
            "units": [
                {"id": "good", "path": good},
                {"id": "missing", "path": os.path.join(tmp, "nope.md")},
                {"id": "undersize", "path": undersize},
                {"id": "notrailer", "path": notrailer},
                {"id": "substring", "path": substring},
                {"id": "isdir", "path": isdir},
                {
                    "id": "background",
                    "path": good,
                    "trailer": "UNIT-COMPLETE: good",
                    "digest": "Started in the background as task-91ab. Check /codex:status",
                },
            ],
        }
        expectations = [
            ("good", V_DELIVERED),
            ("missing", V_MISSING),
            ("undersize", V_UNDERSIZE),
            ("notrailer", V_NO_TRAILER),
            ("substring", V_NO_TRAILER),
            ("isdir", V_NOT_CHECKED),
            ("background", V_BACKGROUND),
        ]

        report = run_manifest(manifest)
        got = {r["id"]: r["verdict"] for r in report["units"]}

        print("--- BOTH-STATES CONTROL (receipt_gate) ---")
        print("KNOWN-BROKEN states -- the gate MUST fire on each:")
        for uid, want in expectations:
            if want == V_DELIVERED:
                continue
            have = got.get(uid)
            mark = "fires" if have == want else "SILENT/WRONG"
            if have != want:
                ok = False
            print("  %-12s expected=%-18s got=%-18s %s" % (uid, want, have, mark))

        print("KNOWN-GOOD state -- the gate MUST be silent:")
        have = got.get("good")
        if have != V_DELIVERED:
            ok = False
        print(
            "  %-12s expected=%-18s got=%-18s %s"
            % (
                "good",
                V_DELIVERED,
                have,
                "silent" if have == V_DELIVERED else "FALSE POSITIVE",
            )
        )

    if ok:
        print(
            "CONTROL-OK  the gate fires in the broken state and is silent in the good state."
        )
        return 0
    print("CONTROL-BROKEN  this gate measures nothing; its verdicts may not be cited.")
    return 1


# ------------------------------------ cli ---------------------------------------------


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Fan-in receipt gate: Test-Path every contracted output BEFORE reading any digest."
    )
    ap.add_argument("--manifest", help="path to the units manifest JSON")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 unless every unit is DELIVERED (default is advisory, exit 0)",
    )
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="run the both-states control and exit (L6)",
    )
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.manifest:
        ap.error("--manifest is required (or pass --self-test)")

    try:
        with open(args.manifest, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except Exception as exc:
        # DEGRADED, not CLEAN: we could not even read the contract.
        print("RECEIPT-GATE %s  manifest unreadable: %s" % (R_DEGRADED, exc))
        return 1 if args.strict else 0

    report = run_manifest(manifest)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)

    if args.strict and report["overall"] != R_CLEAN:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
