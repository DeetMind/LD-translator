"""
Input validation for LDT v2 scenarios.

Checks structural correctness of inputs and produces warnings
(e.g., losses exceeding asset value) without blocking the run.
"""

from __future__ import annotations
from typing import Any
import pandas as pd


def validate_scenario(asset: dict, df: pd.DataFrame, policy: dict, intervention: dict) -> dict:
    """
    Validate a complete scenario.

    Returns:
        {
            "valid": bool,
            "errors": [str, ...],      # hard stops
            "warnings": [str, ...],    # informational
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Asset ────────────────────────────────────────────────────────────
    asset_value = asset.get("asset_value_usd", 0)
    if asset_value <= 0:
        errors.append("Asset value must be greater than zero.")

    hazard_share = asset.get("hazard_share_pct")
    if hazard_share is not None:
        if not (0 < hazard_share <= 1):
            errors.append("Hazard share must be between 0 and 1 (exclusive of 0).")

    # ── Event losses ─────────────────────────────────────────────────────
    required_cols = {"event_id", "annual_probability", "return_period",
                     "hazard_intensity", "gross_loss_usd"}
    missing = required_cols - set(df.columns)
    if missing:
        errors.append(f"Missing CSV columns: {', '.join(sorted(missing))}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    if len(df) < 1:
        errors.append("CSV must contain at least one event row.")
    elif len(df) < 3:
        warnings.append("Fewer than 3 event rows — results may not be meaningful.")

    if (df["annual_probability"] <= 0).any():
        errors.append("All annual_probability values must be > 0.")

    if (df["gross_loss_usd"] < 0).any():
        errors.append("gross_loss_usd values must be >= 0.")

    # Check for non-monotonic probabilities relative to return period
    if "return_period" in df.columns and len(df) >= 2:
        sorted_df = df.sort_values("return_period")
        if not sorted_df["annual_probability"].is_monotonic_decreasing:
            warnings.append(
                "Annual probabilities are not monotonically decreasing with "
                "increasing return period. Verify event table assumptions."
            )

    # Asset-value sanity check
    if asset_value > 0 and (df["gross_loss_usd"] > asset_value).any():
        n_exceed = int((df["gross_loss_usd"] > asset_value).sum())
        warnings.append(
            f"{n_exceed} event(s) have gross loss exceeding stated asset value "
            f"(${asset_value:,.0f}). Results may reflect assumptions beyond "
            f"dwelling replacement cost."
        )

    # ── Policy ───────────────────────────────────────────────────────────
    mode = policy.get("insured_share_mode", "full_policy_inputs")
    if mode == "simple_insured_share_assumption":
        share = policy.get("insured_share_pct")
        if share is None or not (0 <= share <= 1):
            errors.append("Insured share percentage must be between 0 and 1.")
    elif mode == "full_policy_inputs":
        if policy.get("deductible_type") == "flat_usd":
            if (policy.get("deductible_usd") or 0) < 0:
                errors.append("Deductible must be >= 0.")
        elif policy.get("deductible_type") == "percent_of_coverage":
            pct = policy.get("deductible_pct")
            if pct is None or not (0 <= pct <= 1):
                errors.append("Deductible percentage must be between 0 and 1.")

    # ── Intervention ─────────────────────────────────────────────────────
    base_red = intervention.get("base_loss_reduction_pct", 0)
    if not (0 <= base_red <= 1):
        errors.append("Base loss reduction must be between 0 and 1.")

    fail_prob = intervention.get("failure_probability", 0)
    if not (0 <= fail_prob <= 1):
        errors.append("Failure probability must be between 0 and 1.")

    maint = intervention.get("maintenance_haircut_pct", 0)
    if not (0 <= maint <= 1):
        errors.append("Maintenance haircut must be between 0 and 1.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def apply_asset_value_cap(df: pd.DataFrame, asset_value_usd: float) -> tuple[pd.DataFrame, bool]:
    """
    Cap gross_loss_usd at asset_value_usd.

    Returns:
        (capped_df, was_capped) — was_capped is True if any values were reduced.
    """
    df = df.copy()
    mask = df["gross_loss_usd"] > asset_value_usd
    was_capped = bool(mask.any())
    if was_capped:
        df.loc[mask, "gross_loss_usd"] = asset_value_usd
    return df, was_capped
