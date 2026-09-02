#!/usr/bin/env python3
"""Tests for the write-path secret gate in per-edit-check/check.py.

Fake credential strings are built at RUNTIME by concatenation so this test file
itself contains no literal credential shape — otherwise the per-edit-check hook
would block writing it (the gate scanning its own test data).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent


def load_check():
    spec = importlib.util.spec_from_file_location("check_mod_sec", HERE / "check.py")
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Runtime-built fakes (no literal secret shape lives in this file).
FAKE_AWS = "AKIA" + "1234567890ABCDEF"  # AKIA + 16 upper-alnum
FAKE_PEM = "-----BEGIN " + "PRIVATE KEY-----"
FAKE_PGP = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"  # real OpenPGP armor
FAKE_SK = "sk-" + "A" * 45  # >=40 chars after 'sk-' (real keys are longer)
FAKE_GH = "ghp_" + "b" * 36
FAKE_SLACK = "xoxb-" + "1234567890-abcdefghij"
FAKE_GOOGLE = "AIza" + "C" * 35
FAKE_STRIPE = "sk_live_" + "D" * 24
AWS_EXAMPLE = "AKIAIOSFODNN7" + "EXAMPLE"  # AWS docs sample → must be EXEMPT
# Redaction-fixture shape used across this repo (e.g. tools/monitorcore/tests):
# the placeholder marker lives INSIDE the token, so the gate must exempt it.
GH_FAKE_FIXTURE = "ghp_" + "FAKE" + "0" * 32


def _scan_text(mod, tmp_path, text, name="f.py"):
    fp = tmp_path / name
    fp.write_text(text, encoding="utf-8")
    return mod._scan_secrets(str(fp))


# ── high-confidence shapes block ─────────────────────────────────────────────


def test_aws_key_blocks(tmp_path):
    mod = load_check()
    msg = _scan_text(mod, tmp_path, f'aws = "{FAKE_AWS}"\n')
    assert msg and "AWS" in msg


def test_pem_header_blocks(tmp_path):
    mod = load_check()
    msg = _scan_text(mod, tmp_path, FAKE_PEM + "\n")
    assert msg and "private key" in msg.lower()


def test_openai_key_blocks(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'key = "{FAKE_SK}"\n') is not None


def test_github_token_blocks(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'tok = "{FAKE_GH}"\n') is not None


def test_slack_token_blocks(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'tok = "{FAKE_SLACK}"\n') is not None


def test_google_key_blocks(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'k = "{FAKE_GOOGLE}"\n') is not None


def test_stripe_key_blocks(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'k = "{FAKE_STRIPE}"\n') is not None


def test_pgp_armor_blocks(tmp_path):
    """Real PGP private-key armor ('PGP PRIVATE KEY BLOCK') must block (regression: dead branch)."""
    mod = load_check()
    assert _scan_text(mod, tmp_path, FAKE_PGP + "\n") is not None


def test_far_marker_still_blocks(tmp_path):
    """A real secret sharing a line with an INCIDENTAL marker >24 chars away still blocks."""
    mod = load_check()
    line = f'k = "{FAKE_AWS}"' + " " * 40 + "# example\n"
    assert _scan_text(mod, tmp_path, line) is not None


# ── exemptions / clean ───────────────────────────────────────────────────────


def test_aws_example_exempt(tmp_path):
    """The AWS docs sample (line contains EXAMPLE) must NOT block."""
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'aws = "{AWS_EXAMPLE}"\n') is None


def test_placeholder_marker_exempt(tmp_path):
    """A real-shaped key on a line marked YOUR_KEY is treated as a placeholder."""
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'API = "{FAKE_AWS}"  # YOUR_KEY\n') is None


def test_fake_redaction_fixture_exempt(tmp_path):
    """A redaction-test fixture whose token embeds FAKE must NOT block.

    Without this the gate makes the repo's own redaction fixtures un-editable
    (measured: 7 of 20 tracked-file hits were exactly this shape).
    """
    mod = load_check()
    assert _scan_text(mod, tmp_path, f'TOK = "{GH_FAKE_FIXTURE}"\n') is None


def test_clean_file_no_secret(tmp_path):
    mod = load_check()
    assert _scan_text(mod, tmp_path, "x = 1\ndef f():\n    return 42\n") is None


# ── main() integration ───────────────────────────────────────────────────────


def _run_main(mod, fp, env=None):
    old = (sys.stdin, sys.stdout, sys.stderr)
    sys.stdin = io.StringIO(
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": fp}})
    )
    out, err = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = out, err
    rc = 0
    try:
        with mock.patch.dict(os.environ, env or {}, clear=False):
            rc = mod.main()
    except SystemExit as exc:
        rc = int(exc.code) if exc.code is not None else 0
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    return rc, out.getvalue(), err.getvalue()


def test_main_blocks_secret_write(tmp_path):
    mod = load_check()
    fp = tmp_path / "config.py"
    fp.write_text(f'TOKEN = "{FAKE_AWS}"\n', encoding="utf-8")
    rc, out, err = _run_main(mod, str(fp))
    assert rc == 2, "a hardcoded-secret write must block (exit 2)"
    assert out.strip() == "", "exit 2 -> stdout clean, reason on stderr"
    # Was `assert "BLOCKED" in err`. The opener changed because it was measurably
    # false -- PostToolUse cannot prevent the write -- so the assertion moved to what
    # the reason must actually identify. See
    # test_secret_reason_does_not_claim_the_write_was_prevented for the full contract.
    assert "SECRET ON DISK" in err
    # The block reason must NEVER echo the matched bytes. This hook's stderr is
    # injected into agent context, so a reason that quotes "the offending text
    # to be helpful" would print the very credential it caught.
    assert FAKE_AWS not in err, "block reason must not echo the matched credential"


def test_secret_reason_does_not_claim_the_write_was_prevented(tmp_path):
    """The reason must not tell the reader the credential failed to land.

    Measured (B4-POSTTOOL-BLOCK.json, both halves): this hook is wired ONLY at
    PostToolUse, and in every arm -- including the one that returns 2 -- the file it
    objected to was still on disk afterwards, with the credential shape intact. The
    vendor contract says the same thing: PostToolUse runs after the tool has already
    run, so exit 2 cannot unwrite anything.

    A reason opening "BLOCKED" therefore tells an agent the opposite of what happened,
    and the agent's next move (carry on, the secret never landed) is the dangerous one.
    AGENTS.md §9b is explicit that a secret is compromised regardless of how briefly it
    was exposed, so the reason has to say the file is on disk and that the credential
    must be treated as exposed -- and, per §9, must NOT instruct anyone to rotate it.
    """
    mod = load_check()
    fp = tmp_path / "config.py"
    fp.write_text(f'TOKEN = "{FAKE_AWS}"\n', encoding="utf-8")
    rc, _out, err = _run_main(mod, str(fp))
    assert rc == 2, (
        "the secret gate still uses exit 2 -- it is the channel, not a block"
    )
    assert fp.exists(), (
        "precondition: PostToolUse cannot unwrite -- the file is on disk"
    )
    low = err.lower()
    assert "already" in low and "disk" in low, (
        "the reason must state that the file is already written, not imply prevention"
    )
    assert "exposed" in low, "the reason must tell the reader to treat it as exposed"
    assert "blocked" not in low, (
        "'BLOCKED' claims the write was prevented; PostToolUse cannot prevent it"
    )
    assert FAKE_AWS not in err, "reason must not echo the matched credential"


def test_no_inline_comment_contradicts_the_docstring_reconciliation():
    """No `Hard block` comment may survive alongside the docstring that refutes it.

    The module docstring already reconciles §6 correctly -- "exit 2 here is NOT a
    block. This is PostToolUse: the edit has already been written and nothing is
    reverted or denied". An inline comment reading `# Hard block:` teaches the next
    maintainer the opposite, in the same file, and the inline comment is the one
    sitting next to the code they are about to change.
    """
    src = Path(load_check().__file__).read_text(encoding="utf-8")
    assert "exit 2 here is NOT a block" in src, (
        "guard: this test is only meaningful while the docstring makes that claim"
    )
    assert "Hard block" not in src, (
        "an inline `Hard block` comment contradicts the docstring reconciliation"
    )


def test_main_opt_out_allows_secret(tmp_path):
    mod = load_check()
    fp = tmp_path / "config.py"
    fp.write_text(f'TOKEN = "{FAKE_AWS}"\n', encoding="utf-8")
    rc, _out, _err = _run_main(mod, str(fp), env={"PER_EDIT_SECRETS": "off"})
    assert rc != 2, "PER_EDIT_SECRETS=off must not block on secrets"
