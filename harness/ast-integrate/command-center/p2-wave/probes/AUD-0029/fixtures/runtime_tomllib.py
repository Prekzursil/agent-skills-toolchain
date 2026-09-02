"""Runtime-only 3.11 stdlib. Static presence of the import is probe 1; this
file is executed under the floor interpreter by probe 2.
"""
import tomllib

print("tomllib-ok", bool(tomllib.loads("x = 1")))
