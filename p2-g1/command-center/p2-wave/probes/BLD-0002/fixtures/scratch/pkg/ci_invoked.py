"""CI invocation target: python -m pkg.ci_invoked."""


def run() -> str:
    return "ci-ok"


if __name__ == "__main__":
    print(run())
