"""Shard2-w1 rebuild 2026-10-24: AUD-0057 + AUD-0072 emit scripts.

Both artifacts are snapshots of an older tree shape (0057: net +1 default but
gross re-layout — packages moved, new tool files; 0072: three new mapped
confidence phrases in the corpus). Both carry probe-named "reviewer" blocks
(reviewer_id == a probe script name, vendor None, no reviewed_at) — the
self-certification class receipt_core condition 9 and the shard2 contract
forbid. This patch rewrites both emit scripts to the honest builder-side
shape used by the AUD-0082 exemplar:
  * no fabricated reviewer: reviewer block becomes an explicit pending
    marker (verdict NOT-REVIEWED, independent false);
  * state becomes the truthful builder token BUILT (the four non-delivering
    tokens stay reserved for non-delivery), with the BLOCKED
    (reviewer-absent) receipt semantics carried in extensions.failure and
    mirrored in SUBAGENT-RETURN.json;
  * produced_by names this rebuild; the original build vendor is kept in
    extensions.original_build.
Running the emit then rebuilds every live-dependent block from the current
tree.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")

BS_EXT = (
    '        "extensions": {\n'
    '            "builder_process_state": "BLOCKED",\n'
    '            "shard2_rebuild_2026_10_24": (\n'
    '                "Builder-side rebuild from the live tree. The prior snapshot "\n'
    '                "carried a probe-named reviewer block (reviewer_id equal to a "\n'
    '                "probe script name, vendor None, no reviewed_at) - the "\n'
    '                "self-certification class receipt_core condition 9 forbids; it "\n'
    '                "is replaced by this pending-review marker. Receipt state=BLOCKED "\n'
    '                "(failure.classification reviewer-absent) lives in "\n'
    '                "SUBAGENT-RETURN.json; only the independent reviewer closes."\n'
    '            ),\n'
    '            "original_build": ORIGINAL_BUILD,\n'
    '        },\n'
    '        "failure": {\n'
    '            "classification": ["reviewer-absent"],\n'
    '            "reason": (\n'
    '                "Builder-side construction complete: artifact rebuilt from the "\n'
    '                "live tree, both named probes re-run live with exit 0, per-unit "\n'
    '                "manifest row written with the CRLF-normalized sha256. state is "\n'
    '                "BUILT (extensions.builder_process_state=BLOCKED), not SUCCESS, "\n'
    '                "because receipt_core forbids state=SUCCESS without "\n'
    '                "reviewer.verdict=PASS with independent=true; only the "\n'
    '                "independent reviewer closes."\n'
    '            ),\n'
    '            "blocked_on": str(REVIEWER_REQ or "independent reviewer per catalog"),\n'
    '        },'
)

# ---------------- AUD-0057 ----------------
P57 = REPO / "command-center/p2-wave/probes/AUD-0057/emit.py"

OLD57_STATE = '''    doc = {
        "unit_id": "AUD-0057",
        "id": "AUD-0057",
        "state": "SUCCESS",
        "status": "DELIVERED",'''
NEW57_STATE = '''    doc = {
        "unit_id": "AUD-0057",
        "id": "AUD-0057",
        "state": "BUILT",'''

OLD57_PROD = '''        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "tool-author",
            "execution_substrate": "local-parallel",
        },'''
NEW57_PROD = '''        "produced_by": {
            "vendor": "anthropic",
            "model": "claude-opus-5-5",
            "role": "builder-shard2-wave1",
            "execution_substrate": "local-serialized",
        },'''

OLD57_REV = '''        "reviewer": {
            "reviewer_id": "AUD-0057-probe2-mutation-independent-of-census-ast",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs only the scratch mutation both-states and does "
                "not import classify()."
            ),
        },'''
NEW57_REV = '''        "reviewer": {
            "reviewer_id": "independent-reviewer-pending",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "The prior snapshot's reviewer block named a probe script "
                "(AUD-0057-probe2-mutation-independent-of-census-ast), which is the "
                "producing lane, not an independent reviewer. Pending the "
                "catalog's fresh-context reviewer."
            ),
        },'''

REVIEWER_REQ57 = (
    'REVIEWER_REQ = (\n'
    '    "one fresh-context Claude reviewer who has not seen this unit\'s "\n'
    '    "transcript; the reviewer must try to FALSIFY the headline count "\n'
    '    "before PASS, not re-read the artifact"\n'
    ')\n'
    'ORIGINAL_BUILD = {\n'
    '    "vendor": "cursor", "model": "grok-4.6", "role": "tool-author",\n'
    '    "execution_substrate": "local-parallel",\n'
    '}\n'
)

ANCHOR57 = "def main() -> int:\n    live = C.run_census()"


def patch_57(text: str) -> str:
    assert OLD57_STATE in text, "57 state anchor"
    text = text.replace(OLD57_STATE, NEW57_STATE, 1)
    assert OLD57_PROD in text, "57 prod anchor"
    text = text.replace(OLD57_PROD, NEW57_PROD, 1)
    assert OLD57_REV in text, "57 reviewer anchor"
    text = text.replace(OLD57_REV, NEW57_REV + "\n" + BS_EXT, 1)
    assert ANCHOR57 in text, "57 main anchor"
    text = text.replace(ANCHOR57, REVIEWER_REQ57 + "\n\n" + ANCHOR57, 1)
    return text


# ---------------- AUD-0072 ----------------
P72 = REPO / "command-center/p2-wave/probes/AUD-0072/emit_artifact.py"

OLD72_STATE = '''        "kind": "confidence-status-normalization",
        "state": "SUCCESS",'''
NEW72_STATE = '''        "kind": "confidence-status-normalization",
        "state": "BUILT",'''

OLD72_REV = '''        "reviewer": {
            "reviewer_id": "AUD-0072-probe2-unmapped-residue",
            "verdict": "PASS",
            "independent": True,
            "falsify_attempt": (
                "Tried to treat should work as likely via a greedy substring mapper; "
                "the lexical mapper refused and probe 2 requires residue membership."
            ),
        },'''
NEW72_REV = '''        "reviewer": {
            "reviewer_id": "independent-reviewer-pending",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "The prior snapshot's reviewer block named a probe script "
                "(AUD-0072-probe2-unmapped-residue), which is the producing lane, "
                "not an independent reviewer. Pending the catalog's "
                "cross-vendor reviewer."
            ),
        },'''

REQ72_ANCHOR = 'REQUIRED_TOP = ('
REQ72_NEW = (
    'REVIEWER_REQ = (\n'
    '    "catalog reviewer_requirement for AUD-0072 (cross-vendor fresh-context "\n'
    '    "reviewer); see WORK-UNIT-CATALOG.json#AUD-0072"\n'
    ')\n'
    'ORIGINAL_BUILD = {\n'
    '    "note": "prior snapshot build lane (probe-named reviewer block removed)",\n'
    '}\n'
    'REQUIRED_TOP = ('
)

ANCHOR72 = "    doc = {\n        \"unit_id\": \"AUD-0072\","


def patch_72(text: str) -> str:
    assert OLD72_STATE in text, "72 state anchor"
    text = text.replace(OLD72_STATE, NEW72_STATE, 1)
    assert OLD72_REV in text, "72 reviewer anchor"
    text = text.replace(OLD72_REV, NEW72_REV + "\n" + BS_EXT, 1)
    assert REQ72_ANCHOR in text, "72 required anchor"
    text = text.replace(REQ72_ANCHOR, REQ72_NEW, 1)
    return text


def main() -> int:
    t57 = P57.read_text(encoding="utf-8")
    if "builder_process_state" not in t57:
        t57 = patch_57(t57)
        P57.write_bytes(t57.encode("utf-8"))
        py_compile.compile(str(P57), doraise=True, cfile=str(REPO / "_scratch/_e57.pyc"))
        print("emit57 PATCHED + COMPILE-OK")
    else:
        print("emit57 already-patched")
    t72 = P72.read_text(encoding="utf-8")
    if "builder_process_state" not in t72:
        t72 = patch_72(t72)
        P72.write_bytes(t72.encode("utf-8"))
        py_compile.compile(str(P72), doraise=True, cfile=str(REPO / "_scratch/_e72.pyc"))
        print("emit72 PATCHED + COMPILE-OK")
    else:
        print("emit72 already-patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
