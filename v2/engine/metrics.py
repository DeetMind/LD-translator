"""
Summary metrics and EP curve computation for LDT v2.

Computes:
  - Expected Annual Loss (EAL) for gross, insured, and uninsured layers
  - Exceedance Probability (EP) curves
  - Hazard-specific and total-risk reduction percentages
"""

from __future__ import annotations
import pandas as pd
import numpy as np


# ── EAL ──────────────────────────────────────────────────────────────────

def compute_eal(prob: pd.Series, loss: pd.Series) -> float:
    """Expected Annual Loss = sum(annual_probability * loss)."""
    return float((prob * loss).sum())


# ── EP curves ────────────────────────────────────────────────────────────

def compute_ep_curve(prob: pd.Series, loss: pd.Series) -> dict:
    """
    Exceedance Probability curve.

    Sort events by loss descending; cumulative sum of annual_probability
    gives the exceedance probability at each loss level.

    Returns {"loss_usd": [...], "exceedance_probability": [...]}.
    """
    order = loss.argsort()[::-1]
    sorted_loss = loss.iloc[order].values
    sorted_prob = prob.iloc[order].values
    ep = np.cumsum(sorted_prob)
    return {
        "loss_usd": sorted_loss.tolist(),
        "exceedance_probability": ep.tolist(),
    }


# ── Summary metrics ─────────────────────────────────────────────────────

def compute_summary_metrics(df: pd.DataFrame, asset: dict) -> dict:
    """
    Compute all summary metrics from an enriched event table
    (output of insurance.map_to_insured_losses).

    Returns a SummaryMetrics-style dict.
    """
    prob = df["annual_probability"]

    # Gross
    baseline_gross_eal = compute_eal(prob, df["gross_loss_usd"])
    adjusted_gross_eal = compute_eal(prob, df["adjusted_gross_loss_usd"])
    avoided_gross_eal = baseline_gross_eal - adjusted_gross_eal

    # Insured
    baseline_insured_eal = compute_eal(prob, df["baseline_insured_loss_usd"])
    adjusted_insured_eal = compute_eal(prob, df["adjusted_insured_loss_usd"])
    avoided_insured_eal = baseline_insured_eal - adjusted_insured_eal

    # Uninsured
    baseline_uninsured_eal = compute_eal(prob, df["baseline_uninsured_loss_usd"])
    adjusted_uninsured_eal = compute_eal(prob, df["adjusted_uninsured_loss_usd"])
    avoided_uninsured_eal = baseline_uninsured_eal - adjusted_uninsured_eal

    # Hazard-specific reduction %
    hazard_reduction_pct = (
        (avoided_gross_eal / baseline_gross_eal * 100) if baseline_gross_eal > 0 else 0.0
    )

    # Insured reduction %
    insured_reduction_pct = (
        (avoided_insured_eal / baseline_insured_eal * 100) if baseline_insured_eal > 0 else 0.0
    )

    # Total-risk reduction (only if hazard_share_pct provided)
    hazard_share = asset.get("hazard_share_pct")
    total_risk_reduction_pct = None
    if hazard_share and hazard_share > 0:
        # avoided_gross / (baseline_gross / hazard_share) * 100
        total_risk_eal_proxy = baseline_gross_eal / hazard_share
        total_risk_reduction_pct = (
            avoided_gross_eal / total_risk_eal_proxy * 100
            if total_risk_eal_proxy > 0 else 0.0
        )

    # EP curves — gross
    baseline_gross_ep = compute_ep_curve(prob, df["gross_loss_usd"])
    adjusted_gross_ep = compute_ep_curve(prob, df["adjusted_gross_loss_usd"])

    # EP curves — insured
    baseline_insured_ep = compute_ep_curve(prob, df["baseline_insured_loss_usd"])
    adjusted_insured_ep = compute_ep_curve(prob, df["adjusted_insured_loss_usd"])

    # Policy relevance: where does avoided loss sit?
    avoided_inside_insured_pct = (
        (avoided_insured_eal / avoided_gross_eal * 100) if avoided_gross_eal > 0 else 0.0
    )

    return {
        "baseline_gross_eal_usd": round(baseline_gross_eal, 2),
        "adjusted_gross_eal_usd": round(adjusted_gross_eal, 2),
        "avoided_gross_eal_usd": round(avoided_gross_eal, 2),
        "baseline_insured_eal_usd": round(baseline_insured_eal, 2),
        "adjusted_insured_eal_usd": round(adjusted_insured_eal, 2),
        "avoided_insured_eal_usd": round(avoided_insured_eal, 2),
        "baseline_uninsured_eal_usd": round(baseline_uninsured_eal, 2),
        "adjusted_uninsured_eal_usd": round(adjusted_uninsured_eal, 2),
        "avoided_uninsured_eal_usd": round(avoided_uninsured_eal, 2),
        "hazard_specific_reduction_pct": round(hazard_reduction_pct, 1),
        "insured_reduction_pct": round(insured_reduction_pct, 1),
        "total_risk_reduction_pct": (
            round(total_risk_reduction_pct, 1) if total_risk_reduction_pct is not None else None
        ),
        "avoided_inside_insured_pct": round(avoided_inside_insured_pct, 1),
        "ep_curves": {
            "gross_baseline": baseline_gross_ep,
            "gross_adjusted": adjusted_gross_ep,
            "insured_baseline": baseline_insured_ep,
            "insured_adjusted": adjusted_insured_ep,
        },
    }
