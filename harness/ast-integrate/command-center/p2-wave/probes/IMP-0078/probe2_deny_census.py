#!/usr/bin/env python3
"""Named probe 2: deny cell places no file; allow cell installs in the same run."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.installer import census, install  # noqa: E402
from marketplace.trust_policy import (  # noqa: E402
    ActivationError,
    default_policy_document,
    fixture_attestation,
    require_owner_signoff,
)

ART = REPO / "command-center/receipts/IMP-0078.json"


def _pack(root: Path) -> Path:
    src = root / "pkg"
    src.mkdir()
    (src / "plugin.json").write_text('{"id":"probe2.pkg"}\n', encoding="utf-8")
    nested = src / "nested"
    nested.mkdir()
    (nested / "file.txt").write_text("nested\n", encoding="utf-8")
    return src


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0078-probe2 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0078" not in json.dumps(receipt):
        print("FAILED:IMP-0078-probe2 sentinel absent")
        return 1

    unsigned = default_policy_document()
    try:
        require_owner_signoff(unsigned)
        print("FAILED:IMP-0078-probe2 unsigned default activated")
        return 1
    except ActivationError as exc:
        unsigned_blocked = type(exc).__name__

    policy = fixture_attestation()
    with tempfile.TemporaryDirectory(prefix="imp0078-p2-") as tmp_s:
        tmp = Path(tmp_s)
        pkg = _pack(tmp)
        deny_dest = tmp / "deny"
        allow_dest = tmp / "allow"
        deny_dest.mkdir()
        marker = deny_dest / "already-here.txt"
        marker.write_text("census-anchor\n", encoding="utf-8")
        before = census(deny_dest)

        denied = install(pkg, deny_dest, policy, "unsigned", "high", "none")
        after_deny = census(deny_dest)
        if denied.verdict != "deny":
            print("FAILED:IMP-0078-probe2 expected deny", denied.as_dict())
            return 1
        if denied.placed_any_file or denied.write_attempted:
            print("FAILED:IMP-0078-probe2 deny wrote", denied.as_dict())
            return 1
        if after_deny != before or not denied.census_unchanged:
            print("FAILED:IMP-0078-probe2 census changed under deny")
            print(json.dumps({"before": before, "after": after_deny}))
            return 1
        if (deny_dest / "plugin.json").exists() or (
            deny_dest / "nested" / "file.txt"
        ).exists():
            print("FAILED:IMP-0078-probe2 deny placed package files")
            return 1
        if not marker.is_file():
            print("FAILED:IMP-0078-probe2 deny disturbed preexisting file")
            return 1
        if not denied.visibility.get("surface_at_install"):
            print("FAILED:IMP-0078-probe2 deny hid policy")
            return 1

        allowed = install(pkg, allow_dest, policy, "verified", "high", "none")
        if allowed.verdict != "allow" or not allowed.placed_any_file:
            print("FAILED:IMP-0078-probe2 allow did not install", allowed.as_dict())
            return 1
        if not (allow_dest / "plugin.json").is_file():
            print("FAILED:IMP-0078-probe2 allow missing plugin.json")
            return 1
        if not (allow_dest / "nested" / "file.txt").is_file():
            print("FAILED:IMP-0078-probe2 allow missing nested file")
            return 1
        if not allowed.visibility.get("surface_at_install"):
            print("FAILED:IMP-0078-probe2 allow hid policy")
            return 1
        if allowed.visibility.get("cell") != "verified|high|none":
            print("FAILED:IMP-0078-probe2 visibility cell", allowed.visibility)
            return 1

        if census(deny_dest) != before:
            print("FAILED:IMP-0078-probe2 deny dest mutated after allow")
            return 1

    print(
        json.dumps(
            {
                "deny_cell": "unsigned|high|none",
                "deny_placed_any_file": False,
                "deny_census_unchanged": True,
                "allow_cell": "verified|high|none",
                "allow_installed": True,
                "policy_visible": True,
                "unsigned_default_blocked": unsigned_blocked,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0078-probe2 deny census and allow negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
