"""Aligned parser: every documented flag exists."""
import argparse

parser = argparse.ArgumentParser(description="aligned fixture")
parser.add_argument("--input", required=True)
parser.add_argument("--format", default="json")
