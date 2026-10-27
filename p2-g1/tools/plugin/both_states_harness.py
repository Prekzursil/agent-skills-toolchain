"""Both-states probe harness: known-broken + known-good fixtures."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "both-states"
BROKEN = FIX / "known-broken" / "payload.txt"
GOOD = FIX / "known-good" / "payload.txt"
FIRE_MARKER = "FIRE_MARKER"

TRUSTED = "TRUSTED"
UNTRUSTWORTHY = "UNTRUSTWORTHY"


@dataclass
class ProbeResult:
    probe_id: str
    trust: str
    reason: str
    skipped: bool = False
    broken_fixture_present: bool = True
    good_fixture_present: bool = True
    broken_verdict: str = ""
    good_verdict: str = ""
    broken_class: str = ""
    good_class: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProbeSpec:
    probe_id: str
    run: Callable[[Path], Any]
    known_broken: Path
    known_good: Path
    description: str = ""


def _classify(verdict: Any) -> str:
    text = str(verdict or "").upper()
    if text in {"FIRED", "FAIL", "FAILED", "HIT"}:
        return "FIRED"
    if text in {"SILENT", "OK", "PASS", "PASSED"}:
        return "SILENT"
    if "FIRE" in text:
        return "FIRED"
    return "SILENT" if text else "SILENT"


def always_ok_probe(_path: Path) -> str:
    return "OK"


def content_marker_probe(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "FIRED" if FIRE_MARKER in text else "SILENT"


def reviewer_always_pass_probe(_path: Path) -> str:
    return "PASS"


def bundled_fixtures() -> tuple[Path, Path]:
    BROKEN.parent.mkdir(parents=True, exist_ok=True)
    GOOD.parent.mkdir(parents=True, exist_ok=True)
    if not BROKEN.is_file():
        BROKEN.write_text(f"payload {FIRE_MARKER}\n", encoding="utf-8", newline="\n")
    if not GOOD.is_file():
        GOOD.write_text("payload healthy\n", encoding="utf-8", newline="\n")
    return BROKEN, GOOD


def evaluate(spec: ProbeSpec) -> ProbeResult:
    broken_p = Path(spec.known_broken)
    good_p = Path(spec.known_good)
    broken_present = broken_p.is_file()
    good_present = good_p.is_file()
    if not broken_present:
        return ProbeResult(
            probe_id=spec.probe_id,
            trust=UNTRUSTWORTHY,
            reason="missing-broken-fixture",
            skipped=False,
            broken_fixture_present=False,
            good_fixture_present=good_present,
            description=spec.description,
        )
    broken_verdict = spec.run(broken_p)
    good_verdict = spec.run(good_p) if good_present else "MISSING"
    b_class = _classify(broken_verdict)
    g_class = _classify(good_verdict)
    if str(broken_verdict) == str(good_verdict) or b_class == g_class:
        trust = UNTRUSTWORTHY
        reason = "same-verdict-both-states"
    else:
        trust = TRUSTED
        reason = "discriminates"
    return ProbeResult(
        probe_id=spec.probe_id,
        trust=trust,
        reason=reason,
        skipped=False,
        broken_fixture_present=True,
        good_fixture_present=good_present,
        broken_verdict=str(broken_verdict),
        good_verdict=str(good_verdict),
        broken_class=b_class,
        good_class=g_class,
        description=spec.description,
    )


def missing_broken_control() -> ProbeResult:
    return evaluate(
        ProbeSpec(
            probe_id="missing-broken",
            run=always_ok_probe,
            known_broken=HERE / "fixtures" / "both-states" / "absent-broken.fixture",
            known_good=GOOD,
            description="known-broken fixture path is absent",
        )
    )


@dataclass
class CatalogEvidence:
    same_run: bool
    results: list[ProbeResult]

    def by_id(self) -> dict[str, ProbeResult]:
        return {r.probe_id: r for r in self.results}

    @property
    def trusted_count(self) -> int:
        return sum(1 for r in self.results if r.trust == TRUSTED)

    @property
    def untrustworthy_count(self) -> int:
        return sum(1 for r in self.results if r.trust == UNTRUSTWORTHY)


def same_run_catalog_evidence() -> CatalogEvidence:
    broken, good = bundled_fixtures()
    useless = evaluate(
        ProbeSpec(
            probe_id="always-ok",
            run=always_ok_probe,
            known_broken=broken,
            known_good=good,
            description="deliberately useless always-OK probe",
        )
    )
    genuine = evaluate(
        ProbeSpec(
            probe_id="content-marker",
            run=content_marker_probe,
            known_broken=broken,
            known_good=good,
            description="genuine detector: fires only when FIRE_MARKER is present",
        )
    )
    return CatalogEvidence(same_run=True, results=[useless, genuine])
