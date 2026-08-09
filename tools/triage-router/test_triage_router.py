#!/usr/bin/env python3
"""
test_triage_router.py — Tests and demo output for triage_router.

Run:
    python test_triage_router.py

Tests:
  1. Real files from D:/verdict-app-repo/crawler/ (if accessible)
  2. Synthetic simple vs complex Python snippets
  3. Escalation mode
  4. Fail-safe (no lizard + unreadable paths)
  5. Pre-computed score pass-through
  6. CLI integration
  7. Production adoption wiring
"""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path
from dataclasses import asdict

# ---------------------------------------------------------------------------
# Import the router (assume same directory or PYTHONPATH)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
import triage_router as tr

TIERS = tr.DEFAULT_TIERS
HAIKU_MAX = tr.HAIKU_MAX_DEFAULT
SONNET_MAX = tr.SONNET_MAX_DEFAULT

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_CALL = "python tools/triage-router/triage_router.py --files"
MODEL_ROUTE_DOCS = (
    REPO_ROOT / "commands" / "model-route.md",
    REPO_ROOT / "agent-self" / "config" / "commands" / "model-route.md",
)
START_TASK_DOCS = (
    REPO_ROOT / "commands" / "start-task.md",
    REPO_ROOT / "agent-self" / "config" / "commands" / "start-task.md",
)


def _print_verdict(label: str, verdict: tr.Verdict) -> None:
    d = asdict(verdict)
    print(f"\n  [{label}]")
    for k, v in d.items():
        if v is not None:
            print(f"    {k}: {v}")


# ---------------------------------------------------------------------------
# Helpers to create temp Python files
# ---------------------------------------------------------------------------

SIMPLE_PY = textwrap.dedent("""\
    def greet(name: str) -> str:
        return f"Hello, {name}"

    def add(a: int, b: int) -> int:
        return a + b
""")

MODERATE_PY = textwrap.dedent("""\
    def classify(x):
        if x < 0:
            return "negative"
        elif x == 0:
            return "zero"
        elif x < 10:
            return "small"
        elif x < 100:
            return "medium"
        elif x < 1000:
            return "large"
        else:
            return "huge"

    def process(items):
        result = []
        for item in items:
            if isinstance(item, int):
                if item > 0:
                    result.append(item * 2)
                else:
                    result.append(0)
            elif isinstance(item, str):
                result.append(item.upper())
            else:
                result.append(None)
        return result
""")

COMPLEX_PY = textwrap.dedent("""\
    def run_once(data, config, opts, ctx):
        results = []
        for item in data:
            if not item:
                continue
            if opts.get("filter") and not _check(item, opts["filter"]):
                continue
            try:
                processed = _process(item, config)
                if processed is None:
                    if opts.get("strict"):
                        raise ValueError(f"None result for {item}")
                    continue
                for sub in processed:
                    if sub.get("type") == "A":
                        if sub["value"] > 0:
                            results.append({"id": sub["id"], "v": sub["value"] * 2})
                        elif sub["value"] < 0:
                            results.append({"id": sub["id"], "v": 0})
                        else:
                            if opts.get("keep_zero"):
                                results.append({"id": sub["id"], "v": 0})
                    elif sub.get("type") == "B":
                        for child in sub.get("children", []):
                            if child["active"]:
                                try:
                                    r = _transform(child, ctx)
                                    results.append(r)
                                except Exception as e:
                                    if opts.get("raise_on_error"):
                                        raise
                    elif sub.get("type") == "C":
                        while sub.get("pending"):
                            sub = _advance(sub)
                            if sub.get("done"):
                                break
                            if sub.get("error"):
                                if opts.get("abort_on_error"):
                                    return results
                        results.append(sub)
            except ValueError:
                if opts.get("log_errors"):
                    ctx.log(item)
                continue
        return results

    def _check(item, f):
        return bool(item) and f(item)

    def _process(item, config):
        return [{"type": "A", "id": item, "value": 1}]

    def _transform(child, ctx):
        return child

    def _advance(sub):
        sub["done"] = True
        return sub
""")

