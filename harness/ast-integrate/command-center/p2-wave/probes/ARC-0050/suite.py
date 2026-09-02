"""A7 security regression suite: live pack, plant, scan, choke, inject, mutations."""
from __future__ import annotations

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import canary as C  # noqa: E402
import choke as K  # noqa: E402
import inject as I  # noqa: E402
import pipeline as P  # noqa: E402
import plugin.payload as lintmod  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0050/probe1_canary_catch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0050/probe2_mutations_fp.py"
)

UNCAUGHT = (
    "Plant a secret that is not an anthropic/AWS/Slack/PEM/JWT shape "
    "(for example an estate-local token 'arc0050-local-' + hex with no sk-ant- "
    "prefix) inside README.md of a pipeline-produced bundle. plugin.payload "
    "SECRET_RULES do not include that prefix, so C14 secret-gate stays silent. "
    "Independently: put 'Ignore previous instructions' in workflow "
    "metadata.annotations; the sanitizer does not walk DOC_KEYS, so injection "
    "in that field is not caught."
)

ACCEPTABLE_FP_RATE = 0.0


@contextmanager
def _empty_secret_patterns() -> Iterator[None]:
    previous = lintmod._SECRET_RES
    lintmod._SECRET_RES = ()
    try:
        yield
    finally:
        lintmod._SECRET_RES = previous


def _secret_gate_on_bundle(path: Path) -> int:
    members = P.read_zip_members(path)
    return len(P.secret_hits_in_members(members))


def run_canary(tmpdir: Path) -> dict[str, Any]:
    token = C.mint()
    tree = tmpdir / "tree-clean"
    tree.mkdir()
    bundle = tmpdir / "clean.zip"
    pack_meta = P.pack_clean(tree, bundle)
    planted = tmpdir / "planted.zip"
    plant = P.plant_canary_in_bundle(
        bundle, planted, P.PLANT_MEMBER, C.token_of(token)
    )
    scan_clean = P.scan_bundle_cli(bundle)
    scan_planted = P.scan_bundle_cli(planted)
    inproc_clean = _secret_gate_on_bundle(bundle)
    inproc_planted = _secret_gate_on_bundle(planted)
    caught = (
        scan_planted["secret_hit_count"] >= 1
        and inproc_planted >= 1
        and scan_planted["exit_code"] != 0
        and scan_planted.get("c14_status") == "VIOLATED"
    )
    silent_clean = (
        scan_clean["secret_hit_count"] == 0
        and inproc_clean == 0
        and scan_clean["ok"] is True
        and scan_clean.get("c14_status") == "SATISFIED"
    )
    with _empty_secret_patterns():
        mutant_hits = _secret_gate_on_bundle(planted)
        mutant_clean = _secret_gate_on_bundle(bundle)
    restored_hits = _secret_gate_on_bundle(planted)
    return {
        "canary": C.public_meta(token),
        "packer": pack_meta.get("packer"),
        "pipeline": pack_meta.get("pipeline"),
        "members": pack_meta.get("members"),
        "member_count": pack_meta.get("member_count"),
        "plant": {
            "member": plant["member"],
            "pipeline_produced": plant["pipeline_produced"],
            "synthetic_file": plant["synthetic_file"],
            "member_count": plant["member_count"],
            "bytes": plant["bytes"],
        },
        "scan_command": P.SCAN_COMMAND_TEMPLATE,
        "scan_clean": {
            "ok": scan_clean["ok"],
            "exit_code": scan_clean["exit_code"],
            "secret_hit_count": scan_clean["secret_hit_count"],
            "stdout_parseable": scan_clean["stdout_parseable"],
            "subchecks_run": scan_clean["subchecks_run"],
        },
        "scan_planted": {
            "ok": scan_planted["ok"],
            "exit_code": scan_planted["exit_code"],
            "secret_hit_count": scan_planted["secret_hit_count"],
            "secret_rules": scan_planted["secret_rules"],
            "stdout_parseable": scan_planted["stdout_parseable"],
            "subchecks_run": scan_planted["subchecks_run"],
        },
        "inproc_clean_hits": inproc_clean,
        "inproc_planted_hits": inproc_planted,
        "catch_rate": 1.0 if caught else 0.0,
        "caught": caught,
        "silent_on_clean": silent_clean,
        "mutation": {
            "id": "mut-secret-gate",
            "guard": "plugin.payload._SECRET_RES / scan_secrets (C14)",
            "guard_removed_hits": mutant_hits,
            "guard_removed_clean_hits": mutant_clean,
            "guard_removed_red": mutant_hits == 0,
            "guard_restored_hits": restored_hits,
            "guard_restored_green": restored_hits >= 1,
        },
        "both_states": {
            "fired_on_bad": caught,
            "silent_on_good": silent_clean,
        },
        "secret_patterns": list(P.secret_patterns_live()),
    }


