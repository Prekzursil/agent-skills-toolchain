#!/usr/bin/env python3
"""CI collection target: importing a deleted module must error."""
import importlib

importlib.import_module("aud0094_retired_tree_harness_file_00")
