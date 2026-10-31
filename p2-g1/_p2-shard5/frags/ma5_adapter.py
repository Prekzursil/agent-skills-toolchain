    def clear_quarantine(self, path: Path | str) -> None:
        sidecar = self.sidecar(path)
        if sidecar.exists():
            sidecar.unlink()

    def is_quarantined(self, path: Path | str) -> bool:
        return self.sidecar(path).exists()


class MacOSLaunchAdapter:
    """Spawns argv lists (never shell strings) with quarantine preflight."""

    def __init__(
        self,
        backend: SidecarXattrBackend,
        zsh_path: str | None = None,
        require_darwin: bool = False,
    ) -> None:
        self.backend = backend
        self._zsh_path = zsh_path
        self.require_darwin = require_darwin

    def zsh(self) -> Path:
        if self._zsh_path:
            return Path(self._zsh_path)
        found = shutil.which(DEFAULT_SHELL)
        return Path(found) if found else Path("/bin/zsh")

    def _preflight(self, argv: list[str]) -> None:
        if not argv:
            raise AdapterError(EMPTY_ARGV, "argv is empty; nothing to launch")
        if self.require_darwin and not host_signals()["darwin"]:
            raise AdapterError(
                MACOS_SUBSTRATE_MISSING,
                "require_darwin=True but this host's signals are not Darwin",
            )
        tool = str(argv[0])
        if not Path(tool).is_file() and shutil.which(tool) is None:
            raise AdapterError(TOOL_NOT_FOUND, f"launch tool not found: {tool}")
        for part in argv:
            candidate = Path(str(part))
            if candidate.is_file() and self.backend.is_quarantined(candidate):
                raise AdapterError(
                    QUARANTINE_BLOCKED,
                    f"{QUARANTINE_ATTR} present on {candidate.name}; clear it before launch",
                )
