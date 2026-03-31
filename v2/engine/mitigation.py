"""
Mitigation logic for LDT v2.

Computes effective reduction percentage and applies it to gross event losses.

─── Design note ───────────────────────────────────────────────────────────
The mitigation effectiveness parameters below are *placeholder assumptions*
for the hail roof-upgrade demo.  They are intended to be replaced with
IBHS-informed values when available.

Current defaults:
  base_loss_reduction_pct  = 0.35   (illustrative Class 4 roof benefit)
  failure_probability      = 0.05   (installation / extreme-impact risk)
  maintenance_haircut_pct  = 0.10   (aging / wear over policy period)

These are stored in sample_data/sample_mitigation.json and are fully
editable by the user in the UI.  They are intentionally separated from
the event-loss CSV assumptions so that mitigation effectiveness and
hazard/loss scenarios can be updated independently.
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def compute_effective_reduction(
    base_loss_reduction_pct: float,
    failure_probability: float = 0.0,
    maintenance_haircut_pct: float = 0.0,
) -> float:
    """
    Compute the single effective reduction percentage.

    Formula:
        effective = base * (1 - failure_probability) * (1 - maintenance_haircut)
    Capped between 0 and 1.

    This is a simple multiplicative model.  Future versions may use
    hazard-intensity-conditioned reduction curves (e.g., from IBHS
    test data mapping hail size to roof-damage reduction).
    """
    effective = (
        base_loss_reduction_pct
        * (1.0 - failure_probability)
        * (1.0 - maintenance_haircut_pct)
    )
    return float(np.clip(effective, 0.0, 1.0))


def adjust_event_losses(
    df: pd.DataFrame,
    base_loss_reduction_pct: float,
    failure_probability: float = 0.0,
    maintenance_haircut_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Apply mitigation to each event row.

    Adds columns:
        effective_reduction_pct   — single scalar applied uniformly
        adjusted_gross_loss_usd   — gross * (1 - effective_reduction)
        avoided_gross_loss_usd    — gross - adjusted

    ─── Future extension point ────────────────────────────────────────
    For hazard_intensity_curve mode, this function would accept a
    mapping (hazard_intensity → reduction_pct) and compute per-event
    reductions.  The current implementation applies a uniform scalar.
    ────────────────────────────────────────────────────────────────────
    """
    df = df.copy()

    eff = compute_effective_reduction(
        base_loss_reduction_pct, failure_probability, maintenance_haircut_pct
    )

    df["effective_reduction_pct"] = eff
    df["adjusted_gross_loss_usd"] = df["gross_loss_usd"] * (1.0 - eff)
    df["avoided_gross_loss_usd"] = df["gross_loss_usd"] - df["adjusted_gross_loss_usd"]

    return df