VERY_COMPLEX_PY = COMPLEX_PY + textwrap.dedent("""\

    def another_monster(records, rules, cache, db, log):
        for rec in records:
            if rec.get("skip"):
                continue
            matched = False
            for rule in rules:
                if rule.get("disabled"):
                    continue
                cond = rule.get("condition")
                if cond == "all":
                    if all(rec.get(k) == v for k, v in rule.get("match", {}).items()):
                        matched = True
                        break
                elif cond == "any":
                    if any(rec.get(k) == v for k, v in rule.get("match", {}).items()):
                        matched = True
                        break
                elif cond == "none":
                    if not any(rec.get(k) == v for k, v in rule.get("match", {}).items()):
                        matched = True
                        break
            if matched:
                key = rec.get("id")
                if key in cache:
                    cached = cache[key]
                    if cached.get("version") == rec.get("version"):
                        log.debug(f"cache hit {key}")
                        continue
                try:
                    result = db.upsert(rec)
                    if result and result.get("ok"):
                        cache[key] = result
                    elif result and result.get("conflict"):
                        log.warning(f"conflict {key}")
                    else:
                        log.error(f"upsert failed {key}")
                except Exception as exc:
                    log.exception(exc)
                    if rec.get("critical"):
                        raise
""")


# ---------------------------------------------------------------------------
# Test 1: Real files from crawler
# ---------------------------------------------------------------------------


def test_real_files() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 1: Real files from D:/verdict-app-repo/crawler/")
    print("=" * 60)

    files = {
        "crawl_verdict_content.py (complex, expected Opus)": "D:/verdict-app-repo/crawler/crawl_verdict_content.py",
        "taxonomy.py (moderate, expected Sonnet)": "D:/verdict-app-repo/crawler/taxonomy.py",
        "audit_videos.py (moderate-high, expected Sonnet or Opus)": "D:/verdict-app-repo/crawler/audit_videos.py",
    }

    passes = []
    for label, path in files.items():
        if not Path(path).exists():
            print(f"\n  SKIP (not found): {path}")
            continue
        verdict = tr.route([path], TIERS, HAIKU_MAX, SONNET_MAX)
        _print_verdict(label, verdict)
        ok = verdict.recommended_tier in ("sonnet", "opus")
        passes.append(ok)
        print(f"  => {PASS if ok else FAIL} (tier={verdict.recommended_tier})")
    return passes


# ---------------------------------------------------------------------------
# Test 2: Synthetic simple vs complex
# ---------------------------------------------------------------------------


def test_synthetic() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 2: Synthetic files (simple / moderate / complex)")
    print("=" * 60)

    cases = [
        ("simple.py", SIMPLE_PY, "haiku", "simple → Haiku"),
        ("moderate.py", MODERATE_PY, "sonnet", "moderate → Sonnet"),
        # complex.py has avg_ccn≈5.8 + max_ccn penalty → score ~9, lands in sonnet.
        # The escalation gate catches any true under-routing at review time.
        ("complex.py", COMPLEX_PY, "sonnet", "complex (avg_ccn-dominated) → Sonnet"),
        ("very_complex.py", VERY_COMPLEX_PY, "opus", "very complex → Opus"),
    ]

    passes = []
    with tempfile.TemporaryDirectory() as td:
        for fname, content, expected_tier, label in cases:
            fpath = Path(td) / fname
            fpath.write_text(content, encoding="utf-8")
            verdict = tr.route([str(fpath)], TIERS, HAIKU_MAX, SONNET_MAX)
            _print_verdict(label, verdict)
            ok = verdict.recommended_tier == expected_tier
            passes.append(ok)
            print(
                f"  => {PASS if ok else FAIL} (expected={expected_tier}, got={verdict.recommended_tier})"
            )
    return passes


# ---------------------------------------------------------------------------
# Test 3: Escalation mode
# ---------------------------------------------------------------------------


def test_escalation() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 3: Escalation (--escalate)")
    print("=" * 60)

    cases = [
        # Natural tier = haiku (score < 5), escalate from haiku → should become sonnet
        (3.0, "haiku", "sonnet"),
        # Natural tier = sonnet, escalate from sonnet → opus
        (7.0, "sonnet", "opus"),
        # Natural tier = opus, escalate from opus → stays opus (ceiling)
        (15.0, "opus", "opus"),
        # Natural tier = haiku, escalate from sonnet (gate fired at sonnet despite haiku being natural)
        (3.0, "sonnet", "opus"),
    ]

    passes = []
    with tempfile.TemporaryDirectory() as td:
        fpath = Path(td) / "dummy.py"
        fpath.write_text("def f(): return 1\n", encoding="utf-8")
        for score, escalate_from, expected_tier in cases:
            verdict = tr.route(
                [str(fpath)],
                TIERS,
                HAIKU_MAX,
                SONNET_MAX,
                health_score=score,
                escalate_from=escalate_from,
            )
            ok = verdict.recommended_tier == expected_tier
            passes.append(ok)
            label = f"score={score} escalate_from={escalate_from}"
            _print_verdict(label, verdict)
            print(
                f"  => {PASS if ok else FAIL} (expected={expected_tier}, got={verdict.recommended_tier})"
            )
    return passes


