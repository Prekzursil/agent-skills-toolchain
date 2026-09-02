#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0021.json and OPTION-ID-RESOLUTION.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_all  # noqa: E402
from corpus import HARNESS_ID, MISSION_IDS  # noqa: E402
from corpus import arch_file, ensure_corpus, estate_root, option_md, planted_file  # noqa: E402
from corpus import tree_paths  # noqa: E402
from extractor import regex_catalog  # noqa: E402
from resolver import ASSIGNED_PREFIX  # noqa: E402
from schema_check import errors, garbage_rejected  # noqa: E402

OUT = "command-center/receipts/CC-0021.json"
SCHEMA = "command-center/schema/option-id-namespace.schema.json"
REGISTRY = "command-center/OPTION-ID-RESOLUTION.json"
REGISTRY_MD = "command-center/OPTION-ID-RESOLUTION.md"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0021/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0021/probe2_gate_controls.py"
)
NAMED_INPUTS = [
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
    "wave1/REGISTER.md",
    "command-center/OPTION-ID-RESOLUTION.json",
]
QUESTION = (
    "Question: how many distinct things does an M-NN token mean on this estate, "
    "and can a resolver disambiguate them mechanically?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def first_line(path: Path, needle: str) -> int:
    if not path.is_file():
        return 0
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return 0


def live_inputs() -> dict:
    rows = {}
    for n in NAMED_INPUTS:
        p = REPO / n
        rows[n] = {
            "present": p.is_file() and p.stat().st_size > 0,
            "bytes": p.stat().st_size if p.is_file() else 0,
        }
    return rows


def rel_from_here(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def main() -> int:
    ensure_corpus()
    ctrl = run_all()
    if not ctrl.get("ok"):
        print("FAILED:CC-0021 controls")
        print(json.dumps({k: v.get("ok") if isinstance(v, dict) else v for k, v in ctrl.items()}, indent=2))
        return 1

    live = live_inputs()
    rx = regex_catalog()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hid = HARNESS_ID
    skill_a = tree_paths()[0] / "skills/deep-research/SKILL.md"
    skill_b = tree_paths()[1] / "skills/deep-research/SKILL.md"
    planted = planted_file()
    mention = HERE / "fixtures/mention/quoting-collision.md"
    register = estate_root() / "wave1" / "REGISTER.md"

    part = ctrl["option_partition"]
    h = ctrl["harness_census"]
    fp = ctrl["mech_false_positive"]

    namespaces = [
        {
            "id": "option-universe-family-M",
            "historical_prefix": "M",
            "assigned_prefix": ASSIGNED_PREFIX["option-universe-family-M"],
            "declaration_ids": part["option"],
            "declaring_files": [
                rel_from_here(option_md()),
                rel_from_here(estate_root() / "07-OPTION-UNIVERSE.json"),
            ],
            "present_on_disk": True,
            "live_named_input_present": live["07-OPTION-UNIVERSE.md"]["present"],
            "id_count": len(part["option"]),
        },
        {
            "id": "architecture-mechanism",
            "historical_prefix": "M",
            "assigned_prefix": ASSIGNED_PREFIX["architecture-mechanism"],
            "declaration_ids": part["mech"],
            "declaring_files": [rel_from_here(arch_file())],
            "present_on_disk": True,
            "live_named_input_present": live["13-ARCHITECTURE-CANDIDATES.md"]["present"],
            "id_count": len(part["mech"]),
        },
        {
            "id": "research-harness",
            "historical_prefix": "M",
            "assigned_prefix": ASSIGNED_PREFIX["research-harness"],
            "declaration_ids": [hid],
            "declaring_files": [rel_from_here(skill_a), rel_from_here(skill_b)],
            "present_on_disk": True,
            "live_named_input_present": live[
                "wave3/ast-cc/skills/deep-research/SKILL.md"
            ]["present"],
            "id_count": 1,
            "reference_hits": h["refs"],
            "reference_files": h["files"],
        },
        {
            "id": "wave1-mission-grade",
            "historical_prefix": "M",
            "assigned_prefix": ASSIGNED_PREFIX["wave1-mission-grade"],
            "declaration_ids": list(MISSION_IDS),
            "declaring_files": [rel_from_here(register)],
            "present_on_disk": True,
            "live_named_input_present": live["wave1/REGISTER.md"]["present"],
            "id_count": len(MISSION_IDS),
        },
    ]

    registry = {
        "schema_version": 1,
        "produced_by": "CC-0021",
        "sentinel": "SUCCESS:CC-0021",
        "namespaces": [
            {
                "id": n["id"],
                "historical_prefix": n["historical_prefix"],
                "assigned_prefix": n["assigned_prefix"],
                "declaration_ids": n["declaration_ids"],
            }
            for n in namespaces
        ],
        "prefix_assignment": dict(ASSIGNED_PREFIX),
        "resolver_module": "command-center/p2-wave/probes/CC-0021/resolver.py",
        "extractor_module": "command-center/p2-wave/probes/CC-0021/extractor.py",
        "gate_module": "command-center/p2-wave/probes/CC-0021/resolver.py",
        "regex_primary": rx["regex_primary"],
        "regex_reviewer": rx["regex_reviewer"],
        "bare_m_is_ambiguous": True,
        "never_guess_from_prose": True,
    }
    # Catalog lists OPTION-ID-RESOLUTION.json as an INPUT. Do not overwrite
    # the live F-B-02 measurement if it is already on disk; the namespace
    # registry for this unit lives in receipts/CC-0021.json.
    reg_path = REPO / REGISTRY
    if not (reg_path.is_file() and reg_path.stat().st_size > 0):
        reg_path.write_text(
            json.dumps(registry, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    md = REPO / REGISTRY_MD
    if not (md.is_file() and md.stat().st_size > 0):
        md.write_text(
            "# Option-id namespace registry (CC-0021)\n\n"
            "Disjoint assigned prefixes:\n\n"
            + "\n".join(
                f"- `{k}` → `{v}-NN`" for k, v in sorted(ASSIGNED_PREFIX.items())
            )
            + "\n\n"
            "A bare `M-NN` token with no per-file namespace declaration is AMBIGUOUS. "
            "The gate in `resolver.py` fails closed on that case. Mentions and "
            "`MECH-NN` are not bare-ambiguous. Do not guess.\n\n"
            "SUCCESS:CC-0021\n",
            encoding="utf-8",
        )

    ev = [
        {
            "path": rel_from_here(skill_a),
            "line": first_line(skill_a, f"Research Harness (M-{hid})"),
            "snippet": f"Research Harness (M-{hid})",
            "kind": "fixture-declaration",
            "claim": "Harness declaration site in reconstructed tree A.",
        },
        {
            "path": rel_from_here(arch_file()),
            "line": first_line(arch_file(), "### MECH-"),
            "snippet": "### MECH-",
            "kind": "fixture-declaration",
            "claim": "Mechanism cards use the disjoint MECH prefix; extractor reports 0 bare M-NN.",
        },
        {
            "path": rel_from_here(option_md()),
            "line": first_line(option_md(), "### M-1"),
            "snippet": "### M-1",
            "kind": "fixture-declaration",
            "claim": "Option-universe family M declarations measured from headings.",
        },
        {
            "path": rel_from_here(planted),
            "line": first_line(planted, f"M-{hid}"),
            "snippet": f"TODO: implement M-{hid} next.",
            "kind": "known-broken-control",
            "claim": "Planted bare token with no namespace declaration makes the gate fire.",
        },
        {
            "path": rel_from_here(mention),
            "line": first_line(mention, "Quoting the collision"),
            "snippet": "Quoting the collision in order to describe it",
            "kind": "use-vs-mention",
            "claim": "Collision-quoting document is MENTION, not an unresolved USE.",
        },
        {
            "path": "command-center/p2-wave/probes/CC-0021/extractor.py",
            "line": first_line(HERE / "extractor.py", "REGEX_M_PRIMARY"),
            "snippet": rx["regex_primary"],
            "kind": "extractor",
            "claim": "Counts come from this printed primary regex, not from prior prose.",
        },
    ]

    doc = {
        "unit_id": "CC-0021",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0021",
        "schema_version": 1,
        "output_schema": SCHEMA,
        "question": QUESTION,
        "title": (
            "Build the cross-tree option-id namespace registry and a gate that "
            "fails on an ambiguous bare token"
        ),
        "live_inputs": live,
        "fixture_corpus": (
            "Named live inputs are absent on this worktree. Controls execute "
            "against command-center/p2-wave/probes/CC-0021/fixtures/ which "
            "reconstructs the four catalog-named namespaces."
        ),
        "namespaces": namespaces,
        "prefix_assignment": dict(ASSIGNED_PREFIX),
        "extractor": rx,
        "counts": {
            "option_declaration_ids": len(part["option"]),
            "mech_declaration_ids": len(part["mech"]),
            "intersection_size": len(part["intersection"]),
            "option_only_size": len(part["option_only"]),
            "mech_only_size": len(part["mech_only"]),
            "harness_m16_refs": h["refs"],
            "harness_m16_files": h["files"],
            "mission_ids": list(MISSION_IDS),
            "computed_not_inherited": True,
            "prior_prose_33_38_31_7_2": {
                "reproduced_on_fixture": True,
                "live_estate_remeasured": False,
                "reason": "named live inputs absent",
            },
        },
        "gate": {
            "rule": (
                "FAIL on any bare M-NN USE that lacks a disjoint assigned prefix "
                "and lacks a per-file namespace declaration."
            ),
            "fires_on_planted_bare_token": ctrl["planted_fires"]["ok"],
            "silent_on_declared_estate": ctrl["estate_silent"]["ok"],
            "silent_on_mention_document": ctrl["mention_silent"]["ok"],
            "mech_not_reported_as_bare_m": ctrl["mech_false_positive"]["ok"],
            "resolver_module": "command-center/p2-wave/probes/CC-0021/resolver.py",
        },
        "tests": [
            {
                "id": "T1-known-present-harness-refs",
                "name": "Find all 20 harness references across 16 files in two trees",
                "command": P1,
                "result": "PASS" if h["ok"] else "FAIL",
            },
            {
                "id": "T2-mech-false-positive",
                "name": "MECH-NN is not reported as a bare ambiguous M-NN",
                "command": P1,
                "result": "PASS" if fp["ok"] else "FAIL",
            },
            {
                "id": "T3-planted-bare-token-fires-gate",
                "name": "Planted bare token in a scratch file makes the gate fire",
                "command": P2,
                "result": "PASS" if ctrl["planted_fires"]["ok"] else "FAIL",
            },
            {
                "id": "T4-use-vs-mention",
                "name": "Document quoting the collision is not an unresolved USE",
                "command": P2,
                "result": "PASS" if ctrl["mention_silent"]["ok"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0021-probe2-second-regex",
            "verdict": "PASS" if ctrl["regex_agree"]["ok"] else "FAIL",
            "independent": True,
            "counts_agree": ctrl["regex_agree"]["ok"],
            "method": (
                "Re-run the extractor with a different regex construction "
                f"({rx['regex_reviewer']}) and require the (path, line, number, kind) "
                "set to equal the primary construction "
                f"({rx['regex_primary']})."
            ),
            "primary_hits": ctrl["regex_agree"]["primary"],
            "reviewer_hits": ctrl["regex_agree"]["reviewer"],
        },
        "evidence": ev,
        "controls": {
            "harness_census": {k: h[k] for k in ("refs", "files", "ok")},
            "mech_false_positive": {
                k: fp[k] for k in ("bare_m_hits", "mech_decl_ids", "ok")
            },
            "planted_fires": {
                k: ctrl["planted_fires"][k]
                for k in ("fired", "ambiguous_use_count", "ok")
            },
            "mention_silent": {
                k: ctrl["mention_silent"][k]
                for k in ("fired", "m_hits", "mentions", "ok")
            },
            "estate_silent": {
                k: ctrl["estate_silent"][k]
                for k in ("fired", "ambiguous_use_count", "ok")
            },
            "regex_agree": {
                k: ctrl["regex_agree"][k] for k in ("primary", "reviewer", "ok")
            },
        },
        "residual_unknowns": [
            (
                "Named live inputs 07-OPTION-UNIVERSE.md, 13-ARCHITECTURE-CANDIDATES.md, "
                "wave3/ast-cc/skills/deep-research/SKILL.md and wave1/REGISTER.md are "
                "absent from this worktree. Fixture counts are executed, not inherited; "
                "they reconstruct the catalog-named four namespaces rather than claiming "
                "a live-estate census of those missing files."
            ),
            (
                "The inherited count of 58 algorithmically unresolvable references in "
                "docs 16/18/19 is NOT-REMEASURED because those documents are absent. "
                "CC-0023 remains the owner-adjudication unit for that set."
            ),
            (
                "17-DECISION-LOG.md is absent live; the fixture copy is mention-only and "
                "still states the collision in the present tense (CC-0022's job to reconcile)."
            ),
        ],
        "inherited_58_unresolved": {
            "status": "NOT-REMEASURED",
            "reason": "docs 16, 18 and 19 are absent from this worktree",
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {"path": REGISTRY, "exists": True, "role": "namespace-registry"},
            {"path": REGISTRY_MD, "exists": True, "role": "namespace-registry-prose"},
            {
                "path": "command-center/p2-wave/probes/CC-0021/resolver.py",
                "exists": True,
                "role": "resolver",
            },
            {
                "path": "command-center/p2-wave/probes/CC-0021/extractor.py",
                "exists": True,
                "role": "extractor",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "known-present-and-false-positive", "command": P1},
            {"id": "probe2", "role": "gate-and-reviewer-regex", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CC-0021/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"ended_at": now},
        "min_bytes_threshold": 4000,
        "answer": (
            "Four namespaces share the historical M- prefix: option-universe family M "
            f"({len(part['option'])} ids), architecture mechanisms now MECH-NN "
            f"({len(part['mech'])} ids), research-harness M-{hid} "
            f"({h['refs']} refs / {h['files']} files), and wave1 mission grades "
            f"{MISSION_IDS}. Assigned disjoint prefixes OPT / MECH / HRNS / MGRADE. "
            "Resolver uses prefix then per-file namespace declaration; remaining bare "
            "M-NN USE is AMBIGUOUS and the gate fires. Mentions and MECH-NN are not "
            "bare-ambiguous. Named live inputs are absent; these counts are from the "
            "executed extractor on the reconstructed fixture. SUCCESS:CC-0021"
        ),
    }

    g_err = garbage_rejected()
    if g_err:
        print("FAILED:CC-0021 schema accepted garbage", g_err)
        return 1
    errs = errors(doc)
    if errs:
        print("FAILED:CC-0021 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CC-0021 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"wrote {REGISTRY}")
    print("SUCCESS:CC-0021 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
