# Deliberately newer than Python 3.10/3.11: PEP 695 type alias (3.12+).
# A floor interpreter below 3.12 must reject this at compile time.
type FloorMutantAlias = int
print(FloorMutantAlias)
