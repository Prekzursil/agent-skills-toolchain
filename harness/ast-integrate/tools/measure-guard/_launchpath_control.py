"""Both-states control for `launchpath.py` against the REAL repository.

`tests/test_launchpath.py` proves the FUNCTIONS fire, in throwaway repos. It cannot prove the
SHIPPED gate is wired to this tree - a gate can pass a perfect unit suite and still be pointed at
nothing. This runs the shipped `scan()` against this repository in four states and requires the
verdict to change, so a green from the real gate means something.

    LEG 1  as committed                                    -> GREEN
    LEG 2  the vendored copies rolled back to b9a77ad7^,   -> RED     the integration removed
           i.e. the pre-health-pane bytes
    LEG 3  the [cockpit] stanza deleted from the registry  -> RED     the registration removed
    LEG 4  a no-op comment appended to a vendored module   -> GREEN   inverted control

LEG 4 is what stops this being a rubber stamp in the other direction: a harness that reported RED
for any perturbation would score identically on LEG 2 and on a semantically empty edit.

NOTHING HERE MUTATES THE REPOSITORY. The gate is fed a substituted in-memory `oids`/`blobs` pair;
no tracked file is written, staged or read for content. Blob bytes come from `git cat-file`, so
even the "rolled back" state is real committed history rather than a hand-edited approximation.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launchpath as lp  # noqa: E402

PRE_INCREMENT = "b9a77ad7^"
VENDORED = (
    "skills/workflow-monitor/monitorcore",
    ".agents/skills/workflow-monitor/monitorcore",
)
ROLLED_BACK = ("pane.py", "pane_views.py", "unified.py", "health_source.py")


def _blob_at(rev_path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(lp.REPO), "cat-file", "-p", rev_path],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"cannot read {rev_path}: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


def _measure(oids: dict[str, str], blobs: dict[str, bytes]) -> lp.Result:
    result = lp.Result(registries=[], exempted=sorted(lp.EXEMPT))
    with tempfile.TemporaryDirectory(prefix="launchpath-control-") as tmp:
        for registry in lp.registry_paths(oids):
            result.registries.append(registry)
            launched, findings = lp.probe_registry(registry, oids, blobs, Path(tmp))
            result.launched += launched
            result.findings += findings
    return result


def _baseline() -> tuple[dict[str, str], dict[str, bytes]]:
    oids = lp.index_oids(lp.REPO)
    wanted = {o for p, o in oids.items() if p.endswith(lp.REGISTRY_SUFFIX)}
    for pkg in VENDORED:
        prefix = pkg.rsplit("/", 1)[0] + "/"
        wanted |= {o for p, o in oids.items() if p.startswith(prefix)}
    return oids, dict(lp.read_blobs(lp.REPO, wanted))


def _substitute(
    blobs: dict[str, bytes], oids: dict[str, str], path: str, data: bytes
) -> None:
    """Point one tracked path at synthetic bytes, leaving every other path untouched."""
    fake = f"MUTANT::{path}"
    oids[path] = fake
    blobs[fake] = data


def _report(leg: str, expect_ok: bool, result: lp.Result) -> bool:
    verdict = "GREEN" if result.ok else "RED"
    ok = result.ok is expect_ok
    detail = "" if result.ok else f" :: {result.findings[0][:150]}"
    print(f"  [{'PASS' if ok else 'FAIL'}] {leg:<52} -> {verdict}{detail}")
    return ok


def main() -> int:
    legs: list[bool] = []

    base_oids, base_blobs = _baseline()
    legs.append(
        _report("LEG 1 as committed", True, _measure(dict(base_oids), dict(base_blobs)))
    )

    oids, blobs = dict(base_oids), dict(base_blobs)
    for pkg in VENDORED:
        for name in ROLLED_BACK:
            path = f"{pkg}/{name}"
            _substitute(blobs, oids, path, _blob_at(f"{PRE_INCREMENT}:{path}"))
    legs.append(
        _report(
            f"LEG 2 vendored copies rolled back to {PRE_INCREMENT}",
            False,
            _measure(oids, blobs),
        )
    )

    oids, blobs = dict(base_oids), dict(base_blobs)
    for registry in lp.registry_paths(oids):
        text = blobs[oids[registry]].decode("utf-8")
        head, sep, _ = text.partition("[cockpit]")
        if not sep:
            raise SystemExit(
                f"control is stale: {registry} has no [cockpit] stanza to delete"
            )
        _substitute(blobs, oids, registry, head.encode("utf-8"))
    legs.append(
        _report(
            "LEG 3 [cockpit] stanza deleted from both mirrors",
            False,
            _measure(oids, blobs),
        )
    )

    oids, blobs = dict(base_oids), dict(base_blobs)
    for pkg in VENDORED:
        path = f"{pkg}/pane.py"
        _substitute(
            blobs, oids, path, blobs[base_oids[path]] + b"\n# no-op inverted control\n"
        )
    legs.append(
        _report(
            "LEG 4 no-op comment appended (inverted control)",
            True,
            _measure(oids, blobs),
        )
    )

    if all(legs):
        print(
            f"SUCCESS:launchpath-control {len(legs)}/{len(legs)} legs behaved as required"
        )
        return 0
    print(
        f"FAILED:launchpath-control {legs.count(False)} of {len(legs)} legs misbehaved"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
