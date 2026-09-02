"""RES-0161 engine/feature tables, source URLs, and necessity rulings.

Presence is not trusted from this file alone: grade.py re-checks needles
against captured bytes. Necessity is about AgentSpec blueprint families,
not about which CI engine is fashionable.
"""
from __future__ import annotations

UNIT = "RES-0161"
OUT_REL = "command-center/research/prior-art/RES-0161-workflow-dsl-feature-matrix.json"
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
SENTINEL = "SUCCESS:RES-0161"
QUESTION = (
    "Across Argo Workflows, Temporal, Airflow, Prefect, Dagster, AWS Step "
    "Functions and GitHub Actions: which DSL features (typed params, "
    "conditionals, sub-workflows, matrix expansion, artifacts, retries, "
    "timeouts, manual approval) are present in each, and which subset is "
    "strictly necessary to express our required blueprint categories "
    "without escaping to arbitrary code?"
)

ENGINES: tuple[str, ...] = (
    "argo",
    "temporal",
    "airflow",
    "prefect",
    "dagster",
    "aws-stepfunctions",
    "github-actions",
)

FEATURES: tuple[str, ...] = (
    "typed_params",
    "conditionals",
    "sub_workflows",
    "matrix_expansion",
    "artifacts",
    "retries",
    "timeouts",
    "manual_approval",
)

# Six families named by IMP-0178 in the work-unit catalog (USER-PROMPTS.md
# is absent on this worktree). 15+21+12+15+16+17 = 96.
BLUEPRINT_FAMILIES = (
    {
        "id": "research-evidence",
        "n": 15,
        "label": "research/evidence",
        "catalog_token": "research/evidence 15",
    },
    {
        "id": "engineering-reliability",
        "n": 21,
        "label": "engineering/reliability",
        "catalog_token": "engineering/reliability 21",
    },
    {
        "id": "security-governance",
        "n": 12,
        "label": "security/governance",
        "catalog_token": "security/governance 12",
    },
    {
        "id": "product-design",
        "n": 15,
        "label": "product/design",
        "catalog_token": "product/design 15",
    },
    {
        "id": "data-science",
        "n": 16,
        "label": "data/science",
        "catalog_token": "data/science 16",
    },
    {
        "id": "collective-intelligence-meta",
        "n": 17,
        "label": "collective-intelligence/meta",
        "catalog_token": "collective-intelligence/meta 17",
    },
)

# Feature -> necessity. matrix_expansion is the required negative control.
NECESSITY: dict[str, dict] = {
    "typed_params": {
        "verdict": "NECESSARY",
        "category_id": "product-design",
        "spec_anchor": "IMP-0133 Workflow.params / tools/agentspec/agentspec/spec.py:Workflow.params",
        "cannot_express_without": (
            "A blueprint library is instantiable only if typed params exist on "
            "Workflow (spec.py:Workflow.params); otherwise each of the 96 "
            "categories collapses to a hardcoded script."
        ),
    },
    "conditionals": {
        "verdict": "NECESSARY",
        "category_id": "engineering-reliability",
        "spec_anchor": "on_failure family map + Loop.convergence_expr in spec.py",
        "cannot_express_without": (
            "Reliability blueprints must dispatch on closed failure families "
            "(timeout, schema-invalid, truncated-output, ...) without an "
            "embedded Python predicate. That is declarative branching."
        ),
    },
    "sub_workflows": {
        "verdict": "NECESSARY",
        "category_id": "collective-intelligence-meta",
        "spec_anchor": "IMP-0129 Subworkflow node",
        "cannot_express_without": (
            "Meta/council blueprints compose other workflows by reference. "
            "Without a sub-workflow construct the 96-item library cannot nest "
            "and would escape to subprocess or copy-paste."
        ),
    },
    "matrix_expansion": {
        "verdict": "NOT-NECESSARY",
        "category_id": None,
        "spec_anchor": "IMP-0132 DynamicFanOut (receipt-driven cardinality, not cartesian axes)",
        "cannot_express_without": None,
        "why_not_necessary": (
            "GitHub Actions strategy.matrix is a static cartesian product "
            "(os × version). None of the six blueprint families requires "
            "that CI packaging shape. AgentSpec already has DynamicFanOut, "
            "whose width comes from a producer receipt (max_cardinality), "
            "which is a different construct. Marking matrix_expansion "
            "NECESSARY would turn this matrix into a wish list."
        ),
        "negative_control": True,
    },
    "artifacts": {
        "verdict": "NECESSARY",
        "category_id": "research-evidence",
        "spec_anchor": "taxonomy family partial-artifact; WorkUnit outputs",
        "cannot_express_without": (
            "Evidence blueprints must produce claim records as named artifacts. "
            "The closed failure family partial-artifact is unrepresentable if "
            "the DSL cannot name an artifact."
        ),
    },
    "retries": {
        "verdict": "NECESSARY",
        "category_id": "engineering-reliability",
        "spec_anchor": "IMP-0139 RepairLoop",
        "cannot_express_without": (
            "Reliability blueprints retry bounded repair without dropping into "
            "a general-purpose loop in host code."
        ),
    },
    "timeouts": {
        "verdict": "NECESSARY",
        "category_id": "engineering-reliability",
        "spec_anchor": "taxonomy family timeout in taxonomy.py",
        "cannot_express_without": (
            "timeout is a closed failure-taxonomy family. A DSL that cannot "
            "name a deadline cannot classify that family without host-language "
            "timers."
        ),
    },
    "manual_approval": {
        "verdict": "NECESSARY",
        "category_id": "security-governance",
        "spec_anchor": "IMP-0131 HumanCheckpoint",
        "cannot_express_without": (
            "Governance blueprints stop for an owner decision and resume from "
            "a pause_token. Without a checkpoint node they hang or skip the "
            "human gate in code."
        ),
    },
}

