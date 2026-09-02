"""Post-fix ceremony subject: oracles match the expected values in corpus.py."""


def semver_bump(diff):
    if diff.get("deleted_required_key"):
        return "MAJOR"
    return "NONE"


def inverse_ok(action):
    if action.get("inverse"):
        return True
    return bool(action.get("irreversible"))


def packet_question_count_ok(questions):
    return len(questions) == 1


def hook_observed(listing_ok, hook_fired):
    return bool(hook_fired)


def migration_apply_count(n):
    return int(n)


def restore_behaviour_match(restored, expected):
    return restored == expected


def orphan_count(leftovers):
    return len(leftovers)


def hostile_walk_ok(names):
    return all('"' not in n and "'" not in n for n in names)


def archive_allowlist_ok(archive_entries, fs_listing, allow):
    return set(archive_entries).issubset(set(allow))


def secret_canary_found(blob, canary):
    return canary in blob


def sbom_matches_closure(sbom, closure):
    return set(sbom) == set(closure)


def tamper_ok(signed, unsigned_declared):
    return bool(signed) or bool(unsigned_declared)


def rider_blocks(licences):
    return any("rider" in str(x).lower() for x in licences)


def advisory_scan_pass(status):
    return status == "CLEAN"


def matrix_cell_pass(status):
    return status == "RUN"


def notes_grounded(sentences, claim_ids):
    return all(any(cid in s for cid in claim_ids) for s in sentences)


def source_unique_preserved(before_hash, after_hash):
    return before_hash == after_hash


def gate_go(verdicts):
    return all(v == "TRUE" for v in verdicts)


def threshold_publishable(sample_n, min_n, rate):
    return int(sample_n) >= int(min_n)


def cache_refresh_clears_poison(before, after):
    return before != after


def three_way_parity(git_blob, packaged, deployed):
    return git_blob == packaged == deployed


def rollback_coverage_ok(instrumented, manifest_claims):
    return bool(instrumented)


def resolve_ok(status, already_installed):
    return status not in {"revoked", "deprecated-blocked"}
