"""The both-states mutation battery: proof that each install gate is LOAD-BEARING.

WHY THIS EXISTS
    A gate that refuses is not yet a gate that MATTERS. The install could be failing for an
    unrelated reason -- a missing file, a schema error, an exception in the wrong place --
    and the receipt would still say REFUSED with the right code. The only way to know a
    guard is doing the work is to REMOVE IT and watch the same input succeed.

    So for each gate: take :mod:`mkt.install`'s own source, disable exactly one guard by a
    textual substitution, load the result as a separate module, and run the identical
    scenario. The gate is load-bearing iff

        real module -> REFUSED (with the expected code)   AND   mutant -> SUCCESS

    Both halves are required. A mutant that also refuses means the scenario was blocked by
    something else and the test proved nothing about that gate.

DETECTOR DISCIPLINE ON THE MUTATION ITSELF
    :func:`mutate` asserts the pattern occurs EXACTLY ONCE. A substitution that matched zero
    places silently produces an unmutated "mutant" (which then refuses, and would be read as
    "the guard is load-bearing" -- a false pass); a substitution that matched twice disables
    more than the gate under test. Both are detector failures, not findings, and both raise.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import fixture, publish, registry
from .canon import digest_file, read_json, write_json

MUTANT_MODULE = "mkt._mutant_install"


class MutationError(RuntimeError):
    """The mutation could not be applied uniquely -- a detector failure, not a finding."""


def install_source() -> str:
    return (Path(__file__).resolve().parent / "install.py").read_text(encoding="utf-8")


def flexible_pattern(needle: str) -> re.Pattern[str]:
    """Compile ``needle`` into a WHITESPACE-FLEXIBLE regex.

    A literal ``str.count`` needle is brittle against the formatter: ``ruff format`` wrapped four
    of these guards across lines and every literal needle silently stopped matching. The
    uniqueness assertion turned that into a loud failure rather than a false pass, but a battery
    that has to be re-typed after every reformat is a battery that eventually gets deleted -- so
    the needle is written as source text and matched with flexible whitespace between tokens.

    Splitting on whitespace alone was NOT enough and was measured to still miss: the formatter
    inserts a newline immediately after an open paren, i.e. INSIDE what a whitespace split treats
    as one token (``reg.revocations_for(revocation,``). So the needle is tokenised into word runs
    and single punctuation characters, joined with ``\\s+`` between two word tokens (where a
    separator is mandatory) and ``\\s*`` everywhere else.
    """
    tokens = re.findall(r"\w+|\S", needle)
    if not tokens:
        raise MutationError("empty mutation needle")
    parts = [re.escape(tokens[0])]
    for prev, cur in zip(tokens, tokens[1:], strict=False):
        mandatory = _is_word_char(prev[-1]) and _is_word_char(cur[0])
        parts.append((r"\s+" if mandatory else r"\s*") + re.escape(cur))
    return re.compile("".join(parts))


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def count_matches(source: str, needle: str) -> int:
    return len(flexible_pattern(needle).findall(source))


def mutate(source: str, needle: str, replacement: str) -> str:
    """Replace ``needle`` with ``replacement``, requiring EXACTLY one occurrence."""
    pattern = flexible_pattern(needle)
    mutated, count = pattern.subn(lambda _match: replacement, source)
    if count != 1:
        raise MutationError(
            f"mutation pattern must occur exactly once, found {count}: {needle!r}. "
            "Zero means the mutant is unmutated and would produce a false pass; two means the "
            "mutation disables more than the gate under test."
        )
    return mutated


def load_mutant(source: str, *, name: str = MUTANT_MODULE) -> Any:
    """Load mutated source as a real module inside the ``mkt`` package (relative imports work)."""
    spec = importlib.util.spec_from_loader(name, loader=None)
    if (
        spec is None
    ):  # pragma: no cover - importlib always returns a spec for a named loader
        raise MutationError("could not build a module spec for the mutant")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "mkt"
    sys.modules[name] = module
    try:
        # Executing dynamically-built code IS the mechanism here, so the rule's advice --
        # "use explicit dispatch" -- has nothing to dispatch to: the whole point is to run a
        # deliberately BROKEN variant of mkt/install.py and prove the gate under test rejects
        # it. `source` comes from mutate() applied to this repo's own committed install.py,
        # never from user input or the network, and the mutant module is popped from
        # sys.modules on any failure so a broken mutant cannot masquerade as a passing gate.
        #
        # NOT rewritten as spec_from_file_location + loader.exec_module: that calls exec on the
        # compiled code object internally, so it would clear the scanner while changing nothing
        # about what actually runs, and would leave the next reader believing there is no
        # dynamic execution in this file. Suppress honestly rather than launder.
        #
        # semgrep only honours a suppression inline or on the line DIRECTLY above the match, so
        # this comment must stay adjacent to the call.
        # nosemgrep: quality.opengrep.python-exec-use
        exec(compile(source, "<mutant mkt/install.py>", "exec"), module.__dict__)  # noqa: S102
    except (
        Exception
    ):  # pragma: no cover - a broken mutant must not look like a passing gate
        sys.modules.pop(name, None)
        raise
    return module


def unload_mutant(name: str = MUTANT_MODULE) -> None:
    sys.modules.pop(name, None)


# --------------------------------------------------------------------------- #
# scenarios: each returns (registry_root, install kwargs) that the gate blocks
# --------------------------------------------------------------------------- #


def _clone(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def _resign_index(root: Path, index: dict[str, Any], secret: str, now: str) -> None:
    publish.sign_index(index, secret, now=now)
    write_json(registry.index_path(root), index)


def scenario_revoked(built: dict[str, Any], work: Path) -> tuple[Path, dict[str, Any]]:
    """hello-skill@1.0.0 revoked by the moderation board."""
    from .moderation import revoke

    root = _clone(built["registry_root"], work / "sc-revoked")
    revoke(
        root,
        scope={"kind": "version", "name": "hello-skill", "version": "1.0.0"},
        reason="Mutation-battery scenario: this version is revoked.",
        severity="critical",
        authority="pub:moderation-board",
        maintainer_secret_hex=built["root_secret_hex"],
        revocation_id="rev:mut-1",
        now=built["now"],
    )
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_no_revocation_list(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """The revocation list is DELETED -- the fail-closed path."""
    root = _clone(built["registry_root"], work / "sc-no-revocation")
    (root / "revocation.json").unlink()
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_excessive_permissions(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """The over-permissioned package FORCED into a properly signed index."""
    root = _clone(built["registry_root"], work / "sc-evil")
    secret, _ = fixture.keys_for("pub:alpha-tools")
    result = publish.publish(
        built["sources"] / "evil-overreach-1.0.0",
        root,
        secret_hex=secret,
        publisher_id="pub:alpha-tools",
        trust_policy=built["trust_policy"],
        governance=None,
        now=built["now"],
        allow_unverified_aggregate=True,
    )
    index = registry.load_index(root)
    publish.upsert_entry(index, result.entry)
    _resign_index(root, index, built["root_secret_hex"], built["now"])
    return root, {"name": "evil-overreach", "range_text": "=1.0.0"}


def scenario_tampered_manifest(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A manifest field edited AFTER signing (summary text), digests re-mirrored in the index."""
    root = _clone(built["registry_root"], work / "sc-tampered-manifest")
    mpath = root / "packages" / "hello-skill" / "1.0.0" / "manifest.json"
    manifest = read_json(mpath)
    manifest["summary"] = (
        "TAMPERED after signing: this text was never signed by the publisher."
    )
    write_json(mpath, manifest)
    index = registry.load_index(root)
    for entry in index["entries"]:
        if entry["name"] == "hello-skill" and entry["version"] == "1.0.0":
            entry["manifest_digest"] = digest_file(mpath)
    _resign_index(root, index, built["root_secret_hex"], built["now"])
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_tampered_payload(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A payload byte changed in the registry, SIGNED manifest untouched (the FM-2 drift shape).

    The SBOM is updated to match the new bytes ON PURPOSE. A naive version of this scenario --
    tamper the payload and leave the SBOM stale -- was measured to be REFUSED by the SBOM gate
    in the mutant too, so it proved nothing about the payload-digest gate. Shadowing one gate
    with another is the classic way a mutation battery reports a false pass; isolating the gate
    is what makes the M5 result meaningful.
    """
    root = _clone(built["registry_root"], work / "sc-tampered-payload")
    pkg = root / "packages" / "hello-skill" / "1.0.0"
    target = pkg / "payload" / "hello.py"
    target.write_bytes(
        target.read_bytes() + b"\n# injected in the registry after signing\n"
    )
    sbom_doc = read_json(pkg / "sbom.json")
    for component in sbom_doc["components"]:
        if component["name"] == "hello.py":
            component["hashes"][0]["content"] = digest_file(target).split(":", 1)[1]
    write_json(pkg / "sbom.json", sbom_doc)
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_sbom_hole(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A component DROPPED from the SBOM: payload digest still matches, the bill does not.

    This isolates the SBOM gate from the payload-digest gate. Removing a payload FILE would
    trip the digest gate first and would tell us nothing about the SBOM check.
    """
    root = _clone(built["registry_root"], work / "sc-sbom-hole")
    spath = root / "packages" / "hello-skill" / "1.0.0" / "sbom.json"
    doc = read_json(spath)
    doc["components"] = doc["components"][:-1]
    write_json(spath, doc)
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_open_advisory(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """vulnerable-lib, with an open `high` advisory above the policy ceiling."""
    return built["registry_root"], {"name": "vulnerable-lib", "range_text": "=1.0.0"}


def scenario_denied_license(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A package whose SBOM carries a component licence the policy does not allow."""
    root = _clone(built["registry_root"], work / "sc-license")
    secret, _ = fixture.keys_for("pub:beta-labs")
    result = publish.publish(
        built["sources"] / "apache-mixer-1.0.0",
        root,
        secret_hex=secret,
        publisher_id="pub:beta-labs",
        trust_policy=built["trust_policy"],
        governance=None,
        now=built["now"],
        allow_unverified_aggregate=True,
    )
    index = registry.load_index(root)
    publish.upsert_entry(index, result.entry)
    _resign_index(root, index, built["root_secret_hex"], built["now"])
    return root, {"name": "apache-mixer", "range_text": "=1.0.0"}


def scenario_unsigned_index(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """The index re-signed by a key that is NOT a declared registry-maintainer key."""
    root = _clone(built["registry_root"], work / "sc-rogue-index")
    rogue_secret, _ = fixture.keys_for("pub:alpha-tools")
    index = registry.load_index(root)
    _resign_index(root, index, rogue_secret, built["now"])
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


def scenario_rogue_advisory_list(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """``advisories.json`` EMPTIED and re-signed by a NON-maintainer key.

    The attacker's goal is to make the vulnerability gate see nothing. With the maintainer-key
    check the install refuses; without it the emptied list is believed and the vulnerable package
    installs. That is what makes the one-line key check load-bearing rather than ornamental.
    """
    from .crypto import sign_document

    root = _clone(built["registry_root"], work / "sc-rogue-advisory")
    doc = read_json(root / "advisories.json")
    doc["advisories"] = []
    doc.pop("signature", None)
    doc["signature"] = sign_document(
        doc,
        "mkt.advisory.v1",
        fixture.keys_for("pub:alpha-tools")[0],
        signed_at=built["now"],
    )
    write_json(root / "advisories.json", doc)
    return root, {"name": "vulnerable-lib", "range_text": "=1.0.0"}


def scenario_frozen_pin_drift(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A LEGITIMATE re-publish of the same version, against an existing frozen lockfile.

    Everything is correctly signed, so gates 3/9/10 pass and only the lockfile pin disagrees.
    Reaching gate 13 requires exactly this shape -- a tampered payload trips gate 9 first and never
    exercises the pin at all.
    """
    root = _clone(built["registry_root"], work / "sc-frozen-pin")
    seed = work / "sc-frozen-pin-seed"
    if seed.exists():
        shutil.rmtree(seed)

    from . import install as real_install

    real_install.Installer(
        root,
        seed,
        copy.deepcopy(built["trust_policy"]),
        platform_id="win32",
        use_federation=False,
    ).install("hello-skill", "=1.0.0", channel="stable", now=built["now"])

    republished = work / "sc-frozen-pin-src"
    if republished.exists():
        shutil.rmtree(republished)
    shutil.copytree(built["sources"] / "hello-skill-1.0.0", republished)
    target = republished / "payload" / "hello.py"
    target.write_bytes(
        target.read_bytes() + b"\n# republished under the same version\n"
    )
    publish.publish_into(
        republished,
        root,
        secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        publisher_id="pub:alpha-tools",
        maintainer_secret_hex=built["root_secret_hex"],
        trust_policy=built["trust_policy"],
        governance=built["governance"],
        now=built["now"],
        license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
    )
    return root, {
        "name": "hello-skill",
        "range_text": "=1.0.0",
        "channel": "stable",
        "frozen": True,
        "seed_site": seed,
    }


def scenario_unresolvable_dependency(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A package with a REQUIRED dependency that is published nowhere.

    Synthesised here rather than in the committed fixture because its only purpose is this one
    mutation: the fixture's ``dep-consumer`` carries an OPTIONAL missing dependency, which must be
    skipped, so it cannot exercise the required-dependency refusal.
    """
    root = _clone(built["registry_root"], work / "sc-orphan-dep")
    src = work / "sc-orphan-dep-src"
    if src.exists():
        shutil.rmtree(src)
    (src / "payload").mkdir(parents=True)
    (src / "payload" / "README.md").write_text(
        "# orphan-dep\n\nRequires a package that does not exist. The install must refuse.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        src / "package.json",
        {
            "name": "orphan-dep",
            "version": "1.0.0",
            "channel": "stable",
            "kind": "library",
            "summary": "Requires a package published nowhere; the install must refuse.",
            "license": {
                "spdx": "MIT",
                "notice_required": False,
                "aggregate_verified": True,
            },
            "permissions": ["fs:read:packages/orphan-dep/**"],
            "compatibility": {
                "platforms": ["any"],
                "clients": [{"id": "claude-code", "range": ">=2.0.0"}],
            },
            "dependencies": [{"name": "no-such-package", "range": "^1.0.0"}],
            "provenance": {
                "source": "https://fixture.invalid/orphan-dep",
                "source_revision": "9" * 40,
                "builder": "mkt-fixture/1.0.0",
                "reproducible": True,
            },
            "payload_files": ["README.md"],
            "file_licenses": {"README.md": "MIT"},
        },
    )
    result = publish.publish(
        src,
        root,
        secret_hex=fixture.keys_for("pub:alpha-tools")[0],
        publisher_id="pub:alpha-tools",
        trust_policy=built["trust_policy"],
        governance=None,
        now=built["now"],
    )
    index = registry.load_index(root)
    publish.upsert_entry(index, result.entry)
    _resign_index(root, index, built["root_secret_hex"], built["now"])
    return root, {"name": "orphan-dep", "range_text": "=1.0.0", "channel": "stable"}


def scenario_wrong_platform(
    built: dict[str, Any], work: Path
) -> tuple[Path, dict[str, Any]]:
    """A manifest restricted to linux, installed on win32."""
    root = _clone(built["registry_root"], work / "sc-platform")
    mpath = root / "packages" / "hello-skill" / "1.0.0" / "manifest.json"
    manifest = read_json(mpath)
    manifest["compatibility"]["platforms"] = ["linux"]
    secret, _ = fixture.keys_for("pub:alpha-tools")
    manifest.pop("signature", None)
    from .crypto import sign_document

    manifest["signature"] = sign_document(
        manifest, "mkt.manifest.v1", secret, signed_at=built["now"]
    )
    write_json(mpath, manifest)
    index = registry.load_index(root)
    for entry in index["entries"]:
        if entry["name"] == "hello-skill" and entry["version"] == "1.0.0":
            entry["manifest_digest"] = digest_file(mpath)
            entry["signature"] = manifest["signature"]
    _resign_index(root, index, built["root_secret_hex"], built["now"])
    return root, {"name": "hello-skill", "range_text": "=1.0.0", "channel": "stable"}


# --------------------------------------------------------------------------- #
# the battery
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Mutation:
    """One gate, one scenario, and the EDITS that disable exactly that gate.

    ``edits`` is a tuple because a gate is not always one comparison. The payload-digest gate
    is deliberately two: one against the registry copy and one against the copy just written
    into the site. Disabling only the first leaves the second refusing, which would read as
    "load-bearing" while actually measuring a different check -- so the mutation names both and
    the uniqueness assertion applies to each.
    """

    mutation_id: str
    gate: str
    expected_code: str
    edits: tuple[tuple[str, str], ...]
    scenario: Callable[[dict[str, Any], Path], tuple[Path, dict[str, Any]]]


BATTERY: tuple[Mutation, ...] = (
    Mutation(
        "M1-revocation-match",
        "revocation",
        "MKT-I04",
        (
            (
                'hits = reg.revocations_for(revocation, entry["name"], entry["version"], public_key=pub_key)',
                "hits = []",
            ),
        ),
        scenario_revoked,
    ),
    Mutation(
        "M2-revocation-fail-closed",
        "revocation",
        "MKT-I04",
        (
            (
                'if self.trust_policy["on_missing"]["revocation_list"] == "refuse":',
                "if False:",
            ),
        ),
        scenario_no_revocation_list,
    ),
    Mutation(
        "M3-permission-ceiling",
        "permissions",
        "MKT-I05",
        (("if not verdict.admissible:", "if False:"),),
        scenario_excessive_permissions,
    ),
    Mutation(
        "M4-manifest-signature",
        "manifest-signature",
        "MKT-I03",
        (
            (
                'ok, why = verify_document(manifest, "mkt.manifest.v1", expected_public_key=pub_key)',
                'ok, why = True, ""',
            ),
        ),
        scenario_tampered_manifest,
    ),
    Mutation(
        "M5-payload-digest",
        "payload-digest",
        "MKT-I09",
        (
            ('if recomputed != manifest["payload"]["digest"]:', "if False:"),
            ('if installed_digest != manifest["payload"]["digest"]:', "if False:"),
        ),
        scenario_tampered_payload,
    ),
    Mutation(
        "M6-sbom-bijection",
        "sbom",
        "MKT-I10",
        (("if not verdict.ok:", "if False:"),),
        scenario_sbom_hole,
    ),
    Mutation(
        "M7-advisory-ceiling",
        "advisory",
        "MKT-I07",
        (("if blocking:", "if False:"),),
        scenario_open_advisory,
    ),
    Mutation(
        "M8-license-components",
        "license",
        "MKT-I11",
        (("if offenders:", "if False:"),),
        scenario_denied_license,
    ),
    Mutation(
        "M9-index-maintainer-key",
        "index-signature",
        "MKT-I01",
        (
            (
                'ok, why = reg.verify_index_signature(source_root.index, self.trust_policy["registry_maintainer_keys"])',
                'ok, why = True, ""',
            ),
        ),
        scenario_unsigned_index,
    ),
    Mutation(
        "M10-platform-compatibility",
        "compatibility",
        "MKT-I06",
        (
            (
                'if "any" not in platforms and self.platform_id not in platforms:',
                "if False:",
            ),
        ),
        scenario_wrong_platform,
    ),
    Mutation(
        "M11-advisory-maintainer-key",
        "advisory",
        "MKT-I07",
        (
            (
                'if not ok or adv_key not in self.trust_policy["registry_maintainer_keys"]:',
                "if False:",
            ),
        ),
        scenario_rogue_advisory_list,
    ),
    Mutation(
        "M12-lockfile-pin",
        "lockfile",
        "MKT-I13",
        (("if drift:", "if False:"),),
        scenario_frozen_pin_drift,
    ),
    Mutation(
        "M13-dependency-resolution",
        "dependencies",
        "MKT-I12",
        (("for dep in deps:", "for dep in []:"),),
        scenario_unresolvable_dependency,
    ),
)


def _run_one(
    module: Any,
    root: Path,
    site: Path,
    policy: dict[str, Any],
    kwargs: dict[str, Any],
    now: str,
) -> tuple[str, str]:
    # A scenario may need a site that ALREADY holds state (a lockfile pin, an installed version).
    # Each run gets its own copy of that seed so the real run cannot consume what the mutant run
    # needs -- shared mutable state between the two halves would make the comparison meaningless.
    seed = kwargs.get("seed_site")
    if seed is not None and not site.exists():
        shutil.copytree(seed, site)
    inst = module.Installer(root, site, copy.deepcopy(policy), use_federation=False)
    try:
        receipt = inst.install(
            kwargs["name"],
            kwargs.get("range_text", "*"),
            channel=kwargs.get("channel"),
            frozen=bool(kwargs.get("frozen")),
            now=now,
        )
    except module.InstallRefused as exc:
        return "REFUSED", exc.code
    except AssertionError as exc:
        # A mutant that breaks gate accounting is a broken mutant, reported as such.
        return "ACCOUNTING-FAILED", str(exc)[:120]
    return receipt["outcome"], receipt.get("refusal_code", "")


def run_battery(
    work_root: str | Path, *, built: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run every mutation. Returns a per-mutation verdict plus a bottom line."""
    work = Path(work_root)
    if built is None:
        built = fixture.build(work / "fixture", now=fixture.T0)
    policy = built["trust_policy"]
    now = built["now"]
    source = install_source()

    from . import install as real_install

    results = []
    for mutation in BATTERY:
        root, kwargs = mutation.scenario(built, work)
        real_outcome, real_code = _run_one(
            real_install,
            root,
            work / f"site-real-{mutation.mutation_id}",
            policy,
            kwargs,
            now,
        )
        mutant_source = source
        for needle, replacement in mutation.edits:
            mutant_source = mutate(mutant_source, needle, replacement)
        module = load_mutant(mutant_source)
        try:
            mutant_outcome, mutant_code = _run_one(
                module,
                root,
                work / f"site-mutant-{mutation.mutation_id}",
                policy,
                kwargs,
                now,
            )
        finally:
            unload_mutant()
        load_bearing = (
            real_outcome == "REFUSED"
            and real_code == mutation.expected_code
            and mutant_outcome == "SUCCESS"
        )
        results.append(
            {
                "mutation": mutation.mutation_id,
                "gate": mutation.gate,
                "real_outcome": real_outcome,
                "real_code": real_code,
                "expected_code": mutation.expected_code,
                "mutant_outcome": mutant_outcome,
                "mutant_detail": mutant_code,
                "load_bearing": load_bearing,
            }
        )
    return {
        "mutations_declared": len(BATTERY),
        "mutations_run": len(results),
        "load_bearing": sum(1 for r in results if r["load_bearing"]),
        "results": results,
        "all_load_bearing": all(r["load_bearing"] for r in results)
        and len(results) == len(BATTERY),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point so the battery can be run as a gate.

    Fails closed: a zero-mutation run, a broken mutation, or any non-load-bearing gate exits
    non-zero. "Nothing blocking" is not a pass here either.
    """
    import tempfile

    argv = list(argv or [])
    with tempfile.TemporaryDirectory(prefix="mkt-mutations-") as tmp:
        report = run_battery(Path(tmp))
    print(json.dumps(report, indent=2))
    ok = (
        report["all_load_bearing"]
        and report["mutations_run"] == report["mutations_declared"] > 0
    )
    print(
        f"SUCCESS:mkt-mutation-battery {report['load_bearing']}/{report['mutations_declared']} load-bearing"
        if ok
        else f"FAILED:mkt-mutation-battery {report['load_bearing']}/{report['mutations_declared']} load-bearing"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
