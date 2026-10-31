#!/usr/bin/env bash
# One-time cv-studio engine setup (POSIX / WSL / Linux / macOS).
# Creates an ISOLATED venv with RenderCV[full] (bundled Typst) + PyMuPDF, so the
# system Python is never polluted (rendercv[full] pins typer>=0.25). Idempotent.
set -euo pipefail

VENV="${1:-$HOME/.local/share/cv-studio/venv}"
echo "cv-studio setup -> $VENV"

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "FAILED: python3 not found"; exit 1; }

[ -d "$VENV" ] || { mkdir -p "$(dirname "$VENV")"; "$PY" -m venv "$VENV"; }
VPY="$VENV/bin/python"
[ -x "$VPY" ] || { echo "FAILED: venv python missing at $VPY"; exit 1; }

"$VPY" -m pip install --upgrade --quiet pip
"$VPY" -m pip install --upgrade --quiet "rendercv[full]" pymupdf
echo "  rendercv: $("$VENV/bin/rendercv" --version 2>&1 | head -1)"

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLE="$SKILL_DIR/assets/sample-profile.yaml"
if [ -f "$SAMPLE" ]; then
  "$VPY" "$SKILL_DIR/scripts/cvstudio.py" build "$SAMPLE" --out "/tmp/cv-studio-smoke"
  echo "SUCCESS: cv-studio ready. Run: $VPY scripts/cvstudio.py build profile.yaml"
else
  echo "SUCCESS: engine installed (sample not found; skipped smoke)."
fi
