"""Obligation rows for RES-0125. Quotes must occur verbatim in the named capture."""

from __future__ import annotations

# Capture ids are the fetch-script ids (filename stem).
ROWS: list[dict] = [
    {
        "id": "O-OPENAI-NO-HUMAN-MISREP",
        "obligation": (
            "A listing of model-generated blueprints or presets must not represent "
            "the Output as human-generated when it was not."
        ),
        "required_versus_proposed": "required-by-terms",
        "who_is_bound": "user of OpenAI consumer Terms of Use (Output recipient / publisher)",
        "marketplace_must_carry": ["generation_method", "generation_disclosed_in_listing"],
        "capture_id": "wayback-openai-terms-latest",
        "quote": "Represent that Output was human-generated when it was not",
        "document_version": "OpenAI Terms of Use Effective: January 1, 2026",
        "archive_warc": "20260823021834",
        "commit_sha": None,
        "scope_note": (
            "Live openai.com returned HTTP 403 this run (three URLs). Claim is pinned "
            "to the Wayback capture, not to an unversioned live HTML surface."
        ),
        "overclaim_guard": (
            "The clause is a use-restriction, not a mandated C2PA/SPDX schema. It "
            "does require the marketplace not to label model Output as human-authored."
        ),
    },
    {
        "id": "O-OPENAI-OUTPUT-ASSIGNMENT",
        "obligation": (
            "As between the user and OpenAI, and to the extent permitted by applicable "
            "law, the user owns Output; OpenAI assigns its interest (if any) in Output."
        ),
        "required_versus_proposed": "required-by-terms",
        "who_is_bound": "OpenAI (assignment) / user (responsibility for Content)",
        "marketplace_must_carry": ["spdx_license", "publisher_id"],
        "capture_id": "wayback-openai-terms-latest",
        "quote": (
            "you (a) retain your ownership rights in Input and (b) own the Output. "
            "We hereby assign to you all our right, title, and interest, if any, in and to Output."
        ),
        "document_version": "OpenAI Terms of Use Effective: January 1, 2026",
        "archive_warc": "20260823021834",
        "commit_sha": None,
        "scope_note": "Ownership assignment is not a provenance-disclosure schema.",
        "overclaim_guard": (
            "Does not grant copyright in AI-generated material that US law would "
            "refuse to register; see O-US-COPYRIGHT-REG-DISCLOSURE."
        ),
    },
    {
        "id": "O-ANTHROPIC-OUTPUT-ASSIGNMENT",
        "obligation": (
            "Subject to compliance with Anthropic Consumer Terms, Anthropic assigns "
            "to the user all its right, title, and interest (if any) in Outputs."
        ),
        "required_versus_proposed": "required-by-terms",
        "who_is_bound": "Anthropic / user of Consumer Terms of Service",
        "marketplace_must_carry": ["spdx_license", "publisher_id"],
        "capture_id": "anthropic-consumer-terms",
        "quote": (
            "we assign to you all our right, title, and interest (if any) in Outputs"
        ),
        "document_version": "Anthropic Consumer Terms of Service Effective October 8, 2025",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": "Commercial Terms (Effective June 17, 2025) separately state Customer owns Outputs.",
        "overclaim_guard": "No machine-readable marketplace provenance format is named.",
    },
    {
        "id": "O-GOOGLE-GEMINI-LAW-ATTRIBUTION",
        "obligation": (
            "Gemini API Additional Terms require complying with applicable law when "
            "using generated content, which may require attribution to users when "
            "returned as part of an API call. Google does not claim ownership of generated content."
        ),
        "required_versus_proposed": "required-by-terms",
        "who_is_bound": "Gemini API / Google AI Studio user",
        "marketplace_must_carry": ["generation_method", "generation_disclosed_in_listing"],
        "capture_id": "gemini-api-terms",
        "quote": (
            "which may require the provision of attribution to your users when returned "
            "as part of an API call"
        ),
        "document_version": "Gemini API Additional Terms of Service Effective March 23, 2026",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "The attribution duty is conditional on applicable law, not a Google-invented "
            "C2PA mandate."
        ),
        "overclaim_guard": "Does not by itself require Content Credentials on a blueprint listing.",
    },
    {
        "id": "O-GITHUB-AI-OUTPUT-OWNERSHIP",
        "obligation": (
            "GitHub does not claim ownership of Input or Output from AI Features. "
            "The user is responsible for reviewing Output and for third-party licenses."
        ),
        "required_versus_proposed": "required-by-terms",
        "who_is_bound": "GitHub AI Features users under GitHub Terms of Service Section J",
        "marketplace_must_carry": ["spdx_license", "generation_method"],
        "capture_id": "github-tos",
        "quote": "GitHub does not claim ownership of your Input or Output",
        "document_version": "GitHub Terms of Service Effective date: April 27, 2026 Section J",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "GitHub Copilot Product Specific Terms (Business/Enterprise) were HTTP 500 then "
            "404 this run; Section J is the rail named for other Copilot users."
        ),
        "overclaim_guard": "No required provenance header for marketplace listings is stated.",
    },
    {
        "id": "O-EU-ART50-2-PROVIDER-MARKING",
        "obligation": (
            "In the EU, providers of AI systems (including GPAI) that generate synthetic "
            "audio, image, video or text must mark outputs in a machine-readable format "
            "as artificially generated or manipulated, as far as technically feasible."
        ),
        "required_versus_proposed": "required-by-law-somewhere",
        "who_is_bound": "providers of those AI systems (not automatically a third-party marketplace)",
        "marketplace_must_carry": [],
        "capture_id": "eurlex-ai-act-2024-1689",
        "quote": (
            "marked in a machine-readable format and detectable as artificially generated "
            "or manipulated"
        ),
        "document_version": "Regulation (EU) 2024/1689 Article 50(2) CELEX:32024R1689",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "This binds the model/system provider. A marketplace that only lists blueprints "
            "generated by someone else's model is not Art 50(2) by that listing alone."
        ),
        "overclaim_guard": (
            "Art 50 does not name C2PA. Art 50(7) encourages codes of practice; treating "
            "C2PA as the legally required format would be overclaim."
        ),
    },
    {
        "id": "O-EU-ART50-4-DEPLOYER-DISCLOSURE",
        "obligation": (
            "EU deployers must disclose deepfake image/audio/video as artificially generated. "
            "Deployers of systems that generate or manipulate text published to inform the "
            "public on matters of public interest must disclose unless human review plus "
            "editorial responsibility applies."
        ),
        "required_versus_proposed": "required-by-law-somewhere",
        "who_is_bound": "deployers in the Art 50(4) fact patterns",
        "marketplace_must_carry": ["generation_method", "generation_disclosed_in_listing"],
        "capture_id": "eurlex-ai-act-2024-1689",
        "quote": (
            "Deployers of an AI system that generates or manipulates text which is published "
            "with the purpose of informing the public on matters of public interest shall "
            "disclose that the text has been artificially generated or manipulated"
        ),
        "document_version": "Regulation (EU) 2024/1689 Article 50(4) CELEX:32024R1689",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "A software blueprint/preset is not a deepfake. The text-disclosure limb is for "
            "public-interest informing publications, not for code catalogs as such."
        ),
        "overclaim_guard": (
            "Do not treat every marketplace blueprint listing as Art 50(4) text disclosure."
        ),
    },
    {
        "id": "O-US-COPYRIGHT-REG-DISCLOSURE",
        "obligation": (
            "US Copyright Office registration applicants must disclose more-than-de-minimis "
            "AI-generated content in the application and describe the human author's contribution."
        ),
        "required_versus_proposed": "required-by-law-somewhere",
        "who_is_bound": "copyright registration applicants in the United States",
        "marketplace_must_carry": ["generation_method", "ai_generated_extent"],
        "capture_id": "us-fr-ai-copyright-registration-88fr16190",
        "quote": (
            "applicants have a duty to disclose the inclusion of AI-generated content in a "
            "work submitted for registration"
        ),
        "document_version": "88 FR 16190, effective March 16, 2023",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "This is a registration-form duty, not a general publication or marketplace-posting "
            "mandate. Carrying generation_method on the listing makes a later registration truthful."
        ),
        "overclaim_guard": "Not a requirement to attach C2PA to every marketplace row.",
    },
    {
        "id": "O-CA-AB2013-TRAINING-DATA",
        "obligation": (
            "California Civil Code 3111 (AB 2013, Chapter 817) requires a developer of a "
            "generative AI system or service to post training-data documentation on the "
            "developer website on or before January 1, 2026 (and before each subsequent "
            "public release/substantial modification)."
        ),
        "required_versus_proposed": "required-by-law-somewhere",
        "who_is_bound": "developers of GenAI systems/services publicly available to Californians",
        "marketplace_must_carry": [],
        "capture_id": "california-ab2013-text",
        "quote": (
            "the developer of the system or service shall post on the developer’s internet "
            "website documentation regarding the data used by the developer to train the "
            "generative artificial intelligence system or service"
        ),
        "document_version": "AB 2013 (2023-2024) Chapter 817, Civil Code 3111, approved 2024-09-28",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": (
            "Applies to developers of the GenAI system, not to a marketplace listing of a "
            "blueprint generated by a third-party model."
        ),
        "overclaim_guard": "Not a blueprint-row provenance field.",
    },
    {
        "id": "O-C2PA-CONTENT-CREDENTIALS",
        "obligation": (
            "C2PA Content Credentials (a C2PA Manifest) can carry cryptographically bound "
            "assertions about origin, modifications, and use of AI, including digitalSourceType "
            "values such as trainedAlgorithmicMedia. Adopting C2PA on marketplace artifacts "
            "is a proposed interoperability method, not a term or a named legal exclusive format."
        ),
        "required_versus_proposed": "proposed-norm",
        "who_is_bound": "implementers who choose to emit Content Credentials",
        "marketplace_must_carry": ["c2pa_manifest"],
        "capture_id": "c2pa-explainer",
        "quote": "Content Credentials, also known as a C2PA Manifest",
        "document_version": "C2PA Specifications 2.3 Explainer (spec.c2pa.org)",
        "archive_warc": None,
        "commit_sha": "9c58c8c27044e44e8601f6ab13f1bcac1376eb1f",
        "scope_note": (
            "GitHub c2pa-org/specifications main at the named SHA. Spec 2.3 landing was "
            "fetched live; treating C2PA as legally required would be overclaim."
        ),
        "overclaim_guard": "Proposed-norm by design. Catalog control requires at least one such row.",
    },
    {
        "id": "O-SPDX-3-AI-PROFILE",
        "obligation": (
            "SPDX 3.0.1 AI profile documents AI software packages (systems/models/datasets) "
            "including AIPackage and informationAboutTraining. Using it as marketplace "
            "metadata for a blueprint listing is a proposed SBOM/AI-BOM practice, not a "
            "vendor-term requirement."
        ),
        "required_versus_proposed": "proposed-norm",
        "who_is_bound": "implementers who choose SPDX 3 AI profile conformance",
        "marketplace_must_carry": ["spdx_ai_package"],
        "capture_id": "spdx-3.0.1-AI.md",
        "quote": (
            "The AI Profile is designed to provide a standardized way of documenting and "
            "sharing information about AI software packages"
        ),
        "document_version": "SPDX 3.0.1 tag 3.0.1 (commit a745f63e8643d5ae0f0851fcfa6836085308f80b)",
        "archive_warc": None,
        "commit_sha": "a745f63e8643d5ae0f0851fcfa6836085308f80b",
        "scope_note": "AIPackage describes an AI application or trained model, not a workflow blueprint per se.",
        "overclaim_guard": "Proposed-norm. Do not treat SPDX AIPackage as required listing metadata.",
    },
    {
        "id": "O-CC-SIGNALS",
        "obligation": (
            "Creative Commons CC Signals is offered as a hoped-for spectrum of preferences "
            "for when work is used in AI. It is developmental, not an adopted marketplace requirement."
        ),
        "required_versus_proposed": "proposed-norm",
        "who_is_bound": "none (preference vocabulary under development)",
        "marketplace_must_carry": ["cc_signals"],
        "capture_id": "creativecommons-cc-signals",
        "quote": (
            "our hope is that CC signals will offer creators a spectrum of preferences "
            "for when their work is used in AI"
        ),
        "document_version": "Creative Commons CC Signals page (live fetch 2026-08-24)",
        "archive_warc": None,
        "commit_sha": None,
        "scope_note": "Moving HTML page; claim is pinned to capture sha256 + fetch timestamp.",
        "overclaim_guard": "Explicitly proposed. Catalog control row.",
    },
]