# Remote captures. kind is the rail class (prose vs api).
SOURCES: tuple[dict, ...] = (
    # Argo — markdown docs + generated field schema
    {
        "id": "argo-fields",
        "engine": "argo",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/fields.md",
    },
    {
        "id": "argo-parameters",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/parameters.md",
    },
    {
        "id": "argo-conditionals",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/conditionals.md",
    },
    {
        "id": "argo-artifacts",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/artifacts.md",
    },
    {
        "id": "argo-loops",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/loops.md",
    },
    {
        "id": "argo-templates",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/workflow-templates.md",
    },
    {
        "id": "argo-retries",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/retries.md",
    },
    {
        "id": "argo-timeouts",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/timeouts.md",
    },
    {
        "id": "argo-suspend",
        "engine": "argo",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/master/docs/walk-through/suspending.md",
    },
    # Temporal
    {
        "id": "temporal-retry-docs",
        "engine": "temporal",
        "kind": "prose",
        "url": "https://docs.temporal.io/encyclopedia/retry-policies",
    },
    {
        "id": "temporal-fail-docs",
        "engine": "temporal",
        "kind": "prose",
        "url": "https://docs.temporal.io/encyclopedia/detecting-workflow-failures",
    },
    {
        "id": "temporal-child-docs",
        "engine": "temporal",
        "kind": "prose",
        "url": "https://docs.temporal.io/child-workflows",
    },
    {
        "id": "temporal-common-py",
        "engine": "temporal",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/temporalio/sdk-python/main/temporalio/common.py",
    },
    {
        "id": "temporal-workflow-ops-py",
        "engine": "temporal",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/temporalio/sdk-python/main/temporalio/workflow/_workflow_ops.py",
    },
    {
        "id": "temporal-activities-py",
        "engine": "temporal",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/temporalio/sdk-python/main/temporalio/workflow/_activities.py",
    },
    # Airflow
    {
        "id": "airflow-params-docs",
        "engine": "airflow",
        "kind": "prose",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/params.html",
    },
    {
        "id": "airflow-map-docs",
        "engine": "airflow",
        "kind": "prose",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html",
    },
    {
        "id": "airflow-tasks-docs",
        "engine": "airflow",
        "kind": "prose",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html",
    },
    {
        "id": "airflow-dags-docs",
        "engine": "airflow",
        "kind": "prose",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html",
    },
    {
        "id": "airflow-param-py",
        "engine": "airflow",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/apache/airflow/main/task-sdk/src/airflow/sdk/definitions/param.py",
    },
    {
        "id": "airflow-baseoperator-py",
        "engine": "airflow",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/apache/airflow/2.10.4/airflow/models/baseoperator.py",
    },
    {
        "id": "airflow-trigger-py",
        "engine": "airflow",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/apache/airflow/2.10.4/airflow/operators/trigger_dagrun.py",
    },
    # Prefect
    {
        "id": "prefect-flows-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/concepts/flows.mdx",
    },
    {
        "id": "prefect-tasks-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/concepts/tasks.mdx",
    },
    {
        "id": "prefect-retries-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/how-to-guides/workflows/retries.mdx",
    },
    {
        "id": "prefect-inputs-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/how-to-guides/workflows/pass-inputs.mdx",
    },
    {
        "id": "prefect-artifacts-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/how-to-guides/workflows/artifacts.mdx",
    },
    {
        "id": "prefect-concurrent-mdx",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/how-to-guides/workflows/run-work-concurrently.mdx",
    },
    {
        "id": "prefect-flow-runs-apiref",
        "engine": "prefect",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/docs/v3/api-ref/python/prefect-flow_runs.mdx",
    },
    {
        "id": "prefect-tasks-py",
        "engine": "prefect",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/src/prefect/tasks.py",
    },
    {
        "id": "prefect-flow-runs-py",
        "engine": "prefect",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/PrefectHQ/prefect/main/src/prefect/flow_runs.py",
    },
    # Dagster
    {
        "id": "dagster-retry-docs",
        "engine": "dagster",
        "kind": "prose",
        "url": "https://docs.dagster.io/guides/build/ops/op-retries",
    },
    {
        "id": "dagster-graphs-docs",
        "engine": "dagster",
        "kind": "prose",
        "url": "https://docs.dagster.io/guides/build/graphs",
    },
    {
        "id": "dagster-ops-api",
        "engine": "dagster",
        "kind": "prose",
        "url": "https://docs.dagster.io/api/python-api/ops",
    },
    {
        "id": "dagster-config-api",
        "engine": "dagster",
        "kind": "prose",
        "url": "https://docs.dagster.io/api/python-api/config",
    },
    {
        "id": "dagster-policy-py",
        "engine": "dagster",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/dagster-io/dagster/master/python_modules/dagster/dagster/_core/definitions/policy.py",
    },
    {
        "id": "dagster-retries-py",
        "engine": "dagster",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/dagster-io/dagster/master/python_modules/dagster/dagster/_core/execution/retries.py",
    },
    # AWS Step Functions
    {
        "id": "aws-choice",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-choice-state.html",
    },
    {
        "id": "aws-map",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-map-state.html",
    },
    {
        "id": "aws-retry",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html",
    },
    {
        "id": "aws-nested",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-nested-workflows.html",
    },
    {
        "id": "aws-callback",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html",
    },
    {
        "id": "aws-task",
        "engine": "aws-stepfunctions",
        "kind": "prose",
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-task-state.html",
    },
    {
        "id": "asl-spec",
        "engine": "aws-stepfunctions",
        "kind": "api",
        "url": "https://states-language.net/spec.html",
    },
    # GitHub Actions
    {
        "id": "gha-schema",
        "engine": "github-actions",
        "kind": "api",
        "url": "https://json.schemastore.org/github-workflow.json",
    },
    {
        "id": "gha-matrix-docs",
        "engine": "github-actions",
        "kind": "prose",
        "url": "https://docs.github.com/en/actions/using-jobs/using-a-build-matrix-for-your-jobs",
    },
    {
        "id": "gha-env-docs",
        "engine": "github-actions",
        "kind": "prose",
        "url": "https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment",
    },
    {
        "id": "gha-artifact-docs",
        "engine": "github-actions",
        "kind": "prose",
        "url": "https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts",
    },
    {
        "id": "gha-reuse-docs",
        "engine": "github-actions",
        "kind": "prose",
        "url": "https://docs.github.com/en/actions/using-workflows/reusing-workflows",
    },
    {
        "id": "gha-syntax-docs",
        "engine": "github-actions",
        "kind": "prose",
        "url": "https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions",
    },
)

