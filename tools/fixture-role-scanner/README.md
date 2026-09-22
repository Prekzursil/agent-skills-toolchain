# Fixture / content role scanners (TST-0341)

Rebuilds programme scanners so matches are judged by semantic role
(`hooks/_shared/use_vs_mention.py`) rather than payload substring presence.

```bash
python3 tools/fixture-role-scanner/role_scanner.py
python3 tools/fixture-role-scanner/measure_corpora.py
python3 -m pytest tools/fixture-role-scanner/tests -q
```

Evidence contract: for each rebuilt scanner (command / marker / stub / result /
secret / pathword), report FP flags on the historical false-positive corpus
(must be 0) AND TP flags on the true-positive corpus (must equal corpus size).
