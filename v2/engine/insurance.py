"""
Insurance / policy-layer logic for LDT v2.

Maps gross event losses to insured and uninsured losses based on
the user's policy assumptions.

─── Supported modes (this demo) ───────────────────────────────────────
1. full_policy_inputs
     insured = min(max(gross - applicable_deductible, 0), coverage_limit)

2. simple_insured_share_assumption
     insured = min(gross * insured_share_pct, coverage_limit)

In both modes:
     uninsured = gross - insured

─── Coinsurance note ──────────────────────────────────────────────────
coinsurance_pct is captured in the policy object but does NOT alter
calculations in this first demo build.  The field is structured so
coinsurance can be activated later without reworking the UI.
────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def resolve_deductible(policy: dict) -> float:
    """
    Compute the applicable deductible in dollars.

    If deductible_type == 'percent_of_coverage':
        applicable = coverage_limit_usd * deductible_pct
    Else:
        applicable = deductible_usd
    """
    if policy.get("deductible_type") == "percent_of_coverage":
        coverage = policy.get("coverage_limit_usd") or 0.0
        pct = policy.get("deductible_pct") or 0.0
        return coverage * pct
    return policy.get("deductible_usd") or 0.0


def map_to_insured_losses(df: pd.DataFrame, policy: dict) -> pd.DataFrame:
    """
    Add insured and uninsured loss columns to the event table.

    Operates on both 'gross_loss_usd' (baseline) and 'adjusted_gross_loss_usd'
    (post-mitigation) to produce:
        baseline_insured_loss_usd
        baseline_uninsured_loss_usd
        adjusted_insured_loss_usd
        adjusted_uninsured_loss_usd
        avoided_insured_loss_usd
        avoided_uninsured_loss_usd
    """
    df = df.copy()
    mode = policy.get("insured_share_mode", "full_policy_inputs")
    coverage_limit = policy.get("coverage_limit_usd") or float("inf")

    if mode == "simple_insured_share_assumption":
        share = policy.get("insured_share_pct", 1.0)
        df["baseline_insured_loss_usd"] = np.minimum(
            df["gross_loss_usd"] * share, coverage_limit
        )
        df["adjusted_insured_loss_usd"] = np.minimum(
            df["adjusted_gross_loss_usd"] * share, coverage_limit
        )
    else:
        # full_policy_inputs
        deductible = resolve_deductible(policy)
        df["baseline_insured_loss_usd"] = np.minimum(
            np.maximum(df["gross_loss_usd"] - deductible, 0.0), coverage_limit
        )
        df["adjusted_insured_loss_usd"] = np.minimum(
            np.maximum(df["adjusted_gross_loss_usd"] - deductible, 0.0), coverage_limit
        )

    df["baseline_uninsured_loss_usd"] = df["gross_loss_usd"] - df["baseline_insured_loss_usd"]
    df["adjusted_uninsured_loss_usd"] = df["adjusted_gross_loss_usd"] - df["adjusted_insured_loss_usd"]
    df["avoided_insured_loss_usd"] = df["baseline_insured_loss_usd"] - df["adjusted_insured_loss_usd"]
    df["avoided_uninsured_loss_usd"] = df["baseline_uninsured_loss_usd"] - df["adjusted_uninsured_loss_usd"]

    return df
