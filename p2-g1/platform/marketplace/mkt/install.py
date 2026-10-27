"""Install / update / remove / rollback, the lockfile, and the thirteen enforcement gates.

THE CENTRAL PROPERTY THIS MODULE MUST HAVE
    A refusal must actually refuse. Revocation that does not block is the named failure
    mode for this build, so the design puts three structural defences around it:

    1. **Order.** Revocation is gate 4, evaluated BEFORE a single payload byte is read.
    2. **Fail-closed on absence.** A missing, unreadable or unsigned revocation list is a
       REFUSE by default (``trust-policy.on_missing.revocation_list``). A revocation channel
       that can be deleted to re-enable a revoked package is not a revocation channel.
    3. **Positive accounting.** :class:`Installer` records an outcome for EVERY gate in
       :data:`GATES` and refuses to report SUCCESS unless the count matches. A guard that
       swallowed an exception and produced "0 gates, nothing blocking" is the worst defect
       class in this program; ``len(evaluated) == len(GATES)`` is the assertion that makes
       it unstatable here.

    A fourth, external defence lives in :mod:`mkt.mutations`: it disables each guard in an
    isolated copy of THIS module's source and asserts the revoked install then SUCCEEDS,
    which is how we know the guard is load-bearing rather than decorative.

ROLLBACK IS NOT AN ESCAPE HATCH
    Rollback re-runs every gate against the previous version. If that version has since
    been revoked, rollback REFUSES -- which is the correct behaviour and is tested. A
    rollback path that skipped the gates would be the easiest way to install a revoked
    package on this whole surface.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import permissions as perms
from . import registry as reg
from . import sbom as sbom_mod
from . import schemas, versions
from .canon import (
    digest_file,
    ensure_within,
    iso_now,
    payload_digest,
    read_json,
    write_json,
)
from .crypto import verify_document

#: Every gate, in evaluation order. The receipt schema enumerates the same set.
GATES: tuple[str, ...] = (
    "index-signature",
    "publisher-known",
    "manifest-signature",
    "revocation",
    "permissions",
    "compatibility",
    "advisory",
    "conformance-score",
    "payload-digest",
    "sbom",
    "license",
    "dependencies",
    "lockfile",
)

REFUSAL_CODES: dict[str, str] = {
    "index-signature": "MKT-I01",
    "publisher-known": "MKT-I02",
    "manifest-signature": "MKT-I03",
    "revocation": "MKT-I04",
    "permissions": "MKT-I05",
    "compatibility": "MKT-I06",
    "advisory": "MKT-I07",
    "conformance-score": "MKT-I08",
    "payload-digest": "MKT-I09",
    "sbom": "MKT-I10",
    "license": "MKT-I11",
    "dependencies": "MKT-I12",
    "lockfile": "MKT-I13",
}

STATE_DIR = "state"
INSTALLED_NAME = "installed.json"
JOURNAL_NAME = "journal.jsonl"
LOCKFILE_NAME = "mkt-lock.json"
PACKAGES_DIR = "packages"


class InstallRefused(RuntimeError):
    """A gate refused. Carries the gate name, the machine code and the receipt."""

    def __init__(
        self, gate: str, message: str, receipt: dict[str, Any] | None = None
    ) -> None:
        self.gate = gate
        self.code = REFUSAL_CODES.get(gate, "MKT-I99")
        self.receipt = receipt
        super().__init__(f"{self.code} [{gate}] {message}")


@dataclass
class GateOutcome:
    gate: str
    outcome: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"gate": self.gate, "outcome": self.outcome}
        if self.detail:
            out["detail"] = self.detail[:600]
        return out


@dataclass
class Attempt:
    """A single lifecycle attempt: its gates, its outcome, and its receipt."""

    action: str
    name: str
    version: str | None = None
    gates: list[GateOutcome] = field(default_factory=list)
    outcome: str = "FAILED"
    refusal_code: str | None = None
    installed_files: int = 0
    payload_digest: str | None = None
    previous: dict[str, Any] | None = None
    overrides: list[str] = field(default_factory=list)
    detail: str = ""

    def record(self, gate: str, outcome: str, detail: str = "") -> GateOutcome:
        g = GateOutcome(gate, outcome, detail)
        self.gates.append(g)
        return g

    def refuse(self, gate: str, detail: str) -> InstallRefused:
        self.record(gate, "REFUSE", detail)
        self.outcome = "REFUSED"
        self.refusal_code = REFUSAL_CODES.get(gate, "MKT-I99")
        return InstallRefused(gate, detail, self.receipt())

    def receipt(
        self, *, registry_id: str | None = None, at: str | None = None
    ) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "schema_version": "1.0.0",
            "receipt_id": "rcpt:"
            + hashlib.sha256(
                f"{self.action}|{self.name}|{self.version}|{len(self.gates)}|{at or ''}".encode(
                    "utf-8"
                )
            ).hexdigest()[:16],
            "action": self.action,
            "outcome": self.outcome,
            "name": self.name,
            "at": at or iso_now(),
            "gates": [g.as_dict() for g in self.gates]
            or [{"gate": "index-signature", "outcome": "SKIP"}],
        }
        if self.version:
            doc["version"] = self.version
        if registry_id:
            doc["registry_id"] = registry_id
        if self.payload_digest:
            doc["payload_digest"] = self.payload_digest
        if self.installed_files:
            doc["installed_files"] = self.installed_files
        if self.previous:
            doc["previous"] = self.previous
        if self.overrides:
            doc["overrides_used"] = sorted(set(self.overrides))
        if self.refusal_code:
            doc["refusal_code"] = self.refusal_code
        return doc

    def assert_complete(self) -> None:
        """SUCCESS requires an outcome for every declared gate -- assert the POSITIVE.

        Not "nothing blocking". A missing gate means the gate did not run, and a gate that
        did not run has told you nothing.
        """
        seen = [g.gate for g in self.gates]
        missing = [g for g in GATES if g not in seen]
        if missing:
            raise AssertionError(
                f"gate accounting incomplete for {self.action} {self.name}: "
                f"{len(seen)}/{len(GATES)} evaluated, missing {missing}"
            )




# ---------------------------------------------------------------- revocation health
def _version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(version).split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _in_range(version: str, range_text: str) -> bool:
    text = (range_text or "*").strip()
    if text in ("", "*"):
        return True
    for clause in text.split(","):
        clause = clause.strip()
        if not clause or clause == "*":
            continue
        for op in ("<=", ">=", "==", "<", ">", "="):
            if clause.startswith(op):
                bound = clause[len(op) :].strip()
                vk, bk = _version_key(version), _version_key(bound)
                hit = {
                    "<=": vk <= bk,
                    ">=": vk >= bk,
                    "==": vk == bk,
                    "<": vk < bk,
                    ">": vk > bk,
                    "=": vk == bk,
                }[op]
                if not hit:
                    return False
                break
        else:
            if _version_key(version) != _version_key(clause):
                return False
    return True


def _revocation_hits(
    scope: dict[str, Any],
    name: str,
    version: str,
    publisher_public_key: str,
) -> bool:
    kind = str(scope.get("kind"))
    if kind == "version":
        return scope.get("name") == name and str(scope.get("version")) == str(version)
    if kind in ("package", "name"):
        return scope.get("name") == name
    if kind == "range":
        return scope.get("name") == name and _in_range(version, str(scope.get("range") or ""))
    if kind == "key":
        return bool(publisher_public_key) and scope.get("public_key") == publisher_public_key
    return False


class Installer:
    """Installs from a filesystem registry (or its mirrors) into a site root."""

    def __init__(
        self,
        registry_root: str | Path,
        site_root: str | Path,
        trust_policy: dict[str, Any],
        *,
        client_id: str = "claude-code",
        client_version: str = "2.1.0",
        platform_id: str = "win32",
        use_federation: bool = True,
    ) -> None:
        self.registry_root = Path(registry_root).resolve()
        self.site_root = Path(site_root).resolve()
        schemas.validate("trust-policy", trust_policy)
        self.trust_policy = trust_policy
        self.client_id = client_id
        self.client_version = client_version
        self.platform_id = platform_id
        self.view = reg.federate(self.registry_root) if use_federation else None
        self.index = reg.load_index(self.registry_root)
        self.journal: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ state
    @property
    def state_path(self) -> Path:
        return self.site_root / STATE_DIR / INSTALLED_NAME

    @property
    def journal_path(self) -> Path:
        return self.site_root / STATE_DIR / JOURNAL_NAME

    @property
    def lockfile_path(self) -> Path:
        return self.site_root / LOCKFILE_NAME

    def installed(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {"packages": {}}
        return read_json(self.state_path)

    def _write_state(self, state: dict[str, Any]) -> None:
        write_json(self.state_path, state)

    def _append_journal(self, receipt: dict[str, Any]) -> None:
        schemas.validate("install-receipt", receipt)
        self.journal.append(receipt)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(reg.canonical_bytes(receipt).decode("utf-8") + "\n")

    def receipts(self) -> list[dict[str, Any]]:
        if not self.journal_path.is_file():
            return []
        return [
            read_json_line(line)
            for line in self.journal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # ------------------------------------------------------------- lifecycle
    def install(
        self,
        name: str,
        range_text: str = "*",
        *,
        channel: str | None = None,
        allow_vulnerable: bool = False,
        allow_deprecated: bool = True,
        frozen: bool = False,
        now: str | None = None,
        requested_by: str = "direct",
        _in_progress: set[str] | None = None,
    ) -> dict[str, Any]:
        """Install one package and its dependencies. Raises :class:`InstallRefused` on any gate."""
        at = now or iso_now()
        attempt = Attempt(action="install", name=name)
        in_progress = set(_in_progress or ())
        if name in in_progress:
            raise attempt.refuse(
                "dependencies", f"dependency cycle: {' -> '.join([*in_progress, name])}"
            )
        in_progress.add(name)

        source_root, entry = self._resolve(attempt, name, range_text, channel, frozen)
        attempt.version = entry["version"]

        # gate 1 -- index signature -------------------------------------------
        ok, why = reg.verify_index_signature(
            source_root.index, self.trust_policy["registry_maintainer_keys"]
        )
        if not ok:
            raise attempt.refuse("index-signature", why)
        attempt.record("index-signature", "PASS", f"registry {source_root.registry_id}")

        # gate 2 -- publisher known -------------------------------------------
        pub_key = entry["signature"]["public_key"]
        trusted = next(
            (
                p
                for p in self.trust_policy["trusted_publishers"]
                if p["publisher"] == entry["publisher"]
            ),
            None,
        )
        key_rec = reg.publisher_key(source_root.index, entry["publisher"], pub_key)
        if trusted is None or trusted["public_key"] != pub_key or key_rec is None:
            if self.trust_policy["on_missing"]["publisher"] == "refuse":
                raise attempt.refuse(
                    "publisher-known",
                    f"publisher {entry['publisher']} with key {pub_key[:20]}... is not in the trust policy "
                    "or not declared by the registry",
                )
            attempt.record(
                "publisher-known", "WARN", "publisher unknown; policy allows warn"
            )
        elif key_rec["status"] != "active":
            raise attempt.refuse(
                "publisher-known",
                f"publisher key status is {key_rec['status']!r}, not 'active'",
            )
        else:
            attempt.record(
                "publisher-known", "PASS", f"{entry['publisher']} {key_rec['key_id']}"
            )

        # gate 3 -- manifest signature ----------------------------------------
        manifest = reg.load_manifest(source_root.root, entry)
        ok, why = verify_document(
            manifest, "mkt.manifest.v1", expected_public_key=pub_key
        )
        if not ok:
            raise attempt.refuse("manifest-signature", why)
        if manifest["payload"]["digest"] != entry["payload_digest"]:
            raise attempt.refuse(
                "manifest-signature",
                "index payload_digest disagrees with the SIGNED manifest -- the index row was edited",
            )
        if sorted(manifest["permissions"]) != sorted(entry.get("permissions", [])):
            raise attempt.refuse(
                "manifest-signature",
                f"index row permissions {sorted(entry.get('permissions', []))} disagree with the SIGNED "
                f"manifest {sorted(manifest['permissions'])} -- a widened mirror row",
            )
        attempt.record("manifest-signature", "PASS", manifest["signature"]["key_id"])

        # gate 4 -- REVOCATION (before any payload byte is touched) ------------
        self._gate_revocation(attempt, source_root, entry, pub_key)

        # gate 5 -- permissions ------------------------------------------------
        verdict = perms.evaluate(
            manifest["permissions"],
            max_permissions=self.trust_policy["max_permissions"],
            grant_permissions=list((trusted or {}).get("grant_permissions", [])),
            forbidden_permissions=self.trust_policy.get("forbidden_permissions"),
        )
        if not verdict.admissible:
            raise attempt.refuse(
                "permissions",
                f"excessive permissions {verdict.excessive}: "
                + "; ".join(f"{k} -> {v}" for k, v in sorted(verdict.reasons.items())),
            )
        attempt.record(
            "permissions",
            "PASS",
            f"{len(manifest['permissions'])} permission(s) within ceiling",
        )

        # gate 6 -- platform / client compatibility ---------------------------
        self._gate_compatibility(attempt, manifest)

        # gate 7 -- advisories --------------------------------------------------
        self._gate_advisory(attempt, source_root, entry, allow_vulnerable)

        # gate 8 -- conformance score ------------------------------------------
        floor = self.trust_policy["thresholds"]["min_conformance_score"]
        if manifest["quality"]["conformance_score"] < floor:
            raise attempt.refuse(
                "conformance-score",
                f"conformance score {manifest['quality']['conformance_score']} < policy floor {floor}",
            )
        attempt.record(
            "conformance-score",
            "PASS",
            f"{manifest['quality']['conformance_score']} >= {floor}",
        )

        # gate 9 -- payload digest ---------------------------------------------
        pkg_dir = ensure_within(
            source_root.root, f"{PACKAGES_DIR}/{name}/{entry['version']}"
        )
        payload_root = pkg_dir / manifest["payload"]["root"]
        recomputed = self._recompute_payload(payload_root, manifest)
        if recomputed != manifest["payload"]["digest"]:
            raise attempt.refuse(
                "payload-digest",
                f"payload on disk digests to {recomputed}, the signed manifest says "
                f"{manifest['payload']['digest']} -- the registry payload drifted",
            )
        attempt.record("payload-digest", "PASS", recomputed)

        # gate 10 -- SBOM -------------------------------------------------------
        self._gate_sbom(attempt, pkg_dir, payload_root, manifest)

        # gate 11 -- licence ----------------------------------------------------
        self._gate_license(attempt, pkg_dir, manifest)

        # gate 12 -- dependencies ----------------------------------------------
        deps = manifest.get("dependencies", [])
        for dep in deps:
            if (
                dep.get("optional")
                and reg.resolve(source_root.index, dep["name"], dep["range"]) is None
            ):
                continue
            self.install(
                dep["name"],
                dep["range"],
                channel=channel,
                allow_vulnerable=allow_vulnerable,
                allow_deprecated=allow_deprecated,
                frozen=frozen,
                now=at,
                requested_by=name,
                _in_progress=in_progress,
            )
        attempt.record(
            "dependencies", "PASS" if deps else "SKIP", f"{len(deps)} dependency/ies"
        )

        # deprecation is ADVISORY, never a refusal (see package-manifest.schema.json)
        if manifest.get("deprecation"):
            if not allow_deprecated:
                raise attempt.refuse(
                    "license", "package is deprecated and --no-deprecated was requested"
                )
            attempt.overrides.append("allow-deprecated")

        # gate 13a -- lockfile PIN CHECK, before a single byte is written --------
        # The frozen-drift check must happen BEFORE the copy. Ordered the other way (as an
        # earlier version of this module was), a --frozen refusal left the payload sitting in
        # the site with no state entry pointing at it: a half-installed package that every
        # later `installed()` read would deny existed.
        self._check_lockfile_pin(attempt, entry, manifest, frozen)

        # --- copy into the site ------------------------------------------------
        dest = self.site_root / PACKAGES_DIR / name / entry["version"]
        if dest.exists():
            shutil.rmtree(dest)
        try:
            dest.mkdir(parents=True, exist_ok=True)
            for f in manifest["payload"]["files"]:
                src = ensure_within(payload_root, f["path"])
                dst = ensure_within(dest, f["path"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            installed_digest = self._recompute_payload(dest, manifest)
            if installed_digest != manifest["payload"]["digest"]:
                raise attempt.refuse(
                    "payload-digest",
                    f"installed copy digests to {installed_digest}, expected {manifest['payload']['digest']}",
                )
        except BaseException:
            # ROLL THE COPY BACK. A refusal that leaves files behind is a refusal that half
            # installed the package, and the site would then hold bytes no receipt accounts for.
            shutil.rmtree(dest, ignore_errors=True)
            raise

        # gate 13b -- commit the lockfile ---------------------------------------
        self._commit_lockfile(attempt, source_root, entry, manifest, requested_by, at)

        state = self.installed()
        previous = state["packages"].get(name)
        if previous:
            attempt.previous = {
                "version": previous["version"],
                "payload_digest": previous["payload_digest"],
            }
        state["packages"][name] = {
            "version": entry["version"],
            "payload_digest": manifest["payload"]["digest"],
            "publisher": entry["publisher"],
            "permissions": manifest["permissions"],
            "files": len(manifest["payload"]["files"]),
            "installed_at": at,
            "registry_id": source_root.registry_id,
        }
        self._write_state(state)

        attempt.outcome = "SUCCESS"
        attempt.installed_files = len(manifest["payload"]["files"])
        attempt.payload_digest = manifest["payload"]["digest"]
        if allow_vulnerable:
            attempt.overrides.append("allow-vulnerable")
        attempt.assert_complete()
        receipt = attempt.receipt(registry_id=source_root.registry_id, at=at)
        self._append_journal(receipt)
        return receipt

    # ------------------------------------------------------------------ gates
    def _resolve(
        self,
        attempt: Attempt,
        name: str,
        range_text: str,
        channel: str | None,
        frozen: bool,
    ) -> tuple[reg.RegistryRoot, dict[str, Any]]:
        if frozen:
            lock = self.load_lockfile()
            if lock is None:
                raise attempt.refuse(
                    "lockfile", "--frozen requested but there is no lockfile"
                )
            pinned = next((p for p in lock["packages"] if p["name"] == name), None)
            if pinned is None:
                raise attempt.refuse(
                    "lockfile", f"--frozen: {name} is not in the lockfile"
                )
            range_text = f"={pinned['version']}"
        if self.view is not None:
            found = self.view.resolve(name, range_text, channel=channel)
            if found is None:
                raise attempt.refuse(
                    "dependencies",
                    f"no version of {name} satisfies {range_text!r}"
                    + (f" on channel {channel!r}" if channel else "")
                    + (
                        f"; mirror rows rejected: {self.view.rejected}"
                        if self.view.rejected
                        else ""
                    ),
                )
            return found
        entry = reg.resolve(self.index, name, range_text, channel=channel)
        if entry is None:
            raise attempt.refuse(
                "dependencies", f"no version of {name} satisfies {range_text!r}"
            )
        return reg.RegistryRoot(self.registry_root, self.index), entry

    def _gate_revocation(
        self,
        attempt: Attempt,
        source: reg.RegistryRoot,
        entry: dict[str, Any],
        pub_key: str,
    ) -> None:
        """FAIL-CLOSED. Absent list, unsigned list, or any match -> REFUSE."""
        revocation = reg.load_revocation(source.root, source.index)
        if revocation is None:
            if self.trust_policy["on_missing"]["revocation_list"] == "refuse":
                raise attempt.refuse(
                    "revocation",
                    "no revocation list is reachable for this registry and policy says refuse. "
                    "A revocation channel that can be removed to re-enable a revoked package is "
                    "not a revocation channel.",
                )
            attempt.record(
                "revocation", "WARN", "no revocation list; policy allows warn"
            )
            return
        maintainers = self.trust_policy["registry_maintainer_keys"]
        rev_key = (revocation.get("signature") or {}).get("public_key")
        ok, why = verify_document(
            revocation, "mkt.revocation.v1", expected_public_key=rev_key
        )
        if not ok or rev_key not in maintainers:
            raise attempt.refuse(
                "revocation",
                f"revocation list signature is not acceptable ({why or 'key is not a maintainer key'}) -- "
                "an unverifiable revocation list is treated as a refusal, never as an empty one",
            )
        hits = reg.revocations_for(
            revocation, entry["name"], entry["version"], public_key=pub_key
        )
        if hits:
            first = hits[0]
            raise attempt.refuse(
                "revocation",
                f"{entry['name']}@{entry['version']} is REVOKED by {first['revocation_id']} "
                f"({first['scope']['kind']} scope, severity {first['severity']}): {first['reason']}",
            )
        attempt.record(
            "revocation",
            "PASS",
            f"{len(revocation.get('revocations', []))} revocation(s) checked, none match",
        )

    def _gate_compatibility(self, attempt: Attempt, manifest: dict[str, Any]) -> None:
        platforms = manifest["compatibility"]["platforms"]
        if "any" not in platforms and self.platform_id not in platforms:
            raise attempt.refuse(
                "compatibility", f"platform {self.platform_id!r} not in {platforms}"
            )
        clients = manifest["compatibility"]["clients"]
        row = next((c for c in clients if c["id"] == self.client_id), None)
        if row is None:
            raise attempt.refuse(
                "compatibility",
                f"client {self.client_id!r} is not listed in the compatibility matrix "
                f"({[c['id'] for c in clients]})",
            )
        if not versions.satisfies(self.client_version, row["range"]):
            raise attempt.refuse(
                "compatibility",
                f"client {self.client_id} {self.client_version} does not satisfy {row['range']!r}",
            )
        attempt.record(
            "compatibility",
            "PASS",
            f"{self.platform_id}/{self.client_id} {self.client_version}",
        )

    def _gate_advisory(
        self,
        attempt: Attempt,
        source: reg.RegistryRoot,
        entry: dict[str, Any],
        allow_vulnerable: bool,
    ) -> None:
        advisories = reg.load_advisories(source.root, source.index)
        if advisories is None:
            if self.trust_policy["on_missing"]["advisory_list"] == "refuse":
                raise attempt.refuse(
                    "advisory", "no advisory list is reachable and policy says refuse"
                )
            attempt.record("advisory", "WARN", "no advisory list; policy allows warn")
            return
        adv_key = (advisories.get("signature") or {}).get("public_key")
        ok, why = verify_document(
            advisories, "mkt.advisory.v1", expected_public_key=adv_key
        )
        # The KEY must also be a declared maintainer key. Verifying a document against whatever
        # key signed it proves only internal consistency: an attacker who can write
        # advisories.json can re-sign a version with every advisory removed and it would verify
        # perfectly. This check was MISSING in the first version of this module -- the revocation
        # gate had it and the advisory gate did not, which is exactly the kind of asymmetry a
        # self-review is for.
        if not ok or adv_key not in self.trust_policy["registry_maintainer_keys"]:
            raise attempt.refuse(
                "advisory",
                f"advisory list signature is not acceptable "
                f"({why or 'key is not a declared registry-maintainer key'})",
            )
        open_adv = reg.open_advisories_for(advisories, entry["name"], entry["version"])
        ceiling = reg.severity_rank(
            self.trust_policy["thresholds"]["max_advisory_severity"]
        )
        blocking = [a for a in open_adv if reg.severity_rank(a["severity"]) > ceiling]
        if blocking:
            if not (
                allow_vulnerable and self.trust_policy.get("allow_vulnerable_override")
            ):
                worst = max(blocking, key=lambda a: reg.severity_rank(a["severity"]))
                raise attempt.refuse(
                    "advisory",
                    f"{len(blocking)} open advisory/ies above the {self.trust_policy['thresholds']['max_advisory_severity']!r} "
                    f"ceiling; worst {worst['advisory_id']} ({worst['severity']}): {worst['title']}",
                )
            attempt.record(
                "advisory",
                "WARN",
                f"{len(blocking)} blocking advisory/ies OVERRIDDEN by --allow-vulnerable (recorded in the receipt)",
            )
            return
        attempt.record(
            "advisory", "PASS", f"{len(open_adv)} open advisory/ies, none above ceiling"
        )

    def _gate_sbom(
        self,
        attempt: Attempt,
        pkg_dir: Path,
        payload_root: Path,
        manifest: dict[str, Any],
    ) -> None:
        sbom_path = ensure_within(pkg_dir, manifest["sbom_ref"])
        if not sbom_path.is_file():
            if self.trust_policy["on_missing"]["sbom"] == "refuse":
                raise attempt.refuse(
                    "sbom",
                    f"manifest declares an SBOM that does not exist: {sbom_path}",
                )
            attempt.record("sbom", "WARN", "no SBOM; policy allows warn")
            return
        doc = read_json(sbom_path)
        schemas.validate("sbom", doc)
        verdict = sbom_mod.verify(
            doc, payload_root, declared=manifest["payload"]["files"]
        )
        if not verdict.ok:
            raise attempt.refuse(
                "sbom", f"SBOM does not match the payload: {verdict.summary()}"
            )
        attempt.record("sbom", "PASS", verdict.summary())

    def _gate_license(
        self, attempt: Attempt, pkg_dir: Path, manifest: dict[str, Any]
    ) -> None:
        policy = self.trust_policy["license_policy"]
        declared = manifest["license"]["spdx"]
        denied = policy.get("denied_spdx", [])
        if declared in denied:
            raise attempt.refuse(
                "license", f"declared licence {declared!r} is denied by policy"
            )
        if declared not in policy["allowed_spdx"]:
            if policy.get("on_unknown", "refuse") == "refuse":
                raise attempt.refuse(
                    "license",
                    f"declared licence {declared!r} is not in the allowed set {policy['allowed_spdx']}",
                )
            attempt.record(
                "license", "WARN", f"licence {declared!r} unknown; policy allows warn"
            )
            return
        sbom_path = pkg_dir / manifest["sbom_ref"]
        component_licences: set[str] = set()
        if sbom_path.is_file():
            component_licences = set(
                sbom_mod.component_licenses(read_json(sbom_path)).values()
            )
        offenders = sorted(
            c
            for c in component_licences
            if c in denied or c not in policy["allowed_spdx"]
        )
        if offenders:
            raise attempt.refuse(
                "license",
                f"component licences {offenders} are not admissible under the policy even though the "
                f"aggregate declares {declared!r} -- this is the M1 misstatement shape",
            )
        attempt.record(
            "license",
            "PASS",
            f"aggregate {declared}; {len(component_licences)} component licence(s) admissible",
        )

    def _check_lockfile_pin(
        self,
        attempt: Attempt,
        entry: dict[str, Any],
        manifest: dict[str, Any],
        frozen: bool,
    ) -> None:
        """The REFUSE half of the lockfile gate, evaluated before anything is written."""
        if not frozen:
            return
        lock = self.load_lockfile()
        pinned = next(
            (p for p in (lock or {}).get("packages", []) if p["name"] == entry["name"]),
            None,
        )
        if pinned is None:
            return
        drift = []
        if pinned["version"] != entry["version"]:
            drift.append(f"version {pinned['version']} -> {entry['version']}")
        if pinned["manifest_digest"] != entry["manifest_digest"]:
            drift.append("manifest_digest")
        if pinned["payload_digest"] != manifest["payload"]["digest"]:
            drift.append("payload_digest")
        if drift:
            raise attempt.refuse(
                "lockfile",
                f"--frozen: {entry['name']} drifted from the lockfile ({', '.join(drift)}). "
                "A lockfile that tolerates digest drift is marketplace-first FM-2 re-opened.",
            )

    def _commit_lockfile(
        self,
        attempt: Attempt,
        source: reg.RegistryRoot,
        entry: dict[str, Any],
        manifest: dict[str, Any],
        requested_by: str,
        at: str,
    ) -> None:
        """The WRITE half, after the payload is on disk and its digest re-verified."""
        lock = self.load_lockfile() or {
            "schema_version": "1.0.0",
            "lockfile_version": 1,
            "registry_id": source.registry_id,
            "generated_at": at,
            "packages": [],
        }
        pinned = next((p for p in lock["packages"] if p["name"] == entry["name"]), None)
        row = {
            "name": entry["name"],
            "version": entry["version"],
            "manifest_digest": entry["manifest_digest"],
            "payload_digest": manifest["payload"]["digest"],
            "publisher": entry["publisher"],
            "permissions": manifest["permissions"],
            "requested_by": sorted(
                {requested_by, *(pinned or {}).get("requested_by", [])}
            ),
        }
        lock["packages"] = sorted(
            [p for p in lock["packages"] if p["name"] != entry["name"]] + [row],
            key=lambda p: p["name"],
        )
        lock["generated_at"] = at
        lock["index_digest"] = reg.index_digest(source.index)
        schemas.validate("lockfile", lock)
        write_json(self.lockfile_path, lock)
        attempt.record("lockfile", "PASS", f"{len(lock['packages'])} pinned package(s)")

    # ------------------------------------------------------------- other verbs
    def update(self, name: str, range_text: str = "*", **kwargs: Any) -> dict[str, Any]:
        """Install a newer version, keeping the previous one on disk for rollback."""
        state = self.installed()
        current = state["packages"].get(name)
        if current is None:
            raise InstallRefused(
                "dependencies", f"cannot update {name}: it is not installed"
            )
        receipt = self.install(name, range_text, **kwargs)
        receipt = dict(receipt)
        receipt["action"] = "update"
        receipt["previous"] = {
            "version": current["version"],
            "payload_digest": current["payload_digest"],
        }
        schemas.validate("install-receipt", receipt)
        self._rewrite_last_receipt(receipt)
        return receipt

    def remove(self, name: str, *, now: str | None = None) -> dict[str, Any]:
        at = now or iso_now()
        attempt = Attempt(action="remove", name=name)
        state = self.installed()
        current = state["packages"].pop(name, None)
        if current is None:
            attempt.outcome = "FAILED"
            attempt.record("dependencies", "REFUSE", "not installed")
            receipt = attempt.receipt(at=at)
            self._append_journal(receipt)
            return receipt
        dependants = [
            other
            for other, meta in state["packages"].items()
            if name in self._declared_dependencies(other, meta["version"])
        ]
        if dependants:
            state["packages"][name] = current
            attempt.outcome = "REFUSED"
            attempt.refusal_code = REFUSAL_CODES["dependencies"]
            attempt.record(
                "dependencies", "REFUSE", f"still required by {sorted(dependants)}"
            )
            receipt = attempt.receipt(at=at)
            self._append_journal(receipt)
            return receipt
        target = self.site_root / PACKAGES_DIR / name / current["version"]
        if target.exists():
            shutil.rmtree(target)
        attempt.version = current["version"]
        attempt.previous = {
            "version": current["version"],
            "payload_digest": current["payload_digest"],
        }
        attempt.outcome = "SUCCESS"
        attempt.record("dependencies", "PASS", "no dependants")
        self._write_state(state)
        receipt = attempt.receipt(at=at)
        self._append_journal(receipt)
        return receipt

    def health_check(self, *, now: str | None = None) -> dict[str, Any]:
        """Flag installed coordinates named by the registry's CURRENT revocation list.

        Reads the live revocation document at health-check time -- no cache and
        no manual refresh. An absent revocation list fails closed per the trust
        policy's ``on_missing.revocation_list``. Flags are hello-skill@1.0.0
        style coordinates so the output names the revoked package directly.
        """
        at = now or iso_now()
        index = reg.load_index(self.registry_root)
        doc = reg.load_revocation(self.registry_root, index)
        if doc is None:
            on_missing = str(
                (self.trust_policy.get("on_missing") or {}).get("revocation_list", "refuse")
            )
            refused = on_missing == "refuse"
            return {
                "outcome": "REFUSED" if refused else "SUCCESS",
                "code": "REVOCATION_LIST_ABSENT" if refused else "CLEAN",
                "flags": [],
                "checked": [],
                "revocations_considered": 0,
                "checked_at": at,
            }
        state = self.installed()
        flags: list[dict[str, Any]] = []
        checked: list[str] = []
        for name, meta in sorted((state.get("packages") or {}).items()):
            version = str(meta.get("version"))
            checked.append(f"{name}@{version}")
            for entry in doc.get("revocations") or []:
                scope = entry.get("scope") or {}
                if _revocation_hits(scope, name, version, str(meta.get("public_key", ""))):
                    flags.append(
                        {
                            "package": f"{name}@{version}",
                            "revocation_id": entry.get("revocation_id"),
                            "scope": scope,
                            "reason": entry.get("reason"),
                            "severity": entry.get("severity"),
                            "revoked_at": entry.get("revoked_at"),
                            "authority": entry.get("authority"),
                        }
                    )
        return {
            "outcome": "SUCCESS",
            "code": "REVOKED_FLAGGED" if flags else "CLEAN",
            "flags": flags,
            "checked": checked,
            "revocations_considered": len(doc.get("revocations") or []),
            "checked_at": at,
        }

    def rollback(
        self, name: str, *, now: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Return ``name`` to the version recorded in the most recent receipt that had one.

        Every gate runs again. If the previous version has been revoked since, rollback
        REFUSES -- a rollback path that skipped the gates would be the cheapest way to
        install a revoked package on this surface.
        """
        at = now or iso_now()
        previous_version = None
        for receipt in reversed(self.receipts()):
            if receipt["name"] == name and receipt.get("previous"):
                previous_version = receipt["previous"]["version"]
                break
        if previous_version is None:
            attempt = Attempt(action="rollback", name=name, outcome="FAILED")
            attempt.record(
                "lockfile", "REFUSE", "no previous version recorded in the journal"
            )
            receipt = attempt.receipt(at=at)
            self._append_journal(receipt)
            return receipt
        current = self.installed()["packages"].get(name, {}).get("version")
        out = self.install(name, f"={previous_version}", now=at, **kwargs)
        out = dict(out)
        out["action"] = "rollback"
        if current:
            out["previous"] = {
                "version": current,
                "payload_digest": self._digest_of_installed(name, current)
                or out["payload_digest"],
            }
        schemas.validate("install-receipt", out)
        self._rewrite_last_receipt(out)
        return out

    # ------------------------------------------------------------------ helpers
    def load_lockfile(self) -> dict[str, Any] | None:
        if not self.lockfile_path.is_file():
            return None
        doc = read_json(self.lockfile_path)
        schemas.validate("lockfile", doc)
        return doc

    def _recompute_payload(self, root: Path, manifest: dict[str, Any]) -> str:
        rows = []
        for f in manifest["payload"]["files"]:
            path = ensure_within(root, f["path"])
            if not path.is_file():
                return f"sha256:missing:{f['path']}"
            rows.append({"path": f["path"], "sha256": digest_file(path)})
        return payload_digest(rows)

    def _declared_dependencies(self, name: str, version: str) -> list[str]:
        entry = reg.resolve(self.index, name, f"={version}", include_yanked=True)
        if entry is None:
            return []
        try:
            manifest = reg.load_manifest(self.registry_root, entry)
        except reg.RegistryError:
            return []
        return [d["name"] for d in manifest.get("dependencies", [])]

    def _digest_of_installed(self, name: str, version: str) -> str | None:
        for receipt in reversed(self.receipts()):
            if (
                receipt["name"] == name
                and receipt.get("version") == version
                and receipt.get("payload_digest")
            ):
                return receipt["payload_digest"]
        return None

    def _rewrite_last_receipt(self, receipt: dict[str, Any]) -> None:
        """Replace the receipt just appended by ``install`` with the re-labelled one.

        ``update`` and ``rollback`` delegate to ``install`` so they cannot diverge on the
        gates; the journal must still record what the operator actually asked for.
        """
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        if lines:
            lines[-1] = reg.canonical_bytes(receipt).decode("utf-8")
        self.journal_path.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        if self.journal:
            self.journal[-1] = receipt


def read_json_line(line: str) -> dict[str, Any]:
    import json

    return json.loads(line)
