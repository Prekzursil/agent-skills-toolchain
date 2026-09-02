"""Per-check gameability grades derived from captured Scorecard / registry sources.

GAMEABLE: a publisher can collect the points with a local file, config, or
self-attested form and without changing the shipped product's actual risk.
RESISTANT: satisfying the check requires clearing an external measurement
(OSV/OSV-Scanner, real dependents, OSS-Fuzz onboarding) that a file-drop
does not reset.
MIXED: a cheap path and a resistant path coexist in the same check.
"""
from __future__ import annotations

SENTINEL = (
    "SUCCESS:RES-0057 in the receipt AND a per-check gameability grade "
    "where each gameable row carries its cheap-satisfaction recipe"
)
SENTINEL = SENTINEL

# Minimum set of capture needles the probes re-check so grades stay tied to bytes.
CAPTURE_NEEDLES = {
    "scorecard-checks.md": (
        "## License",
        "## Security-Policy",
        "## Vulnerabilities",
        "## Dependency-Update-Tool",
        "## Fuzzing",
        "OSV",
        "SECURITY.md",
        "Dependabot",
        "OSS-Fuzz",
        "does not verify the signatures",
    ),
    "scorecard-license.go": ("LICENSE", "COPYRIGHT"),
    "scorecard-securitypolicy.go": ("security.md", "isSecurityPolicyFilename"),
    "scorecard-vulnerabilities.go": ("ListUnfixedVulnerabilities",),
    "scorecard-fuzzing.go": ("OSSFuzz", "ClusterFuzzLite", "checkOSSFuzz"),
    "npms-quality.js": (
        "licenseEvaluation",
        "readmeEvaluation",
        "evaluateBranding",
        "evaluateHealth",
        "vulnerabilitiesCount",
    ),
    "npms-architecture.md": ("Has README", "Has license", "Has tests"),
    "librariesio-source-rank.rb": (
        "readme_present",
        "license_present",
        "one_point_oh",
        "follows_semver",
        "dependent_projects",
    ),
    "scorecard-api-ossf.json": (
        '"name":"License"',
        '"name":"Vulnerabilities"',
        "osv.dev",
        "SECURITY.md",
    ),
}


def _row(**kw):
    kw.setdefault("recipe_tokens", [])
    kw.setdefault("cheap_satisfaction_recipe", None)
    kw.setdefault("resistant_reason", None)
    return kw


