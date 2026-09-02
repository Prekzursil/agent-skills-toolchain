#!/usr/bin/env python3
"""Probe 2: produced-artifact zero + regression bundle (independent entropy path).

Re-runs the scenario live. After the detector control (probe 1), a zero on
produced directories is trusted only if the leaky producer and the credential
bundle still fire. Does not import pattern_scan. Does not print the canary body.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import entropy_scan as E  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0206.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0206-probe2 {msg}")
    return 1


def main() -> int:
    src = (HERE / "entropy_scan.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(n.name.split(".", 1)[0] == "pattern_scan" for n in node.names):
                return fail("entropy_scan.py imports pattern_scan")
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".", 1)[0] == "pattern_scan":
                return fail("entropy_scan.py imports pattern_scan")
    if "SYNTHETIC_NOT_A_CREDENTIAL_TST0206_" in src:
        return fail("entropy_scan.py hard-codes the canary prefix")

    run = S.run_scenario()
    pub = run.public
    agr = pub["agreement"]
    live = pub["live_produced"]
    clean = pub["produced_clean"]
    leaky = pub["produced_leaky"]
    reg = pub["regression_bundle"]
    print(
        json.dumps(
            {
                "probe": "probe2-produced-zero",
                "unit_id": "TST-0206",
                "canary_sha256": pub["canary_sha256"],
                "clean_pattern_canary_hits": clean["pattern_canary_hits"],
                "clean_entropy_canary_hits": clean["entropy_canary_hits"],
                "leaky_pattern_canary_hits": leaky["pattern_canary_hits"],
                "leaky_entropy_canary_hits": leaky["entropy_canary_hits"],
                "live_files_scanned": live["files_scanned"],
                "live_pattern_canary_hits": live["pattern_canary_hits"],
                "live_entropy_canary_hits": live["entropy_canary_hits"],
                "live_liveness": live["enumerator_liveness"],
                "regression_pattern_fired": reg.get("pattern_credential_fired"),
                "regression_entropy_fired": reg.get("entropy_fired"),
                "both_scanners_agree": agr["both_scanners_agree"],
                "entropy_window": E.WINDOW,
                "entropy_min": E.ENTROPY_MIN,
            },
            sort_keys=True,
        )
    )
    if not agr["detector_control"]:
        return fail("detector control not proven in this run; zero is untrusted")
    if clean["pattern_canary_hits"] != 0 or clean["entropy_canary_hits"] != 0:
        return fail("canary leaked into sandbox produced-clean artifacts")
    if leaky["pattern_canary_hits"] < 1 or leaky["entropy_canary_hits"] < 1:
        return fail("leaky producer did not fire both scanners")
    if not live["enumerator_liveness"]:
        return fail(f"enumerator liveness file missing: {live['liveness_path']}")
    if live["files_scanned"] < 1:
        return fail("live produced-artifact scan read zero files")
    if live["pattern_canary_hits"] != 0 or live["entropy_canary_hits"] != 0:
        return fail("canary present in live produced artifact directories")
    if live.get("required_absent"):
        return fail(f"required produced dirs absent: {live['required_absent']}")
    if not reg.get("pattern_credential_fired") or not reg.get("entropy_fired"):
        return fail("regression credential bundle did not fire both scanners")
    if not agr["both_scanners_agree"]:
        return fail("pattern and entropy scanners disagreed")
    if not pub.get("pass"):
        return fail("scenario pass=false")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0206" not in text:
        return fail("sentinel-absent")
    if run.contains_canary(text):
        return fail("receipt contains this run's canary body")
    live_doc = doc.get("live_produced") or {}
    if "pattern_canary_hits" not in live_doc or int(live_doc["pattern_canary_hits"]) != 0:
        return fail("receipt does not record live pattern canary hits = 0")
    if "entropy_canary_hits" not in live_doc or int(live_doc["entropy_canary_hits"]) != 0:
        return fail("receipt does not record live entropy canary hits = 0")
    if doc.get("agreement", {}).get("both_scanners_agree") is not True:
        return fail("receipt agreement.both_scanners_agree is not true")
    print("SUCCESS:TST-0206-probe2 produced artifacts zero canary; regression fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