# Local files hashed as the second signal for necessity (this program's spec).
LOCAL_SOURCES: tuple[dict, ...] = (
    {
        "id": "local-spec",
        "engine": "agentspec",
        "kind": "api",
        "relpath": "tools/agentspec/agentspec/spec.py",
    },
    {
        "id": "local-taxonomy",
        "engine": "agentspec",
        "kind": "api",
        "relpath": "tools/agentspec/agentspec/taxonomy.py",
    },
    {
        "id": "local-catalog",
        "engine": "agentspec",
        "kind": "prose",
        "relpath": "command-center/WORK-UNIT-CATALOG.json",
    },
)

# Cell evidence: each entry is (capture_id, needle). Both needles must hit
# for PRESENT/PARTIAL. For ABSENT, needles must MISS in those captures
# (search miss is the evidence).
#
# presence values: PRESENT | PARTIAL | ABSENT
CELL_SPEC: dict[tuple[str, str], dict] = {}


def _cell(engine: str, feature: str, presence: str, rails: list[tuple[str, str]], note: str) -> None:
    CELL_SPEC[(engine, feature)] = {
        "presence": presence,
        "rails": [{"capture_id": a, "needle": b} for a, b in rails],
        "note": note,
    }


# --- Argo ---
_cell(
    "argo",
    "typed_params",
    "PARTIAL",
    [
        ("argo-parameters", "inputs:\n      parameters:"),
        ("argo-fields", "Parameter indicate a passed string parameter"),
    ],
    "Named parameters exist; the field schema describes them as strings, not JSON-Schema types.",
)
_cell(
    "argo",
    "conditionals",
    "PRESENT",
    [
        ("argo-conditionals", "when: \"{{steps.flip-coin.outputs.result}} == heads\""),
        ("argo-fields", "When"),
    ],
    "Declarative `when:` on steps (walk-through) plus field registry.",
)
_cell(
    "argo",
    "sub_workflows",
    "PRESENT",
    [
        ("argo-templates", "kind: WorkflowTemplate"),
        ("argo-fields", "workflowTemplateRef"),
    ],
    "WorkflowTemplate + workflowTemplateRef.",
)
_cell(
    "argo",
    "matrix_expansion",
    "PARTIAL",
    [
        ("argo-loops", "withItems"),
        ("argo-fields", "withItems"),
    ],
    "withItems/withParam loop over a list; not a named cartesian matrix.",
)
_cell(
    "argo",
    "artifacts",
    "PRESENT",
    [
        ("argo-artifacts", "artifacts:"),
        ("argo-fields", "outputs.artifacts"),
    ],
    "First-class inputs/outputs artifacts.",
)
_cell(
    "argo",
    "retries",
    "PRESENT",
    [
        ("argo-retries", "retryStrategy"),
        ("argo-fields", "retryStrategy"),
    ],
    "retryStrategy on templates.",
)
_cell(
    "argo",
    "timeouts",
    "PRESENT",
    [
        ("argo-timeouts", "activeDeadlineSeconds"),
        ("argo-fields", "activeDeadlineSeconds"),
    ],
    "activeDeadlineSeconds on workflow/template.",
)
_cell(
    "argo",
    "manual_approval",
    "PRESENT",
    [
        ("argo-suspend", "suspend: {}"),
        ("argo-fields", "suspend"),
    ],
    "suspend template waits for resume/approve.",
)

