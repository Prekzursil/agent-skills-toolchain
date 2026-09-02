#!/usr/bin/env python3
"""Probe 2: translation provenance is present and schema-distinct.

A translated claim must carry source_language, original_span, and the
translated-provisional confidence path. A native claim must carry the
native-direct path. The two path ids must be disjoint. Planting a translated
claim onto the native path, and a native claim onto the translated path,
must fail the schema — both states of the discriminator.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from blueprints import library  # noqa: E402
from claims import ClaimError, translation_distinctness, validate_claim  # noqa: E402
from engine import run_named  # noqa: E402
from taxonomy import NATIVE_PATH, TRANSLATED_PATH  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0236-probe2 {msg}")
    return 1


def main() -> int:
    lib = library()
    run = run_named(lib, "multilingual")
    claims = run["claims"]
    dist = translation_distinctness(claims)
    print(
        "translation "
        f"native={dist['native_count']} translated={dist['translated_count']} "
        f"native_paths={dist['native_path_ids']} "
        f"translated_paths={dist['translated_path_ids']} "
        f"overlap={dist['path_id_overlap']} distinguishable={dist['distinguishable']}"
    )
    if dist["native_count"] < 1 or dist["translated_count"] < 1:
        return _fail("multilingual harvest lacks both native and translated claims")
    if not dist["distinguishable"]:
        return _fail("translated and native claims share a confidence path")
    if dist["native_path_ids"] != [NATIVE_PATH["id"]]:
        return _fail("native path id drifted from taxonomy")
    if dist["translated_path_ids"] != [TRANSLATED_PATH["id"]]:
        return _fail("translated path id drifted from taxonomy")

    translated = next(
        c for c in claims if c["translation"]["is_translated"] is True
    )
    native = next(
        c for c in claims if c["translation"]["is_translated"] is False
    )
    print(
        f"translated_id={translated['id']} source_language={translated['source_language']} "
        f"path={translated['confidence_path']['id']} "
        f"original_span_set={bool(translated['translation']['original_span'])}"
    )
    print(
        f"native_id={native['id']} source_language={native['source_language']} "
        f"path={native['confidence_path']['id']}"
    )
    if translated["source_language"] == native.get("working_language") and not translated[
        "translation"
    ].get("original_span"):
        return _fail("translated claim lost its source-language provenance")
    if not translated["translation"].get("original_span"):
        return _fail("translated claim missing original_span")
    if native["confidence_path"]["id"] == translated["confidence_path"]["id"]:
        return _fail("native and translated claims share confidence_path.id")

    swapped = copy.deepcopy(translated)
    swapped["id"] = "plant-translated-on-native-path"
    swapped["confidence_path"] = dict(NATIVE_PATH)
    try:
        validate_claim(swapped)
        return _fail("schema accepted a translated claim on the native path")
    except ClaimError as exc:
        print(f"translated_on_native_path_rejected={exc}")

    swapped_native = copy.deepcopy(native)
    swapped_native["id"] = "plant-native-on-translated-path"
    swapped_native["confidence_path"] = dict(TRANSLATED_PATH)
    try:
        validate_claim(swapped_native)
        return _fail("schema accepted a native claim on the translated path")
    except ClaimError as exc:
        print(f"native_on_translated_path_rejected={exc}")

    missing_span = copy.deepcopy(translated)
    missing_span["id"] = "plant-translated-without-span"
    missing_span["translation"] = dict(missing_span["translation"])
    missing_span["translation"]["original_span"] = None
    try:
        validate_claim(missing_span)
        return _fail("schema accepted a translated claim without original_span")
    except ClaimError as exc:
        print(f"translated_without_span_rejected={exc}")

    untagged = copy.deepcopy(native)
    untagged["id"] = "plant-missing-class"
    untagged = {k: v for k, v in untagged.items() if k != "evidence_class"}
    try:
        validate_claim(untagged)
        return _fail("schema accepted a claim with no evidence_class")
    except ClaimError as exc:
        print(f"missing_evidence_class_rejected={exc}")

    print(json.dumps({"translation": dist, "claim_count": len(claims)}, sort_keys=True))
    print("SUCCESS:IMP-0236-probe2 translation provenance distinct both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
