"""Research Harness (M-16): a thin orchestration layer over deep-research.

Four additive components on top of the ``/deep-research`` skill, plus a
preflight (mcp_doctor) step:

  * ``routing``  - capability -> ordered live-provider table + classifier.
  * ``cache``    - SHA-256 query-hash cache with per-capability TTL.
  * ``grading``  - deterministic source-confidence grading (A/B/C, High/Med/Low).
  * ``report``   - cited markdown report with numbered citations + provenance.
  * ``preflight``- provider liveness probe so we route only to live MCPs.
  * ``harness``  - pure glue tying preflight + routing into a research plan
                   (sub-question DAG + effort classes).

Reliability set (Lens 12; all stdlib, all offline):

  * ``budget``     - call/token/wall-clock budget with explore/converge/finalize.
  * ``checkpoint`` - append-only JSONL run ledger + resume-from-checkpoint.
  * ``loopguard``  - repeated-query / no-progress detection -> ``partial:loop``.
  * ``compact``    - keep-latest-3 raw tool outputs, digest older ones.
  * ``sufficiency``- per-sub-question sufficiency gate + one bounded follow-up.
  * ``conflicts``  - ``contradicted`` verdict + "Disputed" callouts.

Nothing here makes live network/MCP calls; provider calls and probes are
injected, so the package builds and tests fully offline.
"""

from .budget import EFFORT_CALLS, Budget, estimate_tokens
from .cache import (
    CacheResult,
    ResearchCacheEntry,
    fetch_with_cache,
    normalize_query,
    query_hash,
    read_cache,
    ttl_for,
    write_cache,
)
from .checkpoint import (
    Ledger,
    ResumeState,
    load_ledger,
    open_run,
    record_partial_report,
    record_subquestion_done,
    record_tool_output,
    resume,
    seal,
)
from .compact import compact_ledger, compact_outputs, should_compact
from .conflicts import Dispute, detect_conflict, resolve_claims
from .grading import (
    Grade,
    Source,
    grade_source,
    overall_confidence,
    source_tier,
)
from .harness import ResearchPlan, RoutingDecision, classify_effort, plan_research
from .loopguard import LoopGuard
from .preflight import (
    NO_RETRY_SERVERS,
    ProviderStatus,
    down_servers,
    live_servers,
    retry_allowed,
    routable_servers,
    run_preflight,
)
from .report import (
    REPORT_STATUSES,
    Citation,
    Claim,
    Methodology,
    Report,
    Theme,
    build_citations,
    render,
    summarize_statuses,
)
from .routing import (
    CAPABILITY_FALLBACKS,
    ROUTING_TABLE,
    Provider,
    classify_capability,
    is_excluded,
    is_metered,
    resolve_providers,
    resolve_with_fallback,
    route_subquestion,
)
from .sufficiency import GateDecision, gate, judge_sufficiency

__all__ = [
    "CAPABILITY_FALLBACKS",
    "EFFORT_CALLS",
    "NO_RETRY_SERVERS",
    "REPORT_STATUSES",
    "ROUTING_TABLE",
    "Budget",
    "CacheResult",
    "Citation",
    "Claim",
    "Dispute",
    "GateDecision",
    "Grade",
    "Ledger",
    "LoopGuard",
    "Methodology",
    "Provider",
    "ProviderStatus",
    "Report",
    "ResearchCacheEntry",
    "ResearchPlan",
    "ResumeState",
    "RoutingDecision",
    "Source",
    "Theme",
    "build_citations",
    "classify_capability",
    "classify_effort",
    "compact_ledger",
    "compact_outputs",
    "detect_conflict",
    "down_servers",
    "estimate_tokens",
    "fetch_with_cache",
    "gate",
    "grade_source",
    "is_excluded",
    "is_metered",
    "judge_sufficiency",
    "live_servers",
    "load_ledger",
    "normalize_query",
    "open_run",
    "overall_confidence",
    "plan_research",
    "query_hash",
    "read_cache",
    "record_partial_report",
    "record_subquestion_done",
    "record_tool_output",
    "render",
    "resolve_claims",
    "resolve_providers",
    "resolve_with_fallback",
    "resume",
    "retry_allowed",
    "routable_servers",
    "route_subquestion",
    "run_preflight",
    "seal",
    "should_compact",
    "source_tier",
    "summarize_statuses",
    "ttl_for",
    "write_cache",
]
