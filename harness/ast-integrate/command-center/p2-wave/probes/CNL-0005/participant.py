"""Participant descriptor: the 9 per-seat dials and behavioral identity.

Identity is the canonical tuple AFTER closed defaults. seat_id is an address,
not a tenth dial: two seats with different ids and the same filled dials are
duplicates.
"""
from __future__ import annotations

from typing import Any

NINE_DIALS = (
    "model",
    "vendor",
    "expertise",
    "role",
    "authority",
    "vote_weight",
    "tools",
    "effort",
    "context",
)
REQUIRED_DIALS = ("model", "role", "authority")
OPTIONAL_DIALS = (
    "vendor",
    "expertise",
    "vote_weight",
    "tools",
    "effort",
    "context",
)
OPTIONAL_DEFAULTS = {
    "expertise": None,
    "vote_weight": 1.0,
    "tools": (),
    "effort": "inherit",
    "context": "shared",
}
AUTHORITY_KINDS = ("observe", "advise", "vote", "chair", "bind")
EFFORT_ENUM = ("inherit", "low", "medium", "high")

# Unique model→vendor unless listed with >1 vendor. Ambiguous models refuse
# a missing vendor instead of guessing.
MODEL_VENDOR_REGISTRY: dict[str, tuple[str, ...]] = {
    "claude-opus-4": ("anthropic",),
    "claude-sonnet-4": ("anthropic",),
    "gpt-4.1": ("openai",),
    "o3": ("openai",),
    "gemini-2.5-pro": ("google",),
    "grok-4": ("xai",),
    "mistral-large": ("mistral",),
    "llama-3.1-70b": ("meta", "groq"),
}


