"""Executable models of published 'definition of done' predicates.

Each predicate is a function of an Observation. The estate's twelve-condition
AND-reducer is listed as TWELVE; published systems are scored against it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal

Verdict = Literal["COMPLETE", "INCOMPLETE"]
Ezma = Literal["MISS", "CATCH"]

TWELVE = [
    "1.process_reached_valid_terminal_state",
    "2.expected_artifact_exists",
    "3.artifact_nonempty_above_min_bytes",
    "4.artifact_parses_against_schema",
    "5.required_sentinel_present",
    "6.required_evidence_anchors_exist",
    "7.required_tests_ran_and_passed",
    "8.negative_controls_or_mutations_fail_as_expected",
    "9.independent_reviewer_status_is_PASS",
    "10.no_unresolved_P0_P1_defect_attached",
    "11.output_registered_in_artifact_manifest",
    "12.downstream_consumers_can_read_it",
]


@dataclass(frozen=True)
class Observation:
    """A work-unit outcome as seen by a completion predicate."""

    process_exit_code: int
    artifact_exists: bool
    artifact_bytes: int
    artifact_schema_ok: bool
    sentinel_present: bool
    evidence_anchors_ok: bool
    tests_passed: bool
    negative_controls_fired: bool
    reviewer_pass: bool
    unresolved_p0_p1: bool
    registered_in_manifest: bool
    downstream_read_ok: bool
    provenance_emitted: bool = False
    in_toto_require_named: bool = True
    gha_continue_on_error: bool = False
    upload_if_no_files: str = "warn"


# Estate exit-zero-missing-artifact case (ADV-0003 / catalog control).
EZMA = Observation(
    process_exit_code=0,
    artifact_exists=False,
    artifact_bytes=0,
    artifact_schema_ok=False,
    sentinel_present=False,
    evidence_anchors_ok=False,
    tests_passed=True,
    negative_controls_fired=False,
    reviewer_pass=False,
    unresolved_p0_p1=False,
    registered_in_manifest=False,
    downstream_read_ok=False,
    provenance_emitted=True,
    in_toto_require_named=True,
    gha_continue_on_error=False,
    upload_if_no_files="warn",
)


def _exit0(obs: Observation) -> Verdict:
    return "COMPLETE" if obs.process_exit_code == 0 else "INCOMPLETE"


def posix_exit(obs: Observation) -> Verdict:
    """POSIX/ISO C: termination status 0 / EXIT_SUCCESS is success. No artifact check."""
    return _exit0(obs)


def pytest_exit(obs: Observation) -> Verdict:
    """pytest ExitCode.OK == 0: collected tests passed. No catalog-artifact check."""
    return "COMPLETE" if obs.process_exit_code == 0 and obs.tests_passed else "INCOMPLETE"


def gha_job(obs: Observation) -> Verdict:
    """GitHub Actions job: step result is the process exit code; default Result is Succeeded."""
    if obs.gha_continue_on_error:
        return "COMPLETE"
    return _exit0(obs)


def gha_upload_artifact(obs: Observation) -> Verdict:
    """actions/upload-artifact@v4 default if-no-files-found=warn: missing files do not fail."""
    if obs.upload_if_no_files == "error" and not obs.artifact_exists:
        return "INCOMPLETE"
    return _exit0(obs)


def gitlab_job(obs: Observation) -> Verdict:
    """GitLab CI job success is the script result; artifacts:when on_success uploads after success."""
    return _exit0(obs)


def gnu_make(obs: Observation) -> Verdict:
    """GNU Make: recipe line succeeds iff shell exit status is zero. Target file not required."""
    return _exit0(obs)


def k8s_job(obs: Observation) -> Verdict:
    """Kubernetes Job: container exit 0 counts as succeeded toward .spec.completions."""
    return _exit0(obs)


def slsa_build_l1(obs: Observation) -> Verdict:
    """SLSA Build L1: provenance exists describing how a package was built. Not a named-output gate."""
    return "COMPLETE" if obs.provenance_emitted else "INCOMPLETE"


def in_toto_require(obs: Observation) -> Verdict:
    """in-toto REQUIRE rule: named artifact must appear in the products queue."""
    if obs.in_toto_require_named and not obs.artifact_exists:
        return "INCOMPLETE"
    return "COMPLETE"


def estate_twelve(obs: Observation) -> Verdict:
    """This program's twelve-condition AND-reducer. Exit 0 alone cannot return COMPLETE."""
    checks = [
        obs.process_exit_code == 0,
        obs.artifact_exists,
        obs.artifact_bytes > 0,
        obs.artifact_schema_ok,
        obs.sentinel_present,
        obs.evidence_anchors_ok,
        obs.tests_passed,
        obs.negative_controls_fired,
        obs.reviewer_pass,
        not obs.unresolved_p0_p1,
        obs.registered_in_manifest,
        obs.downstream_read_ok,
    ]
    return "COMPLETE" if all(checks) else "INCOMPLETE"


