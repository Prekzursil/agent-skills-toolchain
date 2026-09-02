# Fixture README — documented test depends on an uncommitted ambient file

```bash
python3 -c "import pathlib, sys; sys.exit(0 if pathlib.Path('ambient.py').is_file() else 3)"
```
