"""The publisher CLI: ``python -m mkt <verb>``.

CONTRACT
    Every verb returns a terminal marker on stdout -- ``SUCCESS:<verb>`` or
    ``FAILED:<verb> <reason>`` -- and an exit code that agrees with it (AGENTS.md section 4).
    Every verb FAILS CLOSED: an unreadable input, an empty walk, or a refusal is non-zero.
    A CLI gate that exits 0 when it found nothing to check is a permanently green gate.

SECRET HANDLING
    A signing key is supplied as a FILE (``--key-file``) holding a 64-char hex seed, or, for
    the fixture only, derived from a public label (``--fixture-key pub:alpha-tools``). The CLI
    never prints a secret, never writes one outside a path the caller named, and never
    rotates or deletes an existing one. ``keygen`` refuses to overwrite an existing key file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import bundle as bundle_mod
from . import fixture, install, lint, moderation, publish, registry, scaffold, schemas
from .canon import read_json, write_json
from .crypto import generate_keypair, key_id

KEY_WARNING = (
    "# mkt signing key (hex seed). Treat as a credential: do not commit, do not paste.\n"
    "# This file was created by `python -m mkt keygen`; mkt never rotates or deletes it.\n"
)


def _load_secret(args: argparse.Namespace) -> str:
    if getattr(args, "fixture_key", None):
        return fixture.keys_for(args.fixture_key)[0]
    if not getattr(args, "key_file", None):
        raise SystemExit(
            "FAILED:mkt no signing key: pass --key-file <path> or --fixture-key <publisher-id>"
        )
    text = Path(args.key_file).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise SystemExit(f"FAILED:mkt key file contains no key line: {args.key_file}")


def _load_policy(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "fixture_policy", False):
        return fixture.trust_policy()
    if not getattr(args, "trust_policy", None):
        raise SystemExit(
            "FAILED:mkt no trust policy: pass --trust-policy <path> or --fixture-policy"
        )
    doc = read_json(args.trust_policy)
    schemas.validate("trust-policy", doc)
    return doc


def _emit(verb: str, ok: bool, payload: Any, reason: str = "") -> int:
    print(json.dumps(payload, indent=2, default=str))
    print(f"SUCCESS:mkt-{verb}" if ok else f"FAILED:mkt-{verb} {reason}".rstrip())
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# verbs
# --------------------------------------------------------------------------- #


def cmd_keygen(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists():
        return _emit(
            "keygen",
            False,
            {"path": str(out)},
            "refusing to overwrite an existing key file",
        )
    secret, public = generate_keypair()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(KEY_WARNING + secret + "\n", encoding="utf-8", newline="\n")
    return _emit(
        "keygen",
        True,
        {"key_file": str(out), "public_key": public, "key_id": key_id(public)},
    )


def cmd_scaffold(args: argparse.Namespace) -> int:
    root = scaffold.scaffold(
        args.into,
        name=args.name,
        version=args.version,
        summary=args.summary,
        spdx=args.license,
        channel=args.channel,
        kind=args.kind,
    )
    files = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
    return _emit("scaffold", True, {"package_dir": str(root), "files": files})


def cmd_validate(args: argparse.Namespace) -> int:
    """Local validator: validate ANY marketplace document against its schema."""
    target = Path(args.path)
    if not target.is_file():
        return _emit("validate", False, {"path": str(target)}, "no such file")
    doc = read_json(target)
    errors = schemas.errors_for(args.schema, doc)
    return _emit(
        "validate",
        not errors,
        {
            "path": str(target),
            "schema": args.schema,
            "errors": errors,
            "error_count": len(errors),
        },
        f"{len(errors)} validation error(s)",
    )


def cmd_selfcheck(args: argparse.Namespace) -> int:
    """Assert the POSITIVE about the contract surface: N of N schemas compile."""
    report = schemas.self_check()
    ok = report["checked"] == report["declared"] and not report["failures"]
    return _emit(
        "selfcheck",
        ok,
        report,
        f"{report['checked']}/{report['declared']} schemas compiled",
    )


def cmd_lint(args: argparse.Namespace) -> int:
    policy = _load_policy(args) if (args.trust_policy or args.fixture_policy) else None
    target = Path(args.path)
    if (target / registry.INDEX_NAME).is_file():
        report = lint.lint_registry(
            target,
            trust_policy=policy,
            governance_path=args.governance
            or fixture.MARKETPLACE_ROOT / "governance-policy.json",
        )
    elif target.is_file():
        index = read_json(args.index) if args.index else None
        report = lint.lint_package(target, trust_policy=policy, index=index)
    else:
        return _emit(
            "lint",
            False,
            {"path": str(target)},
            "not a registry root and not a manifest file",
        )
    if args.out:
        write_json(args.out, report)
    return _emit(
        "lint",
        report["verdict"] == "PASS",
        report,
        f"verdict={report['verdict']} findings={len(report['findings'])} rules={len(report['rules_evaluated'])}/{report['rules_total']}",
    )


def cmd_publish(args: argparse.Namespace) -> int:
    policy = _load_policy(args)
    governance = (
        read_json(args.governance) if args.governance else fixture.governance_policy()
    )
    try:
        result = publish.publish_into(
            args.package,
            args.registry,
            secret_hex=_load_secret(args),
            publisher_id=args.publisher,
            maintainer_secret_hex=_maintainer_secret(args),
            trust_policy=policy,
            governance=governance,
            license_basis_path=args.license_basis,
        )
    except publish.PublishRefused as exc:
        return _emit(
            "publish",
            False,
            {
                "code": exc.code,
                "message": str(exc),
                "findings": [f.__dict__ for f in exc.findings],
            },
            exc.code,
        )
    return _emit(
        "publish",
        True,
        {
            "name": result.name,
            "version": result.version,
            "conformance_score": result.score["total"],
            "payload_files": result.payload_files,
            "manifest": str(result.manifest_path),
            "warnings": result.warnings,
        },
    )


def _maintainer_secret(args: argparse.Namespace) -> str:
    """The index-signing key, which is a DIFFERENT key from the publisher's.

    Role separation is the point (GOVERNANCE.md section 1): only a registry-maintainer key may
    sign the index. Defaulting this to the publisher key would collapse the two roles into one,
    so an explicit ``--maintainer-key-file`` is required outside the fixture.
    """
    path = getattr(args, "maintainer_key_file", None)
    if not path:
        if getattr(args, "fixture_key", None):
            return fixture.keys_for(args.maintainer)[0]
        raise SystemExit(
            "FAILED:mkt missing --maintainer-key-file (the index-signing key)"
        )
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise SystemExit(f"FAILED:mkt maintainer key file contains no key line: {path}")


def cmd_search(args: argparse.Namespace) -> int:
    index = registry.load_index(args.registry)
    hits = registry.search(
        index,
        text=args.text,
        category=args.category,
        tag=args.tag,
        channel=args.channel,
        include_yanked=args.include_yanked,
    )
    return _emit(
        "search",
        True,
        {
            "query": {
                "text": args.text,
                "category": args.category,
                "tag": args.tag,
                "channel": args.channel,
            },
            "count": len(hits),
            "results": [
                {
                    "name": h["name"],
                    "version": h["version"],
                    "channel": h["channel"],
                    "publisher": h["publisher"],
                    "score": h["conformance_score"],
                    "summary": h.get("summary", ""),
                }
                for h in hits
            ],
        },
    )


def cmd_install(args: argparse.Namespace) -> int:
    policy = _load_policy(args)
    inst = install.Installer(
        args.registry,
        args.site,
        policy,
        client_id=args.client,
        client_version=args.client_version,
        platform_id=args.platform,
    )
    verb = args.action
    try:
        if verb == "install":
            receipt = inst.install(
                args.name,
                args.range,
                channel=args.channel,
                allow_vulnerable=args.allow_vulnerable,
                frozen=args.frozen,
            )
        elif verb == "update":
            receipt = inst.update(
                args.name,
                args.range,
                channel=args.channel,
                allow_vulnerable=args.allow_vulnerable,
            )
        elif verb == "remove":
            receipt = inst.remove(args.name)
        else:
            receipt = inst.rollback(args.name)
    except install.InstallRefused as exc:
        return _emit(
            verb,
            False,
            {
                "code": exc.code,
                "gate": exc.gate,
                "message": str(exc),
                "receipt": exc.receipt,
            },
            exc.code,
        )
    return _emit(
        verb,
        receipt["outcome"] == "SUCCESS",
        receipt,
        receipt.get("refusal_code", receipt["outcome"]),
    )


def cmd_health_check(args: argparse.Namespace) -> int:
    """Flag installed packages named by the registry's live revocation list."""
    policy = _load_policy(args)
    inst = install.Installer(
        args.registry,
        args.site,
        policy,
        client_id=args.client,
        client_version=args.client_version,
        platform_id=args.platform,
    )
    report = inst.health_check()
    ok = report.get("outcome") == "SUCCESS"
    return _emit(
        "health-check",
        ok,
        report,
        None if ok else str(report.get("code") or "health-check-refused"),
    )


