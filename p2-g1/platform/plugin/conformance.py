"""The plugin's own contract test: a conformance validator over a built package.

This validates the ARTIFACT, not the source tree. A green source tree says nothing about whether
the thing that ships is installable — that is the packaging gap that a CI-green repo hides.

Every condition is asserted POSITIVELY: the report states *N of N conditions satisfied*, and a
condition that could not be evaluated is recorded as ``NOT-CHECKED`` and counts against the total.
A report that merely says "nothing blocking" is the defect class this program has already paid for
once (a defensive ``hasattr`` swallowed an AttributeError and yielded "0/0 conditions, 0 blocking",
which an aggregate read as PASS).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError
from .fsops import hash_bytes
from .manifest import MANIFEST_RELPATH, parse as parse_manifest
from .packager import ALLOWLIST_RELPATH, INVENTORY_RELPATH, list_members, read_member
from .payload import classify_forbidden, scan_secrets
from .proc import INTERPRETERS, launch_argv

SATISFIED = "SATISFIED"
VIOLATED = "VIOLATED"
NOT_CHECKED = "NOT-CHECKED"


@dataclass
class Condition:
    ident: str
    requirement: str
    status: str
    evidence: str

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.ident,
            "requirement": self.requirement,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass
class ConformanceReport:
    package: str
    conditions: list[Condition] = field(default_factory=list)

    @property
    def satisfied(self) -> int:
        return sum(1 for c in self.conditions if c.status == SATISFIED)

    @property
    def violated(self) -> list[Condition]:
        return [c for c in self.conditions if c.status == VIOLATED]

    @property
    def not_checked(self) -> list[Condition]:
        return [c for c in self.conditions if c.status == NOT_CHECKED]

    @property
    def ok(self) -> bool:
        """Positive assertion: every declared condition must be SATISFIED. No "nothing blocking"."""
        return bool(self.conditions) and self.satisfied == len(self.conditions)

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "conformance-report",
            "package": self.package,
            "condition_count": len(self.conditions),
            "satisfied": self.satisfied,
            "violated": len(self.violated),
            "not_checked": len(self.not_checked),
            "ok": self.ok,
            "verdict": f"{self.satisfied}/{len(self.conditions)} conditions satisfied",
            "conditions": [c.as_dict() for c in self.conditions],
        }


def _add(
    report: ConformanceReport,
    ident: str,
    requirement: str,
    ok: bool | None,
    evidence: str,
) -> None:
    status = NOT_CHECKED if ok is None else (SATISFIED if ok else VIOLATED)
    report.conditions.append(Condition(ident, requirement, status, evidence))


def validate_package(archive: Path) -> ConformanceReport:
    """Run the full contract over a built package. Never raises for a violation; it reports one."""
    report = ConformanceReport(package=str(archive))
    if not archive.exists():
        _add(report, "C00", "the package file exists", False, f"{archive} not found")
        return report
    _add(
        report,
        "C00",
        "the package file exists",
        True,
        f"{archive.stat().st_size} bytes",
    )

    try:
        members = list_members(archive)
    except PluginError as exc:
        _add(report, "C01", "the package is a readable archive", False, exc.detail)
        return report
    _add(
        report,
        "C01",
        "the package is a readable archive",
        True,
        f"{len(members)} members",
    )

    for ident, rel in (
        ("C02", MANIFEST_RELPATH),
        ("C03", INVENTORY_RELPATH),
        ("C04", ALLOWLIST_RELPATH),
    ):
        _add(
            report,
            ident,
            f"the package contains {rel}",
            rel in members,
            f"present={rel in members}",
        )

    manifest = None
    if MANIFEST_RELPATH in members:
        try:
            manifest = parse_manifest(
                read_member(archive, MANIFEST_RELPATH).decode("utf-8")
            )
            _add(
                report,
                "C05",
                "the manifest passes the strict parser",
                True,
                f"{manifest.name} {manifest.version}",
            )
        except PluginError as exc:
            _add(
                report,
                "C05",
                "the manifest passes the strict parser",
                False,
                exc.detail,
            )
    else:
        _add(
            report,
            "C05",
            "the manifest passes the strict parser",
            None,
            "no manifest to parse",
        )

    from .payload import FORBIDDEN_CLASSES

    forbidden = [(m, classify_forbidden(m)) for m in members]
    hits = [(m, k) for m, k in forbidden if k]
    _add(
        report,
        "C06",
        "no member belongs to a forbidden content class (.git, cache, log, transcript, credential)",
        not hits,
        f"{len(members)} members x {len(FORBIDDEN_CLASSES)} forbidden classes "
        f"({', '.join(sorted(FORBIDDEN_CLASSES))}); "
        + (f"first hit {hits[0]}" if hits else "0 hits"),
    )

    inventory: dict[str, object] = {}
    if INVENTORY_RELPATH in members:
        inventory = json.loads(read_member(archive, INVENTORY_RELPATH).decode("utf-8"))
        declared = {e["path"] for e in inventory.get("entries", [])}  # type: ignore[union-attr]
        extra_meta = {MANIFEST_RELPATH, INVENTORY_RELPATH, ALLOWLIST_RELPATH}
        undeclared = sorted(set(members) - declared - extra_meta)
        _add(
            report,
            "C07",
            "every archive member is declared in the inventory",
            not undeclared,
            f"{len(undeclared)} undeclared"
            + (f", first {undeclared[0]}" if undeclared else ""),
        )
        bad = []
        for entry in inventory.get("entries", []):  # type: ignore[union-attr]
            if entry["path"] not in members:
                bad.append(f"{entry['path']}: declared but absent")
                continue
            if hash_bytes(read_member(archive, entry["path"])) != entry["sha256"]:
                bad.append(f"{entry['path']}: hash mismatch")
        _add(
            report,
            "C08",
            "every inventory hash matches the archived bytes",
            not bad,
            f"{len(inventory.get('entries', []))} entries verified, {len(bad)} mismatch"  # type: ignore[arg-type]
            + (f", first {bad[0]}" if bad else ""),
        )
    else:
        _add(
            report,
            "C07",
            "every archive member is declared in the inventory",
            None,
            "no inventory",
        )
        _add(
            report,
            "C08",
            "every inventory hash matches the archived bytes",
            None,
            "no inventory",
        )

    if manifest is not None:
        missing_ep = [e.path for e in manifest.entrypoints if e.path not in members]
        _add(
            report,
            "C09",
            "every declared entrypoint file is present",
            not missing_ep,
            f"{len(manifest.entrypoints)} entrypoints, {len(missing_ep)} missing",
        )
        undeclared_interp = [
            e.ident
            for e in manifest.entrypoints
            if e.interpreter
            and e.interpreter not in {str(i["id"]) for i in manifest.interpreters}
        ]
        _add(
            report,
            "C10",
            "every entrypoint interpreter is declared in interpreters[]",
            not undeclared_interp,
            f"{len(undeclared_interp)} undeclared",
        )
        unknown_interp = [
            str(i["id"])
            for i in manifest.interpreters
            if str(i["id"]) not in INTERPRETERS
        ]
        _add(
            report,
            "C11",
            "every declared interpreter is one the launch adapters support",
            not unknown_interp,
            f"supported={sorted(INTERPRETERS)}; unknown={unknown_interp}",
        )
        adapter_failures: list[str] = []
        for os_name in manifest.platforms:
            for ep in manifest.entrypoints:
                if not ep.interpreter:
                    continue
                try:
                    argv = launch_argv(
                        ep.interpreter,
                        Path("x") / ep.path,
                        list(ep.args),
                        os_name=os_name,
                    )
                    if not argv or not isinstance(argv, list):
                        adapter_failures.append(f"{os_name}/{ep.ident}: empty argv")
                except PluginError as exc:
                    adapter_failures.append(f"{os_name}/{ep.ident}: {exc.detail}")
        _add(
            report,
            "C12",
            "a launch adapter resolves for every entrypoint on every declared platform",
            not adapter_failures,
            f"{len(manifest.platforms)} platforms x {len(manifest.entrypoints)} entrypoints; "
            f"{len(adapter_failures)} failures",
        )
        budget_ok = True
        detail = "no budget declared"
        if manifest.payload_max_bytes or manifest.payload_max_files:
            total = int(inventory.get("total_bytes", 0)) if inventory else 0
            count = int(inventory.get("file_count", 0)) if inventory else 0
            budget_ok = (
                not manifest.payload_max_bytes or total <= manifest.payload_max_bytes
            ) and (
                not manifest.payload_max_files or count <= manifest.payload_max_files
            )
            detail = f"{total}B/{manifest.payload_max_bytes}B, {count}/{manifest.payload_max_files} files"
        _add(
            report,
            "C13",
            "the payload is within its declared size and file-count budget",
            budget_ok,
            detail,
        )
    else:
        for ident, req in (
            ("C09", "every declared entrypoint file is present"),
            ("C10", "every entrypoint interpreter is declared in interpreters[]"),
            ("C11", "every declared interpreter is one the launch adapters support"),
            (
                "C12",
                "a launch adapter resolves for every entrypoint on every declared platform",
            ),
            ("C13", "the payload is within its declared size and file-count budget"),
        ):
            _add(report, ident, req, None, "manifest did not parse")

    import tempfile

    blocking = 0
    with tempfile.TemporaryDirectory() as td:
        for m in members:
            blob = read_member(archive, m)
            tmp = Path(td) / "probe.bin"
            tmp.write_bytes(blob)
            blocking += sum(1 for f in scan_secrets(tmp, m) if f.severity == "blocking")
    _add(
        report,
        "C14",
        "no archived member carries credential-shaped content",
        blocking == 0,
        f"{len(members)} members scanned, {blocking} blocking finding(s)",
    )

    crlf = [
        m
        for m in members
        if b"\r\n" in read_member(archive, m)
        and not m.endswith((".png", ".zip", ".ico"))
    ]
    _add(
        report,
        "C15",
        "no archived text member carries CRLF (line-ending policy)",
        not crlf,
        f"{len(crlf)} CRLF member(s)" + (f", first {crlf[0]}" if crlf else ""),
    )

    return report
