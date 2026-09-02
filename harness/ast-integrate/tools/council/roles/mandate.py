"""Point-of-use mandate enforcement (IMP-0280)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

MODULE_REL = "tools/council/roles/mandate.py"
RIGHTS = ("speaking", "vote", "tool_access", "source_access", "veto")
_RIGHT_TO_FN = {
    "speaking": "speak",
    "vote": "cast_vote",
    "voting": "cast_vote",
    "tool_access": "use_tool",
    "source_access": "use_source",
    "veto": "cast_veto",
}


def load_source(path: str | None = None) -> str:
    p = Path(path) if path else Path(__file__)
    if not p.is_file():
        p = Path(__file__)
    return p.read_text(encoding="utf-8")


@dataclass
class Decision:
    allowed: bool
    right: str = ""
    reason: str = ""
    event: str = ""

    def __post_init__(self) -> None:
        if not self.event:
            self.event = "GRANTED" if self.allowed else "REFUSED"
        if not self.reason:
            self.reason = "granted" if self.allowed else "mandate-missing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "right": self.right,
            "reason": self.reason,
            "event": self.event,
        }


@dataclass
class Seat:
    seat_id: str
    grants: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class RoleMandate:
    name: str
    grants: dict[str, set[str]] = field(default_factory=dict)


def empty_mandate(name: str) -> dict[str, Any]:
    return {"name": name, "grants": {}}


def mandate_granting(role: str, right: str, name: str) -> dict[str, Any]:
    key = "vote" if right in {"vote", "voting"} else right
    return {"name": role, "grants": {key: {name}}}


def seat(seat_id: str, mandate: dict[str, Any]) -> Seat:
    grants = {k: set(v) for k, v in (mandate.get("grants") or {}).items()}
    return Seat(seat_id=seat_id, grants=grants)


def _refuse(right: str, reason: str = "mandate-missing") -> Decision:
    return Decision(allowed=False, right=right, reason=reason, event="REFUSED")


def _grant(right: str) -> Decision:
    return Decision(allowed=True, right=right, reason="granted", event="GRANTED")


def speak(who: Seat, _text: str) -> Decision:
    if "speaking" in who.grants:
        return _grant("speaking")
    return _refuse("speaking")


def cast_vote(who: Seat, _ballot: str) -> Decision:
    if "vote" in who.grants or "voting" in who.grants:
        return _grant("vote")
    return _refuse("vote")


def use_tool(who: Seat, tool: str) -> Decision:
    names = who.grants.get("tool_access") or set()
    if tool in names:
        return _grant("tool_access")
    return _refuse("tool_access")


def use_source(who: Seat, source: str) -> Decision:
    names = who.grants.get("source_access") or set()
    if source in names:
        return _grant("source_access")
    return _refuse("source_access")


def cast_veto(who: Seat, _ballot: str) -> Decision:
    if "veto" in who.grants:
        return _grant("veto")
    return _refuse("veto")


def _exercise(right: str, who: Seat) -> Decision:
    if right in {"speaking"}:
        return speak(who, "x")
    if right in {"vote", "voting"}:
        return cast_vote(who, "aye")
    if right == "tool_access":
        return use_tool(who, "search")
    if right == "source_access":
        return use_source(who, "docs")
    if right == "veto":
        return cast_veto(who, "no")
    names = who.grants.get(right) or set()
    return _grant(right) if names else _refuse(right)


def rights_matrix() -> list[dict[str, Any]]:
    cells = []
    for right in RIGHTS:
        grant_name = "search" if right == "tool_access" else "docs" if right == "source_access" else "note"
        granted = seat("g", mandate_granting("r", right, grant_name))
        denied = seat("d", empty_mandate("e"))
        g = _exercise(right, granted)
        d = _exercise(right, denied)
        cells.append(
            {
                "right": right,
                "with_grant": g.to_dict(),
                "without_grant": d.to_dict(),
                "granted_allowed": g.allowed,
                "denied_allowed": d.allowed,
                "pass": g.allowed and not d.allowed,
            }
        )
    return cells


def enforcement_sites() -> list[dict[str, str]]:
    return [
        {"right": right, "function": fn, "module": MODULE_REL}
        for right, fn in (
            ("speaking", "speak"),
            ("vote", "cast_vote"),
            ("tool_access", "use_tool"),
            ("source_access", "use_source"),
            ("veto", "cast_veto"),
        )
    ]


class _Audit:
    def __init__(self, enforced: Iterable[str], unenforced: Iterable[str]) -> None:
        self._enforced = tuple(enforced)
        self._unenforced = tuple(unenforced)

    def enforced_rights(self) -> Iterable[str]:
        return self._enforced

    def unenforced_rights(self) -> Iterable[str]:
        return self._unenforced

    def to_dict(self) -> dict[str, Any]:
        return {
            "enforced": list(self._enforced),
            "unenforced": list(self._unenforced),
        }


def _fn_always_allows(fn: ast.FunctionDef) -> bool:
    """True when the function body never branches on grants / never refuses."""
    text = ast.dump(fn)
    if "allowed=False" in text or "allowed = False" in text:
        return False
    if "_refuse" in text:
        return False
    if "who.grants" in text or "grants.get" in text:
        return False
    # Look for Compare / If on grants.
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_refuse":
            return False
        if isinstance(node, ast.Attribute) and node.attr == "grants":
            return False
    return True


def point_of_use_audit(source: str | None = None) -> _Audit:
    src = source if isinstance(source, str) else load_source()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return _Audit((), RIGHTS)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    enforced: list[str] = []
    unenforced: list[str] = []
    for right in RIGHTS:
        fn_name = _RIGHT_TO_FN.get(right, right)
        fn = fns.get(fn_name)
        if fn is None or _fn_always_allows(fn):
            unenforced.append(right)
        else:
            enforced.append(right)
    return _Audit(enforced, unenforced)


def strip_enforcement(source: str, right: str) -> str:
    """Remove the grant check for ``right`` so the function always allows."""
    fn_name = _RIGHT_TO_FN.get(right, right)
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    target = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            target = node
            break
    if target is None:
        return source
    start = target.lineno - 1
    end = (target.end_lineno or target.lineno)
    indent = "    "
    if lines[start].startswith("def "):
        pass
    replacement = (
        f"def {fn_name}(who, _arg=None):\n"
        f"{indent}return Decision(allowed=True, right={right!r}, event='GRANTED')\n"
    )
    return "".join(lines[:start]) + replacement + "".join(lines[end:])
