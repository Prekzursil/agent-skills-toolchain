#!/usr/bin/env python3
"""TST-0067 scenario constants: the planted key/value/scope vocabulary.

Single source for the planted names so the probes, harness and consumer all
exercise the same fixture vocabulary recorded in the receipt's constants.
"""
from __future__ import annotations

ENV_KEY = "TST0067_CONSUMER_VAR"
CONFIG_KEY = "planted.mcp.enabled"
OLD = "session-old-value"
NEW = "session-new-value"
ROOT_WRITE = "root-scope-write-inert"
PROJECT_WRITE = "project-scope-write-live"
