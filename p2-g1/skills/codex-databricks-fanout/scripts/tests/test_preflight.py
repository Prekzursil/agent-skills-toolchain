from harness import preflight


def runner(version="0.144.6", ultra_rc=0, bogus_rc=2):
    def run(argv):
        j = " ".join(argv)
        if "--version" in j:
            return 0, f"codex-cli {version}", ""
        if 'model_reasoning_effort="ultra"' in j:
            return ultra_rc, "ok", ""
        if "model_reasoning_effort=" in j:
            return bogus_rc, "", "invalid effort"
        return 0, "", ""

    return run


def test_ready_gates_on_behavior_not_version():
    ok, ver, _ = preflight.assert_codex_ready(runner(version="0.199.0"))
    assert ok and ver == "0.199.0"  # any version accepted; version RECORDED


def test_reports_observed_version():
    ok, ver, _ = preflight.assert_codex_ready(runner(version="0.144.6"))
    assert ver == "0.144.6"


def test_not_ready_if_ultra_rejected():
    ok, _, m = preflight.assert_codex_ready(runner(ultra_rc=2))
    assert not ok and "ultra" in m.lower()


def test_not_ready_if_bogus_accepted():
    ok, _, m = preflight.assert_codex_ready(runner(bogus_rc=0))
    assert not ok and "both-states" in m.lower()


def test_not_ready_if_version_probe_itself_fails():
    # Neither pre-merge variant covered the `codex --version` rc!=0 path, so the
    # STOP-the-fan-out branch was untested; version falls back to "unknown".
    ok, ver, m = preflight.assert_codex_ready(lambda argv: (127, "", "not found"))
    assert not ok and ver == "unknown" and "--version" in m


def test_check_node_preflight_behavioral():
    ok, ver, _ = preflight.check_node_preflight(
        "codex_version: 0.144.6\nultra_rc: 0\nbogus_rc: 2\n"
    )
    assert ok and ver == "0.144.6"
    assert not preflight.check_node_preflight(
        "codex_version: 0.1\nultra_rc: 1\nbogus_rc: 2\n"
    )[0]
    assert not preflight.check_node_preflight(
        "codex_version: 0.1\nultra_rc: 0\nbogus_rc: 0\n"
    )[0]  # blind
