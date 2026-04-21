"""
LDT v3 — Pydantic request / response models
─────────────────────────────────────────────
SME-capable, future-extensible models for commercial building analysis.
Phase 1: single asset, single policy, single intervention, hail + roof only.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────

class AssetClass(str, Enum):
    sme_commercial = "sme_commercial"
    residential = "residential"
    industrial = "industrial"


class MitigationMode(str, Enum):
    uniform_scalar = "uniform_scalar"
    hazard_intensity_curve = "hazard_intensity_curve"


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ── Sub-models ─────────────────────────────────────────────────────────

class CurvePoint(BaseModel):
    """A single point on a hazard-intensity-conditioned reduction curve."""
    hazard_intensity: float = Field(..., ge=0)
    reduction_pct: float = Field(..., ge=0, le=1)


class AssumptionProvenance(BaseModel):
    """Credibility metadata for mitigation assumptions."""
    source_type: Optional[str] = None       # expert_judgment, literature, manufacturer_data, engineering_standard
    citation_note: Optional[str] = None
    confidence_level: Optional[ConfidenceLevel] = None
    notes: Optional[str] = None


class SensitivityCase(BaseModel):
    """Low/base/high parameters for sensitivity analysis."""
    low_reduction_pct: Optional[float] = None
    base_reduction_pct: Optional[float] = None
    high_reduction_pct: Optional[float] = None


class ReinsuranceLayerInput(BaseModel):
    attach_usd: float = Field(..., ge=0)
    limit_usd: float = Field(..., gt=0)


class ArchetypePreset(BaseModel):
    """Pre-filled defaults for an SME archetype."""
    archetype_id: str
    display_label: str
    asset_class: str = "sme_commercial"
    occupancy_type: str = ""
    roof_system_type: str = ""
    roof_age_years: Optional[int] = None
    asset_value_usd: float = 0
    notes: Optional[str] = None


# ── Request models ─────────────────────────────────────────────────────

class AssetInputV3(BaseModel):
    asset_name: str = "Sample Commercial Building"
    asset_class: str = "sme_commercial"
    occupancy_type: str = "small_warehouse"
    asset_value_usd: float = 1_350_000
    location_name: str = ""
    roof_system_type: str = "tpo"
    roof_age_years: Optional[int] = 10
    hazard_share_pct: Optional[float] = None    # 0–1 or None
    future_asset_layers: Optional[List[str]] = None   # e.g. ["solar"]
    archetype_id: Optional[str] = None


class PolicyInputV3(BaseModel):
    coverage_limit_usd: float = 1_350_000
    deductible_type: str = "percent_of_coverage"
    deductible_usd: Optional[float] = None
    deductible_pct: Optional[float] = 0.02
    insured_share_mode: str = "full_policy_inputs"
    insured_share_pct: Optional[float] = None
    coinsurance_pct: Optional[float] = 1.0
    premium_usd_current: Optional[float] = None
    reinsurance_layers: Optional[List[ReinsuranceLayerInput]] = None


class InterventionInputV3(BaseModel):
    intervention_name: str = "Commercial Roof Upgrade"
    mitigation_mode: MitigationMode = MitigationMode.uniform_scalar
    base_loss_reduction_pct: float = 0.35
    failure_probability: float = 0.05
    maintenance_haircut_pct: float = 0.10
    intervention_cost_usd: Optional[float] = None
    curve_points: Optional[List[CurvePoint]] = None
    assumption_provenance: Optional[AssumptionProvenance] = None
    sensitivity_cases: Optional[SensitivityCase] = None


class AnalysisRequestV3(BaseModel):
    events_csv_b64: str
    asset: AssetInputV3 = AssetInputV3()
    policy: PolicyInputV3 = PolicyInputV3()
    intervention: InterventionInputV3 = InterventionInputV3()
    apply_asset_cap: bool = True
