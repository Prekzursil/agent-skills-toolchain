"""Reviewer vs implementer makespan at 1x and 10x, with and without sampling."""
from __future__ import annotations

from typing import Any


def hours(seconds: float) -> float:
    return seconds / 3600.0


def implementer_hours(
    serial_sum_s: float, parallel_sum_s: float, k: float, scale: int
) -> float:
    """Budget-based implementer makespan: serial floor + parallel/K, scaled."""
    if k <= 0:
        raise ValueError("k must be positive")
    return hours(scale * (serial_sum_s + parallel_sum_s / k))


def reviewer_census_hours(slots: int, t_review_s: float, pool: int, scale: int) -> float:
    if pool <= 0:
        raise ValueError("pool must be positive")
    return hours(scale * slots * t_review_s / pool)


def reviewer_sample_hours(
    sample_slots: float, t_review_s: float, pool: int
) -> float:
    """Sample size is capped per stratum and does not grow with scale."""
    if pool <= 0:
        raise ValueError("pool must be positive")
    return hours(sample_slots * t_review_s / pool)


def break_even_t_review_s(
    impl_hours_val: float, slots_scaled: int, pool: int
) -> float:
    """t_review where serial reviewer census equals implementer makespan."""
    if slots_scaled <= 0:
        return float("inf")
    return impl_hours_val * 3600.0 * pool / slots_scaled


def sample_slots_expected(
    n_strata: int, n_per_stratum: int, slots_1x: int, n_units: int
) -> float:
    """n_per_stratum * n_strata, inflated by two-reviewer fraction."""
    units_sampled = n_strata * n_per_stratum
    frac_slots = slots_1x / n_units if n_units else 1.0
    return units_sampled * frac_slots


def table(
    census: dict[str, Any],
    n_per_stratum: int,
    t_review_s: float,
    t_review_label: str,
    pool: int,
    scale: int,
    k_values: tuple[int, ...] = (1, 4, 10, 32),
) -> dict[str, Any]:
    serial = float(census["implementer_budget"]["local_serialized_sum_s"])
    parallel = float(census["implementer_budget"]["parallelizable_sum_s"])
    slots = int(census["reviewer_requirement"]["reviewer_slots_1x"])
    n_units = int(census["n_work_units"])
    n_strata = int(census["n_prefix_strata"])
    samp_slots = sample_slots_expected(n_strata, n_per_stratum, slots, n_units)
    rows = []
    for k in k_values:
        impl = implementer_hours(serial, parallel, k, scale)
        rev_c = reviewer_census_hours(slots, t_review_s, pool, scale)
        rev_s = reviewer_sample_hours(samp_slots, t_review_s, pool)
        be = break_even_t_review_s(impl, slots * scale, pool)
        rows.append(
            {
                "implementer_concurrency_K": k,
                "implementer_h": round(impl, 2),
                "reviewer_census_h": round(rev_c, 2),
                "reviewer_sample_h": round(rev_s, 2),
                "reviewer_is_critical_path_census": rev_c > impl,
                "reviewer_is_critical_path_sample": rev_s > impl,
                "break_even_t_review_s": round(be, 1),
                "sampling_reduction_factor": (rev_c / rev_s) if rev_s else None,
            }
        )
    unlimited_impl = implementer_hours(serial, parallel, 1e12, scale)
    return {
        "scale": scale,
        "t_review_s": t_review_s,
        "t_review_label": t_review_label,
        "reviewer_pool": pool,
        "n_per_stratum": n_per_stratum,
        "n_prefix_strata": n_strata,
        "census_slots": slots * scale,
        "sample_slots_expected": round(samp_slots, 2),
        "implementer_unlimited_K_h": round(unlimited_impl, 2),
        "rows": rows,
    }
