SCHEMA_VERSION = 1

# Fixture launcher frozen by TST-0026. The gate hashes this file; an unversioned
# edit must be rejected. Do not edit without a migration entry and a bump.
PREAMBLE = "freeze-once-first-wave"


def main() -> None:
    print(f"fanout schema_version={SCHEMA_VERSION} preamble={PREAMBLE}")


if __name__ == "__main__":
    main()
