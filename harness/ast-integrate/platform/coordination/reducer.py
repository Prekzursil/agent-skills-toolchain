"""The SHARED completion reducer, reached by delegation - and the gate that keeps it the only one.

There is exactly ONE completion predicate on this platform:
``platform/lib/completion_predicate.py`` (twelve conditions, spec lines 10631-10644). This module
does not re-implement it, does not wrap its verdict in a second opinion, and does not add a
thirteenth condition. It:

  * re-exports the delegate's public surface so a coordination call site never needs a second
    import path (one import path, one plane);
  * resolves a CLAIM to the receipt it recorded and evaluates that receipt through the delegate;
  * ships :func:`assert_single_reducer`, a mechanical gate that fails if a second reducer ever
    appears inside this package.

WHY A GATE AND NOT A CONVENTION

"Duplicate control planes are forbidden" is unenforceable as prose. A future edit that adds a
convenient local ``def evaluate(...)`` here would silently create a second plane, and the two
would drift - which is how condition 9 came to be enforced by ``==`` on free text in the first
place. So the prohibition is a test: :func:`assert_single_reducer` parses every module in this
package and reports any module-level definition of the delegate's decision surface.

The detector is proven in BOTH STATES by ``test_reducer.py``: it must find a synthetic duplicate
plane written to a temp directory (known-broken) and must report clean on this package
(known-good). A detector that has only been run against the clean state measures nothing.

VERDICTS PASS THROUGH UNCHANGED. In particular ``NOT-CHECKED`` stays ``NOT-CHECKED``: a claim
whose receipt leaves a condition unmeasured is INDETERMINATE, never folded into a pass.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from . import _libpath  # noqa: F401  - side effect: platform/lib on sys.path
from .claims import Claim, ClaimState
from .errors import DuplicateControlPlane, StoreCorrupt
from .store import Store

import completion_predicate as _delegate  # noqa: E402  - resolved by _libpath above

__all__ = [
    "BANNED_DEFINITIONS",
    "DELEGATE_MODULE",
    "Outcome",
    "PredicateOptions",
    "PredicateResult",
    "REDUCER_ID",
    "SinglePlaneReport",
    "Verdict",
    "assert_single_reducer",
    "evaluate",
    "load_receipt",
    "reduce_claim",
    "scan_for_duplicate_planes",
]

DELEGATE_MODULE = "completion_predicate"

# --- the delegate's surface, re-exported. These are ALIASES, not definitions. ------------------
REDUCER_ID: str = _delegate.REDUCER_ID
evaluate = _delegate.evaluate
load_receipt = _delegate.load_receipt
PredicateOptions = _delegate.PredicateOptions
PredicateResult = _delegate.PredicateResult
Verdict = _delegate.Verdict
Outcome = _delegate.Outcome

#: Module-level names whose definition inside this package would constitute a second control
#: plane. ``evaluate`` is the decision entry point; the other three are the delegate's condition
#: tables, which only a re-implementation would need.
BANNED_DEFINITIONS: frozenset[str] = frozenset(
    {"evaluate", "CONDITIONS", "CONDITION_TEXT", "NON_WAIVABLE"}
)

#: Number of verbatim condition texts in one .py file that indicates a re-transcription.
_CONDITION_TEXT_THRESHOLD = 3


@dataclass(frozen=True)
class SinglePlaneReport:
    """Positive-form result: N of N modules scanned, and what was found."""

    modules_scanned: int
    modules: tuple[str, ...]
    violations: tuple[dict[str, Any], ...]
    delegate_module: str
    delegate_reducer_id: str

    @property
    def ok(self) -> bool:
        """True only when the delegate is genuinely the delegate AND nothing else defines one.

        Asserts the POSITIVE. A report that merely said "no violations" would pass when the scan
        found zero modules - the measured "0/0 conditions, 0 blocking read as PASS" defect.
        """
        return (
            self.modules_scanned > 0
            and not self.violations
            and self.delegate_module == DELEGATE_MODULE
            and self.delegate_reducer_id == _delegate.REDUCER_ID
        )

    @property
    def sentinel_line(self) -> str:
        if self.ok:
            return (
                f"SUCCESS:single-reducer modules={self.modules_scanned} "
                f"delegate={self.delegate_module} violations=0"
            )
        return (
            f"FAILED:single-reducer modules={self.modules_scanned} "
            f"violations={len(self.violations)} delegate={self.delegate_module}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "single_reducer_report",
            "modules_scanned": self.modules_scanned,
            "modules": list(self.modules),
            "violations": [dict(v) for v in self.violations],
            "delegate_module": self.delegate_module,
            "delegate_reducer_id": self.delegate_reducer_id,
            "ok": self.ok,
            "sentinel_line": self.sentinel_line,
        }


def _aliased_names(tree: ast.Module) -> set[str]:
    """Names bound by an import in this module - aliases, never definitions."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
    return bound


def _delegate_alias_targets(tree: ast.Module) -> set[str]:
    """Module-level ``X = <imported-module>.attr`` assignments: re-exports, not definitions."""
    imported_modules = {
        alias.asname or alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    out: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Attribute) or not isinstance(
            value.value, ast.Name
        ):
            continue
        if value.value.id not in imported_modules:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                out.add(target.id)
    return out


