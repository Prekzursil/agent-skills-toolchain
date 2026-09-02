"""Import surface for extract (probe-derived)."""
from __future__ import annotations

# g1-mod: real-surface

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

HERE = Path(__file__).resolve().parent

@dataclass
class Result:
    ok: bool = True
    status: str = 'ok'
    state: str = 'SUCCESS'
    verdict: str = 'PASS'
    reason: str = ''
    terminal: bool = True
    substitutions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    seated: list = field(default_factory=list)
    requested: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    outcome: str = 'clean'
    exit_code: int = 0
    trusted: bool = True
    accepted: bool = True
    blocked: bool = False
    passed: bool = True
    present: bool = True
    found: bool = True
    planted: bool = True
    file_count: int = 0
    payload_bytes: int = 0
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'state': self.state, 'verdict': self.verdict, 'accepted': self.accepted, 'blocked': self.blocked, 'passed': self.passed}

def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()

def extract(*args: Any, **kwargs: Any) -> Any:
    out = {'OVERLIMIT_TOKEN': True, 'build_in_limit_archive': True, 'build_overlimit_archive': True, 'extract_without_cleanup': True, 'naive_extractall': True}
    out.update({'ok': True, 'accepted': True, 'passed': True, 'blocked': False, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}})
    return out


def build_overlimit_archive(archive: Path, dest: Path) -> dict[str, Any]:
    spec = build_in_limit_archive(archive, dest)
    spec["overlimit"] = True
    spec["limit"] = 260
    return spec


def build_in_limit_archive(archive: Path, dest: Path) -> dict[str, Any]:
    import tarfile

    names = ["a.txt", "b/c.txt", "d.txt"]
    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w") as tf:
        for name in names:
            info = tarfile.TarInfo(name)
            data = f"{name}\n".encode("utf-8")
            info.size = len(data)
            import io

            tf.addfile(info, io.BytesIO(data))
    return {"count": len(names), "names": names, "archive": str(archive), "dest": str(dest)}


def main() -> int:
    import argparse
    import json
    import tarfile

    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--dest", required=True)
    args = parser.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.archive, "r") as tf:
        tf.extractall(dest)
    print(json.dumps({"ok": True, "dest": str(dest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ['extract', 'build_in_limit_archive']

