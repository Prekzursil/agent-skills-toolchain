#!/usr/bin/env python3
GATE_SUMMARY = "reports/gate-summary.json"
def load(root):
    return (root / GATE_SUMMARY).read_text(encoding='utf-8')
