#!/usr/bin/env python3
"""Published idea-pair gold set for TST-0266.

Labels are duplicate / variant / distinct. Adversarial rows are near-duplicates
that differ only in a load-bearing qualifier and MUST be labelled distinct.

Split is frozen here: even numeric ids are tune, odd ids are held-out, so
thresholds cannot be fitted to the kappa half.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLD_PATH = HERE / "fixtures" / "gold_set.json"

# (id, idea_a, idea_b, label, adversarial, qualifier_note)
_ROWS: list[tuple[str, str, str, str, bool, str]] = [
    # --- duplicates: paraphrases of one idea, same load-bearing parameters ---
    (
        "g-001",
        "Cache HTTP responses in Redis",
        "Store HTTP responses in a Redis cache",
        "duplicate",
        False,
        "",
    ),
    (
        "g-002",
        "Add a CLI flag for verbose logs",
        "Add a --verbose command-line option for debug logging",
        "duplicate",
        False,
        "",
    ),
    (
        "g-003",
        "Retry failed API calls with exponential backoff",
        "Use exponential backoff when retrying failed API requests",
        "duplicate",
        False,
        "",
    ),
    (
        "g-004",
        "Compress log files with gzip before archival",
        "Gzip-compress logs prior to archiving them",
        "duplicate",
        False,
        "",
    ),
    (
        "g-005",
        "Run database migrations in a transaction",
        "Apply schema migrations inside a database transaction",
        "duplicate",
        False,
        "",
    ),
    (
        "g-006",
        "Hash passwords with bcrypt",
        "Use bcrypt to hash user passwords",
        "duplicate",
        False,
        "",
    ),
    (
        "g-007",
        "Rate-limit login attempts per IP address",
        "Throttle authentication tries by source IP",
        "duplicate",
        False,
        "",
    ),
    (
        "g-008",
        "Emit structured JSON logs",
        "Write logs as structured JSON records",
        "duplicate",
        False,
        "",
    ),
    (
        "g-009",
        "Pin GitHub Actions to a commit SHA",
        "Pin CI GitHub Action versions to commit SHAs",
        "duplicate",
        False,
        "",
    ),
    (
        "g-010",
        "Serve static assets through a CDN",
        "Deliver static files via a content delivery network",
        "duplicate",
        False,
        "",
    ),
    (
        "g-011",
        "Validate JWT expiry on every request",
        "Check that JSON Web Tokens have not expired on each request",
        "duplicate",
        False,
        "",
    ),
    (
        "g-012",
        "Use parameterized SQL queries",
        "Bind SQL parameters instead of concatenating query strings",
        "duplicate",
        False,
        "",
    ),
    (
        "g-013",
        "Ship a health-check HTTP endpoint",
        "Expose an HTTP health check route",
        "duplicate",
        False,
        "",
    ),
    (
        "g-014",
        "Store session tokens in HttpOnly cookies",
        "Put session tokens in cookies marked HttpOnly",
        "duplicate",
        False,
        "",
    ),
    (
        "g-015",
        "Document the public API with OpenAPI",
        "Publish an OpenAPI specification for the public API",
        "duplicate",
        False,
        "",
    ),
    (
        "g-016",
        "Fail CI when test coverage drops",
        "Make the CI pipeline fail if coverage decreases",
        "duplicate",
        False,
        "",
    ),
    (
        "g-017",
        "Rotate encryption keys on a schedule",
        "Schedule periodic rotation of encryption keys",
        "duplicate",
        False,
        "",
    ),
    (
        "g-018",
        "Index the events table on created_at",
        "Add a created_at index to the events table",
        "duplicate",
        False,
        "",
    ),
    (
        "g-019",
        "Redact secrets from application logs",
        "Strip secrets out of app log output",
        "duplicate",
        False,
        "",
    ),
    (
        "g-020",
        "Prefetch the next page of search results",
        "Eagerly load the following page of search results",
        "duplicate",
        False,
        "",
    ),
    # --- variants: same core idea, extra non-load-bearing scope or audience ---
    (
        "g-021",
        "Cache HTTP responses in Redis",
        "Cache HTTP responses in Redis for the marketing site",
        "variant",
        False,
        "",
    ),
    (
        "g-022",
        "Add a CLI flag for verbose logs",
        "Add a CLI flag for verbose logs in the operator handbook",
        "variant",
        False,
        "",
    ),
    (
        "g-023",
        "Retry failed API calls with exponential backoff",
        "Retry failed API calls with exponential backoff in the billing client",
        "variant",
        False,
        "",
    ),
    (
        "g-024",
        "Compress log files with gzip before archival",
        "Compress application log files with gzip before archival",
        "variant",
        False,
        "",
    ),
    (
        "g-025",
        "Run database migrations in a transaction",
        "Run production database migrations in a transaction",
        "variant",
        False,
        "",
    ),
    (
        "g-026",
        "Hash passwords with bcrypt",
        "Hash customer passwords with bcrypt",
        "variant",
        False,
        "",
    ),
    (
        "g-027",
        "Rate-limit login attempts per IP address",
        "Rate-limit login attempts per IP address on the public site",
        "variant",
        False,
        "",
    ),
    (
        "g-028",
        "Emit structured JSON logs",
        "Emit structured JSON logs from worker processes",
        "variant",
        False,
        "",
    ),
    (
        "g-029",
        "Pin GitHub Actions to a commit SHA",
        "Pin GitHub Actions to a commit SHA in the release workflow",
        "variant",
        False,
        "",
    ),
    (
        "g-030",
        "Serve static assets through a CDN",
        "Serve static marketing assets through a CDN",
        "variant",
        False,
        "",
    ),
    (
        "g-031",
        "Validate JWT expiry on every request",
        "Validate JWT expiry on every API request",
        "variant",
        False,
        "",
    ),
    (
        "g-032",
        "Use parameterized SQL queries",
        "Use parameterized SQL queries in the reporting module",
        "variant",
        False,
        "",
    ),
    (
        "g-033",
        "Ship a health-check HTTP endpoint",
        "Ship a health-check HTTP endpoint on the edge proxy",
        "variant",
        False,
        "",
    ),
    (
        "g-034",
        "Store session tokens in HttpOnly cookies",
        "Store session tokens in HttpOnly cookies for the web app",
        "variant",
        False,
        "",
    ),
    (
        "g-035",
        "Document the public API with OpenAPI",
        "Document the public REST API with OpenAPI",
        "variant",
        False,
        "",
    ),
    (
        "g-036",
        "Fail CI when test coverage drops",
        "Fail CI when test coverage drops on the main branch",
        "variant",
        False,
        "",
    ),
    (
        "g-037",
        "Rotate encryption keys on a schedule",
        "Rotate encryption keys on a schedule for the payments service",
        "variant",
        False,
        "",
    ),
    (
        "g-038",
        "Index the events table on created_at",
        "Index the events table on created_at in the analytics replica",
        "variant",
        False,
        "",
    ),
    (
        "g-039",
        "Redact secrets from application logs",
        "Redact secrets from application logs in staging",
        "variant",
        False,
        "",
    ),
    (
        "g-040",
        "Prefetch the next page of search results",
        "Prefetch the next page of search results on mobile clients",
        "variant",
        False,
        "",
    ),
    # --- distinct: different ideas (not near-duplicates) ---
    (
        "g-041",
        "Cache HTTP responses in Redis",
        "Use a write-ahead log for crash recovery",
        "distinct",
        False,
        "",
    ),
    (
        "g-042",
        "Hash passwords with bcrypt",
        "Shard the primary database by tenant id",
        "distinct",
        False,
        "",
    ),
    (
        "g-043",
        "Pin GitHub Actions to a commit SHA",
        "Move billing to a separate PostgreSQL schema",
        "distinct",
        False,
        "",
    ),
    (
        "g-044",
        "Emit structured JSON logs",
        "Adopt an event-sourced ledger for inventory",
        "distinct",
        False,
        "",
    ),
    (
        "g-045",
        "Ship a health-check HTTP endpoint",
        "Train a ranking model on click logs",
        "distinct",
        False,
        "",
    ),
    (
        "g-046",
        "Document the public API with OpenAPI",
        "Introduce a dead-letter queue for failed jobs",
        "distinct",
        False,
        "",
    ),
    (
        "g-047",
        "Rotate encryption keys on a schedule",
        "Replace the monolith UI with a native desktop client",
        "distinct",
        False,
        "",
    ),
    (
        "g-048",
        "Prefetch the next page of search results",
        "Migrate DNS to a second registrar as a failover",
        "distinct",
        False,
        "",
    ),
    # --- adversarial distinct: near-duplicates, load-bearing qualifier differs ---
    (
        "g-049",
        "Encrypt data at rest with AES-256",
        "Encrypt data at rest with AES-128",
        "distinct",
        True,
        "cipher key size",
    ),
    (
        "g-050",
        "Retry failed jobs 3 times",
        "Retry failed jobs 30 times",
        "distinct",
        True,
        "retry count",
    ),
    (
        "g-051",
        "Collect telemetry with opt-in consent",
        "Collect telemetry with opt-out consent",
        "distinct",
        True,
        "consent polarity",
    ),
    (
        "g-052",
        "Set session TTL to 15 minutes",
        "Set session TTL to 15 hours",
        "distinct",
        True,
        "TTL unit",
    ),
    (
        "g-053",
        "Allow CORS from https://app.example.com",
        "Deny CORS from https://app.example.com",
        "distinct",
        True,
        "allow vs deny",
    ),
    (
        "g-054",
        "Require TLS 1.3 for all inbound traffic",
        "Require TLS 1.2 for all inbound traffic",
        "distinct",
        True,
        "TLS version",
    ),
    (
        "g-055",
        "Keep 7 days of backups",
        "Keep 90 days of backups",
        "distinct",
        True,
        "retention count",
    ),
    (
        "g-056",
        "Enable debug mode in production",
        "Disable debug mode in production",
        "distinct",
        True,
        "enable vs disable",
    ),
    (
        "g-057",
        "Use SHA-256 for artifact checksums",
        "Use SHA-1 for artifact checksums",
        "distinct",
        True,
        "hash algorithm",
    ),
    (
        "g-058",
        "Cap request body size at 1 MB",
        "Cap request body size at 100 MB",
        "distinct",
        True,
        "body size",
    ),
    (
        "g-059",
        "Run the canary at 1 percent of traffic",
        "Run the canary at 50 percent of traffic",
        "distinct",
        True,
        "canary share",
    ),
    (
        "g-060",
        "Bind the service to 127.0.0.1",
        "Bind the service to 0.0.0.0",
        "distinct",
        True,
        "bind address",
    ),
]


def _split_for(pair_id: str) -> str:
    n = int(pair_id.split("-")[1])
    return "tune" if n % 2 == 0 else "heldout"


def pairs() -> list[dict]:
    out = []
    for pair_id, a, b, label, adv, note in _ROWS:
        out.append(
            {
                "id": pair_id,
                "idea_a": a,
                "idea_b": b,
                "label": label,
                "adversarial": adv,
                "qualifier_note": note,
                "split": _split_for(pair_id),
            }
        )
    return out


def gold_document() -> dict:
    rows = pairs()
    return {
        "unit_id": "TST-0266",
        "kappa_floor_preregistered": 0.40,
        "kappa_floor_recorded_at": "2026-08-24T00:00:00Z",
        "kappa_floor_recorded_before_any_score": True,
        "split_rule": "even numeric id -> tune; odd numeric id -> heldout",
        "label_set": ["duplicate", "variant", "distinct"],
        "n": len(rows),
        "n_tune": sum(1 for r in rows if r["split"] == "tune"),
        "n_heldout": sum(1 for r in rows if r["split"] == "heldout"),
        "n_adversarial": sum(1 for r in rows if r["adversarial"]),
        "pairs": rows,
    }


def dump_gold() -> Path:
    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = gold_document()
    GOLD_PATH.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return GOLD_PATH


def load_gold() -> dict:
    if GOLD_PATH.is_file():
        return json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    return gold_document()


if __name__ == "__main__":
    path = dump_gold()
    doc = load_gold()
    print(f"wrote {path} n={doc['n']} tune={doc['n_tune']} heldout={doc['n_heldout']}")
