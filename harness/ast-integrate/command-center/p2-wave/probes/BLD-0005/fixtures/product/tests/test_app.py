"""Test-only read: must classify FIXTURE-ONLY, not product-orphan."""
import os

os.environ.get("BLD0005_PLANTED_FIXTURE_ONLY_KEY")
