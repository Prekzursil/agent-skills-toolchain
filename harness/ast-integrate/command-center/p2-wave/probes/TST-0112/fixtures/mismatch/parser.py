"""Mismatch parser: one undocumented live flag, one documented flag absent."""
import argparse

parser = argparse.ArgumentParser(description="mismatch fixture")
parser.add_argument("--input", required=True)
parser.add_argument("--undocumented-real", action="store_true")
