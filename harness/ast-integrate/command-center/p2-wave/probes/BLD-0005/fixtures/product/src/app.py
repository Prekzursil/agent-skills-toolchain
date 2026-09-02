"""Product-side reads for BLD-0005 planted controls."""
import os

# Negative control: declared in plugin.json config and actually read here.
os.environ.get("BLD0005_PLANTED_MATCHED_KEY")

# Undeclared-knob control: getenv of a variable no shipped config declares.
os.environ.get("BLD0005_PLANTED_UNDECLARED_ENV")
