#!/usr/bin/env python3
"""Probe 1: next health check flags a just-revoked package with no refresh.

Signal (a) of the catalog evidence_requirement: health-check output naming
the revoked package.

Both-states:
  FIRE  — tst0221-revoked-widget is named after an upstream revoke.
  SILENT — tst0221-clean-echo is not flagged in the same run.

Negative control: the stale-cache mutant stays silent until refresh().
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MKT = REPO / "tools" / "marketplace"
CLI = MKT / "revocation_health.py"
sys.path.insert(0, str(MKT))

import revocation_health as H  # noqa: E402

OUT = HERE / "probe1-health-check-no-refresh.raw.json"
UNIT = "TST-0221"


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:TST-0221-probe1 {msg}")
    return 1


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def last_json(text: str) -> dict:
    blob = (text or "").strip()
    idx = blob.find("{")
    if idx < 0:
        return {}
    try:
        doc, _ = json.JSONDecoder().raw_decode(blob[idx:])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def main() -> int:
    payload: dict = {
        "probe": "probe1-health-check-no-refresh",
        "unit_id": UNIT,
        "pass": False,
    }
    with tempfile.TemporaryDirectory(prefix="t221-p1-", dir="/tmp") as td:
        root = Path(td)
        seed = run_cli(["seed", "--root", str(root)])
        if seed.returncode != 0:
            return fail(payload, f"seed exit {seed.returncode}: {seed.stderr}")
        paths = last_json(seed.stdout)
        home, upstream = paths["home"], paths["upstream"]

        before = run_cli(
            ["health-check", "--home", home, "--upstream", upstream, "--mode", "live"]
        )
        before_doc = last_json(before.stdout)
        payload["before"] = {
            "exit_code": before.returncode,
            "ok": before_doc.get("ok"),
            "named_packages": before_doc.get("named_packages"),
            "fetched_upstream": before_doc.get("fetched_upstream"),
            "refresh_called": before_doc.get("refresh_called"),
            "message": before_doc.get("message"),
        }
        if before.returncode != 0 or not before_doc.get("ok"):
            return fail(payload, "clean world was flagged before revoke")
        if before_doc.get("named_packages"):
            return fail(payload, "clean world named a package before revoke")
        if not before_doc.get("fetched_upstream"):
            return fail(payload, "live health-check did not fetch upstream")
        if before_doc.get("refresh_called"):
            return fail(payload, "live health-check required refresh() on clean world")

        rev = run_cli(["revoke", "--upstream", upstream])
        if rev.returncode != 0:
            return fail(payload, f"revoke exit {rev.returncode}")

        # Next health check. No refresh subcommand is invoked.
        after = run_cli(
            ["health-check", "--home", home, "--upstream", upstream, "--mode", "live"]
        )
        after_doc = last_json(after.stdout)
        combined = ((after.stdout or "") + "\n" + (after.stderr or "")).strip()
        payload["after"] = {
            "exit_code": after.returncode,
            "ok": after_doc.get("ok"),
            "named_packages": after_doc.get("named_packages"),
            "flagged": after_doc.get("flagged"),
            "fetched_upstream": after_doc.get("fetched_upstream"),
            "used_cache": after_doc.get("used_cache"),
            "refresh_called": after_doc.get("refresh_called"),
            "message": after_doc.get("message"),
            "stdout_names_package": H.REVOKED_PACKAGE in combined,
            "stderr_names_package": H.REVOKED_PACKAGE in (after.stderr or ""),
        }
        if after.returncode != 2:
            return fail(payload, f"revoked health-check exit {after.returncode}, want 2")
        if after_doc.get("ok"):
            return fail(payload, "revoked health-check ok=true")
        named = list(after_doc.get("named_packages") or [])
        if H.REVOKED_PACKAGE not in named:
            return fail(payload, f"revoked package not named: {named}")
        if H.CLEAN_PACKAGE in named:
            return fail(payload, "clean package was flagged (both-states fail)")
        if H.REVOKED_PACKAGE not in combined:
            return fail(payload, "health-check output did not name the revoked package")
        if after_doc.get("refresh_called"):
            return fail(payload, "live path called refresh(); flag required a manual refresh")
        if not after_doc.get("fetched_upstream"):
            return fail(payload, "live health-check did not fetch upstream after revoke")
        if after_doc.get("used_cache"):
            return fail(payload, "live health-check used cache instead of upstream")

        stale = run_cli(
            [
                "health-check",
                "--home",
                home,
                "--upstream",
                upstream,
                "--mode",
                "stale-cache",
            ]
        )
        stale_doc = last_json(stale.stdout)
        payload["stale_before_refresh"] = {
            "exit_code": stale.returncode,
            "ok": stale_doc.get("ok"),
            "named_packages": stale_doc.get("named_packages"),
            "used_cache": stale_doc.get("used_cache"),
        }
        # The live check above already wrote the fresh list into the cache as a
        # side effect. Re-seed a second world so the mutant is measured against
        # an empty cache after revoke.
        root2 = root / "mutant"
        seed2 = run_cli(["seed", "--root", str(root2)])
        paths2 = last_json(seed2.stdout)
        home2, upstream2 = paths2["home"], paths2["upstream"]
        run_cli(["revoke", "--upstream", upstream2])
        stale2 = run_cli(
            [
                "health-check",
                "--home",
                home2,
                "--upstream",
                upstream2,
                "--mode",
                "stale-cache",
            ]
        )
        stale2_doc = last_json(stale2.stdout)
        payload["stale_fresh_world"] = {
            "exit_code": stale2.returncode,
            "ok": stale2_doc.get("ok"),
            "named_packages": stale2_doc.get("named_packages"),
            "used_cache": stale2_doc.get("used_cache"),
            "fetched_upstream": stale2_doc.get("fetched_upstream"),
        }
        if stale2.returncode != 0 or not stale2_doc.get("ok"):
            return fail(payload, "stale-cache mutant flagged without refresh (not a discriminating mutant)")
        if stale2_doc.get("named_packages"):
            return fail(payload, "stale-cache mutant named a package without refresh")

        live2 = run_cli(
            ["health-check", "--home", home2, "--upstream", upstream2, "--mode", "live"]
        )
        live2_doc = last_json(live2.stdout)
        payload["live_on_mutant_world"] = {
            "exit_code": live2.returncode,
            "named_packages": live2_doc.get("named_packages"),
            "refresh_called": live2_doc.get("refresh_called"),
        }
        if H.REVOKED_PACKAGE not in list(live2_doc.get("named_packages") or []):
            return fail(payload, "live check on mutant world did not flag")

        run_cli(["refresh", "--home", home2, "--upstream", upstream2])
        stale_after = run_cli(
            [
                "health-check",
                "--home",
                home2,
                "--upstream",
                upstream2,
                "--mode",
                "stale-cache",
            ]
        )
        stale_after_doc = last_json(stale_after.stdout)
        payload["stale_after_refresh"] = {
            "exit_code": stale_after.returncode,
            "named_packages": stale_after_doc.get("named_packages"),
        }
        if H.REVOKED_PACKAGE not in list(stale_after_doc.get("named_packages") or []):
            return fail(payload, "stale-cache mutant still silent after refresh")

        payload["pass"] = True
        payload["both_states_control"] = (
            "revoked package named; non-revoked package not flagged; "
            "no manual refresh on the live path"
        )
        payload["negative_control"] = (
            "stale-cache mutant silent until refresh(); live fetch flags immediately"
        )
        payload["signal_a"] = {
            "kind": "health-check-output-names-revoked-package",
            "package": H.REVOKED_PACKAGE,
            "version": H.REVOKED_VERSION,
            "message": after_doc.get("message"),
            "exit_code": after.returncode,
        }
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"flagged={named} exit={after.returncode} "
            f"refresh_called={after_doc.get('refresh_called')} "
            f"stale_missed={stale2_doc.get('ok')}"
        )
        print("SUCCESS:TST-0221-probe1 health-check names revoked package without refresh")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
