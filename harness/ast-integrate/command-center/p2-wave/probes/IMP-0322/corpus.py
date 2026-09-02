"""Fifteen recorded councils plus a labelled repetition-vs-refinement sample.

These are constructed recordings with known labels. They are the measurement
corpus for IMP-0322, not a live production harvest.
"""
from __future__ import annotations

from typing import Any


def _c(
    cid: str,
    text: str,
    *,
    family: str | None = None,
    refinement_of: str | None = None,
    qualifiers: list[str] | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"text": text}
    if cid:
        d["claim_id"] = cid
    if family:
        d["family_id"] = family
    if refinement_of:
        d["refinement_of"] = refinement_of
    if qualifiers:
        d["qualifiers"] = list(qualifiers)
    return d


def _e(eid: str, source: str, quote: str) -> dict[str, Any]:
    return {"evidence_id": eid, "source": source, "quote": quote}


def _r(n: int, claims: list[dict[str, Any]], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"round": n, "claims": claims, "evidence": list(evidence or [])}


def recorded_councils() -> list[dict[str, Any]]:
    """15 councils: 8 looping (must FIRE) and 7 productive/refining (must stay silent)."""
    return [
        {
            "id": "C01-loop-paraphrase",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Deploy the payment API behind a feature flag", family="f1")],
                   [_e("e1", "runbook", "feature flags required for public APIs")]),
                _r(2, [_c("", "The payment API should be deployed behind a feature flag", family="f1")]),
                _r(3, [_c("", "Payment API deployment belongs behind a feature flag", family="f1")]),
                _r(4, [_c("", "Put the payment API behind a feature flag for deploy", family="f1")]),
            ],
        },
        {
            "id": "C02-loop-verbatim",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Keep the ledger append-only", family="led")],
                   [_e("e1", "spec", "append-only log")]),
                _r(2, [_c("c1", "Keep the ledger append-only", family="led")]),
                _r(3, [_c("c1", "Keep the ledger append-only", family="led")]),
                _r(4, [_c("c1", "Keep the ledger append-only", family="led")]),
            ],
        },
        {
            "id": "C03-two-claim-cycle",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [
                    _c("a", "Prefer majority vote when evidence is tied", family="a"),
                    _c("b", "Require a recorded dissent before closing", family="b"),
                ], [_e("e1", "charter", "dissent must be recorded")]),
                _r(2, [
                    _c("", "When evidence is tied, prefer majority vote", family="a"),
                    _c("", "Closing requires a recorded dissent", family="b"),
                ]),
                _r(3, [
                    _c("", "Majority vote is preferred on tied evidence", family="a"),
                    _c("", "A recorded dissent is required before close", family="b"),
                ]),
                _r(4, [
                    _c("", "Tied evidence should prefer the majority vote", family="a"),
                    _c("", "Do not close without a recorded dissent", family="b"),
                ]),
            ],
        },
        {
            "id": "C04-productive-then-stall",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Cache session tokens in memory", family="cache")],
                   [_e("e1", "latency", "in-memory cache is faster")]),
                _r(2, [_c("", "Cache session tokens in memory with a 5 minute TTL",
                          family="cache", refinement_of="c1",
                          qualifiers=["5 minute TTL"])],
                   [_e("e2", "expiry", "TTL prevents stale sessions")]),
                _r(3, [_c("", "Session tokens should be cached in memory with a 5 minute TTL",
                          family="cache")]),
                _r(4, [_c("", "Keep session tokens cached in memory under a 5 minute TTL",
                          family="cache")]),
            ],
        },
        {
            "id": "C05-same-id-restatement",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("ship", "Ship the worker as a systemd unit", family="ship")],
                   [_e("e1", "ops", "systemd is the house standard")]),
                _r(2, [_c("ship", "Ship the worker as a systemd unit", family="ship")]),
                _r(3, [_c("ship", "Ship the worker as a systemd unit", family="ship")]),
                _r(4, [_c("ship", "Ship the worker as a systemd unit", family="ship")]),
            ],
        },
        {
            "id": "C06-reworded-mechanism",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Reject unsigned artifacts at the gate", family="sig")],
                   [_e("e1", "supply-chain", "unsigned artifacts are refused")]),
                _r(2, [_c("", "The gate must reject unsigned artifacts", family="sig")]),
                _r(3, [_c("", "Unsigned artifacts are rejected at the gate", family="sig")]),
                _r(4, [_c("", "Do reject unsigned artifacts at the gate", family="sig")]),
            ],
        },
        {
            "id": "C07-three-way-paraphrase",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Pin every model call to a recorded seed", family="seed")],
                   [_e("e1", "repro", "seed is written to the run artifact")]),
                _r(2, [_c("", "Every model call is pinned to a recorded seed", family="seed")]),
                _r(3, [_c("", "Record a seed and pin every model call to it", family="seed")]),
                _r(4, [_c("", "Model calls stay pinned to the recorded seed", family="seed")]),
            ],
        },
        {
            "id": "C08-refine-then-loop",
            "expect_fire": True,
            "kind": "looping",
            "rounds": [
                _r(1, [_c("c1", "Retry failed fetches", family="retry")]),
                _r(2, [_c("", "Retry failed fetches with a limit of 3 attempts",
                          family="retry", refinement_of="c1",
                          qualifiers=["3 attempts"])],
                   [_e("e1", "net", "three retries cover blips")]),
                _r(3, [_c("", "Failed fetches are retried with a limit of 3 attempts",
                          family="retry")]),
                _r(4, [_c("", "Use a limit of 3 attempts when retrying failed fetches",
                          family="retry")]),
            ],
        },
        {
            "id": "C09-progressive-refinement",
            "expect_fire": False,
            "kind": "refining",
            "rounds": [
                _r(1, [_c("c1", "Deploy the payment API behind a feature flag", family="f1")]),
                _r(2, [_c("", "Deploy the payment API behind a feature flag limited to 5 percent of traffic",
                          family="f1", refinement_of="c1",
                          qualifiers=["5 percent of traffic"])]),
                _r(3, [_c("", "Deploy the payment API behind a feature flag limited to 5 percent of traffic with automatic rollback if error rate exceeds 1 percent",
                          family="f1",
                          qualifiers=["5 percent of traffic", "rollback", "1 percent error"])]),
                _r(4, [_c("", "Deploy the payment API behind a feature flag limited to 5 percent of traffic with automatic rollback if error rate exceeds 1 percent and a 15 minute freeze window",
                          family="f1",
                          qualifiers=["5 percent", "rollback", "1 percent", "15 minute freeze"])]),
            ],
        },
        {
            "id": "C10-numeric-tightening",
            "expect_fire": False,
            "kind": "refining",
            "rounds": [
                _r(1, [_c("q", "Cap concurrent jobs", family="q")]),
                _r(2, [_c("", "Cap concurrent jobs at 8", family="q",
                          refinement_of="q", qualifiers=["8"])]),
                _r(3, [_c("", "Cap concurrent jobs at 8 except for backfill which is capped at 2",
                          family="q", qualifiers=["8", "except", "backfill 2"])]),
                _r(4, [_c("", "Cap concurrent jobs at 8 except for backfill which is capped at 2 with a 30 second timeout",
                          family="q", qualifiers=["8", "except", "2", "30 second timeout"])]),
            ],
        },
        {
            "id": "C11-evidence-only",
            "expect_fire": False,
            "kind": "evidence-only",
            "rounds": [
                _r(1, [_c("c1", "Keep the public bucket private", family="acl")],
                   [_e("e1", "audit-r1", "acl deny all")]),
                _r(2, [_c("c1", "Keep the public bucket private", family="acl")],
                   [_e("e2", "audit-r2", "object listing is blocked")]),
                _r(3, [_c("c1", "Keep the public bucket private", family="acl")],
                   [_e("e3", "audit-r3", "anonymous GET returns 403")]),
                _r(4, [_c("c1", "Keep the public bucket private", family="acl")],
                   [_e("e4", "audit-r4", "bucket policy denies s3:GetObject")]),
            ],
        },
        {
            "id": "C12-new-claims-each-round",
            "expect_fire": False,
            "kind": "productive",
            "rounds": [
                _r(1, [_c("n1", "Add a health endpoint on /readyz", family="n1")]),
                _r(2, [_c("n2", "Emit a structured shutdown event", family="n2")]),
                _r(3, [_c("n3", "Refuse start if the schema hash mismatches", family="n3")]),
                _r(4, [_c("n4", "Page on-call when error rate exceeds 2 percent", family="n4")]),
            ],
        },
        {
            "id": "C13-refine-then-evidence",
            "expect_fire": False,
            "kind": "mixed",
            "rounds": [
                _r(1, [_c("c1", "Encrypt backups at rest", family="enc")]),
                _r(2, [_c("", "Encrypt backups at rest with AES-256", family="enc",
                          refinement_of="c1", qualifiers=["AES-256"])]),
                _r(3, [_c("", "Encrypt backups at rest with AES-256", family="enc")],
                   [_e("e1", "kms", "customer-managed key is required")]),
                _r(4, [_c("", "Encrypt backups at rest with AES-256", family="enc")],
                   [_e("e2", "restore-drill", "restore succeeded from encrypted snapshot")]),
            ],
        },
        {
            "id": "C14-exception-clause",
            "expect_fire": False,
            "kind": "refining",
            "rounds": [
                _r(1, [_c("c1", "Block outbound traffic to unknown hosts", family="fw")]),
                _r(2, [_c("", "Block outbound traffic to unknown hosts except the package mirror",
                          family="fw", refinement_of="c1",
                          qualifiers=["except package mirror"])]),
                _r(3, [_c("", "Block outbound traffic to unknown hosts except the package mirror and the time server",
                          family="fw",
                          qualifiers=["except package mirror", "time server"])]),
                _r(4, [_c("", "Block outbound traffic to unknown hosts except the package mirror and the time server unless an owner waiver is recorded",
                          family="fw",
                          qualifiers=["except", "unless", "owner waiver"])]),
            ],
        },
        {
            "id": "C15-counterexample-productive",
            "expect_fire": False,
            "kind": "productive",
            "rounds": [
                _r(1, [_c("p1", "Majority vote is sufficient", family="p1")],
                   [_e("e1", "tally", "5-2 majority")]),
                _r(2, [_c("p2", "A 5-2 majority with no evidence nodes is not sufficient",
                          family="p2")],
                   [_e("e2", "counter", "unbacked ballots")]),
                _r(3, [_c("p3", "Require each ballot to cite an evidence node", family="p3")]),
                _r(4, [_c("p4", "Treat a fabricated evidence id as unbacked", family="p4")],
                   [_e("e3", "neg", "missing evidence id must not count as backed")]),
            ],
        },
    ]


