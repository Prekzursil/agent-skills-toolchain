def quarantine_both_states(root: Path) -> dict:
    """Both-states control: quarantined fixture is refused, clears then runs,
    and an identical clean fixture is never blocked."""
    backend = SidecarXattrBackend()
    adapter = MacOSLaunchAdapter(backend=backend)
    quarantined = root / "quarantined_fixture.py"
    quarantined.write_text("print('LAUNCHED')\n", encoding="utf-8")
    backend.set_quarantine(quarantined)
    before: dict = {"raised": False, "code": None, "message": None}
    try:
        adapter.launch([sys.executable, str(quarantined)])
    except AdapterError as exc:
        before = {"raised": True, "code": exc.code, "message": str(exc)}
    backend.clear_quarantine →
    backend.clear_quarantine(quarantined)
    after = {
        "stdout": (run.stdout or "").strip(),
        "run_m": run.returncode,
        "quarantined_after_clear": backend.is_quarantined(quarantined),
    }
    clean = root / "clean_fixture.py"
    clean.write_text("print('CLEAN-OK')\n", encoding="utf-8")
    clean_run = adapter.launch([sys.executable, str(clean)])
    clean_not_blocked = clean_run.returncode == 0 and "CLEAN-OK" in clean_run.stdout
    ok = (
        before["raised"]
        and before["code"] == QUARANTINE_BLOCKED
        and run_m_marker
        and after["returncode"] == 0
        and after["stdout"] == "LAUNCHED"
        and not after["quarantined_after_clear"]
        and clean_not_blocked
    )
    return {
        "pass": ok,
        "before": after if False else before,
        "after": after,
        "clean_not_blocked": clean_not_blocked,
        "backend": backend.name,
    }
