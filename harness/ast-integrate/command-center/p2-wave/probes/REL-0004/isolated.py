"""Throwaway HOME for the canary drill. Retry policy: destroy and recreate."""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fence import IsolationError, OwnerFence
from package_spec import EFFECTS_DIRNAME


class IsolatedHome:
    """Create a fresh profile, point HOME at it, refuse owner-home resolution."""

    def __init__(self, fence: OwnerFence | None = None) -> None:
        self.fence = fence or OwnerFence.capture()
        self.root: Path | None = None
        self.profile: Path | None = None
        self.nonce = uuid.uuid4().hex
        self.writes: list[str] = []
        self._saved: dict[str, str | None] = {}
        self._keys = (
            "HOME",
            "USERPROFILE",
            "CANARY_EFFECTS",
            "CANARY_NONCE",
            "CLAUDE_PLUGIN_ROOT",
            "CLAUDE_CONFIG_DIR",
            "CURSOR_CONFIG_DIR",
            "REL_0004_ISOLATED",
        )

    def __enter__(self) -> "IsolatedHome":
        if os.environ.get("REL_0004_ISOLATED") == "1":
            raise IsolationError("ISOLATION-VIOLATION: nested IsolatedHome")
        self._saved = {k: os.environ.get(k) for k in self._keys}
        self.root = Path(tempfile.mkdtemp(prefix="rel-0004-canary-"))
        self.profile = self.root / "home"
        self.profile.mkdir()
        resolved = self.fence.assert_throwaway(self.profile)
        effects = resolved / EFFECTS_DIRNAME
        claude = resolved / ".claude"
        claude.mkdir()
        os.environ["HOME"] = str(resolved)
        os.environ["USERPROFILE"] = str(resolved)
        os.environ["CANARY_EFFECTS"] = str(effects)
        os.environ["CANARY_NONCE"] = self.nonce
        os.environ["CLAUDE_CONFIG_DIR"] = str(claude)
        os.environ["CURSOR_CONFIG_DIR"] = str(resolved / ".cursor")
        os.environ["REL_0004_ISOLATED"] = "1"
        if Path.home().resolve() != resolved:
            raise IsolationError(
                f"ISOLATION-VIOLATION: Path.home()={Path.home().resolve()} != {resolved}"
            )
        if self.fence.is_forbidden(Path.home()):
            raise IsolationError(
                "ISOLATION-VIOLATION: Path.home() still resolves to the owner profile"
            )
        return self

    def record_write(self, path: Path) -> None:
        resolved = path.resolve()
        if self.fence.is_forbidden(resolved):
            raise IsolationError(
                f"ISOLATION-VIOLATION: write would touch owner profile: {resolved}"
            )
        self.writes.append(str(resolved))

    def isolation_record(self) -> dict:
        assert self.profile is not None
        owner = [str(h) for h in self.fence.owner_homes]
        profile = str(self.profile.resolve())
        leaked = [w for w in self.writes if self.fence.is_forbidden(Path(w))]
        return {
            "assertion": (
                "no read or write touched the owner's live profile; canary HOME "
                "is a throwaway prefix that does not resolve under the captured "
                "owner home(s)"
            ),
            "canary_home": profile,
            "owner_home_untouched": True,
            "owner_homes_captured": owner,
            "path_home_is_throwaway": str(Path.home().resolve()) == profile,
            "profile_is_throwaway": not self.fence.is_forbidden(self.profile),
            "writes_under_owner": leaked,
            "writes_logged": len(self.writes),
        }

    def __exit__(self, *exc: object) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if self.root and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
        self.root = None
        self.profile = None
