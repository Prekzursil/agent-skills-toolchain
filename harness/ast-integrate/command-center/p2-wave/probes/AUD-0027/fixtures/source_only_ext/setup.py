"""Intentionally wheel-less C extension: the AUD-0027 source-only control."""
from setuptools import Extension, setup

setup(
    name="aud0027-source-only",
    version="0.0.1",
    ext_modules=[Extension("aud0027_source_only", ["aud0027_source_only.c"])],
)
