"""
Plain-language summary generator for LDT v2.

Produces broker / underwriter-facing text from computed metrics.

─── Template structure ────────────────────────────────────────────────
Sentence 1: Physical effect (gross loss reduction)
Sentence 2: Insurance effect (insured loss reduction)
Sentence 3: Hazard share context (only if hazard_share_pct provided)
Sentence 4: Policy relevance (where avoided loss sits)
────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations


def _fmt_usd(value: float) -> str:
    """Format a dollar amount for display."""
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
) -> str:
    """
    Generate a plain-language summary for the broker / underwriter card.

    Returns a multi-sentence paragraph.
    """
    sentences: list[str] = []

    # Sentence 1 — Physical effect
    avoided_gross = metrics["avoided_gross_eal_usd"]
    reduction_pct = metrics["hazard_specific_reduction_pct"]
    sentences.append(
        f"{intervention_name} reduces expected {hazard_label} loss by "
        f"{_fmt_usd(avoided_gross)}/year ({reduction_pct:.0f}%)."
    )

    # Sentence 2 — Insurance effect
    avoided_insured = metrics["avoided_insured_eal_usd"]
    insured_red_pct = metrics["insured_reduction_pct"]
    sentences.append(
        f"Under the stated policy assumptions, expected insured loss declines "
        f"by {_fmt_usd(avoided_insured)}/year ({insured_red_pct:.0f}%)."
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
            "Most of the avoided loss falls within the insured layer."
        )
    elif inside_pct >= 30:
        sentences.append(
            "Avoided loss is split between the insured and uninsured layers."
        )
    else:
        sentences.append(
            "A significant portion of avoided loss sits below the deductible "
            "or outside the insured layer."
        )

    # Sentence 5 — Reinsurance (conditional)
    if reinsurance_layers:
        material = [l for l in reinsurance_layers if l["ell_reduction_pct"] > 0]
        if material:
            best = max(material, key=lambda l: l["ell_reduction_pct"])
            sentences.append(
                f"Reinsurance layer at {_fmt_usd(best['attach_usd'])} xs "
                f"{_fmt_usd(best['limit_usd'])} sees a "
                f"{best['ell_reduction_pct']:.0f}% reduction in expected layer loss."
            )

    return " ".join(sentences)


def generate_policy_relevance_note(metrics: dict) -> str:
    """
    Short declarative statement for the Policy Relevance card.
    """
    inside_pct = metrics.get("avoided_inside_insured_pct", 0)
    avoided_insured = metrics["avoided_insured_eal_usd"]
    avoided_gross = metrics["avoided_gross_eal_usd"]

    if avoided_gross <= 0:
        return "This intervention has no measurable impact on expected loss under current assumptions."

    if inside_pct >= 70:
        return (
            "Most avoided loss falls within the insured layer. "
            "This intervention is directly relevant to insured outcomes."
        )
    elif inside_pct >= 30:
        return (
            "Avoided loss is distributed across both the insured and retained layers. "
            "The intervention benefits the policyholder and may partially affect "
            "insured outcomes."
        )
    else:
        if avoided_insured <= 0:
            return (
                "This intervention has limited impact on insured loss under current "
                "policy assumptions. Most avoided loss sits below the deductible."
            )
        return (
            "A large share of avoided loss sits outside the insured layer. "
            "The primary benefit accrues to the policyholder's retained risk."
        )
