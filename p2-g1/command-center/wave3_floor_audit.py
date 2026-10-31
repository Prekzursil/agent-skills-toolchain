"""WAVE 3 FLOOR AUDIT - mechanical, independent re-derivation.

Trusts no agent's self-reported number. Every figure here is read off disk or produced by a
subprocess whose output is captured verbatim.

Subcommands (run each; results merge into WAVE3-FLOOR-AUDIT.json):
    d1        defect D1 - cross-vendor predicate against >=20 vendor pairs incl. aliases
    d2        defect D2 - independent catalog census (Task / wildcard / mcp__ vs approval)
    d4        defect D4 - duplicate ids across every workflow doc
    d5        defect D5 - non-canonical assigned_model_vendor_role recount
    routing   check 4 - bytes injected per query at k=1,3,5,10 + precision/recall
    coord     check 5 - adapter degrades loudly, artifact preserved
    hygiene   check 7 - untracked files under platform/ and command-center/

Every check runs its own SEEDED-DEFECT control and records whether the probe FIRED.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
BUILD = REPO / "platform"
CC = REPO / "command-center"
OUT_JSON = CC / "WAVE3-FLOOR-AUDIT.json"

for p in (str(BUILD), str(BUILD / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)


# --------------------------------------------------------------------------- helpers


def load_out() -> dict[str, Any]:
    if OUT_JSON.exists():
        try:
            return json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_out(d: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def merge(key: str, value: Any) -> None:
    d = load_out()
    d[key] = value
    save_out(d)
    print(f"WROTE {key} -> {OUT_JSON}")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> dict[str, Any]:
    """Capture a subprocess verbatim. Never raises on non-zero."""
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "cmd": " ".join(cmd),
            "cwd": str(cwd or REPO),
            "exit": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": " ".join(cmd),
            "cwd": str(cwd or REPO),
            "exit": None,
            "stdout": (e.stdout or b"").decode("utf-8", "replace")
            if isinstance(e.stdout, bytes)
            else (e.stdout or ""),
            "stderr": f"TIMEOUT after {timeout}s",
        }


def lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def blob(rev: str, rel: str) -> bytes | None:
    """Read a git blob. NEVER git archive (it applies EOL conversion on this box)."""
    p = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
    )
    return p.stdout if p.returncode == 0 else None


# ============================================================== D1 cross-vendor


# (executor_vendor, reviewer_vendor, expected_comparison)
#   SAME  = the same vendor spelled differently -> must NOT pass as cross-vendor
#   CROSS = genuinely distinct vendors          -> must pass
#   NC    = not computable (hosting plane / placeholder / unknown) -> must BLOCK
D1_PAIRS: list[tuple[str, Any, str]] = [
    # --- alias pairs: the exact class D1 recorded as 10/10 FALSE GREEN ---
    ("anthropic", "Anthropic", "SAME"),
    ("anthropic", "claude", "SAME"),
    ("anthropic", "ANTHROPIC", "SAME"),
    ("anthropic", "anthropic ", "SAME"),
    ("anthropic", " anthropic", "SAME"),
    ("anthropic", "claude-code", "SAME"),
    ("anthropic", "anthropic.com", "SAME"),
    ("anthropic", "Anthropic PBC", "SAME"),
    ("openai", "codex", "SAME"),
    ("openai", "OpenAI", "SAME"),
    ("openai", "open ai", "SAME"),
    ("openai", "open_ai", "SAME"),
    ("openai", "chatgpt", "SAME"),
    ("openai", "gpt", "SAME"),
    ("google", "gemini", "SAME"),
    ("google", "Google DeepMind", "SAME"),
    ("google", "google.com", "SAME"),
    ("xai", "grok", "SAME"),
    ("meta", "llama", "SAME"),
    ("mistral", "Mistral AI", "SAME"),
    # unicode / control-byte smuggling of the same identity
    ("anthropic", "anthropic\u200b", "SAME"),
    ("anthropic", "anthropic\t", "SAME"),
    ("anthropic", "ANTHROPIC\u00a0", "SAME"),
    ("openai", "ｏｐｅｎａｉ", "SAME"),  # NFKC fullwidth
    # --- genuinely cross-vendor: must still pass, or the fix broke the good direction ---
    ("anthropic", "openai", "CROSS"),
    ("anthropic", "google", "CROSS"),
    ("openai", "google", "CROSS"),
    ("anthropic", "gemini", "CROSS"),
    ("claude", "codex", "CROSS"),
    ("openai", "xai", "CROSS"),
    ("anthropic", "human", "CROSS"),
    ("meta", "mistral", "CROSS"),
    # --- not computable: hosting planes, placeholders, unknowns, malformed ---
    ("bedrock", "anthropic", "NC"),
    ("anthropic", "bedrock", "NC"),
    ("vertex", "openai", "NC"),
    ("azure", "anthropic", "NC"),
    ("openrouter", "google", "NC"),
    ("unassigned", "anthropic", "NC"),
    ("anthropic", "unassigned", "NC"),
    ("anthropic", "totally-made-up-vendor", "NC"),
    ("", "anthropic", "NC"),
    ("anthropic", "", "NC"),
    ("anthropic", None, "NC"),
    ("anthropic", 7, "NC"),
    ("anthropic", {"vendor": "openai"}, "NC"),
]


def _receipt(exec_vendor: Any, rev_vendor: Any) -> dict[str, Any]:
    return {
        "produced_by": {"vendor": exec_vendor, "agent_id": "exec-1"},
        "reviewer": {
            "reviewer_id": "rev-1",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev_vendor,
        },
    }


def check_d1() -> dict[str, Any]:
    import completion_predicate as cp
    import vendor_identity as vi

    opts = cp.PredicateOptions(
        repo_root=REPO,
        require_cross_vendor_review=True,
        require_fresh_context_review=False,
    )

    rows = []
    for ex, rv, expect in D1_PAIRS:
        outcome, reason, detail = cp._c9_reviewer(_receipt(ex, rv), opts)
        comparison, cmp_reason, _ = vi.compare(ex, rv)
        # The predicate contract: only CROSS-VENDOR may reach SATISFIED.
        passed_as_cross = outcome.value == "SATISFIED"
        if expect == "SAME":
            correct = (not passed_as_cross) and comparison.value == "SAME-VENDOR"
        elif expect == "CROSS":
            correct = passed_as_cross and comparison.value == "CROSS-VENDOR"
        else:  # NC
            correct = (not passed_as_cross) and comparison.value == "NOT-COMPUTABLE"
        rows.append(
            {
                "executor": ex if isinstance(ex, str) else repr(ex),
                "reviewer": rv if isinstance(rv, str) else repr(rv),
                "expected": expect,
                "comparison": comparison.value,
                "predicate_outcome": outcome.value,
                "accepted_as_cross_vendor": passed_as_cross,
                "correct": correct,
                "reason": reason[:200],
            }
        )

    alias_rows = [r for r in rows if r["expected"] == "SAME"]
    cross_rows = [r for r in rows if r["expected"] == "CROSS"]
    nc_rows = [r for r in rows if r["expected"] == "NC"]
    wrong = [r for r in rows if not r["correct"]]

    # ---------- DETECTOR CONTROL: re-implement the KNOWN-BROKEN gate, prove the probe fires
    def broken_gate(ex: Any, rv: Any) -> bool:
        """The pre-fix gate verbatim: str(...or '') equality. True == accepted as cross."""
        return str(ex or "") != str(rv or "")

    control_alias_defeats = sum(
        1 for r in alias_rows if broken_gate(r["executor"], r["reviewer"])
    )
    control = {
        "seeded_defect": "re-implement the pre-fix gate `str(exec or '') != str(rev or '')`",
        "alias_pairs_the_broken_gate_accepts_as_cross_vendor": control_alias_defeats,
        "alias_pairs_total": len(alias_rows),
        "probe_FIRED_on_seeded_defect": control_alias_defeats > 0,
        "probe_silent_on_shipped_code": len(
            [r for r in alias_rows if r["accepted_as_cross_vendor"]]
        )
        == 0,
        "both_states_valid": control_alias_defeats > 0
        and len([r for r in alias_rows if r["accepted_as_cross_vendor"]]) == 0,
    }

    # second, mechanically independent signal: the SCHEMA layer must reject free text
    schema_probe = _d1_schema_probe()

    return {
        "pairs_tested": len(rows),
        "alias_pairs_tested": len(alias_rows),
        "cross_pairs_tested": len(cross_rows),
        "not_computable_pairs_tested": len(nc_rows),
        "alias_pairs_ACCEPTED_as_cross_vendor": len(
            [r for r in alias_rows if r["accepted_as_cross_vendor"]]
        ),
        "genuine_cross_pairs_still_accepted": len(
            [r for r in cross_rows if r["accepted_as_cross_vendor"]]
        ),
        "not_computable_pairs_blocked": len(
            [r for r in nc_rows if not r["accepted_as_cross_vendor"]]
        ),
        "incorrect_rows": wrong,
        "detector_control": control,
        "schema_layer": schema_probe,
        "VERDICT": "CLOSED"
        if not wrong and control["both_states_valid"] and schema_probe["ok"]
        else "NOT CLOSED",
        "rows": rows,
    }


def _d1_schema_probe() -> dict[str, Any]:
    """Layer 2: does receipt.schema.json actually reject an unregistered vendor string?"""
    try:
        import jsonschema
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": f"jsonschema unavailable: {e}"}
    sp = BUILD / "schema" / "receipt.schema.json"
    schema = json.loads(sp.read_text(encoding="utf-8"))
    defs = schema.get("$defs", {})
    vid = defs.get("vendor_id")
    vidc = defs.get("vendor_id_canonical")
    enum = list(vid.get("enum", [])) if isinstance(vid, dict) else []
    # both-states: a registered token validates, a garbage token does not
    val = jsonschema.Draft202012Validator({"$defs": defs, "$ref": "#/$defs/vendor_id"})
    good = list(val.iter_errors("anthropic"))
    bad = list(val.iter_errors("totally-made-up-vendor"))
    return {
        "ok": bool(enum) and not good and bool(bad),
        "vendor_id_present": vid is not None,
        "vendor_id_canonical_present": vidc is not None,
        "vendor_id_enum_size": len(enum),
        "registered_token_validates": not good,
        "unregistered_token_REJECTED": bool(bad),
        "reviewer_vendor_ref": _json_at(schema, ["properties", "reviewer"]),
        "note": "both-states control: the same validator accepts a registered token and "
        "rejects an unregistered one, so its rejection is a measurement",
    }


def _json_at(obj: Any, path: list[str]) -> Any:
    cur = obj
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    if isinstance(cur, dict):
        props = cur.get("properties") or {}
        v = props.get("vendor")
        return v
    return None


# ============================================================== D2 catalog census

TASK_TOKEN = re.compile(r"^Task\b", re.IGNORECASE)


#: The catalog's real grant field. Measured, not assumed: `tool_permissions` is present on
#: 2,007/2,007 units while `tools` / `allowed_tools` / `tool_grants` are present on ZERO. My
#: first pass keyed on `tools` and reported hold_Task=0 / hold_mcp__=0, which CONTRADICTED the
#: shipped gate checking a 942-unit population - a self-contradicting reading is a detector
#: failure, not a finding. TOKEN_FIELD_COVERAGE below re-asserts the field exists on every unit
#: so this class of miss cannot recur silently.
_TOKEN_FIELDS = (
    "tool_permissions",
    "tools",
    "tools_required",
    "allowed_tools",
    "tool_grants",
)


def _tokens_of(unit: dict[str, Any]) -> list[str]:
    """Every tool token a unit declares, wherever it declares it."""
    out: list[str] = []
    for key in _TOKEN_FIELDS:
        v = unit.get(key)
        if isinstance(v, list):
            out.extend([str(x) for x in v])
        elif isinstance(v, str):
            out.append(v)
    return out


def _identity_of(token: str) -> str:
    """The token identity is everything before the first '(' - the scope is inside it."""
    return token.split("(", 1)[0].strip()


def check_d2() -> dict[str, Any]:
    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = cat.get("work_units", [])
    items = cat.get("items", [])

    def census(us: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(us)
        approved = 0
        task_units, task_unapproved = [], []
        mcp_units, mcp_unapproved = [], []
        star_any, star_identity, star_scope_only = [], [], []
        for u in us:
            uid = u.get("unit_id") or u.get("id") or "?"
            appr = u.get("owner_approval_required") is True
            approved += 1 if appr else 0
            toks = _tokens_of(u)
            ids = [_identity_of(t) for t in toks]
            if any(TASK_TOKEN.match(i) for i in ids):
                task_units.append(uid)
                if not appr:
                    task_unapproved.append(uid)
            if any(i.startswith("mcp__") for i in ids):
                mcp_units.append(uid)
                if not appr:
                    mcp_unapproved.append(uid)
            if any("*" in t for t in toks):
                star_any.append(uid)
            if any("*" in i for i in ids):
                star_identity.append(uid)
            elif any("*" in t for t in toks):
                star_scope_only.append(uid)
        return {
            "work_units": n,
            "TOKEN_FIELD_COVERAGE": {
                f: sum(1 for u in us if u.get(f) is not None) for f in _TOKEN_FIELDS
            },
            "units_with_zero_tokens": sum(1 for u in us if not _tokens_of(u)),
            "owner_approval_required_true": approved,
            "hold_Task": len(task_units),
            "hold_Task_UNAPPROVED": len(task_unapproved),
            "hold_Task_unapproved_ids": sorted(task_unapproved)[:20],
            "hold_mcp__": len(mcp_units),
            "hold_mcp___UNAPPROVED": len(mcp_unapproved),
            "token_contains_star_anywhere": len(star_any),
            "star_in_token_IDENTITY_broadening": len(star_identity),
            "star_in_token_identity_ids": sorted(star_identity)[:20],
            "star_only_in_scope_narrowing": len(star_scope_only),
        }

    after = census(units)

    # BEFORE, recomputed from the pinned commit's catalog object (never git archive)
    before_raw = blob("0aa6f8fa", "command-center/WORK-UNIT-CATALOG.json")
    before = None
    if before_raw:
        before = census(json.loads(before_raw.decode("utf-8")).get("work_units", []))

    tool_policy = cat.get("tool_policy")
    tp = None
    if isinstance(tool_policy, dict):
        tp = {
            "default": tool_policy.get("default"),
            "allow": len(tool_policy.get("allow", []) or []),
            "deny": len(tool_policy.get("deny", []) or []),
            # the real key is require_owner_approval; `require_approval` does not exist and
            # reading it returned 0, contradicting the lane's documented 2. My miscount.
            "require_owner_approval": len(
                tool_policy.get("require_owner_approval", []) or []
            ),
            "require_owner_approval_tokens": list(
                tool_policy.get("require_owner_approval", []) or []
            ),
            "policy_keys_present": sorted(tool_policy),
            "allow_contains_modal_sandbox_exec": "mcp__cloud-hub__modal_sandbox_exec"
            in (tool_policy.get("allow") or []),
        }

    # does the SHIPPED gate actually fire? drive check_work_unit_authorization directly
    gate = _d2_gate_probe(units, tool_policy)

    return {
        "items_register_untouched_count": len(items),
        "AFTER_on_disk": after,
        "BEFORE_recomputed_from_0aa6f8fa": before,
        "catalog_tool_policy": tp,
        "shipped_gate": gate,
        "detector_control": gate.get("detector_control"),
        "VERDICT": (
            "CLOSED"
            if after["hold_Task_UNAPPROVED"] == 0
            and after["star_in_token_IDENTITY_broadening"] == 0
            and tp is not None
            and gate.get("detector_control", {}).get("probe_FIRED_on_seeded_defect")
            else "NOT CLOSED"
        ),
    }


def _d2_gate_probe(units: list[dict[str, Any]], tool_policy: Any) -> dict[str, Any]:
    """Run the shipped SEM-008..011 rules, then SEED a violation and require it to fire."""
    try:
        from wfdsl import semantics  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"cannot import wfdsl.semantics: {e}"}
    fn = getattr(semantics, "check_work_unit_authorization", None)
    if fn is None:
        return {"ok": False, "error": "check_work_unit_authorization ABSENT"}

    def summarise(rules: Any) -> dict[str, Any]:
        """POSITIVE assertion: every rule present AND its `checked` population non-zero.

        A `0 violations` reading is worthless if `checked` is also 0 - that is the
        guard-converts-a-bug-into-a-green shape this program has already paid for. So
        `checked` is recorded per rule rather than only "nothing blocking".
        """
        out: dict[str, Any] = {}
        for r in rules:
            out[str(r.rule)] = {
                "severity": str(r.severity),
                "checked": int(r.checked),
                "violations": len(r.violations),
                "sample_violation": (
                    json.dumps(r.violations[0], default=str)[:300]
                    if r.violations
                    else None
                ),
            }
        return out

    clean = summarise(fn(units, tool_policy))
    clean_total = sum(v["violations"] for v in clean.values())

    # ---------- seeded defect: a unit holding a deny-listed MCP exec token, unapproved
    seed = {
        "unit_id": "SEEDED-AUDIT-0001",
        "title": "seeded defect for detector control",
        "tool_permissions": [
            "mcp__cloud-hub__modal_sandbox_exec",
            "Task(anything)",
            "Bash(*)",
        ],
        "owner_approval_required": False,
        "execution_substrate": "cloud-batch",
        "reviewer_requirement": "cross-vendor",
    }
    seeded = summarise(fn(units + [seed], tool_policy))
    seeded_total = sum(v["violations"] for v in seeded.values())
    fired = sorted(
        k
        for k, v in seeded.items()
        if v["violations"] > clean.get(k, {}).get("violations", 0)
    )

    return {
        "ok": True,
        "rules_present": sorted(clean),
        "rule_count": len(clean),
        "clean_corpus": clean,
        "clean_corpus_total_violations": clean_total,
        "every_rule_checked_a_nonzero_population": all(
            v["checked"] > 0 for v in clean.values()
        ),
        "detector_control": {
            "seeded_defect": "one unit with mcp__cloud-hub__modal_sandbox_exec + Task(anything) "
            "+ Bash(*) and owner_approval_required=false",
            "seeded_corpus": seeded,
            "seeded_total_violations": seeded_total,
            "rules_that_FIRED_on_the_seed": fired,
            "probe_FIRED_on_seeded_defect": seeded_total > clean_total,
            "probe_silent_on_clean_corpus": clean_total == 0,
            "both_states_valid": seeded_total > clean_total and clean_total == 0,
        },
    }


# ============================================================== D4 duplicate ids


def _iter_workflow_docs() -> list[Path]:
    """Every DSL workflow document under platform/workflows, by CONTENT not by filename.

    Scope stated explicitly: platform/workflows/**/*.json, recursive, including forged/ and
    _shared/. A file counts as a workflow doc iff it parses as a JSON object carrying BOTH
    `dsl_version` and `id` (the DSL's own discriminator) -- so a STATUS/VALIDATION report that
    merely mentions ids is not miscounted.
    """
    out = []
    for p in sorted((BUILD / "workflows").rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and "dsl_version" in d and "id" in d:
            out.append(p)
    return out


def check_d4() -> dict[str, Any]:
    docs = _iter_workflow_docs()
    by_id: dict[str, list[str]] = defaultdict(list)
    for p in docs:
        d = json.loads(p.read_text(encoding="utf-8"))
        by_id[str(d["id"])].append(str(p.relative_to(REPO)).replace("\\", "/"))
    dupes = {k: v for k, v in by_id.items() if len(v) > 1}

    # also: ids duplicated in the wider tree (any json with an `id`, no dsl_version filter)
    wide: dict[str, list[str]] = defaultdict(list)
    for p in sorted((BUILD / "workflows").rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get("id"), str) and "stages" in d:
            wide[d["id"]].append(str(p.relative_to(REPO)).replace("\\", "/"))
    wide_dupes = {k: v for k, v in wide.items() if len(v) > 1}

    # BEFORE state at the pinned commit, same algorithm
    before = _d4_at_rev("0aa6f8fa")

    # ---------- DETECTOR CONTROL: plant a duplicate id in a temp copy, require a hit
    with tempfile.TemporaryDirectory(prefix="d4-control-") as td:
        tmp = Path(td)
        victim = docs[0]
        d = json.loads(victim.read_text(encoding="utf-8"))
        a = tmp / "a.workflow.json"
        b = tmp / "b.workflow.json"
        a.write_text(json.dumps(d), encoding="utf-8")
        b.write_text(json.dumps(d), encoding="utf-8")
        ctrl: dict[str, list[str]] = defaultdict(list)
        for p in sorted(tmp.rglob("*.json")):
            dd = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(dd, dict) and "dsl_version" in dd and "id" in dd:
                ctrl[str(dd["id"])].append(p.name)
        ctrl_dupes = {k: v for k, v in ctrl.items() if len(v) > 1}
        # and the negative half: one file only -> no dupe
        b.unlink()
        ctrl2: dict[str, list[str]] = defaultdict(list)
        for p in sorted(tmp.rglob("*.json")):
            dd = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(dd, dict) and "dsl_version" in dd and "id" in dd:
                ctrl2[str(dd["id"])].append(p.name)
        ctrl2_dupes = {k: v for k, v in ctrl2.items() if len(v) > 1}

    return {
        "scope": "platform/workflows/**/*.json recursive; a doc counts iff it parses as a JSON "
        "object carrying BOTH dsl_version and id",
        "workflow_docs_found": len(docs),
        "distinct_ids": len(by_id),
        "duplicate_ids_AFTER": dupes,
        "duplicate_id_count_AFTER": len(dupes),
        "duplicate_ids_wider_stages_filter": wide_dupes,
        "duplicate_ids_BEFORE_0aa6f8fa": before,
        "detector_control": {
            "seeded_defect": "two temp files carrying the SAME id as an existing doc",
            "probe_FIRED_on_seeded_defect": len(ctrl_dupes) == 1,
            "seeded_hit": {k: v for k, v in ctrl_dupes.items()},
            "probe_silent_when_defect_removed": len(ctrl2_dupes) == 0,
            "both_states_valid": len(ctrl_dupes) == 1 and len(ctrl2_dupes) == 0,
        },
        "VERDICT": "CLOSED" if not dupes and not wide_dupes else "NOT CLOSED",
    }


def _d4_at_rev(rev: str) -> dict[str, Any]:
    p = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev, "platform/workflows"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        return {"error": p.stderr[:400]}
    by_id: dict[str, list[str]] = defaultdict(list)
    n = 0
    for rel in p.stdout.splitlines():
        if not rel.endswith(".json"):
            continue
        raw = blob(rev, rel)
        if raw is None:
            continue
        try:
            d = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and "dsl_version" in d and "id" in d:
            n += 1
            by_id[str(d["id"])].append(rel)
    return {
        "rev": rev,
        "workflow_docs": n,
        "duplicate_ids": {k: v for k, v in by_id.items() if len(v) > 1},
    }


# ============================================================== D5 vendor role


def _classify_assignment(v: Any) -> str:
    if isinstance(v, dict):
        return "object"
    if isinstance(v, str):
        return "string"
    if v is None:
        return "absent"
    return "other:" + type(v).__name__


def check_d5() -> dict[str, Any]:
    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = cat.get("work_units", [])
    items = cat.get("items", [])

    def census(us: list[dict[str, Any]]) -> dict[str, Any]:
        c = Counter(
            _classify_assignment(u.get("assigned_model_vendor_role")) for u in us
        )
        shapes = Counter()
        for u in us:
            v = u.get("assigned_model_vendor_role")
            if isinstance(v, dict):
                shapes["obj:" + ",".join(sorted(v))] += 1
            elif isinstance(v, str):
                shapes["str"] += 1
        return {
            "total": len(us),
            "by_form": dict(c),
            "object_form_CANONICAL": c.get("object", 0),
            "string_form_NONCANONICAL": c.get("string", 0),
            "absent": c.get("absent", 0),
            "structural_key_set_fingerprints": dict(shapes),
            "distinct_fingerprints": len(shapes),
        }

    after = census(units)
    before_raw = blob("0aa6f8fa", "command-center/WORK-UNIT-CATALOG.json")
    before = (
        census(json.loads(before_raw.decode("utf-8")).get("work_units", []))
        if before_raw
        else None
    )
    items_with_field = sum(
        1 for i in items if i.get("assigned_model_vendor_role") is not None
    )

    # independent instrument #2: the project's own strict schema validator
    strict = _d5_strict_probe(units)

    # ---------- DETECTOR CONTROL: seed a slash-triple string unit, require both instruments hit
    seed_units = units + [
        {
            "unit_id": "SEEDED-AUDIT-D5",
            "assigned_model_vendor_role": "opus/anthropic/implementer",
        }
    ]
    seeded = census(seed_units)
    seeded_strict = _d5_strict_probe(seed_units)
    fired = (
        seeded["string_form_NONCANONICAL"] == after["string_form_NONCANONICAL"] + 1
    ) and (
        seeded_strict.get("assignment_type_errors", -1)
        == strict.get("assignment_type_errors", -2) + 1
        if strict.get("ok")
        else True
    )

    return {
        "AFTER_on_disk": after,
        "BEFORE_at_0aa6f8fa": before,
        "items_register_entries_carrying_the_field": items_with_field,
        "strict_schema_instrument": strict,
        "detector_control": {
            "seeded_defect": "one extra unit with assigned_model_vendor_role = "
            "'opus/anthropic/implementer' (the slash-triple string form)",
            "hand_classifier_count_moved": seeded["string_form_NONCANONICAL"]
            - after["string_form_NONCANONICAL"],
            "strict_validator_count_moved": (
                seeded_strict.get("assignment_type_errors")
                - strict.get("assignment_type_errors")
                if strict.get("ok") and seeded_strict.get("ok")
                else None
            ),
            "probe_FIRED_on_seeded_defect": bool(fired),
            "both_states_valid": bool(fired),
        },
        "VERDICT": "SEE NOTE",
    }


def _d5_strict_probe(units: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import jsonschema
    except Exception as e:
        return {"ok": False, "error": str(e)}
    sp = BUILD / "schema" / "work-unit.strict.schema.json"
    if not sp.exists():
        return {"ok": False, "error": f"absent: {sp}"}
    try:
        # Reuse the PLATFORM'S OWN disk-only referencing Registry rather than hand-rolling a
        # resolver: my first attempt used the deprecated RefResolver and died on
        # '$defs/dependency_token', i.e. it was measuring nothing. The platform resolver is a
        # mechanically independent instrument from my hand classifier, which is the point.
        from referencing import Registry, Resource  # type: ignore
        from referencing.jsonschema import DRAFT202012  # type: ignore

        schema = json.loads(sp.read_text(encoding="utf-8"))
        registry = Registry()
        for q in (BUILD / "schema").rglob("*.json"):
            try:
                s = json.loads(q.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(s, dict) and isinstance(s.get("$id"), str):
                registry = registry.with_resource(
                    s["$id"],
                    Resource.from_contents(s, default_specification=DRAFT202012),
                )
        val = jsonschema.Draft202012Validator(schema, registry=registry)
    except Exception as e:
        return {
            "ok": False,
            "error": f"validator build failed: {type(e).__name__}: {e}",
        }
    n = 0
    for u in units:
        for err in val.iter_errors(u):
            path = list(err.absolute_path)
            if path and path[0] == "assigned_model_vendor_role":
                if err.validator == "type":
                    n += 1
    return {
        "ok": True,
        "instrument": "jsonschema Draft202012 vs work-unit.strict.schema.json",
        "assignment_type_errors": n,
    }


# ============================================================== check 4 routing


def check_routing() -> dict[str, Any]:
    res: dict[str, Any] = {}
    res["cli_budget"] = run(
        [sys.executable, str(BUILD / "routing" / "cli.py"), "budget"], cwd=BUILD
    )
    res["cli_metrics"] = run(
        [sys.executable, str(BUILD / "routing" / "cli.py"), "metrics"], cwd=BUILD
    )

    # --- independent re-measurement: I compute bytes myself from the router's own output
    own = _routing_own_measure()
    res["independent_measurement"] = own
    return res


def _routing_per_tier(router: Any, qs: Any) -> dict[str, Any]:
    """Per-tier precision/recall so an easy tier cannot mask a hard one."""
    out: dict[str, Any] = {}
    tiers = sorted({q.tier for q in qs.queries})
    for tier in tiers:
        rows = [q for q in qs.queries if q.tier == tier]
        gold_rows = [q for q in rows if set(q.gold or ())]
        neg_rows = [q for q in rows if not set(q.gold or ())]
        block: dict[str, Any] = {
            "n": len(rows),
            "gold_bearing": len(gold_rows),
            "negatives_gold_is_empty": len(neg_rows),
            "tier_kind": "NEGATIVE (gold is empty; the metric is ABSTENTION, not recall)"
            if neg_rows and not gold_rows
            else "positive",
        }
        for k in (1, 3, 5, 10):
            prec = rec = 0.0
            items = 0
            abstained = 0
            for q in rows:
                sel = list(router.route(q.text, k=k).selected)[:k]
                ids = {
                    str((s[0] if isinstance(s, tuple) else getattr(s, "cap", s)).id)
                    for s in sel
                }
                items += len(sel)
                gold = set(q.gold or ())
                if gold:
                    hit = len(gold & ids)
                    prec += hit / len(ids) if ids else 0.0
                    rec += hit / len(gold)
                elif not sel:
                    abstained += 1
            # DIVIDE BY THE GOLD-BEARING COUNT, not by len(rows). Dividing by len(rows) made
            # the L3 NEGATIVE tier (gold = empty for all 6) read as "recall 0.0 at every k",
            # which looked like a routing hole and was purely my own arithmetic artifact.
            denom = max(1, len(gold_rows))
            block[f"k={k}"] = {
                "precision": round(prec / denom, 4) if gold_rows else None,
                "recall": round(rec / denom, 4) if gold_rows else None,
                "mean_items": round(items / max(1, len(rows)), 2),
                "abstain_rate_on_negatives": (
                    round(abstained / len(neg_rows), 4) if neg_rows else None
                ),
            }
        out[str(tier)] = block
    return out


def _routing_own_measure() -> dict[str, Any]:
    """Re-derive bytes@k and precision/recall WITHOUT the lane's metrics module."""
    try:
        from routing import index as ridx  # type: ignore
        from routing import queries as rq  # type: ignore
        from routing import router as rr  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"import failed: {type(e).__name__}: {e}"}

    out: dict[str, Any] = {"ok": True}
    try:
        inv = ridx.discover()
        qs = rq.load(inv)
        router = rr.Router.build(inv)
    except Exception as e:
        import traceback

        return {
            "ok": False,
            "error": f"setup failed: {type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-1500:],
        }

    out["index_records"] = len(inv.records)
    out["labelled_queries"] = len(qs.queries)

    # Decision.selected is a list of (Capability, score) TUPLES - not Candidate objects. My
    # first pass assumed `.cap` and died with "'tuple' object has no attribute 'cap'". And
    # Capability.id is ALREADY in the gold-label form ("agent:code-reviewer"), so no kind
    # prefix must be synthesised.
    def cap_of(sel: Any) -> Any:
        return sel[0] if isinstance(sel, tuple) else getattr(sel, "cap", sel)

    def cand_id(sel: Any) -> str:
        return str(cap_of(sel).id)

    def card_bytes(sel: Any) -> int:
        cap = cap_of(sel)
        n = getattr(cap, "card_bytes", None)
        if isinstance(n, int):
            return n
        return len(str(getattr(cap, "card", "") or "").encode("utf-8"))

    def full_bytes(sel: Any) -> int:
        cap = cap_of(sel)
        return len(
            str(
                getattr(cap, "desc_source", None)
                or getattr(cap, "routing_text", "")
                or ""
            ).encode("utf-8")
        )

    per_k: dict[str, Any] = {}
    for k in (1, 3, 5, 10):
        tot_card = tot_full = tot_items = 0
        prec_sum = rec_sum = 0.0
        n = 0
        for q in qs.queries:
            d = router.route(q.text, k=k)
            sel = list(d.selected)[:k]
            ids = [cand_id(c) for c in sel]
            tot_card += sum(card_bytes(c) for c in sel)
            tot_full += sum(full_bytes(c) for c in sel)
            tot_items += len(sel)
            gold = set(q.gold or ())
            if gold:
                hit = len(gold & set(ids))
                prec_sum += hit / len(ids) if ids else 0.0
                rec_sum += hit / len(gold)
                n += 1
        nq = max(1, len(qs.queries))
        per_k[str(k)] = {
            "mean_CARD_bytes_injected_per_query": round(tot_card / nq, 1),
            "mean_FULL_description_bytes_if_not_carded": round(tot_full / nq, 1),
            "total_card_bytes": tot_card,
            "mean_items_returned": round(tot_items / nq, 2),
            "precision": round(prec_sum / max(1, n), 4),
            "recall": round(rec_sum / max(1, n), 4),
            "labelled_queries_scored": n,
        }
    out["per_k"] = per_k
    out["per_tier"] = _routing_per_tier(router, qs)

    # ---------- FLOODING TEST: does recall rise only because k rises (i.e. by flooding)?
    r1 = per_k["1"]["recall"]
    r10 = per_k["10"]["recall"]
    b1 = per_k["1"]["mean_CARD_bytes_injected_per_query"]
    b10 = per_k["10"]["mean_CARD_bytes_injected_per_query"]
    items10 = per_k["10"]["mean_items_returned"]

    def flood_verdict(mean_items: float, k: int = 10) -> str:
        return (
            "FLOODING - the router fills every slot"
            if mean_items >= 0.9 * k
            else "NOT FLOODING - the router truncates below k rather than filling it"
        )

    out["flooding"] = {
        "recall_gain_1_to_10": round(r10 - r1, 4),
        "byte_growth_factor_1_to_10": round(b10 / b1, 2) if b1 else None,
        "mean_items_at_k10": items10,
        "k_slots_at_k10": 10,
        "fill_ratio_at_k10": round(items10 / 10, 3),
        "verdict": flood_verdict(items10),
    }

    # ---------- DETECTOR CONTROL: a REAL flooding selector, not a hardcoded constant.
    # `Decision.candidates` is the unthresholded ranking (885 records for one query), so
    # taking candidates[:k] IS a genuine always-fill router. The probe must flag it.
    flood_items_total = 0
    flood_rec = 0.0
    flood_n = 0
    flood_bytes = 0
    for q in qs.queries:
        d = router.route(q.text, k=10)
        sel = list(d.candidates)[:10]
        ids = {str(cap_of(s).id) for s in sel}
        flood_items_total += len(sel)
        flood_bytes += sum(card_bytes(s) for s in sel)
        gold = set(q.gold or ())
        if gold:
            flood_rec += len(gold & ids) / len(gold)
            flood_n += 1
    nq = max(1, len(qs.queries))
    flood_mean_items = round(flood_items_total / nq, 2)
    out["detector_control"] = {
        "seeded_defect": "a flooding selector built from Decision.candidates[:10] (the "
        "unthresholded ranking), i.e. a router that always fills every slot",
        "seeded_mean_items_at_k10": flood_mean_items,
        "seeded_recall_at_k10": round(flood_rec / max(1, flood_n), 4),
        "seeded_mean_card_bytes_per_query": round(flood_bytes / nq, 1),
        "seeded_verdict": flood_verdict(flood_mean_items),
        "shipped_verdict": flood_verdict(items10),
        "probe_FIRED_on_seeded_defect": flood_verdict(flood_mean_items).startswith(
            "FLOODING"
        ),
        "probe_silent_on_shipped_router": not flood_verdict(items10).startswith(
            "FLOODING"
        ),
        "both_states_valid": flood_verdict(flood_mean_items).startswith("FLOODING")
        and not flood_verdict(items10).startswith("FLOODING"),
        "note": "the seeded selector's recall is the ceiling the shipped router gives up in "
        "exchange for not flooding; both numbers are reported so the trade is visible",
    }
    return out


