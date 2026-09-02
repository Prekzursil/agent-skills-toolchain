#!/usr/bin/env python3
"""Probe 2: extension-manifest and GEMINI.md census from frozen captures.

Mechanically different from probe 1 (live PATH/invocation). This probe re-hashes
captured bytes, re-parses ExtensionConfig vs docs, and requires the planted
invented key to be absent on the real files and present on a mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import NOT_DELIVERING, OUT_REL, SENTINEL, UNIT  # noqa: E402
from surface import PLANTED_KEY, census, planted_key_both_states  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    surf = census()
    plant = planted_key_both_states()
    print(
        "source_keys={sk} docs_keys={dk} docs_only={do} source_only={so} "
        "default={d} planted_absent={pa} discriminates={disc}".format(
            sk=surf["source_manifest_keys"],
            dk=surf["docs_manifest_keys"],
            do=surf["docs_only"],
            so=surf["source_only"],
            d=surf["default_context_filename"],
            pa=surf["planted_key_absent_from_real_census"],
            disc=plant["discriminates"],
        )
    )
    print("hierarchy=" + ",".join(h["id"] for h in surf["docs_hierarchy"]))
    print("memory_fns=" + ",".join(surf["source_memory_functions"]))
    if surf["default_context_filename"] != "GEMINI.md":
        return fail("default context filename is not GEMINI.md")
    if PLANTED_KEY in surf["source_manifest_keys"] or PLANTED_KEY in surf["docs_manifest_keys"]:
        return fail("invented key leaked into census")
    if not plant["discriminates"]:
        return fail("parser silent in both states on planted key")
    if "description" not in surf["docs_only"]:
        return fail("expected docs-only description field as the divergence")
    if "name" not in surf["agreed_keys"] or "version" not in surf["agreed_keys"]:
        return fail("name/version not in agreed key set")
    if "contextFileName" not in surf["agreed_keys"]:
        return fail("contextFileName missing from agreed keys")
    needed_dirs = {"commands/", "hooks/hooks.json", "skills/", "agents/", "policies/"}
    got_dirs = {d["path"] for d in surf["directory_conventions"] if d["documented"]}
    if not needed_dirs <= got_dirs:
        return fail(f"directory conventions missing {needed_dirs - got_dirs}")
    hier_ids = {h["id"] for h in surf["docs_hierarchy"]}
    if hier_ids != {"global", "workspace", "jit"}:
        return fail(f"hierarchy ids {hier_ids}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    answers = doc.get("answers") or {}
    if answers.get("docs_only_manifest_keys") != surf["docs_only"]:
        return fail("artifact docs_only mismatch")
    if answers.get("default_context_filename") != "GEMINI.md":
        return fail("artifact default filename mismatch")
    if answers.get("planted_parser_discriminates") is not True:
        return fail("artifact planted parser control not recorded")
    art_keys = (doc.get("extension_surface") or {}).get("source_manifest_keys")
    if art_keys != surf["source_manifest_keys"]:
        return fail("artifact source keys mismatch live census")
    claim_ids = [c.get("claim_id") for c in (doc.get("claims") or [])]
    for needed in (
        "RES-0024-C2-extension-manifest",
        "RES-0024-C3-gemini-md-hierarchy",
        "RES-0024-C4-description-docs-only",
    ):
        if needed not in claim_ids:
            return fail(f"missing claim {needed}")
    print(f"SUCCESS:{UNIT}-probe2 surface census planted-key discriminates docs_only={surf['docs_only']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
