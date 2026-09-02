"""Pinned Goose loci for RES-0030. Parent SHA still contains lead_worker.rs."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REPO = HERE.parents[3]

UNIT_ID = "RES-0030"
SENTINEL = (
    "SUCCESS:RES-0030 in the receipt AND the resolved canonical URL with its "
    "redirect chain plus the escalation threshold at file:line"
)
SHORT_SENTINEL = "SUCCESS:RES-0030"

OLD_HTML = "https://github.com/block/goose"
CANONICAL_HTML = "https://github.com/aaif-goose/goose"
OLD_API = "https://api.github.com/repos/block/goose"
CANONICAL_API = "https://api.github.com/repos/aaif-goose/goose"
REPO_NUMERIC_ID = 846698999
CANONICAL_FULL_NAME = "aaif-goose/goose"

PARENT_SHA = "7f1ca37234db08ab173d48b97560e80f219124db"
REMOVAL_SHA = "6435e1a85c97caffca810fafa6b000df962416be"
REMOVAL_PR = 7989

RAW = "https://raw.githubusercontent.com/aaif-goose/goose"
BLOB = "https://github.com/aaif-goose/goose/blob"

LEAD_WORKER_REL = "crates/goose/src/providers/lead_worker.rs"
INIT_REL = "crates/goose/src/providers/init.rs"
ENV_DOCS_REL = "documentation/docs/guides/environment-variables.md"
TUTORIAL_REL = "documentation/docs/tutorials/lead-worker.md"
RECIPE_REF_REL = "documentation/docs/guides/recipes/recipe-reference.md"
SESSION_RECIPES_REL = "documentation/docs/guides/recipes/session-recipes.md"

LEAD_WORKER_RAW = f"{RAW}/{PARENT_SHA}/{LEAD_WORKER_REL}"
INIT_RAW = f"{RAW}/{PARENT_SHA}/{INIT_REL}"
ENV_DOCS_RAW = f"{RAW}/{PARENT_SHA}/{ENV_DOCS_REL}"
TUTORIAL_RAW = f"{RAW}/{PARENT_SHA}/{TUTORIAL_REL}"
LEAD_WORKER_MAIN_RAW = f"{RAW}/main/{LEAD_WORKER_REL}"
RECIPE_REF_MAIN_RAW = f"{RAW}/main/{RECIPE_REF_REL}"
SESSION_RECIPES_MAIN_RAW = f"{RAW}/main/{SESSION_RECIPES_REL}"
REMOVAL_PR_API = f"https://api.github.com/repos/aaif-goose/goose/pulls/{REMOVAL_PR}"

LEAD_WORKER_PERMALINK = f"{BLOB}/{PARENT_SHA}/{LEAD_WORKER_REL}"
INIT_PERMALINK = f"{BLOB}/{PARENT_SHA}/{INIT_REL}"
ENV_DOCS_PERMALINK = f"{BLOB}/{PARENT_SHA}/{ENV_DOCS_REL}"
TUTORIAL_PERMALINK = f"{BLOB}/{PARENT_SHA}/{TUTORIAL_REL}"
REMOVAL_COMMIT_URL = f"https://github.com/aaif-goose/goose/commit/{REMOVAL_SHA}"
REMOVAL_PR_URL = f"https://github.com/aaif-goose/goose/pull/{REMOVAL_PR}"

# 1-indexed lines measured on PARENT_SHA captures.
DEFAULT_THRESHOLD_LINE = 45  # const DEFAULT_FAILURE_THRESHOLD: usize = 2;
CONFIG_READ_LINE = 198  # get_param::<usize>("GOOSE_LEAD_FAILURE_THRESHOLD")
CONSTRUCTOR_DEFAULT_LINE = 52  # max_failures_before_fallback: 2
TRIGGER_LINE = 151  # turn_count >= self.lead_turns && failure_count >= threshold
SWITCH_LOG_LINE = 163  # SWITCHING TO LEAD MODEL
LEAD_TURNS_DEFAULT_LINE = 44  # const DEFAULT_LEAD_TURNS: usize = 3
ENV_DOCS_THRESHOLD_LINE = 142
TUTORIAL_THRESHOLD_LINE = 77

DEFAULT_FAILURE_THRESHOLD = 2
DEFAULT_LEAD_TURNS = 3
CONFIG_KEY = "GOOSE_LEAD_FAILURE_THRESHOLD"

OUTPUT_REL = "command-center/research/RES-0030.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"

UA = "ast-integrate-RES-0030-research/1.0 (+local G-1 probes)"
