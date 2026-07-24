#!/usr/bin/env python3
"""Both-states tests for wire-check route extraction and reference resolution.

MEASURED DEFECT (2026-07-24). wire-check reported

    route 'band' (added in health_source.py) is linked/navigated 0x
    route 'driver' ...            route 'name' ...

against `tools/monitorcore/monitorcore/health_source.py`. Probing the real `_extract` over the
real file showed `_ROUTE` matching **`dict.get("key")` calls**, not route registrations:

    L141  group='band'    matched='.get("band"'    line: band=str(obj.get("band", "unknown")),
    L142  group='driver'  matched='.get("driver"'  line: driver=str(obj.get("driver", "")),
    L127  group='name'    matched=".get('name'"    line: f"{t.get('name')}:{t.get('pid')} ..."

The `\\.(?:get|post|...)\\s*\\(` alternative was written for `router.get("/users")` and matches
every Python dict lookup. NOTE the briefing for this defect said the trigger was the DATACLASS
FIELD DECLARATIONS at :60-61 (`band: str = "unknown"`); that premise is REFUTED — those lines
match `_ROUTE` zero times, which the case labelled "dataclass field declarations match _ROUTE 0x"
pins. The names coincide only because the same identifiers are both fields and dict keys.

BOTH STATES. Every "must not be a route" case is paired with a real route dialect that MUST still
be extracted, so a fix that simply stops finding routes fails this file.

Run:  python test_wire_check_routes.py
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

_CHECK = Path(__file__).resolve().parent / "check.py"
_spec = importlib.util.spec_from_file_location("wire_check_under_test", _CHECK)
check = importlib.util.module_from_spec(_spec)
sys.modules["wire_check_under_test"] = check
_spec.loader.exec_module(check)

# Verbatim from tools/monitorcore/monitorcore/health_source.py (the file that produced the fires).
HEALTH_SOURCE = '''
@dataclass(frozen=True)
class HealthPayload:
    """One sentinel sample."""

    band: str = "unknown"
    driver: str = ""
    orphan_count: int = 0


def _to_payload(obj: dict[str, object]) -> HealthPayload:
    orphan_top = tuple(
        f"{t.get('name')}:{t.get('pid')} (ppid {t.get('ppid')}, {t.get('rss_mb')} MB)"
        for t in top
    )
    return HealthPayload(
        band=str(obj.get("band", "unknown")),
        driver=str(obj.get("driver", "")),
        orphan_count=int(num(orph, "count")),
    )


def render(p: HealthPayload) -> str:
    if p.driver:
        return p.band
    return ""
'''

# Each real dialect must survive. `/` is the invariant every one of them shares.
ROUTE_DIALECTS = [
    ("express get", "router.get('/checkout_xyz', checkoutHandler)", "/checkout_xyz"),
    ("express post", 'app.post("/api/login", h)', "/api/login"),
    (
        "flask decorator",
        '@app.route("/admin/users")\ndef users(): pass',
        "/admin/users",
    ),
    ("fastapi decorator", '@router.route("/items/{item_id}")', "/items/{item_id}"),
    (
        "django path",
        "path('articles/<int:year>/', views.year_archive)",
        "articles/<int:year>/",
    ),
    ("react router", '<Route path="/settings" element={<S/>} />', "/settings"),
]

# Ordinary dict lookups that are NOT routes.
DICT_LOOKUPS = [
    ("dict.get str default", 'band=str(obj.get("band", "unknown")),', "band"),
    ("dict.get empty default", 'driver=str(obj.get("driver", "")),', "driver"),
    ("dict.get in f-string", "f\"{t.get('name')}:{t.get('pid')}\"", "name"),
    ("dict.get snake key", "f\"{t.get('rss_mb')} MB\"", "rss_mb"),
    ("config lookup", 'timeout = cfg.get("timeout_seconds", 30)', "timeout_seconds"),
    ("delete by key", 'store.delete("session_token")', "session_token"),
]


def main() -> int:
    cases: list[tuple[str, bool, bool]] = []

    # ---- FIRE side: every real route dialect is still extracted -------------------------
    for label, snippet, want in ROUTE_DIALECTS:
        _syms, routes = check._extract(snippet)
        cases.append((f"route dialect kept: {label} -> {want!r}", want in routes, True))

    # ---- SILENT side: a dict lookup is never a route ------------------------------------
    for label, snippet, key in DICT_LOOKUPS:
        _syms, routes = check._extract(snippet)
        cases.append(
            (f"dict lookup NOT a route: {label} -> {key!r}", key in routes, False)
        )

    # ---- the measured file, end to end --------------------------------------------------
    syms, routes = check._extract(HEALTH_SOURCE)
    cases.append(("health_source.py yields ZERO routes", bool(routes), False))
    cases.append(
        ("health_source.py still yields its real symbol", "HealthPayload" in syms, True)
    )

    # ---- the REFUTED premise, pinned so it cannot be re-asserted ------------------------
    _s, r = check._extract('band: str = "unknown"\ndriver: str = ""\nname: str = "x"\n')
    cases.append(("dataclass field declarations match _ROUTE 0x", bool(r), False))
    # ...and they are not mistaken for top-level definitions either.
    cases.append(("dataclass field declarations are not symbols", bool(_s), False))

    # ---- reference resolution: attribute access + kwarg construction count as USE -------
    # LOCKING tests, not a fix. The briefing suspected _ref_count of failing to resolve these
    # shapes; measured, it does NOT fail — the definition-exclusion regex does not match an
    # annotated field, so `driver: str = ""` and `p.driver` both count. These cases pin that
    # behaviour so a future edit to `def_re` cannot regress it into the false 0 the briefing
    # feared. UNVERIFIED whether some other shape drives _ref_count to a false 0; the settling
    # experiment is an AST-resolver diff over every symbol `_extract` yields repo-wide.
    tmp = Path(tempfile.mkdtemp(prefix="wc-refs-"))
    (tmp / "health_source.py").write_text(HEALTH_SOURCE, encoding="utf-8")
    (tmp / "dead.py").write_text(
        "def never_called_anywhere():\n    return 1\n", encoding="utf-8"
    )
    cases.append(
        (
            "kwarg construction + annotation resolve as references (HealthPayload)",
            check._ref_count(str(tmp), "HealthPayload") > 0,
            True,
        )
    )
    cases.append(
        (
            "attribute access p.driver resolves as a reference",
            check._ref_count(str(tmp), "driver") > 0,
            True,
        )
    )
    cases.append(
        (
            "a genuinely unreferenced symbol still counts 0 (guard not disarmed)",
            check._ref_count(str(tmp), "never_called_anywhere") > 0,
            False,
        )
    )
    shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for name, got, want in cases:
        if got != want:
            ok = False
        print(f"  {'OK ' if got == want else 'XX '} {name}: got={got} want={want}")

    fires = sum(1 for _, _, w in cases if w)
    print(
        f"\nRESULT: {'ALL PASS' if ok else 'FAILURES PRESENT'}  "
        f"({len(cases)} cases: {fires} must hold, {len(cases) - fires} must stay empty)"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
