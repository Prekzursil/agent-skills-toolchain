"""Fixture argparse CLI for the TST-0251 detector control."""
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toy-cli")
    parser.add_argument("--alpha", action="store_true")
    parser.add_argument("--beta", required=False)
    parser.add_argument("--gamma-path", default=".")
    return parser
