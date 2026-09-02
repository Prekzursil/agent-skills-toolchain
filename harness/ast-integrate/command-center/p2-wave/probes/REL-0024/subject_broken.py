"""Pre-fix ceremony subject: each oracle returns the wrong value."""


def semver_bump(diff):
    if diff.get("deleted_required_key"):
        return "PATCH"
    return "NONE"


def inverse_ok(action):
    return True


def packet_question_count_ok(questions):
    return True


def hook_observed(listing_ok, hook_fired):
    return bool(listing_ok)


def migration_apply_count(n):
    return int(n) * 2


def restore_behaviour_match(restored, expected):
    return restored is not None


def orphan_count(leftovers):
    return 0


def hostile_walk_ok(names):
    return True


def archive_allowlist_ok(archive_entries, fs_listing, allow):
    return set(fs_listing).issubset(set(allow))


def secret_canary_found(blob, canary):
    return False


def sbom_matches_closure(sbom, closure):
    return True


def tamper_ok(signed, unsigned_declared):
    return True


def rider_blocks(licences):
    return False


def advisory_scan_pass(status):
    return True


def matrix_cell_pass(status):
    return True


def notes_grounded(sentences, claim_ids):
    return True


def source_unique_preserved(before_hash, after_hash):
    return True


def gate_go(verdicts):
    return True


def threshold_publishable(sample_n, min_n, rate):
    return True


def cache_refresh_clears_poison(before, after):
    return True


def three_way_parity(git_blob, packaged, deployed):
    return git_blob == packaged


def rollback_coverage_ok(instrumented, manifest_claims):
    return bool(manifest_claims)


def resolve_ok(status, already_installed):
    return True
