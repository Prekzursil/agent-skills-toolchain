#!/usr/bin/env python3
"""TST-0219 probe 2: detector-confused mutant + independent tree hashes.

The confused mutant (ignores origin pins, picks the highest version from any
registry) MUST install the public v9.9.9 artifact - proving the public payload
is live and distinct and that origin pinning is load-bearing. Both dest trees
are re-hashed with a mechanically different API (os.walk byte-inventory) as
the independent signal; the resolved-set comparison must agree with the
resolver's own rglob-based tree hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from resolver import ResolutionRefused, dest_tree_hash, install, install_confused_mutant  # noqa: E402

FIXTURES = HERE / "fixtures2"
PRIVATE = "https://registry.private.example"
PUBLIC = "https://registry.public.example"


def walk_tree_hash(dest: Path) -> str:
    """Independent tree hash: os.walk + file read (different API from rglob)."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            h.update(str(p.relative_to(dest)).replace("\\", "/").encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    priv = FIXTURES / "private"
    pub = FIXTURES / "public"
    private_payload = b"acme-internal-sdk 1.0.0 PRIVATE payload - internal only\n"
    public_hi = b"acme-internal-sdk 9.9.9 PUBLIC highest-version payload\n"
    for root, version, payload in (
        (priv, "1.0.0", private_payload),
        (pub, "9.9.9", public_hi),
    ):
        d = root / "acme-internal-sdk" / version
        d.mkdir(parents=True, exist_ok=True)
        (d / "payload.txt").write_bytes(payload)
    registries = {PRIVATE: priv, PUBLIC: pub}
    integrity = hashlib.sha256(private_payload).hexdigest()
    lockfile = {"name": "acme-internal-sdk", "version": "1.0.0", "origin": PRIVATE, "integrity": integrity}

    dest_mutant = FIXTURES / "dest-mutant"
    mutant = install_confused_mutant(lockfile, dest_mutant, registries)

    dest_good = FIXTURES / "dest-good"
    good = install(lockfile, dest_good, registries)

    mutant_walk = walk_tree_hash(dest_mutant)
    good_walk = walk_tree_hash(dest_good)
    hashes_agree = mutant_walk == mutant["tree_sha256"] and good_walk == good["tree_sha256"]

    mutant_installed_public = (
        mutant["installed"]["origin"] == PUBLIC
        and mutant["installed"]["version"] == "9.9.9"
        and mutant["installed"]["integrity"] == hashlib.sha256(public_hi).hexdigest()
    )

    # the mutant's tree must differ from the pinned install's tree
    trees_differ = mutant["tree_sha256"] != good["tree_sha256"]

    checks = {
        "detector_confused_mutant_installs_public": mutant_installed_public,
        "mutant_proves_public_payload_live": mutant["outcome"] == "SUCCESS",
        "independent_walk_hash_agrees": hashes_agree,
        "mutant_tree_differs_from_pinned_tree": trees_differ,
    }
    out = {
        "probe": "probe2_tree_hash",
        "unit": "TST-0219",
        "mutant_install": {"installed": mutant["installed"], "tree_sha256": mutant["tree_sha256"]},
        "pinned_install": {"installed": good["installed"], "tree_sha256": good["tree_sha256"]},
        "independent_walk_hashes": {"mutant": mutant_walk, "pinned": good_walk},
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_tree_hash.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(FIXTURES, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
