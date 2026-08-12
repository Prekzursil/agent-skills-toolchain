"""A registered monitor must actually LAUNCH from the COMMITTED tree, not merely exist in it.

THE HOLE THIS CLOSES, measured 2026-08-12 at 2467dcd3. Three gates already guard the monitor
registry and every one of them stops short of running anything:

    vendordrift.py                       every committed copy of `monitorcore` is byte-identical
    tests/test_registry_commit_truth.py  the two registry mirrors match IN THE COMMIT, and every
                                         stanza's entry is a TRACKED path
    tests/test_registry_shipped.py       the entry exists ON THIS BOX's working tree

Byte-identical, tracked and present are three different questions from LAUNCHES. A shim whose
import breaks, a vendored copy missing the module the shim imports, a stanza renamed to a file
that parses but renders nothing, an entry that exits 0 without ever reaching its board - each of
those passes all three gates. That is the silent-no-op shape this repository has already been
bitten by once (`ui-audit` reverting to `main()` never running: exit 0, no artifacts, no error,
and every "audit passed" after it vacuous).

WHAT THIS GATE DOES. It materialises the registry and the probed skill directories from the
blobs git actually STORED, into a throwaway tree, and EXECUTES the registered entry there in a
bounded probe mode, requiring both exit 0 and a marker that proves the program reached its
render. Nothing is read from the working tree, so the answer is the one a fresh clone would
give - the check the fleet audit found existed nowhere.

WHY BLOBS AND NOT THE WORKING TREE. This box checks out CRLF and a Linux runner checks out LF;
a working-tree launch answers a question CI never asks. `git ls-files -s` gives the OID git
stored and `git cat-file --batch` hands back those exact bytes. `git archive` is NOT used: it
applies export-time EOL conversion and returns the CRLF worktree form on Windows, i.e. it
verifies the wrong bytes (`blobread.py` carries the three-route measurement).

WHY MOST STANZAS ARE NOT EXECUTED, AND WHY THAT IS NOT A SILENT SKIP. Four of the six registered
monitors are interactive pollers with no bounded, non-interactive probe mode, and `crcp` is
quarantined estate-wide. Skipping them silently would let the gate report a green computed over
almost nothing, so every stanza must be EITHER probed or carry a written exemption, and both
directions fail closed: a NEW stanza that is neither is a failure (it cannot arrive ungated and
unnoticed), and a probe or exemption naming a stanza the registry no longer has is also a
failure (the policy cannot rot into fiction). The honest scope is therefore: 1 of 6 stanzas is
executed, in each of the 2 registry mirrors, and the other 5 are accounted for by name.

FAIL CLOSED, six ways: an empty `git ls-files`; zero registries discovered; a registry that
parses to zero stanzas; a probed stanza whose entry is untracked; a skill directory that
materialises zero files; and a probe that times out. "0 findings" must never be reachable by
having found nothing to run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: A registry is a tracked path ending in this. The `tools/monitorcore/tests/fixtures/
#: monitors.toml` TEST FIXTURE deliberately does not, so it is excluded by construction rather
#: than by a hardcoded deny-list that a renamed fixture could slip past.
REGISTRY_SUFFIX = "monitor-launcher/monitors.toml"

#: Below this, assume discovery broke rather than that the registries were deleted. 2 mirrors
#: observed at 2467dcd3.
MIN_REGISTRIES = 1


class LaunchPathError(RuntimeError):
    """Discovery collapsed: the gate cannot honestly report anything."""


@dataclass(frozen=True)
class Probe:
    """A stanza this gate executes, and what proves the program actually rendered."""

    monitor: str
    #: Arguments appended after the entry script path.
    argv_tail: tuple[str, ...]
    #: A substring that MUST appear in stdout. Chosen to prove the launch reached the board, and
    #: to survive cosmetic reformatting of the frame around it.
    require: str
    timeout_s: float = 240.0


#: The stanzas executed end to end.
#:
#: `cockpit` is the unified board. `--once` renders a single frame and exits, and `--pane health`
#: selects the pane added by the MON increment, so the marker below proves the whole chain -
#: registry stanza -> `unified_board.py` shim -> the VENDORED `monitorcore` package beside it ->
#: the pane registry containing HEALTH. The marker is `:health` rather than the literal
#: `[6:health]` so that adding a seventh pane (which renumbers the strip) does not turn this gate
#: into a nuisance that gets deleted.
PROBES: tuple[Probe, ...] = (
    Probe(
        monitor="cockpit",
        argv_tail=("--once", "--pane", "health", "--width", "100"),
        require=":health",
    ),
)

#: Stanzas deliberately NOT executed, each with the reason. Kept as data, not as a comment, so
#: the gate can fail when one goes stale.
EXEMPT: Mapping[str, str] = {
    "wfmon": "persistent interactive poller; no bounded non-interactive probe mode",
    "agentmon": "one-shot spawner over a live transcript tree; nothing to render in a clean tree",
    "codexmon": "persistent interactive poller over ~/.codex rollouts; no bounded probe mode",
    "crcp": "CRCP is quarantined estate-wide; this gate must not start any part of it",
    "csmon": "shells to the `cs` dispatcher and a WSL2 daemon; not launchable on a CI runner",
}


@dataclass
class Result:
    """What the gate measured. `ok` is False if `findings` is non-empty."""

    registries: list[str] = field(default_factory=list)
    launched: list[str] = field(default_factory=list)
    exempted: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


def index_oids(repo: Path) -> dict[str, str]:
    """Every tracked path mapped to the blob OID git stored for it.

    `-z` rather than plain `-s`: without it git applies `core.quotePath` and wraps any path with
    a non-ASCII or unusual byte in quotes, which would silently drop that file from the walk.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise LaunchPathError(f"git ls-files failed in {repo}: {detail}")
    oids: dict[str, str] = {}
    for record in proc.stdout.decode("utf-8", "surrogateescape").split("\0"):
        meta, tab, path = record.partition("\t")
        if not tab:
            continue
        fields = meta.split()
        if len(fields) >= 2:
            oids[path] = fields[1]
    if not oids:
        raise LaunchPathError(
            f"git ls-files listed NOTHING in {repo}; discovery is broken, not the tree"
        )
    return oids


