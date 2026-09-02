"""Wrap live estate path guards and record string-vs-identity behaviour."""
from __future__ import annotations

import sys
from pathlib import Path

import guards as G
import scenario as S
from winpath import sep_fold

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"


def _load_estate():
    """Load live estate modules. `plugin` must be platform/plugin, not tools/plugin."""
    if str(CC_TOOLS) not in sys.path:
        sys.path.insert(0, str(CC_TOOLS))
    plat = str(REPO / "platform")
    existing = sys.modules.get("plugin")
    origin = (getattr(existing, "__file__", "") or "").replace("\\", "/")
    if existing is not None and "/tools/plugin/" in (origin + "/"):
        for key in list(sys.modules):
            if key == "plugin" or key.startswith("plugin."):
                del sys.modules[key]
    if plat in sys.path:
        sys.path.remove(plat)
    sys.path.insert(0, plat)
    from plugin.payload import AllowRule  # noqa: WPS433
    import reconcile_delivery as rec  # noqa: WPS433
    import render as rend  # noqa: WPS433

    return AllowRule, rec, rend


def estate_allow_covers(granted: str, candidate: str) -> str:
    """Live allowlist: platform/plugin/payload.py AllowRule.matches (fnmatch)."""
    allow_rule_cls, _, _ = _load_estate()
    wider = sep_fold(granted).rstrip("/")
    narrower = sep_fold(candidate)
    rule = allow_rule_cls(glob=wider + "/*", reason="tst-0066-estate-allowlist")
    return G.ACCEPT if rule.matches(narrower) else G.REJECT


def estate_deny_declaring(candidate: str) -> str:
    """DECLARING_DOCS is an exclude/deny list on repo-relative strings."""
    _, rec, _ = _load_estate()
    rel = sep_fold(candidate)
    return G.REJECT if rec._is_declaring_doc(rel) else G.ACCEPT


def estate_render_bound(root: str, candidate: str) -> str:
    """Same membership test as render's 'root must bound every write'."""
    return G.pathlib_contains(root, candidate)


def fire(guard_id: str, kind: str, policy: str, candidate: str, impl) -> dict:
    verdict = impl(candidate)
    return {
        "guard_id": guard_id,
        "kind": kind,
        "policy": policy,
        "candidate": candidate,
        "verdict": verdict,
    }


def control_and_canonical_shots() -> list[dict]:
    """Both aliases against control (string) and canonical guards."""
    rows: list[dict] = []

    def deny_s(c: str) -> str:
        return G.string_deny_exact(S.DENIED_SECRET, c)

    def deny_c(c: str) -> str:
        return G.canonical_deny_exact(S.DENIED_SECRET, c)

    def allow_s(c: str) -> str:
        return G.string_allow_prefix(S.ALLOWED_HOOKS, c)

    def allow_c(c: str) -> str:
        return G.canonical_allow_prefix(S.ALLOWED_HOOKS, c)

    def cont_s(c: str) -> str:
        return G.string_contains(S.REPO_ROOT, c)

    def cont_c(c: str) -> str:
        return G.canonical_contains(S.REPO_ROOT, c)

    shots = [
        ("control-deny", "deny-guard", S.DENIED_SECRET, deny_s),
        ("control-deny", "deny-guard", S.DENIED_SECRET_DOT, deny_s),
        ("control-deny", "deny-guard", S.DENIED_SECRET_SPACE, deny_s),
        ("control-deny", "deny-guard", S.DENIED_SECRET_83, deny_s),
        ("canonical-deny", "deny-guard", S.DENIED_SECRET, deny_c),
        ("canonical-deny", "deny-guard", S.DENIED_SECRET_DOT, deny_c),
        ("canonical-deny", "deny-guard", S.DENIED_SECRET_SPACE, deny_c),
        ("canonical-deny", "deny-guard", S.DENIED_SECRET_83, deny_c),
        ("control-allow", "allowlist", S.ALLOWED_HOOK, allow_s),
        ("control-allow", "allowlist", S.ALLOWED_HOOK_DOT, allow_s),
        ("control-allow", "allowlist", S.OUTSIDE_HOOKS_VIA_DOT, allow_s),
        ("control-allow", "allowlist", S.OUTSIDE_HOOKS_VIA_83, allow_s),
        ("canonical-allow", "allowlist", S.ALLOWED_HOOK, allow_c),
        ("canonical-allow", "allowlist", S.ALLOWED_HOOK_DOT, allow_c),
        ("canonical-allow", "allowlist", S.ALLOWED_HOOK_83, allow_c),
        ("canonical-allow", "allowlist", S.OUTSIDE_HOOKS_VIA_DOT, allow_c),
        ("canonical-allow", "allowlist", S.OUTSIDE_HOOKS_VIA_83, allow_c),
        ("control-contain", "containment", S.INSIDE_LONG, cont_s),
        ("control-contain", "containment", S.INSIDE_DOT, cont_s),
        ("control-contain", "containment", S.OUTSIDE_VIA_DOT, cont_s),
        ("control-contain", "containment", S.OUTSIDE_VIA_83, cont_s),
        ("canonical-contain", "containment", S.INSIDE_LONG, cont_c),
        ("canonical-contain", "containment", S.INSIDE_DOT, cont_c),
        ("canonical-contain", "containment", S.INSIDE_VIA_83, cont_c),
        ("canonical-contain", "containment", S.OUTSIDE_VIA_DOT, cont_c),
        ("canonical-contain", "containment", S.OUTSIDE_VIA_83, cont_c),
    ]
    for gid, kind, cand, impl in shots:
        rows.append(fire(gid, kind, "see-candidate", cand, impl))
    return rows


