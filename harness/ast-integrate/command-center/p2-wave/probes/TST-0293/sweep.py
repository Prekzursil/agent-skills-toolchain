"""Run the 64-preset sweep plus timeout and completeness negative controls."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from presets import NAMED_AT_11200_11225, all_presets, distinctness_key, timeout_fixture
from simulate import completeness_ok, simulate
from validate import validate_all


def sweep(seed: int = 0) -> dict[str, Any]:
    specs = all_presets()
    schema = validate_all()
    runs = [simulate(spec, seed=seed) for spec in specs]
    table = [
        {
            "name": r["preset_id"],
            "protocol": r["protocol_name"],
            "family": r["family"],
            "named": r["named_at_11200_11225"],
            "terminal_state": r["terminal_state"],
            "wall_clock_ms": r["wall_clock_ms"],
            "rounds_used": r["rounds_used"],
            "row_result": r["row_result"],
            "outputs_present": r["outputs_present"],
            "outputs_missing": r["outputs_missing"],
        }
        for r in runs
    ]
    fingerprints = [distinctness_key(s) for s in specs]
    seen: set[tuple] = set()
    uniq_dupes: list[tuple] = []
    counts: dict[tuple, int] = {}
    for fp in fingerprints:
        counts[fp] = counts.get(fp, 0) + 1
    for fp, n in counts.items():
        if n > 1 and fp not in seen:
            seen.add(fp)
            uniq_dupes.append(fp)

    timeout_run = simulate(timeout_fixture(), seed=seed)
    mutant = deepcopy(runs[0])
    mutant["outputs"]["dissent"] = []
    mutant["outputs_present"]["dissent"] = False
    mutant["outputs_missing"] = ["dissent"]
    mutant_complete = completeness_ok(mutant)

    named_in_table = {row["name"] for row in table if row["named"]}
    named_missing = sorted(set(NAMED_AT_11200_11225) - {row["name"] for row in table})

    all_done = all(r["terminal_state"] == "DONE" for r in runs)
    all_complete = all(completeness_ok(r) for r in runs)
    pass_ok = (
        schema["n_presets"] == 64
        and schema["n_schema_ok"] == 64
        and schema["named_coverage_ok"]
        and schema["negative_control"]["fired"]
        and all_done
        and all_complete
        and not uniq_dupes
        and timeout_run["terminal_state"] == "TIMEOUT"
        and timeout_run["row_result"] == "FAILED"
        and mutant_complete is False
        and not named_missing
        and named_in_table == set(NAMED_AT_11200_11225)
    )
    return {
        "n": len(runs),
        "all_terminal_done": all_done,
        "all_outputs_complete": all_complete,
        "schema": {
            "n_ok": schema["n_schema_ok"],
            "n": schema["n_presets"],
            "named_missing": schema["named_missing"],
            "negative_fired": schema["negative_control"]["fired"],
        },
        "distinctness_collisions": [list(fp) for fp in uniq_dupes[:5]],
        "timeout_control": {
            "id": timeout_run["preset_id"],
            "terminal_state": timeout_run["terminal_state"],
            "row_result": timeout_run["row_result"],
            "fired": timeout_run["terminal_state"] == "TIMEOUT",
        },
        "missing_output_control": {
            "complete": mutant_complete,
            "fired": mutant_complete is False,
        },
        "named_in_table_missing": named_missing,
        "table": table,
        "runs": runs,
        "pass": pass_ok,
        "live_model_arm": {
            "status": "NOT-RUN",
            "reason": "owner-gated paid quota; simulator arm is the delivery surface",
        },
        "substrate": {
            "tools_council_simulate_py": False,
            "local_simulator": "command-center/p2-wave/probes/TST-0293/simulate.py",
            "b05_library_on_tree": False,
            "note": "Presets instantiated in-probe from catalog-cited CNL names; production simulate.py absent.",
        },
    }