ROWS: list[dict] = [
    _row(
        id="scorecard.Binary-Artifacts",
        family="openssf-scorecard",
        check="Binary-Artifacts",
        grade="GAMEABLE",
        recipe_tokens=["binary"],
        cheap_satisfaction_recipe=(
            "Cheap action: `git rm` every committed executable / `.class` / "
            "`.pyc` / minified runtime blob (or start a source-only repo). "
            "Scorecard awards 10 when the tree contains no detected binary "
            "files; it does not require reproducible builds. A publisher who "
            "never ships binaries in git maxes this check with zero product change."
        ),
        why="Absence-of-file check; remediation in checks.md is 'remove binaries'.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Branch-Protection",
        family="openssf-scorecard",
        check="Branch-Protection",
        grade="GAMEABLE",
        recipe_tokens=["force", "deletion"],
        cheap_satisfaction_recipe=(
            "Cheap action for the first Scorecard tier (3/10): in GitHub "
            "Settings → Branches, enable 'Prevent force pushes' and "
            "'Prevent deletions' on the default branch. No reviewer, no "
            "status check, and no admin-enforcement is required for that "
            "tier. Remaining tiers cost more, but a publisher can still "
            "show a non-zero Branch-Protection score from two checkboxes "
            "that do not change shipped code."
        ),
        why="Tiered GitHub settings; tier 1 is UI checkboxes, not engineering.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.CI-Tests",
        family="openssf-scorecard",
        check="CI-Tests",
        grade="GAMEABLE",
        recipe_tokens=["test", "github-actions"],
        cheap_satisfaction_recipe=(
            "Cheap action: add `.github/workflows/ci.yml` whose job name or "
            "check-run name contains `test` (or `github-actions`) and that "
            "`echo ok`. Scorecard looks for well-known CI names among recent "
            "commit statuses; it does not require that tests assert product "
            "behavior. An always-green no-op workflow satisfies the probe."
        ),
        why="Name-matching CI statuses, not test semantics.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.CII-Best-Practices",
        family="openssf-scorecard",
        check="CII-Best-Practices",
        grade="GAMEABLE",
        recipe_tokens=["bestpractices.dev", "passing"],
        cheap_satisfaction_recipe=(
            "Cheap action for 5/10: create a project at https://www.bestpractices.dev/ "
            "and self-attest the Passing questionnaire. Scorecard trusts the "
            "badge API; it does not re-verify the answers. Gold (10/10) is "
            "harder (multiple developers), but Passing is a form, not a fuzzer."
        ),
        why="Badge API + self-attestation; overlapping Scorecard checks are not re-run.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Code-Review",
        family="openssf-scorecard",
        check="Code-Review",
        grade="GAMEABLE",
        recipe_tokens=["review"],
        cheap_satisfaction_recipe=(
            "Cheap action: require a pull-request review and install a bot "
            "(or a second account) that auto-approves. Scorecard credits "
            "reviewed changesets; it does not require that the reviewer is a "
            "distinct human who read the diff. Prow/tide-style auto-LGTM "
            "and GitHub 'approve own PR via PAT' both clear the check."
        ),
        why="Review event presence, not reviewer independence.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Contributors",
        family="openssf-scorecard",
        check="Contributors",
        grade="GAMEABLE",
        recipe_tokens=["companies", "organizations"],
        cheap_satisfaction_recipe=(
            "Cheap action: commit with three email domains that look like "
            "distinct companies (`dev@acme.example`, `dev@contoso.example`, "
            "`dev@globex.example`). Scorecard infers 'companies or "
            "organizations' from commit metadata, not from employment."
        ),
        why="Org inference from git emails is spoofable.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Dangerous-Workflow",
        family="openssf-scorecard",
        check="Dangerous-Workflow",
        grade="RESISTANT",
        recipe_tokens=[],
        resistant_reason=(
            "The check parses GitHub Actions YAML for untrusted-checkout + "
            "write / script-injection patterns. Adding a dummy file does not "
            "clear a dangerous pattern that is already present; the publisher "
            "must change workflow semantics. Caveat (named, not hidden): a "
            "repo with zero workflows scores 10 by absence, so this is "
            "resistant for projects that already use GHA, not a universal bar."
        ),
        why="Semantic workflow analysis, not file presence.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Dependency-Update-Tool",
        family="openssf-scorecard",
        check="Dependency-Update-Tool",
        grade="GAMEABLE",
        recipe_tokens=["Dependabot", "Renovate"],
        cheap_satisfaction_recipe=(
            "Cheap action: commit `.github/dependabot.yml` (or `renovate.json`) "
            "for one ecosystem. checks.md states the check 'can determine only "
            "whether the dependency update tool is enabled; it does not ensure "
            "that the tool is run or that the tool's pull requests are merged.' "
            "Live API on ossf/scorecard reports 'detected update tool: Dependabot: "
            ".github/dependabot.yml'."
        ),
        why="Config-file presence; merge behavior not observed.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Fuzzing",
        family="openssf-scorecard",
        check="Fuzzing",
        grade="MIXED",
        recipe_tokens=["ClusterFuzzLite", "OSS-Fuzz"],
        cheap_satisfaction_recipe=(
            "Cheap path: add a ClusterFuzzLite workflow YAML, or a language "
            "fuzz entrypoint Scorecard already greps for (Go `Fuzz*` test, "
            "JS `fast-check`, Haskell QuickCheck). fuzzing.go treats "
            "ClusterFuzzLite and in-tree fuzz functions as success without "
            "Google review."
        ),
        resistant_reason=(
            "Resistant path: `checkOSSFuzz` requires the repository to appear "
            "on the OSS-Fuzz project list (Google onboarding / review). That "
            "path cannot be satisfied by dropping a YAML file in the publisher's "
            "own repo."
        ),
        why="One check, two detectors: YAML/grep vs third-party OSS-Fuzz membership.",
        structured_captures=["scorecard-fuzzing.go", "scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.License",
        family="openssf-scorecard",
        check="License",
        grade="GAMEABLE",
        recipe_tokens=["LICENSE", "COPYING", "COPYRIGHT"],
        cheap_satisfaction_recipe=(
            "Cheap action: `printf '%s\\n' 'MIT License' 'Permission is hereby "
            "granted...' > LICENSE` at repo root (or COPYING / COPYRIGHT / "
            "LICENSES/<SPDX>.txt). license.go matches those filenames; "
            "checks.md scores 6/10 for the name, 3/10 for top-level, 1/10 for "
            "OSI/FSF. Live API on ossf/scorecard: 'license file detected: LICENSE' "
            "score 10. No runtime behavior changes."
        ),
        why="Filename heuristics in license.go; live API confirms file-detect scoring.",
        structured_captures=["scorecard-license.go", "scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Maintained",
        family="openssf-scorecard",
        check="Maintained",
        grade="GAMEABLE",
        recipe_tokens=["commit", "90 days"],
        cheap_satisfaction_recipe=(
            "Cheap action: a scheduled GitHub Action that commits a timestamp "
            "to a junk file once a week for 90 days (or reopen/comment on "
            "issues as a collaborator). checks.md: highest score if there is "
            "at least one commit per week during the previous 90 days. Dummy "
            "commits satisfy the activity heuristic."
        ),
        why="Activity heuristic, not patch quality.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Packaging",
        family="openssf-scorecard",
        check="Packaging",
        grade="GAMEABLE",
        recipe_tokens=["GitHub Actions", "package"],
        cheap_satisfaction_recipe=(
            "Cheap action: add a GitHub Actions workflow that uploads an empty "
            "tarball to GitHub Packages / npm / PyPI (or goreleaser with a "
            "stub binary). Scorecard looks for packaging workflows, not for "
            "whether the artifact is useful or reviewed."
        ),
        why="Workflow-shape detection, not package quality.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Pinned-Dependencies",
        family="openssf-scorecard",
        check="Pinned-Dependencies",
        grade="GAMEABLE",
        recipe_tokens=["pin", "hash"],
        cheap_satisfaction_recipe=(
            "Cheap action: pin GitHub Actions and container images to any "
            "full-length hash SHA (`uses: owner/action@<40-hex>`). Scorecard does "
            "not check that the publisher reviewed the pinned object; copying "
            "a SHA from a compromised action still counts as pinned."
        ),
        why="Syntactic pin, not provenance review.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.SAST",
        family="openssf-scorecard",
        check="SAST",
        grade="GAMEABLE",
        recipe_tokens=["CodeQL", "codeql-action"],
        cheap_satisfaction_recipe=(
            "Cheap action: add `.github/workflows/codeql.yml` using "
            "`github/codeql-action` (or enable github-code-scanning). "
            "Scorecard looks for the Action / app name on recent PRs; it does "
            "not require that findings are fixed or that the query suite "
            "covers the language actually shipped."
        ),
        why="Tool-name presence, not finding remediation.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.SBOM",
        family="openssf-scorecard",
        check="SBOM",
        grade="GAMEABLE",
        recipe_tokens=["SBOM", "CycloneDX", "SPDX"],
        cheap_satisfaction_recipe=(
            "Cheap action: generate a CycloneDX or SPDX JSON (even from an "
            "empty package) and attach it as a release asset or commit it. "
            "checks.md awards 5/10 for any SBOM found and 5/10 more if it is "
            "a release artifact. Content accuracy is not verified."
        ),
        why="Artifact-name presence, not SBOM correctness.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Security-Policy",
        family="openssf-scorecard",
        check="Security-Policy",
        grade="GAMEABLE",
        recipe_tokens=["security.md", "SECURITY.md"],
        cheap_satisfaction_recipe=(
            "Cheap action: commit `SECURITY.md` (or `.github/security.md`) "
            "containing (1) an email or https URL, (2) extra prose, (3) the "
            "substrings `vuln` and `disclos` plus a number of days. "
            "isSecurityPolicyFilename() is a case-insensitive name match; "
            "content scoring is keyword hits. Live API on ossf/scorecard: "
            "'security policy file detected: SECURITY.md' score 10."
        ),
        why="Filename + keyword heuristics; live API file-detect scoring.",
        structured_captures=["scorecard-securitypolicy.go", "scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Signed-Releases",
        family="openssf-scorecard",
        check="Signed-Releases",
        grade="GAMEABLE",
        recipe_tokens=[".asc", ".intoto.jsonl", "does not verify the signatures"],
        cheap_satisfaction_recipe=(
            "Cheap action: attach any `*.asc` / `*.sig` / `*.minisig` / "
            "`*.intoto.jsonl` next to the last five release archives, signed "
            "with a key nobody pins. checks.md: 'Note: The check does not "
            "verify the signatures.' Provenance filename `.intoto.jsonl` "
            "alone raises the score to 10."
        ),
        why="Signature-file presence; cryptographic verify is explicitly out of scope.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Token-Permissions",
        family="openssf-scorecard",
        check="Token-Permissions",
        grade="GAMEABLE",
        recipe_tokens=["permissions", "contents: read"],
        cheap_satisfaction_recipe=(
            "Cheap action: set top-level `permissions: { contents: read }` "
            "(or `read-all`) in each workflow YAML. Job-level writes can "
            "remain; composite actions may still escalate. Scorecard grades "
            "the YAML permissions block, not the effective token after "
            "reusable workflows."
        ),
        why="Static YAML permissions, not runtime token graph.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Vulnerabilities",
        family="openssf-scorecard",
        check="Vulnerabilities",
        grade="RESISTANT",
        recipe_tokens=["ListUnfixedVulnerabilities", "OSV"],
        resistant_reason=(
            "Scorecard calls VulnerabilitiesClient.ListUnfixedVulnerabilities "
            "on the commit + local path (OSV / OSV-Scanner). Adding LICENSE "
            "or SECURITY.md does not clear OSV hits. Live structured probe "
            "on github.com/ossf/scorecard: License=10 and Security-Policy=10 "
            "while Vulnerabilities=0 with 61 osv.dev IDs listed. Caveats "
            "(named): `osv-scanner.toml` ignore IDs, and a tree with no "
            "lockfile / no OSV-indexed packages can get a free pass — still "
            "not a file-drop satisfaction of an existing known vuln."
        ),
        why="External OSV measurement; same-repo API differential vs file-drop checks.",
        structured_captures=["scorecard-vulnerabilities.go", "scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="scorecard.Webhooks",
        family="openssf-scorecard",
        check="Webhooks",
        grade="GAMEABLE",
        recipe_tokens=["secret", "webhook"],
        cheap_satisfaction_recipe=(
            "Cheap action: either configure no repo webhooks (vacuous pass) "
            "or set any secret string on existing webhooks. Scorecard checks "
            "that a token is configured, not that it is rotated or verified "
            "server-side."
        ),
        why="Presence of a webhook secret, not authenticity of the receiver.",
        structured_captures=["scorecard-api-ossf.json"],
        prose_captures=["scorecard-checks.md"],
    ),
    _row(
        id="npms.quality.carefulness",
        family="registry-npms",
        check="npms-quality-carefulness",
        grade="GAMEABLE",
        recipe_tokens=["licenseEvaluation", "readmeEvaluation"],
        cheap_satisfaction_recipe=(
            "Cheap action: set `license` in package.json, write a README ≥400 "
            "bytes, add an eslint config, a `.npmignore`, a CHANGELOG, and "
            "publish `1.0.0`. quality.js evaluateCarefulness (licenseEvaluation + "
            "readmeEvaluation) is a weighted sum "
            "of those booleans/sizes times a 1.0.0 stability flag. architecture.md "
            "lists 'Has README? Has license?' as quality attributes."
        ),
        why="npms quality.js carefulness is documentation/metadata presence.",
        structured_captures=["npms-quality.js"],
        prose_captures=["npms-architecture.md"],
    ),
    _row(
        id="npms.quality.branding",
        family="registry-npms",
        check="npms-quality-branding",
        grade="GAMEABLE",
        recipe_tokens=["evaluateBranding", "badges"],
        cheap_satisfaction_recipe=(
            "Cheap action: add four README badges and a homepage URL whose "
            "host differs from the repository host. evaluateBranding is "
            "0.4*customHomepage + 0.6*badgeCount(normalized to 4). The "
            "itnext writeup of npms search score documents this exact cheap path."
        ),
        why="Badge count and homepage host inequality.",
        structured_captures=["npms-quality.js"],
        prose_captures=["npms-architecture.md"],
    ),
    _row(
        id="npms.quality.tests",
        family="registry-npms",
        check="npms-quality-tests",
        grade="GAMEABLE",
        recipe_tokens=["testsSize", "hasTestScript"],
        cheap_satisfaction_recipe=(
            "Cheap action: add a hasTestScript `test` script and ≥400 bytes under a test "
            "path (even `assert(true)`). evaluateTests weights testsSize 0.6; "
            "coverage and CI status can stay empty/pending."
        ),
        why="Byte-size of tests directory, not assertion strength.",
        structured_captures=["npms-quality.js"],
        prose_captures=["npms-architecture.md"],
    ),
    _row(
        id="npms.quality.health",
        family="registry-npms",
        check="npms-quality-health",
        grade="MIXED",
        recipe_tokens=["vulnerabilitiesCount", "dependenciesCount"],
        cheap_satisfaction_recipe=(
            "Cheap path: publish with zero runtime dependencies. evaluateHealth "
            "returns 1 immediately when dependenciesCount===0, which is a "
            "perfect health score for an empty package."
        ),
        resistant_reason=(
            "Once real dependencies exist, vulnerabilitiesCount is drawn from "
            "an advisory feed and cannot be cleared by adding a README. That "
            "sub-score is the resistant slice; the zero-dep short-circuit is "
            "the game."
        ),
        why="Health mixes advisory counts with a no-deps free pass.",
        structured_captures=["npms-quality.js"],
        prose_captures=["npms-architecture.md"],
    ),
    _row(
        id="librariesio.sourcerank.presence",
        family="registry-librariesio",
        check="SourceRank-presence-points",
        grade="GAMEABLE",
        recipe_tokens=["readme_present", "license_present", "one_point_oh", "follows_semver"],
        cheap_satisfaction_recipe=(
            "Cheap action: add a README, declare a license, publish 1.0.0, "
            "follow SemVer, fill description+homepage+keywords, and tag two "
            "versions. source_rank.rb awards 1 point each for "
            "basic_info_present, repository_present, readme_present, "
            "license_present, versions_present, follows_semver, "
            "recent_release, not_brand_new, one_point_oh. SourceBroken "
            "(alphaxiv 2512.24400) models the same 1-point presence metrics "
            "as trivially attacker-settable."
        ),
        why="One-point presence flags in source_rank.rb.",
        structured_captures=["librariesio-source-rank.rb"],
        prose_captures=["npms-architecture.md"],
    ),
    _row(
        id="librariesio.sourcerank.dependents",
        family="registry-librariesio",
        check="SourceRank-dependent-projects",
        grade="RESISTANT",
        recipe_tokens=["dependent_projects", "log_scale"],
        resistant_reason=(
            "source_rank.rb sets dependent_projects to log_scale(dependents_count)*2 "
            "(Math.log10) "
            "and dependent_repositories to log10(dependent_repos_count). Those "
            "counts come from other packages declaring a dependency. Adding a "
            "LICENSE does not mint dependents. Stars/contributors are more "
            "gameable (bought stars); dependents are the resistant core of "
            "SourceRank. SourceRank 2.0 issue 1916 itself flags download-count "
            "hammering as a game to avoid — dependents are the harder column."
        ),
        why="Log-scaled real dependent counts, not presence flags.",
        structured_captures=["librariesio-source-rank.rb"],
        prose_captures=["npms-architecture.md"],
    ),
]


def rows_by_grade(grade: str) -> list[dict]:
    return [r for r in ROWS if r["grade"] == grade]


def gameable_rows() -> list[dict]:
    return [r for r in ROWS if r["grade"] in {"GAMEABLE", "MIXED"}]


def resistant_rows() -> list[dict]:
    return [r for r in ROWS if r["grade"] in {"RESISTANT", "MIXED"}]


CAPTURE_NEEDLES = CAPTURE_NEEDLES
gameable_rows = gameable_rows
resistant_rows = resistant_rows