def cmd_revoke(args: argparse.Namespace) -> int:
    scope: dict[str, Any] = {"kind": args.scope, "name": args.name}
    if args.scope == "version":
        scope["version"] = args.version
    elif args.scope == "range":
        scope["range"] = args.range
    elif args.scope == "key":
        scope = {"kind": "key", "public_key": args.public_key}
    try:
        doc = moderation.revoke(
            args.registry,
            scope=scope,
            reason=args.reason,
            severity=args.severity,
            authority=args.authority,
            maintainer_secret_hex=_load_secret(args),
        )
    except moderation.ModerationError as exc:
        return _emit("revoke", False, {"message": str(exc)}, "moderation-error")
    return _emit(
        "revoke",
        True,
        {"revocations": [r["revocation_id"] for r in doc["revocations"]]},
    )


def cmd_export(args: argparse.Namespace) -> int:
    coords = [tuple(c.split("@", 1)) for c in args.package]
    manifest = bundle_mod.export_bundle(
        args.registry,
        args.out,
        packages=[(n, v) for n, v in coords],
        maintainer_secret_hex=_load_secret(args),
    )
    return _emit(
        "export",
        True,
        {
            "bundle_id": manifest["bundle_id"],
            "packages": manifest["packages"],
            "includes": manifest["includes"],
        },
    )