# ---------------------------------------------------------------------------
# Test 4: Fail-safe (unreadable paths + no lizard CSV to parse)
# ---------------------------------------------------------------------------


def test_failsafe() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 4: Fail-safe (non-existent paths)")
    print("=" * 60)

    passes = []
    # Pass a path that does not exist — lizard will error, stdlib read will fail
    verdict = tr.route(
        ["/nonexistent/path/that/does/not/exist.py"],
        TIERS,
        HAIKU_MAX,
        SONNET_MAX,
    )
    _print_verdict("non-existent file", verdict)
    ok = verdict.recommended_tier == "opus"
    passes.append(ok)
    print(
        f"  => {PASS if ok else FAIL} (expected fail-safe→opus, got={verdict.recommended_tier})"
    )
    return passes


# ---------------------------------------------------------------------------
# Test 5: Pre-computed score
# ---------------------------------------------------------------------------


def test_provided_score() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 5: Pre-computed --health-score pass-through")
    print("=" * 60)

    passes = []
    cases = [
        (2.0, "haiku"),
        (7.5, "sonnet"),
        (12.0, "opus"),
    ]
    with tempfile.TemporaryDirectory() as td:
        fpath = Path(td) / "dummy.py"
        fpath.write_text("def f(): return 1\n", encoding="utf-8")
        for score, expected_tier in cases:
            verdict = tr.route(
                [str(fpath)], TIERS, HAIKU_MAX, SONNET_MAX, health_score=score
            )
            ok = verdict.recommended_tier == expected_tier
            passes.append(ok)
            label = f"provided score={score}"
            _print_verdict(label, verdict)
            print(
                f"  => {PASS if ok else FAIL} (expected={expected_tier}, got={verdict.recommended_tier})"
            )
    return passes


# ---------------------------------------------------------------------------
# Test 6: CLI integration smoke test
# ---------------------------------------------------------------------------


def test_cli() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 6: CLI JSON output smoke test")
    print("=" * 60)

    passes = []
    with tempfile.TemporaryDirectory() as td:
        fpath = Path(td) / "simple.py"
        fpath.write_text(SIMPLE_PY, encoding="utf-8")

        # Use main() directly
        import io
        from unittest.mock import patch

        out_buf = io.StringIO()
        with patch("sys.stdout", out_buf):
            rc = tr.main(["--files", str(fpath), "--pretty"])
        output = out_buf.getvalue()
        try:
            data = json.loads(output)
            has_tier = "recommended_tier" in data
            has_model = "model_id" in data
            has_score = "health_score" in data
            ok = has_tier and has_model and has_score and rc == 0
        except json.JSONDecodeError:
            ok = False

        passes.append(ok)
        print(f"\n  CLI output:\n{output}")
        print(
            f"  => {PASS if ok else FAIL} (valid JSON with required fields, exit={rc})"
        )
    return passes


# ---------------------------------------------------------------------------
# Test 7: Production adoption wiring
# ---------------------------------------------------------------------------


