"""Load planted fixtures plus in-tree acquisition captures for WFA-0031."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_PATH = REPO / "command-center" / "wfa" / "legal_gate.py"
FIXTURES = HERE / "fixtures"
RES0109 = REPO / "command-center" / "p2-wave" / "probes" / "RES-0109" / "captures"
RES0136 = REPO / "command-center" / "p2-wave" / "probes" / "RES-0136" / "fixtures"


def load_gate():
    spec = importlib.util.spec_from_file_location("wfa_legal_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {GATE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wfa_legal_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            return path.read_text(encoding="latin-1")
        except OSError:
            return None


def _json(path: Path) -> Any:
    text = _read(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def planted_sources(gate) -> list:
    SourceInput = gate.SourceInput
    rows = []

    def plant(name: str, *, license_name: str | None, api_name: str | None,
              readme_name: str | None = None, terms_name: str | None = None,
              http_status: int | None = None):
        root = FIXTURES / name
        lic = _read(root / license_name) if license_name else None
        api = _json(root / api_name) if api_name else None
        readme = _read(root / readme_name) if readme_name else None
        terms = _read(root / terms_name) if terms_name else None
        rows.append(
            SourceInput(
                source_id=f"plant:{name}",
                origin="planted-fixture",
                license_text=lic,
                license_filename=license_name,
                license_http_status=http_status if license_name else 404,
                api_doc=api,
                readme_text=readme,
                terms_text=terms,
            )
        )

    plant("plant-unlicensed", license_name=None, api_name="api.json",
          readme_name="README.md", http_status=404)
    plant("plant-gpl3", license_name="LICENSE", api_name="api.json")
    plant("plant-apache2", license_name="LICENSE", api_name="api.json")
    plant("plant-rider", license_name="LICENSE", api_name="api.json")
    plant("plant-disagree", license_name="LICENSE", api_name="api.json")
    plant("plant-mit-agree", license_name="LICENSE", api_name="api.json")
    plant("plant-tos-evade", license_name=None, api_name=None,
          terms_name="TERMS.md", http_status=404)
    return rows


def res0109_sources(gate) -> list:
    SourceInput = gate.SourceInput
    index_path = RES0109 / "captures_index.json"
    index = _json(index_path)
    if not isinstance(index, dict):
        return []
    out = []
    for cand in index.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        cid = str(cand.get("id") or cand.get("repo") or "unknown")
        repo = str(cand.get("repo") or cid)
        lic_meta = cand.get("license_file") or {}
        api_meta = cand.get("api") or {}
        readme_meta = cand.get("readme") or {}
        eco_meta = cand.get("ecosystems") or {}
        lic_rel = lic_meta.get("path")
        api_rel = api_meta.get("path")
        readme_rel = readme_meta.get("path")
        lic_status = lic_meta.get("http_status")
        lic_text = _read(RES0109 / lic_rel) if lic_rel else None
        if lic_status not in (None, 200):
            lic_text = None
        api_doc = _json(RES0109 / api_rel) if api_rel else None
        classifier = api_meta.get("classifier_spdx")
        eco_license = eco_meta.get("license")
        override = None
        override_avail = None
        override_route = None
        # If GitHub API payload is an error, fall back to index/ecosyste.ms
        # host metadata — still independent of the LICENSE blob.
        github_ok = (
            isinstance(api_doc, dict)
            and not gate.api_payload_is_error(api_doc)
            and api_meta.get("error") in (None, "")
            and api_meta.get("http_status") in (None, 200)
        )
        if not github_ok:
            api_doc = None
            if classifier:
                override = str(classifier)
                override_avail = True
                override_route = "captures_index.classifier_spdx"
            elif eco_license:
                override = str(eco_license)
                override_avail = True
                override_route = "ecosyste.ms.license"
            else:
                override_avail = False
                override_route = "host-metadata-unavailable"
        out.append(
            SourceInput(
                source_id=f"res0109:{repo}",
                origin="res-0109-captures",
                license_text=lic_text,
                license_filename=lic_meta.get("filename") or lic_rel,
                license_http_status=lic_status,
                api_doc=api_doc,
                api_spdx_override=override,
                api_available_override=override_avail,
                api_route_override=override_route,
                readme_text=_read(RES0109 / readme_rel) if readme_rel else None,
            )
        )
    return out


def res0136_sources(gate) -> list:
    SourceInput = gate.SourceInput
    out = []
    for name in ("llama3.1.LICENSE", "mcp_agent_mail.LICENSE"):
        path = RES0136 / name
        text = _read(path)
        if text is None:
            continue
        out.append(
            SourceInput(
                source_id=f"res0136:{name}",
                origin="res-0136-fixtures",
                license_text=text,
                license_filename=name,
                license_http_status=200,
                api_doc=None,
                api_available_override=False,
                api_route_override="no-host-api-for-fixture",
            )
        )
    return out


def all_sources(gate) -> list:
    return planted_sources(gate) + res0109_sources(gate) + res0136_sources(gate)
