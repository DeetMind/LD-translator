"""
LDT v3 — Plain-language summary generator
──────────────────────────────────────────
SME-generic wording. Broker/underwriter-facing.
"""

from __future__ import annotations


def _fmt_usd(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def generate_broker_summary(
    metrics: dict,
    intervention_name: str = "This intervention",
    hazard_label: str = "hail",
    hazard_share_pct: float | None = None,
    reinsurance_layers: list[dict] | None = None,
    mitigation_mode: str = "uniform_scalar",
    asset_metadata: dict | None = None,
) -> str:
    """
    Generate a plain-language summary for the broker/underwriter card.
    SME-generic wording — no residential-specific language.
    """
    sentences: list[str] = []

    # Context from asset metadata
    asset_desc = ""
    if asset_metadata:
        occ = asset_metadata.get("occupancy_type", "")
        roof = asset_metadata.get("roof_system_type", "")
        if occ:
            asset_desc = f" for this {occ.replace('_', ' ')} property"

    # Sentence 1 — Physical effect
    avoided_gross = metrics["avoided_gross_eal_usd"]
    reduction_pct = metrics["hazard_specific_reduction_pct"]
    sentences.append(
        f"{intervention_name} reduces expected {hazard_label} loss by "
        f"{_fmt_usd(avoided_gross)}/year ({reduction_pct:.0f}%){asset_desc}."
    )

    # Sentence 2 — Insurance effect
    avoided_insured = metrics["avoided_insured_eal_usd"]
    insured_red = metrics["insured_reduction_pct"]
    sentences.append(
        f"Under the stated policy assumptions, expected insured loss declines "
        f"by {_fmt_usd(avoided_insured)}/year ({insured_red:.0f}%)."
    )

    # Sentence 3 — Hazard share (conditional)
    total_red = metrics.get("total_risk_reduction_pct")
    if hazard_share_pct is not None and total_red is not None:
        share_display = f"{hazard_share_pct * 100:.0f}%"
        sentences.append(
            f"{hazard_label.capitalize()} represents {share_display} of estimated "
            f"total risk, implying an overall risk reduction of approximately "
            f"{total_red:.0f}%."
        )

    # Sentence 4 — Policy relevance
    inside_pct = metrics.get("avoided_inside_insured_pct", 0)
    if inside_pct >= 70:
        sentences.append(
            "Most of the avoided loss falls within the insured layer.")
    elif inside_pct >= 30:
        sentences.append(
            "Avoided loss is split between the insured and uninsured layers.")
    else:
        sentences.append(
            "A significant portion of avoided loss sits below the deductible "
            "or outside the insured layer.")

    # Sentence 5 — Mitigation mode note
    if mitigation_mode == "hazard_intensity_curve":
        sentences.append(
            "Mitigation effectiveness varies by event severity "
            "(hazard-intensity-conditioned curve).")

    # Sentence 6 — Reinsurance (conditional)
    if reinsurance_layers:
        material = [l for l in reinsurance_layers if l["ell_reduction_pct"] > 0]
        if material:
            best = max(material, key=lambda l: l["ell_reduction_pct"])
            sentences.append(
                f"Reinsurance layer at {_fmt_usd(best['attach_usd'])} xs "
                f"{_fmt_usd(best['limit_usd'])} sees a "
                f"{best['ell_reduction_pct']:.0f}% reduction in expected "
                f"layer loss."
            )

    return " ".join(sentences)


def generate_policy_relevance_note(metrics: dict) -> str:
    """Short declarative statement for the Policy Relevance card."""
    inside_pct = metrics.get("avoided_inside_insured_pct", 0)
    avoided_insured = metrics["avoided_insured_eal_usd"]
    avoided_gross = metrics["avoided_gross_eal_usd"]

    if avoided_gross <= 0:
        return ("This intervention has no measurable impact on expected loss "
                "under current assumptions.")
    if inside_pct >= 70:
        return ("Most avoided loss falls within the insured layer. "
                "This intervention is directly relevant to insured outcomes.")
    elif inside_pct >= 30:
        return ("Avoided loss is distributed across both the insured and "
                "retained layers. The intervention benefits the policyholder "
                "and may partially affect insured outcomes.")
    else:
        if avoided_insured <= 0:
            return ("This intervention has limited impact on insured loss "
                    "under current policy assumptions. Most avoided loss "
                    "sits below the deductible.")
        return ("A large share of avoided loss sits outside the insured layer. "
                "The primary benefit accrues to the policyholder's "
                "retained risk.")


def generate_model_scope_note(asset: dict) -> str:
    """
    Short note clarifying what is and isn't included in the current model.
    """
    future = asset.get("future_asset_layers") or []
    base = ("Current model includes building and roof loss only. "
            "Losses are modeled at the single-asset level.")
    if future:
        layers_str = ", ".join(future)
        base += (f" Additional asset layers ({layers_str}) are noted "
                 "but not yet included in the loss calculation.")
    return base
