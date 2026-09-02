"""Labelled 20-licence control set for IMP-0156.

Each row is an expected SPDX id plus the files a candidate tree would carry.
Labels live here; identification lives in tools/workflow_foundry/license_extract.py.
The probe fails unless extract_licence hits expected on 20/20.
"""
from __future__ import annotations

from typing import Any

CONTROL: list[dict[str, Any]] = [
    {
        "id": "c01-mit",
        "expected": "MIT",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "MIT License\n\n"
                "Copyright (c) 2024 IMP-0156 control\n\n"
                "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
                'of this software and associated documentation files (the "Software"), to deal\n'
                "in the Software without restriction, including without limitation the rights\n"
                "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
                "copies of the Software, and to permit persons to whom the Software is\n"
                "furnished to do so, subject to the following conditions:\n\n"
                "The above copyright notice and this permission notice shall be included in all\n"
                "copies or substantial portions of the Software.\n\n"
                'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
                "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
                "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
                "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
                "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
                "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
                "SOFTWARE.\n"
            )
        },
    },
    {
        "id": "c02-apache-2.0",
        "expected": "Apache-2.0",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Apache License\n"
                "Version 2.0, January 2004\n"
                "http://www.apache.org/licenses/\n\n"
                "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n"
                "1. Definitions.\n"
            )
        },
    },
    {
        "id": "c03-bsd-2-clause",
        "expected": "BSD-2-Clause",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Copyright (c) 2024 IMP-0156 control\n\n"
                "Redistribution and use in source and binary forms, with or without\n"
                "modification, are permitted provided that the following conditions are met:\n\n"
                "1. Redistributions of source code must retain the above copyright notice, this\n"
                "   list of conditions and the following disclaimer.\n\n"
                "2. Redistributions in binary form must reproduce the above copyright notice,\n"
                "   this list of conditions and the following disclaimer in the documentation\n"
                "   and/or other materials provided with the distribution.\n\n"
                'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"\n'
                "AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n"
                "IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE\n"
                "DISCLAIMED.\n"
            )
        },
    },
    {
        "id": "c04-bsd-3-clause",
        "expected": "BSD-3-Clause",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Copyright (c) 2024 IMP-0156 control\n\n"
                "Redistribution and use in source and binary forms, with or without\n"
                "modification, are permitted provided that the following conditions are met:\n\n"
                "1. Redistributions of source code must retain the above copyright notice, this\n"
                "   list of conditions and the following disclaimer.\n\n"
                "2. Redistributions in binary form must reproduce the above copyright notice,\n"
                "   this list of conditions and the following disclaimer in the documentation\n"
                "   and/or other materials provided with the distribution.\n\n"
                "3. Neither the name of the copyright holder nor the names of its\n"
                "   contributors may be used to endorse or promote products derived from\n"
                "   this software without specific prior written permission.\n\n"
                'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"\n'
            )
        },
    },
    {
        "id": "c05-gpl-2.0-only",
        "expected": "GPL-2.0-only",
        "method": "spdx-header",
        "files": {
            "src/mod.c": (
                "/* SPDX-License-Identifier: GPL-2.0-only */\n"
                "int workflow_step(void) { return 0; }\n"
            )
        },
    },
    {
        "id": "c06-gpl-2.0-or-later",
        "expected": "GPL-2.0-or-later",
        "method": "spdx-header",
        "files": {
            "src/mod.c": (
                "/* SPDX-License-Identifier: GPL-2.0-or-later */\n"
                "int workflow_step(void) { return 1; }\n"
            )
        },
    },
    {
        "id": "c07-gpl-3.0-only",
        "expected": "GPL-3.0-only",
        "method": "license-file",
        "files": {
            "COPYING": (
                "GNU GENERAL PUBLIC LICENSE\n"
                "Version 3, 29 June 2007\n\n"
                "Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n"
                "Everyone is permitted to copy and distribute verbatim copies\n"
                "of this license document, but changing it is not allowed.\n"
            )
        },
    },
    {
        "id": "c08-lgpl-2.1-only",
        "expected": "LGPL-2.1-only",
        "method": "spdx-header",
        "files": {
            "lib/compat.py": "# SPDX-License-Identifier: LGPL-2.1-only\n\ndef ping():\n    return True\n"
        },
    },
    {
        "id": "c09-lgpl-3.0-only",
        "expected": "LGPL-3.0-only",
        "method": "spdx-header",
        "files": {
            "lib/compat.py": "# SPDX-License-Identifier: LGPL-3.0-only\n\ndef ping():\n    return True\n"
        },
    },
    {
        "id": "c10-agpl-3.0-only",
        "expected": "AGPL-3.0-only",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "GNU AFFERO GENERAL PUBLIC LICENSE\n"
                "Version 3, 19 November 2007\n\n"
                "Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n"
            )
        },
    },
    {
        "id": "c11-mpl-2.0",
        "expected": "MPL-2.0",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Mozilla Public License Version 2.0\n"
                "==================================\n\n"
                "1. Definitions\n"
                "--------------\n"
            )
        },
    },
    {
        "id": "c12-isc",
        "expected": "ISC",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Copyright (c) 2024 IMP-0156 control\n\n"
                "Permission to use, copy, modify, and/or distribute this software for any\n"
                "purpose with or without fee is hereby granted, provided that the above\n"
                "copyright notice and this permission notice appear in all copies.\n\n"
                'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES\n'
                "WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF\n"
                "MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR\n"
                "ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES\n"
                "WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN\n"
                "ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF\n"
                "OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.\n"
            )
        },
    },
    {
        "id": "c13-unlicense",
        "expected": "Unlicense",
        "method": "license-file",
        "files": {
            "UNLICENSE": (
                "This is free and unencumbered software released into the public domain.\n\n"
                "Anyone is free to copy, modify, publish, use, compile, sell, or\n"
                "distribute this software, either in source code form or as a compiled\n"
                "binary, for any purpose, commercial or non-commercial, and by any\n"
                "means.\n\n"
                'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,\n'
                "EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF\n"
                "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n"
            )
        },
    },
    {
        "id": "c14-cc0-1.0",
        "expected": "CC0-1.0",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "CC0 1.0 Universal\n\n"
                "Statement of Purpose\n\n"
                "The laws of most jurisdictions throughout the world automatically confer\n"
                "exclusive Copyright and Related Rights upon the creator and subsequent\n"
                "owner(s) of an original work of authorship and/or a database.\n"
            )
        },
    },
    {
        "id": "c15-epl-2.0",
        "expected": "EPL-2.0",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Eclipse Public License - v 2.0\n\n"
                "THE ACCOMPANYING PROGRAM IS PROVIDED UNDER THE TERMS OF THIS ECLIPSE\n"
                'PUBLIC LICENSE ("AGREEMENT"). ANY USE, REPRODUCTION OR DISTRIBUTION\n'
                "OF THE PROGRAM CONSTITUTES RECIPIENT'S ACCEPTANCE OF THIS AGREEMENT.\n"
            )
        },
    },
    {
        "id": "c16-bsl-1.0",
        "expected": "BSL-1.0",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Boost Software License - Version 1.0 - August 17th, 2003\n\n"
                "Permission is hereby granted, free of charge, to any person or organization\n"
                "obtaining a copy of the software and accompanying documentation covered by\n"
                'this license (the "Software") to use, reproduce, display, distribute,\n'
                "execute, and transmit the Software.\n"
            )
        },
    },
    {
        "id": "c17-0bsd",
        "expected": "0BSD",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Zero-Clause BSD\n\n"
                "Permission to use, copy, modify, and/or distribute this software for any\n"
                "purpose with or without fee is hereby granted.\n\n"
                'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES\n'
                "WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF\n"
                "MERCHANTABILITY AND FITNESS.\n"
            )
        },
    },
    {
        "id": "c18-zlib",
        "expected": "Zlib",
        "method": "license-file",
        "files": {
            "LICENSE": (
                "Copyright (c) 2024 IMP-0156 control\n\n"
                "This software is provided 'as-is', without any express or implied\n"
                "warranty. In no event will the authors be held liable for any damages\n"
                "arising from the use of this software.\n\n"
                "Permission is granted to anyone to use this software for any purpose,\n"
                "including commercial applications, and to alter it and redistribute it\n"
                "freely, subject to the following restrictions:\n\n"
                "1. The origin of this software must not be misrepresented; you must not\n"
                "   claim that you wrote the original software.\n"
            )
        },
    },
    {
        "id": "c19-artistic-2.0",
        "expected": "Artistic-2.0",
        "method": "package-metadata",
        "files": {
            "package.json": (
                "{\n"
                '  "name": "imp-0156-artistic-control",\n'
                '  "version": "1.0.0",\n'
                '  "license": "Artistic-2.0"\n'
                "}\n"
            )
        },
    },
    {
        "id": "c20-cddl-1.0",
        "expected": "CDDL-1.0",
        "method": "spdx-header",
        "files": {
            "src/gate.java": (
                "/* SPDX-License-Identifier: CDDL-1.0 */\n"
                "class Gate { int allow() { return 1; } }\n"
            )
        },
    },
]


def silent_default_traps() -> list[dict[str, Any]]:
    """Fixtures that must stay UNKNOWN — never MIT/Apache/BSD by default."""
    return [
        {
            "id": "trap-empty",
            "expected": "UNKNOWN",
            "files": {"README.md": "# a candidate with no licence files\n"},
        },
        {
            "id": "trap-permissive-word",
            "expected": "UNKNOWN",
            "files": {
                "package.json": (
                    "{\n"
                    '  "name": "sounds-open",\n'
                    '  "license": "permissive"\n'
                    "}\n"
                )
            },
        },
        {
            "id": "trap-bare-bsd",
            "expected": "UNKNOWN",
            "files": {
                "package.json": (
                    "{\n"
                    '  "name": "ambiguous-bsd",\n'
                    '  "license": "BSD"\n'
                    "}\n"
                )
            },
        },
        {
            "id": "trap-unrecognised-blob",
            "expected": "UNKNOWN",
            "files": {
                "LICENSE": "All rights reserved. Contact sales@example.invalid.\n",
                "package.json": (
                    "{\n"
                    '  "name": "rider-trap",\n'
                    '  "license": "MIT"\n'
                    "}\n"
                ),
            },
        },
    ]
