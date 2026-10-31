"""Tests for the foundation layers: error taxonomy, filesystem, process, logging, policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plugin import errors, fsops, logs, policy, proc
from plugin.errors import BY_CODE, TAXONOMY, PluginError

# --------------------------------------------------------------------------- taxonomy


def test_taxonomy_codes_and_exit_codes_are_unique() -> None:
    codes = [e.code for e in TAXONOMY]
    exits = [e.exit_code for e in TAXONOMY]
    assert len(set(codes)) == len(codes), (
        "a duplicate error code breaks the published contract"
    )
    assert len(set(exits)) == len(exits), (
        "two classes sharing an exit code cannot be told apart"
    )


def test_every_taxonomy_row_is_fully_populated() -> None:
    for e in TAXONOMY:
        for field in ("title", "cause", "impact", "next_command"):
            assert getattr(e, field).strip(), f"{e.code}.{field} is empty"
        assert e.fail_mode in {"fail-open", "fail-closed"}
        assert 0 <= e.exit_code <= 125


def test_every_next_command_names_a_real_cli_verb() -> None:
    from plugin.cli import build_parser

    verbs = set(build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001
    for e in TAXONOMY:
        first = e.next_command.split()
        if first[0] != "astplugin":
            continue
        if len(first) > 1 and first[1] != "--help":
            assert first[1] in verbs, (
                f"{e.code}.next_command names unknown verb {first[1]!r}"
            )


def test_unknown_code_cannot_be_raised() -> None:
    with pytest.raises(KeyError):
        PluginError("E_MADE_UP", "nope")


def test_render_carries_cause_impact_and_next_command() -> None:
    err = PluginError("E_BUDGET", "payload is 9 GB", context={"over_by": 9})
    text = err.render("build")
    assert text.startswith("FAILED:build E_BUDGET")
    for needle in (
        "what happened",
        "cause",
        "impact",
        "next command",
        "exit code",
        "over_by",
    ):
        assert needle in text
    assert err.exit_code == BY_CODE["E_BUDGET"].exit_code


# --------------------------------------------------------------------------- fsops


@pytest.mark.parametrize(
    "bad",
    [
        "../escape.txt",
        "a/../../escape.txt",
        "/absolute.txt",
        "//server/share/x.txt",
        "C:/windows/system32/x.txt",
        "nul",
        "sub/CON.txt",
        "sub/lpt1",
        "",
        " padded.txt ",
    ],
)
def test_check_relpath_rejects_unsafe_paths(bad: str) -> None:
    with pytest.raises(PluginError) as exc:
        fsops.check_relpath(bad)
    assert exc.value.code == "E_IO"


def test_check_relpath_accepts_ordinary_paths() -> None:
    assert str(fsops.check_relpath("lib/astplugin/cli.py")) == "lib/astplugin/cli.py"
    assert str(fsops.check_relpath(r"lib\astplugin\cli.py")) == "lib/astplugin/cli.py"


def test_safe_join_contains(tmp_path: Path) -> None:
    target = fsops.safe_join(tmp_path, "a/b/c.txt")
    assert target.is_relative_to(tmp_path)
    with pytest.raises(PluginError):
        fsops.safe_join(tmp_path, "../outside.txt")


def test_content_hash_is_eol_stable_but_raw_hash_is_not(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"line one\nline two\n")
    crlf.write_bytes(b"line one\r\nline two\r\n")
    assert fsops.content_hash(lf) == fsops.content_hash(crlf), (
        "EOL-normalised hashing is what stops CRLF checkouts reporting phantom drift"
    )
    assert fsops.raw_hash(lf) != fsops.raw_hash(crlf), (
        "raw_hash must stay byte-exact; if it normalised too, archive determinism would be unverifiable"
    )


def test_binary_content_is_not_eol_normalised(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"\x00\x01\r\n\x02")
    b.write_bytes(b"\x00\x01\n\x02")
    assert fsops.content_hash(a) != fsops.content_hash(b)


def test_case_collisions_finds_only_real_groups() -> None:
    assert fsops.case_collisions(["a/B.txt", "a/b.txt", "c.txt"]) == [
        ["a/B.txt", "a/b.txt"]
    ]
    assert fsops.case_collisions(["a.txt", "b.txt"]) == []


def test_atomic_write_leaves_no_partial_on_success(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "file.txt"
    fsops.atomic_write_bytes(target, b"payload")
    assert target.read_bytes() == b"payload"
    assert not list(tmp_path.glob("**/.tmp-*")), "a temp file survived the atomic write"


def test_atomic_write_text_honours_explicit_eol(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    fsops.atomic_write_text(p, "a\r\nb\n")
    assert p.read_bytes() == b"a\nb\n"
    fsops.atomic_write_text(p, "a\nb\n", eol="\r\n")
    assert p.read_bytes() == b"a\r\nb\r\n"


def test_move_dir_uses_rename_when_the_os_allows_it(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "f.txt").write_text("x", encoding="utf-8")
    strategy = fsops.move_dir(src, tmp_path / "dest")
    assert strategy == "rename"
    assert (tmp_path / "dest" / "sub" / "f.txt").read_text(encoding="utf-8") == "x"
    assert not src.exists()


def test_move_dir_falls_back_when_rename_always_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both-states control for the WinError-5 flake: with rename forced to fail, the move must
    still complete via the copy fallback (and the source must be gone afterwards)."""
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "f.txt").write_text("y", encoding="utf-8")

    def always_denied(*_a: object, **_k: object) -> None:
        raise PermissionError("[WinError 5] Access is denied (synthetic)")

    monkeypatch.setattr(fsops.os, "replace", always_denied)
    monkeypatch.setattr(fsops, "DIR_MOVE_BACKOFF", 0.0)
    strategy = fsops.move_dir(src, tmp_path / "dest")
    assert strategy == "copy-fallback"
    assert (tmp_path / "dest" / "sub" / "f.txt").read_text(encoding="utf-8") == "y"
    assert not src.exists()


