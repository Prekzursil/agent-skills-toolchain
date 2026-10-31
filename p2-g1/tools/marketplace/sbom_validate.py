"""SBOM document validator used as a supporting artifact for IMP-0092."""


def validate_sbom(doc: dict) -> list[str]:
    if not isinstance(doc, dict):
        return ["not-object"]
    if "components" in doc and not isinstance(doc.get("components"), list):
        return ["components-not-list"]
    return []
