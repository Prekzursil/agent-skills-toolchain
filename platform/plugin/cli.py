"""The ``astplugin`` CLI: one subcommand per lifecycle verb, one exit code per failure class.

Every mutating verb accepts ``--dry-run``. Every failure is rendered through
``errors.PluginError.render`` so the user always gets cause / impact / the exact next command, and
the process exit code is the taxonomy's code for that class — never a bare 1.

Terminal state discipline: each verb prints exactly one ``SUCCESS:<verb>`` or ``FAILED:<verb>``
line, so a caller (or a harness) can parse the outcome without reading prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import build as build_mod
from . import deploy as deploy_mod
from . import lifecycle, migrate, policy, schemas
from .cache import Cache
from .conformance import validate_package
from .errors import EXIT_OK, EXIT_USAGE, PluginError, taxonomy_document
from .health import doctor, health_check, probe_control_document
from .journal import Prefix, journal_document, read_installed
from .manifest import MANIFEST_RELPATH, load as load_manifest
from .payload import secret_findings_document

PROG = "astplugin"


def _emit(doc: object, out: Path | None) -> None:
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if out is None:
        return
    if str(out) == "-":
        sys.stdout.write(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")


def _prefix(args: argparse.Namespace) -> Prefix:
    if not getattr(args, "prefix", None):
        raise PluginError("E_USAGE", "--prefix is required for this command")
    return Prefix(Path(args.prefix).expanduser().resolve())


def _live(args: argparse.Namespace, prefix: Prefix) -> Path:
    return (
        Path(args.live).expanduser().resolve()
        if getattr(args, "live", None)
        else prefix.root / "live"
    )


def _active_manifest(prefix: Prefix):  # noqa: ANN202 - Manifest, imported lazily for cycle safety
    state = read_installed(prefix)
    if not state:
        raise PluginError("E_TXN", "nothing is installed in this prefix")
    return load_manifest(
        prefix.version_dir(str(state["active_version"])) / MANIFEST_RELPATH
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG, description="ast-integrate platform plugin lifecycle"
    )
    sub = p.add_subparsers(dest="verb", required=True)

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument(
            "--json",
            type=Path,
            default=None,
            help="write the result document here ('-' = stdout)",
        )
        return sp

    sp = add("build", "build the deterministic package")
    sp.add_argument("--repo-root", type=Path, default=Path.cwd())
    sp.add_argument("--out", type=Path, default=Path("dist"))
    sp.add_argument("--version", default=build_mod.PLUGIN_VERSION)
    sp.add_argument("--report-secrets", type=Path, default=None)
    sp.add_argument("--inventory", type=Path, default=None)
    sp.add_argument("--explain-payload", action="store_true")

    sp = add("schemas", "materialise or check the on-disk schema files")
    sp.add_argument("--repo-root", type=Path, default=Path.cwd())
    sp.add_argument("--write", action="store_true")

    for verb, help_ in (
        ("install", "stage, verify, activate, deploy"),
        ("update", "install a newer version, preserving live overrides"),
    ):
        sp = add(verb, help_)
        sp.add_argument("--package", type=Path, required=True)
        sp.add_argument("--prefix", required=True)
        sp.add_argument("--live", default=None)
        sp.add_argument("--client-version", default="1.0.0")
        sp.add_argument("--dry-run", action="store_true")
        if verb == "install":
            sp.add_argument("--no-deploy", action="store_true")

    for verb, help_ in (
        ("repair", "restore files with no live-unique content"),
        ("rollback", "activate the previous version"),
        ("sync", "live deployment synchronisation"),
    ):
        sp = add(verb, help_)
        sp.add_argument("--prefix", required=True)
        sp.add_argument("--live", default=None)
        sp.add_argument("--dry-run", action="store_true")
        if verb == "sync":
            sp.add_argument("--decisions", type=Path, default=None)
            sp.add_argument("--force-source", action="store_true")

    sp = add("uninstall", "remove the plugin")
    sp.add_argument("--prefix", required=True)
    sp.add_argument("--live", default=None)
    sp.add_argument("--dry-run", action="store_true")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--retain-user-data", action="store_true")
    g.add_argument("--purge-user-data", action="store_true")

    sp = add("cache", "cache status, refresh, invalidation, verification")
    sp.add_argument("--prefix", required=True)
    sp.add_argument("--refresh", action="store_true")
    sp.add_argument("--invalidate", action="store_true")
    sp.add_argument("--verify", action="store_true")
    sp.add_argument("--prune", action="store_true")
    sp.add_argument("--bypass", action="store_true")

    sp = add("health-check", "run the probe registry")
    sp.add_argument("--prefix", required=True)
    sp.add_argument(
        "--controls", action="store_true", help="also prove each probe discriminates"
    )
    sp.add_argument("--clear-stale-lock", action="store_true")
    sp.add_argument("--repair-layout", action="store_true")

    sp = add("doctor", "map every failing probe to its remediating command")
    sp.add_argument("--prefix", required=True)

    sp = add("conform", "run the conformance validator over a package")
    sp.add_argument("--package", type=Path, required=True)

    sp = add("migrate", "migrate an old prefix layout")
    sp.add_argument("--prefix", required=True)
    sp.add_argument("--version", default=build_mod.PLUGIN_VERSION)
    sp.add_argument("--dry-run", action="store_true")

    sp = add("diagnose", "client / OS / shell compatibility diagnostics")
    sp.add_argument("--prefix", default=None)
    sp.add_argument("--client-version", default=None)

    sp = add("journal", "dump the transaction journal")
    sp.add_argument("--prefix", required=True)

    sp = add("projection", "print the manifest-to-live-config projection map")
    sp.add_argument("--prefix", required=True)
    sp.add_argument("--live", default=None)

    add("errors", "print the error taxonomy")
    add("policies", "print the exec and failure policies")
    return p


def _run(args: argparse.Namespace) -> tuple[str, int, object]:  # noqa: C901, PLR0911, PLR0912
    verb = args.verb
    if verb == "build":
        out_dir = args.out.resolve()
        result, payload = build_mod.build(
            args.repo_root.resolve(), out_dir, version=args.version
        )
        if args.report_secrets:
            _emit(secret_findings_document(payload), args.report_secrets)
        inv = payload.inventory(name=build_mod.PLUGIN_NAME, version=args.version)
        if args.inventory:
            _emit(inv, args.inventory)
        doc: dict[str, object] = {
            **result.as_dict(),
            "payload_file_count": payload.file_count,
            "payload_total_bytes": payload.total_bytes,
            "secret_findings_blocking": sum(
                1 for f in payload.findings if f.severity == "blocking"
            ),
        }
        if args.explain_payload:
            doc["allowlist"] = [
                {"glob": r.glob, "reason": r.reason} for r in build_mod.ALLOW_RULES
            ]
            doc["entries"] = [e.as_dict() for e in payload.entries]
        return verb, EXIT_OK, doc

    if verb == "schemas":
        root = args.repo_root.resolve()
        if args.write:
            written = schemas.materialise(root)
            return verb, EXIT_OK, {"artifact": "schema-materialise", "written": written}
        problems = schemas.check(root)
        return (
            verb,
            EXIT_OK if not problems else 51,
            {"artifact": "schema-check", "in_sync": not problems, "problems": problems},
        )

    if verb == "install":
        prefix = _prefix(args)
        res = lifecycle.install(
            args.package.resolve(),
            prefix,
            live_root=_live(args, prefix),
            client_version=args.client_version,
            deploy=not args.no_deploy,
            dry_run=args.dry_run,
        )
        return verb, EXIT_OK, res.as_dict()

    if verb == "update":
        prefix = _prefix(args)
        res = lifecycle.update(
            args.package.resolve(),
            prefix,
            live_root=_live(args, prefix),
            client_version=args.client_version,
            dry_run=args.dry_run,
        )
        return verb, EXIT_OK, res.as_dict()

    if verb == "repair":
        prefix = _prefix(args)
        res = lifecycle.repair(
            prefix, live_root=_live(args, prefix), dry_run=args.dry_run
        )
        return verb, EXIT_OK, res.as_dict()

    if verb == "rollback":
        prefix = _prefix(args)
        res = lifecycle.rollback(
            prefix, live_root=_live(args, prefix), dry_run=args.dry_run
        )
        return verb, EXIT_OK, res.as_dict()

    if verb == "uninstall":
        prefix = _prefix(args)
        choice = (
            "retain"
            if args.retain_user_data
            else ("purge" if args.purge_user_data else None)
        )
        res = lifecycle.uninstall(
            prefix,
            live_root=_live(args, prefix),
            user_data=choice,
            dry_run=args.dry_run,
        )
        return verb, EXIT_OK, res.as_dict()

    if verb == "sync":
        prefix = _prefix(args)
        manifest = _active_manifest(prefix)
        state = read_installed(prefix)
        vroot = prefix.version_dir(str(state["active_version"]))
        live = _live(args, prefix)
        res = deploy_mod.sync(
            manifest,
            vroot,
            live,
            prefix,
            dry_run=args.dry_run,
            force_source=args.force_source,
        )
        drift = deploy_mod.drift_document(res.entries)
        if args.decisions:
            _emit(deploy_mod.divergence_decisions(res.entries), args.decisions)
        code = EXIT_OK if not res.needs_decision else 30
        return verb, code, {**res.as_dict(), "drift": drift}

    if verb == "cache":
        prefix = _prefix(args)
        cache = Cache(prefix.cache, bypass=args.bypass)
        actions: dict[str, object] = {}
        if args.verify:
            actions["quarantined"] = cache.verify()
        if args.invalidate:
            actions["invalidated"] = cache.invalidate()
        if args.refresh:
            state = read_installed(prefix)
            sources: dict[str, bytes] = {}
            if state:
                vroot = prefix.version_dir(str(state["active_version"]))
                from .fsops import iter_files, relposix

                sources = {
                    relposix(vroot, f): f.read_bytes() for f in iter_files(vroot)
                }
            actions["refreshed"] = len(cache.refresh(sources))
        if args.prune:
            actions["evicted"] = cache.prune()
        return verb, EXIT_OK, {**cache.stats().as_dict(), "actions": actions}

    if verb == "health-check":
        prefix = _prefix(args)
        if args.clear_stale_lock and prefix.lock.exists():
            prefix.lock.unlink()
        if args.repair_layout:
            prefix.ensure()
        report = health_check(prefix, with_controls=args.controls)
        doc = report.as_dict()
        if args.controls:
            doc["control_summary"] = probe_control_document(report.controls)
        return verb, EXIT_OK if report.ok else 50, doc

    if verb == "doctor":
        prefix = _prefix(args)
        adv = doctor(prefix)
        return verb, EXIT_OK if adv["ok"] else 50, adv

    if verb == "conform":
        report = validate_package(args.package.resolve())
        return verb, EXIT_OK if report.ok else 51, report.as_dict()

    if verb == "migrate":
        prefix = _prefix(args)
        ledger = migrate.migrate(
            prefix.root, version=args.version, dry_run=args.dry_run
        )
        return verb, EXIT_OK, ledger

    if verb == "diagnose":
        manifest = None
        if args.prefix:
            manifest = _active_manifest(_prefix(args))
        doc = migrate.diagnose(manifest, client_version=args.client_version)
        code = EXIT_OK if doc.get("compatible") in (True, None) else 70
        return verb, code, doc

    if verb == "journal":
        return verb, EXIT_OK, journal_document(_prefix(args))

    if verb == "projection":
        prefix = _prefix(args)
        manifest = _active_manifest(prefix)
        state = read_installed(prefix)
        vroot = prefix.version_dir(str(state["active_version"]))
        return (
            verb,
            EXIT_OK,
            deploy_mod.projection_map(manifest, vroot, _live(args, prefix)),
        )

    if verb == "errors":
        return verb, EXIT_OK, taxonomy_document()

    if verb == "policies":
        return (
            verb,
            EXIT_OK,
            {
                "artifact": "policy-bundle",
                "exec_policy": policy.exec_policy_document(),
                "failure_policy": policy.failure_policy_document(),
                "taxonomy_agreement_problems": policy.policy_taxonomy_agreement(),
            },
        )

    raise PluginError("E_USAGE", f"unhandled verb {verb!r}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed usage
        return int(exc.code or EXIT_USAGE)
    try:
        verb, code, doc = _run(args)
    except PluginError as err:
        print(err.render(args.verb), file=sys.stderr)
        return err.exit_code
    except KeyboardInterrupt:  # pragma: no cover
        print("FAILED:interrupted", file=sys.stderr)
        return 130
    _emit(doc, getattr(args, "json", None))
    marker = f"{'SUCCESS' if code == EXIT_OK else 'FAILED'}:{verb}"
    print(marker if code == EXIT_OK else f"{marker} exit={code}")
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
