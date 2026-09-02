#!/usr/bin/env python3
"""Primary-source catalog for RES-0158 SAT-to-protocol transfer.

Each source is a two-rail pair candidate. Capture tries urls in order.
Needles are substrings that MUST appear in the captured bytes (or extracted
PDF text) before a claim may cite the source.
"""
from __future__ import annotations

UA = (
    "RES-0158-sat-transfer/1.0 "
    "(research capture; +https://www.cia.gov/resources/csi/)"
)

SOURCES: list[dict] = [
    {
        "id": "cia-tradecraft-primer",
        "rail": "R1-official-manual",
        "kind": "structured-official-pdf",
        "urls": [
            "https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf",
            "https://web.archive.org/web/20200923154641id_/"
            "https://www.cia.gov/library/center-for-the-study-of-intelligence/"
            "csi-publications/books-and-monographs/Tradecraft-Primer-apr09.pdf",
        ],
        "covers": [
            "ach",
            "key-assumptions-check",
            "devils-advocacy",
            "team-a-team-b",
        ],
    },
    {
        "id": "heuer-pia-html",
        "rail": "R2-method-origin",
        "kind": "prose-html-chapter",
        "urls": [
            "https://web.archive.org/web/20201112024629id_/"
            "https://www.cia.gov/library/center-for-the-study-of-intelligence/"
            "csi-publications/books-and-monographs/"
            "psychology-of-intelligence-analysis/art11.html",
            "https://web.archive.org/web/20170716200000id_/"
            "https://www.cia.gov/library/center-for-the-study-of-intelligence/"
            "csi-publications/books-and-monographs/"
            "psychology-of-intelligence-analysis/art11.html",
            "https://www.cia.gov/resources/csi/static/"
            "Psychology-of-Intelligence-Analysis.pdf",
        ],
        "covers": ["ach", "ach-failure"],
    },
    {
        "id": "icd-203-pdf",
        "rail": "R1-official-standard",
        "kind": "structured-official-pdf",
        "urls": [
            "https://www.dni.gov/files/documents/ICD/ICD-203.pdf",
            "https://www.dni.gov/files/documents/ICD/ICD-203-Analytic-Standards.pdf",
            "https://www.dni.gov/files/ODNI/documents/ICD/"
            "ICD-203-Analytic-Standards-21-Dec-2022.pdf",
            "https://irp.fas.org/dni/icd/icd-203.pdf",
            "https://fas.org/irp/dni/icd/icd-203.pdf",
        ],
        "covers": ["icd-203"],
    },
    {
        "id": "odni-objectivity-html",
        "rail": "R2-official-prose",
        "kind": "prose-html",
        "urls": [
            "https://www.dni.gov/index.php/how-we-work/objectivity",
            "https://www.dni.gov/index.php/who-we-are/organizations/"
            "123-about/1726-objectivity?tmpl=component",
        ],
        "covers": ["icd-203"],
    },
    {
        "id": "rand-rr1408",
        "rail": "R1-peer-eval",
        "kind": "structured-eval-pdf",
        "urls": [
            "https://www.rand.org/content/dam/rand/pubs/research_reports/"
            "RR1400/RR1408/RAND_RR1408.pdf",
            "https://www.rand.org/pubs/research_reports/RR1408.html",
        ],
        "covers": ["ach-failure", "sat-eval"],
    },
    {
        "id": "chang-sat-html",
        "rail": "R2-peer-eval",
        "kind": "prose-abstract-html",
        "urls": [
            "https://www.tandfonline.com/doi/full/10.1080/02684527.2017.1400230",
            "https://doi.org/10.1080/02684527.2017.1400230",
            "https://www.tandfonline.com/doi/abs/10.1080/02684527.2017.1400230",
        ],
        "covers": ["ach-failure"],
    },
    {
        "id": "veinott-premortem",
        "rail": "R1-method-eval",
        "kind": "structured-eval-pdf",
        "urls": [
            "https://idl.iscram.org/files/veinott/2010/1048_Veinott_etal2010.pdf",
            "https://idl.iscram.org/files/veinott/2010/1048_Veinott_etal2010.pdf",
            "https://digitalcommons.mtu.edu/cgi/viewcontent.cgi?"
            "article=1463&context=etdr",
        ],
        "covers": ["premortem"],
    },
    {
        "id": "klein-premortem-html",
        "rail": "R2-method-origin",
        "kind": "prose-html",
        "urls": [
            "https://www.psychologytoday.com/us/blog/seeing-what-others-dont/"
            "202101/the-pre-mortem-method",
            "https://hbr.org/2007/09/performing-a-project-premortem",
        ],
        "covers": ["premortem"],
    },
]
