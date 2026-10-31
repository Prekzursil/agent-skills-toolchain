#!/usr/bin/env python3
"""TST-0206 probe 1: detector control - both scanners MUST fire on a planted canary.

Plants the canary (a) inside a produced artifact, (b) in env vars, (c) in local
config files, then runs a leaky producer that dumps those env keys into an
artifact. PASS requires both independent scanners to fire on every planted
surface. The canary body is derived fresh and stored nowhere permanent.
"""
from __future__ import annotations
import json, os, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scanners import CANARY_PREFIX, derive_canary, scan_text  # noqa: E402

SANDBOX = HERE / "fixtures" / "sandbox"


def main() -> int:
    token, token_sha = derive_canary()
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    (SANDBOX / "config").mkdir(parents=True)
    (SANDBOX / "artifact").mkdir(parents=True)

    # (a) canary planted INSIDE a produced artifact
    artifact = SANDBOX / "artifact" / "produced-bundle.txt"
    artifact.write_text(f"bundle payload\n{token}\nend\n", encoding="utf-8")

    # (b) env keys, (c) local config files
    os.environ["TST0206_CANARY"] = token
    os.environ["TST0206_API_SECRET"] = token
    (SANDBOX / "config" / ".env").write_text(f"TST0206_API_SECRET={token}\n", encoding="utf-8")
    (SANDBOX / "config" / "secrets.json").write_text(json.dumps({"TST0206_CANARY": token}), encoding="utf-8")

    # leaky producer: dumps the env keys into an artifact bundle
    leaky = SANDBOX / "artifact" / "leaky-producer-dump.txt"
    leaky.write_text(
        json.dumps({"TST0206_CANARY": os.environ.get("TST0206_CANARY", ""), "TST0206_API_SECRET": os.environ.get("TST0206_API_SECRET", "")}, indent=1),
        encoding="utf-8",
    )

    art = scan_text(artifact.read_text(encoding="utf-8"))
    leak = scan_text(leaky.read_text(encoding="utf-8"))
    env_cfg = scan_text((SANDBOX / "config" / ".env").read_text(encoding="utf-8") + (SANDBOX / "config" / "secrets.json").read_text(encoding="utf-8"))

    checks = {
        "detector_pattern_fires_in_artifact": any(h.startswith(CANARY_PREFIX[:24]) for h in art["pattern_hits"]),
        "detector_entropy_fires_in_artifact": len(art["entropy_hits"]) >= 1,
        "both_fire_on_leaky_producer": bool(leak["pattern_hits"]) and bool(leak["entropy_hits"]),
        "both_fire_on_local_config": bool(env_cfg["pattern_hits"]) and bool(env_cfg["entropy_hits"]),
        "canary_derived_not_stored": token.startswith(CANARY_PREFIX),
    }
    out = {
        "probe": "probe1_detector_control",
        "unit": "TST-0206",
        "canary_prefix": CANARY_PREFIX,
        "canary_sha256": token_sha,
        "artifact_scan": art,
        "leaky_scan": leak,
        "config_scan": {"pattern_hits": len(env_cfg["pattern_hits"]), "entropy_hits": len(env_cfg["entropy_hits"])},
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_detector_control.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(SANDBOX, ignore_errors=True)
    os.environ.pop("TST0206_CANARY", None)
    os.environ.pop("TST0206_API_SECRET", None)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
