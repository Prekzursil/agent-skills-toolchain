#!/usr/bin/env python3
"""Probe 2: published not-frozen scope; freeze cannot be over-read.

Every published not-frozen example must exist, classify as not-frozen, and
leave the gate silent when edited in a scratch overlay. The live freeze-set
hash must match the artifact. Independent of probe 1's both-states narrative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as B  # noqa: E402
import ceremony as C  # noqa: E402
import gate as G  # noqa: E402
import inventory as I  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0110.json"
MARK = b"\n/* ARC-0110-scope-mutation */\n"


def main() -> int:
    census = I.census()
    print(
        "frozen="
        f"{census['frozen_count']} schemas={census['schema_count']} "
        f"launchers={census['launcher_count']} set={census['set_sha256'][:16]}"
    )
    if census["not_frozen_examples_missing"]:
        print(
            "FAILED:ARC-0110-probe2 missing "
            + ",".join(census["not_frozen_examples_missing"])
        )
        return 1
    if census["not_frozen_examples_overclassed"]:
        print(
            "FAILED:ARC-0110-probe2 overclassed "
            + ",".join(census["not_frozen_examples_overclassed"])
        )
        return 1

    overlay = {}
    for rel in I.NOT_FROZEN_EXAMPLES:
        overlay[rel] = (REPO / rel).read_bytes() + MARK
        if I.classify(rel) != "not-frozen":
            print(f"FAILED:ARC-0110-probe2 {rel} classified {I.classify(rel)}")
            return 1
    scoped = G.evaluate(REPO, census["frozen"], overlay=overlay, migrations=[])
    print(
        f"scope_gate ok={scoped['ok']} ignored={len(scoped['nonfrozen_changes_ignored'])} "
        f"rejections={len(scoped['rejections'])}"
    )
    if not scoped["ok"] or scoped["rejections"]:
        print("FAILED:ARC-0110-probe2 gate fired on published not-frozen paths")
        print(json.dumps(scoped["rejections"], indent=2)[:2000])
        return 1
    ignored = set(scoped["nonfrozen_changes_ignored"])
    missing_ignored = [rel for rel in I.NOT_FROZEN_EXAMPLES if rel not in ignored]
    if missing_ignored:
        print(f"FAILED:ARC-0110-probe2 overlay paths not ignored: {missing_ignored}")
        return 1

    frozen_rel = census["frozen"][0]["path"]
    if frozen_rel in I.NOT_FROZEN_EXAMPLES:
        print("FAILED:ARC-0110-probe2 frozen path listed as not-frozen")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0110-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0110-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0110" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0110-probe2 sentinel absent")
        return 1
    art_fp = doc.get("fingerprint") or {}
    art_frozen = (doc.get("census") or {}).get("frozen") or []
    from hashutil import digest_bytes

    recomputed = digest_bytes(
        ("\n".join(f"{r['path']} {r['sha256']}" for r in art_frozen) + "\n").encode(
            "utf-8"
        )
    )[0]
    if art_fp.get("set_sha256") != recomputed:
        print("FAILED:ARC-0110-probe2 artifact freeze-set hash is not self-consistent")
        return 1
    if art_fp.get("frozen_count") != len(art_frozen):
        print("FAILED:ARC-0110-probe2 artifact frozen_count is not self-consistent")
        return 1
    if art_fp.get("frozen_count") != (doc.get("census") or {}).get("frozen_count"):
        print("FAILED:ARC-0110-probe2 census frozen_count disagrees with fingerprint")
        return 1
    if (doc.get("trigger") or {}).get("id") != C.TRIGGER_ID:
        print("FAILED:ARC-0110-probe2 trigger id missing or wrong")
        return 1
    if not (doc.get("trigger") or {}).get("armed"):
        print("FAILED:ARC-0110-probe2 freeze not armed")
        return 1
    scope = doc.get("not_frozen") or {}
    art_examples = [e.get("path") for e in (scope.get("examples") or [])]
    for rel in I.NOT_FROZEN_EXAMPLES:
        if rel not in art_examples:
            print(f"FAILED:ARC-0110-probe2 artifact omitted not-frozen example {rel}")
            return 1
    if len(scope.get("classes") or []) < 2:
        print("FAILED:ARC-0110-probe2 artifact omitted not-frozen classes")
        return 1

    # Independent of probe 1: still require the unmigrated plant to fire, so a
    # scope-only silent gate cannot be mistaken for a freeze.
    plant = B.run(REPO)
    if not plant["detector_control"].get("fired"):
        print("FAILED:ARC-0110-probe2 independent unmigrated plant did not fire")
        return 1
    print("SUCCESS:ARC-0110-probe2 not-frozen scope published and gate-silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
