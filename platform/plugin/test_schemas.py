"""Schema tests: every schema is valid, describes a REAL emitted artifact, and rejects a mutant.

Three layers, because any one alone is theatre:

1. each schema compiles against JSON Schema 2020-12(a malformed schema would otherwise validate
   nothing while appearing to pass);
2. the artifact the code ACTUALLY emits validates — no hand-written fixtures, so a schema cannot
   drift away from its producer;
3. a targeted mutant of that same artifact FAILS. A schema that accepts everything is
   indistinguishable from no schema at all, so the negative control is what makes layer 2 mean
   something.

Plus a disk-sync check, so a hand-edit of a generated schema file is a test failure.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from plugin import deploy as deploy_mod
from plugin import errors, health, journal, logs, migrate, payload, policy, schemas
from plugin.build import ALLOW_RULES, MAX_BYTES, MAX_FILES, build, manifest_for
from plugin.conformance import validate_package
from plugin.journal import Prefix, Transaction
from plugin.lifecycle import install
from plugin.manifest import MANIFEST_RELPATH, load as load_manifest

VALIDATOR = jsonschema.Draft202012Validator


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Produce one REAL instance of every artifact this package emits."""
    root = Path(__file__).resolve().parents[2]
    work = tmp_path_factory.mktemp("artifacts")
    result, pay = build(root, work / "dist")
    prefix = Prefix(work / "prefix")
    live = work / "prefix" / "live"
    res = install(result.archive, prefix, live_root=live)
    vroot = prefix.version_dir(str(res.version))
    manifest = load_manifest(vroot / MANIFEST_RELPATH)
    prov = deploy_mod.Provenance.load(prefix.state / deploy_mod.PROVENANCE_NAME)

    # Manufacture a real DIVERGED row so the drift/decision artifacts are non-empty.
    lf = live / "commands" / "astplugin.md"
    lf.write_text(
        lf.read_text(encoding="utf-8") + "\nlocal\n", encoding="utf-8", newline="\n"
    )
    sf = vroot / "commands" / "astplugin.md"
    sf.write_text(
        sf.read_text(encoding="utf-8") + "\nupstream\n", encoding="utf-8", newline="\n"
    )
    entries = deploy_mod.classify(manifest, vroot, live, prov)

    with Transaction(prefix, "artifact-demo") as txn:
        txn.add("noop", {"note": "for the journal artifact"}, None)

    legacy = work / "legacy"
    legacy.mkdir()
    (legacy / "plugin.json").write_text('{"name":"x"}', encoding="utf-8", newline="\n")
    plan = migrate.plan_migration(legacy, version="1.0.0")
    ledger = migrate.migrate(legacy, version="1.0.0", dry_run=True)

    log = logs.Logger(work / "demo.log")
    record = log.info("install", "activated", version="1.0.0", password="hunter2")

    report = health.health_check(prefix, with_controls=True)

    return {
        "payload-allowlist": payload.allowlist_document(
            ALLOW_RULES, budget_bytes=MAX_BYTES, budget_files=MAX_FILES
        ),
        "payload-inventory": pay.inventory(
            name=manifest.name, version=manifest.version
        ),
        "secret-finding": payload.secret_findings_document(pay),
        "compatibility": migrate.diagnose(manifest, client_version="1.2.3"),
        "projection-map": deploy_mod.projection_map(manifest, vroot, live),
        "txn-journal": journal.journal_document(prefix),
        "deploy-provenance": prov.as_document(),
        "drift-classification": deploy_mod.drift_document(entries),
        "divergence-decision": deploy_mod.divergence_decisions(entries),
        "health-report": report.as_dict(),
        "probe-control": health.probe_control_document(report.controls),
        "conformance-report": validate_package(result.archive).as_dict(),
        "migration-step": plan.as_dict(),
        "migration-ledger": ledger,
        "error-taxonomy": errors.taxonomy_document(),
        "failure-policy": policy.failure_policy_document(),
        "exec-policy": policy.exec_policy_document(),
        "log-record": record.as_dict(),
        "_manifest": manifest.as_dict(),
    }


# --------------------------------------------------------------------------- layer 1


