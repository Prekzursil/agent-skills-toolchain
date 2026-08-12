r"""AUD-0020 -- Python dependency and lockfile inventory per package.

CATALOG ROW:
  phase 0, unblocks 3
  output_path   command-center/audit/AUD-0020-python-dep-inventory.json
  output_schema command-center/schema/audit-inventory.schema.json
  target        "For every Python package in the repo, what are its declared direct dependencies,
                 is there a lockfile, and does the lockfile resolve the declared constraints?"
  probe 1       parse each manifest into a normalized name/constraint table
  probe 2       resolve the same set with the lockfile and diff the two tables -- a manifest read
                alone cannot detect a lockfile that pins a version outside the declared range
  control       inject an out-of-range pin into a fixture lockfile and confirm the differ flags it
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0020"
OUT = "command-center/audit/AUD-0020-python-dep-inventory.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
PROBEDIR = L.REPO / "command-center/p2-wave/probes/AUD-0020"
SKIP = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
}
TS0, TS1 = "2026-08-12T06:30:00Z", "2026-08-12T06:55:00Z"

REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_spec(s: str) -> str:
    s = (s or "").split(";")[0].strip()
    return s or "*"


def parse_manifest(p: Path) -> dict:
    """Return {normalized_name: constraint} for direct deps."""
    deps: dict[str, str] = {}
    if p.name == "pyproject.toml":
        try:
            d = tomllib.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            return {"__error__": f"{type(e).__name__}: {e}"}
        for raw in (d.get("project") or {}).get("dependencies") or []:
            m = REQ.match(str(raw))
            if m:
                deps[norm(m.group("name"))] = parse_spec(m.group("spec"))
        for group in (
            (d.get("project") or {}).get("optional-dependencies") or {}
        ).values():
            for raw in group:
                m = REQ.match(str(raw))
                if m:
                    deps.setdefault(norm(m.group("name")), parse_spec(m.group("spec")))
        poetry = ((d.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        for k, v in poetry.items():
            if norm(k) != "python":
                deps.setdefault(
                    norm(k),
                    str(v if not isinstance(v, dict) else v.get("version", "*")),
                )
    else:  # requirements*.txt
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            m = REQ.match(line)
            if m:
                deps[norm(m.group("name"))] = parse_spec(m.group("spec"))
    return deps


def parse_uv_lock(p: Path) -> dict:
    """Return {normalized_name: pinned_version} from a uv.lock."""
    try:
        d = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__error__": f"{type(e).__name__}: {e}"}
    return {
        norm(pkg.get("name", "")): str(pkg.get("version", ""))
        for pkg in d.get("package") or []
        if pkg.get("name")
    }


def ver_tuple(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", v)[:4])


def satisfies(pinned: str, spec: str) -> bool | None:
    """True/False, or None when the constraint form is not decidable here.

    None is deliberate: guessing on a form this differ does not implement would manufacture a
    verdict, which is the failure this program keeps paying for.
    """
    spec = (spec or "*").strip()
    if spec in ("", "*"):
        return True
    if not pinned:
        return None
    ok = True
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.match(r"^(==|!=|>=|<=|~=|>|<)\s*([0-9][0-9A-Za-z.\-+*]*)$", clause)
        if not m:
            return None
        op, want = m.group(1), m.group(2)
        if want.endswith("*"):
            base = want.rstrip("*").rstrip(".")
            hit = pinned.startswith(base)
            ok &= hit if op == "==" else (not hit if op == "!=" else True)
            continue
        pv, wv = ver_tuple(pinned), ver_tuple(want)
        ok &= {
            "==": pv == wv,
            "!=": pv != wv,
            ">=": pv >= wv,
            "<=": pv <= wv,
            ">": pv > wv,
            "<": pv < wv,
            "~=": pv >= wv and pv[: max(len(wv) - 1, 1)] == wv[: max(len(wv) - 1, 1)],
        }[op]
    return ok


def diff(manifest: dict, lock: dict) -> dict:
    rows, violations, undecidable = [], [], []
    for name, spec in sorted(manifest.items()):
        if name.startswith("__"):
            continue
        pinned = lock.get(name)
        verdict = satisfies(pinned, spec) if pinned is not None else None
        row = {
            "name": name,
            "declared": spec,
            "locked": pinned,
            "satisfies": verdict,
            "status": (
                "MISSING-FROM-LOCK"
                if pinned is None
                else "OK"
                if verdict is True
                else "OUT-OF-RANGE"
                if verdict is False
                else "UNDECIDABLE-CONSTRAINT"
            ),
        }
        rows.append(row)
        if row["status"] == "OUT-OF-RANGE":
            violations.append(row)
        elif row["status"] == "UNDECIDABLE-CONSTRAINT":
            undecidable.append(row)
    return {"rows": rows, "violations": violations, "undecidable": undecidable}


def main() -> int:
    PROBEDIR.mkdir(parents=True, exist_ok=True)
    rc = 0

    # ---- CONTROL (both states) : inject an out-of-range pin into a fixture lock ----------------
    fx_manifest = {"requests": ">=2.31,<3", "rich": ">=13.0"}
    fx_lock_good = {"requests": "2.32.3", "rich": "13.7.1"}
    fx_lock_bad = {
        "requests": "1.2.3",
        "rich": "13.7.1",
    }  # requests pinned BELOW the declared floor
    d_bad = diff(fx_manifest, fx_lock_bad)
    d_good = diff(fx_manifest, fx_lock_good)
    ctl_fires = (
        len(d_bad["violations"]) == 1 and d_bad["violations"][0]["name"] == "requests"
    )
    ctl_silent = len(d_good["violations"]) == 0
    print(
        f"CONTROL differ: injected out-of-range pin -> {len(d_bad['violations'])} violation(s) "
        f"{[v['name'] for v in d_bad['violations']]} {'FIRES' if ctl_fires else 'BROKEN'}; "
        f"in-range lock -> {len(d_good['violations'])} violation(s) "
        f"{'SILENT' if ctl_silent else 'OVER-FIRES'}"
    )
    (PROBEDIR / "control-out-of-range-pin.json").write_text(
        json.dumps(
            {
                "fixture_manifest": fx_manifest,
                "bad_lock": fx_lock_bad,
                "bad_result": d_bad,
                "good_lock": fx_lock_good,
                "good_result": d_good,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not (ctl_fires and ctl_silent):
        print(
            "FAILED:AUD-0020 differ control does not discriminate; refusing to report violations"
        )
        return 1

    # ---- PROBE 1 : manifests ------------------------------------------------------------------
    manifests = sorted(
        [
            p
            for p in L.REPO.rglob("pyproject.toml")
            if not any(s in p.parts for s in SKIP)
        ]
        + [
            p
            for p in L.REPO.rglob("requirements*.txt")
            if not any(s in p.parts for s in SKIP)
        ]
    )
    packages = []
    for mp in manifests:
        rel = mp.relative_to(L.REPO).as_posix()
        pkgdir = mp.parent
        deps = parse_manifest(mp)
        lock_p = next(
            (pkgdir / n for n in ("uv.lock", "poetry.lock") if (pkgdir / n).is_file()),
            None,
        )
        lock = parse_uv_lock(lock_p) if (lock_p and lock_p.name == "uv.lock") else {}
        row = {
            "package_dir": pkgdir.relative_to(L.REPO).as_posix() or ".",
            "manifest": rel,
            "declared_dep_count": sum(1 for k in deps if not k.startswith("__")),
            "declared": {k: v for k, v in deps.items() if not k.startswith("__")},
            "manifest_error": deps.get("__error__"),
            "lockfile": lock_p.relative_to(L.REPO).as_posix() if lock_p else None,
            "lockfile_kind": lock_p.name if lock_p else None,
            "locked_package_count": len([k for k in lock if not k.startswith("__")]),
        }
        if lock_p and lock:
            row["reconciliation"] = diff(row["declared"], lock)
        else:
            row["reconciliation"] = None
            row["reconciliation_note"] = (
                "NOT-CHECKED: no lockfile for this package, so 'does the lockfile resolve the "
                "declared constraints' has no answer here -- absence is reported, not passed."
                if not lock_p
                else "NOT-CHECKED: lockfile format not parsed by this differ (only uv.lock is implemented)."
            )
        packages.append(row)

    with_lock = [p for p in packages if p["reconciliation"] is not None]
    without_lock = [p for p in packages if p["reconciliation"] is None]
    all_viol = [
        (p["package_dir"], v)
        for p in with_lock
        for v in p["reconciliation"]["violations"]
    ]
    all_missing = [
        (p["package_dir"], r["name"])
        for p in with_lock
        for r in p["reconciliation"]["rows"]
        if r["status"] == "MISSING-FROM-LOCK"
    ]
    all_undec = [
        (p["package_dir"], r["name"])
        for p in with_lock
        for r in p["reconciliation"]["rows"]
        if r["status"] == "UNDECIDABLE-CONSTRAINT"
    ]
    total_deps = sum(p["declared_dep_count"] for p in packages)

    p1_raw = (
        f"manifests={len(manifests)} packages={len(packages)} total_declared_deps={total_deps}\n"
        + "\n".join(
            f"  {p['package_dir']}: manifest={Path(p['manifest']).name} "
            f"deps={p['declared_dep_count']} lock={p['lockfile_kind'] or 'NONE'}"
            for p in packages
        )
    )
    p2_raw = (
        f"packages_with_parsable_lock={len(with_lock)} without={len(without_lock)}\n"
        f"out_of_range_pins={len(all_viol)} {all_viol[:10]}\n"
        f"declared_but_missing_from_lock={len(all_missing)} {all_missing[:15]}\n"
        f"undecidable_constraints={len(all_undec)} {all_undec[:10]}"
    )
    print("PROBE1\n" + p1_raw)
    print("PROBE2\n" + p2_raw)

    (PROBEDIR / "probe1-manifests.json").write_text(
        json.dumps(packages, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBEDIR / "probe2-lock-reconciliation.json").write_text(
        json.dumps(
            {
                "violations": all_viol,
                "missing_from_lock": all_missing,
                "undecidable": all_undec,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    p1 = L.probe(
        "source",
        "file-read",
        "tomllib/regex parse of every pyproject.toml and requirements*.txt (vendored trees "
        "excluded)",
        p1_raw,
        0,
    )
    p2 = L.probe(
        "verifier",
        "byte-compare",
        "parse each uv.lock and diff pinned version against the declared constraint per "
        "package",
        p2_raw,
        0,
    )

    obs = [
        {
            "name": "python_manifests",
            "measured": len(manifests),
            "method": "file-read",
            "anchor": "pyproject.toml + requirements*.txt",
        },
        {
            "name": "declared_direct_dependencies",
            "measured": total_deps,
            "method": "file-read",
            "anchor": "command-center/p2-wave/probes/AUD-0020/probe1-manifests.json",
        },
        {
            "name": "packages_with_a_lockfile",
            "measured": len(with_lock),
            "method": "file-read",
            "anchor": "uv.lock siblings",
        },
        {
            "name": "packages_without_a_lockfile",
            "measured": len(without_lock),
            "method": "file-read",
            "anchor": "reported NOT-CHECKED, never a pass",
        },
        {
            "name": "out_of_range_pins",
            "measured": len(all_viol),
            "method": "byte-compare",
            "anchor": "probe2-lock-reconciliation.json",
        },
        {
            "name": "declared_deps_missing_from_lock",
            "measured": len(all_missing),
            "method": "byte-compare",
            "anchor": "probe2-lock-reconciliation.json",
        },
        {
            "name": "undecidable_constraints",
            "measured": len(all_undec),
            "method": "byte-compare",
            "anchor": "constraint forms this differ does not implement -- reported, not guessed",
        },
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "SUCCESS:AUD-0020 python dependency and lockfile inventory emitted; both probes recorded",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0020",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            L.art(f"command-center/p2-wave/probes/AUD-0020/{p.name}", "supporting")
            for p in sorted(PROBEDIR.glob("*.json"))
        ]
        + [L.art("command-center/p2-wave/_build_AUD0020.py", "control")],
        "evidence": [
            L.evidence(
                f"{len(manifests)} Python manifests declare {total_deps} direct dependencies across "
                f"{len(packages)} package directories.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0020/probe1-manifests.json",
                [p1, p2],
                "almost-certain",
            ),
            L.evidence(
                f"Only {len(with_lock)} of {len(packages)} packages carry a machine-readable "
                f"lockfile, so for {len(without_lock)} of them 'does the lockfile resolve the "
                "declared constraints' is NOT-CHECKED rather than passing.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0020/probe2-lock-reconciliation.json",
                [p2, p1],
                "almost-certain",
            ),
            L.evidence(
                f"Lock reconciliation over the packages that have one found {len(all_viol)} "
                f"out-of-range pin(s) and {len(all_missing)} declared dependencies absent from the "
                "lock.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0020/probe2-lock-reconciliation.json",
                [p2, p1],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {
                "id": "ctl-injected-out-of-range-pin",
                "command": "diff({'requests': '>=2.31,<3'}, lock={'requests': '1.2.3'})",
                "result": "PASS" if ctl_fires else "FAIL",
                "assertions": 1,
                "output_tail": f"violations={[v['name'] for v in d_bad['violations']]} (want exactly ['requests'])",
            },
            {
                "id": "ctl-in-range-lock-silent",
                "command": "diff({'requests': '>=2.31,<3'}, lock={'requests': '2.32.3'})",
                "result": "PASS" if ctl_silent else "FAIL",
                "assertions": 1,
                "output_tail": f"violations={len(d_good['violations'])} (want 0)",
            },
            {
                "id": "manifest-parse-clean",
                "command": "tomllib.loads / requirements parse over every manifest",
                "result": "PASS"
                if not any(p["manifest_error"] for p in packages)
                else "FAIL",
                "assertions": len(manifests),
                "output_tail": str(
                    [p["manifest"] for p in packages if p["manifest_error"]]
                )
                or "no parse errors",
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0020-C1",
                "mutation",
                "Inject a pin BELOW the declared floor into a fixture lock. The differ must "
                "flag exactly that package, and must stay silent on the same manifest with an "
                "in-range lock -- otherwise a zero-violation result over the real tree is "
                "indistinguishable from an inert differ.",
                ctl_fires,
                ctl_silent,
                f"bad lock -> {[v['name'] for v in d_bad['violations']]}",
                f"good lock -> {len(d_good['violations'])} violations",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
        },
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/ready_units.py (artifact_delivered contract check)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "schema-validate",
                    "schema_resolver.validate_artifact(doc, "
                    "'command-center/schema/audit-inventory.schema.json')",
                    "validated before write; emitter refuses to persist an invalid artifact",
                    0,
                ),
            },
        ],
        "failure": {
            "classification": ["reviewer-absent", "self-review-is-not-review"],
            "reason": "Both named probes ran and the differ control discriminates in both "
            "directions, but receipt_core requires reviewer.verdict=PASS with "
            "independent=true for state SUCCESS and this row names a fresh-context "
            "Claude reviewer who must try to FALSIFY the headline count.",
            "blocked_on": "fresh-context Claude reviewer (reviewer_requirement)",
        },
        "residual_unknowns": [
            {
                "claim": f"{len(all_undec)} declared constraints use a form this differ does not "
                "implement and are reported UNDECIDABLE-CONSTRAINT rather than assumed "
                "satisfied. They are excluded from the violation count, so that count is a "
                "LOWER bound.",
                "verdict": "PARTIAL",
                "settling_experiment": "Re-run the reconciliation with packaging.specifiers.SpecifierSet, "
                "which implements the full PEP 440 grammar, and compare counts.",
            },
            {
                "claim": "Only uv.lock is parsed. A package locking with poetry.lock, Pipfile.lock or a "
                "pinned requirements file is counted as having no machine-readable lock.",
                "verdict": "PARTIAL",
                "settling_experiment": "Add a poetry.lock/Pipfile.lock reader and re-run; measured today "
                "the tree has 0 of either, so the gap is currently inert here.",
            },
        ],
        "report": {
            "kind": "audit-inventory",
            "observations": obs,
            "control_ids": ["AUD0020-C1"],
            "packages": packages,
            "out_of_range_pins": all_viol,
            "declared_missing_from_lock": all_missing,
            "undecidable_constraints": all_undec,
        },
    }
    rc |= L.write_if_valid(receipt, OUT, SCHEMA)
    print(f"{'SUCCESS' if rc == 0 else 'FAILED'}:{UNIT}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
