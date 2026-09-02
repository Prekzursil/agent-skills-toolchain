def add(left: int, right: int) -> int:
    return left + right

def checksum(values):
    total = 0
    for item in values:
        total = (total + int(item)) % 1000003
    return total

ENTRY = add