@dataclass(frozen=True)
class PublishedPredicate:
    id: str
    system: str
    definition_of_done: str
    apply: Callable[[Observation], Verdict]
    covers_twelve: tuple[int, ...]
    missed_failure: str
    missed_failure_scenario: str
    rails: tuple[str, str]
    quotes: tuple[str, str]
    permalinks: tuple[str, str]


PREDICATES: tuple[PublishedPredicate, ...] = (
    PublishedPredicate(
        id="posix_exit",
        system="POSIX.1 / ISO C exit()",
        definition_of_done="Process termination with status 0 or EXIT_SUCCESS.",
        apply=posix_exit,
        covers_twelve=(1,),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "A worker calls exit(0) / EXIT_SUCCESS without creating the catalog "
            "output_path. wait/waitpid reports success. No path, size, schema, "
            "sentinel, or reviewer check exists in the predicate."
        ),
        rails=("glibc-exit.c", "posix-exit.html"),
        quotes=(
            "_exit (status);",
            "may be 0, EXIT_SUCCESS, EXIT_FAILURE",
        ),
        permalinks=(
            "https://raw.githubusercontent.com/bminor/glibc/glibc-2.40/stdlib/exit.c",
            "https://pubs.opengroup.org/onlinepubs/9699919799/functions/exit.html",
        ),
    ),
    PublishedPredicate(
        id="pytest_exit",
        system="pytest 8.3.4 ExitCode",
        definition_of_done="Exit code 0: all tests collected and passed successfully.",
        apply=pytest_exit,
        covers_twelve=(1, 7),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "pytest collects and passes tests (exit 0) while the catalog JSON "
            "the unit contracted to emit is never written. ExitCode.OK does not "
            "name an output path."
        ),
        rails=("pytest-exit-codes-api.json", "pytest-exit-codes.rst"),
        quotes=(
            "doc/en/reference/exit-codes.rst",
            ":Exit code 0: All tests were collected and passed successfully",
        ),
        permalinks=(
            "https://api.github.com/repos/pytest-dev/pytest/contents/doc/en/reference/exit-codes.rst?ref=8.3.4",
            "https://raw.githubusercontent.com/pytest-dev/pytest/8.3.4/doc/en/reference/exit-codes.rst",
        ),
    ),
    PublishedPredicate(
        id="gha_job",
        system="GitHub Actions job/step conclusion",
        definition_of_done="Step/job Succeeded from the command exit code; default Result is Succeeded.",
        apply=gha_job,
        covers_twelve=(1,),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "A workflow step's last command exits 0. The runner records Succeeded "
            "even when the catalog output_path was never created. continue-on-error "
            "can additionally remap Failed to Succeeded."
        ),
        rails=("gha-runner-execution-context.cs", "gha-workflow-syntax.html"),
        quotes=(
            "_record.Result = _record.Result ?? TaskResult.Succeeded;",
            "The runner will report the status of the step as fail/succeed based on this exit code.",
        ),
        permalinks=(
            "https://raw.githubusercontent.com/actions/runner/v2.321.0/src/Runner.Worker/ExecutionContext.cs",
            "https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions",
        ),
    ),
    PublishedPredicate(
        id="gha_upload_artifact",
        system="actions/upload-artifact@v4",
        definition_of_done="Upload named paths; default if-no-files-found=warn does not fail the action.",
        apply=gha_upload_artifact,
        covers_twelve=(),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "upload-artifact runs after a green step. The path glob matches nothing. "
            "Default if-no-files-found=warn prints a warning and the action succeeds, "
            "so the job stays green with no artifact."
        ),
        rails=("gha-upload-artifact-action.yml", "gha-upload-artifact-readme.md"),
        quotes=(
            "default: 'warn'",
            "If a path (or paths), result in no files being found for the artifact, the action will succeed but print out a warning.",
        ),
        permalinks=(
            "https://raw.githubusercontent.com/actions/upload-artifact/v4.6.0/action.yml",
            "https://raw.githubusercontent.com/actions/upload-artifact/v4.6.0/README.md",
        ),
    ),
    PublishedPredicate(
        id="gitlab_job",
        system="GitLab CI job + artifacts:when",
        definition_of_done="Job success is the script result; artifacts upload on_success after the job already succeeded.",
        apply=gitlab_job,
        covers_twelve=(1,),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "The job script echoes ok and exits 0 without writing artifacts:paths. "
            "on_success means uploads happen only when the job already succeeded; "
            "missing paths do not rewrite that success into failure."
        ),
        rails=("gitlab-job-control.md", "gitlab-yaml-artifacts.html"),
        quotes=(
            "succeed even if all of its manual jobs fail.",
            "on_success</code> (default): Upload artifacts only when the job succeeds.",
        ),
        permalinks=(
            "https://gitlab.com/gitlab-org/gitlab/-/raw/v17.7.0-ee/doc/ci/jobs/job_control.md",
            "https://docs.gitlab.com/ci/yaml/#artifacts",
        ),
    ),
    PublishedPredicate(
        id="gnu_make",
        system="GNU Make recipe status",
        definition_of_done="A recipe line succeeds iff the shell exit status is zero.",
        apply=gnu_make,
        covers_twelve=(1,),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "A recipe runs `true` (or a compiler that exits 0) and never creates "
            "the target file. Make treats the rule as finished because the shell "
            "exit status is zero. This run exits 0 with the expected file absent."
        ),
        rails=("make-job.c", "make-errors.html"),
        quotes=(
            "if (exit_sig == 0 && exit_code == 0)",
            "If the shell completed successfully (the exit status is",
        ),
        permalinks=(
            "https://raw.githubusercontent.com/mirror/make/master/src/job.c",
            "https://www.gnu.org/software/make/manual/html_node/Errors.html",
        ),
    ),
    PublishedPredicate(
        id="k8s_job",
        system="Kubernetes Job",
        definition_of_done="Container exit code 0 means the container succeeded; Job Complete when completions are met.",
        apply=k8s_job,
        covers_twelve=(1,),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "A Job pod's container writes nothing to a volume and exits 0. The Job "
            "controller increments succeeded toward .spec.completions. No check "
            "that a named output object exists."
        ),
        rails=("k8s-job-controller-api.json", "k8s-job.md"),
        quotes=(
            "pkg/controller/job/job_controller.go",
            "an exit code of 0 means that the container succeeded",
        ),
        permalinks=(
            "https://api.github.com/repos/kubernetes/kubernetes/contents/pkg/controller/job/job_controller.go?ref=v1.32.1",
            "https://raw.githubusercontent.com/kubernetes/website/release-1.32/content/en/docs/concepts/workloads/controllers/job.md",
        ),
    ),
    PublishedPredicate(
        id="slsa_build_l1",
        system="SLSA Build L1",
        definition_of_done="Provenance exists showing how the package was built (digest + build description).",
        apply=slsa_build_l1,
        covers_twelve=(),
        missed_failure="exit-zero-missing-artifact",
        missed_failure_scenario=(
            "A build platform emits SLSA provenance whose subject is whatever the "
            "builder hashed after an exit-0 run. L1 requires provenance to exist; "
            "it does not require a prior contracted catalog path, schema, sentinel, "
            "or reviewer PASS. The estate EZMA worker can still mint provenance."
        ),
        rails=("slsa-v1-levels-api.json", "slsa-v1-levels.md"),
        quotes=(
            "docs/spec/v1.0/levels.md",
            "Provenance showing how the package was built",
        ),
        permalinks=(
            "https://api.github.com/repos/slsa-framework/slsa/contents/docs/spec/v1.0/levels.md?ref=v1.0.0",
            "https://raw.githubusercontent.com/slsa-framework/slsa/v1.0.0/docs/spec/v1.0/levels.md",
        ),
    ),
    PublishedPredicate(
        id="in_toto_require",
        system="in-toto layout REQUIRE rule",
        definition_of_done="Named artifact must appear as a material or product of the step.",
        apply=in_toto_require,
        covers_twelve=(2,),
        missed_failure="empty-or-schema-invalid-product",
        missed_failure_scenario=(
            "REQUIRE only checks that the filename is in the products queue. An "
            "empty file, a schema-invalid JSON, a missing sentinel, absent "
            "evidence anchors, skipped negative controls, no reviewer, open P0, "
            "unregistered manifest row, or unreadable downstream copy all still "
            "satisfy REQUIRE."
        ),
        rails=("in-toto-verifylib.py", "in-toto-spec.md"),
        quotes=(
            "if filename not in artifacts_queue:",
            "the specified artifact must appear as a material",
        ),
        permalinks=(
            "https://raw.githubusercontent.com/in-toto/in-toto/v2.2.0/in_toto/verifylib.py",
            "https://raw.githubusercontent.com/in-toto/docs/master/in-toto-spec.md",
        ),
    ),
)


def ezma_result(p: PublishedPredicate) -> Ezma:
    return "MISS" if p.apply(EZMA) == "COMPLETE" else "CATCH"


def coverage_row(p: PublishedPredicate) -> dict:
    covered = set(p.covers_twelve)
    return {
        "predicate_id": p.id,
        "system": p.system,
        "covers": [TWELVE[i - 1] for i in p.covers_twelve],
        "does_not_cover": [c for i, c in enumerate(TWELVE, 1) if i not in covered],
        "covers_all_twelve": covered == set(range(1, 13)),
        "ezma": ezma_result(p),
        "verdict_on_ezma": p.apply(EZMA),
        "missed_failure": p.missed_failure,
        "missed_failure_scenario": p.missed_failure_scenario,
    }


def table() -> list[dict]:
    return [coverage_row(p) for p in PREDICATES]


def any_equivalent_to_twelve() -> bool:
    return any(set(p.covers_twelve) == set(range(1, 13)) for p in PREDICATES)


def observation_dict() -> dict:
    return asdict(EZMA)
