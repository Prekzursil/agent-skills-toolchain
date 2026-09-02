# FIPS 180-4 SHA-256 test vector (empty message)

NIST FIPS 180-4 defines SHA-256. The empty-message digest is a published
self-test vector used by implementations as a known-answer test:

    SHA-256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

This is a cited external number. Equivalent measurement here is
`hashlib.sha256(b"").hexdigest()` on this interpreter, 11 times.
