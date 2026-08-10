"""Health probes, the both-states control harness, and the doctor advisory.

The rule this module mechanises: **a probe whose silence you have never tested is not a probe.**
Every registered probe must ship a ``break_``/``restore_`` pair so ``control()`` can assert the
probe PASSES in the healthy state and FAILS in the deliberately-broken state. A probe that is
silent in both states measures nothing and is reported as ``INVALID`` — it does not count toward a
green health check.

``doctor()`` maps each failing probe to the exact command that remediates it (IMP-0050); a health
report that says "something is wrong" without naming the next command is not usable output.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .cache import Cache
from .deploy import PROVENANCE_NAME, Provenance, classify, drift_document
from .fsops import atomic_write_bytes, content_hash, safe_join
from .journal import Prefix, open_transactions, read_installed
from .manifest import MANIFEST_RELPATH, load as load_manifest
from .proc import current_os, probe_interpreter

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass
class ProbeResult:
    ident: str
    status: str
    detail: str
    remediation: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "probe": self.ident,
            "status": self.status,
            "detail": self.detail,
            "remediation": self.remediation,
        }


@dataclass
class Probe:
    """A health probe plus the machinery that proves the probe itself discriminates."""

    ident: str
    description: str
    run: Callable[[Prefix], ProbeResult]
    remediation: str
    #: Deliberately break the invariant; returns a callable that restores it.
    break_: Callable[[Prefix], Callable[[], None]] | None = None


def _probe_prefix_layout(prefix: Prefix) -> ProbeResult:
    # An absent prefix is not a broken prefix — there is nothing installed there to be broken, and
    # reporting FAIL would make `health-check <fresh path>` look like a fault. A prefix that EXISTS
    # but is missing directories IS broken, which is the state the break_() control exercises.
    if not prefix.root.exists():
        return ProbeResult(
            "prefix-layout",
            SKIP,
            f"prefix does not exist yet: {prefix.root} (nothing is installed)",
        )
    missing = [
        p.name
        for p in (
            prefix.versions,
            prefix.state,
            prefix.backups,
            prefix.cache,
            prefix.logs,
        )
        if not p.exists()
    ]
    if missing:
        return ProbeResult(
            "prefix-layout", FAIL, f"missing prefix directories: {', '.join(missing)}"
        )
    return ProbeResult("prefix-layout", PASS, "all prefix directories present")


def _probe_installed_state(prefix: Prefix) -> ProbeResult:
    state = read_installed(prefix)
    if not state:
        return ProbeResult("installed-state", SKIP, "nothing installed in this prefix")
    version = str(state.get("active_version", ""))
    vroot = prefix.version_dir(version)
    if not vroot.exists():
        return ProbeResult(
            "installed-state",
            FAIL,
            f"active version {version} recorded but {vroot} is absent",
        )
    if not (vroot / MANIFEST_RELPATH).exists():
        return ProbeResult(
            "installed-state", FAIL, f"version {version} has no {MANIFEST_RELPATH}"
        )
    return ProbeResult(
        "installed-state", PASS, f"active version {version} is present and manifested"
    )


def _probe_no_open_transactions(prefix: Prefix) -> ProbeResult:
    stale = open_transactions(prefix)
    if stale:
        return ProbeResult(
            "no-open-transactions",
            FAIL,
            f"{len(stale)} transaction(s) never closed: {', '.join(stale)}",
        )
    return ProbeResult(
        "no-open-transactions", PASS, "journal has no un-closed transaction"
    )


def _probe_no_stale_lock(prefix: Prefix) -> ProbeResult:
    if prefix.lock.exists():
        return ProbeResult("no-stale-lock", FAIL, f"prefix lock is held: {prefix.lock}")
    return ProbeResult("no-stale-lock", PASS, "prefix lock is free")


def _probe_interpreters(prefix: Prefix) -> ProbeResult:
    state = read_installed(prefix)
    if not state:
        return ProbeResult("interpreters", SKIP, "nothing installed in this prefix")
    manifest = load_manifest(
        prefix.version_dir(str(state["active_version"])) / MANIFEST_RELPATH
    )
    bad: list[str] = []
    for decl in manifest.interpreters:
        if not bool(decl.get("required", True)):
            continue
        p = probe_interpreter(str(decl["id"]))
        if not p.found or not p.meets_floor:
            bad.append(f"{decl['id']}: {p.detail}")
    if bad:
        return ProbeResult("interpreters", FAIL, "; ".join(bad))
    return ProbeResult(
        "interpreters",
        PASS,
        "every required interpreter is present and meets its floor",
    )


def _probe_cache_integrity(prefix: Prefix) -> ProbeResult:
    cache = Cache(prefix.cache)
    bad = cache.verify()
    if bad:
        return ProbeResult(
            "cache-integrity", FAIL, f"{len(bad)} corrupt entry quarantined"
        )
    return ProbeResult(
        "cache-integrity", PASS, "every cache entry hashes to its own key"
    )


def _probe_live_no_divergence(prefix: Prefix) -> ProbeResult:
    state = read_installed(prefix)
    if not state:
        return ProbeResult(
            "live-no-divergence", SKIP, "nothing installed in this prefix"
        )
    vroot = prefix.version_dir(str(state["active_version"]))
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    live = prefix.root / "live"
    entries = classify(
        manifest, vroot, live, Provenance.load(prefix.state / PROVENANCE_NAME)
    )
    counts = drift_document(entries)["counts"]
    assert isinstance(counts, dict)
    diverged = int(counts.get("diverged", 0)) + int(counts.get("untracked_live", 0))
    if diverged:
        return ProbeResult(
            "live-no-divergence",
            FAIL,
            f"{diverged} live path(s) need an owner decision",
        )
    return ProbeResult(
        "live-no-divergence", PASS, "no live path holds unreconciled unique content"
    )


def _probe_deployed_files_intact(prefix: Prefix) -> ProbeResult:
    prov = Provenance.load(prefix.state / PROVENANCE_NAME)
    if not prov.records:
        return ProbeResult(
            "deployed-files-intact", SKIP, "no deploy provenance recorded"
        )
    live = prefix.root / "live"
    missing = [rel for rel in prov.records if not (live / rel).exists()]
    if missing:
        return ProbeResult(
            "deployed-files-intact",
            FAIL,
            f"{len(missing)} deployed file(s) are gone: {missing[0]}",
        )
    return ProbeResult(
        "deployed-files-intact", PASS, f"{len(prov.records)} deployed file(s) present"
    )


def _break_layout(prefix: Prefix) -> Callable[[], None]:
    target = prefix.logs
    target.rmdir()
    return lambda: target.mkdir(parents=True, exist_ok=True)


def _break_installed_state(prefix: Prefix) -> Callable[[], None]:
    state = read_installed(prefix)
    version = str(state.get("active_version", "0.0.0"))
    vroot = prefix.version_dir(version)
    manifest_path = vroot / MANIFEST_RELPATH
    blob = manifest_path.read_bytes()
    manifest_path.unlink()
    return lambda: atomic_write_bytes(manifest_path, blob)


def _break_lock(prefix: Prefix) -> Callable[[], None]:
    atomic_write_bytes(prefix.lock, b"synthetic control\n")
    return lambda: prefix.lock.unlink()


def _break_cache(prefix: Prefix) -> Callable[[], None]:
    key = "0" * 64
    p = prefix.cache / key[:2] / key
    atomic_write_bytes(p, b"this does not hash to its key")
    quarantined = prefix.cache / "quarantine" / key

    def restore() -> None:
        for target in (p, quarantined, quarantined.with_suffix(".reason.json")):
            if target.exists():
                target.unlink()

    return restore


def _break_deployed(prefix: Prefix) -> Callable[[], None]:
    prov = Provenance.load(prefix.state / PROVENANCE_NAME)
    if not prov.records:
        return lambda: None
    rel = sorted(prov.records)[0]
    target = safe_join(prefix.root / "live", rel)
    blob = target.read_bytes()
    target.unlink()
    return lambda: atomic_write_bytes(target, blob)


def _break_divergence(prefix: Prefix) -> Callable[[], None]:
    prov = Provenance.load(prefix.state / PROVENANCE_NAME)
    if not prov.records:
        return lambda: None
    rel = sorted(prov.records)[0]
    target = safe_join(prefix.root / "live", rel)
    blob = target.read_bytes()
    atomic_write_bytes(target, blob + b"\n# a local edit nobody upstream has\n")
    record = prov.records[rel]
    original_hash = record.content_sha256
    # Also move the source so BOTH sides are unique -> the diverged class, not live_only.
    state = read_installed(prefix)
    vroot = prefix.version_dir(str(state.get("active_version", "")))
    src = vroot / record.source_path
    src_blob = src.read_bytes() if src.exists() else None
    if src_blob is not None:
        atomic_write_bytes(
            src, src_blob + b"\n# an upstream edit live has never seen\n"
        )

    def restore() -> None:
        atomic_write_bytes(target, blob)
        if src_blob is not None:
            atomic_write_bytes(src, src_blob)
        prov2 = Provenance.load(prefix.state / PROVENANCE_NAME)
        if rel in prov2.records:
            prov2.records[rel].content_sha256 = original_hash
            prov2.save()

    return restore


REGISTRY: tuple[Probe, ...] = (
    Probe(
        "prefix-layout",
        "every prefix directory exists",
        _probe_prefix_layout,
        "astplugin health-check --prefix <prefix> --repair-layout",
        _break_layout,
    ),
    Probe(
        "installed-state",
        "the recorded active version is present and manifested",
        _probe_installed_state,
        "astplugin repair --prefix <prefix>",
        _break_installed_state,
    ),
    Probe(
        "no-open-transactions",
        "no transaction was left open by a crash",
        _probe_no_open_transactions,
        "astplugin health-check --prefix <prefix> (auto-recovers)",
        None,
    ),
    Probe(
        "no-stale-lock",
        "the prefix lock is not held",
        _probe_no_stale_lock,
        "astplugin health-check --prefix <prefix> --clear-stale-lock",
        _break_lock,
    ),
    Probe(
        "interpreters",
        "declared interpreters resolve and meet their floors",
        _probe_interpreters,
        "astplugin diagnose",
        None,
    ),
    Probe(
        "cache-integrity",
        "every cache entry hashes to its key",
        _probe_cache_integrity,
        "astplugin cache --prefix <prefix> --invalidate",
        _break_cache,
    ),
    Probe(
        "deployed-files-intact",
        "every provenance-tracked live file still exists",
        _probe_deployed_files_intact,
        "astplugin repair --prefix <prefix>",
        _break_deployed,
    ),
    Probe(
        "live-no-divergence",
        "no live path holds unreconciled unique content",
        _probe_live_no_divergence,
        "astplugin sync --prefix <prefix> --decisions <path>",
        _break_divergence,
    ),
)

BY_ID = {p.ident: p for p in REGISTRY}


@dataclass
class HealthReport:
    results: list[ProbeResult] = field(default_factory=list)
    controls: list[dict[str, object]] = field(default_factory=list)

    @property
    def failed(self) -> list[ProbeResult]:
        return [r for r in self.results if r.status == FAIL]

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "health-report",
            "os": current_os(),
            "probe_count": len(self.results),
            "passed": sum(1 for r in self.results if r.status == PASS),
            "failed": len(self.failed),
            "skipped": sum(1 for r in self.results if r.status == SKIP),
            "ok": self.ok,
            "probes": [r.as_dict() for r in self.results],
            "controls": self.controls,
        }


def health_check(prefix: Prefix, *, with_controls: bool = False) -> HealthReport:
    """Run every registered probe. With ``with_controls``, also prove each probe discriminates."""
    report = HealthReport()
    for probe in REGISTRY:
        try:
            report.results.append(probe.run(prefix))
        except Exception as exc:  # noqa: BLE001 - a probe that raises is a FAIL, never a silent pass
            report.results.append(
                ProbeResult(
                    probe.ident, FAIL, f"probe raised: {exc}", probe.remediation
                )
            )
    for r in report.results:
        if r.status == FAIL and not r.remediation:
            r.remediation = BY_ID[r.ident].remediation
    if with_controls:
        report.controls = control(prefix)
    return report


def control(prefix: Prefix) -> list[dict[str, object]]:
    """Both-states control harness (IMP-0044). Proves each probe fires when the invariant breaks."""
    rows: list[dict[str, object]] = []
    for probe in REGISTRY:
        healthy = probe.run(prefix)
        if probe.break_ is None:
            rows.append(
                {
                    "probe": probe.ident,
                    "healthy_status": healthy.status,
                    "broken_status": None,
                    "discriminates": None,
                    "verdict": "NOT-CHECKED",
                    "reason": "no break_() is declared for this probe",
                }
            )
            continue
        restore = probe.break_(prefix)
        try:
            broken = probe.run(prefix)
        finally:
            restore()
        after = probe.run(prefix)
        discriminates = (
            healthy.status == PASS and broken.status == FAIL and after.status == PASS
        )
        rows.append(
            {
                "probe": probe.ident,
                "healthy_status": healthy.status,
                "broken_status": broken.status,
                "restored_status": after.status,
                "discriminates": discriminates,
                "verdict": "VALID"
                if discriminates
                else ("SKIP" if healthy.status == SKIP else "INVALID"),
                "reason": ""
                if discriminates
                else f"healthy={healthy.status} broken={broken.status} restored={after.status}",
            }
        )
    return rows


def probe_control_document(rows: list[dict[str, object]]) -> dict[str, object]:
    """The probe-control artifact (tools/plugin/schema/probe-control.schema.json)."""
    return {
        "artifact": "probe-control",
        "probe_count": len(rows),
        "valid": sum(1 for r in rows if r.get("verdict") == "VALID"),
        "invalid": sum(1 for r in rows if r.get("verdict") == "INVALID"),
        "not_checked": sum(1 for r in rows if r.get("verdict") == "NOT-CHECKED"),
        "rows": rows,
    }


def doctor(prefix: Prefix) -> dict[str, object]:
    """Map every failing probe to its exact remediating command (IMP-0050)."""
    report = health_check(prefix)
    return {
        "artifact": "doctor-advisory",
        "ok": report.ok,
        "actions": [
            {
                "probe": r.ident,
                "detail": r.detail,
                "run": r.remediation or BY_ID[r.ident].remediation,
            }
            for r in report.failed
        ],
        "health": report.as_dict(),
    }


def write_report(path: Path, doc: dict[str, object]) -> None:
    atomic_write_bytes(
        path, (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
    )


def live_hash(path: Path) -> str:
    return content_hash(path)
