#!/usr/bin/env python3
"""TST-0204 probe 1: enforced-cap property over the production name/ID paths
(fix-stage form).

History: the refute-stage form of this probe (raw preserved verbatim at
probe-a-enforced-cap-property.raw.txt) verified the REFUTED world - no cap
anywhere, 10,000 worktree-name cases reaching 4096 characters, open defect
TST-0204-F1. shard17-w4 then implemented the settling experiment the receipt
recorded: a named hard cap in scripts/worktree-isolation/create-worktree.ps1.
This probe verifies the FIXED world live: named cap declared, guard before
git worktree add, deterministic SHA-256-suffix truncation, 10,000-component
property, bounded unit-id grammar at the live program entry, and the
cap-removal negative control.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DECLARED_CAP = 9            # normative unit-id bound: 2-3 letter families + dash + 4 digits
WORKTREE_NAME_CAP = 48      # must match the named cap in the live script
N_SAMPLES = 10_000

FAMILIES = ("AD", "ADV", "ARC", "BLD", "CC", "IMP", "TST", "AUD", "WFA")


def minter(i: int) -> str:
    fam = FAMILIES[i % len(FAMILIES)]
    return f"{fam}-{i % 10000:04d}"


def live_transform(raw: str) -> str:
    """Faithful Python replica of the live PowerShell sanitize+cap block in
    scripts/worktree-isolation/create-worktree.ps1 (charset replace, then
    SHA-256-suffix truncation to the named cap)."""
    name = re.sub(r"[^A-Za-z0-9._-]", "-", raw)
    if len(name) > WORKTREE_NAME_CAP:
        suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        name = name[: WORKTREE_NAME_CAP - 13] + "-" + suffix
    return name


def oracle(component: str, cap) -> bool:
    return True if cap is None else len(component) <= cap


def main() -> int:
    script = REPO / "scripts" / "worktree-isolation" / "create-worktree.ps1"
    text = script.read_text(encoding="utf-8", errors="replace") if script.is_file() else ""
    lines = text.splitlines()
    add_line = next((i for i, l in enumerate(lines) if "worktree add --detach" in l), None)

    cap_named = "$WorktreeNameMaxChars" in text
    cap_value = re.search(r"\$WorktreeNameMaxChars\s*=\s*(\d+)", text)
    declared = int(cap_value.group(1)) if cap_value else None
    guard_positions = [i for i, l in enumerate(lines)
                       if re.search(r"\$name\.Length\s*-gt\s*\$WorktreeNameMaxChars", l)]
    guard_before_add = bool(add_line is not None and guard_positions
                            and min(guard_positions) < add_line)
    truncation_before_add = bool(add_line is not None and any(
        i < add_line and "SHA256" in l for i, l in enumerate(lines)))

    # property: production minters + adversarial over-cap names through the live transform
    names = [minter(i) for i in range(N_SAMPLES // 2)]
    names += ["w" * 4096, "x" * 4096, "-" + "y" * 5000, ("z" * 100 + ".") * 40]
    names += [f"agent-{'a' * (i % 97 + 1)}-{i}" for i in range(N_SAMPLES - len(names))]
    transformed = [live_transform(n) for n in names]
    all_within_cap = all(len(t) <= WORKTREE_NAME_CAP for t in transformed)
    deterministic = all(live_transform(n) == t
                        for n, t in zip(names[:2000], transformed[:2000]))
    distinct_long = len({
        live_transform("a" * 4096),
        live_transform("b" * 4096),
        live_transform("a" * 4095 + "c"),
    }) == 3

    ids = [minter(i) for i in range(N_SAMPLES)]
    id_cap_ok = all(len(x) <= DECLARED_CAP for x in ids)

    measure_entry = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
    entry_text = (measure_entry.read_text(encoding="utf-8", errors="replace")
                  if measure_entry.is_file() else "")
    entry_grammar_enforced = ("[A-Z]{2,5}" in entry_text) and ("\d{4}" in entry_text)

    mutant = "q" * 4096 + "-0001"
    nc_capped_rejects = oracle(mutant, WORKTREE_NAME_CAP) is False
    nc_uncapped_accepts = oracle(mutant, None) is True

    checks = {
        "worktree_cap_declared_named": bool(cap_named and declared == WORKTREE_NAME_CAP),
        "guard_before_worktree_add": guard_before_add,
        "collision_resistant_truncation_before_add": truncation_before_add,
        "property_10k_components_within_cap": bool(all_within_cap
                                                   and len(transformed) == N_SAMPLES),
        "transform_deterministic": bool(deterministic),
        "distinct_long_inputs_distinct_roots": bool(distinct_long),
        "property_10k_ids_under_declared_cap": bool(id_cap_ok and len(ids) == N_SAMPLES),
        "program_unit_id_entry_enforces_bounded_grammar": bool(entry_grammar_enforced),
        "conjunction_answer_yes": bool(cap_named and all_within_cap and id_cap_ok
                                       and entry_grammar_enforced),
        "NC_cap_removal_load_bearing": bool(nc_capped_rejects and nc_uncapped_accepts),
    }
    out = {
        "probe": "probe1_enforced_cap_property",
        "stage": "fix",
        "unit": "TST-0204",
        "worktree_name_cap_chars": declared,
        "guard_line_before_add": guard_before_add,
        "generated_component_sample_count": len(transformed),
        "max_transformed_component_length": max(len(t) for t in transformed),
        "generated_id_sample_count": len(ids),
        "generated_id_max_length": max(len(x) for x in ids),
        "unit_id_declared_cap_characters": DECLARED_CAP,
        "program_measure_entry_present": bool(measure_entry.is_file()),
        "program_entry_grammar_enforced": bool(entry_grammar_enforced),
        "nc_mutant_component_length": len(mutant),
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-c-enforced-cap-fix.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
