"""The config layer: a rail is a TOML row, and a bad row fails at LOAD, not at dispatch."""

from __future__ import annotations

import pytest
from agentspec.argv import PROMPT_TRANSPORTS, WINDOWS_CMDLINE_CAP

from agentrail.rails import (
    NATIVE_TRANSPORTS,
    ConfigError,
    RailRow,
    expand_rows,
    load_rows,
    row_by_name,
    verified_names,
)

MINIMAL = """
config_version = "1"

[rail.demo]
exe_globs = ["/bin/demo"]
native_transport = "stdin"
receipt_format = "text"
receipt_forbidden_markers = ["in progress"]
"""


def test_load_rows_parses_a_minimal_row() -> None:
    (row,) = load_rows(MINIMAL)
    assert row.name == "demo"
    assert row.exe_globs == ("/bin/demo",)
    assert row.native_transport == "stdin"
    assert row.cap == WINDOWS_CMDLINE_CAP
    assert row.default_timeout_s == 900
    assert row.verified is False
    assert row.notes == ""
    assert row.prompt_flag is None


def test_load_rows_accepts_every_optional_key() -> None:
    text = """
config_version = "1"

[rail.full]
exe_globs = ["/a/*"]
exe_fallbacks = ["/b"]
hardening = ["--safe"]
base_flags = ["run"]
native_transport = "file"
prompt_flag = "--prompt-file"
receipt_format = "json"
receipt_required_fields = ["status"]
receipt_flag = "-o"
default_timeout_s = 42
cap = 100
verified = true
notes = "hello"
"""
    (row,) = load_rows(text)
    assert row.hardening == ("--safe",)
    assert row.base_flags == ("run",)
    assert row.receipt_flag == "-o"
    assert row.default_timeout_s == 42
    assert row.cap == 100
    assert row.verified is True
    assert row.notes == "hello"


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("this is not toml = = =", "not valid TOML"),
        ('config_version = "9"\n[rail.a]\n', "config version must be"),
        ('config_version = "1"\n', "declares no"),
        ('config_version = "1"\nrail = 3\n', "declares no"),
        ('config_version = "1"\n[rail]\n', "declares no"),
    ],
)
def test_load_rows_rejects_a_malformed_document(text: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_rows(text)


def test_load_rows_rejects_a_non_table_row() -> None:
    with pytest.raises(ConfigError, match="expected a table"):
        load_rows('config_version = "1"\n[rail]\ndemo = 3\n')


def test_load_rows_rejects_an_empty_rail_name() -> None:
    with pytest.raises(ConfigError, match="rail table name must be non-empty"):
        load_rows('config_version = "1"\n[rail.""]\n')


def _toml_escape(char: str) -> str:
    """The six characters TOML reads as a unicode escape, built without a backslash.

    Composed with :func:`chr` on purpose. ``tomllib`` REFUSES a raw control byte in a
    key, so a test that embeds one passes for the wrong reason -- the document is
    rejected before this package sees it. The ESCAPED form is accepted and decodes back
    into the control character, which is what actually reaches the rail name.
    """
    return chr(92) + f"u{ord(char):04X}"


_ESC = _toml_escape("\x1b")
_BEL = _toml_escape("\x07")


@pytest.mark.parametrize(
    "quoted_name",
    [
        "my rail",
        "my" + chr(9) + "rail",
        "rail" + _ESC + "[31m",
        _ESC + "]8;;http://evil" + _BEL + "rail",
    ],
    ids=["space", "tab", "csi-colour", "osc-8-hyperlink"],
)
def test_load_rows_rejects_a_rail_name_agentspec_could_not_render(
    quoted_name: str,
) -> None:
    """REGRESSION: the rail name is a marker id too, and it was only checked for emptiness.

    ``agentrail resolve <rail>`` renders ``SUCCESS:<name>``, and the name also parametrises the
    ``env-missing-<name>`` taxonomy code. With only the emptiness check, ``[rail."my rail"]``
    in a ``--config`` file crashed the CLI with an unenveloped ``ValueError`` -- and a
    repo-supplied config is untrusted input (AGENTS.md 9), so no malice is required.

    The last two rows use TOML's ``\\uXXXX`` KEY ESCAPE rather than a raw byte, and that is a
    measured distinction, not a stylistic one: ``tomllib`` refuses a raw ``\\x1b`` in a key
    ("Illegal character") but ACCEPTS the escaped form and hands back a real control character.
    Writing the raw byte would have produced a test that passes for the wrong reason -- TOML
    rejecting the document -- and proved nothing about this check.

    Refused at LOAD, which is this module's stated contract: "raised at LOAD time, never at
    dispatch time".
    """
    body = (
        '\nexe_globs = ["/x"]\nnative_transport = "stdin"\n'
        'receipt_format = "text"\nreceipt_forbidden_markers = ["p"]\n'
    )
    with pytest.raises(ConfigError, match="rail table name"):
        load_rows(f'config_version = "1"\n[rail."{quoted_name}"]{body}')


def test_the_hostile_rail_name_documents_reach_tomllib_intact() -> None:
    """DETECTOR CONTROL for the test above: prove TOML delivered the bad key.

    Without this, a document TOML itself rejected would make the check look like it fired.
    """
    import tomllib

    key = _ESC + "[31m"
    parsed = tomllib.loads(f'["{key}"]\nx = 1\n')
    assert list(parsed) == ["\x1b[31m"]


def test_a_rail_name_with_no_control_bytes_still_loads() -> None:
    """The control: the new check must not have banned ordinary names."""
    rows = load_rows(MINIMAL)
    assert rows[0].name == "demo"


def test_load_rows_rejects_missing_required_keys() -> None:
    with pytest.raises(ConfigError, match="missing required key"):
        load_rows('config_version = "1"\n[rail.demo]\nexe_globs = ["/x"]\n')


def test_load_rows_rejects_an_unknown_key() -> None:
    text = MINIMAL + '\nsurprise = "yes"\n'
    with pytest.raises(ConfigError, match=r"unknown key\(s\) \['surprise'\]"):
        load_rows(text)


@pytest.mark.parametrize(
    ("original", "override", "fragment"),
    [
        (
            'native_transport = "stdin"',
            'native_transport = "smoke-signal"',
            "native_transport must be one of",
        ),
        (
            'receipt_format = "text"',
            'receipt_format = "yaml"',
            "receipt_format must be one of",
        ),
    ],
)
def test_load_rows_rejects_an_unknown_enum_value(
    original: str, override: str, fragment: str
) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_rows(MINIMAL.replace(original, override))


def test_load_rows_rejects_a_row_nothing_can_resolve() -> None:
    text = MINIMAL.replace('exe_globs = ["/bin/demo"]', "")
    with pytest.raises(ConfigError, match="declare exe_globs and/or exe_fallbacks"):
        load_rows(text)


def test_load_rows_rejects_a_file_transport_without_a_prompt_flag() -> None:
    text = MINIMAL.replace('native_transport = "stdin"', 'native_transport = "file"')
    with pytest.raises(ConfigError, match="requires prompt_flag"):
        load_rows(text)


@pytest.mark.parametrize(
    "override",
    [
        'receipt_format = "json"\nreceipt_required_fields = []',
        'receipt_format = "text"\nreceipt_forbidden_markers = []',
    ],
)
def test_load_rows_rejects_a_vacuous_receipt_spec(override: str) -> None:
    """A vacuous spec silently reduces the AND-gate to 'exit 0 AND non-empty'."""
    text = MINIMAL.replace(
        'receipt_format = "text"\nreceipt_forbidden_markers = ["in progress"]', override
    )
    with pytest.raises(ConfigError, match="receipt spec is vacuous"):
        load_rows(text)


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ("native_transport = 7", "native_transport must be a string"),
        ('exe_globs = "not-a-list"', "exe_globs must be a list of strings"),
        ("exe_globs = [1, 2]", "exe_globs must be a list of strings"),
        ("default_timeout_s = true", "default_timeout_s must be an int"),
        ('default_timeout_s = "900"', "default_timeout_s must be an int"),
        ("default_timeout_s = 0", "default_timeout_s must be positive"),
        ('verified = "yes"', "verified must be a bool"),
        ("prompt_flag = 5", "prompt_flag must be a string"),
    ],
)
def test_load_rows_rejects_a_wrongly_typed_value(override: str, fragment: str) -> None:
    key = override.split(" =")[0]
    body = "\n".join(
        line for line in MINIMAL.splitlines() if not line.startswith(f"{key} =")
    )
    with pytest.raises(ConfigError, match=fragment):
        load_rows(f"{body}\n{override}\n")


