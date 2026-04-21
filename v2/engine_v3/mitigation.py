"""
LDT v3 — Mitigation logic with pluggable modes
────────────────────────────────────────────────
Mode 1: uniform_scalar — same reduction to all events (v2 behavior)
Mode 2: hazard_intensity_curve — per-event interpolation from curve points

In both modes, failure probability and maintenance haircut are always
applied on top:
    effective = raw_reduction * (1 - failure) * (1 - maintenance)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from .models import MitigationMode


def compute_effective_reduction(base: float, failure: float,
                                maintenance: float) -> float:
    """Effective scalar reduction after failure and maintenance adjustments."""
    return base * (1.0 - failure) * (1.0 - maintenance)


def _interpolate_curve(hazard_intensities: pd.Series,
                       curve_points: list[dict]) -> np.ndarray:
    """
    Linearly interpolate reduction_pct from curve_points at each event's
    hazard_intensity. Clamp at min/max curve boundaries.

    curve_points: list of {"hazard_intensity": float, "reduction_pct": float}
    """
    # Sort by intensity
    sorted_pts = sorted(curve_points, key=lambda p: p["hazard_intensity"])
    x_pts = np.array([p["hazard_intensity"] for p in sorted_pts])
    y_pts = np.array([p["reduction_pct"] for p in sorted_pts])

    # np.interp clamps outside range by default
    return np.interp(hazard_intensities.values, x_pts, y_pts)


def adjust_event_losses(df: pd.DataFrame, intervention: dict) -> pd.DataFrame:
    """
    Apply mitigation to event losses based on mitigation_mode.

    Adds columns:
        raw_reduction_pct          (per-event raw curve or scalar value)
        effective_reduction_pct    (after failure + maintenance)
        adjusted_gross_loss_usd
        avoided_gross_loss_usd

    Returns a copy of df with new columns.
    """
    df = df.copy()
    mode = intervention.get("mitigation_mode", MitigationMode.uniform_scalar)
    failure = intervention.get("failure_probability", 0)
    maintenance = intervention.get("maintenance_haircut_pct", 0)

    if mode == MitigationMode.hazard_intensity_curve:
        # ── Curve mode ─────────────────────────────────────────────────
        curve_points = intervention.get("curve_points", [])
        raw_reductions = _interpolate_curve(df["hazard_intensity"], curve_points)
        df["raw_reduction_pct"] = raw_reductions
    else:
        # ── Scalar mode (v2 behavior) ──────────────────────────────────
        base = intervention.get("base_loss_reduction_pct", 0)
        df["raw_reduction_pct"] = base

    # Apply failure + maintenance on top
    df["effective_reduction_pct"] = (
        df["raw_reduction_pct"] * (1.0 - failure) * (1.0 - maintenance)
    )

    # Compute adjusted losses
    df["adjusted_gross_loss_usd"] = (
        df["gross_loss_usd"] * (1.0 - df["effective_reduction_pct"])
    )
    df["avoided_gross_loss_usd"] = (
        df["gross_loss_usd"] - df["adjusted_gross_loss_usd"]
    )

    return df
