"""Who may modify the A2 generator templates, and what is NOT claimed."""
from __future__ import annotations

REQUIRED_AUTHORIZERS = ("a2-security-reviewer", "codex-cross-vendor")

POLICY = {
    "generator_templates": {
        "paths": [
            "command-center/p2-wave/probes/ARC-0010/generator.py",
            "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        ],
        "who_may_modify": list(REQUIRED_AUTHORIZERS),
        "rule": (
            "Two-person, cross-vendor review: Anthropic-side security-reviewer "
            "AND Codex. Either alone is insufficient. Re-pinning outputs is the "
            "same two identities."
        ),
    },
    "output_pin": {
        "path": "command-center/p2-wave/probes/ARC-0013/pins/output-fingerprint.json",
        "who_may_modify": list(REQUIRED_AUTHORIZERS),
        "rule": "Updating the pin authorizes a new golden tree. Same two reviewers.",
    },
    "registry_entries": {
        "path": "command-center/p2-wave/probes/ARC-0010/registry.json",
        "who_may_modify": ["a2-architect"],
        "rule": (
            "Typed registry edits are architect-owned. If they change generated "
            "bytes, the output-fingerprint gate trips until the pin is re-authorized."
        ),
    },
    "generated_outputs": {
        "who_may_modify": [],
        "rule": "Nobody hand-edits generated files. Restore is regenerate.",
    },
    "signing": {
        "kind": "output-fingerprint-sha256 plus authorized_by list",
        "org_gpg_on_this_worktree": False,
        "honest_limit": (
            "This tree has no org signing key. The pin digest plus the two "
            "authorized_by identities is the demonstrated authorization, not a "
            "production GPG/cosign deployment."
        ),
    },
    "github_codeowners_live": False,
}
