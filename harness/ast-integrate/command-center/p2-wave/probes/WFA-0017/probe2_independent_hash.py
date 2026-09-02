#!/usr/bin/env python3
"""Probe 2: independent content-hash recount across live trees.

Does not call scenario.hash_agreement. Re-walks SKILL.md files, hashes
bytes, and checks the artifact's reported intersection / identical /
divergent sets.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.OUT
SKILL_NAMES = {"skill.md"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0017-probe2 {msg}")
    return 1


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def name_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    mapping = S.parse_frontmatter_mapping(text)
    return S.skill_name(path, mapping)


def walk(root: Path) -> dict[str, set[str]]:
    by_name: dict[str, set[str]] = {}
    if not root.is_dir():
        return by_name
    skip = {".git", "node_modules", "__pycache__", ".venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if name.lower() not in SKILL_NAMES:
                continue
            p = Path(dirpath) / name
            by_name.setdefault(name_of(p), set()).add(sha256_file(p))
    return by_name


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact absent")
    text = ART.read_text(encoding="utf-8")
    if S.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    trees = doc.get("evidence_a", {}).get("inventories") or {}
    walked: dict[str, dict[str, set[str]]] = {}
    for label, inv in trees.items():
        if not isinstance(inv, dict):
            continue
        walked[label] = walk(Path(inv.get("root") or ""))

    a = walked.get("agents") or {}
    c = walked.get("claude") or {}
    shared = sorted(set(a) & set(c))
    identical = []
    divergent = []
    for name in shared:
        if a[name] == c[name] and len(a[name]) == 1:
            identical.append(name)
        else:
            divergent.append(name)

    claimed = doc.get("evidence_b", {}).get("content_hash_equality") or {}
    claimed_shared = list(claimed.get("shared_names") or [])
    claimed_ident = list(claimed.get("identical_content") or [])
    claimed_div = list(claimed.get("divergent_content") or [])

    pair = doc.get("evidence_b", {}).get("canonical_vs_compat") or {}
    canon = walked.get("repo_canonical") or {}
    compat = walked.get("repo") or {}
    pair_shared = sorted(set(canon) & set(compat))
    pair_ident = []
    pair_div = []
    for name in pair_shared:
        if canon[name] == compat[name] and len(canon[name]) == 1:
            pair_ident.append(name)
        else:
            pair_div.append(name)

    print(
        json.dumps(
            {
                "independent": {
                    "counts": {k: len(v) for k, v in walked.items()},
                    "agents_names": sorted(a),
                    "claude_names": sorted(c),
                    "repo_names": sorted(compat),
                    "repo_canonical_names": sorted(canon),
                    "shared": shared,
                    "identical": identical,
                    "divergent": divergent,
                    "canonical_vs_compat": {
                        "shared": pair_shared,
                        "identical": pair_ident,
                        "divergent": pair_div,
                    },
                },
                "claimed": {
                    "shared": claimed_shared,
                    "identical": claimed_ident,
                    "divergent": claimed_div,
                    "canonical_vs_compat": {
                        "shared": list(pair.get("shared_names") or []),
                        "identical": list(pair.get("identical_content") or []),
                        "divergent": list(pair.get("divergent_content") or []),
                    },
                },
            },
            indent=2,
        )
    )
    if set(shared) != set(claimed_shared):
        return fail(f"shared-name mismatch live={shared} claimed={claimed_shared}")
    if set(identical) != set(claimed_ident):
        return fail(
            f"identical-hash mismatch live={identical} claimed={claimed_ident}"
        )
    if set(divergent) != set(claimed_div):
        return fail(
            f"divergent-hash mismatch live={divergent} claimed={claimed_div}"
        )
    if pair:
        if set(pair_shared) != set(pair.get("shared_names") or []):
            return fail("canonical-vs-compat shared-name mismatch")
        if set(pair_ident) != set(pair.get("identical_content") or []):
            return fail("canonical-vs-compat identical-hash mismatch")
        if set(pair_div) != set(pair.get("divergent_content") or []):
            return fail("canonical-vs-compat divergent-hash mismatch")

    # Live inventories' name lists must match the independent walk.
    for label, inv in trees.items():
        if not isinstance(inv, dict):
            continue
        claimed_names = inv.get("names") or []
        live_names = walked.get(label) or {}
        if set(live_names) != set(claimed_names):
            return fail(
                f"{label} name-set mismatch live={sorted(live_names)} "
                f"claimed={claimed_names}"
            )

    gfam = doc.get("g_family_96") or {}
    if "statement" not in gfam or not str(gfam.get("statement") or "").strip():
        return fail("g_family_96.statement absent")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if (tests.get("registry-96-counting-rule") or {}).get("result") != "PASS":
        return fail("registry-96 test not PASS")
    print(
        f"independent_shared={len(shared)} identical={len(identical)} "
        f"divergent={len(divergent)} g96_kind={gfam.get('kind')}"
    )
    print("SUCCESS:WFA-0017-probe2 independent hash recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
