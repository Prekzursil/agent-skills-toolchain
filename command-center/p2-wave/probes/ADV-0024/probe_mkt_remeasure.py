#!/usr/bin/env python3
"""ADV-0024 mkt-lane re-measure (2026-10-21): packager refusal test against the LIVE
platform/marketplace tree.

The 2026-08-19 measurement ran mkt lanes from a durable vendored SUT because the
sparse Linux worktree lacked platform/marketplace. The 2026-10-21 tree at c119cf0da
CONTAINS platform/marketplace, so this probe closes the NOT-CHECKED residual by
re-executing the abuse matrix through the real publish path:

  control  : unmodified fixture source publishes (harness not failing everything)
  B-cred-u : UNDECLARED token-shaped file added to payload  -> expect refusal (MKT-P03)
  B-cred-d : DECLARED token-shaped file (provider prefix)   -> expect refusal (MKT-P06)
  B-env    : DECLARED file with prefixed env assignment     -> record accept/refuse
  B-git    : DECLARED .git tree member                      -> record accept/refuse
  B-blob   : DECLARED 2 MiB blob                            -> record accept/refuse (byte ceiling?)

All tokens are SYNTHETIC non-authenticating values (catalog tests_required: "the token
fixture uses a synthetic non-authenticating value; no live credential is used at any
point"). For every accepted publish, the emitted registry payload is enumerated with an
independent os.walk (shares no code with mkt's bundler) so silent inclusion/exclusion is
distinguished from refusal.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'platform' / 'marketplace'))

from mkt import fixture, publish  # noqa: E402

SYNTH_TOKEN = "ghp_" + "SyntheticNonAuthenticatingValueADV0024"  # 43 chars, never valid
SYNTH_PAT = "github_pat_" + "SYNTHETICADV0024NOTAREALTOKEN1111222233334444"


def variant(src_root: Path, name: str, mutate) -> Path:
    """Copy the fixture hello-skill source and apply a mutation."""
    dst = src_root.parent / f"adv0024-{name}-1.0.0"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src_root, dst)
    mutate(dst)
    return dst


def declare(pkg: Path, extra_files: list[str]) -> None:
    pj = json.loads((pkg / "package.json").read_text(encoding="utf-8"))
    pj["payload_files"] = sorted(set(pj["payload_files"]) | set(extra_files))
    pj["file_licenses"].update({f: "MIT" for f in extra_files})
    (pkg / "package.json").write_text(json.dumps(pj, indent=2) + "\n", encoding="utf-8")


def run_lane(label: str, pkg: Path, built: dict) -> dict:
    rec: dict = {"lane": label, "package": pkg.name}
    try:
        result = publish.publish_into(
            pkg,
            built["registry_root"],
            secret_hex=built["root_secret_hex"],
            publisher_id="pub:alpha-tools",
            maintainer_secret_hex=built["root_secret_hex"],
            trust_policy=built["trust_policy"],
            governance=built["governance"],
            license_basis_path=REPO / "platform/marketplace/fixture/LICENSE",
        )
        rec["published"] = True
        rec["payload_files"] = result.payload_files
        rec["warnings"] = [str(w) for w in result.warnings]
        # independent member enumeration from the emitted registry tree
        base = Path(built["registry_root"]) / "packages" / result.name / result.version
        members = sorted(str(p.relative_to(base)).replace("\\", "/")
                         for p in base.rglob("*") if p.is_file())
        rec["emitted_members"] = members
    except publish.PublishRefused as exc:
        rec["published"] = False
        rec["code"] = exc.code
        rec["message"] = str(exc)[:300]
        rec["finding_rules"] = sorted({f.rule for f in exc.findings})
    except Exception as exc:  # noqa: BLE001
        rec["published"] = False
        rec["code"] = f"UNEXPECTED:{type(exc).__name__}"
        rec["message"] = str(exc)[:300]
    return rec


def main() -> int:
    out: dict = {"probe": "ADV-0024 mkt-lane live re-measure", "date": "2026-10-21",
                 "repo_head": "c119cf0da", "lanes": []}
    with tempfile.TemporaryDirectory(prefix="adv0024-mkt-") as tmp:
        work = Path(tmp)
        built = fixture.build(work, now=fixture.T0)
        src = built["sources"] / "hello-skill-1.0.0"

        # control: unmodified source must publish
        out["lanes"].append(run_lane("CONTROL-clean-publish", src, built))

        # B-cred-u: undeclared token-shaped file
        def m_und(pkg):
            (pkg / "payload" / "token.txt").write_text("token " + SYNTH_TOKEN + "\n", encoding="utf-8")
        out["lanes"].append(run_lane("B-cred-undeclared", variant(src, "credu", m_und), built))

        # B-cred-d: declared provider-prefixed token
        def m_decd(pkg):
            (pkg / "payload" / "token2.txt").write_text("value: " + SYNTH_PAT + "\n", encoding="utf-8")
            declare(pkg, ["token2.txt"])
        out["lanes"].append(run_lane("B-cred-declared-prefix", variant(src, "credd", m_decd), built))

        # B-env: declared file with prefixed env assignment
        def m_env(pkg):
            (pkg / "payload" / "settings.env").write_text("DB_PASSWORD=SYNTHETIC_ENV_SECRET_2026\n", encoding="utf-8")
            declare(pkg, ["settings.env"])
        out["lanes"].append(run_lane("B-env-declared", variant(src, "envd", m_env), built))

        # B-git: declared .git tree
        def m_git(pkg):
            (pkg / "payload" / ".git").mkdir(exist_ok=True)
            (pkg / "payload" / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (pkg / "payload" / ".git" / "config").write_text("[core]\n", encoding="utf-8")
            declare(pkg, [".git/HEAD", ".git/config"])
        out["lanes"].append(run_lane("B-git-declared", variant(src, "gitd", m_git), built))

        # B-blob: declared 2 MiB blob (byte-ceiling probe; Aug found NO ceiling -> D4)
        def m_blob(pkg):
            (pkg / "payload" / "big.bin").write_bytes(b"A" * (2 * 1024 * 1024))
            declare(pkg, ["big.bin"])
        out["lanes"].append(run_lane("B-blob-2MiB-declared", variant(src, "blobd", m_blob), built))

    print("ADV0024_MKT_BEGIN")
    print(json.dumps(out, indent=2, sort_keys=True))
    print("ADV0024_MKT_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
