"""IMP-0230 package marker: blueprint-authoring/v1 contract + scaffold.

Re-exports the registration gate and the scaffold generator so consumers can
`from tools.blueprint_contract import ...` with the repo root on sys.path.
"""
from tools.blueprint_contract.contract import (
    CONTRACT_ID,
    REQUIRED_ELEMENTS,
    VIOLATION_IDS,
    GateResult,
    register_blueprint,
    run_declared_smoke,
    validate_blueprint,
)
from tools.blueprint_contract.scaffold import (
    SCAFFOLD_ID,
    dump_blueprint,
    emit_scaffold,
    scaffold_blueprint,
)

__all__ = [
    "CONTRACT_ID",
    "REQUIRED_ELEMENTS",
    "VIOLATION_IDS",
    "GateResult",
    "register_blueprint",
    "run_declared_smoke",
    "validate_blueprint",
    "SCAFFOLD_ID",
    "dump_blueprint",
    "emit_scaffold",
    "scaffold_blueprint",
]