def labelled_pairs() -> list[dict[str, Any]]:
    """Hand-labelled repetition vs refinement. Rate is measured, not assumed."""
    return [
        {
            "id": "P01",
            "label": "repetition",
            "old": "Deploy the payment API behind a feature flag",
            "new": "The payment API should be deployed behind a feature flag",
        },
        {
            "id": "P02",
            "label": "repetition",
            "old": "Keep the ledger append-only",
            "new": "The ledger stays append-only",
        },
        {
            "id": "P03",
            "label": "repetition",
            "old": "Reject unsigned artifacts at the gate",
            "new": "The gate must reject unsigned artifacts",
        },
        {
            "id": "P04",
            "label": "repetition",
            "old": "Pin every model call to a recorded seed",
            "new": "Every model call is pinned to a recorded seed",
        },
        {
            "id": "P05",
            "label": "repetition",
            "old": "Ship the worker as a systemd unit",
            "new": "The worker ships as a systemd unit",
        },
        {
            "id": "P06",
            "label": "repetition",
            "old": "Keep the public bucket private",
            "new": "The public bucket is kept private",
        },
        {
            "id": "P07",
            "label": "repetition",
            "old": "Encrypt backups at rest",
            "new": "Backups are encrypted at rest",
        },
        {
            "id": "P08",
            "label": "repetition",
            "old": "Retry failed fetches",
            "new": "Failed fetches are retried",
        },
        {
            "id": "P09",
            "label": "refinement",
            "old": "Deploy the payment API behind a feature flag",
            "new": "Deploy the payment API behind a feature flag limited to 5 percent of traffic",
        },
        {
            "id": "P10",
            "label": "refinement",
            "old": "Cap concurrent jobs",
            "new": "Cap concurrent jobs at 8",
        },
        {
            "id": "P11",
            "label": "refinement",
            "old": "Retry failed fetches",
            "new": "Retry failed fetches with a limit of 3 attempts",
        },
        {
            "id": "P12",
            "label": "refinement",
            "old": "Encrypt backups at rest",
            "new": "Encrypt backups at rest with AES-256",
        },
        {
            "id": "P13",
            "label": "refinement",
            "old": "Block outbound traffic to unknown hosts",
            "new": "Block outbound traffic to unknown hosts except the package mirror",
        },
        {
            "id": "P14",
            "label": "refinement",
            "old": "Cache session tokens in memory",
            "new": "Cache session tokens in memory with a 5 minute TTL",
        },
        {
            "id": "P15",
            "label": "refinement",
            "old": "Cap concurrent jobs at 8",
            "new": "Cap concurrent jobs at 8 except for backfill which is capped at 2",
        },
        {
            "id": "P16",
            "label": "refinement",
            "old": "Deploy the payment API behind a feature flag limited to 5 percent of traffic",
            "new": "Deploy the payment API behind a feature flag limited to 5 percent of traffic with automatic rollback if error rate exceeds 1 percent",
        },
    ]
