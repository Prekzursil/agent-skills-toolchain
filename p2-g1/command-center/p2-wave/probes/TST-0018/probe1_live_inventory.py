#!/usr/bin/env python3
"""TST-0018 probe1: live re-derivation of the silent-in-both-states census.

Re-runs the receipt census arithmetic through the scanner, checks live disk
presence of every checked detector, and re-runs the named inert detector
(plugin/hook_fire_probe.py:filesystem_only_verdict) LIVE against a genuinely
firing good fixture and a genuinely dead broken fixture.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center" / "receipts" / "TST-0018.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scanner  # noqa: E402

HOOK_PROBE = REPO / "tools" / "plugin" / "hook_fire_probe.py"

GOOD_HOOKS = {
    "hooks": {
        "PreToolUse": [
            {"id": "hook.pre-tool", "hooks": [{"command": "scripts/emit_sentinel.py"}]}
        ]
    }
}
GOOD_EMITTER = (
    "import os, pathlib\n"
    "p = pathlib.Path(os.environ['HOOK_FIRE_SENTINEL_PATH'])\n"
    "p.write_text('HOOK_FIRED ' + os.environ['HOOK_FIRE_NONCE'])\n"
)
BROKEN_EMITTER = "import sys\nsys.exit(1)\n"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_fixture(root: Path, emitter: str) -> Path:
    cfg = root / "cfg"
    (cfg / "scripts").mkdir(parents=True)
    (cfg / "hooks.json").write_text(json.dumps(GOOD_HOOKS), encoding="utf-8")
    (cfg / "scripts" / "emit_sentinel.py").write_text(emitter, encoding="utf-8")
    return cfg


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    res = scanner.scan(receipt.get("rows") or [])
    counts = res["counts"]
    check("scanner-recompute-matches-receipt-counts", counts == receipt.get("counts"),
          {"live": counts, "recorded": receipt.get("counts")})
    check("census-arithmetic",
          counts["valid"] + counts["inert"] == counts["checked"]
          and counts["checked"] + counts["not_checked"] == counts["inventory"],
          "valid+inert=checked; checked+not_checked=inventory")
    check("inert-named-not-summarised", res["inert"] == receipt.get("inert"),
          {"live_inert": res["inert"], "recorded_inert": receipt.get("inert")})
    check("no-all-clean-claim",
          receipt.get("all_clean_claim") is False
          and receipt.get("identical_outputs_reported_as_inert") is True,
          "all_clean_claim=false; identical outputs reported as INERT")

    enum = receipt.get("enumerator") or {}
    ids = set(enum.get("ids") or [])
    union = (set(receipt.get("valid") or []) | set(receipt.get("inert") or [])
             | set(receipt.get("not_checked") or []))
    check("enumerator-covers-partition",
          len(ids) == enum.get("count") == 105 and union <= ids and len(union) == 105,
          {"enumerator_count": enum.get("count"), "union_size": len(union),
           "ids_subset": union <= ids})

    missing = []
    for det in (receipt.get("valid") or []) + (receipt.get("inert") or []):
        rel, sym = det.split(":", 1)
        path = REPO / "tools" / rel
        if not path.is_file():
            missing.append(det + ":file")
            continue
        if "def " + sym not in path.read_text(encoding="utf-8"):
            missing.append(det + ":symbol")
    check("checked-detectors-present-on-disk", not missing,
          {"checked": 11, "missing": missing})

    inert_named = (receipt.get("inert") or []) == ["plugin/hook_fire_probe.py:filesystem_only_verdict"]
    check("receipt-names-exactly-the-shipped-inert", inert_named, receipt.get("inert"))
    inert_row = next(r for r in receipt["rows"]
                     if r.get("detector_id") == "plugin/hook_fire_probe.py:filesystem_only_verdict")
    check("recorded-inert-row-identical-sha",
          inert_row.get("good_sha256") == inert_row.get("broken_sha256")
          and inert_row.get("verdict") == "IDENTICAL",
          {"good_sha": str(inert_row.get("good_sha256"))[:16],
           "broken_sha": str(inert_row.get("broken_sha256"))[:16]})

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        mod = load_module(HOOK_PROBE, "hook_fire_probe_live")
        good_cfg = make_fixture(tmp / "good", GOOD_EMITTER)
        broken_cfg = make_fixture(tmp / "broken", BROKEN_EMITTER)
        fs_good = mod.filesystem_only_verdict(good_cfg)
        fs_broken = mod.filesystem_only_verdict(broken_cfg)
        run_good = mod.run_probe(good_cfg)
        run_broken = mod.run_probe(broken_cfg)
        check("live-inert-reproduced-identical-both-states",
              fs_good == fs_broken == "FIRED",
              {"good": fs_good, "broken": fs_broken})
        check("live-control-two-state-detector-differs",
              run_good.verdict == "FIRED" and run_broken.verdict == "NOT-FIRED",
              {"good": run_good.verdict, "good_sentinel": run_good.sentinel_observed,
               "broken": run_broken.verdict, "broken_sentinel": run_broken.sentinel_observed})
        live_sha = scanner.sha256_canonical({"fired": True, "payload": fs_good})
        check("live-sha-matches-recorded-inert-sha",
              live_sha == inert_row.get("good_sha256"),
              {"live": live_sha, "recorded": inert_row.get("good_sha256"),
               "shape": "fired+payload as recorded"})

    out = {"probe": "probe1-live-inventory", "unit_id": "TST-0018", "pass": not red,
           "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
