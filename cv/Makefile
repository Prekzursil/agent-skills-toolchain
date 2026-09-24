# cv/Makefile - POSIX parity driver for the CV system.
#
# build.ps1 is the canonical driver on Windows (PowerShell 7). This Makefile
# exposes the SAME target names for a POSIX box (Linux, macOS, WSL, Git Bash
# with GNU make). `pwsh ./build.ps1 list` asserts the parity, so the two cannot
# silently drift.
#
# Every target is a thin wrapper around a Python entry point in this directory.
# No rendering logic and no facts live here.
#
#   make preflight      # is the toolchain present
#   make setup          # create .venv and install (one time)
#   make all            # gate -> documents -> verify -> test
#   make view VIEW=ats-en
#
# On Windows the venv interpreter is .venv/Scripts/python.exe; on POSIX it is
# .venv/bin/python. PY is resolved below, and can be overridden:
#   make all PY=/path/to/python

ROOT    := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
OUT     := $(ROOT)/out
VENV    := $(ROOT)/.venv
SYSPY   ?= python3

# Prefer the POSIX venv layout, fall back to the Windows one, then to SYSPY.
PY := $(firstword $(wildcard $(VENV)/bin/python) $(wildcard $(VENV)/Scripts/python.exe) $(SYSPY))

VIEW ?=

.PHONY: help list preflight setup gate research-profile views view templates aux clean-copy all verify test clean

help:
	@echo ''
	@echo '  cv/Makefile - one-command builds (POSIX parity of build.ps1)'
	@echo ''
	@echo '    help              Print this table.'
	@echo '    list              List what the drivers actually expose.'
	@echo '    preflight         Check Python, venv, RenderCV, PyMuPDF are present and runnable.'
	@echo '    setup             Create .venv and install the render toolchain (one time).'
	@echo '    gate              Run the fail-closed zero-fabrication lint over profile.yaml.'
	@echo '    research-profile  Deliverable #1: the one-page research profile.'
	@echo '    views             All rendercv views via tools/build.py --all.'
	@echo '    view VIEW=<name>  One named view.'
	@echo '    templates         ats-en + ro documents via templates/render_template.py --all.'
	@echo '    aux               Academic CV + cover letters + LinkedIn + platform packs + Europass.'
	@echo '    clean-copy        Same as aux with TODO markers omitted, into out/templates-clean.'
	@echo '    all               gate -> documents -> verify -> test.'
	@echo '    verify            Re-run the PDF no-regression contract over every PDF in out/.'
	@echo '    test              pytest (122 cases) + the three gate self-tests.'
	@echo '    clean             Delete out/ (generated documents only; never profile.yaml).'
	@echo ''
	@echo '  Documents land in out/ . Nothing here invents a fact: every string'
	@echo '  comes from profile.yaml and is gated by tools/zerofab.py.'
	@echo ''

list:
	@echo '==> views exposed by tools/build.py'
	@"$(PY)" "$(ROOT)/tools/build.py" --list-views
	@echo '==> templates exposed by templates/render_template.py'
	@"$(PY)" "$(ROOT)/templates/render_template.py" --list
	@echo '==> auxiliary views exposed by templates/emit.py'
	@"$(PY)" "$(ROOT)/templates/emit.py" --list

preflight:
	@echo '==> preflight'
	@"$(PY)" -V
	@"$(PY)" -c 'import importlib.metadata as m; print("  OK    rendercv  ", m.version("rendercv"))'
	@"$(PY)" -c 'import importlib.metadata as m; print("  OK    pymupdf   ", m.version("pymupdf"))'
	@"$(PY)" -c 'import yaml; print("  OK    pyyaml    ", yaml.__version__)'
	@"$(PY)" -c 'import importlib.metadata as m; print("  OK    typst     ", m.version("typst"))'
	@test -f "$(ROOT)/profile.yaml" && echo '  OK    profile.yaml present'
	@echo 'SUCCESS:preflight'

setup:
	@echo '==> setup: creating .venv and installing the render toolchain'
	"$(SYSPY)" -m venv "$(VENV)"
	"$(PY)" -m pip install --upgrade pip
	"$(PY)" -m pip install 'rendercv[full]' pymupdf ruamel.yaml pyyaml jinja2 pytest ruff
	@$(MAKE) --no-print-directory preflight
	@echo 'SUCCESS:setup'

gate:
	"$(PY)" "$(ROOT)/tools/zerofab.py" "$(ROOT)/profile.yaml"

research-profile:
	"$(PY)" "$(ROOT)/templates/research-profile/render.py"

views:
	"$(PY)" "$(ROOT)/tools/build.py" --all

view:
	@test -n "$(VIEW)" || (echo 'usage: make view VIEW=<name>   (see: make list)'; exit 2)
	"$(PY)" "$(ROOT)/tools/build.py" --view "$(VIEW)"

templates:
	"$(PY)" "$(ROOT)/templates/render_template.py" --all

aux:
	"$(PY)" "$(ROOT)/templates/emit.py" --all

clean-copy:
	"$(PY)" "$(ROOT)/templates/emit.py" --all --todo omit --out "$(OUT)/templates-clean"

# Only DELIVERABLES are swept. tools/verify.py --selftest writes deliberately
# broken fixtures (US-Letter, two-column, ligature-damaged) into out/_selftest/
# to prove each check fires; verifying those would fail by design. Any
# underscore-prefixed directory under out/ is fixtures, not documents.
verify:
	@set -e; \
	found=0; \
	for p in $$(find "$(OUT)" -name '*.pdf' -not -path '*/_*/*' 2>/dev/null); do \
	    found=1; \
	    echo "==> verify $$(basename $$p)"; \
	    "$(PY)" "$(ROOT)/tools/verify.py" --pdf "$$p"; \
	done; \
	if [ $$found -eq 0 ]; then echo '  (no PDFs in out/ yet - nothing to verify)'; fi
	@echo 'SUCCESS:verify'

test:
	"$(PY)" -m pytest "$(ROOT)/tools/test_zerofab.py" "$(ROOT)/tools/test_build.py" "$(ROOT)/templates/test_templates.py" -q
	"$(PY)" "$(ROOT)/tools/verify.py" --selftest
	"$(PY)" "$(ROOT)/templates/docgate.py" --selftest
	"$(PY)" "$(ROOT)/templates/killlist.py" --self-test
	@echo 'SUCCESS:test'

all: preflight gate research-profile views templates aux clean-copy verify test
	@echo 'SUCCESS:all'

clean:
	@rm -rf "$(OUT)" && echo '  removed out/' || true
	@echo 'SUCCESS:clean'
