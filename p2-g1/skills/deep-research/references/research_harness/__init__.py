"""Research Harness (M-16): a thin orchestration layer over deep-research.

Four additive components on top of the ``/deep-research`` skill, plus a
preflight (mcp_doctor) step:

  * ``routing``  - capability -> ordered live-provider table + classifier.
  * ``cache``    - SHA-256 query-hash cache with per-capability TTL.
  * ``grading``  - deterministic source-confidence grading (A/B/C, High/Med/Low).
  * ``report``   - cited markdown report with numbered citations + provenance.
  * ``preflight``- provider liveness probe so we route only to live MCPs.
  * ``harness``  - pure glue tying preflight + routing into a research plan.

Nothing here makes live network/MCP calls; provider calls and probes are
injected, so the package builds and tests fully offline.
"""

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
from .grading import (
    Grade,
    Source,
    grade_source,
    overall_confidence,
    source_tier,
)
from .harness import ResearchPlan, RoutingDecision, plan_research
from .preflight import (
    ProviderStatus,
    down_servers,
    live_servers,
    routable_servers,
    run_preflight,
)
from .report import (
    Citation,
    Claim,
    Methodology,
    Report,
    Theme,
    build_citations,
    render,
)
from .routing import (
    ROUTING_TABLE,
    Provider,
    classify_capability,
    is_excluded,
    resolve_providers,
    route_subquestion,
)

__all__ = [
    "ROUTING_TABLE",
    "CacheResult",
    "Citation",
    "Claim",
    "Grade",
    "Methodology",
    "Provider",
    "ProviderStatus",
    "Report",
    "ResearchCacheEntry",
    "ResearchPlan",
    "RoutingDecision",
    "Source",
    "Theme",
    "build_citations",
    "classify_capability",
    "down_servers",
    "fetch_with_cache",
    "grade_source",
    "is_excluded",
    "live_servers",
    "normalize_query",
    "overall_confidence",
    "plan_research",
    "query_hash",
    "read_cache",
    "render",
    "resolve_providers",
    "routable_servers",
    "route_subquestion",
    "run_preflight",
    "source_tier",
    "ttl_for",
    "write_cache",
]
