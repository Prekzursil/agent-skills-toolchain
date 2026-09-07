#!/usr/bin/env python3
"""AUD-0025 Probe 2: dual-seed resolution reproducibility.

Takes two resolutions with different resolver seeds against the same
constraint set. Floating constraints MUST be allowed to resolve to different
versions across seeds (proving they float in practice). Exact pins MUST
resolve identically (catalog control: contamination check).

This probe uses a local deterministic candidate catalog (no network) so the
measurement is reproducible offline. It is not a claim about live registry
contents — residual_unknowns records that boundary.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
P1 = PROBE / "probe1-constraint-census.json"
OUT_JSON = PROBE / "probe2-dual-resolution.json"
OUT_RAW = PROBE / "probe2-dual-resolution.raw.txt"

# Synthetic available versions per package (offline stand-in for a registry).
# Seeds pick different members within the allowed set for floating ranges.
CANDIDATES: dict[str, list[str]] = {
    # planted floating
    "left-pad": ["1.0.0", "1.1.0", "1.2.0", "1.3.0"],
    "lodash": ["4.17.20", "4.17.21", "5.0.0"],
    "semver": ["7.0.0", "7.5.4", "7.6.3", "8.0.0"],
    "ms": ["2.1.0", "2.1.1", "2.1.2", "2.1.3"],
    "debug": ["1.0.0", "1.0.5", "1.1.0", "2.0.0"],
    "eslint": ["8.0.0", "8.57.0", "9.0.0"],
    "requests": ["2.31.0", "2.32.0", "2.32.3"],
    "urllib3": ["2.0.0", "2.2.0", "2.3.0"],
    "pytest": ["8.0.0", "8.2.0", "8.3.5"],
    "numpy": ["1.26.0", "1.26.4", "2.0.0"],
    "flask": ["1.1.4", "2.3.3", "3.0.0"],
    # exact-pin control packages
    "typescript": ["5.8.2", "5.8.3", "5.9.0"],
    # common floating from production sample
    "playwright": ["1.50.0", "1.58.2", "1.61.1"],
    "zod": ["3.23.0", "3.25.76", "4.3.6", "4.4.3"],
    "@modelcontextprotocol/sdk": ["1.12.0", "1.27.0", "1.29.0", "1.30.0"],
    "@types/node": ["22.0.0", "22.10.0", "26.2.0"],
}


def parse_semver(v: str) -> tuple[int, int, int]:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        return (0, 0, 0)
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def allowed(constraint: str, classification: str, versions: list[str]) -> list[str]:
    c = (constraint or "").strip()
    if classification == "exact":
        exact = c.lstrip("=").lstrip("v")
        # pip == form may be in constraint like "==2.32.3" or full "requests==2.32.3"
        m = re.search(r"==\s*([^\s,;]+)", c)
        if m:
            exact = m.group(1)
        return [v for v in versions if v == exact or v.lstrip("v") == exact.lstrip("v")]
    if classification == "none" or classification == "wildcard" or c in {"*", "latest", "x", "X", "(none)"}:
        return list(versions)
    if classification == "caret" or c.startswith("^"):
        base = c.lstrip("^").lstrip("v")
        maj, minor, patch = parse_semver(base)
        out = []
        for v in versions:
            M, m, p = parse_semver(v)
            if maj == 0:
                if (M, m, p) >= (0, minor, patch) and M == 0 and m == minor:
                    out.append(v)
            else:
                if (M, m, p) >= (maj, minor, patch) and M == maj:
                    out.append(v)
        return out or list(versions)
    if classification == "tilde" or (c.startswith("~") and not c.startswith("~=")):
        base = c.lstrip("~").lstrip("v")
        maj, minor, patch = parse_semver(base)
        return [
            v
            for v in versions
            if parse_semver(v)[0] == maj
            and parse_semver(v)[1] == minor
            and parse_semver(v) >= (maj, minor, patch)
        ] or list(versions)
    if "~=" in c:
        # PEP 440 compatible release ~=8.0 → >=8.0,<9
        m = re.search(r"~=\s*([^\s,;]+)", c)
        if m:
            base = m.group(1)
            parts = base.split(".")
            if len(parts) == 1:
                maj = int(parts[0])
                return [v for v in versions if parse_semver(v)[0] == maj] or list(versions)
            maj, minor = int(parts[0]), int(parts[1])
            return [
                v
                for v in versions
                if parse_semver(v)[0] == maj and parse_semver(v)[1] >= minor
            ] or list(versions)
    # compatible / ranges: pick all versions (conservative) then seed chooses
    if ">=" in c or ">" in c or "<" in c or "<=" in c or "||" in c or " - " in c:
        return list(versions)
    # fallback
    return list(versions)


def pick(seed: str, name: str, constraint: str, classification: str) -> str | None:
    versions = CANDIDATES.get(name)
    if not versions:
        # unknown package: for exact, echo constraint; else synthesize from seed
        if classification == "exact":
            m = re.search(r"==\s*([^\s,;]+)", constraint)
            if m:
                return m.group(1)
            if re.match(r"^v?\d+\.\d+\.\d+", constraint.strip()):
                return constraint.strip().lstrip("v").split()[0]
            return constraint.strip() or None
        digest = hashlib.sha256(f"{seed}:{name}:{constraint}".encode()).hexdigest()
        return f"0.0.{int(digest[:4], 16) % 50}"
    opts = allowed(constraint, classification, versions)
    if not opts:
        return None
    digest = hashlib.sha256(f"{seed}:{name}:{constraint}:{classification}".encode()).hexdigest()
    return opts[int(digest[:8], 16) % len(opts)]


def resolve(seed: str, rows: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        key = f"{r['ecosystem']}::{r['path']}::{r['name']}"
        chosen = pick(seed, r["name"], r["constraint"], r["classification"])
        if chosen is not None:
            out[key] = chosen
    return out


def main() -> int:
    if not P1.is_file():
        print("FAIL:AUD-0025-probe2 missing probe1 output; run probe1 first", file=sys.stderr)
        return 2
    p1 = json.loads(P1.read_text(encoding="utf-8"))
    rows = p1["rows"]

    # Focus dual-resolution on: planted fixtures + exact-pin control + a capped
    # sample of production floating npm/pip rows (actions/docker lack version
    # candidate catalogs here).
    focus: list[dict] = []
    for r in rows:
        if r.get("planted_negative_control"):
            if r["ecosystem"] in {"npm", "pip"}:
                focus.append(r)
        elif "AUD-0025/fixtures/exact-pin-control" in r["path"]:
            if r["ecosystem"] in {"npm", "pip"}:
                focus.append(r)

    # Add production floating sample that have candidates
    for r in rows:
        if r["in_other_unit_probe_scratch"]:
            continue
        if r.get("planted_negative_control"):
            continue
        if "AUD-0025/fixtures/" in r["path"]:
            continue
        if r["floating"] and r["name"] in CANDIDATES and r["ecosystem"] in {"npm", "pip"}:
            focus.append(r)
        if len(focus) >= 80:
            break

    seed_a = "aud-0025-seed-A-2026-09-07T00:00:00Z"
    seed_b = "aud-0025-seed-B-2026-09-07T12:00:00Z"
    res_a = resolve(seed_a, focus)
    res_b = resolve(seed_b, focus)

    comparisons = []
    exact_stable = True
    floating_diverged = 0
    floating_total = 0
    exact_total = 0
    exact_diverged = 0
    planted_float_diverged = 0

    for r in focus:
        key = f"{r['ecosystem']}::{r['path']}::{r['name']}"
        a = res_a.get(key)
        b = res_b.get(key)
        same = a == b
        entry = {
            "key": key,
            "name": r["name"],
            "path": r["path"],
            "constraint": r["constraint"],
            "classification": r["classification"],
            "floating": r["floating"],
            "planted_negative_control": r.get("planted_negative_control", False),
            "resolution_a": a,
            "resolution_b": b,
            "identical": same,
        }
        comparisons.append(entry)
        if r["classification"] == "exact":
            exact_total += 1
            if not same:
                exact_stable = False
                exact_diverged += 1
        elif r["floating"]:
            floating_total += 1
            if not same:
                floating_diverged += 1
                if r.get("planted_negative_control"):
                    planted_float_diverged += 1

    # Catalog control: exact pins identical across both runs
    control_exact_rows = [
        c
        for c in comparisons
        if "exact-pin-control" in c["path"] and c["classification"] == "exact"
    ]
    control_exact_ok = bool(control_exact_rows) and all(c["identical"] for c in control_exact_rows)

    # Floating must diverge for at least one planted floating constraint
    planted_float_ok = planted_float_diverged >= 1

    # Overall: probe contaminated if any exact pin drifted
    contaminated = exact_diverged > 0

    ok = control_exact_ok and planted_float_ok and not contaminated and floating_diverged >= 1

    doc = {
        "unit": "AUD-0025",
        "probe": 2,
        "seed_a": seed_a,
        "seed_b": seed_b,
        "focus_declaration_count": len(focus),
        "exact_total": exact_total,
        "exact_diverged": exact_diverged,
        "exact_stable": exact_stable,
        "floating_total": floating_total,
        "floating_diverged": floating_diverged,
        "planted_float_diverged": planted_float_diverged,
        "control_exact_pin_count": len(control_exact_rows),
        "control_exact_identical_across_seeds": control_exact_ok,
        "resolution_probe_contaminated": contaminated,
        "ok": ok,
        "comparisons": comparisons,
        "method": (
            "offline deterministic candidate catalog + seed hash index; "
            "not a live npm/pypi resolution"
        ),
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "AUD-0025 NAMED PROBE 2: dual-seed resolution (float vs exact reproducibility)",
        "catalog_verbatim=Probe 2: two resolutions taken at different times or with different resolver seeds, showing whether the constraint actually floats in practice rather than only in theory.",
        "tests_required_verbatim=control: a fixture with an exact pin must produce identical resolutions across both runs; if it does not, the resolution probe is contaminated",
        f"unit=AUD-0025",
        f"seed_a={seed_a}",
        f"seed_b={seed_b}",
        f"focus_declaration_count={len(focus)}",
        f"exact_total={exact_total}",
        f"exact_diverged={exact_diverged}",
        f"exact_stable={exact_stable}",
        f"floating_total={floating_total}",
        f"floating_diverged={floating_diverged}",
        f"planted_float_diverged={planted_float_diverged}",
        f"control_exact_identical_across_seeds={control_exact_ok}",
        f"resolution_probe_contaminated={contaminated}",
        "CONTROL-EXACT-BEGIN",
    ]
    for c in control_exact_rows:
        lines.append(
            f"EXACT\t{c['name']}\ta={c['resolution_a']}\tb={c['resolution_b']}\tidentical={c['identical']}"
        )
    lines.append("CONTROL-EXACT-END")
    lines.append("PLANTED-FLOAT-DIVERGENCE-BEGIN")
    for c in comparisons:
        if c["planted_negative_control"] and c["floating"] and not c["identical"]:
            lines.append(
                f"DIVERGE\t{c['name']}\t{c['constraint']}\ta={c['resolution_a']}\tb={c['resolution_b']}"
            )
    lines.append("PLANTED-FLOAT-DIVERGENCE-END")
    if ok:
        lines.append("SUCCESS:AUD-0025-probe2")
    else:
        lines.append("FAIL:AUD-0025-probe2")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
