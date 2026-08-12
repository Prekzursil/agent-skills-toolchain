#!/usr/bin/env python3
"""Test suite for ``workflow_lint.py`` -- the saved-Workflow static linter.

Stdlib-only and location-independent: it imports the module by basename (pytest's
default ``prepend`` import mode puts this file's directory on ``sys.path``), so the
byte-identical copy under both dual-write roots (``skills/`` and ``.agents/skills/``)
passes unchanged. Runnable two ways::

    pytest test_workflow_lint.py            # the CI gate (full suite, incl. tmp_path tests)
    python test_workflow_lint.py            # convenience: the no-fixture subset only

The suite is written to exercise every branch of ``workflow_lint`` (the CI lane runs
it under ``--cov-branch --cov-fail-under=100``); each assertion checks real linter
behaviour, never a tautology.
"""

from __future__ import annotations

import io
import json
import pathlib
import re
from contextlib import redirect_stderr, redirect_stdout

import workflow_lint as wl

# --------------------------------------------------------------------------- #
# Minimal well-formed workflow used as a clean baseline. It carries a pure-literal
# meta, no banned non-determinism, a schema on the agent fan-in, an args parse-if-
# string guard, and a null-tolerant parallel barrier -- so a correct linter reports
# ZERO findings on it. Each dirty case below mutates exactly one property.
# --------------------------------------------------------------------------- #
CLEAN = """\
export const meta = {
  name: 'clean-wf',
  description: 'a clean baseline workflow',
  phases: [{ title: 'One' }, { title: 'Two' }],
}

const parsed = typeof args === 'string' ? JSON.parse(args) : args
phase('One')
const SCHEMA = { type: 'object', additionalProperties: false, required: ['answer'] }
const one = await agent('do a thing for ' + parsed.topic, { label: 'one', schema: SCHEMA })
const many = (
  await parallel(items.map((it) => () => withTimeout(() => agent(it, { schema: SCHEMA }), 600000, it)))
).filter(Boolean)
return { one, many }
"""


# --------------------------------------------------------------------------- #
# mask_code
# --------------------------------------------------------------------------- #
def test_mask_preserves_length_and_newlines():
    src = "const a = 1 // note\n/* b\n c */ const d = 2\n"
    masked = wl.mask_code(src)
    assert len(masked) == len(src)
    assert masked.count("\n") == src.count("\n")


def test_mask_blanks_line_comment_but_keeps_code():
    masked = wl.mask_code("x = Date.now() // Date.now() here is a comment\n")
    # the real call survives; the one inside the comment is blanked away
    assert masked.count("Date.now") == 1


def test_mask_blanks_block_comment_including_delimiters():
    masked = wl.mask_code("a /* Math.random() */ b")
    assert "Math.random" not in masked
    assert masked.startswith("a ")
    assert masked.rstrip().endswith("b")


def test_mask_unterminated_block_comment_runs_to_eof():
    masked = wl.mask_code("a /* unterminated Date.now()")
    assert "Date.now" not in masked
    assert len(masked) == len("a /* unterminated Date.now()")


def test_mask_blanks_single_and_double_quoted_strings():
    masked = wl.mask_code("const s = 'Date.now()' + \"Math.random()\"")
    assert "Date.now" not in masked
    assert "Math.random" not in masked
    # the delimiters themselves are preserved so bracket balancing still works
    assert masked.count("'") == 2
    assert masked.count('"') == 2


def test_mask_string_escape_is_consumed():
    # the escaped quote must NOT close the string, so the trailing code is still code
    masked = wl.mask_code("s = 'a\\'b' ; y = 1")
    assert "y = 1" in masked


def test_mask_string_escaped_newline_preserves_line_count():
    src = '"a\\\nb"'
    masked = wl.mask_code(src)
    assert masked.count("\n") == 1
    assert len(masked) == len(src)


def test_mask_string_backslash_at_eof():
    masked = wl.mask_code("'a\\")
    assert len(masked) == len("'a\\")


def test_mask_raw_newline_inside_string_is_preserved():
    # malformed (unterminated) string spanning a newline: mask tolerates it
    masked = wl.mask_code("'a\nb")
    assert masked.count("\n") == 1


def test_mask_template_blanks_literal_text_only():
    masked = wl.mask_code("const t = `hello Date.now() ${x}`")
    # literal text is blanked...
    assert "hello" not in masked
    # ...but the ${} interpolation interior is preserved as code
    assert "x" in masked


def test_mask_template_preserves_interpolation_code():
    masked = wl.mask_code("const t = `x ${Date.now()} y`")
    # a banned call hidden in an interpolation is still visible to the checks
    assert "Date.now" in masked


