"""Package hygiene gate: allowlisted payload, size budget, forbidden classes."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import io
import tempfile
from pathlib import Path
from typing import Any
import zipfile

from payload_allowlist import include_globs, is_allowlisted, load_allowlist, select_pairs

HERE = Path(__file__).resolve().parent
SIZE_CEILING = 52_428_800


@dataclass
class Member:
    path: str
    is_dir: bool
    size: int


@dataclass
class PackResult:
    ok: bool
    file_count: int
    total_uncompressed_bytes: int
    size_ceiling_bytes: int
    headroom_bytes: int
    integrity_digest: str
    package_id: str
    members: list[Member]
    findings: list[str] = field(default_factory=list)
    entries: list[dict[str, Any]] = field(default_factory=list)
    top_ten_by_size: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "file_count": self.file_count,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "size_ceiling_bytes": self.size_ceiling_bytes,
            "headroom_bytes": self.headroom_bytes,
            "integrity_digest": self.integrity_digest,
            "package_id": self.package_id,
            "entries": self.entries,
            "top_ten_by_size": self.top_ten_by_size,
            "findings": list(self.findings),
        }


def load_config() -> dict[str, Any]:
    doc = load_allowlist()
    return {
        "allowlist_globs": include_globs(doc),
        "size_ceiling_bytes": int((doc.get("budget") or {}).get("max_bytes") or SIZE_CEILING),
        "doc": doc,
    }


def select_allowlisted(root: Path, globs: list[str]) -> list[tuple[str, Path]]:
    doc = load_allowlist()
    if globs:
        doc = dict(doc)
        doc["include"] = [{"glob": g} for g in globs]
    return select_pairs(root, doc)


def _pack_pairs(pairs: list[tuple[str, Path]], *, ceiling: int) -> PackResult:
    buf = io.BytesIO()
    findings: list[str] = []
    members: list[Member] = []
    total = 0
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, src in pairs:
            data = src.read_bytes()
            total += len(data)
            zf.writestr(rel, data)
            members.append(Member(rel, False, len(data)))
            if rel.endswith(".git") or "/.git/" in rel or rel.startswith(".git/"):
                findings.append(f"git:{rel}")
            if rel.endswith(".log") or "transcript" in rel.lower():
                findings.append(f"log:{rel}")
            low = rel.lower()
            if "credential" in low or "password" in low or low.endswith(".pem"):
                findings.append(f"credential-name:{rel}")
    digest = hashlib.sha256(buf.getvalue()).hexdigest()
    if total > ceiling:
        findings.append("size-budget")
    entries = [{"path": m.path, "bytes": m.size} for m in members]
    top = sorted(entries, key=lambda e: e["bytes"], reverse=True)[:10]
    return PackResult(
        ok=not findings,
        file_count=len(members),
        total_uncompressed_bytes=total,
        size_ceiling_bytes=ceiling,
        headroom_bytes=ceiling - total,
        integrity_digest=digest,
        package_id=digest[:16],
        members=members,
        findings=findings,
        entries=entries,
        top_ten_by_size=top,
    )


def pack_current_worktree(root: Path) -> PackResult:
    cfg = load_config()
    pairs = select_allowlisted(root, cfg["allowlist_globs"])
    return _pack_pairs(pairs, ceiling=cfg["size_ceiling_bytes"])


def test_clean_package_passes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ph-clean-") as tmp:
        root = Path(tmp)
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (root / "README.md").write_text("# demo\n", encoding="utf-8")
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        pairs = [
            ("LICENSE", root / "LICENSE"),
            ("README.md", root / "README.md"),
            (".claude-plugin/plugin.json", root / ".claude-plugin" / "plugin.json"),
        ]
        packed = _pack_pairs(pairs, ceiling=SIZE_CEILING)
        return {
            "pass": packed.ok,
            "gate_ok": packed.ok,
            "file_count": packed.file_count,
            "total_uncompressed_bytes": packed.total_uncompressed_bytes,
            "headroom_bytes": packed.headroom_bytes,
            "integrity_digest": packed.integrity_digest,
        }


def test_gate_fails_on_a_planted_dot_git() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ph-git-") as tmp:
        root = Path(tmp)
        git = root / ".git"
        git.mkdir()
        (git / "config").write_text("[core]\n", encoding="utf-8")
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        packed = _pack_pairs(
            [("LICENSE", root / "LICENSE"), (".git/config", git / "config")],
            ceiling=SIZE_CEILING,
        )
        mutant_pairs = [("LICENSE", root / "LICENSE")]
        mutant = _pack_pairs(mutant_pairs, ceiling=SIZE_CEILING)
        return {
            "pass": (not packed.ok) and mutant.ok,
            "gate_ok": packed.ok,
            "mutant_disabled_git_rule_ok": mutant.ok,
            "findings": packed.findings,
        }


def test_gate_fails_above_the_size_budget() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ph-size-") as tmp:
        root = Path(tmp)
        big = root / "README.md"
        big.write_bytes(b"x" * 2000)
        over = _pack_pairs([("README.md", big)], ceiling=100)
        under = _pack_pairs([("README.md", big)], ceiling=10_000)
        return {
            "pass": (not over.ok) and under.ok,
            "gate_ok": over.ok,
            "clean_under_budget_ok": under.ok,
        }


def test_gate_fails_on_transcript_log_and_credential_names() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ph-cred-") as tmp:
        root = Path(tmp)
        log = root / "session.transcript.log"
        cred = root / "credential-store.txt"
        log.write_text("log-body-secret-should-not-leak-XYZ\n", encoding="utf-8")
        cred.write_text("password=should-not-appear\n", encoding="utf-8")
        packed = _pack_pairs(
            [("session.transcript.log", log), ("credential-store.txt", cred)],
            ceiling=SIZE_CEILING,
        )
        report = str(packed.findings)
        leaked = "password=should-not-appear" in report or "log-body-secret" in report
        return {
            "pass": (not packed.ok) and not leaked,
            "gate_ok": packed.ok,
            "credential_body_absent_from_report": not leaked,
            "findings": packed.findings,
        }
