"""
LDT v3 — Summary metrics and EP curves
───────────────────────────────────────
Same calculations as v2, plus reinsurance layer metrics.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def compute_eal(prob: pd.Series, loss: pd.Series) -> float:
    """Expected Annual Loss = sum(annual_probability * loss)."""
    return float((prob * loss).sum())


def compute_ep_curve(prob: pd.Series, loss: pd.Series) -> dict:
    """EP curve: sort by loss desc, cumulative prob = exceedance probability."""
    order = loss.argsort()[::-1]
    sorted_loss = loss.iloc[order].values
    sorted_prob = prob.iloc[order].values
    ep = np.cumsum(sorted_prob)
    return {
        "loss_usd": sorted_loss.tolist(),
        "exceedance_probability": ep.tolist(),
    }


def compute_summary_metrics(df: pd.DataFrame, asset: dict) -> dict:
    """Full summary metrics from enriched event table."""
    prob = df["annual_probability"]

    # Gross
    bl_gross = compute_eal(prob, df["gross_loss_usd"])
    adj_gross = compute_eal(prob, df["adjusted_gross_loss_usd"])
    avoid_gross = bl_gross - adj_gross

    # Insured
    bl_ins = compute_eal(prob, df["baseline_insured_loss_usd"])
    adj_ins = compute_eal(prob, df["adjusted_insured_loss_usd"])
    avoid_ins = bl_ins - adj_ins

    # Uninsured
    bl_unins = compute_eal(prob, df["baseline_uninsured_loss_usd"])
    adj_unins = compute_eal(prob, df["adjusted_uninsured_loss_usd"])
    avoid_unins = bl_unins - adj_unins

    # Reduction percentages
    haz_red = (avoid_gross / bl_gross * 100) if bl_gross > 0 else 0.0
    ins_red = (avoid_ins / bl_ins * 100) if bl_ins > 0 else 0.0

    # Total-risk reduction
    haz_share = asset.get("hazard_share_pct")
    total_red = None
    if haz_share and haz_share > 0:
        total_eal = bl_gross / haz_share
        total_red = (avoid_gross / total_eal * 100) if total_eal > 0 else 0.0

    # EP curves
    bl_gross_ep = compute_ep_curve(prob, df["gross_loss_usd"])
    adj_gross_ep = compute_ep_curve(prob, df["adjusted_gross_loss_usd"])
    bl_ins_ep = compute_ep_curve(prob, df["baseline_insured_loss_usd"])
    adj_ins_ep = compute_ep_curve(prob, df["adjusted_insured_loss_usd"])

    # Policy relevance
    inside_pct = (avoid_ins / avoid_gross * 100) if avoid_gross > 0 else 0.0

    return {
        "baseline_gross_eal_usd": round(bl_gross, 2),
        "adjusted_gross_eal_usd": round(adj_gross, 2),
        "avoided_gross_eal_usd": round(avoid_gross, 2),
        "baseline_insured_eal_usd": round(bl_ins, 2),
        "adjusted_insured_eal_usd": round(adj_ins, 2),
        "avoided_insured_eal_usd": round(avoid_ins, 2),
        "baseline_uninsured_eal_usd": round(bl_unins, 2),
        "adjusted_uninsured_eal_usd": round(adj_unins, 2),
        "avoided_uninsured_eal_usd": round(avoid_unins, 2),
        "hazard_specific_reduction_pct": round(haz_red, 1),
        "insured_reduction_pct": round(ins_red, 1),
        "total_risk_reduction_pct": (
            round(total_red, 1) if total_red is not None else None),
        "avoided_inside_insured_pct": round(inside_pct, 1),
        "ep_curves": {
            "gross_baseline": bl_gross_ep,
            "gross_adjusted": adj_gross_ep,
            "insured_baseline": bl_ins_ep,
            "insured_adjusted": adj_ins_ep,
        },
    }


def compute_reinsurance_layer_metrics(
    prob: pd.Series, baseline_loss: pd.Series,
    adjusted_loss: pd.Series, layers: list[dict],
) -> list[dict]:
    """Compute ELL, LOL%, and reduction per reinsurance layer."""
    results = []
    for layer in layers:
        attach = layer["attach_usd"]
        limit = layer["limit_usd"]

        bl_ll = np.minimum(np.maximum(baseline_loss - attach, 0), limit)
        bl_ell = float((prob * bl_ll).sum())
        bl_lol = bl_ell / limit if limit > 0 else 0

        adj_ll = np.minimum(np.maximum(adjusted_loss - attach, 0), limit)
        adj_ell = float((prob * adj_ll).sum())
        adj_lol = adj_ell / limit if limit > 0 else 0

        reduction = (bl_ell - adj_ell) / bl_ell * 100 if bl_ell > 0 else 0

        results.append({
            "attach_usd": attach,
            "limit_usd": limit,
            "baseline_ell_usd": round(bl_ell, 2),
            "baseline_lol_pct": round(bl_lol * 100, 2),
            "mitigated_ell_usd": round(adj_ell, 2),
            "mitigated_lol_pct": round(adj_lol * 100, 2),
            "ell_reduction_pct": round(reduction, 1),
        })
    return results