def cmd_import(args: argparse.Namespace) -> int:
    policy = _load_policy(args)
    try:
        manifest = bundle_mod.import_bundle(
            args.bundle,
            args.registry,
            trust_policy=policy,
            maintainer_secret_hex=_load_secret(args),
        )
    except bundle_mod.BundleError as exc:
        return _emit("import", False, {"message": str(exc)}, "bundle-refused")
    return _emit(
        "import",
        True,
        {"bundle_id": manifest["bundle_id"], "packages": manifest["packages"]},
    )


def cmd_fixture(args: argparse.Namespace) -> int:
    built = fixture.build(args.into)
    unexpected = [r for r in built["refusals"] if r["expected"] != r["actual"]]
    return _emit(
        "fixture",
        not unexpected and len(built["published"]) == len(fixture.PUBLISHABLE),
        {
            "registry_root": str(built["registry_root"]),
            "published": built["published"],
            "refusals": built["refusals"],
            "entries": len(built["index"]["entries"]),
        },
        f"{len(unexpected)} refusal(s) did not match the expected code",
    )


def cmd_mutations(args: argparse.Namespace) -> int:
    from . import mutations

    return mutations.main([])


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mkt", description="marketplace publisher CLI")
    sub = p.add_subparsers(dest="verb", required=True)

    g = sub.add_parser(
        "keygen", help="create an Ed25519 signing key file (refuses to overwrite)"
    )
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_keygen)

    s = sub.add_parser(
        "scaffold", help="create a new package that already passes the linter"
    )
    s.add_argument("--name", required=True)
    s.add_argument("--into", default=".")
    s.add_argument("--version", default="0.1.0")
    s.add_argument("--summary", default=None)
    s.add_argument("--license", default="MIT")
    s.add_argument("--channel", default="beta", choices=["stable", "beta", "canary"])
    s.add_argument("--kind", default="library")
    s.set_defaults(func=cmd_scaffold)

    v = sub.add_parser(
        "validate",
        help="local validator: check a document against a marketplace schema",
    )
    v.add_argument("path")
    v.add_argument("--schema", required=True, choices=list(schemas.SCHEMA_NAMES))
    v.set_defaults(func=cmd_validate)

    sc = sub.add_parser(
        "selfcheck", help="assert every declared schema exists and compiles"
    )
    sc.set_defaults(func=cmd_selfcheck)

    ln = sub.add_parser("lint", help="lint a registry root or a single manifest")
    ln.add_argument("path")
    ln.add_argument("--trust-policy", default=None)
    ln.add_argument("--fixture-policy", action="store_true")
    ln.add_argument("--index", default=None)
    ln.add_argument("--governance", default=None)
    ln.add_argument("--out", default=None)
    ln.set_defaults(func=cmd_lint)

    pb = sub.add_parser("publish", help="publish a package directory into a registry")
    pb.add_argument("package")
    pb.add_argument("--registry", required=True)
    pb.add_argument("--publisher", required=True)
    pb.add_argument("--key-file", default=None)
    pb.add_argument("--fixture-key", default=None)
    pb.add_argument("--maintainer", default="pub:registry-root")
    pb.add_argument("--maintainer-key-file", default=None)
    pb.add_argument("--trust-policy", default=None)
    pb.add_argument("--fixture-policy", action="store_true")
    pb.add_argument("--governance", default=None)
    pb.add_argument("--license-basis", default=None)
    pb.set_defaults(func=cmd_publish)

    se = sub.add_parser("search", help="search the registry index")
    se.add_argument("--registry", required=True)
    se.add_argument("--text", default=None)
    se.add_argument("--category", default=None)
    se.add_argument("--tag", default=None)
    se.add_argument("--channel", default=None)
    se.add_argument("--include-yanked", action="store_true")
    se.set_defaults(func=cmd_search)

    for action in ("install", "update", "remove", "rollback"):
        i = sub.add_parser(action, help=f"{action} a package in a site root")
        i.add_argument("name")
        i.add_argument("--registry", required=True)
        i.add_argument("--site", required=True)
        i.add_argument("--range", default="*")
        i.add_argument("--channel", default=None)
        i.add_argument("--trust-policy", default=None)
        i.add_argument("--fixture-policy", action="store_true")
        i.add_argument("--client", default="claude-code")
        i.add_argument("--client-version", default="2.1.0")
        i.add_argument("--platform", default=sys.platform)
        i.add_argument("--allow-vulnerable", action="store_true")
        i.add_argument("--frozen", action="store_true")
        i.set_defaults(func=cmd_install, action=action)

    hc = sub.add_parser(
        "health-check", help="flag installed packages named by the live revocation list"
    )
    hc.add_argument("--registry", required=True)
    hc.add_argument("--site", required=True)
    hc.add_argument("--trust-policy", default=None)
    hc.add_argument("--fixture-policy", action="store_true")
    hc.add_argument("--client", default="claude-code")
    hc.add_argument("--client-version", default="2.1.0")
    hc.add_argument("--platform", default=sys.platform)
    hc.set_defaults(func=cmd_health_check)

    rv = sub.add_parser("revoke", help="revoke a package, version, range, or key")
    rv.add_argument("--registry", required=True)
    rv.add_argument(
        "--scope", required=True, choices=["version", "range", "package", "key"]
    )
    rv.add_argument("--name", default=None)
    rv.add_argument("--version", default=None)
    rv.add_argument("--range", default=None)
    rv.add_argument("--public-key", default=None)
    rv.add_argument("--reason", required=True)
    rv.add_argument(
        "--severity",
        default="critical",
        choices=["none", "low", "medium", "high", "critical"],
    )
    rv.add_argument("--authority", required=True)
    rv.add_argument("--key-file", default=None)
    rv.add_argument("--fixture-key", default=None)
    rv.set_defaults(func=cmd_revoke)

    ex = sub.add_parser("export", help="export an offline bundle")
    ex.add_argument("--registry", required=True)
    ex.add_argument("--out", required=True)
    ex.add_argument("--package", action="append", required=True, metavar="NAME@VERSION")
    ex.add_argument("--key-file", default=None)
    ex.add_argument("--fixture-key", default=None)
    ex.set_defaults(func=cmd_export)

    im = sub.add_parser("import", help="verify and import an offline bundle")
    im.add_argument("bundle")
    im.add_argument("--registry", required=True)
    im.add_argument("--trust-policy", default=None)
    im.add_argument("--fixture-policy", action="store_true")
    im.add_argument("--key-file", default=None)
    im.add_argument("--fixture-key", default=None)
    im.set_defaults(func=cmd_import)

    fx = sub.add_parser(
        "fixture", help="build the test fixture marketplace into a directory"
    )
    fx.add_argument("--into", required=True)
    fx.set_defaults(func=cmd_fixture)

    mu = sub.add_parser(
        "mutations", help="run the both-states mutation battery over the install gates"
    )
    mu.set_defaults(func=cmd_mutations)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:  # a _load_* helper already emitted a FAILED marker
        if isinstance(exc.code, str):
            print(exc.code)
            return 1
        raise
    except (
        schemas.ValidationFailed,
        registry.RegistryError,
        moderation.ModerationError,
        bundle_mod.BundleError,
    ) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, indent=2))
        print(f"FAILED:mkt-{args.verb} {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