def test_move_dir_reports_e_io_when_both_strategies_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    monkeypatch.setattr(
        fsops.os,
        "replace",
        lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("no")),
    )
    monkeypatch.setattr(
        fsops.shutil,
        "copytree",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")),
    )
    monkeypatch.setattr(fsops, "DIR_MOVE_BACKOFF", 0.0)
    with pytest.raises(PluginError) as exc:
        fsops.move_dir(src, tmp_path / "dest")
    assert exc.value.code == "E_IO"


def test_normalised_size_matches_shipped_bytes(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"a\nb\n")
    crlf.write_bytes(b"a\r\nb\r\n")
    assert fsops.normalised_size(lf) == fsops.normalised_size(crlf) == 4
    assert crlf.stat().st_size == 6, (
        "the raw size differs; that is exactly why st_size is unusable"
    )


def test_extended_path_only_kicks_in_when_long() -> None:
    short = Path("C:/short/path.txt")
    assert fsops.extended(short) == short
    long = Path("C:/" + ("x" * 20 + "/") * 15 + "f.txt")
    got = str(fsops.extended(long))
    if fsops.os.name == "nt":  # type: ignore[attr-defined]
        assert got.startswith("\\\\?\\")
    else:
        assert got == str(long)


# --------------------------------------------------------------------------- proc


def test_run_refuses_a_command_string() -> None:
    with pytest.raises(PluginError) as exc:
        proc.run("echo hi")  # type: ignore[arg-type]
    assert exc.value.code == "E_USAGE"


def test_run_refuses_non_string_argv() -> None:
    with pytest.raises(PluginError):
        proc.run([1, 2])  # type: ignore[list-item]


def test_run_executes_an_argv_array() -> None:
    import sys

    res = proc.run([sys.executable, "-c", "print('ok')"])
    assert res.ok and res.stdout.strip() == "ok"


def test_python3_interpreter_probe_finds_this_interpreter() -> None:
    p = proc.probe_interpreter("python3")
    assert p.found and p.meets_floor, f"python3 probe failed: {p.as_dict()}"


def test_undeclared_interpreter_probe_reports_not_declared() -> None:
    p = proc.probe_interpreter("cobol")
    assert not p.found and "not declared" in p.detail


def test_require_interpreter_raises_for_missing() -> None:
    with pytest.raises(PluginError) as exc:
        proc.require_interpreter("cobol")
    assert exc.value.code == "E_INTERP"


