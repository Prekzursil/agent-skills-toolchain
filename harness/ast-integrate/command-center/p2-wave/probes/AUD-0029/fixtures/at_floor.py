"""Control: features at or below declared Python 3.10. Must NOT be flagged."""


def add(a, b):
    return a + b


def main():
    xs = [1, 2, 3]
    total = 0
    for item in xs:
        total = total + item
    return add(2, 3) + total


if __name__ == "__main__":
    print(main())
