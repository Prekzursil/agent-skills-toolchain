"""Windows ERROR_SHARING_VIOLATION overlay for held-handle lifecycle probes.

POSIX unlink/replace of an open file succeeds. Windows mandatory locking
raises WinError 32 and the same sequential replace leaves a mixed tree.
This overlay is the Linux-host stand-in for that Windows rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ERROR_SHARING_VIOLATION = 32


@dataclass(frozen=True)
class Locker:
    pid: int
    name: str
    kind: str  # hook | log | module


class SharingViolation(OSError):
    """Windows sharing violation (winerror=32) raised by the overlay."""

    def __init__(self, path: Path, locker: Locker):
        self.path = Path(path)
        self.locker = locker
        self.winerror = ERROR_SHARING_VIOLATION
        msg = (
            f"[WinError {ERROR_SHARING_VIOLATION}] The process cannot access "
            f"the file because it is being used by another process: '{self.path}' "
            f"(locking process pid={locker.pid} name={locker.name} kind={locker.kind})"
        )
        super().__init__(13, msg)
        self.errno = 13
        self.filename = str(self.path)


class LockedFilesError(RuntimeError):
    """Loud refuse before mutation: names the locking process id."""

    def __init__(self, command: str, held: list[tuple[str, Locker]]):
        self.command = command
        self.held = list(held)
        parts = [
            f"pid={locker.pid} name={locker.name} kind={locker.kind} path={rel}"
            for rel, locker in self.held
        ]
        self.message = (
            f"{command} refused: Windows sharing violation; locking process "
            + "; ".join(parts)
        )
        super().__init__(self.message)


def _key(path: Path) -> str:
    return Path(path).resolve().as_posix()


class WinLockFS:
    """File ops that deny overwrite/unlink of held paths (Windows share mode)."""

    def __init__(self) -> None:
        self._held: dict[str, Locker] = {}

    def hold(self, path: Path, locker: Locker) -> None:
        self._held[_key(path)] = locker

    def release(self, path: Path) -> None:
        self._held.pop(_key(path), None)

    def locker_for(self, path: Path) -> Locker | None:
        return self._held.get(_key(path))

    def is_held(self, path: Path) -> bool:
        return _key(path) in self._held

    def held_under(self, root: Path) -> list[tuple[str, Locker]]:
        root_key = _key(root)
        out: list[tuple[str, Locker]] = []
        for k, locker in sorted(self._held.items()):
            if k == root_key or k.startswith(root_key + "/"):
                rel = Path(k).relative_to(Path(root_key)).as_posix()
                out.append((rel, locker))
        return out

    def _deny_mutate(self, path: Path) -> None:
        locker = self.locker_for(path)
        if locker is not None:
            raise SharingViolation(path, locker)

    def write_bytes(self, path: Path, data: bytes) -> None:
        path = Path(path)
        if path.exists():
            self._deny_mutate(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def unlink(self, path: Path) -> None:
        path = Path(path)
        if path.exists():
            self._deny_mutate(path)
            path.unlink()

    def rename_file(self, src: Path, dst: Path) -> None:
        """Rename of a held file is allowed (FILE_SHARE_DELETE style).

        Overwriting a held destination is not.
        """
        src = Path(src)
        dst = Path(dst)
        if dst.exists():
            self._deny_mutate(dst)
        src.rename(dst)

    def rename_dir(self, src: Path, dst: Path) -> None:
        src = Path(src)
        dst = Path(dst)
        held = self.held_under(src)
        if held:
            rel, locker = held[0]
            raise SharingViolation(src / rel, locker)
        if dst.exists():
            raise FileExistsError(str(dst))
        src.rename(dst)

    def rmtree_sequential(self, root: Path) -> None:
        """Delete files in sorted order; stop at the first held path.

        Already-unlinked files stay gone: this is the half-updated P0.
        """
        root = Path(root)
        files = sorted(p for p in root.rglob("*") if p.is_file())
        for path in files:
            self.unlink(path)
        dirs = sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True)
        for d in dirs:
            try:
                d.rmdir()
            except OSError:
                pass
        try:
            root.rmdir()
        except OSError:
            pass