def test_every_declared_target_has_a_schema() -> None:
    assert len(schemas.TARGETS) == 19
    assert ".claude-plugin/plugin.schema.json" in schemas.TARGETS
    assert sum(1 for k in schemas.TARGETS if k.startswith("tools/plugin/schema/")) == 18


@pytest.mark.parametrize("name", sorted(schemas.SCHEMAS))
def test_each_artifact_schema_is_itself_valid(name: str) -> None:
    VALIDATOR.check_schema(schemas.SCHEMAS[name])


def test_manifest_schema_is_itself_valid() -> None:
    VALIDATOR.check_schema(schemas.PLUGIN_MANIFEST_SCHEMA)


# --------------------------------------------------------------------------- layer 2


@pytest.mark.parametrize("name", sorted(schemas.SCHEMAS))
def test_real_emitted_artifact_validates(name: str, artifacts: dict[str, Any]) -> None:
    doc = artifacts[name]
    VALIDATOR(schemas.SCHEMAS[name]).validate(doc)


def test_the_shipped_manifest_validates_against_the_manifest_schema(
    artifacts: dict[str, Any],
) -> None:
    VALIDATOR(schemas.PLUGIN_MANIFEST_SCHEMA).validate(artifacts["_manifest"])


def test_the_repo_root_manifest_also_validates_where_it_overlaps(
    repo_root: Path,
) -> None:
    """The live root manifest must validate green under the IMP-0006 profile.

    Phase-4 fields (compatibility/…) are contracted optional properties; the
    current client surface (name/version/description/author/license/keywords)
    alone must pass without injecting additive blocks.
    """
    doc = json.loads(
        (repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    VALIDATOR(schemas.PLUGIN_MANIFEST_SCHEMA).validate(doc)


# --------------------------------------------------------------------------- layer 3


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    return lambda d: d.pop(key, None)


#: name -> mutation that MUST make the real artifact invalid.
MUTANTS: dict[str, Callable[[dict[str, Any]], None]] = {
    "payload-allowlist": lambda d: d.update(policy="allow-by-default"),
    "payload-inventory": lambda d: d["forbidden_matches"].append(".git/config"),
    "secret-finding": lambda d: d["findings"].append(
        {
            "path": "x",
            "rule": "r",
            "line": 1,
            "severity": "blocking",
            "excerpt_shape": "ghp_realvalue",
        }
    ),
    "compatibility": _drop("os"),
    "projection-map": lambda d: d["entrypoints"][0].pop("launch"),
    "txn-journal": lambda d: d["records"].append({"event": "teleported", "ts": 1.0}),
    "deploy-provenance": lambda d: d["records"].append(
        {
            "live_path": "x",
            "source_path": "y",
            "version": "1",
            "content_sha256": "short",
            "deployed_at": 1.0,
            "mode": "copy",
        }
    ),
    "drift-classification": lambda d: d["counts"].pop("diverged"),
    "divergence-decision": lambda d: d.update(auto_resolved=True),
    "health-report": lambda d: d["probes"].append(
        {"probe": "x", "status": "MAYBE", "detail": "d", "remediation": ""}
    ),
    "probe-control": lambda d: d["rows"].append(
        {"probe": "x", "healthy_status": "PASS", "verdict": "GREEN"}
    ),
    "conformance-report": lambda d: d.update(verdict="nothing blocking"),
    "migration-step": lambda d: d["steps"].append({"id": "x", "description": "y"}),
    "migration-ledger": _drop("ok"),
    "error-taxonomy": lambda d: d["classes"].pop(),
    "failure-policy": lambda d: d.update(default_mode="fail-open"),
    "exec-policy": lambda d: d["rules"][0].update(credential_read_allowed=True),
    "log-record": lambda d: d.update(level="trace"),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_artifact_is_rejected(name: str, artifacts: dict[str, Any]) -> None:
    """Negative control: without this, layer 2 could pass against a schema that accepts anything."""
    doc = json.loads(json.dumps(artifacts[name]))
    VALIDATOR(schemas.SCHEMAS[name]).validate(
        doc
    )  # sanity: the unmutated copy is valid
    MUTANTS[name](doc)
    with pytest.raises(jsonschema.ValidationError):
        VALIDATOR(schemas.SCHEMAS[name]).validate(doc)


def test_every_artifact_schema_has_a_negative_control() -> None:
    assert set(MUTANTS) == set(schemas.SCHEMAS), (
        f"schemas with no negative control: {sorted(set(schemas.SCHEMAS) - set(MUTANTS))}"
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(name="Bad_Name"),
        lambda d: d.update(version="1.0"),
        lambda d: d.update(surprise=True),
        lambda d: d["compatibility"].update(platforms=["solaris"]),
        lambda d: d["entrypoints"][0].pop("interpreter"),
        lambda d: d["entrypoints"][0].update(kind="daemon"),
        lambda d: d["author"].update(nickname="x"),
    ],
)
def test_manifest_schema_rejects_each_mutant(mutate, artifacts: dict[str, Any]) -> None:
    doc = json.loads(json.dumps(artifacts["_manifest"]))
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        VALIDATOR(schemas.PLUGIN_MANIFEST_SCHEMA).validate(doc)


def test_manifest_schema_accepts_the_reserved_extension_namespace(
    artifacts: dict[str, Any],
) -> None:
    doc = json.loads(json.dumps(artifacts["_manifest"]))
    doc["x-anything"] = {"free": "form"}
    VALIDATOR(schemas.PLUGIN_MANIFEST_SCHEMA).validate(doc)


# --------------------------------------------------------------------------- disk sync


def test_on_disk_schemas_match_this_module(repo_root: Path) -> None:
    problems = schemas.check(repo_root)
    assert problems == [], (
        "on-disk schema files drifted from platform/plugin/schemas.py; "
        "regenerate with `python platform/plugin/astplugin.py schemas --write`"
    )


def test_every_declared_path_exists_on_disk(repo_root: Path) -> None:
    missing = [rel for rel in schemas.TARGETS if not (repo_root / rel).exists()]
    assert missing == [], f"declared schema paths absent from disk: {missing}"


def test_disk_check_detects_a_hand_edit(tmp_path: Path) -> None:
    """Both-states control for the sync check: it must FIRE on a deliberately edited copy."""
    schemas.materialise(tmp_path)
    assert schemas.check(tmp_path) == []
    victim = tmp_path / "tools" / "plugin" / "schema" / "error-taxonomy.schema.json"
    victim.write_text(
        victim.read_text(encoding="utf-8").replace('"version"', '"vers1on"'),
        encoding="utf-8",
    )
    problems = schemas.check(tmp_path)
    assert any("error-taxonomy" in p for p in problems), problems


def test_disk_check_detects_a_missing_file(tmp_path: Path) -> None:
    schemas.materialise(tmp_path)
    (tmp_path / "tools" / "plugin" / "schema" / "exec-policy.schema.json").unlink()
    assert any("exec-policy" in p and "missing" in p for p in schemas.check(tmp_path))


def test_catalog_references_to_plugin_schemas_now_resolve(repo_root: Path) -> None:
    """The 19 plugin-lane tokens the work-unit catalog declares must exist on disk.

    Measured before this unit: 18 ``tools/plugin/schema/*`` paths + ``.claude-plugin/
    plugin.schema.json`` were referenced by 20 work units and none existed.
    """
    catalog = json.loads(
        (repo_root / "command-center" / "WORK-UNIT-CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    import re

    token = re.compile(r"[A-Za-z0-9_./\-]*\.schema\.json")
    declared: set[str] = set()
    for unit in catalog["work_units"]:
        for match in token.findall(json.dumps(unit)):
            rel = match.lstrip("/")
            if (
                rel.startswith("tools/plugin/schema/")
                or rel == ".claude-plugin/plugin.schema.json"
            ):
                declared.add(rel)
    assert declared, "the detector found no plugin-lane tokens at all; it is broken"
    unresolved = sorted(r for r in declared if not (repo_root / r).exists())
    assert unresolved == [], f"still unresolved: {unresolved}"


def test_shipped_package_carries_the_schemas(built_package: Path) -> None:
    from plugin.packager import list_members

    shipped = [m for m in list_members(built_package) if m.startswith("schema/")]
    assert len(shipped) == 18, f"expected 18 shipped schemas, got {len(shipped)}"


def test_manifest_for_matches_the_schema_before_any_io() -> None:
    VALIDATOR(schemas.PLUGIN_MANIFEST_SCHEMA).validate(manifest_for().as_dict())
