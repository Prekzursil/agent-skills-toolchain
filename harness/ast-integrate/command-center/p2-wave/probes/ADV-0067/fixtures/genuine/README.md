# genuine-quality-pack

## Purpose

Implements integer addition and a small checksum used by the marketplace fixture so reviewers can re-run behaviour, not just open a file that exists.

## Install

Place the package root on PYTHONPATH and import src.plugin.

## Usage

Call add(2, 3) and expect 5. checksum walks a sequence of ints.

## Tests

tests/test_plugin.py asserts those identities.

## Provenance

Builder id and materials are in provenance.json; the SBOM lists the two Python modules that actually shipped.