# --- Temporal (SDK-first; several features are host-language, not DSL) ---
_cell(
    "temporal",
    "typed_params",
    "PARTIAL",
    [
        ("temporal-common-py", "class RetryPolicy"),
        ("temporal-workflow-ops-py", "def execute_child_workflow"),
    ],
    "Workflow args are host-language typed; there is no declarative param schema DSL. Rails confirm SDK, not a YAML schema.",
)
_cell(
    "temporal",
    "conditionals",
    "ABSENT",
    [
        ("temporal-child-docs", "Choice state"),
        ("temporal-retry-docs", "when:"),
    ],
    "No declarative if/Choice. Branching is Python/Go if inside workflow code (escape).",
)
_cell(
    "temporal",
    "sub_workflows",
    "PRESENT",
    [
        ("temporal-child-docs", "Child Workflows"),
        ("temporal-workflow-ops-py", "execute_child_workflow"),
    ],
    "Child workflows are a first-class SDK API.",
)
_cell(
    "temporal",
    "matrix_expansion",
    "ABSENT",
    [
        ("temporal-child-docs", "strategy.matrix"),
        ("temporal-retry-docs", "withItems"),
    ],
    "No cartesian matrix construct in Temporal docs/SDK captures.",
)
_cell(
    "temporal",
    "artifacts",
    "ABSENT",
    [
        ("temporal-child-docs", "outputs.artifacts"),
        ("temporal-common-py", "upload-artifact"),
    ],
    "No first-class artifact object; payloads go through activities + external storage.",
)
_cell(
    "temporal",
    "retries",
    "PRESENT",
    [
        ("temporal-retry-docs", "Retry Policy"),
        ("temporal-common-py", "class RetryPolicy"),
    ],
    "RetryPolicy on activities.",
)
_cell(
    "temporal",
    "timeouts",
    "PRESENT",
    [
        ("temporal-fail-docs", "Workflow Task Timeout"),
        ("temporal-activities-py", "start_to_close_timeout"),
    ],
    "Workflow Task Timeout in failure-detection docs; start_to_close_timeout in the activity API.",
)
_cell(
    "temporal",
    "manual_approval",
    "PARTIAL",
    [
        ("temporal-child-docs", "signal"),
        ("temporal-workflow-ops-py", "signal"),
    ],
    "Signals/updates can implement approval; there is no named Approval state.",
)

