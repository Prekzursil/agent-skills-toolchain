# AUD-0027 planted source-only control

Catalog `tests_required`:

> control: attempt an install of a package known to be source-only and confirm
> the probe reports a compiler requirement rather than a clean pass

Planted subject: PyPI `crcmod==1.7` (latest at census time) — publishes **sdist only**
(zero wheels on the project file list). Probe 2 must attempt
`pip install --only-binary=:all: crcmod==1.7` into a clean venv and record a
non-zero exit as `compiler_requirement` (binary install impossible; sdist would
need a C toolchain), not a clean pass.
