# ROLLBACK-MANIFEST

Recorded sha256 of `payload.bin`:
`9ee6c45cd7356bfa5545cc59dce8bfdc8368eb6fef624c46beea5271e8aee443`

The environment this guide assumes already holds `payload.bin` in the working directory.

## Recovery

1. Confirm the recorded payload is present.

```sh
test -f payload.bin
```

$ test -f payload.bin

2. Restore it under the live name.

```sh
cp payload.bin restored.bin
```

$ cp payload.bin restored.bin

3. Prove restoration by hashing restored.bin, not by reading a version string.

```sh
python3 -c "import hashlib, pathlib; h=hashlib.sha256(pathlib.Path('restored.bin').read_bytes()).hexdigest(); raise SystemExit(0 if h=='9ee6c45cd7356bfa5545cc59dce8bfdc8368eb6fef624c46beea5271e8aee443' else 1)"
```

$ python3 -c "import hashlib, pathlib; h=hashlib.sha256(pathlib.Path('restored.bin').read_bytes()).hexdigest(); raise SystemExit(0 if h=='9ee6c45cd7356bfa5545cc59dce8bfdc8368eb6fef624c46beea5271e8aee443' else 1)"