MARKETPLACE_FIELDS: list[dict] = [
    {
        "field": "generation_method",
        "required_versus_proposed": "required-by-terms",
        "values": ["human", "a2-ssot-generator", "model-assisted", "model-generated"],
        "why": (
            "O-OPENAI-NO-HUMAN-MISREP: a listing that omits this field can present "
            "model Output as if a person wrote it. Distinguishes A2 registry projection "
            "(_generated.generator_version) from LLM generation."
        ),
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "generation_disclosed_in_listing",
        "required_versus_proposed": "required-by-terms",
        "values": ["true", "false"],
        "why": "The method must be visible in the listing UI, not only in a hidden JSON key.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "ai_generated_extent",
        "required_versus_proposed": "required-by-law-somewhere",
        "values": ["none", "de-minimis", "substantial", "unknown"],
        "why": "O-US-COPYRIGHT-REG-DISCLOSURE: needed if the listing is later registered.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "spdx_license",
        "required_versus_proposed": "required-by-terms",
        "values": ["SPDX identifier; LICENSE-ABSENT blocks publication (IMP-0093)"],
        "why": "Publisher still declares a license for the listing; vendor assignment is not a license string.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "publisher_id",
        "required_versus_proposed": "required-by-terms",
        "values": ["publisher registry id (IMP-0075)"],
        "why": "Someone must be accountable for the listing representation.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "name",
        "required_versus_proposed": "required-by-terms",
        "values": ["package name"],
        "why": "Already required by lockfile.schema.json; not AI provenance.",
        "present_in_lockfile_schema": True,
        "present_in_a2_marketplace_header": True,
    },
    {
        "field": "version",
        "required_versus_proposed": "required-by-terms",
        "values": ["package version"],
        "why": "Already required by lockfile.schema.json.",
        "present_in_lockfile_schema": True,
        "present_in_a2_marketplace_header": True,
    },
    {
        "field": "source_url",
        "required_versus_proposed": "required-by-terms",
        "values": ["upstream URL"],
        "why": "Already required by lockfile.schema.json; pin of bits, not of generation method.",
        "present_in_lockfile_schema": True,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "digest",
        "required_versus_proposed": "required-by-terms",
        "values": ["sha256 hex"],
        "why": "Already required by lockfile.schema.json (IMP-0084).",
        "present_in_lockfile_schema": True,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "_generated.generator_id",
        "required_versus_proposed": "proposed-norm",
        "values": ["a2-ssot-generator"],
        "why": (
            "A2 marketplace entries already carry generator provenance for registry "
            "projection. That is not LLM provenance and must not be reused as such."
        ),
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": True,
    },
    {
        "field": "c2pa_manifest",
        "required_versus_proposed": "proposed-norm",
        "values": ["Content Credentials bytes or URI"],
        "why": "O-C2PA-CONTENT-CREDENTIALS",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "spdx_ai_package",
        "required_versus_proposed": "proposed-norm",
        "values": ["SPDX 3 AIPackage fragment"],
        "why": "O-SPDX-3-AI-PROFILE",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "cc_signals",
        "required_versus_proposed": "proposed-norm",
        "values": ["CC Signals preference codes when the vocabulary ships"],
        "why": "O-CC-SIGNALS",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "model_vendor",
        "required_versus_proposed": "proposed-norm",
        "values": ["openai", "anthropic", "google", "github", "other", "none"],
        "why": "Useful pin; not required by the captured assignment clauses.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "model_id",
        "required_versus_proposed": "proposed-norm",
        "values": ["vendor model identifier"],
        "why": "Proposed pin of the generating model.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
    {
        "field": "model_version",
        "required_versus_proposed": "proposed-norm",
        "values": ["vendor model version / snapshot id"],
        "why": "Unversioned model names are the 05-ECO moving-surface defect class.",
        "present_in_lockfile_schema": False,
        "present_in_a2_marketplace_header": False,
    },
]
