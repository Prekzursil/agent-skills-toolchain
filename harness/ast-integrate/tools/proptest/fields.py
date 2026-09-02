"""Generated types and required fields for TST-0116 schemas."""
from __future__ import annotations

GENERATED_TYPES = ("work_unit", "receipt", "council_spec", "workflow_dag")
REQUIRED_BY_TYPE = {
    "work_unit": ("id", "output_path"),
    "receipt": ("unit_id", "state"),
    "council_spec": ("id", "seats"),
    "workflow_dag": ("id", "nodes", "edges"),
}
