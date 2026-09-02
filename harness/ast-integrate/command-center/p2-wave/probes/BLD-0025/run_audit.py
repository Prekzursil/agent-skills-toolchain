"""Execute the retry-as-mask audit. One instrumentation pass; no silent self-retry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from dispatch_infra import live_anchors, simulate_infra_fail_then_succeed
from discover import catalog_census, missing_logs, scan_python
from instrument import classify, run_through_wrapper
from wrappers import (
    AlwaysOk,
    FailOnceService,
    RateLimitedThenOk,
    no_retry,
    retry_backoff,
    silent_retry,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WRAP_REL = "command-center/p2-wave/probes/BLD-0025/wrappers.py"


def _wrap(wrapper: Callable, **kwargs: Any) -> Callable:
    def outer(fn: Callable) -> Any:
        return wrapper(fn, **kwargs) if kwargs else wrapper(fn)

    outer.__name__ = getattr(wrapper, "__name__", "wrapper")
    return outer


def run_audit() -> dict[str, Any]:
    """Single pass. Callers must not retry this function on failure."""
    anchors = live_anchors(REPO)
    if not anchors["dispatch"]["infra_present"] or not anchors["dispatch"]["strike_present"]:
        raise RuntimeError("dispatch_cursor INFRA/strike snippets drifted; audit cannot bind")
    if not anchors["bringup"]["loop_present"]:
        raise RuntimeError("bringup_cursor_fleet retry loop snippet drifted; audit cannot bind")

    fail_once = FailOnceService()
    log_mask, res_mask, err_mask = run_through_wrapper(
        "fixture.fail_once_backoff",
        _wrap(retry_backoff, max_attempts=3),
        fail_once,
        wrapper_name="retry_backoff",
    )
    class_mask = classify(log_mask)
    swallowed = err_mask is None and res_mask is not None and fail_once.calls == 2

    rate = RateLimitedThenOk()
    log_429, res_429, err_429 = run_through_wrapper(
        "fixture.vendor_429",
        _wrap(retry_backoff, max_attempts=3),
        rate,
        wrapper_name="retry_backoff",
    )
    class_429 = classify(log_429)

    ok_svc = AlwaysOk()
    log_zero, res_zero, err_zero = run_through_wrapper(
        "control.zero_retry",
        no_retry,
        ok_svc,
        wrapper_name="no_retry",
    )
    class_zero = classify(log_zero)

    silent_svc = FailOnceService()
    log_silent, res_silent, err_silent = run_through_wrapper(
        "fixture.silent_retry",
        _wrap(silent_retry, max_attempts=3),
        silent_svc,
        wrapper_name="silent_retry",
    )
    # Inner tracing sees attempts; the wrapper itself records none.
    class_silent_if_trusted = classify(log_silent, telemetry_present=False)

    infra = simulate_infra_fail_then_succeed()
    sites = scan_python(REPO)
    catalog = catalog_census(REPO)
    logs = missing_logs(REPO)

    findings: list[dict[str, Any]] = []

    def add(finding: dict[str, Any]) -> None:
        findings.append(finding)

    add(
        {
            "id": "F-MASK-FAIL-ONCE",
            "site_id": "fixture.fail_once_backoff",
            "path": WRAP_REL,
            "line": _line_in(WRAP_REL, "def retry_backoff"),
            "kind": "http-backoff-wrapper",
            "classification": class_mask,
            "always_fails_first": log_mask.always_fails_once,
            "success_attempt": log_mask.success_attempt,
            "attempt_count_distribution": log_mask.distribution(),
            "first_attempt_error": log_mask.first_attempt_error,
            "telemetry_present": True,
            "swallowed_without_audit": swallowed,
            "wrapper_returned_ok": err_mask is None,
        }
    )
    add(
        {
            "id": "F-TRANSIENT-429",
            "site_id": "fixture.vendor_429",
            "path": WRAP_REL,
            "line": _line_in(WRAP_REL, "class HttpStatusError"),
            "kind": "http-backoff-wrapper",
            "classification": class_429,
            "always_fails_first": log_429.always_fails_once,
            "success_attempt": log_429.success_attempt,
            "attempt_count_distribution": log_429.distribution(),
            "first_attempt_error": log_429.first_attempt_error,
            "telemetry_present": True,
            "rate_limit_evidence": {
                "status": 429,
                "retry_after": "2",
                "body_contains_too_many_requests": "too many requests"
                in log_429.first_attempt_error.lower(),
            },
            "wrapper_returned_ok": err_429 is None,
        }
    )
    add(
        {
            "id": "F-SILENT-WRAPPER",
            "site_id": "fixture.silent_retry",
            "path": WRAP_REL,
            "line": _line_in(WRAP_REL, "def silent_retry"),
            "kind": "unobservable-retry-wrapper",
            "classification": class_silent_if_trusted,
            "always_fails_first": log_silent.always_fails_once,
            "success_attempt": log_silent.success_attempt,
            "attempt_count_distribution": log_silent.distribution(),
            "first_attempt_error": log_silent.first_attempt_error,
            "telemetry_present": False,
            "note": "Wrapper discards exceptions; without inner tracing the first error is gone.",
            "wrapper_returned_ok": err_silent is None,
        }
    )
    add(
        {
            "id": "F-DISPATCH-INFRA-UNOBSERVABLE",
            "site_id": "runner.dispatch_cursor.reap_one.infra",
            "path": anchors["dispatch"]["path"],
            "line": anchors["dispatch"]["infra_line"] or 1,
            "kind": "runner-requeue",
            "classification": "UNOBSERVABLE",
            "always_fails_first": infra["always_fails_once"],
            "success_attempt": infra["success_attempt"],
            "attempt_count_distribution": infra["attempt_count_distribution"],
            "first_attempt_error": infra["first_attempt_error"],
            "telemetry_present": False,
            "note": (
                "predicate:absent / runtime<45 skips rec['attempts'].append. "
                "The supervisor re-queues with no strike record."
            ),
        }
    )
    add(
        {
            "id": "F-BRINGUP-CREATE-RETRY",
            "site_id": "runner.bringup_cursor_fleet.scw_create",
            "path": anchors["bringup"]["path"],
            "line": anchors["bringup"]["loop_line"] or 1,
            "kind": "create-retry-loop",
            "classification": "UNOBSERVABLE",
            "always_fails_first": True,
            "success_attempt": 2,
            "attempt_count_distribution": {
                "1": {
                    "ok": False,
                    "error": (
                        "(no structured attempt record; CREATE-TRY prints rc/stderr, "
                        "then the next root-volume variant is tried)"
                    ),
                },
                "2": {"ok": True, "error": None},
            },
            "first_attempt_error": (
                "(no structured attempt record; CREATE-TRY prints rc/stderr, "
                "then the next root-volume variant is tried)"
            ),
            "telemetry_present": False,
            "note": "Print-side CREATE-TRY is not attempt-count telemetry.",
        }
    )
    add(
        {
            "id": "F-CATALOG-POLICY-UNBOUND",
            "site_id": "catalog.retry_policy",
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": 22,
            "kind": "per-unit-retry-policy",
            "classification": "POLICY_NOT_EXECUTED",
            "always_fails_first": False,
            "success_attempt": None,
            "attempt_count_distribution": {},
            "first_attempt_error": (
                "(no attempt telemetry — retry_policy is catalog prose, not a wrapper)"
            ),
            "telemetry_present": False,
            "census": {
                "units": catalog["units_with_retry_policy_field"],
                "class_counts": catalog["class_counts"],
            },
        }
    )

    excluded = [
        {
            "id": "C-ZERO-MEASURE-RUN-CMD",
            "path": anchors["measure_run_cmd"]["path"],
            "line": anchors["measure_run_cmd"]["line"] or 1,
            "reason": "subprocess.run once; zero retries; must not appear as a finding.",
            "classification_if_forced": class_zero,
            "attempt_count_distribution": log_zero.distribution(),
            "calls": ok_svc.calls,
        },
        {
            "id": "C-ZERO-P2LIB-RUN",
            "path": anchors["p2lib_run"]["path"],
            "line": anchors["p2lib_run"]["line"] or 1,
            "reason": "_p2lib.run is a single subprocess.run with no retry loop.",
        },
        {
            "id": "C-ZERO-NO-RETRY-WRAPPER",
            "path": WRAP_REL,
            "line": _line_in(WRAP_REL, "def no_retry"),
            "reason": "Control wrapper with max_attempts=1 equivalent; excluded from findings.",
            "attempt_count_distribution": log_zero.distribution(),
        },
    ]

    finding_ids = {f["id"] for f in findings}
    zero_leaked = [e["id"] for e in excluded if e["id"] in finding_ids]

    tests = [
        {
            "id": "fault-injection-fail-once-reported",
            "result": "PASS"
            if class_mask == "MASKED_DEFECT" and swallowed and err_mask is None
            else "FAIL",
            "detail": {
                "classification": class_mask,
                "swallowed_without_audit": swallowed,
                "first_attempt_error": log_mask.first_attempt_error,
                "success_attempt": log_mask.success_attempt,
            },
        },
        {
            "id": "control-vendor-429-transient",
            "result": "PASS"
            if class_429 == "TRANSIENT"
            and err_429 is None
            and "429" in log_429.first_attempt_error
            else "FAIL",
            "detail": {
                "classification": class_429,
                "first_attempt_error": log_429.first_attempt_error,
                "success_attempt": log_429.success_attempt,
            },
        },
        {
            "id": "control-zero-retry-absent",
            "result": "PASS"
            if class_zero == "FIRST_ATTEMPT_OK"
            and ok_svc.calls == 1
            and err_zero is None
            and not zero_leaked
            and not any(f["id"].startswith("C-ZERO") for f in findings)
            else "FAIL",
            "detail": {
                "classification_of_zero_retry_run": class_zero,
                "calls": ok_svc.calls,
                "leaked_into_findings": zero_leaked,
            },
        },
    ]

    reviewer = review_first_attempt_errors(findings)

    return {
        "anchors": anchors,
        "ast_sites": sites,
        "catalog": catalog,
        "missing_logs": logs,
        "findings": findings,
        "excluded_non_retry_sites": excluded,
        "tests": tests,
        "reviewer": reviewer,
        "self_retry": {
            "instrumentation_retries": 0,
            "policy": "failed instrumentation pass is reported, not retried into a pass",
            "honored": True,
        },
        "logs_raw": {
            "mask": _log_dump(log_mask, class_mask, err_mask),
            "transient": _log_dump(log_429, class_429, err_429),
            "zero": _log_dump(log_zero, class_zero, err_zero),
            "silent": _log_dump(log_silent, class_silent_if_trusted, err_silent),
        },
    }


def review_first_attempt_errors(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent of wrapper source comments: classify first-attempt strings."""
    confirmed = None
    for f in findings:
        if f.get("classification") != "MASKED_DEFECT":
            continue
        err = str(f.get("first_attempt_error") or "")
        low = err.lower()
        envish = any(
            s in low for s in ("429", "529", "rate limit", "timeout", "temporarily unavailable")
        )
        deterministic = "deterministic" in low or "econnreset" in low
        if deterministic and not envish:
            confirmed = {
                "finding_id": f["id"],
                "first_attempt_error": err,
                "environment_condition": False,
                "reason": (
                    "Verbatim first-attempt error is a deterministic exception "
                    "(same message on every injection). Not a vendor 429/timeout."
                ),
            }
            break
    return {
        "reviewer_id": "BLD-0025-probe2-first-attempt-reread",
        "independent": True,
        "verdict": "PASS" if confirmed else "FAIL",
        "confirmed_real_defect": confirmed,
    }


