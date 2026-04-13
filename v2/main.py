"""
Loss Distribution Translator v2 — FastAPI backend
──────────────────────────────────────────────────
Routes only.  All calculation logic lives in engine/.

Hail · Residential Property · Roof Upgrade Demo
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import json
import io
import base64
from pathlib import Path

from engine.validation import validate_scenario, apply_asset_value_cap
from engine.mitigation import adjust_event_losses, compute_effective_reduction
from engine.insurance import map_to_insured_losses, resolve_deductible
from engine.metrics import compute_summary_metrics, compute_reinsurance_layer_metrics
from engine.summaries import generate_broker_summary, generate_policy_relevance_note

app = FastAPI(title="Loss Distribution Translator v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (index.html, styles.css, app.js)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Request / response models ───────────────────────────────────────────

class AssetInput(BaseModel):
    asset_name: str = "Sample Residential Property"
    asset_value_usd: float = 375000
    location_name: str = ""
    hazard_share_pct: Optional[float] = None   # 0–1 or None

class ReinsuranceLayerInput(BaseModel):
    attach_usd: float
    limit_usd: float

class PolicyInput(BaseModel):
    coverage_limit_usd: float = 375000
    deductible_type: str = "percent_of_coverage"   # flat_usd | percent_of_coverage
    deductible_usd: Optional[float] = None
    deductible_pct: Optional[float] = 0.02
    insured_share_mode: str = "full_policy_inputs"  # full_policy_inputs | simple_insured_share_assumption
    insured_share_pct: Optional[float] = None
    coinsurance_pct: Optional[float] = 1.0
    premium_usd_current: Optional[float] = None
    reinsurance_layers: Optional[List[ReinsuranceLayerInput]] = None

class InterventionInput(BaseModel):
    intervention_name: str = "Impact-Resistant Roof Upgrade (Class 4)"
    base_loss_reduction_pct: float = 0.35
    failure_probability: float = 0.05
    maintenance_haircut_pct: float = 0.10
    intervention_cost_usd: Optional[float] = None

class AnalysisRequest(BaseModel):
    events_csv_b64: str
    asset: AssetInput = AssetInput()
    policy: PolicyInput = PolicyInput()
    intervention: InterventionInput = InterventionInput()
    apply_asset_cap: bool = True


# ── Routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text()


@app.post("/api/v2/analyze")
async def analyze(request: AnalysisRequest):
    # Parse CSV
    try:
        csv_bytes = base64.b64decode(request.events_csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")

    asset = request.asset.model_dump()
    policy = request.policy.model_dump()
    intervention = request.intervention.model_dump()

    # Validate
    validation = validate_scenario(asset, df, policy, intervention)
    if not validation["valid"]:
        return JSONResponse(
            status_code=400,
            content={"errors": validation["errors"], "warnings": validation["warnings"]},
        )

    # Optional asset-value cap
    was_capped = False
    if request.apply_asset_cap and asset["asset_value_usd"] > 0:
        df, was_capped = apply_asset_value_cap(df, asset["asset_value_usd"])

    # Step 1 — Mitigation
    df = adjust_event_losses(
        df,
        base_loss_reduction_pct=intervention["base_loss_reduction_pct"],
        failure_probability=intervention.get("failure_probability", 0),
        maintenance_haircut_pct=intervention.get("maintenance_haircut_pct", 0),
    )

    # Step 2 — Insurance mapping
    df = map_to_insured_losses(df, policy)

    # Step 3 — Summary metrics
    metrics = compute_summary_metrics(df, asset)

    # Step 3b — Reinsurance layer metrics (optional)
    reinsurance_results = None
    layers_input = policy.get("reinsurance_layers")
    if layers_input:
        layers = [{"attach_usd": l["attach_usd"], "limit_usd": l["limit_usd"]} for l in layers_input]
        reinsurance_results = compute_reinsurance_layer_metrics(
            df["annual_probability"],
            df["gross_loss_usd"],
            df["adjusted_gross_loss_usd"],
            layers,
        )

    # Step 4 — Plain-language summaries
    effective_reduction = compute_effective_reduction(
        intervention["base_loss_reduction_pct"],
        intervention.get("failure_probability", 0),
        intervention.get("maintenance_haircut_pct", 0),
    )

    broker_summary = generate_broker_summary(
        metrics,
        intervention_name=intervention.get("intervention_name", "This intervention"),
        hazard_label="hail",
        hazard_share_pct=asset.get("hazard_share_pct"),
        reinsurance_layers=reinsurance_results,
    )

    policy_relevance_note = generate_policy_relevance_note(metrics)

    # Resolved deductible for display
    resolved_deductible_usd = resolve_deductible(policy)

    # Build event table for frontend
    event_table_cols = [
        "event_id", "annual_probability", "return_period", "hazard_intensity",
        "gross_loss_usd", "adjusted_gross_loss_usd", "avoided_gross_loss_usd",
        "baseline_insured_loss_usd", "adjusted_insured_loss_usd", "avoided_insured_loss_usd",
        "baseline_uninsured_loss_usd", "adjusted_uninsured_loss_usd",
    ]
    event_table = df[[c for c in event_table_cols if c in df.columns]].copy()

    return JSONResponse(content={
        "metrics": metrics,
        "broker_summary": broker_summary,
        "policy_relevance_note": policy_relevance_note,
        "effective_reduction_pct": round(effective_reduction * 100, 1),
        "resolved_deductible_usd": round(resolved_deductible_usd, 2),
        "was_capped_by_asset_value": was_capped,
        "warnings": validation["warnings"],
        "event_table": event_table.to_dict(orient="records"),
        "reinsurance_layers": reinsurance_results,
    })


@app.get("/api/v2/sample-data")
async def get_sample_data():
    """Return sample CSV, mitigation, and policy data for the hail demo."""
    base = Path(__file__).parent / "sample_data"
    return {
        "csv": (base / "sample_hail_scenario.csv").read_text(),
        "mitigation": json.loads((base / "sample_mitigation.json").read_text()),
        "policy": json.loads((base / "sample_policy.json").read_text()),
    }


@app.get("/api/v2/download-sample-csv")
async def download_sample_csv():
    """Download the sample hail scenario CSV for format reference."""
    path = Path(__file__).parent / "sample_data" / "sample_hail_scenario.csv"
    return StreamingResponse(
        io.BytesIO(path.read_bytes()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_hail_scenario.csv"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