# --- Airflow ---
_cell(
    "airflow",
    "typed_params",
    "PRESENT",
    [
        ("airflow-param-py", "class Param"),
        ("airflow-params-docs", "schema"),
    ],
    "airflow.models.param.Param with JSON schema.",
)
_cell(
    "airflow",
    "conditionals",
    "PARTIAL",
    [
        ("airflow-dags-docs", "BranchPythonOperator"),
        ("airflow-dags-docs", "branch"),
    ],
    "BranchPythonOperator runs a Python callable — branching exists, but the predicate is host code.",
)
_cell(
    "airflow",
    "sub_workflows",
    "PRESENT",
    [
        ("airflow-dags-docs", "TriggerDagRunOperator"),
        ("airflow-trigger-py", "class TriggerDagRunOperator"),
    ],
    "TriggerDagRunOperator starts another DAG (docs + operator source).",
)
_cell(
    "airflow",
    "matrix_expansion",
    "PARTIAL",
    [
        ("airflow-map-docs", "expand("),
        ("airflow-map-docs", "Dynamic Task Mapping"),
    ],
    "expand() maps over a runtime list, not a static cartesian matrix keyword.",
)
_cell(
    "airflow",
    "artifacts",
    "PARTIAL",
    [
        ("airflow-dags-docs", "XCom"),
        ("airflow-tasks-docs", "XCom"),
    ],
    "XCom is small metadata passing, not a file artifact object.",
)
_cell(
    "airflow",
    "retries",
    "PRESENT",
    [
        ("airflow-tasks-docs", "retries"),
        ("airflow-baseoperator-py", "retries"),
    ],
    "BaseOperator.retries.",
)
_cell(
    "airflow",
    "timeouts",
    "PRESENT",
    [
        ("airflow-tasks-docs", "execution_timeout"),
        ("airflow-baseoperator-py", "execution_timeout"),
    ],
    "execution_timeout on tasks.",
)
_cell(
    "airflow",
    "manual_approval",
    "ABSENT",
    [
        ("airflow-tasks-docs", "HumanCheckpoint"),
        ("airflow-dags-docs", "required reviewers"),
    ],
    "No first-class human-approval operator in these captures (sensors would be an escape).",
)

