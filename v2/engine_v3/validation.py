"""
LDT v3 — Input validation
──────────────────────────
SME-generic validation. No residential-specific wording.
"""

from __future__ import annotations
import pandas as pd
from .models import MitigationMode


REQUIRED_CSV_COLS = {
    "event_id", "annual_probability", "return_period",
    "hazard_intensity", "gross_loss_usd",
}


def validate_scenario_v3(asset: dict, df: pd.DataFrame,
                         policy: dict, intervention: dict) -> dict:
    """
    Validate a v3 analysis request.
    Returns {"valid": bool, "errors": [...], "warnings": [...]}.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── CSV structure ──────────────────────────────────────────────────
    missing = REQUIRED_CSV_COLS - set(df.columns)
    if missing:
        errors.append(f"CSV missing columns: {', '.join(sorted(missing))}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    if len(df) == 0:
        errors.append("CSV contains no event rows.")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ── Probabilities ──────────────────────────────────────────────────
    probs = df["annual_probability"]
    if (probs <= 0).any() or (probs > 1).any():
        errors.append("annual_probability must be > 0 and <= 1 for all events.")

    if probs.sum() > 1.0 + 1e-9:
        warnings.append(
            f"Sum of annual probabilities is {probs.sum():.4f}. "
            "This is valid for overlapping events but may indicate data issues."
        )

    # ── Losses ─────────────────────────────────────────────────────────
    if (df["gross_loss_usd"] < 0).any():
        errors.append("gross_loss_usd must be non-negative for all events.")

    asset_val = asset.get("asset_value_usd", 0)
    if asset_val > 0 and (df["gross_loss_usd"] > asset_val).any():
        warnings.append(
            "One or more event losses exceed the stated asset value. "
            "Losses will be capped if the asset-value cap is enabled."
        )

    # ── Asset fields ───────────────────────────────────────────────────
    if asset_val <= 0:
        warnings.append("Asset value is zero or missing. Loss capping is disabled.")

    roof_age = asset.get("roof_age_years")
    if roof_age is not None and roof_age < 0:
        errors.append("Roof age must be non-negative.")

    # ── Policy ─────────────────────────────────────────────────────────
    mode = policy.get("insured_share_mode", "full_policy_inputs")
    if mode == "full_policy_inputs":
        ded_type = policy.get("deductible_type", "flat_usd")
        if ded_type == "percent_of_coverage":
            pct = policy.get("deductible_pct", 0)
            if pct is not None and (pct < 0 or pct > 1):
                errors.append("Deductible percentage must be between 0 and 1.")
        else:
            ded = policy.get("deductible_usd", 0)
            if ded is not None and ded < 0:
                errors.append("Deductible must be non-negative.")
    elif mode == "simple_insured_share_assumption":
        share = policy.get("insured_share_pct")
        if share is not None and (share < 0 or share > 1):
            errors.append("Insured share percentage must be between 0 and 1.")

    # ── Reinsurance layers ─────────────────────────────────────────────
    layers = policy.get("reinsurance_layers")
    if layers:
        for i, l in enumerate(layers):
            if l.get("limit_usd", 0) <= 0:
                errors.append(f"Reinsurance layer {i+1}: limit must be > 0.")

    # ── Intervention ───────────────────────────────────────────────────
    base_red = intervention.get("base_loss_reduction_pct", 0)
    if base_red < 0 or base_red > 1:
        errors.append("Base loss reduction must be between 0% and 100%.")

    fail = intervention.get("failure_probability", 0)
    if fail < 0 or fail > 1:
        errors.append("Failure probability must be between 0% and 100%.")

    maint = intervention.get("maintenance_haircut_pct", 0)
    if maint < 0 or maint > 1:
        errors.append("Maintenance haircut must be between 0% and 100%.")

    # ── Curve-mode validation ──────────────────────────────────────────
    mit_mode = intervention.get("mitigation_mode", "uniform_scalar")
    if mit_mode == MitigationMode.hazard_intensity_curve:
        curve = intervention.get("curve_points")
        if not curve or len(curve) < 2:
            errors.append(
                "Hazard-intensity curve mode requires at least 2 curve points."
            )
        else:
            intensities = [p["hazard_intensity"] for p in curve]
            reductions = [p["reduction_pct"] for p in curve]

            # Check reductions in range
            for i, r in enumerate(reductions):
                if r < 0 or r > 1:
                    errors.append(
                        f"Curve point {i+1}: reduction_pct must be between 0 and 1."
                    )

            # Check for duplicate intensities
            if len(set(intensities)) < len(intensities):
                warnings.append(
                    "Duplicate hazard_intensity values in curve points. "
                    "First occurrence will be used."
                )

            # Check sortability
            sorted_intensities = sorted(intensities)
            if intensities != sorted_intensities:
                warnings.append(
                    "Curve points are not sorted by hazard_intensity. "
                    "They will be sorted automatically."
                )

    # ── Future asset layers ────────────────────────────────────────────
    future = asset.get("future_asset_layers")
    if future:
        if not isinstance(future, list):
            errors.append("future_asset_layers must be a list of strings.")
        else:
            for layer in future:
                if not isinstance(layer, str):
                    errors.append("Each future_asset_layer must be a string.")
                    break

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def apply_asset_value_cap(df: pd.DataFrame, asset_value_usd: float):
    """Cap gross losses at asset value. Returns (df, was_capped)."""
    df = df.copy()
    was_capped = (df["gross_loss_usd"] > asset_value_usd).any()
    if was_capped:
        df["gross_loss_usd"] = df["gross_loss_usd"].clip(upper=asset_value_usd)
    return df, bool(was_capped)
