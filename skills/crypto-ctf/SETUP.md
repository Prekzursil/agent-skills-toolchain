# crypto-ctf — SETUP (external, NOT vendored)

This skill is vendored **stripped**: only `SKILL.md` is under version control. The runtime
machinery the live skill relies on is intentionally **excluded** from the repo because it is
large, self-updating, or carries its own git history + example key material. Recreate it
locally after checkout — it is a one-time setup step, not a code change.

## What is excluded (and why)

| Excluded path | Why it is not vendored |
|---|---|
| `.venv/` (~313 MB) | A local Python virtualenv — rebuild it, never commit it. |
| `RsaCtfTool/` | A separate upstream clone with its **own `.git/`** and example `*.priv` / `*.pem` / `*.key` files. Vendoring it would nest a repo and check in key material. |
| `node_modules/`, `__pycache__/`, caches | Build/deploy bloat. |

## Recreate the runtime (matches the paths in `SKILL.md`)

The `SKILL.md` references a dedicated venv and an editable `RsaCtfTool` clone next to the
skill. On deploy (live skill dir is `~/.claude/skills/crypto-ctf/`), rebuild them:

```bash
cd ~/.claude/skills/crypto-ctf

# 1. Dedicated venv (do NOT pollute the global interpreter)
python -m venv .venv
PY="$PWD/.venv/Scripts/python.exe"   # Windows; use .venv/bin/python on Linux/macOS
"$PY" -m pip install --upgrade pip
"$PY" -m pip install pycryptodome gmpy2 sympy pwntools z3-solver

# 2. RsaCtfTool — external clone, installed editable (its deps come with it)
git clone https://github.com/RsaCtfTool/RsaCtfTool.git RsaCtfTool
"$PY" -m pip install -e RsaCtfTool

# 3. Verify the stack (the SKILL.md self-test)
"$PY" -c "import Crypto, gmpy2, sympy, z3, pwnlib; from Crypto.Util.number import inverse; print('crypto-ctf venv OK', Crypto.__version__, gmpy2.version(), sympy.__version__)"
```

After this, every command in `SKILL.md` (the `.venv` python + `python -m RsaCtfTool.main ...`)
works against the local runtime. Nothing above is tracked in this repo.
