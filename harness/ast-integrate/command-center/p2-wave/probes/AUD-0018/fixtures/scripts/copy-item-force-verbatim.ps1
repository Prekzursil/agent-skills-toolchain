param($SrcFile, $DestFile)
# AUD-0018 planted control. Lines 2-66 pad so Copy-Item -Force sits at line 67,
# matching the catalog's measured fact shape for scripts/sync-rules.ps1:67.
# This script copies verbatim. It does not transform. It has no nested-repo,
# vendored-tree, or repo-owned-file guards. Direction is parameterized.
# planted-pad 06
# planted-pad 07
# planted-pad 08
# planted-pad 09
# planted-pad 10
# planted-pad 11
# planted-pad 12
# planted-pad 13
# planted-pad 14
# planted-pad 15
# planted-pad 16
# planted-pad 17
# planted-pad 18
# planted-pad 19
# planted-pad 20
# planted-pad 21
# planted-pad 22
# planted-pad 23
# planted-pad 24
# planted-pad 25
# planted-pad 26
# planted-pad 27
# planted-pad 28
# planted-pad 29
# planted-pad 30
# planted-pad 31
# planted-pad 32
# planted-pad 33
# planted-pad 34
# planted-pad 35
# planted-pad 36
# planted-pad 37
# planted-pad 38
# planted-pad 39
# planted-pad 40
# planted-pad 41
# planted-pad 42
# planted-pad 43
# planted-pad 44
# planted-pad 45
# planted-pad 46
# planted-pad 47
# planted-pad 48
# planted-pad 49
# planted-pad 50
# planted-pad 51
# planted-pad 52
# planted-pad 53
# planted-pad 54
# planted-pad 55
# planted-pad 56
# planted-pad 57
# planted-pad 58
# planted-pad 59
# planted-pad 60
# planted-pad 61
# planted-pad 62
# planted-pad 63
# planted-pad 64
# planted-pad 65
# planted-pad 66
Copy-Item -Path $SrcFile -Destination $DestFile -Force