class DescriptorError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _norm_tools(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise DescriptorError("TOOLS_TYPE", "tools must be an array of strings")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise DescriptorError("TOOLS_ITEM", "tools items must be non-empty strings")
        if item in seen:
            raise DescriptorError("TOOLS_DUP", f"duplicate tool {item!r}")
        seen.add(item)
        out.append(item)
    return tuple(sorted(out))


def _norm_authority(value: Any) -> tuple[str, bool, bool]:
    if not isinstance(value, dict):
        raise DescriptorError("AUTHORITY_TYPE", "authority must be an object with kind")
    kind = value.get("kind")
    if kind not in AUTHORITY_KINDS:
        raise DescriptorError(
            "AUTHORITY_KIND", f"authority.kind must be one of {AUTHORITY_KINDS}"
        )
    extra = set(value) - {"kind", "can_bind", "can_veto"}
    if extra:
        raise DescriptorError("AUTHORITY_EXTRA", f"unknown authority fields {sorted(extra)}")
    can_bind = bool(value.get("can_bind", False))
    can_veto = bool(value.get("can_veto", False))
    if kind == "bind":
        can_bind = True
    return (str(kind), can_bind, can_veto)


def _norm_effort(value: Any) -> str:
    if value is None:
        return "inherit"
    if not isinstance(value, str) or value not in EFFORT_ENUM:
        raise DescriptorError("EFFORT_ENUM", f"effort must be one of {EFFORT_ENUM}")
    return value


def _norm_context(value: Any) -> str:
    if value is None:
        return "shared"
    if not isinstance(value, str) or not value.strip():
        raise DescriptorError("CONTEXT_TYPE", "context must be a non-empty string")
    return value.strip()


def _norm_weight(value: Any) -> float:
    if value is None:
        return 1.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DescriptorError("WEIGHT_TYPE", "vote_weight must be a number")
    w = float(value)
    if w <= 0:
        raise DescriptorError("WEIGHT_RANGE", "vote_weight must be > 0")
    return round(w, 6)


def derive_vendor(model: str, vendor: Any) -> str:
    listed = MODEL_VENDOR_REGISTRY.get(model)
    if vendor is None or vendor == "":
        if listed is None:
            raise DescriptorError(
                "VENDOR_UNKNOWN_MODEL",
                f"vendor omitted and model {model!r} is not in the unique-vendor registry",
            )
        if len(listed) != 1:
            raise DescriptorError(
                "VENDOR_AMBIGUOUS",
                f"vendor omitted and model {model!r} maps to {list(listed)}; specify vendor",
            )
        return listed[0]
    if not isinstance(vendor, str) or not vendor.strip():
        raise DescriptorError("VENDOR_TYPE", "vendor must be a non-empty string")
    got = vendor.strip()
    if listed is not None and got not in listed:
        raise DescriptorError(
            "VENDOR_MISMATCH",
            f"vendor {got!r} is not a registered host of {model!r} ({list(listed)})",
        )
    return got


def fill(seat: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with optional dials filled. Raises DescriptorError."""
    if not isinstance(seat, dict):
        raise DescriptorError("SEAT_TYPE", "seat must be an object")
    unknown = set(seat) - {"seat_id", *NINE_DIALS}
    if unknown:
        raise DescriptorError("UNKNOWN_FIELD", f"unknown fields {sorted(unknown)}")
    seat_id = seat.get("seat_id")
    if not isinstance(seat_id, str) or not seat_id.strip():
        raise DescriptorError(
            "SEAT_ID", "seat_id is required (address, not a behavioral dial)"
        )
    model = seat.get("model")
    role = seat.get("role")
    if not isinstance(model, str) or not model.strip():
        raise DescriptorError("MODEL_REQUIRED", "model is required; no silent default")
    if not isinstance(role, str) or not role.strip():
        raise DescriptorError("ROLE_REQUIRED", "role is required; no silent default")
    if "authority" not in seat:
        raise DescriptorError(
            "AUTHORITY_REQUIRED", "authority is required; no silent default"
        )
    kind, can_bind, can_veto = _norm_authority(seat.get("authority"))
    expertise = seat.get("expertise", OPTIONAL_DEFAULTS["expertise"])
    if expertise is not None and (not isinstance(expertise, str) or not expertise.strip()):
        raise DescriptorError("EXPERTISE_TYPE", "expertise must be null or a non-empty string")
    return {
        "seat_id": seat_id.strip(),
        "model": model.strip(),
        "vendor": derive_vendor(model.strip(), seat.get("vendor")),
        "expertise": None if expertise is None else expertise.strip(),
        "role": role.strip(),
        "authority": {"kind": kind, "can_bind": can_bind, "can_veto": can_veto},
        "vote_weight": _norm_weight(seat.get("vote_weight")),
        "tools": list(_norm_tools(seat.get("tools"))),
        "effort": _norm_effort(seat.get("effort")),
        "context": _norm_context(seat.get("context")),
    }


def identity_key(seat: dict[str, Any]) -> tuple[Any, ...]:
    filled = fill(seat)
    auth = filled["authority"]
    return (
        filled["model"],
        filled["vendor"],
        filled["expertise"],
        filled["role"],
        (auth["kind"], auth["can_bind"], auth["can_veto"]),
        filled["vote_weight"],
        tuple(filled["tools"]),
        filled["effort"],
        filled["context"],
    )


def unspecified_optionals(seat: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for dial in OPTIONAL_DIALS:
        if dial not in seat:
            missing.append(dial)
            continue
        val = seat.get(dial)
        if val in (None, "", []):
            missing.append(dial)
    return missing


def find_duplicates(seats: list[dict[str, Any]]) -> dict[str, Any]:
    """Flag pairs that differ in NO filled dial. Different seat_id is not enough."""
    findings: list[dict[str, Any]] = []
    keys: dict[tuple[Any, ...], list[str]] = {}
    ids: dict[str, int] = {}
    filled_rows: list[dict[str, Any]] = []
    for seat in seats:
        filled = fill(seat)
        sid = filled["seat_id"]
        ids[sid] = ids.get(sid, 0) + 1
        key = identity_key(seat)
        keys.setdefault(key, []).append(sid)
        filled_rows.append(filled)
    for sid, n in ids.items():
        if n > 1:
            findings.append({"code": "DUPLICATE_SEAT_ID", "seat_ids": [sid], "count": n})
    for key, group in keys.items():
        unique_ids = list(dict.fromkeys(group))
        if len(group) > 1:
            identity = {}
            for i, dial in enumerate(NINE_DIALS):
                if dial == "authority":
                    identity[dial] = {
                        "kind": key[i][0],
                        "can_bind": key[i][1],
                        "can_veto": key[i][2],
                    }
                else:
                    identity[dial] = key[i]
            findings.append(
                {
                    "code": "DUPLICATE_SEAT",
                    "seat_ids": unique_ids,
                    "count": len(group),
                    "identity": identity,
                }
            )
    fired = any(f["code"] == "DUPLICATE_SEAT" for f in findings)
    return {
        "fired": fired,
        "silent": not fired,
        "findings": findings,
        "seat_count": len(seats),
        "distinct_identity_count": len(keys),
        "filled": filled_rows,
    }


def verbatim_negative_control(result: dict[str, Any]) -> str:
    codes = sorted({f["code"] for f in result["findings"]})
    ids: list[str] = []
    for f in result["findings"]:
        if f["code"] == "DUPLICATE_SEAT":
            ids = f["seat_ids"]
            break
    return (
        "On the rejected state (two seats that differ in NO dial, including "
        "after filling optional defaults) the check reports fired=True "
        f"codes={codes} seat_ids={ids}. It does not silently accept the pair. "
        "On the accepted state (two seats that differ in at least one filled "
        "dial) the same check reports fired=False findings=[]."
    )


def chair_opus() -> dict[str, Any]:
    return {
        "seat_id": "chair-1",
        "model": "claude-opus-4",
        "role": "chair",
        "authority": {"kind": "chair", "can_bind": True, "can_veto": False},
        "expertise": "systems-architecture",
        "tools": ["read", "grep"],
        "effort": "high",
        "context": "shared",
    }


def critic_gpt() -> dict[str, Any]:
    return {
        "seat_id": "critic-1",
        "model": "gpt-4.1",
        "vendor": "openai",
        "role": "critic",
        "authority": {"kind": "vote"},
        "vote_weight": 1.0,
        "tools": ["read"],
        "effort": "medium",
        "context": "shared",
    }


def scribe_gemini() -> dict[str, Any]:
    """Omits every optional dial; defaults keep required-dial distinguishability."""
    return {
        "seat_id": "scribe-1",
        "model": "gemini-2.5-pro",
        "role": "scribe",
        "authority": {"kind": "observe"},
    }


def good_roster() -> list[dict[str, Any]]:
    return [chair_opus(), critic_gpt(), scribe_gemini()]


def zero_dial_diff_pair() -> list[dict[str, Any]]:
    """Same filled identity, different seat_id. Must be DUPLICATE_SEAT."""
    return [
        scribe_gemini(),
        {
            "seat_id": "scribe-clone",
            "model": "gemini-2.5-pro",
            "role": "scribe",
            "authority": {"kind": "observe"},
        },
    ]


def vendor_derived_pair() -> list[dict[str, Any]]:
    """Omitted unique vendor vs explicit vendor: same identity."""
    return [
        {
            "seat_id": "a",
            "model": "claude-opus-4",
            "role": "analyst",
            "authority": {"kind": "vote"},
        },
        {
            "seat_id": "b",
            "model": "claude-opus-4",
            "vendor": "anthropic",
            "role": "analyst",
            "authority": {"kind": "vote"},
            "vote_weight": 1.0,
            "tools": [],
            "effort": "inherit",
            "context": "shared",
            "expertise": None,
        },
    ]


def distinct_model_pair() -> list[dict[str, Any]]:
    return [
        {
            "seat_id": "a",
            "model": "claude-opus-4",
            "role": "analyst",
            "authority": {"kind": "vote"},
        },
        {
            "seat_id": "b",
            "model": "gpt-4.1",
            "role": "analyst",
            "authority": {"kind": "vote"},
        },
    ]


def ambiguous_vendor_seat() -> dict[str, Any]:
    return {
        "seat_id": "llama-1",
        "model": "llama-3.1-70b",
        "role": "analyst",
        "authority": {"kind": "vote"},
    }


def invalid_missing_model() -> dict[str, Any]:
    return {
        "seat_id": "ghost",
        "role": "critic",
        "authority": {"kind": "vote"},
    }


def invalid_extra_field() -> dict[str, Any]:
    return {
        "seat_id": "extra",
        "model": "gpt-4.1",
        "role": "critic",
        "authority": {"kind": "vote"},
        "temperature": 0.2,
    }


def invalid_negative_weight() -> dict[str, Any]:
    return {
        "seat_id": "neg",
        "model": "gpt-4.1",
        "role": "critic",
        "authority": {"kind": "vote"},
        "vote_weight": -1,
    }
