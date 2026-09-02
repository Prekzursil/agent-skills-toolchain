"""Read CNF-0018 domain fields from a receipt (report payload or legacy top-level)."""
from __future__ import annotations


def report_of(doc: dict) -> dict:
    report = doc.get("report")
    return report if isinstance(report, dict) else {}


def failures_of(doc: dict) -> list:
    report = report_of(doc)
    failures = report.get("failures") or doc.get("failures") or []
    return failures if isinstance(failures, list) else []


def known_failure_of(doc: dict):
    report = report_of(doc)
    if "known_failure_reproduced" in report:
        return report.get("known_failure_reproduced")
    return doc.get("known_failure_reproduced")


def container_of(doc: dict) -> dict:
    report = report_of(doc)
    container = report.get("container") or doc.get("container") or {}
    return container if isinstance(container, dict) else {}
