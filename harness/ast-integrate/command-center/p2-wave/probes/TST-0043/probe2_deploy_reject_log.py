#!/usr/bin/env python3
"""Probe 2: deploy log carries an explicit REJECT line for a malformed skill.

Silence is a failure. Both-states: conforming skill is installed; malformed
skill is not. A silent-skip mutant copies the malformed skill with no REJECT
line and must be distinguishable from the real gate.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import deploy as D  # noqa: E402
import fixtures as F  # noqa: E402

UNIT = "TST-0043"
ART = HERE / "artifacts"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def write_log(name: str, lines: list[str]) -> Path:
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    body = "# TST-0043 deploy log\n" + "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    F.write_static_fixtures()
    ART.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tst0043-p2-") as td:
        root = Path(td)
        src = F.mixed_tree(root / "src")
        dest = root / "live"
        result = D.deploy_tree(src, dest)
        log_path = write_log("deploy-malformed.log", result.log_lines)

        reject_lines = result.reject_lines()
        accept_lines = result.accept_lines()
        if not reject_lines:
            return fail("malformed deploy produced no REJECT line (silence)")
        if not any("reason=FRONTMATTER_UNPARSEABLE" in ln for ln in reject_lines):
            return fail(f"REJECT line missing FRONTMATTER_UNPARSEABLE: {reject_lines}")
        if not any("skill=broken-yaml" in ln for ln in reject_lines):
            return fail(f"REJECT line missing skill=broken-yaml: {reject_lines}")
        if not any(ln.startswith("REJECT ") for ln in reject_lines):
            return fail("REJECT prefix missing")

        echo_live = dest / "skills" / "echo-skill" / "SKILL.md"
        broken_live = dest / "skills" / "broken-yaml" / "SKILL.md"
        if not echo_live.is_file():
            return fail("conforming echo-skill was not installed")
        if broken_live.exists():
            return fail("malformed broken-yaml was installed (should be rejected)")
        if "echo-skill" not in result.accepted:
            return fail("echo-skill missing from accepted")
        if not any("skill=echo-skill" in ln for ln in accept_lines):
            return fail("no ACCEPT line for conforming skill")
        if result.ok:
            return fail("mixed deploy reported ok=True despite a rejection")

        clean_src = F.conforming_tree(root / "clean-src")
        clean_dest = root / "clean-live"
        clean = D.deploy_tree(clean_src, clean_dest)
        if not clean.ok:
            return fail(f"clean deploy failed: {clean.log_lines}")
        if clean.reject_lines():
            return fail(f"clean deploy logged REJECT: {clean.reject_lines()}")
        write_log("deploy-clean.log", clean.log_lines)
        if not (clean_dest / "skills" / "echo-skill" / "SKILL.md").is_file():
            return fail("clean deploy missing echo-skill")
        if not (clean_dest / "skills" / "scoped-skill" / "SKILL.md").is_file():
            return fail("clean deploy missing scoped-skill")

        silent_dest = root / "silent-live"
        silent = D.silent_skip_deploy(src, silent_dest)
        silent_broken = silent_dest / "skills" / "broken-yaml" / "SKILL.md"
        if not silent_broken.is_file():
            return fail("silent-skip mutant did not copy malformed skill")
        if silent.reject_lines():
            return fail("silent-skip mutant unexpectedly logged REJECT")
        if not silent.ok:
            return fail("silent-skip mutant reported not ok")
        distinguished = bool(result.reject_lines()) and not silent.reject_lines()
        if not distinguished:
            return fail("could not distinguish real gate from silent-skip mutant")

        payload = {
            "probe": "probe2-deploy-reject-log",
            "unit_id": UNIT,
            "reject_lines": reject_lines,
            "accept_lines": accept_lines,
            "malformed_installed": broken_live.exists(),
            "conforming_installed": echo_live.is_file(),
            "clean_ok": clean.ok,
            "clean_reject_count": len(clean.reject_lines()),
            "silent_skip_installed_malformed": silent_broken.is_file(),
            "silent_skip_reject_count": len(silent.reject_lines()),
            "silence_is_failure": True,
            "log_path": str(log_path.relative_to(HERE.parents[3])).replace("\\", "/"),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        for ln in reject_lines:
            print(ln)
        print("SUCCESS:TST-0043-probe2 explicit REJECT line; silent skip distinguished")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
