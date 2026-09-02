#!/usr/bin/env python3
"""Provenance-labeled candidate pool for RES-0146.

Ground truth is the `label` field, assigned from publication provenance
(site/author/publication pattern or a published dataset's collection label).
Classifiers must not read this module.
"""
from __future__ import annotations

# Practitioner: durable named author, standards/project docs, or long-running
# personal engineering blogs. Basis is venue/author history, not prose style.
PRACTITIONER: list[dict] = [
    {
        "id": "p01-pep8",
        "urls": ["https://raw.githubusercontent.com/python/peps/main/peps/pep-0008.rst"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "Python PEP 8: PEP editors / Guido van Rossum; python/peps git history "
            "since 2001. Venue is the language's own process, not a content mill."
        ),
    },
    {
        "id": "p02-pep484",
        "urls": ["https://raw.githubusercontent.com/python/peps/main/peps/pep-0484.rst"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "PEP 484 (Guido van Rossum, Jukka Lehtosalo, Łukasz Langa). Named "
            "language-core authors; python/peps repository."
        ),
    },
    {
        "id": "p03-pep617",
        "urls": ["https://raw.githubusercontent.com/python/peps/main/peps/pep-0617.rst"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "PEP 617 (Pablo Galindo, Lysandros Nikolaou, Guido van Rossum). "
            "CPython core-dev authorship."
        ),
    },
    {
        "id": "p04-pep3333",
        "urls": ["https://raw.githubusercontent.com/python/peps/main/peps/pep-3333.rst"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "PEP 3333 (Phillip J. Eby); WSGI spec under python/peps.",
    },
    {
        "id": "p05-pep572",
        "urls": ["https://raw.githubusercontent.com/python/peps/main/peps/pep-0572.rst"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "PEP 572 (Tim Peters, Guido van Rossum, et al.); python/peps.",
    },
    {
        "id": "p06-linux-coding-style",
        "urls": [
            "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/process/coding-style.rst"
        ],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "Linux kernel Documentation/process/coding-style.rst in torvalds/linux; "
            "kernel.org process docs with a multi-decade git author record."
        ),
    },
    {
        "id": "p07-linux-submitting",
        "urls": [
            "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/process/submitting-patches.rst"
        ],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "Kernel submitting-patches.rst; same kernel.org process corpus.",
    },
    {
        "id": "p08-sqlite-atomic",
        "urls": ["https://www.sqlite.org/atomiccommit.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "sqlite.org atomic-commit documentation by D. Richard Hipp; project "
            "docs on the official domain since the 2000s."
        ),
    },
    {
        "id": "p09-sqlite-wal",
        "urls": ["https://www.sqlite.org/wal.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "sqlite.org WAL documentation; Hipp / SQLite project site.",
    },
    {
        "id": "p10-sqlite-isolation",
        "urls": ["https://www.sqlite.org/isolation.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "sqlite.org isolation.html; official project documentation.",
    },
    {
        "id": "p11-go-errors",
        "urls": [
            "https://raw.githubusercontent.com/golang/website/master/content/doc/faq.md",
            "https://go.dev/doc/faq",
        ],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "Go FAQ on go.dev / golang/website; Go team publication venue.",
    },
    {
        "id": "p12-go-effective",
        "urls": [
            "https://raw.githubusercontent.com/golang/website/master/content/doc/effective_go.md",
            "https://go.dev/doc/effective_go",
        ],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "Effective Go; official Go team document on go.dev.",
    },
    {
        "id": "p13-nginx-proxy",
        "urls": ["https://nginx.org/en/docs/http/ngx_http_proxy_module.html"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "nginx.org module documentation; vendor/project docs with a stable "
            "module-manual publication pattern, not a third-party SEO mill."
        ),
    },
    {
        "id": "p14-nginx-rewrite",
        "urls": ["https://nginx.org/en/docs/http/ngx_http_rewrite_module.html"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "nginx.org rewrite-module manual; official project docs.",
    },
    {
        "id": "p15-rfc8259",
        "urls": ["https://www.rfc-editor.org/rfc/rfc8259.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "RFC 8259 via rfc-editor.org; IETF consensus process, named authors "
            "on the datatracker, publication pattern is standards-track not SEO."
        ),
    },
    {
        "id": "p16-rfc3986",
        "urls": ["https://www.rfc-editor.org/rfc/rfc3986.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "RFC 3986 (Berners-Lee, Fielding, Masinter); rfc-editor.org.",
    },
    {
        "id": "p17-rfc7519",
        "urls": ["https://www.rfc-editor.org/rfc/rfc7519.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "RFC 7519 JWT; IETF / rfc-editor.org.",
    },
    {
        "id": "p18-danluu-consistency",
        "urls": [
            "https://raw.githubusercontent.com/danluu/danluu.github.io/master/_posts/2015-11-20-file-consistency.md",
            "https://danluu.com/file-consistency/",
        ],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": (
            "Dan Luu personal blog; multi-year named-author archive (danluu.com / "
            "github.com/danluu/danluu.github.io)."
        ),
    },
    {
        "id": "p19-danluu-easy",
        "urls": [
            "https://danluu.com/sounds-easy/",
            "https://raw.githubusercontent.com/danluu/danluu.github.io/master/sounds-easy.md",
        ],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": "Dan Luu personal engineering blog; named author, long archive.",
    },
    {
        "id": "p20-jvns-tcpdump",
        "urls": [
            "https://jvns.ca/blog/2018/03/24/tcpdump-is-amazing/",
            "https://raw.githubusercontent.com/jvns/jvns.ca/master/content/blog/2018-03-24-tcpdump-is-amazing.md",
        ],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": (
            "Julia Evans (jvns.ca); named author, blog running since ~2014 with "
            "dated posts and an RSS archive."
        ),
    },
    {
        "id": "p21-jvns-debug",
        "urls": ["https://jvns.ca/blog/2016/03/26/a-few-debugging-tips/"],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": "Julia Evans jvns.ca dated 2016 post; same long-running author site.",
    },
    {
        "id": "p22-fowler-ci",
        "urls": ["https://martinfowler.com/bliki/ContinuousIntegration.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": (
            "Martin Fowler bliki ContinuousIntegration; named author, martinfowler.com "
            "running since the 2000s."
        ),
    },
    {
        "id": "p23-fowler-tdd",
        "urls": ["https://martinfowler.com/bliki/TestDrivenDevelopment.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "Martin Fowler bliki; same named-author venue.",
    },
    {
        "id": "p24-simonw-datasette",
        "urls": [
            "https://simonwillison.net/2020/Sep/10/datasette-014/",
            "https://simonwillison.net/2022/Mar/1/datasette-scale/",
        ],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": (
            "Simon Willison simonwillison.net; named author, blog since 2002, "
            "Datasette project notes."
        ),
    },
    {
        "id": "p25-k8s-blog",
        "urls": [
            "https://raw.githubusercontent.com/kubernetes/website/main/content/en/blog/2018/07-18-11-ways-not-to-get-hacked.md",
            "https://kubernetes.io/blog/2018/07/18/11-ways-not-to-get-hacked/",
        ],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "Official Kubernetes blog on kubernetes.io / kubernetes/website; "
            "project publication venue with named SIG authors."
        ),
    },
    {
        "id": "p26-django-middleware",
        "urls": [
            "https://raw.githubusercontent.com/django/django/main/docs/topics/http/middleware.txt",
            "https://docs.djangoproject.com/en/5.1/topics/http/middleware/",
        ],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "Django official docs (django/django); project documentation venue.",
    },
    {
        "id": "p27-postgres-mvcc",
        "urls": [
            "https://www.postgresql.org/docs/16/mvcc-intro.html",
            "https://www.postgresql.org/docs/current/mvcc-intro.html",
        ],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "postgresql.org official docs; project manual, not a mill domain.",
    },
    {
        "id": "p28-rfc6902",
        "urls": ["https://www.rfc-editor.org/rfc/rfc6902.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "RFC 6902 JSON Patch; rfc-editor.org / IETF.",
    },
    {
        "id": "p29-rfc5789",
        "urls": ["https://www.rfc-editor.org/rfc/rfc5789.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "RFC 5789 PATCH method; rfc-editor.org.",
    },
    {
        "id": "p30-apenwarr",
        "urls": ["https://apenwarr.ca/log/20201227"],
        "label": "practitioner",
        "provenance_kind": "site-history",
        "provenance_basis": "Avery Pennarun apenwarr.ca/log; named author, long-running log.",
    },
    {
        "id": "p31-rust-faq",
        "urls": [
            "https://raw.githubusercontent.com/rust-lang/blog.rust-lang.org/master/posts/2015-04-10-Fearless-Concurrency.md",
            "https://blog.rust-lang.org/2015/04/10/Fearless-Concurrency.html",
        ],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "Official Rust blog; rust-lang.org project venue.",
    },
    {
        "id": "p32-cpython-tutorial",
        "urls": [
            "https://raw.githubusercontent.com/python/cpython/main/Doc/tutorial/appetite.rst"
        ],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "CPython official tutorial (python/cpython Doc/); PSF venue.",
    },
    {
        "id": "p33-gh-actions-security",
        "urls": [
            "https://raw.githubusercontent.com/github/docs/main/content/actions/security-guides/security-hardening-for-github-actions.md",
            "https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions",
        ],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "GitHub Docs (github/docs); vendor product documentation.",
    },
    {
        "id": "p34-httpwg-semantics-intro",
        "urls": ["https://www.rfc-editor.org/rfc/rfc9110.txt"],
        "label": "practitioner",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "RFC 9110 HTTP Semantics; rfc-editor.org / HTTP WG.",
    },
    {
        "id": "p35-sqlite-lang",
        "urls": ["https://www.sqlite.org/lang.html"],
        "label": "practitioner",
        "provenance_kind": "author-record",
        "provenance_basis": "sqlite.org SQL language doc; Hipp project site.",
    },
]

# Mill / machine-generated class: high-volume tutorial-SEO domains (publication
# pattern: large catalog, house/ghost byline, commercial SEO) OR texts whose
# collection label in a published dataset is ChatGPT/API-generated.
# Labels are NOT assigned by reading style.
MILL: list[dict] = [
    {
        "id": "m01-guru99-linux",
        "urls": ["https://www.guru99.com/linux-commands.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "guru99.com: high-volume tutorial mill domain (thousands of similar "
            "how-to pages, commercial SEO catalog, no durable named practitioner "
            "as the site's publication identity)."
        ),
    },
    {
        "id": "m02-guru99-python",
        "urls": ["https://www.guru99.com/python-tutorials.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com Python tutorial hub; same mill catalog pattern.",
    },
    {
        "id": "m03-guru99-git",
        "urls": ["https://www.guru99.com/git-tutorial.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com Git tutorial; mill catalog.",
    },
    {
        "id": "m04-javatpoint-python",
        "urls": ["https://www.javatpoint.com/python-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "javatpoint.com: high-volume tutorial mill (massive parallel topic "
            "catalog, house brand, SEO acquisition pattern)."
        ),
    },
    {
        "id": "m05-javatpoint-linux",
        "urls": ["https://www.javatpoint.com/linux-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "javatpoint.com Linux tutorial; mill catalog.",
    },
    {
        "id": "m06-javatpoint-git",
        "urls": ["https://www.javatpoint.com/git"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "javatpoint.com Git page; mill catalog.",
    },
    {
        "id": "m07-tp-python",
        "urls": ["https://www.tutorialspoint.com/python/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "tutorialspoint.com: long-running tutorial mill / SEO catalog with "
            "house authorship rather than a named practitioner archive."
        ),
    },
    {
        "id": "m08-tp-linux",
        "urls": ["https://www.tutorialspoint.com/unix/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com Unix/Linux index; mill catalog.",
    },
    {
        "id": "m09-tp-git",
        "urls": ["https://www.tutorialspoint.com/git/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com Git index; mill catalog.",
    },
    {
        "id": "m10-gfg-python",
        "urls": ["https://www.geeksforgeeks.org/python-programming-language/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "geeksforgeeks.org: high-volume contributor mill (huge SEO catalog, "
            "thin per-article authorship relative to publication volume)."
        ),
    },
    {
        "id": "m11-gfg-linux",
        "urls": ["https://www.geeksforgeeks.org/linux-commands/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org Linux commands; mill catalog.",
    },
    {
        "id": "m12-gfg-git",
        "urls": ["https://www.geeksforgeeks.org/git-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org Git tutorial; mill catalog.",
    },
    {
        "id": "m13-sth-agile",
        "urls": ["https://www.softwaretestinghelp.com/agile-scrum-methodology/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "softwaretestinghelp.com: QA/tutorial mill with a large SEO catalog "
            "and house bylines."
        ),
    },
    {
        "id": "m14-sth-python",
        "urls": ["https://www.softwaretestinghelp.com/python-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "softwaretestinghelp.com Python tutorial; mill catalog.",
    },
    {
        "id": "m15-educba-python",
        "urls": ["https://www.educba.com/python-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "educba.com: commercial course/tutorial mill catalog.",
    },
    {
        "id": "m16-educba-git",
        "urls": ["https://www.educba.com/git-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "educba.com Git tutorial; mill catalog.",
    },
    {
        "id": "m17-simplilearn-python",
        "urls": ["https://www.simplilearn.com/tutorials/python-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": (
            "simplilearn.com tutorials: commercial SEO/lead-gen mill wrapping "
            "thin how-to pages around course funnels."
        ),
    },
    {
        "id": "m18-simplilearn-agile",
        "urls": ["https://www.simplilearn.com/tutorials/agile-scrum-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "simplilearn.com Agile tutorial hub; mill/lead-gen catalog.",
    },
    {
        "id": "m19-hackr-python",
        "urls": ["https://hackr.io/blog/python-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "hackr.io blog tutorials; affiliate/SEO mill pattern.",
    },
    {
        "id": "m20-hackr-git",
        "urls": ["https://hackr.io/blog/git-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "hackr.io Git tutorial; mill catalog.",
    },
    {
        "id": "m21-guru99-sql",
        "urls": ["https://www.guru99.com/sql.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com SQL hub; mill catalog.",
    },
    {
        "id": "m22-javatpoint-sql",
        "urls": ["https://www.javatpoint.com/sql-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "javatpoint.com SQL tutorial; mill catalog.",
    },
    {
        "id": "m23-tp-sql",
        "urls": ["https://www.tutorialspoint.com/sql/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com SQL index; mill catalog.",
    },
    {
        "id": "m24-gfg-sql",
        "urls": ["https://www.geeksforgeeks.org/sql-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org SQL tutorial; mill catalog.",
    },
    {
        "id": "m25-guru99-docker",
        "urls": ["https://www.guru99.com/docker-tutorial.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com Docker tutorial; mill catalog.",
    },
    {
        "id": "m26-javatpoint-docker",
        "urls": ["https://www.javatpoint.com/docker-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "javatpoint.com Docker tutorial; mill catalog.",
    },
    {
        "id": "m27-tp-docker",
        "urls": ["https://www.tutorialspoint.com/docker/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com Docker index; mill catalog.",
    },
    {
        "id": "m28-gfg-docker",
        "urls": ["https://www.geeksforgeeks.org/docker-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org Docker tutorial; mill catalog.",
    },
    {
        "id": "m29-sth-api",
        "urls": ["https://www.softwaretestinghelp.com/what-is-api-testing/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "softwaretestinghelp.com API testing; mill catalog.",
    },
    {
        "id": "m30-educba-linux",
        "urls": ["https://www.educba.com/linux-commands/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "educba.com Linux commands; mill catalog.",
    },
    {
        "id": "m31-simplilearn-git",
        "urls": ["https://www.simplilearn.com/tutorials/git-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "simplilearn.com Git tutorial hub; mill/lead-gen.",
    },
    {
        "id": "m32-guru99-k8s",
        "urls": ["https://www.guru99.com/kubernetes-tutorial.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com Kubernetes tutorial; mill catalog.",
    },
    {
        "id": "m33-javatpoint-k8s",
        "urls": ["https://www.javatpoint.com/kubernetes"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "javatpoint.com Kubernetes page; mill catalog.",
    },
    {
        "id": "m34-tp-k8s",
        "urls": ["https://www.tutorialspoint.com/kubernetes/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com Kubernetes index; mill catalog.",
    },
    {
        "id": "m35-gfg-k8s",
        "urls": ["https://www.geeksforgeeks.org/kubernetes-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org Kubernetes tutorial; mill catalog.",
    },
    {
        "id": "m36-guru99-java",
        "urls": ["https://www.guru99.com/java-tutorial.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com Java tutorial; mill catalog.",
    },
    {
        "id": "m37-tp-java",
        "urls": ["https://www.tutorialspoint.com/java/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com Java index; mill catalog.",
    },
    {
        "id": "m38-gfg-java",
        "urls": ["https://www.geeksforgeeks.org/java/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org Java hub; mill catalog.",
    },
    {
        "id": "m39-guru99-js",
        "urls": ["https://www.guru99.com/interactive-javascript-tutorials.html"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "guru99.com JavaScript tutorials; mill catalog.",
    },
    {
        "id": "m40-tp-js",
        "urls": ["https://www.tutorialspoint.com/javascript/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com JavaScript index; mill catalog.",
    },
    {
        "id": "m41-gfg-js",
        "urls": ["https://www.geeksforgeeks.org/javascript/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org JavaScript hub; mill catalog.",
    },
    {
        "id": "m42-sth-selenium",
        "urls": ["https://www.softwaretestinghelp.com/selenium-tutorial/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "softwaretestinghelp.com Selenium tutorial; mill catalog.",
    },
    {
        "id": "m43-simplilearn-js",
        "urls": ["https://www.simplilearn.com/tutorials/javascript-tutorial"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "simplilearn.com JavaScript tutorial hub; mill/lead-gen.",
    },
    {
        "id": "m44-tp-html",
        "urls": ["https://www.tutorialspoint.com/html/index.htm"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "tutorialspoint.com HTML index; mill catalog.",
    },
    {
        "id": "m45-gfg-html",
        "urls": ["https://www.geeksforgeeks.org/html/"],
        "label": "mill",
        "provenance_kind": "publication-pattern",
        "provenance_basis": "geeksforgeeks.org HTML hub; mill catalog.",
    },
]

HC3_ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=Hello-SimpleAI/HC3"
    "&config=all&split=train&offset={offset}&length={length}"
)
HC3_DATASET = "https://huggingface.co/datasets/Hello-SimpleAI/HC3"
HC3_PAPER = "https://arxiv.org/abs/2301.07597"
HC3_PROVENANCE_CHATGPT = (
    "HC3 collection label `chatgpt`: Guo et al. 2023 pulled these answers from "
    "the ChatGPT API. The label is a collection provenance, not a stylistic "
    "judgement by this unit's classifier."
)
HC3_PROVENANCE_HUMAN = (
    "HC3 collection label `human`: Guo et al. 2023 collected these answers from "
    "human sources (Stack Exchange / Reddit / Wikipedia / encyclopedia). Label "
    "is collection provenance, not this unit's style judgement."
)


def all_candidates() -> list[dict]:
    return list(PRACTITIONER) + list(MILL)