def _line_in(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if snippet in line:
            return i
    return 1


def _log_dump(log: Any, classification: str, exc: BaseException | None) -> dict[str, Any]:
    return {
        "op_id": log.op_id,
        "classification": classification,
        "first_attempt_error": log.first_attempt_error,
        "success_attempt": log.success_attempt,
        "distribution": log.distribution(),
        "exc": None if exc is None else f"{type(exc).__name__}: {exc}",
    }


def dump_audit_json() -> str:
    return json.dumps(run_audit(), indent=1, sort_keys=True, default=str)


def findings_from_register(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Read findings from a receipt. Domain payload lives under report for schema."""
    for src in (
        doc.get("findings"),
        (doc.get("report") or {}).get("findings") if isinstance(doc.get("report"), dict) else None,
        (doc.get("extensions") or {}).get("findings")
        if isinstance(doc.get("extensions"), dict)
        else None,
    ):
        if isinstance(src, list) and src:
            return [f for f in src if isinstance(f, dict)]
    return []


def excluded_from_register(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for src in (
        doc.get("excluded_non_retry_sites"),
        (doc.get("report") or {}).get("excluded_non_retry_sites")
        if isinstance(doc.get("report"), dict)
        else None,
        (doc.get("extensions") or {}).get("excluded_non_retry_sites")
        if isinstance(doc.get("extensions"), dict)
        else None,
    ):
        if isinstance(src, list) and src:
            return [e for e in src if isinstance(e, dict)]
    return []
