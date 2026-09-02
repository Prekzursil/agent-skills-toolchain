"""CNF-0093 scenarios: holding partition, three planted leak paths, control."""
from __future__ import annotations

import json
from pathlib import Path

import partition_runtime as PR

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def all_specs() -> dict[str, dict]:
    return {
        "holding": PR.spec_holding(),
        "leak-shared-transcript": PR.spec_leak_transcript(),
        "leak-synthesis-paraphrase": PR.spec_leak_synthesis(),
        "leak-tool-results": PR.spec_leak_tools(),
        "redaction-disabled": PR.spec_redaction_disabled(),
    }


def build_fixtures() -> dict[str, dict]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    assembled = {}
    for name, spec in all_specs().items():
        run = PR.assemble(spec)
        assembled[name] = run
        (FIXTURES / f"{name}.json").write_text(
            json.dumps(run, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    index = {
        "lattice_id": PR.LATTICE_ID,
        "owning_seat": PR.OWNING_SEAT,
        "non_owning_seats": list(PR.NON_OWNING),
        "unpartitioned_field": PR.UNPARTITIONED_FIELD,
        "runs": sorted(assembled),
    }
    (FIXTURES / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return assembled