def test_adoption_wiring() -> list[bool]:
    print("\n" + "=" * 60)
    print("TEST 7: Production adoption wiring")
    print("=" * 60)

    router = REPO_ROOT / "tools" / "triage-router" / "triage_router.py"
    tools_registry = REPO_ROOT / "tools" / "README.md"
    quality_workflow = REPO_ROOT / ".github" / "workflows" / "quality.yml"
    model_route_bodies = {
        path: path.read_text(encoding="utf-8") for path in MODEL_ROUTE_DOCS
    }
    start_task_bodies = {
        path: path.read_text(encoding="utf-8") for path in START_TASK_DOCS
    }
    tools_registry_body = tools_registry.read_text(encoding="utf-8")
    quality_workflow_body = quality_workflow.read_text(encoding="utf-8")

    # Positive control: prove every inspected surface and anchor is readable before
    # trusting a missing adoption token from any of them.
    router_present = router.is_file() and "def route(" in router.read_text(
        encoding="utf-8"
    )
    known_present_anchors = (
        router_present
        and all("# Model Route Command" in body for body in model_route_bodies.values())
        and all(
            "decompose into work units with DoD items, file scopes, dependencies"
            in body
            for body in start_task_bodies.values()
        )
        # Repointed 2026-08-09: the previous anchor was
        # "[`tools/mcp/agent-lanes-codex`](mcp/README.md)", a tree deleted by the
        # ChatGPT-web/orchestrator retirement. The anchor's only job is to prove
        # tools/README.md was read before a missing adoption token is trusted, so any
        # still-present registry entry serves; workstation-codex-bundle is not part of
        # the retirement.
        and "[`tools/mcp/workstation-codex-bundle`](mcp/README.md)"
        in tools_registry_body
        and "gate-tests-coverage harness (enshrined runtime; measured, not 100%-gated)"
        in quality_workflow_body
    )

    cases = [("known-present detector anchors found", known_present_anchors)]

    model_route_parity = len({path.read_bytes() for path in MODEL_ROUTE_DOCS}) == 1

    # Known-broken before F02: neither /model-route copy invoked the CLI nor
    # consumed its required fields, escalation contract, and Opus fail-safe.
    for path, body in model_route_bodies.items():
        label = path.relative_to(REPO_ROOT).as_posix()
        cases.extend(
            [
                (
                    f"{label} invokes the router CLI with command-copy parity",
                    model_route_parity and ROUTER_CALL in body,
                ),
                (
                    f"{label} consumes verdict and fail-safe",
                    model_route_parity
                    and all(
                        token in body
                        for token in (
                            "`recommended_tier`",
                            "`model_id`",
                            "--escalate <current-tier>",
                            "claude-opus-4-8",
                        )
                    ),
                ),
            ]
        )

    start_task_parity = len({path.read_bytes() for path in START_TASK_DOCS}) == 1

    # Known-broken before F02: neither /start-task copy delegated model choice,
    # consumed the recommended tier, or escalated after a verification failure.
    for path, body in start_task_bodies.items():
        label = path.relative_to(REPO_ROOT).as_posix()
        scope_at = body.find(
            "decompose into work units with DoD items, file scopes, dependencies"
        )
        route_at = body.find("/model-route", max(scope_at, 0))
        dispatch_at = body.find("**Pattern**: Spawn parallel sub-agents")
        route_window = (
            body[route_at:dispatch_at]
            if route_at >= 0 and dispatch_at > route_at
            else ""
        )
        cases.extend(
            [
                (
                    f"{label} routes after file scope with command-copy parity",
                    start_task_parity
                    and scope_at >= 0
                    and scope_at < route_at < dispatch_at,
                ),
                (
                    f"{label} consumes recommended_tier",
                    start_task_parity and "`recommended_tier`" in route_window,
                ),
                (
                    f"{label} wires verification failure to escalation",
                    start_task_parity and "--escalate <current-tier>" in route_window,
                ),
            ]
        )

    cases.extend(
        [
            # Known-broken before F02: the shipped tool was absent from the live registry.
            (
                "tool is listed in the tools registry",
                "[`tools/triage-router`](triage-router/README.md)"
                in tools_registry_body,
            ),
            # Known-broken before F02: quality CI never executed this standalone suite.
            (
                "quality CI executes the standalone suite",
                (
                    "      - name: triage-router standalone regression\n"
                    "        working-directory: tools/triage-router\n"
                    "        run: python test_triage_router.py"
                )
                in quality_workflow_body,
            ),
        ]
    )

    passes = []
    for label, ok in cases:
        passes.append(ok)
        print(f"  => {PASS if ok else FAIL} {label}")
    return passes


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def main() -> None:
    all_passes: list[bool] = []

    all_passes += test_real_files()
    all_passes += test_synthetic()
    all_passes += test_escalation()
    all_passes += test_failsafe()
    all_passes += test_provided_score()
    all_passes += test_cli()
    all_passes += test_adoption_wiring()

    total = len(all_passes)
    passed = sum(all_passes)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