def run_permissions() -> dict[str, Any]:
    honest = K.permission_boundary_cases("verb")
    removed = K.permission_boundary_cases("allow-all")
    restored = K.permission_boundary_cases("verb")
    return {
        "choke": {"symbol": K.CHOKE_SYMBOL, "path": K.CHOKE_PATH, "single": True},
        "honest": honest,
        "both_states": {
            "fired_on_bad": honest["fired_on_bad"],
            "silent_on_good": honest["silent_on_good"],
        },
        "mutation": {
            "id": "mut-choke-allow-all",
            "guard": "choke.evaluate_capability verb-vs-grant",
            "guard_removed_red": removed["fired_on_bad"] is False,
            "guard_restored_green": restored["fired_on_bad"] is True
            and restored["silent_on_good"] is True,
            "removed_denied_decision": removed["denied"]["decision"],
            "restored_denied_decision": restored["denied"]["decision"],
            "mention_stays_allow": honest["mention"]["decision"] == "ALLOW",
        },
    }


def run_malicious(tmpdir: Path) -> dict[str, Any]:
    clean_root = tmpdir / "plug-clean"
    bad_root = tmpdir / "plug-bad"
    clean_root.mkdir()
    bad_root.mkdir()
    clean_zip = tmpdir / "plug-clean.zip"
    bad_zip = tmpdir / "plug-bad.zip"
    P.pack_with_hook(clean_root, clean_zip, P.CLEAN_HOOK)
    P.pack_with_hook(bad_root, bad_zip, P.MALICIOUS_HOOK)
    grants = ["fs:read"]
    clean_m = P.read_zip_members(clean_zip)
    bad_m = P.read_zip_members(bad_zip)
    honest_clean = K.inspect_plugin_bundle(clean_m, grants, mode="verb")
    honest_bad = K.inspect_plugin_bundle(bad_m, grants, mode="verb")
    removed_bad = K.inspect_plugin_bundle(bad_m, grants, mode="allow-all")
    restored_bad = K.inspect_plugin_bundle(bad_m, grants, mode="verb")
    mention_members = dict(clean_m)
    mention_members["SKILL.md"] = (
        clean_m["SKILL.md"]
        + b"\nA malicious plugin calling process:exec must be rejected.\n"
    )
    mention = K.inspect_plugin_bundle(mention_members, grants, mode="verb")
    return {
        "clean_rejected": honest_clean["rejected"],
        "bad_rejected": honest_bad["rejected"],
        "bad_undeclared": honest_bad["undeclared_invokes"],
        "mention_rejected": mention["rejected"],
        "both_states": {
            "fired_on_bad": honest_bad["rejected"] is True,
            "silent_on_good": honest_clean["rejected"] is False
            and mention["rejected"] is False,
        },
        "mutation": {
            "id": "mut-plugin-allow-all",
            "guard": "choke.inspect_plugin_bundle verb invoke vs grants",
            "guard_removed_red": removed_bad["rejected"] is False,
            "guard_restored_green": restored_bad["rejected"] is True,
            "removed_undeclared": removed_bad["undeclared_invokes"],
            "restored_undeclared": restored_bad["undeclared_invokes"],
        },
        "member_count_bad": len(bad_m),
    }


