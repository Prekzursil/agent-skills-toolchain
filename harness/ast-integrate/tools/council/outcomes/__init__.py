"""Council outcomes: the closed outcome-kind set and the checks that keep it intact.

Submodules (import them directly for the full surface):

* :mod:`council.outcomes.kinds` -- closed outcome kinds, ``parse_outcome`` / ``required_fields_for``
* :mod:`council.outcomes.pipeline` -- identity-preserving outcome pipeline
* :mod:`council.outcomes.census` -- static census of downstream readers that collapse kinds
* :mod:`council.outcomes.dissent` -- dissent capture, attribution and synthesis with conservation ledgers
* :mod:`council.outcomes.unresolved` -- unresolved-question ledger with an executable experiment per entry
* :mod:`council.outcomes.lineage_export` -- decision lineage and supersession markers on overturn
* :mod:`council.outcomes.completeness` -- charter completeness (present AND non-vacuous)
* :mod:`council.outcomes.action_plan` -- decision to sequenced action plan with traceability

Only names that are unique across the package are re-exported here. ``census`` (a submodule and
a function in both ``census`` and ``completeness``), ``capture`` (``dissent`` and ``unresolved``)
and ``SCHEMA_REL`` (``unresolved`` and ``lineage_export``) are reached through their submodule.
"""
from __future__ import annotations

from . import action_plan, census, completeness, dissent, kinds, lineage_export, pipeline, unresolved
from .action_plan import (
    KIND_TO_TYPE,
    PlanError,
    agreed_id_set,
    dissent_id_set,
    inject_statement_mismatch,
    inject_unagreed_action,
    plan_from_decision,
    traceability_check,
    validate_action,
    validate_plan,
)
from .census import (
    ALL_KINDS,
    BINARY_LABELS,
    CLASS_COERCES,
    CLASS_NO_READER,
    CLASS_PRESERVES,
    CLASS_UNREADABLE,
    KIND_NAMES,
    PROTECTED_KINDS,
    assert_coercer_caught,
    classify_file,
    count_kinds,
)
from .completeness import (
    CHARTER_REQUIRED_OUTPUTS,
    VACUOUS_MUTANT_LABELS,
    check_artifact,
    complete_artifact,
    completeness_score,
    is_vacuous,
    load_recorded_fixtures,
    vacuity_reason,
    vacuous_mutants,
)
from .dissent import (
    AttributionError,
    ConservationError,
    Dissent,
    DissentPipeline,
    LedgerRow,
    PipelineResult,
    PresenceFailure,
    PresenceRow,
    aggregate_parent,
    attribute,
    conservation,
    dissents_from_artifact,
    drop_dissent,
    from_kernel_events,
    is_dissent_turn,
    presence_check,
    summarise_away,
    synthesise,
)
from .kinds import (
    KIND_CONDITIONAL,
    KIND_DECISION,
    KIND_NO_DECISION,
    KIND_PROOF_OF_IMPOSSIBILITY,
    REQUIRED,
    CollapseForbidden,
    OutcomeValidationError,
    parse_outcome,
    required_fields_for,
)
from .lineage_export import (
    LINEAGE_RECORD_SCHEMA,
    STATUS_LIVE,
    STATUS_SUPERSEDED,
    ContradictionPair,
    ContradictionScan,
    LineageSchemaError,
    append_binding,
    build_record,
    commit_overturn,
    empty_log,
    load_log,
    mark_predecessor,
    question_key,
    save_log,
    scan_live_contradictions,
    validate_record,
)
from .pipeline import outcome_unmodified, payload_fingerprint, run_pipeline
from .unresolved import (
    ENTRY_SCHEMA,
    STOPPING_CONDITION_ID,
    audit_entry,
    audit_ledger,
    schema_errors,
    schema_errors_entry,
    stopping_condition_15,
)

__all__ = [
    # submodules
    "action_plan",
    "census",
    "completeness",
    "dissent",
    "kinds",
    "lineage_export",
    "pipeline",
    "unresolved",
    # kinds
    "KIND_CONDITIONAL",
    "KIND_DECISION",
    "KIND_NO_DECISION",
    "KIND_PROOF_OF_IMPOSSIBILITY",
    "REQUIRED",
    "CollapseForbidden",
    "OutcomeValidationError",
    "parse_outcome",
    "required_fields_for",
    # pipeline
    "outcome_unmodified",
    "payload_fingerprint",
    "run_pipeline",
    # census
    "ALL_KINDS",
    "BINARY_LABELS",
    "CLASS_COERCES",
    "CLASS_NO_READER",
    "CLASS_PRESERVES",
    "CLASS_UNREADABLE",
    "KIND_NAMES",
    "PROTECTED_KINDS",
    "assert_coercer_caught",
    "classify_file",
    "count_kinds",
    # dissent
    "AttributionError",
    "ConservationError",
    "Dissent",
    "DissentPipeline",
    "LedgerRow",
    "PipelineResult",
    "PresenceFailure",
    "PresenceRow",
    "aggregate_parent",
    "attribute",
    "conservation",
    "dissents_from_artifact",
    "drop_dissent",
    "from_kernel_events",
    "is_dissent_turn",
    "presence_check",
    "summarise_away",
    "synthesise",
    # unresolved
    "ENTRY_SCHEMA",
    "STOPPING_CONDITION_ID",
    "audit_entry",
    "audit_ledger",
    "schema_errors",
    "schema_errors_entry",
    "stopping_condition_15",
    # lineage_export
    "LINEAGE_RECORD_SCHEMA",
    "STATUS_LIVE",
    "STATUS_SUPERSEDED",
    "ContradictionPair",
    "ContradictionScan",
    "LineageSchemaError",
    "append_binding",
    "build_record",
    "commit_overturn",
    "empty_log",
    "load_log",
    "mark_predecessor",
    "question_key",
    "save_log",
    "scan_live_contradictions",
    "validate_record",
    # completeness
    "CHARTER_REQUIRED_OUTPUTS",
    "VACUOUS_MUTANT_LABELS",
    "check_artifact",
    "complete_artifact",
    "completeness_score",
    "is_vacuous",
    "load_recorded_fixtures",
    "vacuity_reason",
    "vacuous_mutants",
    # action_plan
    "KIND_TO_TYPE",
    "PlanError",
    "agreed_id_set",
    "dissent_id_set",
    "inject_statement_mismatch",
    "inject_unagreed_action",
    "plan_from_decision",
    "traceability_check",
    "validate_action",
    "validate_plan",
]