# ============================================================== check 5 coordination


def check_coord() -> dict[str, Any]:
    from coordination.adapters import load_adapter_registry  # type: ignore
    from coordination.capability import default_registry  # type: ignore
    from coordination.errors import CapabilityUnavailable  # type: ignore

    reg = load_adapter_registry()
    cr = default_registry()

    # a real work artifact on disk that MUST survive the refusal
    with tempfile.TemporaryDirectory(prefix="coord-audit-") as td:
        art = Path(td) / "work-artifact.json"
        payload = {"unit": "AUDIT-COORD-1", "result": "partial work that must survive"}
        art.write_text(json.dumps(payload), encoding="utf-8")
        before_sha = hashlib.sha256(art.read_bytes()).hexdigest()

        cases = []
        # codex-cli REFUSES subagent.spawn and mcp.tools; gemini-cli is UNMEASURED for all
        for adapter_id, cap, expect in [
            ("codex-cli", "subagent.spawn", "REFUSED"),
            ("codex-cli", "mcp.tools", "REFUSED"),
            ("codex-cli", "sandbox.enforced", "REFUSED"),
            ("claude-code", "schema.typed_output", "REFUSED"),
            ("gemini-cli", "fs.write", "UNMEASURED"),
            ("human-owner", "subagent.spawn", "REFUSED"),
            ("codex-cli", "fs.read", "OFFERED"),  # the good direction: must NOT raise
        ]:
            a = reg.adapters[adapter_id]
            support = a.supports(cap, cr)
            raised, exc_type, msg, preserved, sentinel, terminal = (
                False,
                None,
                "",
                [],
                None,
                None,
            )
            try:
                a.require(
                    cap, unit_id="AUDIT-COORD-1", preserved_artifacts=[art], registry=cr
                )
            except CapabilityUnavailable as e:
                raised = True
                exc_type = type(e).__name__
                msg = str(e)
                preserved = list(getattr(e, "preserved_artifacts", ()) or ())
            except Exception as e:  # any other exception is ALSO a finding
                raised = True
                exc_type = type(e).__name__
                msg = str(e)
            if raised:
                d = a.degrade(
                    unit_id="AUDIT-COORD-1",
                    capability=cap,
                    reason=msg[:160],
                    preserved_artifacts=[art],
                )
                sentinel = d.sentinel_line
                terminal = d.terminal_state
            cases.append(
                {
                    "adapter": adapter_id,
                    "capability": cap,
                    "declared_support": support.value,
                    "expected": expect,
                    "raised_typed_exception": raised,
                    "exception_type": exc_type,
                    "message_head": msg[:220],
                    "preserved_artifacts": preserved,
                    "sentinel_line": sentinel,
                    "terminal_state": terminal,
                    "artifact_still_on_disk": art.exists(),
                    "artifact_sha_unchanged": hashlib.sha256(
                        art.read_bytes()
                    ).hexdigest()
                    == before_sha,
                    "LOUD": raised and terminal == "BLOCKED" and bool(sentinel),
                }
            )

        unsupported = [c for c in cases if c["expected"] != "OFFERED"]
        supported = [c for c in cases if c["expected"] == "OFFERED"]

        # ---------- DETECTOR CONTROL: a SILENT adapter must be flagged
        class SilentAdapter:
            adapter_id = "seeded-silent-adapter"

            def require(
                self, capability, *, unit_id, preserved_artifacts=(), registry=None
            ):
                return None  # swallows the refusal -> the exact defect

        silent = SilentAdapter()
        silent_raised = False
        try:
            silent.require("subagent.spawn", unit_id="AUDIT-COORD-1")
        except Exception:
            silent_raised = True
        control = {
            "seeded_defect": "an adapter whose require() returns None instead of raising",
            "seeded_adapter_raised": silent_raised,
            "probe_FIRED_on_seeded_defect": not silent_raised,  # probe = 'must raise'; it did not
            "probe_silent_on_shipped_adapters": all(c["LOUD"] for c in unsupported),
            "both_states_valid": (not silent_raised)
            and all(c["LOUD"] for c in unsupported),
        }

        # a False return would be indistinguishable from success - assert no falsy path exists
        falsy = _coord_no_falsy_path()

        return {
            "unsupported_operations_forced": len(unsupported),
            "all_unsupported_raised_typed_exception": all(
                c["raised_typed_exception"] for c in unsupported
            ),
            "all_unsupported_terminal_state_BLOCKED": all(
                c["terminal_state"] == "BLOCKED" for c in unsupported
            ),
            "all_artifacts_preserved": all(
                c["artifact_still_on_disk"] and c["artifact_sha_unchanged"]
                for c in cases
            ),
            "supported_operation_did_NOT_raise": all(
                not c["raised_typed_exception"] for c in supported
            ),
            "cases": cases,
            "degraded_outcome_cannot_read_as_success": falsy,
            "detector_control": control,
            "VERDICT": "CLOSED"
            if all(c["LOUD"] for c in unsupported)
            and all(not c["raised_typed_exception"] for c in supported)
            and all(c["artifact_still_on_disk"] for c in cases)
            and control["both_states_valid"]
            else "NOT CLOSED",
        }