@pytest.mark.parametrize("os_name", [proc.OS_WINDOWS, proc.OS_MACOS, proc.OS_LINUX])
def test_launch_adapter_resolves_on_every_os(os_name: str) -> None:
    argv = proc.launch_argv(
        "python3", Path("bin/astplugin.py"), ["health-check"], os_name=os_name
    )
    assert isinstance(argv, list) and len(argv) >= 3
    assert argv[-2:] == [
        "bin\\astplugin.py" if proc.os.sep == "\\" else "bin/astplugin.py",
        "health-check",
    ]


def test_pwsh_adapter_injects_the_file_flag() -> None:
    argv = proc.launch_argv("pwsh", Path("s.ps1"), [], os_name=proc.OS_WINDOWS)
    assert "-File" in argv and "-NoProfile" in argv


def test_launch_adapter_rejects_an_undeclared_interpreter() -> None:
    with pytest.raises(PluginError) as exc:
        proc.launch_argv("cobol", Path("x"), [], os_name=proc.OS_LINUX)
    assert exc.value.code == "E_INTERP"


def test_marshal_args_spills_only_when_over_budget(tmp_path: Path) -> None:
    small = proc.marshal_args(["tool"], "tiny", tmp_path, flag="--prompt")
    assert small == ["tool", "--prompt", "tiny"]
    big = proc.marshal_args(
        ["tool"], "x" * (proc.ARG_BUDGET + 1), tmp_path, flag="--prompt"
    )
    assert big[1] == "--prompt-file" and Path(big[2]).exists()


def test_pathconv_suppression_is_scoped_to_revision_shaped_args() -> None:
    assert proc._needs_pathconv_suppression(["git", "show", "origin/main:x.py"])  # noqa: SLF001
    assert not proc._needs_pathconv_suppression(["git", "status"])  # noqa: SLF001


# --------------------------------------------------------------------------- logs


def test_redaction_denies_by_default_on_key_name() -> None:
    out = logs.redact({"password": "hunter2", "note": "fine"})
    assert out["password"] == "<redacted:key-name>"
    assert out["note"] == "fine"


def test_redaction_catches_a_shaped_token_in_free_text() -> None:
    sample = "authorization header: ghp_" + "a" * 40
    out = logs.redact_text(sample)
    assert "ghp_" not in out and "<redacted:" in out


def test_redaction_recurses_into_nested_structures() -> None:
    out = logs.redact({"a": [{"secret": "x" * 40}], "b": {"c": "ok"}})
    assert out["a"][0]["secret"] == "<redacted:key-name>"
    assert out["b"]["c"] == "ok"


def test_logger_writes_redacted_jsonl_and_rotates(tmp_path: Path) -> None:
    log = logs.Logger(tmp_path / "p.log", max_bytes=512, keep=2)
    log.info("install", "started", password="hunter2")
    for i in range(200):
        log.info("install", "step", index=i, note="x" * 40)
    records = log.read()
    assert records, "no records were written"
    assert all(
        r["fields"].get("password", "<redacted:key-name>") == "<redacted:key-name>"
        for r in records
    )
    assert (tmp_path / "p.log.1").exists(), (
        "rotation never fired despite exceeding max_bytes"
    )
    for line in (tmp_path / "p.log").read_text(encoding="utf-8").splitlines():
        assert "hunter2" not in line


def test_logger_rejects_an_unknown_level(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown log level"):
        logs.Logger(tmp_path / "p.log").log("trace", "op", "event")


# --------------------------------------------------------------------------- policy


def test_failure_policy_agrees_with_the_error_taxonomy() -> None:
    assert policy.policy_taxonomy_agreement() == []


def test_exactly_one_component_is_fail_open_and_says_why() -> None:
    open_rules = [r for r in policy.FAILURE_RULES if r.mode == "fail-open"]
    assert [r.component for r in open_rules] == ["cache"]
    assert "accelerator" in open_rules[0].reason


def test_exec_policy_forbids_credential_reads_everywhere() -> None:
    doc = policy.exec_policy_document()
    assert doc["install_runs_shipped_code"] is False
    assert all(r["credential_read_allowed"] is False for r in doc["rules"])  # type: ignore[index]


def test_taxonomy_document_round_trips_as_json() -> None:
    doc = errors.taxonomy_document()
    assert json.loads(json.dumps(doc))["classes"][0]["code"].startswith("E_")
