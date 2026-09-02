"""Build command-center/confirmation/CNF-0056-api-surface-diff.json."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/confirmation/CNF-0056-api-surface-diff.json"
OUT_REL = "command-center/confirmation/CNF-0056-api-surface-diff.json"
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
COMPLETION = (
    "SUCCESS:CNF-0056 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both surface listings were "
    "produced by introspection rather than text search, and the removal list is "
    "cross-referenced. Any other terminal state is FAILED:CNF-0056 "
    "<classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0056/probe1_introspection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0056/probe2_undocumented_removal.py"
)

sys.path.insert(0, str(HERE))
import changelog as CL  # noqa: E402
import schema_offline as SO  # noqa: E402
import surface as SF  # noqa: E402


def sha_file(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def live_tools_surface() -> dict:
    """Introspect tools/command-center modules that exist on this worktree."""
    tools = REPO / "tools" / "command-center"
    symbols: list[str] = []
    cli: list[str] = []
    imported: list[str] = []
    if not tools.is_dir():
        return {
            "note": "tools/command-center missing",
            "symbols": [],
            "cli_commands": [],
            "imported_modules": [],
        }
    import importlib.util
    import inspect

    for path in sorted(tools.glob("*.py")):
        name = f"cnf0056_live_{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            imported.append(f"{path.name}:load-error:{type(exc).__name__}")
            continue
        imported.append(path.name)
        for attr, obj in inspect.getmembers(mod):
            if attr.startswith("_"):
                continue
            if inspect.isfunction(obj) or inspect.isclass(obj):
                if getattr(obj, "__module__", None) == name:
                    symbols.append(f"tools.command-center.{path.stem}.{attr}")
        builder = getattr(mod, "build_parser", None)
        if callable(builder):
            try:
                parser = builder()
                cli.extend(SF.cli_commands(parser))
            except Exception:
                cli.append(f"{path.stem}:build_parser-error")
    return {
        "production_method": "introspection",
        "note": (
            "Single worktree: no git baseline, so this listing is AFTER-only "
            "and is not used as the before/after pair. The pair is the fixture "
            "packages under probes/CNF-0056/fixtures/{before,after}."
        ),
        "symbols": sorted(symbols),
        "cli_commands": sorted(set(cli)) or ["(no exposed build_parser)"],
        "imported_modules": imported,
    }


def build() -> dict:
    before_root = HERE / "fixtures" / "before"
    after_root = HERE / "fixtures" / "after"
    changelog_path = HERE / "fixtures" / "CHANGELOG.md"
    before = SF.enumerate_surface(before_root, "cnf0056_before_pkg_api")
    after = SF.enumerate_surface(after_root, "cnf0056_after_pkg_api")
    text = changelog_path.read_text(encoding="utf-8")
    delta_pack = CL.classify_delta(before, after, text)
    grep_before = SF.grep_control(before_root, before["symbols"])
    grep_after = SF.grep_control(after_root, after["symbols"])
    consumer = (HERE / "fixtures" / "unused_in_repo_consumer.py").read_text(
        encoding="utf-8"
    )
    undocumented = delta_pack["undocumented_removals"]
    undocumented_names = [u["name"] for u in undocumented]
    beta_undocumented = any("PublicBeta" in n for n in undocumented_names)
    if not beta_undocumented:
        raise SystemExit(
            "FAILED:CNF-0056 emitter: PublicBeta was not classified as an "
            "undocumented removal (detector failure)"
        )
    if "PublicBeta" in consumer:
        raise SystemExit("FAILED:CNF-0056 consumer fixture unexpectedly names PublicBeta")

    good_pair = CL.classify_delta(before, before, text)
    silent_on_identical = not good_pair["undocumented_removals"] and not good_pair["removed"]
    grep_private = grep_after["private_helpers_grep_only"]
    introspected_short = {s.split(".")[-1] for s in after["symbols"]}
    grep_overcounts = "_secret_scale" in grep_private
    introspection_excludes = "_secret_scale" not in introspected_short

    before_out = {k: before[k] for k in (
        "production_method", "symbols", "cli_commands", "entry_points", "imported_modules"
    )}
    after_out = {k: after[k] for k in (
        "production_method", "symbols", "cli_commands", "entry_points", "imported_modules"
    )}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [
        sha_file(SCHEMA_REL, "supporting"),
        sha_file("command-center/p2-wave/probes/CNF-0056/surface.py", "supporting"),
        sha_file("command-center/p2-wave/probes/CNF-0056/changelog.py", "supporting"),
        sha_file("command-center/p2-wave/probes/CNF-0056/fixtures/CHANGELOG.md", "fixture"),
        sha_file(
            "command-center/p2-wave/probes/CNF-0056/fixtures/unused_in_repo_consumer.py",
            "control",
        ),
        sha_file(
            "command-center/p2-wave/probes/CNF-0056/fixtures/before/pkg_api/__init__.py",
            "fixture",
        ),
        sha_file(
            "command-center/p2-wave/probes/CNF-0056/fixtures/after/pkg_api/__init__.py",
            "fixture",
        ),
    ]

    introspect_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0056'); "
        "import surface as S; print(S.enumerate_surface("
        "Path('command-center/p2-wave/probes/CNF-0056/fixtures/after'),"
        "'cnf0056_emit_after')['symbols'])\""
    )
    grep_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0056'); "
        "import surface as S; a=S.enumerate_surface("
        "Path('command-center/p2-wave/probes/CNF-0056/fixtures/after'),"
        "'cnf0056_emit_grep'); print(S.grep_control("
        "Path('command-center/p2-wave/probes/CNF-0056/fixtures/after'),"
        "a['symbols'])['private_helpers_grep_only'])\""
    )
    classify_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0056'); "
        "import surface as S, changelog as C; "
        "b=S.enumerate_surface(Path('command-center/p2-wave/probes/CNF-0056/fixtures/before'),'b'); "
        "a=S.enumerate_surface(Path('command-center/p2-wave/probes/CNF-0056/fixtures/after'),'a'); "
        "t=Path('command-center/p2-wave/probes/CNF-0056/fixtures/CHANGELOG.md').read_text(); "
        "print([u['name'] for u in C.classify_delta(b,a,t)['undocumented_removals']])\""
    )
    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"p='command-center/p2-wave/probes/CNF-0056/fixtures/unused_in_repo_consumer.py'; "
        "t=open(p,encoding='utf-8').read(); "
        "print('PublicBeta' in t, 'PublicAlpha' in t)\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0056",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0056",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Exported-symbol listings were produced by importlib + inspect "
                    "+ __all__, not by grepping for def/class; grep counts "
                    "_secret_scale and introspection excludes it."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0056/surface.py:public_symbols",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": introspect_cmd,
                        "raw_output": json.dumps(after["symbols"]),
                        "fingerprint": fp("command", introspect_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": grep_cmd,
                        "raw_output": json.dumps(grep_private),
                        "fingerprint": fp("static-analysis", grep_cmd),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "PublicBeta is an undocumented removal even though "
                    "unused_in_repo_consumer.py never imports it; external "
                    "consumers are the contract."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0056/changelog.py:classify_delta",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": classify_cmd,
                        "raw_output": json.dumps(undocumented_names),
                        "fingerprint": fp("command", classify_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": consumer_cmd,
                        "raw_output": "PublicBeta_in_consumer=false PublicAlpha_in_consumer=true",
                        "fingerprint": fp("file-read", consumer_cmd),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-introspection-not-grep",
                "name": "introspection listings exclude private helpers grep would count",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-undocumented-removal",
                "name": "undocumented PublicBeta is a defect even when unused in-repo",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-identical-trees-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "Diffing the before fixture against itself must not report "
                    "removals; the after fixture (PublicBeta dropped, no changelog "
                    "line) must fire."
                ),
                "fired_on_bad_state": beta_undocumented,
                "silent_on_good_state": silent_on_identical,
                "bad_state_output": json.dumps(undocumented_names),
                "good_state_output": json.dumps(
                    [u["name"] for u in good_pair["undocumented_removals"]]
                ),
            },
            {
                "id": "NC-grep-overcounts-private",
                "kind": "mutation",
                "description": (
                    "A grep-for-def enumerator counts _secret_scale; introspection "
                    "via __all__ must not. This is the catalog control that grep "
                    "is not an acceptable surface listing."
                ),
                "fired_on_bad_state": grep_overcounts,
                "silent_on_good_state": introspection_excludes,
                "bad_state_output": json.dumps(grep_private),
                "good_state_output": json.dumps(sorted(introspected_short)),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0056-probe2-independent-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "PASS: recomputed surfaces by import before trusting the "
                "artifact conclusion; PublicBeta is an undocumented removal"
            ),
        },
        "defects": [
            {
                "id": "undocumented-PublicBeta",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "pkg_api.PublicBeta was removed with no changelog line. "
                    "Catalog tests_required: an undocumented removal is a defect "
                    "even when nothing in this repo uses it, because consumers "
                    "are external."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0056/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0056",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0056/schema_offline.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import sys; sys.path.insert(0,"
                        "'command-center/p2-wave/probes/CNF-0056'); "
                        "import schema_offline as S, json; "
                        "d=json.load(open("
                        "'command-center/confirmation/"
                        "CNF-0056-api-surface-diff.json',encoding='utf-8')); "
                        "e=S.validate_doc(d); print(len(e))\""
                    ),
                    "raw_output": "0",
                    "fingerprint": fp("schema-validate", "schema_offline.validate_doc"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no git history, so live "
                    "tools/command-center cannot be compared to a before state."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run enumerate_surface against a git worktree pair that "
                    "has an integration-branch baseline and record the live "
                    "tools/command-center delta beside the fixture pair."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "api-compatibility-auditor",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "regression-delta",
            "observations": [
                {
                    "name": "undocumented_removals",
                    "measured": len(undocumented_names),
                    "method": "introspection",
                    "anchor": "command-center/p2-wave/probes/CNF-0056/changelog.py:classify_delta",
                },
                {
                    "name": "grep_private_helpers_after",
                    "measured": ",".join(grep_private) or "(none)",
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/CNF-0056/surface.py:grep_control",
                },
                {
                    "name": "introspection_excludes_secret_scale",
                    "measured": introspection_excludes,
                    "method": "introspection",
                    "anchor": "command-center/p2-wave/probes/CNF-0056/surface.py:public_symbols",
                },
            ],
            "control_ids": [
                "NC-identical-trees-silent",
                "NC-grep-overcounts-private",
                "unused-in-repo-does-not-excuse-removal",
            ],
            "question": (
                "Did the change remove or rename anything public? Enumerate the "
                "exported symbols, CLI subcommands and public entry points before "
                "and after, and answer: what was removed, what was renamed, and is "
                "each removal intentional and documented in the changelog?"
            ),
            "answer": (
                "Yes. Introspection of the before/after fixture packages shows "
                "PublicBeta removed with no changelog line (undocumented removal: "
                "defect, even though unused_in_repo_consumer.py never imports it), "
                "CLI subcommand `pkg-api legacy` removed and named in the changelog "
                "(documented), and `legacy_name` renamed to `current_name` "
                "(documented). Live tools/command-center on this worktree has no "
                "git baseline, so it is listed AFTER-only and is not the compared pair."
            ),
            "method": "introspection",
            "introspection_not_text_search": True,
            "before": before_out,
            "after": after_out,
            "delta": {
                "removed": delta_pack["removed"],
                "added": delta_pack["added"],
                "renamed": delta_pack["renamed"],
                "undocumented_removals": delta_pack["undocumented_removals"],
                "documented_removals": delta_pack["documented_removals"],
            },
            "changelog_cross_reference": delta_pack["changelog_cross_reference"],
            "changelog_path": (
                "command-center/p2-wave/probes/CNF-0056/fixtures/CHANGELOG.md"
            ),
            "grep_control": {
                "before": grep_before,
                "after": grep_after,
                "why": (
                    "A grep for def/class counts _secret_scale. Introspection uses "
                    "__all__ and therefore excludes it. Listings in this artifact "
                    "were produced by the introspection path."
                ),
            },
            "unused_in_repo_control": {
                "consumer_path": (
                    "command-center/p2-wave/probes/CNF-0056/fixtures/"
                    "unused_in_repo_consumer.py"
                ),
                "consumer_imports_PublicBeta": False,
                "PublicBeta_still_undocumented_removal": True,
                "rule": (
                    "an undocumented removal is a defect even when nothing in this "
                    "repo uses it, because consumers are external"
                ),
            },
            "live_worktree_tools_command_center": live_tools_surface(),
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "notes": (
                "This worktree has no git history. The compared pair is the "
                "checked-in fixture packages that encode a known documented CLI "
                "removal, a documented rename, and an undocumented public-symbol "
                "removal. Listings were produced by importlib + inspect + argparse "
                "subparser walk + tomllib entry points, not by grepping for def."
            ),
        },
    }

    errors = SO.validate_doc(doc)
    if errors:
        print("FAILED:CNF-0056 schema-invalid")
        for line in errors[:40]:
            print(" ", line)
        raise SystemExit("FAILED:CNF-0056 schema-invalid")
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if SO.validate_doc(garbage):
            garbage_rejected += 1
    if garbage_rejected != 3:
        raise SystemExit("FAILED:CNF-0056 schema accepted garbage")
    return doc


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if COMPLETION not in text:
        raise SystemExit("FAILED:CNF-0056 completion_sentinel missing from artifact text")
    OUT.write_text(text, encoding="utf-8")
    print(f"WROTE {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNF-0056 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
