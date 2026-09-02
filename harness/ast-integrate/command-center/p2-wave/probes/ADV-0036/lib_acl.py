#!/usr/bin/env python3
"""Windows NTFS DACL engine used by ADV-0036.

Renders and parses icacls-style ACL text, classifies writers from ALLOW
entries, and computes effective write rights for a non-elevated token.
Canonical ACE order is explicit deny, explicit allow, inherited deny,
inherited allow. Inherited-deny versus inherited-allow is why a textual
scan and an empirical write can disagree.

This is a local model. It does not invoke icacls.exe, does not touch a
live Windows volume, and does not modify any ACL on the worktree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
FILE_APPEND_DATA = 0x0004
FILE_READ_EA = 0x0008
FILE_WRITE_EA = 0x0010
FILE_EXECUTE = 0x0020
FILE_DELETE_CHILD = 0x0040
FILE_READ_ATTRIBUTES = 0x0080
FILE_WRITE_ATTRIBUTES = 0x0100
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
SYNCHRONIZE = 0x00100000
GENERIC_ALL = 0x10000000
GENERIC_EXECUTE = 0x20000000
GENERIC_WRITE = 0x40000000
GENERIC_READ = 0x80000000

FILE_GENERIC_READ = (
    FILE_READ_DATA | FILE_READ_ATTRIBUTES | FILE_READ_EA | READ_CONTROL | SYNCHRONIZE
)
FILE_GENERIC_WRITE = (
    FILE_WRITE_DATA
    | FILE_WRITE_ATTRIBUTES
    | FILE_WRITE_EA
    | FILE_APPEND_DATA
    | READ_CONTROL
    | SYNCHRONIZE
)
FILE_GENERIC_EXECUTE = FILE_EXECUTE | FILE_READ_ATTRIBUTES | READ_CONTROL | SYNCHRONIZE
FILE_ALL_ACCESS = 0x001F01FF

PERM_MASK = {
    "F": GENERIC_ALL,
    "M": FILE_GENERIC_READ | FILE_GENERIC_WRITE | FILE_GENERIC_EXECUTE | DELETE,
    "W": FILE_GENERIC_WRITE,
    "RX": FILE_GENERIC_READ | FILE_GENERIC_EXECUTE,
    "R": FILE_GENERIC_READ,
    "D": DELETE,
    "N": 0,
    "WDAC": WRITE_DAC,
    "WO": WRITE_OWNER,
    "DE": DELETE,
    "DC": FILE_DELETE_CHILD,
    "WD": FILE_WRITE_DATA,
    "AD": FILE_APPEND_DATA,
    "GW": GENERIC_WRITE,
    "GA": GENERIC_ALL,
}

SID_NAMES = {
    "SY": r"NT AUTHORITY\SYSTEM",
    "BA": r"BUILTIN\Administrators",
    "BU": r"BUILTIN\Users",
    "AU": r"NT AUTHORITY\Authenticated Users",
    "WD": "Everyone",
    "IU": r"NT AUTHORITY\INTERACTIVE",
    "OW": "CREATOR OWNER",
    "USER": r"HOST\nonadmin",
    "TI": r"NT SERVICE\TrustedInstaller",
}
NAME_TO_SID = {name.lower(): sid for sid, name in SID_NAMES.items()}

BROAD_SIDS = frozenset({"WD", "AU", "BU", "IU"})
ADMIN_SIDS = frozenset({"BA"})
SYSTEM_SIDS = frozenset({"SY", "TI"})
NON_ELEVATED_SIDS = frozenset({"USER", "AU", "BU", "WD", "IU"})
ELEVATED_SIDS = NON_ELEVATED_SIDS | {"BA"}

# Concrete write bits after GENERIC_* expansion. Do not include
# READ_CONTROL/SYNCHRONIZE: those overlap FILE_GENERIC_READ and would
# mark Users(RX) as writers.
WRITE_BITS = (
    FILE_WRITE_DATA
    | FILE_APPEND_DATA
    | DELETE
    | WRITE_DAC
    | WRITE_OWNER
    | FILE_WRITE_EA
    | FILE_WRITE_ATTRIBUTES
    | FILE_DELETE_CHILD
)

_ACE_LINE = re.compile(r"^\s+(?P<name>.+?):(?P<flags>(?:\([^)]+\))+)\s*$")


@dataclass
class ACE:
    ace_type: str
    sid: str
    perm: str
    inherited: bool = False
    inherit_only: bool = False
    object_inherit: bool = False
    container_inherit: bool = False

    def mask(self, is_dir: bool = False) -> int:
        bits = PERM_MASK.get(self.perm.upper(), 0)
        if is_dir and self.perm.upper() == "M":
            bits |= FILE_DELETE_CHILD
        return expand_generic(bits)


@dataclass
class SecurityDescriptor:
    path: str
    owner: str
    dacl: list[ACE] = field(default_factory=list)
    is_dir: bool = False
    parent_path: str | None = None
    parent_owner: str | None = None
    parent_dacl: list[ACE] | None = None
    parent_is_dir: bool = True


def expand_generic(mask: int) -> int:
    out = mask
    if mask & GENERIC_ALL:
        out |= FILE_ALL_ACCESS
    if mask & GENERIC_WRITE:
        out |= FILE_GENERIC_WRITE
    if mask & GENERIC_READ:
        out |= FILE_GENERIC_READ
    if mask & GENERIC_EXECUTE:
        out |= FILE_GENERIC_EXECUTE
    return out


def canonical_order(dacl: Iterable[ACE]) -> list[ACE]:
    def key(ace: ACE) -> tuple[int, int]:
        return (1 if ace.inherited else 0, 0 if ace.ace_type.upper() == "DENY" else 1)

    return sorted(list(dacl), key=key)


def _ace_sid(ace: ACE, owner: str) -> str:
    return owner if ace.sid == "OW" else ace.sid


def access_check(
    sd: SecurityDescriptor,
    token_sids: Iterable[str],
    desired: int,
    *,
    use_parent: bool = False,
) -> bool:
    token = set(token_sids)
    if use_parent:
        dacl = sd.parent_dacl or []
        owner = sd.parent_owner or sd.owner
        is_dir = sd.parent_is_dir
    else:
        dacl = sd.dacl
        owner = sd.owner
        is_dir = sd.is_dir
    granted = 0
    want = expand_generic(desired)
    for ace in canonical_order(dacl):
        if ace.inherit_only:
            continue
        if _ace_sid(ace, owner) not in token:
            continue
        mask = ace.mask(is_dir=is_dir)
        if ace.ace_type.upper() == "DENY":
            if mask & want:
                return False
        else:
            granted |= mask & want
            if (granted & want) == want:
                return True
    return False


def can_write_data(sd: SecurityDescriptor, token_sids: Iterable[str]) -> bool:
    return access_check(sd, token_sids, FILE_WRITE_DATA)


def can_delete(sd: SecurityDescriptor, token_sids: Iterable[str]) -> bool:
    return access_check(sd, token_sids, DELETE)


def can_replace_via_parent(sd: SecurityDescriptor, token_sids: Iterable[str]) -> bool:
    if not sd.parent_dacl:
        return False
    parent_add = access_check(sd, token_sids, FILE_WRITE_DATA, use_parent=True)
    parent_dc = access_check(sd, token_sids, FILE_DELETE_CHILD, use_parent=True)
    return parent_add and (parent_dc or can_delete(sd, token_sids))


def classify_writers_from_aces(dacl: Iterable[ACE], owner: str) -> dict[str, list[str]]:
    """Textual classification: ALLOW ACEs that grant write bits.

    Denies are ignored here on purpose. Probe 2 evaluates denies.
    """
    buckets: dict[str, list[str]] = {
        "owner": [],
        "administrators": [],
        "SYSTEM": [],
        "broad": [],
        "other": [],
    }
    seen: set[tuple[str, str]] = set()
    for ace in dacl:
        if ace.ace_type.upper() != "ALLOW":
            continue
        if ace.inherit_only:
            continue
        if not (ace.mask() & WRITE_BITS):
            continue
        sid = _ace_sid(ace, owner)
        key = (sid, ace.perm)
        if key in seen:
            continue
        seen.add(key)
        label = f"{SID_NAMES.get(sid, sid)}:{ace.perm}{' (I)' if ace.inherited else ''}"
        if sid in SYSTEM_SIDS:
            buckets["SYSTEM"].append(label)
        elif sid in ADMIN_SIDS:
            buckets["administrators"].append(label)
        elif sid in BROAD_SIDS:
            buckets["broad"].append(label)
        elif sid == owner or ace.sid == "OW":
            buckets["owner"].append(label)
        else:
            buckets["other"].append(label)
    return buckets


def render_icacls(sd: SecurityDescriptor) -> str:
    lines = [sd.path]
    for ace in sd.dacl:
        name = SID_NAMES.get(ace.sid, ace.sid)
        flags: list[str] = []
        if ace.inherited:
            flags.append("I")
        if ace.object_inherit:
            flags.append("OI")
        if ace.container_inherit:
            flags.append("CI")
        if ace.inherit_only:
            flags.append("IO")
        if ace.ace_type.upper() == "DENY":
            flags.append("DENY")
        flags.append(ace.perm)
        lines.append("        " + name + ":" + "".join("(" + f + ")" for f in flags))
    lines.append("Successfully processed 1 files; Failed processing 0 files")
    return "\n".join(lines) + "\n"


def parse_icacls(text: str) -> tuple[str, list[ACE]]:
    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty icacls text")
    path = lines[0].strip()
    aces: list[ACE] = []
    for ln in lines[1:]:
        if ln.lower().startswith("successfully processed"):
            continue
        m = _ACE_LINE.match(ln)
        if not m:
            continue
        name = m.group("name").strip()
        sid = NAME_TO_SID.get(name.lower(), name)
        tokens = re.findall(r"\(([^)]+)\)", m.group("flags"))
        inherited = "I" in tokens
        oi = "OI" in tokens
        ci = "CI" in tokens
        io = "IO" in tokens
        deny = any(t.upper() == "DENY" for t in tokens)
        perms = [
            t
            for t in tokens
            if t not in {"I", "OI", "CI", "IO", "NP"} and t.upper() != "DENY"
        ]
        aces.append(
            ACE(
                ace_type="DENY" if deny else "ALLOW",
                sid=sid,
                perm=perms[-1] if perms else "N",
                inherited=inherited,
                inherit_only=io,
                object_inherit=oi,
                container_inherit=ci,
            )
        )
    return path, aces


def naive_broad_writable(icacls_text: str) -> bool:
    """Broken classifier: Users/Everyone/Authenticated plus (F|M|W).

    Ignores (DENY) and canonical order. Must fire on the inherited-deny trap
    while the engine denies the write.
    """
    for ln in icacls_text.splitlines():
        low = ln.lower()
        if not any(key in low for key in ("users", "everyone", "authenticated", "interactive")):
            continue
        if re.search(r"\((?:F|M|W|GW|GA|WD)\)", ln):
            return True
    return False


def consumer_sshd_admin_keys(sd: SecurityDescriptor) -> dict:
    """OpenSSH administrators_authorized_keys bar.

    Only SYSTEM and Administrators may appear. Inherited ACEs and any
    Users/Everyone/Authenticated ACE cause a silent reject.
    """
    reasons: list[str] = []
    allowed = {"SY", "BA"}
    for ace in sd.dacl:
        if ace.inherited:
            reasons.append("inherited-ace")
        sid = _ace_sid(ace, sd.owner)
        if sid not in allowed:
            reasons.append("principal:" + sid)
        if ace.inherit_only or ace.object_inherit or ace.container_inherit:
            reasons.append("inheritance-flag")
    reasons = sorted(set(reasons))
    return {
        "consumer": "openssh-administrators_authorized_keys",
        "reject": bool(reasons),
        "reasons": reasons,
        "note": (
            "sshd silently ignores the file when the ACL is wrong; it does "
            "not emit an ACL error."
        ),
    }


def writer_summary(buckets: dict[str, list[str]]) -> dict:
    return {
        "owner": list(buckets.get("owner") or []),
        "administrators": list(buckets.get("administrators") or []),
        "SYSTEM": list(buckets.get("SYSTEM") or []),
        "broad": list(buckets.get("broad") or []),
        "other": list(buckets.get("other") or []),
        "has_broad_writer": bool(buckets.get("broad")),
        "has_owner_writer": bool(buckets.get("owner")),
    }


def self_test() -> dict:
    failures: list[str] = []

    def sd_of(
        dacl: list[ACE],
        owner: str = "BA",
        parent: list[ACE] | None = None,
    ) -> SecurityDescriptor:
        return SecurityDescriptor(
            path=r"C:\x\f",
            owner=owner,
            dacl=dacl,
            parent_path=r"C:\x",
            parent_owner=owner,
            parent_dacl=parent,
        )

    pf = sd_of(
        [
            ACE("ALLOW", "SY", "F"),
            ACE("ALLOW", "BA", "F"),
            ACE("ALLOW", "BU", "RX", inherited=True),
        ]
    )
    if can_write_data(pf, NON_ELEVATED_SIDS):
        failures.append("program-files Users(RX) must not write")
    if not can_write_data(pf, ELEVATED_SIDS):
        failures.append("administrators must write program-files")

    user = sd_of(
        [
            ACE("ALLOW", "SY", "F"),
            ACE("ALLOW", "BA", "F"),
            ACE("ALLOW", "OW", "F"),
        ],
        owner="USER",
    )
    if not can_write_data(user, NON_ELEVATED_SIDS):
        failures.append("owner-full must accept non-elevated write")

    prot = sd_of([ACE("ALLOW", "SY", "F"), ACE("ALLOW", "BA", "F")])
    if can_write_data(prot, NON_ELEVATED_SIDS):
        failures.append("protected SY+BA must reject non-elevated write")
    if consumer_sshd_admin_keys(prot)["reject"]:
        failures.append("protected SY+BA must be accepted by sshd consumer")

    everyone = sd_of(
        [
            ACE("ALLOW", "SY", "F"),
            ACE("ALLOW", "BA", "F"),
            ACE("ALLOW", "WD", "F"),
        ]
    )
    if not can_write_data(everyone, NON_ELEVATED_SIDS):
        failures.append("Everyone(F) must accept non-elevated write")
    if not consumer_sshd_admin_keys(everyone)["reject"]:
        failures.append("Everyone(F) must be rejected by sshd consumer")

    trap = sd_of(
        [
            ACE("ALLOW", "SY", "F"),
            ACE("ALLOW", "BA", "F"),
            ACE("DENY", "BU", "W", inherited=True),
            ACE("ALLOW", "BU", "M", inherited=True),
        ]
    )
    text = render_icacls(trap)
    path, parsed = parse_icacls(text)
    if path != trap.path:
        failures.append("icacls parse lost path")
    parsed_sd = SecurityDescriptor(path, "BA", parsed)
    if can_write_data(parsed_sd, NON_ELEVATED_SIDS):
        failures.append("inherited deny must beat inherited allow")
    buckets = classify_writers_from_aces(parsed, "BA")
    if not buckets["broad"]:
        failures.append("textual classifier must still list Users as writer")
    if not naive_broad_writable(text):
        failures.append("naive grep must fire on inherited-deny trap")

    override = sd_of(
        [
            ACE("ALLOW", "AU", "W"),
            ACE("DENY", "AU", "W", inherited=True),
        ]
    )
    if not can_write_data(override, NON_ELEVATED_SIDS):
        failures.append("explicit allow must beat inherited deny")

    loose_parent = [
        ACE("ALLOW", "SY", "F"),
        ACE("ALLOW", "BA", "F"),
        ACE("ALLOW", "BU", "M"),
    ]
    tight = sd_of(
        [ACE("ALLOW", "SY", "F"), ACE("ALLOW", "BA", "F")],
        parent=loose_parent,
    )
    if can_write_data(tight, NON_ELEVATED_SIDS):
        failures.append("tight file must reject in-place write")
    if not can_replace_via_parent(tight, NON_ELEVATED_SIDS):
        failures.append("Users(M) parent must allow replace")

    order = canonical_order(
        [
            ACE("ALLOW", "BU", "M", inherited=True),
            ACE("DENY", "BU", "W", inherited=True),
            ACE("ALLOW", "SY", "F"),
            ACE("DENY", "WD", "W"),
        ]
    )
    kinds = [(a.inherited, a.ace_type, a.sid) for a in order]
    expect = [
        (False, "DENY", "WD"),
        (False, "ALLOW", "SY"),
        (True, "DENY", "BU"),
        (True, "ALLOW", "BU"),
    ]
    if kinds != expect:
        failures.append("canonical order " + str(kinds))

    return {"ok": not failures, "failures": failures, "n_checks": 12}


if __name__ == "__main__":
    report = self_test()
    print(("PASS" if report["ok"] else "FAIL") + " lib_acl.self_test")
    if report["failures"]:
        for item in report["failures"]:
            print(" ", item)
        raise SystemExit(1)