def test_mask_template_interpolation_with_nested_braces():
    masked = wl.mask_code("const t = `${ {a: 1}.a } tail`")
    assert masked.count("\n") == 0
    # nested object braces do not end the interpolation early: 'tail' stays blanked
    assert "tail" not in masked


def test_mask_template_escape_inside():
    masked = wl.mask_code("`a\\`b`")
    assert len(masked) == len("`a\\`b`")


def test_mask_unterminated_template_runs_to_eof():
    masked = wl.mask_code("`open ${x}")
    assert len(masked) == len("`open ${x}")


# --------------------------------------------------------------------------- #
# meta checks
# --------------------------------------------------------------------------- #
def test_meta_missing_is_error():
    findings = wl.lint_text("phase('x')\nreturn {}\n")
    metas = [f for f in findings if f.check == "meta-missing"]
    assert len(metas) == 1
    assert metas[0].level == wl.ERROR
    assert metas[0].line == 1


def test_meta_in_comment_does_not_count():
    # an `export const meta` that only appears in a comment is still "missing"
    findings = wl.lint_text("// export const meta = { name: 'x' }\nreturn {}\n")
    assert any(f.check == "meta-missing" for f in findings)


def test_meta_pure_literal_passes():
    src = (
        "export const meta = {\n"
        "  name: 'ok',\n"
        "  description: 'd',\n"
        "  phases: [{ title: 'a', detail: 'x' }, { title: 'b' }],\n"
        "  nested: { deep: [1, 2, 3], flag: true, none: null, f: false },\n"
        "}\n"
    )
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_quoted_keys_pass():
    findings = wl.lint_text("export const meta = { 'name': 'x', \"d\": 'y' }\n")
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_number_forms_pass():
    findings = wl.lint_text(
        "export const meta = { a: 1, b: -2.5, c: 0xff, d: 1e3, e: 10n }\n"
    )
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_computed_field_is_not_literal():
    findings = wl.lint_text("export const meta = { name: buildName() }\n")
    m = [f for f in findings if f.check == "meta-not-literal"]
    assert len(m) == 1
    assert m[0].level == wl.ERROR


