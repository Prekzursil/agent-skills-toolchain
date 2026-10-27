def _copy_flagset(flags: dict) -> dict:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in flags.items()}


def flagset(kind: str | None = None) -> dict:
    """BSD or GNU userland flags; kind=None selects from the measured host."""
    if kind is None:
        kind = "bsd" if host_signals()["darwin"] else "gnu"
    if kind == "bsd":
        return _copy_flagset(_BSD_FLAGS)
    if kind == "gnu":
        return _copy_flagset(_GNU_FLAGS)
    raise AdapterError(TOOL_NOT_FOUND, f"unknown flagset kind: {kind!r}")


def flags_differ() -> bool:
    return _BSD_FLAGS["sed_inplace"] != _GNU_FLAGS["sed_inplace"]


class SidecarXattrBackend:
    """Quarantine emulation: the xattr lives in a sidecar file next to the
    payload, so the both-states control is executable where real
    com.apple.quarantine xattrs do not exist."""

    name = "sidecar-xattr"

    def sidecar(self, path: Path | str) -> Path:
        p = Path(path)
        return p.with_name(p.name + ".quarantine-xattr")

    def set_quarantine(self, path: Path | str, value: str = "0083;imp0014;fixture") -> None:
        self.sidecar(path).write_text(
            f"{QUARANTINE_ATTR}={value}\n", encoding="utf-8"
        )
