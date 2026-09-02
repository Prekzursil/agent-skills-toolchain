"""Measure the built package and PROVE BY ENUMERATION what it does and does not contain.

The spec's one explicit prohibition is that the artifact must not carry the repository's ``.git``,
unrelated caches, logs, transcripts, credentials, or gigabytes of unrelated content. "We were
careful" is not evidence, so this script:

* prints the archive's byte size, its sha256, and its exact member count;
* prints EVERY member with its size, so the claim is auditable rather than asserted;
* enumerates each forbidden class against every member and reports the per-class hit count —
  including a **detector control** that runs the same classifier over a synthetic member list
  containing one known-forbidden path per class, so a zero cannot be a broken matcher;
* scans every member for credential shapes and reports the count (never the value).

Run from the repo root::

    python platform/plugin/measure_package.py [--package <zip>] [--json <path>]

Last line is ``SUCCESS:measure-package`` or ``FAILED:measure-package <reason>``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "platform"))

from plugin.build import MAX_BYTES, MAX_FILES, PLUGIN_NAME, PLUGIN_VERSION, build  # noqa: E402
from plugin.packager import archive_sha256  # noqa: E402
from plugin.payload import FORBIDDEN_CLASSES, classify_forbidden, scan_secrets  # noqa: E402

#: One known-forbidden path per class. The classifier MUST flag every one of these, otherwise a
#: "0 hits" verdict on the real package means nothing.
CONTROL_PATHS: dict[str, str] = {
    "vcs": ".git/config",
    "cache": "__pycache__/mod.pyc",
    "log": "run.log",
    "transcript": "sessions/2026-08-10.jsonl",
    "credential": ".env",
    "backup": "cli.py.bak",
    "archive": "unrelated-bundle.tar.gz",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="measure and audit the built plugin package"
    )
    ap.add_argument("--package", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    problems: list[str] = []
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.package:
        archive = args.package.resolve()
    else:
        tmp = tempfile.TemporaryDirectory(prefix="astplugin-measure-")
        result, _ = build(REPO_ROOT, Path(tmp.name))
        archive = result.archive

    size = archive.stat().st_size
    sha = archive_sha256(archive)
    with zipfile.ZipFile(archive) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        members = {i.filename: i.file_size for i in infos}
        blobs = {i.filename: zf.read(i.filename) for i in infos}

    print("=" * 78)
    print(f"PACKAGE MEASUREMENT  {PLUGIN_NAME} {PLUGIN_VERSION}")
    print("=" * 78)
    print(f"archive            : {archive}")
    print(f"archive bytes      : {size:,}  (budget {MAX_BYTES:,})")
    print(f"archive sha256     : {sha}")
    print(f"member count       : {len(members)}  (budget {MAX_FILES})")
    print(f"uncompressed bytes : {sum(members.values()):,}")

    print("\n--- EVERY MEMBER (enumerated; this is the whole package) ---")
    for name in sorted(members):
        print(f"  {members[name]:>8,}  {name}")

    print(
        "\n--- DETECTOR CONTROL: the classifier must flag a known-present item per class ---"
    )
    control_ok = True
    for klass, probe in sorted(CONTROL_PATHS.items()):
        got = classify_forbidden(probe)
        ok = got == klass
        control_ok &= ok
        print(f"  {'OK  ' if ok else 'BAD '} {klass:<11} {probe:<28} -> {got}")
    if not control_ok:
        problems.append("the forbidden-content classifier failed its own control")

    print("\n--- FORBIDDEN-CLASS ENUMERATION over the real package ---")
    per_class: dict[str, list[str]] = {k: [] for k in FORBIDDEN_CLASSES}
    for name in sorted(members):
        klass = classify_forbidden(name)
        if klass:
            per_class[klass].append(name)
    for klass in sorted(per_class):
        hits = per_class[klass]
        print(
            f"  {klass:<11} patterns={len(FORBIDDEN_CLASSES[klass]):<3} hits={len(hits)}"
            + (f"  {hits}" if hits else "")
        )
        if hits:
            problems.append(
                f"forbidden class {klass} matched {len(hits)} member(s): {hits}"
            )

    print("\n--- EXPLICIT ABSENCE CHECKS (the spec's named prohibitions) ---")
    checks = {
        "no .git member": not any(".git" in m.split("/") for m in members),
        "no __pycache__ / .pyc member": not any(
            m.endswith(".pyc") or "__pycache__" in m.split("/") for m in members
        ),
        "no node_modules member": not any(
            "node_modules" in m.split("/") for m in members
        ),
        "no .log member": not any(m.endswith(".log") for m in members),
        "no .jsonl transcript member": not any(m.endswith(".jsonl") for m in members),
        "no .env / key / credential member": not any(
            m.endswith((".env", ".pem", ".key", ".pfx", ".p12"))
            or "credential" in m.lower()
            for m in members
        ),
        "no nested archive member": not any(
            m.endswith((".zip", ".tar", ".tar.gz", ".tgz", ".7z")) for m in members
        ),
        "no test module shipped": not any(
            Path(m).name.startswith("test_") for m in members
        ),
        f"archive under budget ({MAX_BYTES:,} B)": size < MAX_BYTES,
        f"member count under budget ({MAX_FILES})": len(members) <= MAX_FILES,
    }
    for label, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            problems.append(f"absence check failed: {label}")

    print(
        "\n--- CREDENTIAL-SHAPE SCAN over every member (shapes only, never values) ---"
    )
    blocking = 0
    advisory = 0
    with tempfile.TemporaryDirectory() as td:
        for name, blob in sorted(blobs.items()):
            probe = Path(td) / "member.bin"
            probe.write_bytes(blob)
            for finding in scan_secrets(probe, name):
                if finding.severity == "blocking":
                    blocking += 1
                    print(
                        f"  BLOCKING {name}:{finding.line} rule={finding.rule} {finding.excerpt_shape}"
                    )
                elif finding.severity == "advisory":
                    advisory += 1
    print(f"  members scanned={len(blobs)}  blocking={blocking}  advisory={advisory}")
    if blocking:
        problems.append(f"{blocking} blocking credential finding(s) inside the package")

    doc = {
        "artifact": "package-measurement",
        "package": str(archive),
        "archive_bytes": size,
        "archive_sha256": sha,
        "member_count": len(members),
        "uncompressed_bytes": sum(members.values()),
        "budget": {"max_bytes": MAX_BYTES, "max_files": MAX_FILES},
        "members": [{"path": n, "bytes": members[n]} for n in sorted(members)],
        "detector_control": {
            k: classify_forbidden(v) for k, v in sorted(CONTROL_PATHS.items())
        },
        "detector_control_valid": control_ok,
        "forbidden_hits": {k: v for k, v in sorted(per_class.items())},
        "absence_checks": checks,
        "credential_scan": {
            "scanned": len(blobs),
            "blocking": blocking,
            "advisory": advisory,
        },
        "problems": problems,
    }
    if args.json:
        target = args.json
        if str(target) == "-":
            print(json.dumps(doc, indent=2, sort_keys=True))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(doc, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    print("\n" + "=" * 78)
    if problems:
        for p in problems:
            print(f"  ! {p}")
        print(f"FAILED:measure-package {len(problems)} problem(s)")
    else:
        print(
            "SUCCESS:measure-package no forbidden content, within budget, no credential findings"
        )
    if tmp is not None:
        tmp.cleanup()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