def read_blobs(repo: Path, oids: Iterable[str]) -> dict[str, bytes]:
    """Blob bytes exactly as stored, one `git cat-file --batch` for the whole set."""
    wanted = sorted(set(oids))
    if not wanted:
        return {}
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=("\n".join(wanted) + "\n").encode("ascii"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise LaunchPathError(f"git cat-file --batch failed: {detail}")
    out = proc.stdout
    blobs: dict[str, bytes] = {}
    pos = 0
    while pos < len(out):
        end = out.find(b"\n", pos)
        if end < 0:
            raise LaunchPathError("git cat-file --batch: truncated header")
        header = out[pos:end].decode("utf-8", "replace").split()
        if len(header) != 3 or header[1] != "blob":
            raise LaunchPathError(f"git cat-file --batch: unexpected header {header!r}")
        size = int(header[2])
        start = end + 1
        blobs[header[0]] = out[start : start + size]
        pos = start + size + 1
    missing = [oid for oid in wanted if oid not in blobs]
    if missing:
        raise LaunchPathError(
            f"git cat-file --batch returned no blob for {missing[:3]}"
        )
    return blobs


def registry_paths(oids: Mapping[str, str]) -> list[str]:
    return sorted(p for p in oids if p.endswith(REGISTRY_SUFFIX))


def skills_root(registry_path: str) -> str:
    """`skills/monitor-launcher/monitors.toml` -> `skills`.

    The registry's `dir` is relative to the DEPLOYED skills root, so each mirror resolves its
    stanzas against its own parent tree. Hardcoding `skills/` would make the gate blind to the
    `.agents/` mirror, which is precisely the shape `vendordrift.py` was written to end.
    """
    return registry_path.rsplit("/", 2)[0]


def parse_stanzas(data: bytes, where: str) -> dict[str, dict[str, object]]:
    try:
        parsed = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise LaunchPathError(f"{where}: not parseable as TOML ({exc})") from exc
    stanzas = {k: v for k, v in parsed.items() if isinstance(v, dict)}
    if not stanzas:
        raise LaunchPathError(f"{where}: parsed to ZERO stanzas; nothing to check")
    return stanzas


def materialise(
    blobs: Mapping[str, bytes], files: Mapping[str, str], dest: Path
) -> int:
    """Write stored blob bytes to `dest`, preserving the repo-relative layout."""
    written = 0
    for path, oid in files.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blobs[oid])
        written += 1
    return written


def run_probe(entry: Path, probe: Probe, cwd: Path) -> tuple[bool, str]:
    """Execute one entry script. Returns (ok, detail)."""
    env = dict(os.environ)
    env.pop(
        "PYTHONPATH", None
    )  # the shim owns sys.path[0]; nothing may shadow the vendored pkg
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [sys.executable, str(entry), *probe.argv_tail]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            cwd=str(cwd),
            env=env,
            timeout=probe.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {probe.timeout_s:.0f}s"
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        # Non-empty lines only: an argparse usage block is mostly indented continuation lines, and
        # a naive last-3-lines slice renders the diagnosis as whitespace (measured).
        tail = [ln.strip() for ln in (stderr or stdout).splitlines() if ln.strip()][-3:]
        return False, f"exit {proc.returncode}: {' | '.join(tail) or '<no output>'}"
    if probe.require not in stdout:
        head = [ln.strip() for ln in stdout.splitlines() if ln.strip()][:2]
        return (
            False,
            f"exit 0 but stdout lacks {probe.require!r}: {' | '.join(head) or '<empty>'}",
        )
    return True, "exit 0, marker present"