def run_injection() -> dict[str, Any]:
    honest = I.run_corpus(enabled=True)
    removed = I.run_corpus(enabled=False)
    restored = I.run_corpus(enabled=True)
    expected = [
        r
        for r in honest["rows"]
        if r["expect_catch"] and r["class"] != "uncaught-hole"
    ]
    clean = [
        r
        for r in honest["rows"]
        if (not r["expect_catch"]) and r["class"] != "uncaught-hole"
    ]
    hole = [r for r in honest["rows"] if r["class"] == "uncaught-hole"]
    return {
        "n": honest["n"],
        "true_positive": honest["true_positive"],
        "false_positive": honest["false_positive"],
        "false_negative": honest["false_negative"],
        "catch_rate_on_expected": honest["catch_rate_on_expected"],
        "per_class": honest["per_class"],
        "surfaces": {
            "workflow": sum(1 for r in honest["rows"] if r["surface"] == "workflow"),
            "council": sum(1 for r in honest["rows"] if r["surface"] == "council"),
        },
        "both_states": {
            "fired_on_bad": all(r["caught"] for r in expected),
            "silent_on_good": all(not r["caught"] for r in clean),
        },
        "documented_hole": hole[0] if hole else None,
        "mutation": {
            "id": "mut-inject-disabled",
            "guard": "inject.sanitize_artifact instruction-field walk",
            "guard_removed_red": removed["true_positive"] == 0,
            "guard_restored_green": restored["true_positive"] == len(expected)
            and restored["false_positive"] == 0,
            "removed_true_positive": removed["true_positive"],
            "restored_true_positive": restored["true_positive"],
        },
        "row_ids": [r["id"] for r in honest["rows"]],
    }


def run_false_positives(
    canary_live: dict[str, Any], injection: dict[str, Any]
) -> dict[str, Any]:
    clean_secret_fp = 0 if canary_live["silent_on_clean"] else 1
    inject_fp = int(injection["false_positive"])
    n_clean_secret_bundles = 1
    n_clean_inject = sum(
        1
        for rid in injection["row_ids"]
        if rid.startswith("inj-benign") or rid.endswith("description")
    )
    n_clean = n_clean_secret_bundles + n_clean_inject
    fp = clean_secret_fp + inject_fp
    rate = (fp / n_clean) if n_clean else 1.0
    return {
        "acceptable_rate": ACCEPTABLE_FP_RATE,
        "measured_rate": rate,
        "false_positives": fp,
        "n_clean": n_clean,
        "composition": {
            "clean_pipeline_bundles": n_clean_secret_bundles,
            "benign_injection_artifacts": n_clean_inject,
        },
        "within_budget": rate <= ACCEPTABLE_FP_RATE,
    }


def run_uncaught_control(tmpdir: Path) -> dict[str, Any]:
    """Prove the named hole: unprefixed estate-local token is not secret-gate shaped."""
    tree = tmpdir / "tree-hole"
    tree.mkdir()
    bundle = tmpdir / "hole-clean.zip"
    P.pack_clean(tree, bundle)
    planted = tmpdir / "hole-planted.zip"
    local = "arc0050-local-" + ("cafebabe" * 4)
    plant = P.plant_canary_in_bundle(bundle, planted, P.PLANT_MEMBER, local)
    hits = _secret_gate_on_bundle(planted)
    return {
        "prefix": "arc0050-local-",
        "member": plant["member"],
        "secret_hit_count": hits,
        "gate_silent": hits == 0,
        "proves_named_hole": hits == 0,
    }


def corpus_composition(
    canary_live: dict[str, Any],
    injection: dict[str, Any],
    malicious: dict[str, Any],
) -> dict[str, Any]:
    classes = {
        "clean-pipeline-bundle": 1,
        "planted-canary-bundle": 1,
        "malicious-plugin-bundle": 1,
        "clean-plugin-bundle": 1,
        "prompt-injection-workflow": injection["surfaces"]["workflow"],
        "prompt-injection-council": injection["surfaces"]["council"],
        "documented-uncaught-local-token": 1,
    }
    return {
        "size": sum(classes.values()),
        "per_class": classes,
        "pipeline_members": canary_live.get("members") or [],
        "malicious_undeclared": malicious.get("bad_undeclared") or [],
    }


