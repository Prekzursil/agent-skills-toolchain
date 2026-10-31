"""Vulnerability status ingestion from live advisory sources (IMP-0088 -> IMP-0098).

Every verdict is TIME-STAMPED (queried_at + advisory database snapshot id + input
hash) - vulnerability status is a property of a moment, never a permanent package
attribute. A CLEAN verdict is only trusted in a run where the KNOWN-VULNERABLE
control (lodash 4.17.20 / CVE-2021-23337) also fired; an unreachable advisory
source yields UNKNOWN, never CLEAN; osv-scanner exit 127 (missing tool) is UNKNOWN,
which is a different thing from exit 1 (findings). Freshness follows IMP-0095:
a changed input hash or an age beyond the window marks STALE, and STALE is never
rendered as CLEAN.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

FRESHNESS_WINDOW_SECONDS = 86400
KNOWN_CONTROL_CVE = "CVE-2021-23337"
KNOWN_CONTROL_NAME = "lodash"
KNOWN_CONTROL_VERSION = "4.17.20"
CLEAN_CONTROL_NAME = "@ast-integrate/no-such-package-imp-0098"


class Status(str, Enum):
    CLEAN = "CLEAN"
    VULNERABLE = "VULNERABLE"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class SourceUnavailable(RuntimeError):
    """The advisory source could not be reached. Maps to UNKNOWN, never CLEAN."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def input_hash(*parts: Any) -> str:
    payload = json.dumps(list(parts), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def purl_for(ecosystem: str, name: str, version: str) -> str:
    return f"pkg:{ecosystem}/{name}@{version}"


def known_control_component() -> dict[str, str]:
    """The known-present control: a component with a KNOWN historical CVE."""
    return {
        "ecosystem": "npm",
        "name": KNOWN_CONTROL_NAME,
        "version": KNOWN_CONTROL_VERSION,
        "purl": purl_for("npm", KNOWN_CONTROL_NAME, KNOWN_CONTROL_VERSION),
        "cve": KNOWN_CONTROL_CVE,
    }


def ids_contain(ids: Iterable[str], cve: str) -> bool:
    for i in ids:
        if str(i).upper() == cve.upper():
            return True
    return False


def interpret_osv_scanner_exit(code: int) -> str:
    """osv-scanner exit discipline: 0 clean, 1 findings, 127 missing tool.

    127 is UNKNOWN - a missing tool is not a clean result, and it is not a
    finding either.
    """
    if code == 0:
        return Status.CLEAN.value
    if code == 1:
        return Status.VULNERABLE.value
    return Status.UNKNOWN.value


class OsvHttpSource:
    """Live OSV query (api.osv.dev/v1/query). Raises SourceUnavailable on failure."""

    endpoint = "https://api.osv.dev/v1/query"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def query(self, ecosystem: str, name: str, version: str) -> dict[str, Any]:
        body = json.dumps({
            "package": {"ecosystem": {"npm": "npm"}.get(ecosystem, ecosystem),
                        "name": name},
            "version": version,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise SourceUnavailable(f"osv.dev unreachable: {exc}") from exc
        doc = json.loads(raw.decode("utf-8"))
        ids: list[str] = []
        for vuln in doc.get("vulns") or []:
            ids.append(str(vuln.get("id") or ""))
            for alias in vuln.get("aliases") or []:
                ids.append(str(alias))
        ids = [i for i in ids if i]
        snapshot = "osv.dev:" + hashlib.sha256(raw).hexdigest()[:32]
        return {"advisory_ids": ids, "advisory_db_snapshot_id": snapshot,
                "raw_count": len(doc.get("vulns") or [])}


class GithubAdvisorySource:
    """Independent second source: GitHub Advisory DB REST (not a re-parse of the
    OSV payload - a different database, a different host). Raises
    SourceUnavailable on failure; the caller maps that to UNKNOWN."""

    endpoint = "https://api.github.com/advisories"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def query(self, ecosystem: str, name: str, version: str) -> dict[str, Any]:
        url = f"{self.endpoint}?affects={name}@{version}&ecosystem={ecosystem}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise SourceUnavailable(f"github advisories unreachable: {exc}") from exc
        doc = json.loads(raw.decode("utf-8"))
        ids: list[str] = []
        for adv in doc:
            ids.append(str(adv.get("ghsa_id") or ""))
            if adv.get("cve_id"):
                ids.append(str(adv["cve_id"]))
        ids = [i for i in ids if i]
        snapshot = "github-advisory:" + hashlib.sha256(raw).hexdigest()[:32]
        return {"advisory_ids": ids, "advisory_db_snapshot_id": snapshot,
                "raw_count": len(doc)}


class FakeSource:
    """Hermetic seam: canned answers for tests and detector controls."""

    def __init__(self, answers=None, unreachable: bool = False,
                 snapshot: str = "fake:deadbeef") -> None:
        self.answers = answers or {}
        self.unreachable = unreachable
        self.snapshot = snapshot

    def query(self, ecosystem: str, name: str, version: str) -> dict[str, Any]:
        if self.unreachable:
            raise SourceUnavailable("fake source set unreachable")
        ids = self.answers.get((ecosystem, name, version), [])
        return {"advisory_ids": list(ids), "advisory_db_snapshot_id": self.snapshot,
                "raw_count": len(ids)}


@dataclass
class SbomStore:
    """Minimal CycloneDX-component store for ingestion fixtures."""

    documents: list = field(default_factory=list)

    def components(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for doc in self.documents:
            for comp in doc.get("components") or []:
                ecosystem = "npm"
                purl = str(comp.get("purl") or "")
                if purl.startswith("pkg:"):
                    ecosystem = purl.split("/")[0].replace("pkg:", "") or "npm"
                out.append({
                    "ecosystem": ecosystem,
                    "name": str(comp.get("name") or ""),
                    "version": str(comp.get("version") or ""),
                    "purl": purl or purl_for(ecosystem, str(comp.get("name") or ""),
                                             str(comp.get("version") or "")),
                })
        return out

    @classmethod
    def from_paths(cls, *paths) -> "SbomStore":
        docs = []
        for p in paths:
            with open(p, encoding="utf-8") as fh:
                docs.append(json.loads(fh.read()))
        return cls(documents=docs)


def freshness(verdict: dict[str, Any], *, now: str | None = None,
              window_seconds: int = FRESHNESS_WINDOW_SECONDS) -> str:
    """IMP-0095 decay semantics: changed input hash or age beyond the window is
    STALE; STALE is never rendered as CLEAN/PASS."""
    if verdict.get("status") == Status.UNKNOWN.value:
        return Status.UNKNOWN.value
    if verdict.get("input_hash") != input_hash(verdict.get("purl"), verdict.get("queried_at")):
        return Status.STALE.value
    if now is None:
        return "fresh"
    try:
        then = datetime.strptime(str(verdict.get("queried_at")), "%Y-%m-%dT%H:%M:%SZ")
        nowdt = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return Status.STALE.value
    age = (nowdt - then).total_seconds()
    return "fresh" if 0 <= age <= window_seconds else Status.STALE.value


def ingest_components(components, *, source=None, second_source=None,
                      require_control: bool = True) -> dict[str, Any]:
    """Ingest advisories for every component; gate CLEAN on the control firing."""
    source = source if source is not None else OsvHttpSource()
    comps = list(components)
    verdicts: list[dict[str, Any]] = []
    control_fired = False
    for comp in comps:
        queried_at = now_iso()
        ih = input_hash(comp.get("purl"), queried_at)
        try:
            got = source.query(comp["ecosystem"], comp["name"], comp["version"])
        except SourceUnavailable as exc:
            verdicts.append({
                "ecosystem": comp["ecosystem"], "name": comp["name"],
                "version": comp["version"], "purl": comp.get("purl", ""),
                "advisory_ids": [], "advisory_db_snapshot_id": "",
                "queried_at": queried_at, "input_hash": ih,
                "status": Status.UNKNOWN.value, "warning": str(exc),
            })
            continue
        advisory_ids = list(got.get("advisory_ids") or [])
        if advisory_ids:
            status: str = Status.VULNERABLE.value
        else:
            # CLEAN is only trusted in a run where the known-vulnerable control
            # also fired; the control is checked right after this loop, so a CLEAN
            # here is provisional and downgraded if the control never fires.
            status = "CLEAN-PROVISIONAL"
        verdicts.append({
            "ecosystem": comp["ecosystem"], "name": comp["name"],
            "version": comp["version"], "purl": comp.get("purl", ""),
            "advisory_ids": advisory_ids,
            "advisory_db_snapshot_id": got.get("advisory_db_snapshot_id", ""),
            "queried_at": queried_at, "input_hash": ih,
            "status": status, "warning": "",
        })
    if require_control:
        control_row = next((v for v in verdicts if v["name"] == KNOWN_CONTROL_NAME), None)
        if control_row is not None and ids_contain(control_row["advisory_ids"], KNOWN_CONTROL_CVE):
            control_fired = True
    for v in verdicts:
        if v["status"] == "CLEAN-PROVISIONAL":
            v["status"] = Status.CLEAN.value if (control_fired or not require_control) \
                else Status.UNKNOWN.value
            if v["status"] == Status.UNKNOWN.value:
                v["warning"] = "clean not trusted: known-vulnerable control did not fire"
    counts = {
        "vulnerable": sum(1 for v in verdicts if v["status"] == Status.VULNERABLE.value),
        "clean": sum(1 for v in verdicts if v["status"] == Status.CLEAN.value),
        "unknown": sum(1 for v in verdicts if v["status"] == Status.UNKNOWN.value),
    }
    return {
        "verdicts": verdicts,
        "control_fired": control_fired,
        "component_count": len(verdicts),
        "vulnerable_count": counts["vulnerable"],
        "clean_count": counts["clean"],
        "unknown_count": counts["unknown"],
        "never_clean_on_failure": all(
            v["status"] != Status.CLEAN.value for v in verdicts if v["warning"]
        ),
        "queried_at": now_iso(),
    }


def two_source_known_cve(first_ids, second_ids, cve: str = KNOWN_CONTROL_CVE) -> dict[str, Any]:
    """Signal 2: the known CVE must appear in BOTH independently queried sources."""
    a = [str(i) for i in first_ids]
    b = [str(i) for i in second_ids]
    return {
        "cve": cve,
        "in_first": ids_contain(a, cve),
        "in_second": ids_contain(b, cve),
        "both": ids_contain(a, cve) and ids_contain(b, cve),
    }


__all__ = [
    "CLEAN_CONTROL_NAME", "FRESHNESS_WINDOW_SECONDS",
    "GithubAdvisorySource", "KNOWN_CONTROL_CVE", "KNOWN_CONTROL_NAME",
    "KNOWN_CONTROL_VERSION", "OsvHttpSource", "SbomStore", "SourceUnavailable",
    "FakeSource", "Status", "freshness", "ingest_components",
    "interpret_osv_scanner_exit", "known_control_component", "ids_contain",
    "purl_for", "two_source_known_cve",
]
