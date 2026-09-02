"""Known-length third-party quotation used only as an extent plant.

The MIT permission grant is third-party expression (OSI/MIT license
text). Length is derived from this string's UTF-8 encoding. The extent
measurer must recover that length from the marked wrapper file without
reading PAYLOAD_BYTES.
"""

PAYLOAD = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software and associated documentation files (the \"Software\"), "
    "to deal in the Software without restriction, including without limitation "
    "the rights to use, copy, modify, merge, publish, distribute, sublicense, "
    "and/or sell copies of the Software, and to permit persons to whom the "
    "Software is furnished to do so, subject to the following conditions:"
)
PAYLOAD_BYTES = len(PAYLOAD.encode("utf-8"))
BEGIN_MARK = "BEGIN_ADV0143_THIRD_PARTY"
END_MARK = "END_ADV0143_THIRD_PARTY"
PLANT_REL = (
    "command-center/p2-wave/probes/ADV-0143/fixtures/third-party-license-plant.txt"
)