# --- Prefect ---
_cell(
    "prefect",
    "typed_params",
    "PRESENT",
    [
        ("prefect-inputs-mdx", "type validation"),
        ("prefect-inputs-mdx", "def my_workflow(name: str"),
    ],
    "Flow function parameters with type validation.",
)
_cell(
    "prefect",
    "conditionals",
    "ABSENT",
    [
        ("prefect-flows-mdx", "when:"),
        ("prefect-tasks-mdx", "Choice"),
    ],
    "No declarative conditional construct in the flow/task MDX; users write Python if.",
)
_cell(
    "prefect",
    "sub_workflows",
    "PRESENT",
    [
        ("prefect-flows-mdx", "subflow"),
        ("prefect-tasks-py", "subflow"),
    ],
    "Subflows documented and referenced in the tasks module.",
)
_cell(
    "prefect",
    "matrix_expansion",
    "PARTIAL",
    [
        ("prefect-concurrent-mdx", ".map("),
        ("prefect-tasks-mdx", "map"),
    ],
    "task.map is runtime mapping, not strategy.matrix cartesian axes.",
)
_cell(
    "prefect",
    "artifacts",
    "PRESENT",
    [
        ("prefect-artifacts-mdx", "create_link_artifact"),
        ("prefect-artifacts-mdx", "artifact"),
    ],
    "create_*_artifact APIs.",
)
_cell(
    "prefect",
    "retries",
    "PRESENT",
    [
        ("prefect-retries-mdx", "@flow(retries=3)"),
        ("prefect-tasks-py", "retries"),
    ],
    "@flow(retries=N) / task retries.",
)
_cell(
    "prefect",
    "timeouts",
    "PRESENT",
    [
        ("prefect-tasks-py", "timeout_seconds"),
        ("prefect-flows-mdx", "Timeouts"),
    ],
    "timeout_seconds on the task API; Timeouts linked from the flow concept page.",
)
_cell(
    "prefect",
    "manual_approval",
    "PRESENT",
    [
        ("prefect-flow-runs-py", "def pause_flow_run"),
        ("prefect-flow-runs-apiref", "pause_flow_run"),
    ],
    "pause_flow_run blocks until resumed.",
)

# --- Dagster ---
_cell(
    "dagster",
    "typed_params",
    "PRESENT",
    [
        ("dagster-config-api", "Config"),
        ("dagster-ops-api", "config"),
    ],
    "Run/op config schema.",
)
_cell(
    "dagster",
    "conditionals",
    "ABSENT",
    [
        ("dagster-graphs-docs", "when:"),
        ("dagster-retry-docs", "Choice"),
    ],
    "Graphs are Python; no declarative Choice/when in these captures.",
)
_cell(
    "dagster",
    "sub_workflows",
    "PRESENT",
    [
        ("dagster-graphs-docs", "Graph"),
        ("dagster-graphs-docs", "graph"),
    ],
    "Graphs nest ops/graphs.",
)
_cell(
    "dagster",
    "matrix_expansion",
    "ABSENT",
    [
        ("dagster-graphs-docs", "strategy.matrix"),
        ("dagster-retry-docs", "withItems"),
    ],
    "No cartesian matrix keyword in these captures (DynamicOut would be a different page).",
)
_cell(
    "dagster",
    "artifacts",
    "PARTIAL",
    [
        ("dagster-graphs-docs", "asset"),
        ("dagster-ops-api", "Output"),
    ],
    "Software-defined assets / IO managers, not a generic artifact blob type in the op DSL.",
)
_cell(
    "dagster",
    "retries",
    "PRESENT",
    [
        ("dagster-retry-docs", "RetryPolicy"),
        ("dagster-policy-py", "class RetryPolicy"),
    ],
    "RetryPolicy on ops.",
)
_cell(
    "dagster",
    "timeouts",
    "ABSENT",
    [
        ("dagster-policy-py", "timeout"),
        ("dagster-retry-docs", "execution_timeout"),
    ],
    "RetryPolicy captures have no timeout field; no execution_timeout in the retry guide.",
)
_cell(
    "dagster",
    "manual_approval",
    "ABSENT",
    [
        ("dagster-graphs-docs", "required reviewers"),
        ("dagster-retry-docs", "pause_flow_run"),
    ],
    "No human-checkpoint construct in these captures.",
)

