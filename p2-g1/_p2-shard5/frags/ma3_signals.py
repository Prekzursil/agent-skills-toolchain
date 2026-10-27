def child_uname() -> str:
    """Family-normalized sysname from a genuinely launched child process."""
    return uname_family(child_uname_raw())


def host_signals() -> dict:
    """Two independent host signals; darwin=True only when both say Darwin.

    Compared as OS families with the raw string preserved: MSYS build
    strings (MINGW64_NT-...) and sys.platform == win32 are one family
    (Windows), so the adapter never calls its own host a disagreement.
    """
    signal1_raw = child_uname_raw()
    signal1 = uname_family(signal1_raw)
    signal2 = sys.platform
    family2 = _PLATFORM_FAMILY.get(signal2, signal2)
    agree = bool(signal1) and signal1 == family2
    return {
        "signal1_child_uname": signal1,
        "signal1_raw_uname": signal1_raw,
        "signal2_sys_platform": signal2,
        "signal2_family": family2,
        "signals_agree": agree,
        "darwin": agree and signal1 == "Darwin",
        "interpreter": sys.executable,
        "default_shell": DEFAULT_SHELL,
    }
