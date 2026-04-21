"""
LDT v3 — Insurance / policy-layer logic
────────────────────────────────────────
Reused from v2 with identical calculation logic.
Structured for future per-asset insurance treatment.

Supported modes:
1. full_policy_inputs  — insured = min(max(gross - deductible, 0), limit)
2. simple_insured_share — insured = min(gross * share, limit)

Coinsurance captured but not active in Phase 1.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def resolve_deductible(policy: dict) -> float:
    """Compute applicable deductible in dollars."""
    if policy.get("deductible_type") == "percent_of_coverage":
        coverage = policy.get("coverage_limit_usd") or 0.0
        pct = policy.get("deductible_pct") or 0.0
        return coverage * pct
    return policy.get("deductible_usd") or 0.0


def map_to_insured_losses(df: pd.DataFrame, policy: dict) -> pd.DataFrame:
    """
    Add insured/uninsured loss columns for both baseline and mitigated.

    Produces:
        baseline_insured_loss_usd, baseline_uninsured_loss_usd
        adjusted_insured_loss_usd, adjusted_uninsured_loss_usd
        avoided_insured_loss_usd, avoided_uninsured_loss_usd
    """
    df = df.copy()
    mode = policy.get("insured_share_mode", "full_policy_inputs")
    coverage_limit = policy.get("coverage_limit_usd") or float("inf")

    if mode == "simple_insured_share_assumption":
        share = policy.get("insured_share_pct", 1.0)
        df["baseline_insured_loss_usd"] = np.minimum(
            df["gross_loss_usd"] * share, coverage_limit)
        df["adjusted_insured_loss_usd"] = np.minimum(
            df["adjusted_gross_loss_usd"] * share, coverage_limit)
    else:
        deductible = resolve_deductible(policy)
        df["baseline_insured_loss_usd"] = np.minimum(
            np.maximum(df["gross_loss_usd"] - deductible, 0.0), coverage_limit)
        df["adjusted_insured_loss_usd"] = np.minimum(
            np.maximum(df["adjusted_gross_loss_usd"] - deductible, 0.0),
            coverage_limit)

    df["baseline_uninsured_loss_usd"] = (
        df["gross_loss_usd"] - df["baseline_insured_loss_usd"])
    df["adjusted_uninsured_loss_usd"] = (
        df["adjusted_gross_loss_usd"] - df["adjusted_insured_loss_usd"])
    df["avoided_insured_loss_usd"] = (
        df["baseline_insured_loss_usd"] - df["adjusted_insured_loss_usd"])
    df["avoided_uninsured_loss_usd"] = (
        df["baseline_uninsured_loss_usd"] - df["adjusted_uninsured_loss_usd"])

    return df