def estate_shots() -> list[dict]:
    rows: list[dict] = []

    def allow(c: str) -> str:
        return estate_allow_covers(S.ALLOWED_HOOKS, c)

    def deny(c: str) -> str:
        return estate_deny_declaring(c)

    def bound(c: str) -> str:
        return estate_render_bound(S.REPO_ROOT, c)

    shots = [
        (
            "estate-permission-allowlist",
            "allowlist",
            "platform/plugin/payload.py:AllowRule.matches",
            allow,
            [
                S.ALLOWED_HOOK,
                S.ALLOWED_HOOK_DOT,
                S.ALLOWED_HOOK_83,
                S.OUTSIDE_HOOKS_VIA_DOT,
                S.OUTSIDE_HOOKS_VIA_83,
                S.DENIED_SECRET,
            ],
        ),
        (
            "estate-reconcile-deny",
            "deny-guard",
            "tools/command-center/reconcile_delivery.py:_is_declaring_doc",
            deny,
            [
                S.ESTATE_DENIED_REL,
                S.ESTATE_DENIED_DOT,
                S.ESTATE_DENIED_83,
                "command-center/receipts/TST-0066.json",
            ],
        ),
        (
            "estate-render-containment",
            "containment",
            "tools/command-center/render.py:write_all + Path.parents",
            bound,
            [
                S.INSIDE_LONG,
                S.INSIDE_DOT,
                S.INSIDE_VIA_83,
                S.OUTSIDE_VIA_DOT,
                S.OUTSIDE_VIA_83,
            ],
        ),
    ]
    for gid, kind, policy, impl, cands in shots:
        for cand in cands:
            row = fire(gid, kind, policy, cand, impl)
            rows.append(row)
    return rows


def classify_estate(rows: list[dict]) -> list[dict]:
    """Per guard: does it compare strings (alias of a denied/in-root path diverges)?"""
    by: dict[str, list[dict]] = {}
    for row in rows:
        by.setdefault(row["guard_id"], []).append(row)
    out = []
    for gid, shots in by.items():
        kind = shots[0]["kind"]
        policy = shots[0]["policy"]
        # String-comparing: trailing-dot or 8.3 of a *policy-relevant* identity
        # gets a different verdict than the long name.
        diverged = []
        if gid == "estate-reconcile-deny":
            long_v = next(s["verdict"] for s in shots if s["candidate"] == S.ESTATE_DENIED_REL)
            for s in shots:
                if s["candidate"] in {S.ESTATE_DENIED_DOT, S.ESTATE_DENIED_83}:
                    if s["verdict"] != long_v:
                        diverged.append(s)
        elif gid == "estate-permission-allowlist":
            long_v = next(s["verdict"] for s in shots if s["candidate"] == S.ALLOWED_HOOK)
            for s in shots:
                if s["candidate"] in {S.ALLOWED_HOOK_DOT, S.ALLOWED_HOOK_83}:
                    if s["verdict"] != long_v:
                        diverged.append(s)
        elif gid == "estate-render-containment":
            long_v = next(s["verdict"] for s in shots if s["candidate"] == S.INSIDE_LONG)
            for s in shots:
                if s["candidate"] in {S.INSIDE_DOT, S.INSIDE_VIA_83}:
                    if s["verdict"] != long_v:
                        diverged.append(s)
        compares_strings = bool(diverged)
        out.append(
            {
                "guard_id": gid,
                "kind": kind,
                "policy": policy,
                "compares_path_strings": compares_strings,
                "alias_verdict_diverged": diverged,
                "shots": shots,
            }
        )
    return out
