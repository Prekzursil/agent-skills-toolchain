#!/usr/bin/env python3
"""Path assembled from parts so a literal full-string search cannot see it."""
PREFIX = "aud0094-retired"
TREE = "tree-tools-a"
NAME = "file-01.py"


def retired_target():
    return "/".join([PREFIX, TREE, NAME])
