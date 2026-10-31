"""Phase 1 corpus normalization + mechanism-level deduplication.

Modules
-------
extract    : deterministic parsers, one per corpus record class -> raw records
mechanism  : mechanism signature derivation (artifact set x verb class x locus)
dedup      : signature-based duplicate detection + support/contradiction edges
rank       : evidence/convergence/severity/impact ranking (NOT repetition count)
build      : driver that writes CANONICAL-CLAIMS.json + .md
"""

__all__ = ["extract", "mechanism", "dedup", "rank", "build"]