def test_receipt_spec_round_trips_both_formats() -> None:
    text_row = RailRow(
        name="t", receipt_format="text", receipt_forbidden_markers=("x",)
    )
    json_row = RailRow(
        name="j", receipt_format="json", receipt_required_fields=("status",)
    )
    assert text_row.receipt_spec().forbidden_markers == ("x",)
    assert json_row.receipt_spec().required_fields == ("status",)
    assert not text_row.receipt_spec().is_vacuous()
    assert not json_row.receipt_spec().is_vacuous()


def test_rail_spec_keeps_the_prompt_flag_only_for_the_file_transport() -> None:
    row = RailRow(name="r", prompt_flag="--pf", hardening=("--safe",))
    assert row.rail_spec("exe", transport="file").prompt_flag == "--pf"
    assert row.rail_spec("exe", transport="stdin").prompt_flag is None
    assert row.rail_spec("exe", transport="file").hardening == ("--safe",)


def test_rail_spec_refuses_a_transport_outside_the_agentspec_enum() -> None:
    """The enum is agentspec's and is never widened here."""
    with pytest.raises(ConfigError, match="transport must be one of"):
        RailRow(name="r").rail_spec("exe", transport="argv")
    assert "argv" in NATIVE_TRANSPORTS
    assert "argv" not in PROMPT_TRANSPORTS


def test_expand_rows_substitutes_home_in_both_path_fields() -> None:
    row = RailRow(name="r", exe_globs=("${HOME}/a/*",), exe_fallbacks=("${HOME}/b",))
    (expanded,) = expand_rows((row,), {"HOME": "/home/me"})
    assert expanded.exe_globs == ("/home/me/a/*",)
    assert expanded.exe_fallbacks == ("/home/me/b",)


@pytest.mark.parametrize("value", ["${NOPE}/x", "$/broken"])
def test_expand_rows_refuses_an_unresolvable_variable(value: str) -> None:
    """A literal ``${HOME}`` surviving into a path would be reported as a missing exe."""
    row = RailRow(name="r", exe_globs=(value,))
    with pytest.raises(ConfigError, match="cannot expand"):
        expand_rows((row,), {"HOME": "/home/me"})


def test_row_by_name_finds_and_reports() -> None:
    rows = (RailRow(name="a"), RailRow(name="b"))
    assert row_by_name(rows, "b").name == "b"
    with pytest.raises(ConfigError, match="known rails: a, b"):
        row_by_name(rows, "c")


def test_verified_names_is_sorted_and_only_the_proven_rails() -> None:
    rows = (
        RailRow(name="z", verified=True),
        RailRow(name="a", verified=True),
        RailRow(name="m", verified=False),
    )
    assert verified_names(rows) == ("a", "z")