def run_suite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="arc0050-") as raw:
        tmp = Path(raw)
        canary_live = run_canary(tmp)
        permissions = run_permissions()
        malicious = run_malicious(tmp)
        injection = run_injection()
        fp = run_false_positives(canary_live, injection)
        hole = run_uncaught_control(tmp)

    mutations = [
        {
            "id": canary_live["mutation"]["id"],
            "test_id": "secret-leak-canary",
            "guard": canary_live["mutation"]["guard"],
            "guard_removed_red": canary_live["mutation"]["guard_removed_red"],
            "guard_restored_green": canary_live["mutation"]["guard_restored_green"],
        },
        {
            "id": permissions["mutation"]["id"],
            "test_id": "permission-boundary",
            "guard": permissions["mutation"]["guard"],
            "guard_removed_red": permissions["mutation"]["guard_removed_red"],
            "guard_restored_green": permissions["mutation"]["guard_restored_green"],
        },
        {
            "id": malicious["mutation"]["id"],
            "test_id": "malicious-plugin",
            "guard": malicious["mutation"]["guard"],
            "guard_removed_red": malicious["mutation"]["guard_removed_red"],
            "guard_restored_green": malicious["mutation"]["guard_restored_green"],
        },
        {
            "id": injection["mutation"]["id"],
            "test_id": "prompt-injection",
            "guard": injection["mutation"]["guard"],
            "guard_removed_red": injection["mutation"]["guard_removed_red"],
            "guard_restored_green": injection["mutation"]["guard_restored_green"],
        },
    ]
    tests_ok = (
        canary_live["caught"]
        and canary_live["silent_on_clean"]
        and canary_live["catch_rate"] == 1.0
        and permissions["both_states"]["fired_on_bad"]
        and permissions["both_states"]["silent_on_good"]
        and malicious["both_states"]["fired_on_bad"]
        and malicious["both_states"]["silent_on_good"]
        and injection["both_states"]["fired_on_bad"]
        and injection["both_states"]["silent_on_good"]
        and all(m["guard_removed_red"] and m["guard_restored_green"] for m in mutations)
        and fp["within_budget"]
        and hole["proves_named_hole"]
    )
    return {
        "ok": tests_ok,
        "canary": canary_live,
        "permissions": permissions,
        "malicious": malicious,
        "injection": injection,
        "false_positive_budget": fp,
        "uncaught_control": hole,
        "mutations": mutations,
        "corpus": corpus_composition(canary_live, injection, malicious),
        "reviewer_uncaught": UNCAUGHT,
        "named_probes": {"probe1": P1, "probe2": P2},
        "design_json_present": (REPO / "command-center/phase3/A7/DESIGN.json").is_file(),
    }


def catalog_validator():
    """Compile the catalog test-plan schema. jsonschema 4.10 has no registry= kw."""
    declared = "command-center/schema/test-plan.schema.json"
    try:
        lib = str(REPO / "platform" / "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)
        from schema_resolver import validator_for  # noqa: WPS433

        return validator_for(declared)
    except Exception:
        return _validator_refresolver(declared)


def _validator_refresolver(declared: str):
    import jsonschema

    shim_path = REPO / declared
    profiles_path = REPO / "platform/schema/artifact-class-profiles.schema.json"
    receipt_path = REPO / "platform/schema/receipt.schema.json"
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    store = {
        "https://ast-integrate.invalid/command-center/schema/test-plan.schema.json": shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    for doc in (shim, profiles, receipt):
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    cls = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    return cls(shim, resolver=resolver)


def assert_green(live: dict[str, Any]) -> None:
    if not live.get("ok"):
        raise AssertionError(
            "ARC-0050 suite is not green:\n"
            + json.dumps(live, indent=2, default=str)[:4000]
        )
