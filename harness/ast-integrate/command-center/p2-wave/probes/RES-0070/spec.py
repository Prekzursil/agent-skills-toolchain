#!/usr/bin/env python3
"""Field-by-field agent-step cache-key specification (RES-0070).

Bazel hashes a declared action (command line, env, inputs). Nix input-addresses
an output by the derivation that produced it. Neither system hashes a URL and
hopes the bytes behind it stay still. This module is the agent-step analog:
every field that can change the output is either in the key or the step is
named uncacheable.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

UNCACHEABLE_LIVE_WEB = "live-web-unsapped-search-then-reason"
UNCACHEABLE_SAMPLER = "non-deterministic-sampler"

CACHE_KEY_FIELDS: list[dict[str, str]] = [
    {
        "id": "step_mnemonic",
        "bazel_nix_analog": (
            "Bazel fingerprints the action mnemonic in SpawnAction.computeKey "
            "(fp.addString(mnemonic))."
        ),
        "justification": (
            "Two different step kinds (retrieve vs. synthesize vs. tool-call) "
            "must not share a memo slot. The mnemonic is the cheapest "
            "collision-breaker and is already in Bazel's action key."
        ),
        "omit_failure": "retrieve and synthesize collide on the same prompt.",
    },
    {
        "id": "model_identity",
        "bazel_nix_analog": (
            "Tool/compiler identity: a hermetic build pins the toolchain. "
            "Nix input-address is a function of the derivation, including the builder."
        ),
        "justification": (
            "The catalog names model version as a first-class input. The same "
            "prompt through provider:model:revision A and B is a different "
            "action. Identity is provider + model id + snapshot/revision, not "
            "a marketing name."
        ),
        "omit_failure": "gpt-x-2024-04 and gpt-x-2025-01 collide.",
    },
    {
        "id": "sampling_parameters",
        "bazel_nix_analog": (
            "Command-line analog. SpawnAction.computeKey adds commandLines to "
            "the fingerprint. Temperature is a declared execution parameter."
        ),
        "justification": (
            "Temperature, top_p, max_tokens, and seed (when present) change the "
            "output distribution. Omitting temperature makes T=0 and T=1 share "
            "a key, which is the exact unsound-cache-key defect."
        ),
        "omit_failure": "temperature=0 and temperature=1 collide.",
    },
    {
        "id": "prompt_bytes_sha256",
        "bazel_nix_analog": (
            "Declared input file contents. Bazel hashes input files, not paths. "
            "DVC: file hashes are calculated from file contents only."
        ),
        "justification": (
            "The prompt/system/tool-preamble is the primary declared input. "
            "Hash the exact bytes sent, not a template id that can be edited "
            "underfoot."
        ),
        "omit_failure": "two different prompts collide.",
    },
    {
        "id": "tool_policy_sha256",
        "bazel_nix_analog": "Command line / toolchain files: available tools change the action.",
        "justification": (
            "Which tools the model may call, and their JSON schemas, change "
            "behavior. A policy digest belongs in the key the same way argv does."
        ),
        "omit_failure": "read-only vs. write-enabled tool sets collide.",
    },
    {
        "id": "declared_input_artifact_sha256s",
        "bazel_nix_analog": (
            "Bazel: required inputs are declared explicitly for each action. "
            "Nix: input-addressed output path is a function of the derivation inputs."
        ),
        "justification": (
            "Attached files, prior-step outputs, and retrieved blobs enter as "
            "content hashes (sorted), never as workspace paths."
        ),
        "omit_failure": "two different attached PDFs collide.",
    },
    {
        "id": "live_source_snapshot_sha256",
        "bazel_nix_analog": (
            "Source identity is a content hash (Git / file digest), not a URL. "
            "Bazel hermeticity: isolate the build from host-system change."
        ),
        "justification": (
            "A live web source is an input. The URL is a path. The captured "
            "response body (plus final URL after redirects and HTTP status) "
            "must be snapshotted and hashed into the key. If no snapshot "
            "exists, the step is not cacheable — see uncacheable class "
            + UNCACHEABLE_LIVE_WEB
            + "."
        ),
        "omit_failure": "same URL, different page body, same key (stale serve).",
    },
    {
        "id": "declared_env",
        "bazel_nix_analog": (
            "Only environment variables explicitly whitelisted via --action_env "
            "are included in a Bazel action definition. Undeclared $PATH "
            "differences otherwise prevent (or silently poison) cache hits."
        ),
        "justification": (
            "Declared env (region, feature flags) that the step is allowed to "
            "read. Secrets never enter the key; they also must not enter the action."
        ),
        "omit_failure": "two declared feature-flag envs collide.",
    },
]

FIELD_IDS: tuple[str, ...] = tuple(f["id"] for f in CACHE_KEY_FIELDS)

UNCACHEABLE_STEP_CLASSES: list[dict[str, str]] = [
    {
        "id": UNCACHEABLE_LIVE_WEB,
        "title": "Live-web unsapped search-then-reason",
        "definition": (
            "A step whose output depends on a live web fetch or search-index "
            "result that was not captured as declared input bytes (body sha256, "
            "final URL, HTTP status, fetch timestamp) before the model call."
        ),
        "why_not_cacheable": (
            "There is no content digest to put in the key. Keying by URL is "
            "unsound: the same URL can yield different bodies. Bazel analog: "
            "an undeclared host input / non-hermetic action. Nix analog: an "
            "impurity. The honest mark is uncacheable, not a partial key."
        ),
        "control": (
            "Two fetches of one URL with different bodies must not share a "
            "cache slot. A URL-only mutant key collides; the classifier "
            "refuses to emit a key at all."
        ),
    },
    {
        "id": UNCACHEABLE_SAMPLER,
        "title": "Non-deterministic sampler (exact-output memoization)",
        "definition": (
            "Exact-output memoization of a step with temperature > 0, no seed, "
            "and no documented deterministic decoding."
        ),
        "why_not_cacheable": (
            "The output is not a function of the declared inputs. A cache hit "
            "would pretend replay. Distributional caches are a different "
            "contract and are out of scope for this unit."
        ),
        "control": (
            "classify() returns this class; compute_key() raises UncacheableStep."
        ),
    },
]


class UncacheableStep(ValueError):
    def __init__(self, class_id: str, detail: str = "") -> None:
        self.class_id = class_id
        super().__init__(class_id if not detail else f"{class_id}: {detail}")


def _digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def classify(step: dict[str, Any]) -> str:
    """Return 'cacheable' or a named uncacheable class id."""
    url = step.get("live_web_url")
    snap = step.get("live_source_snapshot_sha256")
    if url and not snap:
        return UNCACHEABLE_LIVE_WEB
    try:
        temp = float(step.get("temperature") if step.get("temperature") is not None else 0)
    except (TypeError, ValueError):
        temp = 0.0
    if (
        temp > 0
        and step.get("seed") is None
        and not step.get("deterministic_decoding")
    ):
        return UNCACHEABLE_SAMPLER
    return "cacheable"


def materialize_fields(
    step: dict[str, Any], omit: str | None = None
) -> dict[str, Any]:
    sampling = {
        "temperature": step.get("temperature", 0),
        "top_p": step.get("top_p"),
        "max_tokens": step.get("max_tokens"),
        "seed": step.get("seed"),
    }
    artifacts = list(step.get("declared_input_artifact_sha256s") or [])
    artifacts_sorted = sorted(str(a) for a in artifacts)
    env = dict(step.get("declared_env") or {})
    fields = {
        "step_mnemonic": step.get("step_mnemonic"),
        "model_identity": {
            "provider": step.get("model_provider"),
            "model_id": step.get("model_id"),
            "revision": step.get("model_revision"),
        },
        "sampling_parameters": sampling,
        "prompt_bytes_sha256": step.get("prompt_bytes_sha256"),
        "tool_policy_sha256": step.get("tool_policy_sha256"),
        "declared_input_artifact_sha256s": artifacts_sorted,
        "live_source_snapshot_sha256": step.get("live_source_snapshot_sha256"),
        "declared_env": {k: env[k] for k in sorted(env)},
    }
    if omit is not None:
        if omit not in fields:
            raise KeyError(omit)
        fields.pop(omit)
    return fields


def compute_key(
    step: dict[str, Any], omit: str | None = None, *, force: bool = False
) -> str:
    """Content-addressed key. Raises UncacheableStep unless force=True."""
    cls = classify(step)
    if cls != "cacheable" and not force:
        raise UncacheableStep(cls)
    return _digest(materialize_fields(step, omit=omit))


def url_only_mutant_key(step: dict[str, Any]) -> str:
    """Unsound mutant: hashes the URL instead of the captured body.

    Control: two different bodies behind one URL collide.
    """
    fields = materialize_fields(step)
    fields["live_source_snapshot_sha256"] = step.get("live_web_url")
    return _digest(fields)


def base_step(**overrides: Any) -> dict[str, Any]:
    step: dict[str, Any] = {
        "step_mnemonic": "synthesize",
        "model_provider": "openai",
        "model_id": "gpt-x",
        "model_revision": "2024-04-09",
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 512,
        "seed": 0,
        "deterministic_decoding": True,
        "prompt_bytes_sha256": "a" * 64,
        "tool_policy_sha256": "b" * 64,
        "declared_input_artifact_sha256s": ["c" * 64],
        "live_web_url": "https://example.test/page",
        "live_source_snapshot_sha256": "d" * 64,
        "declared_env": {"REGION": "us"},
    }
    step.update(overrides)
    return step