# --- AWS Step Functions ---
_cell(
    "aws-stepfunctions",
    "typed_params",
    "PARTIAL",
    [
        ("asl-spec", "Parameters"),
        ("aws-task", "Parameters"),
    ],
    "ASL Parameters pass JSON; no JSON-Schema param types in the spec capture.",
)
_cell(
    "aws-stepfunctions",
    "conditionals",
    "PRESENT",
    [
        ("aws-choice", "Choice"),
        ("asl-spec", "Choice"),
    ],
    "Choice state is declarative.",
)
_cell(
    "aws-stepfunctions",
    "sub_workflows",
    "PRESENT",
    [
        ("aws-nested", "nested"),
        ("aws-nested", "StartExecution"),
    ],
    "Nested state machine executions.",
)
_cell(
    "aws-stepfunctions",
    "matrix_expansion",
    "PARTIAL",
    [
        ("aws-map", "Map"),
        ("asl-spec", "Map"),
    ],
    "Map iterates an array; not GHA cartesian axes.",
)
_cell(
    "aws-stepfunctions",
    "artifacts",
    "PARTIAL",
    [
        ("asl-spec", "ResultPath"),
        ("aws-task", "ResultPath"),
    ],
    "JSON result routing, not file artifacts.",
)
_cell(
    "aws-stepfunctions",
    "retries",
    "PRESENT",
    [
        ("aws-retry", "Retry"),
        ("asl-spec", "Retry"),
    ],
    "Retry field on states.",
)
_cell(
    "aws-stepfunctions",
    "timeouts",
    "PRESENT",
    [
        ("asl-spec", "TimeoutSeconds"),
        ("aws-task", "TimeoutSeconds"),
    ],
    "TimeoutSeconds on Task/state.",
)
_cell(
    "aws-stepfunctions",
    "manual_approval",
    "PARTIAL",
    [
        ("aws-callback", "waitForTaskToken"),
        ("aws-callback", "$$.Task.Token"),
    ],
    "Callback with task token is the usual approval pattern; not named HumanCheckpoint.",
)

# --- GitHub Actions ---
_cell(
    "github-actions",
    "typed_params",
    "PRESENT",
    [
        ("gha-schema", "workflow_dispatch"),
        ("gha-syntax-docs", "workflow_dispatch"),
    ],
    "workflow_dispatch inputs with type boolean/choice/number/string.",
)
_cell(
    "github-actions",
    "conditionals",
    "PRESENT",
    [
        ("gha-syntax-docs", "jobs.&lt;job_id&gt;.if"),
        ("gha-schema", "expressionSyntax"),
    ],
    "Declarative `if` on jobs/steps.",
)
_cell(
    "github-actions",
    "sub_workflows",
    "PRESENT",
    [
        ("gha-reuse-docs", "workflow_call"),
        ("gha-schema", "workflow_call"),
    ],
    "Reusable workflows via workflow_call.",
)
_cell(
    "github-actions",
    "matrix_expansion",
    "PRESENT",
    [
        ("gha-matrix-docs", "matrix"),
        ("gha-schema", "\"matrix\""),
    ],
    "strategy.matrix cartesian product — the popular feature that is NOT necessary for our families.",
)
_cell(
    "github-actions",
    "artifacts",
    "PRESENT",
    [
        ("gha-artifact-docs", "upload-artifact"),
        ("gha-artifact-docs", "artifact"),
    ],
    "Documented artifact upload/download (action-shaped, but first-class product feature).",
)
_cell(
    "github-actions",
    "retries",
    "ABSENT",
    [
        ("gha-schema", "\"retry\""),
        ("gha-syntax-docs", "jobs.<job_id>.steps.retry"),
    ],
    "github-workflow.json has no retry keyword; native step retry is absent.",
)
_cell(
    "github-actions",
    "timeouts",
    "PRESENT",
    [
        ("gha-schema", "timeout-minutes"),
        ("gha-syntax-docs", "timeout-minutes"),
    ],
    "timeout-minutes on jobs/steps.",
)
_cell(
    "github-actions",
    "manual_approval",
    "PRESENT",
    [
        ("gha-env-docs", "required reviewers"),
        ("gha-schema", "environment"),
    ],
    "Environment protection rules / required reviewers.",
)

assert len(CELL_SPEC) == len(ENGINES) * len(FEATURES)
assert all(NECESSITY[f]["verdict"] in {"NECESSARY", "NOT-NECESSARY"} for f in FEATURES)
assert NECESSITY["matrix_expansion"]["verdict"] == "NOT-NECESSARY"
assert sum(f["n"] for f in BLUEPRINT_FAMILIES) == 96
