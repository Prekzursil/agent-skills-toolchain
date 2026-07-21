"""compchem-validators · posebusters.py

Post-dock POSE-VALIDITY checking + a SHADOW-mode compchem claim-gate helper.

Two capabilities, both designed to ride the *existing* bus (lexical + file-presence;
no trained critic, no vector-DB, no 2nd runtime) and both **fail-open**:

1. ``check_pose`` / ``check_poses`` — validate that a docked pose is physically
   plausible. Uses the real `PoseBusters` package when it is importable; otherwise
   degrades to a coarse, honestly-labelled pure-Python geometry sanity pass
   (bond-length range + non-bonded steric clash) so the skill is useful even on a
   host where the heavy scientific stack (rdkit/posebusters — currently incompatible
   with Python 3.14) is not installed.

2. ``compchem_claim_advisory`` — the "docking done / ΔG=… / MD converged" CLAIM-GATE
   that the queue folds into ``claim_warning``. Shipped here as an importable
   **SHADOW-mode** helper: it OBSERVES a claim, checks whether a validity artifact
   (a PoseBusters pass / a redock RMSD / a convergence artifact) accompanies it, and
   if the claim fires with NO evidence it LOGS an advisory to a separate, bounded,
   auto-rotating sink and returns an advisory dict. It NEVER blocks, NEVER nags,
   NEVER raises — per COUNCIL C5 (shadow-mode as the graduation discipline) and C1.5
   (domain gates are project-scoped, off-by-default globally).

Evidence: MASTER-DECISION-QUEUE E.4 (PoseBusters post-dock pose validity;
"compchem-preflight guards input, nothing guards output"); COUNCIL-VERDICT C5.

The gate module (``claim_warning``) is intentionally NOT edited by this skill — it is
out of scope and project-scoped by council decision. This file provides the callable
the gate *would* consume; wiring is the harness owner's decision.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "SHADOW_CONTRACT",
    "PoseReport",
    "check_pose",
    "check_poses",
    "compchem_claim_advisory",
    "classify_compchem_claim",
    "has_validity_evidence",
    "posebusters_available",
    "shadow_log_path",
]

# ---------------------------------------------------------------------------
# Anti-zombie SHADOW contract (COUNCIL C5.i): every shadowed gate carries a
# named promotion metric, owner, graduation deadline and a falsifiable fire-rate
# hypothesis so it can never rot in shadow limbo.
# ---------------------------------------------------------------------------
SHADOW_CONTRACT: dict[str, Any] = {
    "module": "compchem-claim-gate",
    "mode": "SHADOW",  # OFF -> SHADOW -> ADVISE -> ENFORCE ; starts here, never auto-enforces
    "risk_class": "heuristic-nag",  # C5 tier 3: full ladder required
    "promotion_metric": "shadow-precision vs owner claude-reflect corrections on compchem claims",
    "promotion_bar": "precision >= 0.80 over >= 20 fired events, false-nag < 5%",
    "owner": "harness owner (darias.grama)",
    "graduation_deadline_days": 30,
    "fire_rate_hypothesis": "fires on < 2% of all messages (compchem claims are rare); "
    "of those, > 60% genuinely lack a co-located validity artifact",
    "never": "blocks, nags interactively, or raises — observe + log only",
}

# ---------------------------------------------------------------------------
# Bounded, auto-rotating, SEPARATE shadow sink (COUNCIL C5.iii): shadow logs must
# NOT go to the main ledger (terminal.jsonl is already multi-MB); they go to their
# own rotating file so the fitness scorer (F1) that reads them is never self-DoS'd.
# ---------------------------------------------------------------------------
_SHADOW_MAX_BYTES = 512 * 1024  # rotate at 512 KB
_SHADOW_BACKUPS = 1  # keep one .1 backup


def shadow_log_path() -> Path:
    """Resolve the shadow-sink file (override with $COMPCHEM_SHADOW_DIR)."""
    base = os.environ.get("COMPCHEM_SHADOW_DIR")
    if base:
        d = Path(base)
    else:
        d = Path.home() / ".claude" / "gem-hunt-2026-07-12" / "shadow"
    return d / "compchem-claim-gate.jsonl"


def _shadow_log(event: dict[str, Any]) -> Path | None:
    """Append one JSONL event to the bounded rotating sink. Fail-open (returns None)."""
    try:
        path = shadow_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Rotate if over the size cap.
        try:
            if path.exists() and path.stat().st_size >= _SHADOW_MAX_BYTES:
                backup = path.with_suffix(path.suffix + ".1")
                if backup.exists():
                    backup.unlink()
                path.rename(backup)
        except OSError:
            pass
        line = json.dumps(event, ensure_ascii=False, default=str)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return path
    except Exception:
        # Fail-open: a logging failure must never affect the caller.
        return None


# ===========================================================================
# 1. POSE VALIDITY
# ===========================================================================

# Coarse fallback geometry thresholds (Angstroms). Honestly labelled — these are
# NOT the PoseBusters reference-distribution checks, just a physical-plausibility
# floor so an obviously-broken pose (overlapping atoms / absurd bonds) is caught
# even without rdkit/posebusters.
_MIN_BOND_A = 0.7
_MAX_BOND_A = 2.6
_CLASH_A = 1.2  # non-bonded heavy-atom clash floor


@dataclass
class PoseReport:
    """Structured pose-validity verdict."""

    pose_id: str
    valid: bool
    engine: str  # "posebusters" | "geometry-fallback" | "unparsed"
    checks: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    summary: str = ""
    n_atoms: int = 0
    n_bonds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def marker(self) -> str:
        """Terminal-state marker for a docking-validation step (AGENTS.md §4)."""
        tag = "PASS" if self.valid else "FAIL"
        return f"POSEBUSTERS:{tag} id={self.pose_id} engine={self.engine} " + (
            "ok" if self.valid else "failures=" + ",".join(self.failures)
        )


def posebusters_available() -> bool:
    """True only if the *real* PoseBusters package (with its ``PoseBusters`` API)
    is reachable.

    NB name-collision: this very file is ``posebusters.py``. If it is imported as
    the top-level module ``posebusters`` it SHADOWS the PyPI package, and a bare
    ``import posebusters`` would return *this* module (giving a false positive).
    We guard by requiring the hallmark ``PoseBusters`` attribute, which this
    module deliberately does not define — so under shadowing we honestly report
    False and fall back to the geometry floor. To use the authoritative checker,
    import these helpers under a distinct namespace (see SKILL.md · Consumption).
    """
    try:
        import posebusters as _pkg  # type: ignore

        return hasattr(_pkg, "PoseBusters")
    except Exception:
        return False


def check_pose(
    pose_path: str | os.PathLike[str] | None = None,
    *,
    cond: str = "dock",
    pose_id: str | None = None,
    sdf_text: str | None = None,
) -> PoseReport:
    """Validate a single docked pose.

    Prefers the real ``PoseBusters`` (config ``cond``: "dock"|"redock"|"mol").
    Falls back to :func:`_geometry_sanity` (bond-range + steric-clash) when the
    package is unavailable. ``sdf_text`` lets you validate an in-memory pose
    without touching disk (used by the tests and by streamed MCP output).
    """
    pid = pose_id or (Path(pose_path).name if pose_path else "inline")
    if posebusters_available() and pose_path is not None:
        try:
            return _run_posebusters(str(pose_path), cond=cond, pose_id=pid)
        except Exception as exc:  # fall through to geometry sanity
            report = _geometry_from_any(pose_path, sdf_text, pid)
            report.checks["posebusters_error"] = str(exc)
            return report
    return _geometry_from_any(pose_path, sdf_text, pid)


def check_poses(
    poses: Iterable[str | os.PathLike[str]], *, cond: str = "dock"
) -> list[PoseReport]:
    """Validate many poses; returns one report each (invalid poses do not abort)."""
    out: list[PoseReport] = []
    for p in poses:
        try:
            out.append(check_pose(p, cond=cond))
        except Exception as exc:
            out.append(
                PoseReport(
                    pose_id=str(p),
                    valid=False,
                    engine="unparsed",
                    failures=["exception"],
                    summary=f"could not validate: {exc}",
                )
            )
    return out


def _run_posebusters(pose_path: str, *, cond: str, pose_id: str) -> PoseReport:
    """Drive the real PoseBusters package. Only called when it imports."""
    from posebusters import PoseBusters  # type: ignore

    buster = PoseBusters(config=cond)
    df = buster.bust([pose_path], full_report=True)
    # PoseBusters returns a DataFrame of boolean checks; a pose is valid iff all True.
    bool_cols = [c for c in df.columns if df[c].dtype == bool]
    row = df.iloc[0] if len(df) else None
    checks: dict[str, Any] = {}
    failures: list[str] = []
    if row is not None:
        for c in bool_cols:
            passed = bool(row[c])
            checks[c] = passed
            if not passed:
                failures.append(c)
    valid = len(failures) == 0 and row is not None
    return PoseReport(
        pose_id=pose_id,
        valid=valid,
        engine="posebusters",
        checks=checks,
        failures=failures,
        summary="all PoseBusters checks passed"
        if valid
        else f"{len(failures)} PoseBusters check(s) failed",
    )


def _geometry_from_any(
    pose_path: str | os.PathLike[str] | None,
    sdf_text: str | None,
    pose_id: str,
) -> PoseReport:
    text = sdf_text
    if text is None and pose_path is not None:
        try:
            text = Path(pose_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return PoseReport(
                pose_id=pose_id,
                valid=False,
                engine="unparsed",
                failures=["read-error"],
                summary=f"cannot read pose: {exc}",
            )
    if not text:
        return PoseReport(
            pose_id=pose_id,
            valid=False,
            engine="unparsed",
            failures=["empty"],
            summary="no pose content",
        )
    return _geometry_sanity(text, pose_id)


def _parse_sdf_v2000(
    text: str,
) -> tuple[list[tuple[float, float, float, str]], list[tuple[int, int]]]:
    """Tolerant SDF/MOL V2000 parse → (atoms[(x,y,z,elem)], bonds[(i,j)] 0-indexed).

    Whitespace-tolerant: standard SDF is fixed-width but space-padded, so a token
    split recovers x/y/z/element and the bond i/j/type reliably for well-formed
    files. Raises ValueError on a structure it cannot read.
    """
    lines = text.splitlines()
    # Counts line is the 4th line (index 3) in a MOL block.
    counts_idx = 3
    if len(lines) <= counts_idx:
        raise ValueError("too short for a MOL/SDF block")
    counts = lines[counts_idx]
    try:
        n_atoms = int(counts[0:3])
        n_bonds = int(counts[3:6])
    except ValueError:
        parts = counts.split()
        n_atoms = int(parts[0])
        n_bonds = int(parts[1])
    atoms: list[tuple[float, float, float, str]] = []
    a0 = counts_idx + 1
    for k in range(n_atoms):
        row = lines[a0 + k].split()
        if len(row) < 4:
            raise ValueError(f"bad atom line: {lines[a0 + k]!r}")
        x, y, z = float(row[0]), float(row[1]), float(row[2])
        atoms.append((x, y, z, row[3]))
    bonds: list[tuple[int, int]] = []
    b0 = a0 + n_atoms
    for k in range(n_bonds):
        row = lines[b0 + k].split()
        if len(row) < 2:
            raise ValueError(f"bad bond line: {lines[b0 + k]!r}")
        i, j = int(row[0]) - 1, int(row[1]) - 1
        bonds.append((i, j))
    return atoms, bonds


def _dist(
    a: tuple[float, float, float, str], b: tuple[float, float, float, str]
) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _geometry_sanity(sdf_text: str, pose_id: str) -> PoseReport:
    """Coarse pure-Python physical-plausibility floor (no rdkit)."""
    try:
        atoms, bonds = _parse_sdf_v2000(sdf_text)
    except (ValueError, IndexError) as exc:
        return PoseReport(
            pose_id=pose_id,
            valid=False,
            engine="unparsed",
            failures=["parse-error"],
            summary=f"could not parse pose geometry: {exc}",
        )

    failures: list[str] = []
    bonded = {frozenset((i, j)) for i, j in bonds}

    # Heavy atoms only for the clash check (H's legitimately sit close).
    heavy = [k for k, a in enumerate(atoms) if a[3] != "H"]

    # 1) bond-length range
    bad_bonds: list[tuple[int, int, float]] = []
    for i, j in bonds:
        if 0 <= i < len(atoms) and 0 <= j < len(atoms):
            d = _dist(atoms[i], atoms[j])
            if d < _MIN_BOND_A or d > _MAX_BOND_A:
                bad_bonds.append((i + 1, j + 1, round(d, 3)))
    if bad_bonds:
        failures.append("bond_lengths_in_range")

    # 2) non-bonded steric clash (heavy-atom, exclude directly bonded pairs)
    clashes: list[tuple[int, int, float]] = []
    for xi in range(len(heavy)):
        for xj in range(xi + 1, len(heavy)):
            i, j = heavy[xi], heavy[xj]
            if frozenset((i, j)) in bonded:
                continue
            d = _dist(atoms[i], atoms[j])
            if d < _CLASH_A:
                clashes.append((i + 1, j + 1, round(d, 3)))
    if clashes:
        failures.append("no_internal_clash")

    # 3) all-atoms-connected sanity (degenerate: every atom has >=1 bond when n>1)
    if len(atoms) > 1 and bonds:
        touched = {i for b in bonds for i in b}
        if len(touched) < len(atoms):
            failures.append("all_atoms_connected")

    valid = not failures
    return PoseReport(
        pose_id=pose_id,
        valid=valid,
        engine="geometry-fallback",
        checks={
            "bad_bonds": bad_bonds,
            "clashes": clashes,
            "note": "coarse geometry floor (no rdkit/posebusters); NOT the full "
            "PoseBusters reference-distribution suite — install posebusters for "
            "the authoritative check",
        },
        failures=failures,
        summary="passed coarse geometry floor"
        if valid
        else "coarse geometry floor flagged: " + ", ".join(failures),
        n_atoms=len(atoms),
        n_bonds=len(bonds),
    )


# ===========================================================================
# 2. SHADOW-MODE COMPCHEM CLAIM-GATE
# ===========================================================================

# Lexical patterns for a compchem *result claim* (on the existing bus — same
# mechanism family as ClaimWarningModule's "tests pass" detector).
_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bdock(?:ing|ed)\b.{0,30}\b(?:done|complete|success|finished)\b",
        r"\b(?:pose|ligand)s?\b.{0,20}\bdocked\b",
        r"\b(?:Δ?G|dG|delta[-\s]?G)\b\s*[=:~<>]",
        r"\bbinding\s+(?:energy|affinity|free\s+energy)\b",
        r"\bMM[-\s]?GBSA\b",
        r"\bkcal\s*/\s*mol\b",
        r"\b(?:MD|simulation|trajectory)\b.{0,20}\b(?:converged|equilibrated)\b",
        r"\bconverged\b.{0,20}\b(?:MD|simulation|trajectory)\b",
        r"\bglide\s*(?:score|gscore)\b",
        r"\bfree[-\s]energy\s+perturbation\b|\bFEP\b.{0,20}\b(?:done|complete|result)\b",
    )
)

# Lexical / structural markers that a VALIDITY ARTIFACT is present.
_EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bposebusters?\b",
        r"\bpb[_-]?valid\b|\bpose[_-]?valid\b",
        r"\bredock\b.{0,20}\brmsd\b|\brmsd\b.{0,20}\bredock\b",
        r"\brmsd\s*[=:<]\s*\d",
        r"\bconvergence\b.{0,20}(?:plot|artifact|check|metric)",
        r"\bblock[-\s]?averag",
        r"\bequilibration\b.{0,20}(?:plateau|converged)",
    )
)

# File-name markers of a validity artifact on disk.
_EVIDENCE_FILE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"posebuster",
        r"pb[_-]?report",
        r"redock.*rmsd|rmsd.*redock",
        r"convergence",
        r"_pv\.mae|mmgbsa.*\.csv|-out\.csv",
    )
)


def classify_compchem_claim(text: str) -> dict[str, Any]:
    """Return {claim: bool, matched: [patterns]} for a compchem result claim."""
    matched = [p.pattern for p in _CLAIM_PATTERNS if p.search(text or "")]
    return {"claim": bool(matched), "matched": matched}


def has_validity_evidence(
    text: str, artifacts: Sequence[str] | None = None
) -> dict[str, Any]:
    """Detect a co-located validity artifact in the message text or artifact list.

    A file-name marker counts only if the file actually EXISTS (presence, not a
    mere mention — matching the honesty intent: an `_pv.maegz` string in prose is
    not evidence, an existing MM-GBSA out.csv is).
    """
    text = text or ""
    text_hits = [p.pattern for p in _EVIDENCE_PATTERNS if p.search(text)]
    file_hits: list[str] = []
    for a in artifacts or []:
        name = str(a)
        if any(p.search(name) for p in _EVIDENCE_FILE_PATTERNS):
            exists = False
            try:
                exists = Path(name).exists()
            except OSError:
                exists = False
            if exists:
                file_hits.append(name)
    return {
        "evidence": bool(text_hits or file_hits),
        "text_markers": text_hits,
        "file_markers": file_hits,
    }


def compchem_claim_advisory(
    text: str,
    *,
    artifacts: Sequence[str] | None = None,
    log: bool = True,
    session: str | None = None,
) -> dict[str, Any]:
    """SHADOW-mode compchem claim-gate. OBSERVE + LOG ONLY — never blocks/raises.

    Returns an advisory dict. ``would_fire`` is True when a compchem result claim
    is present with NO co-located validity artifact — i.e. what an ENFORCE-mode
    gate WOULD flag. In SHADOW mode this only writes to the bounded rotating sink
    and hands the advisory back to the caller (the ``claim_warning`` module would
    decide; this helper never decides for it).
    """
    try:
        claim = classify_compchem_claim(text)
        evidence = has_validity_evidence(text, artifacts)
        would_fire = bool(claim["claim"]) and not evidence["evidence"]
        advisory = None
        if would_fire:
            advisory = (
                "compchem result claim detected without a co-located validity "
                "artifact. Before treating this as done, attach ONE of: a "
                "PoseBusters pass (check_pose), a redock RMSD (< ~2 Å), or an MD "
                "convergence artifact. A pose can score well yet be physically "
                "impossible."
            )
        result = {
            "mode": SHADOW_CONTRACT["mode"],
            "would_fire": would_fire,
            "claim": claim,
            "evidence": evidence,
            "advisory": advisory,
            "blocked": False,  # invariant: shadow never blocks
            "ts": time.time(),
        }
        if log and claim["claim"]:  # only log when a claim was actually seen
            _shadow_log(
                {
                    "module": SHADOW_CONTRACT["module"],
                    "mode": SHADOW_CONTRACT["mode"],
                    "would_fire": would_fire,
                    "session": session,
                    "matched": claim["matched"],
                    "evidence": evidence,
                    "text_head": (text or "")[:200],
                    "ts": result["ts"],
                }
            )
        return result
    except Exception as exc:
        # Fail-open: the gate can never break the caller.
        return {
            "mode": "SHADOW",
            "would_fire": False,
            "blocked": False,
            "error": str(exc),
        }


if __name__ == "__main__":  # tiny smoke when run directly
    print("posebusters_available:", posebusters_available())
    demo = compchem_claim_advisory("Docking done, dG = -9.2 kcal/mol")
    print("would_fire (no evidence):", demo["would_fire"])
    print("advisory:", demo["advisory"])