def scan_for_duplicate_planes(package_dir: str | Path) -> SinglePlaneReport:
    """Parse every ``*.py`` under ``package_dir`` and report second-plane definitions.

    Test modules are scanned too: a duplicate reducer smuggled into a test fixture would drift
    just as badly as one in production code.
    """
    root = Path(package_dir)
    violations: list[dict[str, Any]] = []
    modules: list[str] = []
    condition_texts = tuple(_delegate.CONDITION_TEXT.values())

    for py in sorted(root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        modules.append(py.name)
        source = py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py))
        aliases = _aliased_names(tree) | _delegate_alias_targets(tree)
        for node in tree.body:
            names: list[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            for name in names:
                if name in BANNED_DEFINITIONS and name not in aliases:
                    violations.append(
                        {
                            "file": py.name,
                            "line": node.lineno,
                            "symbol": name,
                            "reason": (
                                f"module-level definition of {name!r} is the delegate's decision "
                                f"surface; import it from {DELEGATE_MODULE} instead of defining it"
                            ),
                        }
                    )
        hits = [t for t in condition_texts if t in source]
        if len(hits) >= _CONDITION_TEXT_THRESHOLD:
            violations.append(
                {
                    "file": py.name,
                    "line": 0,
                    "symbol": "<condition-texts>",
                    "reason": (
                        f"{len(hits)} of the delegate's 12 condition texts appear verbatim; a "
                        "re-transcription of the condition table is a second control plane"
                    ),
                }
            )

    return SinglePlaneReport(
        modules_scanned=len(modules),
        modules=tuple(modules),
        violations=tuple(violations),
        delegate_module=getattr(evaluate, "__module__", "?"),
        delegate_reducer_id=REDUCER_ID,
    )


def assert_single_reducer(package_dir: str | Path | None = None) -> SinglePlaneReport:
    """Raise :class:`DuplicateControlPlane` unless this package has exactly one reducer."""
    report = scan_for_duplicate_planes(package_dir or Path(__file__).resolve().parent)
    if not report.ok:
        raise DuplicateControlPlane(
            report.sentinel_line
            + "; violations="
            + "; ".join(
                f"{v['file']}:{v['line']} {v['symbol']}" for v in report.violations
            )
        )
    return report


def reduce_claim(
    store: Store,
    unit_id: str,
    opts: Any,
    *,
    require_completed_state: bool = False,
) -> PredicateResult:
    """Evaluate the receipt a claim recorded, through the SHARED reducer.

    ``opts`` is a ``completion_predicate.PredicateOptions``. It is passed through untouched: unit
    CLASS policy belongs to the caller, and a receipt that could declare its own applicability
    would be self-certifying - the failure the predicate exists to prevent.
    """
    raw = store.read(store.path_for("claims", unit_id))
    if raw is None:
        raise StoreCorrupt(f"no claim for unit {unit_id!r}")
    claim = Claim.from_dict(raw)
    if require_completed_state and claim.state is not ClaimState.COMPLETED:
        raise StoreCorrupt(
            f"claim for {unit_id!r} is {claim.state.value}, not COMPLETED; a reduction was "
            "requested on a unit that never claimed to be finished"
        )
    if not claim.receipt_path:
        raise StoreCorrupt(
            f"claim for {unit_id!r} records no receipt_path; there is nothing to reduce. A claim "
            "without a receipt is not an incomplete pass, it is an unmeasured unit."
        )
    receipt = load_receipt(claim.receipt_path)
    return evaluate(receipt, opts)


def main(argv: Sequence[str] | None = None) -> int:
    """The single-plane gate's body. Entry point: ``single_reducer_gate.py``.

    Deliberately NOT invoked via ``python reducer.py``: this module uses relative imports, so
    running the file directly raises ``ImportError: attempted relative import with no known parent
    package``. Measured while adding this gate - a "python <module>" gate that cannot even import
    is the no-op gate ci-hygiene section 1 warns about, one step worse. The thin wrapper script
    fixes ``sys.path`` first and is the only supported entry point.

    Written to the shape ``rules/common/ci-hygiene.md`` section 1 requires, because the failure it
    describes is exactly what a naive ``python -m`` gate would be here: a module whose logic lives
    in unreferenced functions imports cleanly, prints nothing, and exits 0 forever.

    So this ``main`` (a) enumerates the ACTUAL inputs, (b) FAILS CLOSED - an empty walk returns
    non-zero rather than "nothing found, therefore fine" - and (c) emits a terminal
    ``SUCCESS:``/``FAILED:`` marker. ``test_reducer.py`` runs it against a known-bad tree and
    requires exit 1, so the gate has been observed going red.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    target = Path(args[0]) if args else Path(__file__).resolve().parent
    if not target.is_dir():
        print(f"FAILED:single-reducer {target} is not a directory")
        return 1
    report = scan_for_duplicate_planes(target)
    for violation in report.violations:
        print(
            f"FAILED:single-reducer {violation['file']}:{violation['line']} "
            f"{violation['symbol']} - {violation['reason']}"
        )
    print(report.sentinel_line)
    return 0 if report.ok else 1
