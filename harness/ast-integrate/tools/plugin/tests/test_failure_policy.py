#!/usr/bin/env python3
"""Tests for the fail-open / fail-closed policy table (IMP-0053).

One injection per component, the negative control (a flipped declaration goes
red), the hooks fail-open-on-syntax-error case, the static no-swallow audit with
its planted both-states control, schema refusal, and the kind-only reviewer.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import failure_policy as FP  # noqa: E402
import fp_components as fpc  # noqa: E402


def test_one_injection_per_component() -> None:
    table = FP.load_table()
    outcomes = FP.inject_all(table)
    assert sorted(outcomes) == sorted(r["id"] for r in table["components"])
    assert all(o.failure for o in outcomes.values()), "every injected fault must be observed"
    FP.assert_injections_match_declarations(outcomes, table)
    specs = FP.specs_from_table(table)
    for cid, spec in specs.items():
        got = outcomes[cid]
        if spec.posture == FP.FAIL_OPEN:
            assert got.proceed and got.degraded and not got.denied, cid
        else:
            assert got.denied and not got.proceed and not got.degraded, cid
    assert len([s for s in specs.values() if s.posture == FP.FAIL_OPEN]) == 4
    assert len([s for s in specs.values() if s.posture == FP.FAIL_CLOSED]) == 7


def test_negative_control_flip_declaration_goes_red() -> None:
    table = FP.load_table()
    for cid in ("hooks", "secret_gate"):
        control = FP.negative_control_flip_goes_red(cid, table)
        assert control["green_before_flip"], control
        assert control["went_red"], control
        assert any(m.get("id") == cid for m in control["mismatches"]), control
    # A missing injection is also red: declared without injection.
    outcomes = FP.inject_all(table)
    outcomes.pop("rollback")
    try:
        FP.assert_injections_match_declarations(outcomes, table)
    except FP.PolicyViolation as exc:
        assert any(m["id"] == "rollback" for m in exc.mismatches)
    else:
        raise AssertionError("missing injection was accepted")


def test_hooks_fail_open_on_config_syntax_error() -> None:
    out = FP.hooks_config_syntax_error()
    assert out.proceed and out.failure and out.degraded and not out.denied, out
    assert "JSONDecodeError" in out.error, out.error
    # Positive control: a parseable config with a working hook is clean.
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "hooks.json"
        cfg.write_text(json.dumps({"hooks": []}), encoding="utf-8")
        fired: list[int] = []
        ctx = fpc.Context(hooks_config=cfg, hooks=[lambda: fired.append(1)])
        clean = fpc.Hooks().apply(ctx)
        assert clean.proceed and not clean.failure and not clean.degraded and fired == [1]
        # A raising hook body: still proceed, degraded, warning recorded.
        def boom() -> None:
            raise ValueError("hook body failed")

        ctx = fpc.Context(hooks_config=cfg, hooks=[boom])
        broken = fpc.Hooks().apply(ctx)
        assert broken.proceed and broken.degraded and broken.failure and ctx.warnings


def test_static_audit_fail_closed_has_no_swallow_to_pass() -> None:
    table = FP.load_table()
    audit = FP.audit_fail_closed_components(table)
    assert audit["clean"], audit
    assert audit["fail_closed_ids"] == sorted(
        r["id"] for r in table["components"] if r["posture"] == FP.FAIL_CLOSED
    )
    assert audit["missing_apply"] == [] and audit["path"] == "fp_components.py"
    both = FP.both_states_auditor(table)
    assert both["both_states"] and both["fired_on_planted"] and both["silent_on_real"], both
    # Each swallow shape is a finding on its own.
    shapes = {
        "pass": "        except Exception:\n            pass\n",
        "return-none": "        except Exception:\n            return None\n",
        "return-ok": "        except Exception:\n            return self.ok()\n",
        "proceeding-outcome": "        except Exception as exc:\n            return Outcome(proceed=True, denied=False, degraded=True, failure=True)\n",
        "fall-through": "        except Exception as exc:\n            log(exc)\n",
    }
    for name, handler in shapes.items():
        src = (
            "class Outcome: pass\nclass Gate:\n    def apply(self, ctx, fault=None):\n"
            "        try:\n            self.check(ctx, fault)\n" + handler + "        return Outcome()\n"
        )
        report = FP.audit_source(src, {"gate": "Gate"})
        assert report["findings"], name
    # The deny path is not a finding; a missing apply is.
    good = "class Gate:\n    def apply(self, ctx, fault=None):\n        try:\n            self.check(ctx, fault)\n        except Exception as exc:\n            return self.deny(exc)\n        return self.ok()\n"
    assert FP.audit_source(good, {"gate": "Gate"})["clean"]
    assert FP.audit_source("class Gate: pass\n", {"gate": "Gate"})["missing_apply"] == ["gate"]


def test_table_schema_refuses_bad_rows() -> None:
    table = FP.load_table()
    assert FP.validate_table(table) == []
    bad = copy.deepcopy(table)
    bad["components"][0]["on_failure"] = "deny"  # fail-open row that denies
    assert FP.validate_table(bad)
    bad = copy.deepcopy(table)
    bad["components"].pop()  # dropping a published row is a schema violation
    assert FP.validate_table(bad)
    bad = copy.deepcopy(table)
    bad["default_posture"] = "fail-open"
    assert FP.validate_table(bad)
    bad = copy.deepcopy(table)
    bad["components"][4]["posture"] = "fail-open"
    bad["components"][4]["on_failure"] = "proceed"  # validator published fail-closed
    assert any("published as fail-closed" in e for e in FP.validate_table(bad))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        try:
            FP.load_table(p)
        except FP.TableInvalid:
            pass
        else:
            raise AssertionError("invalid table was loaded")


def test_reviewer_classifies_from_kind_only() -> None:
    table = FP.load_table()
    review = FP.independent_classification(table)
    assert review["verdict"] == "PASS" and not review["reads_posture_field"], review
    rows = [(r["id"], r["kind"]) for r in table["components"]]
    derived = FP.classify_by_kind(rows)
    assert derived["hooks"] == FP.FAIL_OPEN and derived["secret_gate"] == FP.FAIL_CLOSED
    assert FP.classify_by_kind([("x", "unknown-kind")])["x"] == FP.FAIL_CLOSED
    flipped = copy.deepcopy(table)
    flipped["components"][0]["posture"] = FP.FAIL_CLOSED
    assert FP.independent_classification(flipped)["verdict"] == "FAIL"


def test_real_checks_deny_on_bad_input_without_injection() -> None:
    ctx = fpc.Context(text="key AKIAABCDEFGHIJKLMNOP here")
    assert fpc.SecretGate().apply(ctx).denied
    ctx = fpc.Context(signature="deadbeef")
    assert fpc.SignatureCheck().apply(ctx).denied
    ctx = fpc.Context(payload_paths=["../etc/passwd"])
    assert fpc.PayloadAllowlist().apply(ctx).denied
    ctx = fpc.Context(used_permissions={"read", "network"})
    assert fpc.ToolPermissions().apply(ctx).denied
    ctx = fpc.Context(manifest={"name": "x", "version": "1", "entry": "m"})
    assert fpc.Validators().apply(ctx).denied
    assert not fpc.Rollback().apply(fpc.Context()).denied


TESTS = [
    test_one_injection_per_component,
    test_negative_control_flip_declaration_goes_red,
    test_hooks_fail_open_on_config_syntax_error,
    test_static_audit_fail_closed_has_no_swallow_to_pass,
    test_table_schema_refuses_bad_rows,
    test_reviewer_classifies_from_kind_only,
    test_real_checks_deny_on_bad_input_without_injection,
]


def main() -> int:
    for test in TESTS:
        test()
        print(f"ok {test.__name__}")
    print(f"SUCCESS:IMP-0053-tests {len(TESTS)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
