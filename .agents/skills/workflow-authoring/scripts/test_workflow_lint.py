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
const many = (await parallel(items.map((it) => () => agent(it, { schema: SCHEMA })))).filter(Boolean)
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
# args-as-string guard (warn)
# --------------------------------------------------------------------------- #
def test_args_without_guard_warns():
    src = "export const meta = { name: 'x' }\nconst t = args.topic\n"
    findings = wl.lint_text(src)
    a = [f for f in findings if f.check == "args-parse-if-string"]
    assert len(a) == 1
    assert a[0].level == wl.WARN
    assert a[0].line == 2


def test_args_json_parse_guard_suppresses_warning():
    src = "export const meta = { name: 'x' }\nconst p = JSON.parse(args)\nconst t = p.topic\nconst u = args.other\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-parse-if-string"]


def test_args_typeof_guard_suppresses_warning():
    src = "export const meta = { name: 'x' }\nconst p = typeof args === 'string' ? JSON.parse(args) : args\nconst t = args.topic\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-parse-if-string"]


def test_args_string_method_access_not_flagged():
    src = "export const meta = { name: 'x' }\nconst parts = args.split(' ')\nconst n = args.length\n"
    findings = wl.lint_text(src)
    assert not [f for f in findings if f.check == "args-parse-if-string"]


def test_args_multiple_fields_deduped_by_line():
    src = "export const meta = { name: 'x' }\nconst t = args.a + args.b\nconst u = args.c\n"
    findings = wl.lint_text(src)
    warns = [f for f in findings if f.check == "args-parse-if-string"]
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
    assert "WARN[args-parse-if-string]" in out


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