def test_meta_date_now_field_is_not_literal():
    findings = wl.lint_text("export const meta = { name: 'x', ts: Date.now() }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_computed_key_is_not_literal():
    findings = wl.lint_text("export const meta = { ['k' + 'e']: 'v' }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_template_interpolation_value_is_not_literal():
    findings = wl.lint_text("export const meta = { name: `wf-${id}` }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_spread_is_not_literal():
    findings = wl.lint_text("export const meta = { ...base, name: 'x' }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_method_shorthand_is_not_literal():
    findings = wl.lint_text("export const meta = { name() { return 1 } }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_missing_colon_is_not_literal():
    findings = wl.lint_text("export const meta = { name 'x' }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_bad_separator_is_not_literal():
    findings = wl.lint_text("export const meta = { a: 1 b: 2 }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_unterminated_object_is_not_literal():
    findings = wl.lint_text("export const meta = { a: 1,")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_identifier_value_is_not_object():
    findings = wl.lint_text("export const meta = buildMeta\n")
    assert any(f.check == "meta-not-object" for f in findings)


def test_meta_string_value_is_not_object():
    findings = wl.lint_text("export const meta = 'not an object'\n")
    assert any(f.check == "meta-not-object" for f in findings)


def test_meta_empty_after_equals_is_not_object():
    findings = wl.lint_text("export const meta = ")
    assert any(f.check == "meta-not-object" for f in findings)


def test_meta_unterminated_comment_after_equals_is_not_literal():
    findings = wl.lint_text("export const meta = /* oops")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_line_number_points_at_offending_token():
    src = "export const meta = {\n  name: 'x',\n  ts: Date.now(),\n}\n"
    findings = wl.lint_text(src)
    m = [f for f in findings if f.check == "meta-not-literal"][0]
    assert m.line == 3


def test_meta_comment_between_members_ok():
    findings = wl.lint_text(
        "export const meta = { name: 'x', /* c */ description: 'y' }\n"
    )
    assert not [f for f in findings if f.check.startswith("meta-")]


# --------------------------------------------------------------------------- #
# banned non-determinism (hard fails)
# --------------------------------------------------------------------------- #
def test_date_now_is_error():
    findings = wl.lint_text(CLEAN + "const t = Date.now()\n")
    d = [f for f in findings if f.check == "no-date-now"]
    assert len(d) == 1
    assert d[0].level == wl.ERROR


def test_math_random_is_error():
    findings = wl.lint_text(CLEAN + "const r = Math.random()\n")
    assert any(f.check == "no-math-random" and f.level == wl.ERROR for f in findings)


def test_math_round_is_not_flagged():
    findings = wl.lint_text(CLEAN + "const r = Math.round(1.4)\n")
    assert not [f for f in findings if f.check == "no-math-random"]


def test_argless_new_date_is_error():
    findings = wl.lint_text(CLEAN + "const d = new Date()\n")
    assert any(
        f.check == "no-argless-new-date" and f.level == wl.ERROR for f in findings
    )


def test_new_date_with_arg_is_allowed():
    findings = wl.lint_text(CLEAN + "const d = new Date(0)\n")
    assert not [f for f in findings if f.check == "no-argless-new-date"]


def test_banned_calls_ignored_in_strings_and_comments():
    src = CLEAN + "const s = 'Date.now()' // Math.random() and new Date()\n"
    findings = wl.lint_text(src)
    assert not [
        f
        for f in findings
        if f.check in {"no-date-now", "no-math-random", "no-argless-new-date"}
    ]


# --------------------------------------------------------------------------- #
# args-unguarded guard (warn)
# --------------------------------------------------------------------------- #
def test_args_without_guard_warns():
    src = "export const meta = { name: 'x' }\nconst t = args.topic\n"
    findings = wl.lint_text(src)
    a = [f for f in findings if f.check == "args-unguarded"]
    assert len(a) == 1
    assert a[0].level == wl.WARN
    assert a[0].line == 2


def test_args_json_parse_guard_suppresses_warning():
    src = "export const meta = { name: 'x' }\nconst p = JSON.parse(args)\nconst t = p.topic\nconst u = args.other\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-unguarded"]


def test_args_typeof_guard_suppresses_warning():
    src = "export const meta = { name: 'x' }\nconst p = typeof args === 'string' ? JSON.parse(args) : args\nconst t = args.topic\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-unguarded"]


def test_args_string_method_access_not_flagged():
    src = "export const meta = { name: 'x' }\nconst parts = args.split(' ')\nconst n = args.length\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-unguarded"]


def test_args_multiple_fields_deduped_by_line():
    src = "export const meta = { name: 'x' }\nconst t = args.a + args.b\nconst u = args.c\n"
    findings = wl.lint_text(src)
    warns = [f for f in findings if f.check == "args-unguarded"]
    # two lines carry structured access -> two warnings (deduped per line)
    assert sorted(f.line for f in warns) == [2, 3]


# --------------------------------------------------------------------------- #
# agent() schema (warn)
# --------------------------------------------------------------------------- #
def test_agent_without_schema_warns():
    src = "export const meta = { name: 'x' }\nconst r = await agent('do it', { label: 'a' })\n"
    findings = wl.lint_text(src)
    s = [f for f in findings if f.check == "agent-schema"]
    assert len(s) == 1
    assert s[0].level == wl.WARN


def test_agent_with_schema_ok():
    src = "export const meta = { name: 'x' }\nconst r = await agent('do it', { schema: S })\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "agent-schema"]


def test_agent_prompt_only_warns():
    src = "export const meta = { name: 'x' }\nconst r = await agent('do it')\n"
    findings = wl.lint_text(src)
    assert any(f.check == "agent-schema" for f in findings)


def test_agent_word_boundary_not_matched_in_agenttype():
    # `agentType` and `myagent(` must not be read as an `agent(` call
    src = "export const meta = { name: 'x' }\nconst o = { agentType: 'codex' }\nconst z = myagent('p')\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "agent-schema"]


def test_agent_unbalanced_is_skipped():
    # a syntactically broken call is left to a real parser; we do not crash
    src = "export const meta = { name: 'x' }\nconst r = agent('oops'\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "agent-schema"]


def test_agent_schema_in_prompt_string_does_not_count():
    # the literal word schema: inside the prompt must not satisfy the check
    src = "export const meta = { name: 'x' }\nconst r = await agent('return schema: foo', { label: 'a' })\n"
    findings = wl.lint_text(src)
    assert any(f.check == "agent-schema" for f in findings)


# --------------------------------------------------------------------------- #
# parallel() filter(Boolean) (warn)
# --------------------------------------------------------------------------- #
def test_parallel_immediate_filter_ok():
    src = "export const meta = { name: 'x' }\nconst r = (await parallel(t)).filter(Boolean)\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "parallel-filter-boolean"]


def test_parallel_no_filter_warns():
    src = (
        "export const meta = { name: 'x' }\nconst r = await parallel(t)\nreturn r[0]\n"
    )
    findings = wl.lint_text(src)
    p = [f for f in findings if f.check == "parallel-filter-boolean"]
    assert len(p) == 1
    assert p[0].level == wl.WARN


def test_parallel_assigned_then_chained_filter_ok():
    # the rtv-pdr pattern: const raw = await parallel(...); raw.map(...).filter(Boolean)
    src = (
        "export const meta = { name: 'x' }\n"
        "const raw = await parallel(thunks)\n"
        "const survivors = raw.map((s, i) => s ? { id: i, s } : null).filter(Boolean)\n"
    )
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "parallel-filter-boolean"]


def test_parallel_assigned_no_filter_anywhere_warns():
    src = (
        "export const meta = { name: 'x' }\n"
        "const raw = await parallel(thunks)\n"
        "const first = raw[0]\n"
    )
    findings = wl.lint_text(src)
    assert any(f.check == "parallel-filter-boolean" for f in findings)


def test_parallel_let_binding_chained_filter_ok():
    src = (
        "export const meta = { name: 'x' }\n"
        "let raw = await parallel(thunks)\n"
        "const ok = raw.filter(Boolean)\n"
    )
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "parallel-filter-boolean"]


def test_parallel_unbalanced_is_skipped():
    src = "export const meta = { name: 'x' }\nconst r = await parallel(t\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "parallel-filter-boolean"]


def test_parallel_bare_call_without_assignment_warns():
    src = "export const meta = { name: 'x' }\nawait parallel(thunks)\n"
    findings = wl.lint_text(src)
    assert any(f.check == "parallel-filter-boolean" for f in findings)


# --------------------------------------------------------------------------- #
# clean baseline
# --------------------------------------------------------------------------- #
def test_clean_workflow_has_no_findings():
    assert wl.lint_text(CLEAN) == []


# --------------------------------------------------------------------------- #
# Finding / formatting
# --------------------------------------------------------------------------- #
def test_format_finding_shape():
    f = wl.Finding("wf.mjs", 12, wl.ERROR, "no-date-now", "banned")
    assert wl.format_finding(f) == "wf.mjs:12: ERROR[no-date-now]: banned"


def test_findings_are_sorted_by_line_then_check():
    src = "export const meta = { name: 'x' }\nconst a = args.z\nconst b = Date.now()\n"
    findings = wl.lint_text(src)
    keys = [(f.line, f.check) for f in findings]
    assert keys == sorted(keys)


# --------------------------------------------------------------------------- #
# lint_file + file/dir walking
# --------------------------------------------------------------------------- #
def test_lint_file_reads_and_lints(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(CLEAN + "const t = Date.now()\n", encoding="utf-8")
    findings = wl.lint_file(p)
    assert any(f.check == "no-date-now" for f in findings)
    assert all(f.path == str(p) for f in findings)


def test_lint_file_missing_is_read_error(tmp_path):
    p = tmp_path / "nope.mjs"
    findings = wl.lint_file(p)
    assert len(findings) == 1
    assert findings[0].check == "read-error"
    assert findings[0].level == wl.ERROR


def test_lint_file_non_utf8_is_read_error(tmp_path):
    p = tmp_path / "bad.mjs"
    p.write_bytes(b"\xff\xfe export const meta = {}")
    findings = wl.lint_file(p)
    assert findings[0].check == "read-error"


def test_iter_workflow_files_expands_dir(tmp_path):
    (tmp_path / "a.js").write_text("//a", encoding="utf-8")
    (tmp_path / "b.mjs").write_text("//b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("//c", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.js").write_text("//d", encoding="utf-8")
    found = {p.name for p in wl.iter_workflow_files([str(tmp_path)])}
    assert found == {"a.js", "b.mjs", "d.js"}


def test_iter_workflow_files_keeps_explicit_file(tmp_path):
    p = tmp_path / "explicit.txt"
    p.write_text("x", encoding="utf-8")
    found = wl.iter_workflow_files([str(p)])
    assert [q.name for q in found] == ["explicit.txt"]


def test_iter_workflow_files_nonexistent_kept_for_read_error(tmp_path):
    missing = tmp_path / "ghost.mjs"
    found = wl.iter_workflow_files([str(missing)])
    assert [q.name for q in found] == ["ghost.mjs"]


def test_iter_workflow_files_dedups_and_sorts(tmp_path):
    (tmp_path / "a.js").write_text("//a", encoding="utf-8")
    (tmp_path / "b.js").write_text("//b", encoding="utf-8")
    found = wl.iter_workflow_files([str(tmp_path), str(tmp_path)])
    names = [p.name for p in found]
    assert names == ["a.js", "b.js"]


# --------------------------------------------------------------------------- #
# main / CLI
# --------------------------------------------------------------------------- #
def _run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = wl.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_clean_returns_zero(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(CLEAN, encoding="utf-8")
    code, out, err = _run_main([str(p)])
    assert code == 0
    assert "0 error" in err


def test_main_hard_fail_returns_one(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(CLEAN + "const t = Date.now()\n", encoding="utf-8")
    code, out, err = _run_main([str(p)])
    assert code == 1
    assert "ERROR[no-date-now]" in out


def test_main_warnings_only_returns_zero(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(
        "export const meta = { name: 'x' }\nconst t = args.topic\n", encoding="utf-8"
    )
    code, out, err = _run_main([str(p)])
    assert code == 0
    assert "WARN[args-unguarded]" in out


def test_main_strict_fails_on_warning(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(
        "export const meta = { name: 'x' }\nconst t = args.topic\n", encoding="utf-8"
    )
    code, _out, _err = _run_main(["--strict", str(p)])
    assert code == 1


def test_main_json_output(tmp_path):
    p = tmp_path / "wf.mjs"
    p.write_text(CLEAN + "const t = Date.now()\n", encoding="utf-8")
    code, out, _err = _run_main(["--json", str(p)])
    assert code == 1
    payload = json.loads(out)
    assert any(row["check"] == "no-date-now" for row in payload)
    assert all(
        {"path", "line", "level", "check", "message"} <= row.keys() for row in payload
    )


def test_main_directory_argument(tmp_path):
    (tmp_path / "a.mjs").write_text(CLEAN, encoding="utf-8")
    (tmp_path / "b.mjs").write_text(
        CLEAN + "const r = Math.random()\n", encoding="utf-8"
    )
    code, out, _err = _run_main([str(tmp_path)])
    assert code == 1
    assert "no-math-random" in out


def test_main_empty_dir_returns_zero(tmp_path):
    code, _out, err = _run_main([str(tmp_path)])
    assert code == 0
    assert "0 file" in err


# --------------------------------------------------------------------------- #
# additional branch coverage: mask edges
# --------------------------------------------------------------------------- #
def test_mask_template_interpolation_unterminated_runs_to_eof():
    masked = wl.mask_code("`${x")  # ${ opened, never closed
    assert len(masked) == len("`${x")


def test_mask_template_backslash_at_eof():
    masked = wl.mask_code("`a\\")
    assert len(masked) == len("`a\\")


def test_mask_template_raw_newline_preserved():
    src = "`a\nb`"
    masked = wl.mask_code(src)
    assert masked.count("\n") == 1
    assert len(masked) == len(src)


# --------------------------------------------------------------------------- #
# additional branch coverage: meta literal parser edges
# --------------------------------------------------------------------------- #
def test_meta_line_comment_inside_ok():
    findings = wl.lint_text("export const meta = {\n  name: 'x' // trailing\n}\n")
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_line_comment_no_newline_is_not_literal():
    findings = wl.lint_text("export const meta = { name: 'x' //")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_string_escape_ok():
    findings = wl.lint_text("export const meta = { s: 'a\\x', name: 'y' }\n")
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_unterminated_string_is_not_literal():
    findings = wl.lint_text("export const meta = { s: 'abc")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_keyword_like_identifier_is_not_literal():
    findings = wl.lint_text("export const meta = { a: nullish }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_eof_after_colon_is_not_literal():
    findings = wl.lint_text("export const meta = { a:")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_eof_after_key_is_not_literal():
    findings = wl.lint_text("export const meta = { a")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_eof_after_value_is_not_literal():
    findings = wl.lint_text("export const meta = { a: 1")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_empty_object_ok():
    findings = wl.lint_text("export const meta = {}\n")
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_empty_array_value_ok():
    findings = wl.lint_text("export const meta = { phases: [] }\n")
    assert not [f for f in findings if f.check.startswith("meta-")]


def test_meta_array_bad_separator_is_not_literal():
    findings = wl.lint_text("export const meta = { a: [1 2] }\n")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_array_unterminated_is_not_literal():
    findings = wl.lint_text("export const meta = { a: [1,")
    assert any(f.check == "meta-not-literal" for f in findings)


def test_meta_excessive_nesting_is_not_literal():
    # a pathologically deep meta must yield a clean finding, never a RecursionError:
    # a linter must not crash on the file it is handed.
    findings = wl.lint_text("export const meta = { a: " + "[" * 150)
    assert any(f.check == "meta-not-literal" for f in findings)


# --------------------------------------------------------------------------- #
# additional branch coverage: parallel member-chain scan edges
# --------------------------------------------------------------------------- #
def test_parallel_chain_with_space_after_dot_ok():
    src = (
        "export const meta = { name: 'x' }\n"
        "const raw = await parallel(t)\n"
        "const y = raw. filter(Boolean)\n"
    )
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "parallel-filter-boolean"]


def test_parallel_chain_unbalanced_call_warns():
    src = (
        "export const meta = { name: 'x' }\n"
        "const raw = await parallel(t)\n"
        "const y = raw.map(x\n"
    )
    findings = wl.lint_text(src)
    assert any(f.check == "parallel-filter-boolean" for f in findings)


def test_parallel_var_at_eof_warns():
    src = "export const meta = { name: 'x' }\nconst raw = await parallel(t)\nreturn raw"
    findings = wl.lint_text(src)
    assert any(f.check == "parallel-filter-boolean" for f in findings)


# --------------------------------------------------------------------------- #
# templates/resume-wired-fanout.md -- the shipped resume-manifest wiring template.
#
# A template that teaches a footgun is worse than no template, so the fenced `js`
# block is gated here rather than trusted. Note the block is a WORKFLOW body: its
# top-level `return` is legal only because the runtime wraps the body, so
# `node --check` rejects it by design -- which is exactly why the template is
# markdown (matching governed-run-orchestrator.md) and is checked with the
# project's own lexical linter instead.
# --------------------------------------------------------------------------- #
_TEMPLATE = (
    pathlib.Path(__file__).resolve().parents[1] / "templates" / "resume-wired-fanout.md"
)
_JS_BLOCK = re.compile(r"\n```js\n(.*?)\n```\n", re.S)


def _template_block() -> str:
    blocks = _JS_BLOCK.findall(_TEMPLATE.read_text(encoding="utf-8"))
    assert len(blocks) == 1, f"expected exactly one ```js block, found {len(blocks)}"
    return blocks[0]


def _strip_js_comments(src: str) -> str:
    """Remove // and /* */ comments, leaving string literals intact.

    Needed because the assertions below are substring checks: without this, a token that
    appears only inside a comment satisfies a test about the CODE. Renaming a flag in the
    code while leaving its comment behind would then keep CI green.
    """
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":  # skip a string literal whole
            quote, i = c, i + 1
            out.append(quote)
            while i < n:
                if src[i] == "\\":
                    out.append(src[i : i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _template_code() -> str:
    """The template's executable code with comments removed."""
    return _strip_js_comments(_template_block())


def test_resume_template_exists_in_this_dual_write_root():
    """Resolves relative to THIS file, so both dual-write roots are covered."""
    assert _TEMPLATE.is_file(), _TEMPLATE


def test_resume_template_block_is_lint_clean():
    findings = wl.lint_text(_template_block(), str(_TEMPLATE))
    assert findings == [], [wl.format_finding(f) for f in findings]


def test_resume_template_lint_is_not_a_vacuous_pass():
    """Both-states control: the linter MUST fire on a mutated copy of the block.

    A clean verdict is only evidence if the detector can go red on this input.
    """
    mutated = _template_block().replace(
        "const HOME =", "const T = Date.now()\nconst HOME =", 1
    )
    findings = wl.lint_text(mutated, str(_TEMPLATE))
    assert any(f.check == "no-date-now" for f in findings), findings


def test_resume_template_carries_all_three_contract_touchpoints():
    """The wiring is the point; a template missing a touch-point cannot resume.

    Asserted against comment-stripped CODE: a flag named only in a comment is not wiring.
    """
    code = _template_code()
    for token in ("--next", "--mark-partial", "--mark-done", "--mark-failed", "--ids"):
        assert token in code, (
            f"{token} missing from the template CODE (comments stripped)"
        )


def test_resume_template_write_ahead_precedes_the_terminal_mark():
    """--mark-partial must be instructed BEFORE --mark-done, or nothing is recoverable.

    Ordering is a property of the CODE; comment order proves nothing about execution order.
    """
    code = _template_code()
    assert code.index("--mark-partial") < code.index("--mark-done")


def test_resume_template_declares_a_literal_work_list_and_derives_ids():
    code = _template_code()
    assert "const UNITS = [" in code
    assert "UNITS.map((u) => u.id).join(',')" in code


def test_resume_template_throws_on_a_collapsed_work_list():
    """SKILL.md rule 2 + the measured 49->1 collapse: a template must fail loudly.

    Against CODE: a `throw` shown inside a comment is an illustration, not a guard.
    """
    assert "throw new Error(" in _template_code()


def test_comment_stripper_is_not_vacuous():
    """Both-states control for _strip_js_comments itself.

    If the stripper silently returned its input, every assertion above would be exactly as
    weak as the substring checks it replaced - and would still pass. So prove it removes a
    comment, keeps code, and does not eat a `//` inside a string literal.
    """
    assert "gone" not in _strip_js_comments("const a = 1 // gone\n")
    assert "const a = 1" in _strip_js_comments("const a = 1 // gone\n")
    assert "gone" not in _strip_js_comments("/* gone */const b = 2")
    assert "https://x" in _strip_js_comments('const u = "https://x"')
    # and it must actually change the real template, or routing through it is a no-op
    assert len(_template_code()) < len(_template_block())


def test_resume_template_discloses_the_unproven_durability_half():
    """An UNVERIFIED claim must be inline in the template, not omitted."""
    block = _template_block()
    assert "UNVERIFIED" in block
    assert "page-cache" in block or "power" in block


# --------------------------------------------------------------------------- #
# NEW RULES, 2026-08-12. Every one is BOTH-STATES in a single test: a broken
# fixture that MUST produce the finding AND a fixed fixture that MUST NOT. A rule
# with only a positive fixture is half a detector
# (rules/common/single-signal-verification.md 3b). Written with plain loops rather
# than pytest.mark.parametrize so the module stays stdlib-only and `python
# test_workflow_lint.py` keeps working.
# --------------------------------------------------------------------------- #
_HEAD = "export const meta = { name: 'x' }\n"
_TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "templates"


def _checks(src: str) -> list[str]:
    return [f.check for f in wl.lint_text(_HEAD + src)]


# --- sandbox-forbidden (ERROR) ---------------------------------------------- #
def test_sandbox_forbidden_both_states():
    broken = [
        "const x = require('fs')\n",
        "const m = await import('./x.js')\n",
        "import fs from 'node:fs'\n",
        "const v = eval('1+1')\n",
        "const f = new Function('return 1')\n",
        "const p = process.env.HOME\n",
    ]
    for src in broken:
        hits = [f for f in wl.lint_text(_HEAD + src) if f.check == "sandbox-forbidden"]
        assert len(hits) == 1, (src, hits)
        assert hits[0].level == wl.ERROR, src

    fixed = [
        # the same tokens as MENTIONS -- in a comment and in a string. The mask
        # must keep them silent, else the rule is unusable on any workflow whose
        # PROMPT text discusses these APIs (use-vs-mention).
        "// do not call require() or eval() here\n",
        "const prompt = 'never use process.env or new Function()'\n",
        # near-miss identifiers must not trip the word boundaries
        "const requires = ['a']\nconst imported = 1\nconst reprocess = 2\n",
        "export const other = { a: 1 }\n",
    ]
    for src in fixed:
        assert "sandbox-forbidden" not in _checks(src), src


# --- barrier-without-timeout (WARN), design item H6 -------------------------- #
def test_barrier_without_timeout_both_states():
    bare = (
        "const r = (await parallel(u.map((x) => () => "
        "agent(x, { schema: S })))).filter(Boolean)\n"
    )
    hits = [
        f for f in wl.lint_text(_HEAD + bare) if f.check == "barrier-without-timeout"
    ]
    assert len(hits) == 1, hits
    assert hits[0].level == wl.WARN
    assert hits[0].line == 2

    fixed = [
        # withTimeout wrapper (the shipped H6 helper)
        "const r = (await parallel(u.map((x) => () => withTimeout(() => "
        "agent(x, { schema: S }), 600000, x)))).filter(Boolean)\n",
        # a hand-written Promise.race
        "const r = (await parallel(u.map((x) => () => Promise.race(["
        "agent(x, { schema: S }), t])))).filter(Boolean)\n",
        # settle() -- no bare barrier at all
        "const r = await settle(u.map((x) => () => agent(x, { schema: S })), 600000)\n",
        # a barrier with no agent() inside is not this rule's business
        "const r = (await parallel(u.map((x) => () => f(x)))).filter(Boolean)\n",
        # unbalanced call -> skipped, never crashes
        "const r = parallel(agent(\n",
    ]
    for src in fixed:
        assert "barrier-without-timeout" not in _checks(src), src


# --- prefer-pipeline (WARN) -------------------------------------------------- #
def test_prefer_pipeline_both_states():
    smell = (
        "const a = await parallel(f1)\n"
        "const b = a.flat().map((x) => x.id)\n"
        "const c = await parallel(b.map((x) => () => g(x)))\n"
    )
    hits = [f for f in wl.lint_text(_HEAD + smell) if f.check == "prefer-pipeline"]
    assert len(hits) == 1, hits
    assert hits[0].level == wl.WARN
    assert hits[0].line == 4

    # The runtime enumerates exactly THREE shapes where a barrier IS correct.
    # The rule must stay silent on all three, or authors will disable it.
    legitimate = [
        # 1. dedup/merge across the FULL set before expensive downstream work
        "const a = await parallel(f1)\n"
        "const b = [...new Set(a.flat())]\n"
        "const c = await parallel(b.map((x) => () => g(x)))\n",
        # 2. early-exit when the total count is zero
        "const a = await parallel(f1)\n"
        "if (a.length === 0) return 'none'\n"
        "const c = await parallel(a.map((x) => () => g(x)))\n",
        # 3. stage N's prompt references "the other findings"
        "const a = await parallel(f1)\n"
        "const ctx = a.join('|')\n"
        "const c = await parallel(a.map((x) => () => g(x, ctx)))\n",
        # a reduce-based merge is cross-item too
        "const a = await parallel(f1)\nconst b = a.reduce(r, 0)\n"
        "const c = await parallel([b])\n",
        # only ONE barrier -- nothing to compare
        "const a = await parallel(f1)\n",
        # the second barrier does not consume the first one's result
        "const a = await parallel(f1)\nconst z = 1\nconst c = await parallel(f2)\n",
        # the first barrier is not assigned to anything
        "await parallel(f1)\nconst q = 2\nconst c = await parallel(f2)\n",
        # unbalanced first barrier -> skipped
        "const a = await parallel(\nconst c = await parallel(b)\n",
    ]
    for src in legitimate:
        assert "prefer-pipeline" not in _checks(src), src


# --- budget-loop-unguarded (WARN) -------------------------------------------- #
def test_budget_loop_unguarded_both_states():
    broken = (
        "while (budget.remaining() > 50000) {\n  await agent('x', {schema: S})\n}\n"
    )
    hits = [
        f for f in wl.lint_text(_HEAD + broken) if f.check == "budget-loop-unguarded"
    ]
    assert len(hits) == 1, hits
    assert hits[0].level == wl.WARN
    assert hits[0].line == 2

    fixed = [
        "while (budget.total && budget.remaining() > 50000) {\n  f()\n}\n",
        "while (i < 3) {\n  f()\n}\n",  # no budget in the condition at all
        "while (budget.remaining\n",  # unbalanced -> skipped, never crashes
    ]
    for src in fixed:
        assert "budget-loop-unguarded" not in _checks(src), src


# --- the H6 template itself must be lint-clean ------------------------------- #
def test_h6_template_block_is_lint_clean():
    """The paste-in helper must not trip the linter that recommends it."""
    path = _TEMPLATES / "h6-timeout-heartbeat.md"
    md = path.read_text(encoding="utf-8")
    block = md[md.index("<!-- H6-BEGIN -->") : md.index("<!-- H6-END -->")]
    body = block[block.index("```js") + 5 : block.rindex("```")]
    src = _HEAD + body + "\nconst r = await settle([], 1000, [])\nreturn r.length\n"
    findings = wl.lint_text(src, str(path))
    assert findings == [], [wl.format_finding(f) for f in findings]


def test_parallel_null_typing_map_is_accepted_both_states():
    """A `.map()` that NAMES null types the drop; a `.map()` that does not, does not."""
    typed = "const r = (await parallel(t)).map((x) => (x === null ? DROP : x))\n"
    assert "parallel-filter-boolean" not in _checks(typed)

    untyped = "const r = (await parallel(t)).map((x) => x.id)\n"
    assert "parallel-filter-boolean" in _checks(untyped)

    unbalanced = "const r = (await parallel(t)).map(\n"
    assert "parallel-filter-boolean" in _checks(unbalanced)


def test_resume_template_points_at_the_h6_template():
    """The H6 pointer added to resume-wired-fanout.md must not rot silently."""
    text = (_TEMPLATES / "resume-wired-fanout.md").read_text(encoding="utf-8")
    assert "h6-timeout-heartbeat.md" in text
    assert "withTimeout(" in text


# --------------------------------------------------------------------------- #
# standalone runner -- runs the NO-FIXTURE subset only (CI runs the full suite,
# including the tmp_path tests, via pytest); it is a convenience, not the gate.
# --------------------------------------------------------------------------- #
def _standalone() -> int:
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    failures = 0
    for test in tests:
        params = list(
            getattr(test, "__code__").co_varnames[: test.__code__.co_argcount]
        )
        if params:  # tests needing a fixture (tmp_path) run only under pytest
            continue
        try:
            test()
        except AssertionError as exc:  # noqa: PERF203 - report every failure
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
        else:
            print(f"PASS  {test.__name__}")
    print(
        f"\n{'FAILURES: ' + str(failures) if failures else 'all no-fixture tests passed'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_standalone())