def check_policy(monitors: Iterable[str], where: str) -> list[str]:
    """Every stanza probed or exempt, and no probe/exemption naming a stanza that is gone."""
    present = set(monitors)
    probed = {p.monitor for p in PROBES}
    accounted = probed | set(EXEMPT)
    findings = []
    for orphan in sorted(present - accounted):
        findings.append(
            f"{where}: stanza [{orphan}] is neither probed nor exempt - a new monitor cannot "
            f"arrive ungated; add a Probe or an EXEMPT reason"
        )
    for stale in sorted(accounted - present):
        findings.append(
            f"{where}: launch policy names [{stale}] but the registry has no such stanza - "
            f"the policy has gone stale"
        )
    return findings


def probe_registry(
    registry_path: str,
    oids: Mapping[str, str],
    blobs: Mapping[str, bytes],
    workdir: Path,
) -> tuple[list[str], list[str]]:
    """Materialise and launch every probed stanza of one registry mirror."""
    root = skills_root(registry_path)
    stanzas = parse_stanzas(blobs[oids[registry_path]], registry_path)
    findings = check_policy(stanzas, registry_path)
    launched: list[str] = []

    for probe in PROBES:
        stanza = stanzas.get(probe.monitor)
        if stanza is None:
            continue  # already reported as a stale policy entry above
        directory, entry = stanza.get("dir"), stanza.get("entry")
        if not isinstance(directory, str) or not isinstance(entry, str):
            findings.append(
                f"{registry_path}: [{probe.monitor}] has no string dir/entry"
            )
            continue
        prefix = f"{root}/{directory}/"
        entry_path = f"{prefix}{entry}"
        subtree = {p: o for p, o in oids.items() if p.startswith(prefix)}
        if not subtree:
            findings.append(
                f"{registry_path}: [{probe.monitor}] {prefix} holds ZERO tracked files"
            )
            continue
        if entry_path not in subtree:
            findings.append(
                f"{registry_path}: [{probe.monitor}] entry {entry_path} is UNTRACKED"
            )
            continue
        dest = workdir / probe.monitor / root.replace("/", "_").replace(".", "_")
        written = materialise(blobs, subtree, dest)
        if written == 0:
            findings.append(
                f"{registry_path}: [{probe.monitor}] materialised ZERO files"
            )
            continue
        ok, detail = run_probe(dest / entry_path, probe, cwd=dest)
        label = f"{registry_path}:[{probe.monitor}] -> {entry_path}"
        if ok:
            launched.append(f"{label} ({written} files, {detail})")
        else:
            findings.append(f"{label} did NOT launch: {detail}")
    return launched, findings


def scan(repo: Path | None = None, *, workdir: Path | None = None) -> Result:
    """Measure every registry mirror. Raises `LaunchPathError` when discovery itself collapses."""
    root = repo or REPO
    oids = index_oids(root)
    registries = registry_paths(oids)
    if len(registries) < MIN_REGISTRIES:
        raise LaunchPathError(
            f"discovered {len(registries)} registries matching '*{REGISTRY_SUFFIX}' "
            f"(minimum {MIN_REGISTRIES}); discovery is broken, not the tree"
        )
    # Two passes: the registries must be READ before the gate knows which skill directories a
    # probed stanza points at, so their blobs are fetched first and the subtrees second.
    blobs = dict(read_blobs(root, {oids[p] for p in registries}))
    needed: set[str] = set()
    for registry in registries:
        base = skills_root(registry)
        stanzas = parse_stanzas(blobs[oids[registry]], registry)
        for probe in PROBES:
            stanza = stanzas.get(probe.monitor)
            directory = stanza.get("dir") if isinstance(stanza, dict) else None
            if isinstance(directory, str):
                prefix = f"{base}/{directory}/"
                needed |= {o for p, o in oids.items() if p.startswith(prefix)}
    blobs.update(read_blobs(root, needed))

    result = Result(registries=list(registries), exempted=sorted(EXEMPT))
    if workdir is not None:
        for registry in registries:
            launched, findings = probe_registry(registry, oids, blobs, workdir)
            result.launched += launched
            result.findings += findings
        return result
    with tempfile.TemporaryDirectory(prefix="launchpath-") as tmp:
        for registry in registries:
            launched, findings = probe_registry(registry, oids, blobs, Path(tmp))
            result.launched += launched
            result.findings += findings
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO), help="repository root to measure")
    parser.add_argument(
        "--json", action="store_true", help="emit the measurement as JSON"
    )
    args = parser.parse_args(argv)

    try:
        result = scan(Path(args.repo))
    except LaunchPathError as exc:
        print(f"FAILED:launchpath {exc}")
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "registries": result.registries,
                    "launched": result.launched,
                    "exempted": result.exempted,
                    "findings": result.findings,
                    "ok": result.ok,
                },
                indent=2,
            )
        )
    else:
        for line in result.launched:
            print(f"  LAUNCHED {line}")
        for name in result.exempted:
            print(f"  exempt   [{name}]: {EXEMPT[name]}")
        for line in result.findings:
            print(f"  FINDING  {line}")

    if not result.ok:
        print(
            f"FAILED:launchpath {len(result.findings)} registered monitor(s) do not launch"
        )
        return 1
    print(
        f"SUCCESS:launchpath {len(result.launched)} launch(es) from committed blobs across "
        f"{len(result.registries)} registry mirror(s); {len(result.exempted)} stanza(s) exempt"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
