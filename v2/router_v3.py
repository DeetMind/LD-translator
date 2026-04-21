"""
LDT v3 — API router
────────────────────
Thin route handlers. All logic in engine_v3/scenario_runner.py.
Mounted into the main FastAPI app alongside v2 routes.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pathlib import Path
import json
import io

from engine_v3.models import AnalysisRequestV3
from engine_v3.scenario_runner import run_scenario_v3

router = APIRouter(prefix="/api/v3", tags=["v3"])

STATIC_DIR = Path(__file__).parent / "static_v3"
SAMPLE_DIR = Path(__file__).parent / "sample_data_v3"


# ── Analysis ───────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_v3(request: AnalysisRequestV3):
    try:
        result = run_scenario_v3(request)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"errors": [str(e)]})

    if not result.get("ok", True):
        return JSONResponse(
            status_code=400,
            content={
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
            },
        )

    # Remove internal flag before returning
    result.pop("ok", None)
    return JSONResponse(content=result)


# ── Sample data ────────────────────────────────────────────────────────

@router.get("/sample-data")
async def get_sample_data_v3():
    """Return sample CSV, mitigation, policy, and archetypes for the SME demo."""
    return {
        "csv": (SAMPLE_DIR / "sample_hail_sme_scenario.csv").read_text(),
        "mitigation": json.loads(
            (SAMPLE_DIR / "sample_mitigation_v3.json").read_text()),
        "policy": json.loads(
            (SAMPLE_DIR / "sample_policy_v3.json").read_text()),
        "archetypes": json.loads(
            (SAMPLE_DIR / "archetypes.json").read_text()),
    }


@router.get("/download-sample-csv")
async def download_sample_csv_v3():
    """Download the sample SME hail scenario CSV."""
    path = SAMPLE_DIR / "sample_hail_sme_scenario.csv"
    return StreamingResponse(
        io.BytesIO(path.read_bytes()),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=sample_hail_sme_scenario.csv"
        },
    )


@router.get("/archetypes")
async def get_archetypes():
    """Return available archetype presets."""
    data = json.loads((SAMPLE_DIR / "archetypes.json").read_text())
    return data


# ── v3 frontend ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def v3_index():
    """Serve the v3 frontend page."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return HTMLResponse("<h1>LDT v3 — page not built yet</h1>")
