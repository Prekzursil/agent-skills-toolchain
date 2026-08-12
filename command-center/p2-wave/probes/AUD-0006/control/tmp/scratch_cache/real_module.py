"""A genuinely authored module that happens to live under a scratch-looking path.

This is the row's required planted mutant: a path-only classifier loses it, a content
classifier rescues it."""

from pathlib import Path


def resolve_manifest(root: Path) -> Path:
    """Return the manifest path for a repo root."""
    return root / "command-center" / "ARTIFACT-MANIFEST.json"


def test_resolve_manifest():
    assert resolve_manifest(Path("/x")).name == "ARTIFACT-MANIFEST.json"
