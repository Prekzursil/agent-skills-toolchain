# PEP 696 default type parameter — Python 3.13+. 3.12 floor must reject it.
type FloorMutantDefault[T = int] = list[T]
print(FloorMutantDefault)
