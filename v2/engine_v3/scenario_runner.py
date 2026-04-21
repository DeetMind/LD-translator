"""
LDT v3 — Scenario runner (orchestration layer)
───────────────────────────────────────────────
Thin, reusable pipeline:
    parse → validate → cap → mitigate → insure → metrics → summaries → response

Routes call run_scenario_v3() and return the result.
"""

from __future__ import annotations
import pandas as pd
import io
import base64

from .models import AnalysisRequestV3
from .validation import validate_scenario_v3, apply_asset_value_cap
from .mitigation import adjust_event_losses, compute_effective_reduction
from .insurance import map_to_insured_losses, resolve_deductible
from .metrics import compute_summary_metrics, compute_reinsurance_layer_metrics
from .summaries import (
    generate_broker_summary,
    generate_policy_relevance_note,
    generate_model_scope_note,
)


def run_scenario_v3(request: AnalysisRequestV3) -> dict:
    """
    Execute a full v3 analysis scenario.

    Returns a dict ready for JSONResponse, or raises ValueError on
    parse/validation errors.
    """
    # ── Parse CSV ──────────────────────────────────────────────────────
    try:
        csv_bytes = base64.b64decode(request.events_csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise ValueError(f"CSV parse error: {e}")

    asset = request.asset.model_dump()
    policy = request.policy.model_dump()
    intervention = request.intervention.model_dump()

    # ── Validate ───────────────────────────────────────────────────────
    validation = validate_scenario_v3(asset, df, policy, intervention)
    if not validation["valid"]:
        return {
            "ok": False,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    # ── Asset-value cap ────────────────────────────────────────────────
    was_capped = False
    if request.apply_asset_cap and asset["asset_value_usd"] > 0:
        df, was_capped = apply_asset_value_cap(df, asset["asset_value_usd"])

    # ── Step 1: Mitigation ─────────────────────────────────────────────
    df = adjust_event_losses(df, intervention)

    # ── Step 2: Insurance mapping ──────────────────────────────────────
    df = map_to_insured_losses(df, policy)

    # ── Step 3: Summary metrics ────────────────────────────────────────
    metrics = compute_summary_metrics(df, asset)

    # ── Step 3b: Reinsurance ───────────────────────────────────────────
    reinsurance_results = None
    layers_raw = policy.get("reinsurance_layers")
    if layers_raw:
        layers = [{"attach_usd": l["attach_usd"], "limit_usd": l["limit_usd"]}
                  for l in layers_raw]
        reinsurance_results = compute_reinsurance_layer_metrics(
            df["annual_probability"],
            df["gross_loss_usd"],
            df["adjusted_gross_loss_usd"],
            layers,
        )

    # ── Step 4: Summaries ──────────────────────────────────────────────
    mit_mode = intervention.get("mitigation_mode", "uniform_scalar")

    # Effective reduction for display
    if mit_mode == "uniform_scalar":
        eff_red = compute_effective_reduction(
            intervention["base_loss_reduction_pct"],
            intervention.get("failure_probability", 0),
            intervention.get("maintenance_haircut_pct", 0),
        )
    else:
        # For curve mode, report average effective reduction across events
        eff_red = float(df["effective_reduction_pct"].mean()) if len(df) > 0 else 0

    broker_summary = generate_broker_summary(
        metrics,
        intervention_name=intervention.get("intervention_name", "This intervention"),
        hazard_label="hail",
        hazard_share_pct=asset.get("hazard_share_pct"),
        reinsurance_layers=reinsurance_results,
        mitigation_mode=mit_mode,
        asset_metadata=asset,
    )

    policy_relevance = generate_policy_relevance_note(metrics)
    model_scope = generate_model_scope_note(asset)
    resolved_ded = resolve_deductible(policy)

    # ── Build event table ──────────────────────────────────────────────
    event_cols = [
        "event_id", "annual_probability", "return_period", "hazard_intensity",
        "gross_loss_usd", "adjusted_gross_loss_usd", "avoided_gross_loss_usd",
        "raw_reduction_pct", "effective_reduction_pct",
        "baseline_insured_loss_usd", "adjusted_insured_loss_usd",
        "avoided_insured_loss_usd",
        "baseline_uninsured_loss_usd", "adjusted_uninsured_loss_usd",
    ]
    event_table = df[[c for c in event_cols if c in df.columns]].copy()

    # ── Assemble response ──────────────────────────────────────────────
    return {
        "ok": True,
        "version": "v3",
        "metrics": metrics,
        "broker_summary": broker_summary,
        "policy_relevance_note": policy_relevance,
        "model_scope_note": model_scope,
        "mitigation_mode": mit_mode,
        "effective_reduction_pct": round(eff_red * 100, 1) if mit_mode == "uniform_scalar" else round(eff_red * 100, 1),
        "resolved_deductible_usd": round(resolved_ded, 2),
        "was_capped_by_asset_value": was_capped,
        "warnings": validation["warnings"],
        "event_table": event_table.to_dict(orient="records"),
        "reinsurance_layers": reinsurance_results,
        "asset_metadata": {
            "asset_name": asset.get("asset_name"),
            "asset_class": asset.get("asset_class"),
            "occupancy_type": asset.get("occupancy_type"),
            "roof_system_type": asset.get("roof_system_type"),
            "roof_age_years": asset.get("roof_age_years"),
            "future_asset_layers": asset.get("future_asset_layers"),
            "archetype_id": asset.get("archetype_id"),
        },
        "assumption_provenance": intervention.get("assumption_provenance"),
        "sensitivity_cases": intervention.get("sensitivity_cases"),
    }