def _coord_no_falsy_path() -> dict[str, Any]:
    from coordination.adapters import DegradedOutcome  # type: ignore

    d = DegradedOutcome(
        adapter_id="a", unit_id="u", capability="c", reason="r", preserved_artifacts=()
    )
    fields = {f for f in getattr(DegradedOutcome, "__dataclass_fields__", {})}
    return {
        "ok_is_hard_false": d.ok is False,
        "ok_is_a_property_not_a_field": "ok" not in fields,
        "terminal_state_default": d.terminal_state,
        "constructing_with_terminal_SUCCESS_still_ok_false": DegradedOutcome(
            adapter_id="a",
            unit_id="u",
            capability="c",
            reason="r",
            preserved_artifacts=(),
            terminal_state="SUCCESS",
        ).ok
        is False,
    }


# ============================================================== check 7 hygiene


DELIVERABLE_EXT = {
    ".json",
    ".md",
    ".py",
    ".txt",
    ".zip",
    ".yaml",
    ".yml",
    ".toml",
    ".schema.json",
}


def check_hygiene() -> dict[str, Any]:
    # -u=all so git does NOT collapse an untracked DIRECTORY into one line (a scope trap
    # that produced a wrong conclusion earlier in this program)
    p = subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    untracked = [ln[3:].strip().strip('"') for ln in lines if ln.startswith("??")]
    modified = [
        ln[3:].strip().strip('"') for ln in lines if ln[:2].strip() in {"M", "MM", "AM"}
    ]

    def under(prefix: str, paths: list[str]) -> list[str]:
        return sorted(x for x in paths if x.startswith(prefix))

    plat = under("platform/", untracked)
    ccu = under("command-center/", untracked)
    root = sorted(
        x
        for x in untracked
        if "/" not in x.rstrip("/")
        or (not x.startswith(("platform/", "command-center/")))
    )

    def is_scratch(rel: str) -> bool:
        name = rel.rsplit("/", 1)[-1]
        if name.startswith("_"):
            return True
        if "/__pycache__/" in rel or rel.endswith(".pyc"):
            return True
        if "/.pytest_cache/" in rel:
            return True
        return False

    def deliverables(paths: list[str]) -> list[str]:
        out = []
        for x in paths:
            if is_scratch(x):
                continue
            ext = "." + x.rsplit(".", 1)[-1] if "." in x.rsplit("/", 1)[-1] else ""
            if ext in DELIVERABLE_EXT:
                out.append(x)
        return sorted(out)

    plat_deliv = deliverables(plat)
    cc_deliv = deliverables(ccu)

    # ---------- DETECTOR CONTROL: does the untracked scan see a KNOWN-PRESENT new file?
    probe = REPO / "platform" / "_wave3_audit_control_probe.tmp"
    probe.write_text("detector control\n", encoding="utf-8")
    p2 = subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall", "--", "platform"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    saw = any("_wave3_audit_control_probe.tmp" in ln for ln in p2.stdout.splitlines())
    probe.unlink(missing_ok=True)
    p3 = subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall", "--", "platform"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    gone = not any(
        "_wave3_audit_control_probe.tmp" in ln for ln in p3.stdout.splitlines()
    )

    return {
        "scope": "git status --porcelain=v1 -uall over the whole repo (NOT -unormal, which "
        "collapses an untracked directory to one line)",
        "total_status_lines": len(lines),
        "untracked_total": len(untracked),
        "untracked_under_platform": len(plat),
        "untracked_under_command_center": len(ccu),
        "untracked_elsewhere": len(root),
        "modified_tracked": len(modified),
        "modified_tracked_paths": modified,
        "UNTRACKED_DELIVERABLES_platform": plat_deliv,
        "UNTRACKED_DELIVERABLES_command_center": cc_deliv,
        "untracked_deliverable_count": len(plat_deliv) + len(cc_deliv),
        "untracked_scratch_count": len(plat)
        + len(ccu)
        - len(plat_deliv)
        - len(cc_deliv),
        "untracked_elsewhere_paths": root[:40],
        "detector_control": {
            "seeded_defect": "create platform/_wave3_audit_control_probe.tmp then remove it",
            "probe_FIRED_on_seeded_defect": saw,
            "probe_silent_after_removal": gone,
            "both_states_valid": saw and gone,
        },
    }


# ============================================================== main

DISPATCH = {
    "d1": ("check1_D1_cross_vendor", check_d1),
    "d2": ("check1_D2_workunit_authz", check_d2),
    "d4": ("check1_D4_duplicate_workflow_ids", check_d4),
    "d5": ("check1_D5_vendor_role_canonical", check_d5),
    "routing": ("check4_routing", check_routing),
    "coord": ("check5_coordination", check_coord),
    "hygiene": ("check7_repo_hygiene", check_hygiene),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in DISPATCH:
        print("usage: wave3_floor_audit.py {" + ",".join(DISPATCH) + "}")
        return 2
    key, fn = DISPATCH[argv[1]]
    try:
        result = fn()
    except Exception as e:
        import traceback

        result = {
            "ok": False,
            "PROBE_CRASHED": True,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-3000:],
        }
        merge(key, result)
        print(f"FAILED:{argv[1]} {type(e).__name__}: {e}")
        return 1
    merge(key, result)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:6000])
    print(f"SUCCESS:{argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
