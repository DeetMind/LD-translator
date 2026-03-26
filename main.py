"""
Loss Distribution Translator — FastAPI backend
Translates a physical flood mitigation intervention into insurance-relevant metrics.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import json
import io
import os
from typing import List, Optional
from pathlib import Path

app = FastAPI(title="Loss Distribution Translator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data models ──────────────────────────────────────────────────────────────

class ReinsuranceLayer(BaseModel):
    attach_usd: float
    limit_usd: float

class MitigationParams(BaseModel):
    project_name: str
    design_height_ft: float
    freeboard_ft: float
    protected_loss_reduction_pct: float   # 0–1
    overtop_loss_reduction_pct: float     # 0–1
    failure_probability: float            # 0–1
    maintenance_haircut_pct: float        # 0–1

class InsuranceStructure(BaseModel):
    deductible_usd: float
    attachment_points_usd: List[float]
    reinsurance_layers: List[ReinsuranceLayer]
    capital_thresholds_usd: List[float]

class AnalysisRequest(BaseModel):
    events_csv_b64: str          # base64-encoded CSV text
    mitigation: MitigationParams
    insurance: InsuranceStructure

# ── Core calculation functions ────────────────────────────────────────────────

def apply_mitigation(df: pd.DataFrame, m: MitigationParams) -> pd.DataFrame:
    """
    Step 1 — depth-conditional loss reduction
      If flood_depth_ft <= design_height_ft:
          adjusted_loss = gross_loss * (1 - protected_loss_reduction_pct)
      Else:
          adjusted_loss = gross_loss * (1 - overtop_loss_reduction_pct)

    Step 2 — blend with structural failure probability
      effective_loss = (1 - failure_prob) * adjusted_loss + failure_prob * gross_loss

    Step 3 — maintenance haircut on the benefit
      benefit       = gross_loss - effective_loss
      haircut_benefit = benefit * (1 - maintenance_haircut_pct)
      final_loss    = gross_loss - haircut_benefit
    """
    df = df.copy()

    # Step 1
    protected_mask = df["flood_depth_ft"] <= m.design_height_ft
    df["adjusted_loss"] = np.where(
        protected_mask,
        df["gross_loss_usd"] * (1 - m.protected_loss_reduction_pct),
        df["gross_loss_usd"] * (1 - m.overtop_loss_reduction_pct),
    )

    # Step 2
    df["effective_loss"] = (
        (1 - m.failure_probability) * df["adjusted_loss"]
        + m.failure_probability * df["gross_loss_usd"]
    )

    # Step 3
    benefit = df["gross_loss_usd"] - df["effective_loss"]
    haircut_benefit = benefit * (1 - m.maintenance_haircut_pct)
    df["final_loss"] = df["gross_loss_usd"] - haircut_benefit

    return df


def compute_eal(annual_prob: pd.Series, loss: pd.Series) -> float:
    """Expected Annual Loss = sum(annual_probability * loss)"""
    return float((annual_prob * loss).sum())


def compute_ep_curve(annual_prob: pd.Series, loss: pd.Series) -> dict:
    """
    Exceedance Probability curve.
    Sort events by loss descending; for each loss level EP = sum of
    annual_probability for events with loss >= that level.
    Returns dict with lists 'loss' and 'ep'.
    """
    order = loss.argsort()[::-1]
    sorted_loss = loss.iloc[order].values
    sorted_prob = annual_prob.iloc[order].values
    ep = np.cumsum(sorted_prob)
    return {"loss_usd": sorted_loss.tolist(), "exceedance_probability": ep.tolist()}


def compute_pml(annual_prob: pd.Series, loss: pd.Series, return_period: int) -> float:
    """
    PML at a given return period.
    Find the largest loss where cumulative exceedance probability >= 1/return_period.
    Uses interpolation on the EP curve.
    """
    target_ep = 1.0 / return_period
    order = loss.argsort()[::-1]
    sorted_loss = loss.iloc[order].values
    sorted_prob = annual_prob.iloc[order].values
    ep = np.cumsum(sorted_prob)

    # Find the first (largest) loss where cumulative EP >= target.
    # Because losses are sorted descending, idx[0] is the loss at the
    # boundary where the EP curve first crosses the target return period.
    idx = np.where(ep >= target_ep)[0]
    if len(idx) == 0:
        return 0.0
    return float(sorted_loss[idx[0]])


def compute_attachment_probabilities(
    annual_prob: pd.Series, loss: pd.Series, attachment_points: List[float]
) -> List[dict]:
    """
    For each attachment point A:
      attachment_prob = sum(annual_probability where loss > A)
    """
    results = []
    for attach in attachment_points:
        mask = loss > attach
        prob = float(annual_prob[mask].sum())
        results.append({"attachment_usd": attach, "exceedance_probability": prob})
    return results


def compute_layer_metrics(
    annual_prob: pd.Series, loss: pd.Series, layers: List[ReinsuranceLayer]
) -> List[dict]:
    """
    For each reinsurance layer (attach, limit):
      layer_loss = min(max(loss - attach, 0), limit)
      expected_layer_loss = sum(annual_probability * layer_loss)
    """
    results = []
    for layer in layers:
        layer_loss = np.minimum(np.maximum(loss - layer.attach_usd, 0), layer.limit_usd)
        ell = float((annual_prob * layer_loss).sum())
        results.append({
            "attach_usd": layer.attach_usd,
            "limit_usd": layer.limit_usd,
            "expected_layer_loss_usd": ell,
            "loss_on_line_pct": ell / layer.limit_usd if layer.limit_usd > 0 else 0,
        })
    return results


def compute_capital_exceedance(
    annual_prob: pd.Series, loss: pd.Series, thresholds: List[float]
) -> List[dict]:
    """
    Probability of exceeding each capital threshold.
    Same as attachment probability logic.
    """
    results = []
    for threshold in thresholds:
        mask = loss > threshold
        prob = float(annual_prob[mask].sum())
        results.append({"threshold_usd": threshold, "exceedance_probability": prob})
    return results


def run_analysis(df: pd.DataFrame, mit: MitigationParams, ins: InsuranceStructure) -> dict:
    df_mit = apply_mitigation(df, mit)

    prob = df["annual_probability"]
    gross = df["gross_loss_usd"]
    final = df_mit["final_loss"]

    # EAL
    baseline_eal = compute_eal(prob, gross)
    mitigated_eal = compute_eal(prob, final)
    eal_reduction_pct = (baseline_eal - mitigated_eal) / baseline_eal * 100 if baseline_eal else 0

    # EP curves
    baseline_ep = compute_ep_curve(prob, gross)
    mitigated_ep = compute_ep_curve(prob, final)

    # PMLs
    b_pml100 = compute_pml(prob, gross, 100)
    m_pml100 = compute_pml(prob, final, 100)
    b_pml250 = compute_pml(prob, gross, 250)
    m_pml250 = compute_pml(prob, final, 250)

    # Attachment probabilities
    b_attach = compute_attachment_probabilities(prob, gross, ins.attachment_points_usd)
    m_attach = compute_attachment_probabilities(prob, final, ins.attachment_points_usd)

    # Layer metrics
    b_layers = compute_layer_metrics(prob, gross, ins.reinsurance_layers)
    m_layers = compute_layer_metrics(prob, final, ins.reinsurance_layers)

    # Capital thresholds
    b_capital = compute_capital_exceedance(prob, gross, ins.capital_thresholds_usd)
    m_capital = compute_capital_exceedance(prob, final, ins.capital_thresholds_usd)

    # Event-level table
    event_table = df_mit[[
        "event_id", "annual_probability", "return_period",
        "flood_depth_ft", "gross_loss_usd", "final_loss"
    ]].copy()
    event_table["loss_reduction_usd"] = event_table["gross_loss_usd"] - event_table["final_loss"]
    event_table["loss_reduction_pct"] = (
        event_table["loss_reduction_usd"] / event_table["gross_loss_usd"] * 100
    ).round(1)

    return {
        "project_name": mit.project_name,
        "kpis": {
            "baseline_eal": baseline_eal,
            "mitigated_eal": mitigated_eal,
            "eal_reduction_pct": eal_reduction_pct,
            "baseline_pml_100": b_pml100,
            "mitigated_pml_100": m_pml100,
            "pml_100_reduction_pct": (b_pml100 - m_pml100) / b_pml100 * 100 if b_pml100 else 0,
            "baseline_pml_250": b_pml250,
            "mitigated_pml_250": m_pml250,
            "pml_250_reduction_pct": (b_pml250 - m_pml250) / b_pml250 * 100 if b_pml250 else 0,
        },
        "ep_curves": {
            "baseline": baseline_ep,
            "mitigated": mitigated_ep,
        },
        "attachment_probabilities": {
            "baseline": b_attach,
            "mitigated": m_attach,
        },
        "reinsurance_layers": {
            "baseline": b_layers,
            "mitigated": m_layers,
        },
        "capital_thresholds": {
            "baseline": b_capital,
            "mitigated": m_capital,
        },
        "event_table": event_table.to_dict(orient="records"),
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return html_path.read_text()


@app.post("/api/analyze")
async def analyze(request: AnalysisRequest):
    import base64
    try:
        csv_bytes = base64.b64decode(request.events_csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")

    required_cols = {"event_id", "annual_probability", "return_period",
                     "flood_depth_ft", "gross_loss_usd"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing CSV columns: {missing}")

    result = run_analysis(df, request.mitigation, request.insurance)
    return JSONResponse(content=result)


@app.get("/faq", response_class=HTMLResponse)
async def faq():
    faq_path = Path(__file__).parent / "faq.html"
    return faq_path.read_text()


@app.get("/api/download-example-csv")
async def download_example_csv():
    path = Path(__file__).parent / "sample_data" / "example_events.csv"
    return StreamingResponse(
        io.BytesIO(path.read_bytes()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=example_events.csv"},
    )


@app.get("/api/sample-data")
async def get_sample_data():
    """Return sample CSV and JSON payloads for quick-start."""
    sample_csv_path = Path(__file__).parent / "sample_data" / "example_events.csv"
    sample_mit_path = Path(__file__).parent / "sample_data" / "sample_mitigation.json"
    sample_ins_path = Path(__file__).parent / "sample_data" / "sample_insurance.json"
    return {
        "csv": sample_csv_path.read_text(),
        "mitigation": json.loads(sample_mit_path.read_text()),
        "insurance": json.loads(sample_ins_path.read_text()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
