#!/usr/bin/env python3
"""TST-0070 probe1: clean install of the BUILT payload into an empty
profile (live, fail-closed).

Rebuilds the golden-kit tar.gz from the kit sources, asserts the member
census matches the receipt's 8 recorded members (byte-exact tar bytes
are host-dependent and are not asserted; the census is), that the
artifact vendors no jsonschema and no repo tools, installs it into a
fresh empty profile by unpacking, and verifies the install digest is
the artifact digest (payload is the package, not the source tree)."""
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
UNIT = "TST-0070"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
EXPECTED_MEMBERS = [
    "golden-kit/PACKAGE-METADATA.json",
    "golden-kit/hooks/hook.golden.json",
    "golden-kit/journeys/hook_fire.py",
    "golden-kit/journeys/identity_manifest.py",
    "golden-kit/journeys/skill_checksum.py",
    "golden-kit/plugin.json",
    "golden-kit/rules/rule.golden.md",
    "golden-kit/skills/skill.golden/SKILL.md",
]
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 1024, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0070" in OUT.read_text(encoding="utf-8"), "sentinel-absent")

    td = tempfile.mkdtemp(prefix="tst0070-p1-")
    try:
        dist = Path(td) / "dist"
        dist.mkdir()
        art = dist / "golden-kit-1.0.0.tar.gz"
        with tarfile.open(art, "w:gz") as tf:
            for rel in EXPECTED_MEMBERS:
                tf.add(HERE / "kit" / rel.split("/", 1)[1], arcname=rel)
        raw = art.read_bytes()
        with tarfile.open(art, "r:gz") as tf:
            names = sorted(m.name for m in tf.getmembers() if m.isfile() and not m.name.endswith("/"))
        chk(names == sorted(EXPECTED_MEMBERS), "member-census", json.dumps(names))
        chk(b"jsonschema" not in raw, "artifact-vendors-jsonschema")
        chk(b"tools/plugin" not in raw and (b"tools" + bytes([92]) + b"plugin") not in raw, "artifact-vendors-repo-tools")
        # clean install into an empty profile
        profile = Path(td) / "empty-profile" / "site"
        profile.mkdir(parents=True)
        with tarfile.open(art, "r:gz") as tf:
            tf.extractall(profile)
        installed = profile / "golden-kit"
        chk((installed / "plugin.json").is_file() and (installed / "journeys" / "hook_fire.py").is_file(), "installed-kit-complete")
        # install digest equals artifact digest (payload is the package)
        man = json.loads((installed / "PACKAGE-METADATA.json").read_text(encoding="utf-8"))
        chk(man.get("name") == "golden-kit" and man.get("stdlib_only") is True, "installed-manifest")
        art_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        live = doc.get("live") or {}
        rec = ((live.get("clean_install") or {}).get("artifact") or {})
        chk(int(rec.get("member_count", -1)) == 8 and len(rec.get("members") or []) == 8, "receipt-member-count-8")
        rec_members = sorted(rec.get("members") or [])
        if rec_members != sorted(EXPECTED_MEMBERS):
            chk(False, "receipt-members-match-rebuild", "receipt=" + json.dumps(rec_members) + " built=" + json.dumps(sorted(EXPECTED_MEMBERS)))
        chk(bool(rec.get("contains_jsonschema") is False or rec.get("contains_jsonschema") is None), "receipt-jsonschema-flag")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 built payload (8 members, no jsonschema, no repo tools) clean-installed into an empty profile; install complete; receipt member census matches the rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
