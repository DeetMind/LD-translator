# Loss Distribution Translator — Specification Document

**Version:** 3.0 (current build)
**Last updated:** April 2026
**Status:** Working prototype — illustrative data only

---

## 1. Purpose

The Loss Distribution Translator (LDT) converts physical risk reduction into insurance-relevant financial outcomes.

When a building owner invests in mitigation — such as upgrading a roof to resist hail — the physical benefit (less damage) and the financial benefit (lower insurance loss) are not the same number. Losses interact with policy structure: deductibles absorb small losses, coverage limits cap large ones, and the portion that changes for the insurer versus the property owner depends entirely on where the avoided loss falls relative to those boundaries.

The LDT makes that translation explicit. It takes an event-based loss distribution, applies a mitigation assumption, maps the result through a policy layer, and reports what changes — for the insurer, for the property owner, and for reinsurance layers above.

**It is not a hazard model, a damage model, or a pricing engine.** It operates downstream of all three. It takes losses as given and translates them.

---

## 2. What the tool is and is not

### What it is

- A **translation layer** between physical risk reduction and insurance-relevant metrics
- A **sensitivity tool** for exploring how mitigation interacts with policy structure
- A **communication device** for making the insurance case for resilience investment
- A **single-asset, single-hazard** calculator operating on user-supplied event losses

### What it is not

- Not a catastrophe model — it does not simulate weather, geology, or hazard frequency
- Not a vulnerability model — it does not convert hazard intensity into damage
- Not an actuarial pricing tool — it does not estimate premium or binding terms
- Not a portfolio tool — it handles one building at a time, not aggregations
- Not empirically calibrated — outputs are mechanically correct but depend entirely on input assumptions

---

## 3. Core workflow

The tool executes a fixed five-step pipeline:

```
[Event Losses] → [Mitigation] → [Insurance Mapping] → [Metrics] → [Summaries]
```

### Step 1: Event loss input

The user provides a CSV with one row per loss scenario:

| Column | Description |
|--------|-------------|
| `event_id` | Unique event identifier (e.g., H001) |
| `annual_probability` | Probability this event occurs in any given year (0 < p ≤ 1) |
| `return_period` | Inverse of probability (e.g., 100 = 1-in-100-year event) |
| `hazard_intensity` | Severity measure (e.g., hail diameter in inches) |
| `gross_loss_usd` | Total loss to the building if this event occurs, before any insurance |

Events are independent scenarios, not a time series. Each represents a distinct severity level with an associated annual likelihood. The sample dataset contains 10 events spanning 2-year to 500-year return periods.

**Asset-value cap:** If enabled, gross losses are clipped at the stated replacement value before any calculations. This prevents losses from exceeding the physical value of the building.

### Step 2: Mitigation

The tool supports two mitigation modes:

#### Mode A — Uniform scalar (default)

Three parameters combine into a single effective reduction applied identically to every event:

```
effective_reduction = base_reduction × (1 - failure_probability) × (1 - maintenance_haircut)
```

| Parameter | Meaning | Sample value |
|-----------|---------|-------------|
| Base reduction | Idealized loss reduction from the intervention | 35% |
| Failure probability | Chance the intervention fails entirely in a given event | 5% |
| Maintenance haircut | Long-run degradation from imperfect maintenance | 10% |

Sample calculation: 0.35 × (1 - 0.05) × (1 - 0.10) = **29.9% effective reduction**

Every event's gross loss is reduced by this percentage:

```
adjusted_gross_loss = gross_loss × (1 - effective_reduction)
avoided_gross_loss = gross_loss - adjusted_gross_loss
```

#### Mode B — Hazard-intensity curve

Instead of a single reduction percentage, the user provides a curve mapping hazard intensity to reduction:

| Hail diameter (in) | Reduction |
|---------------------|-----------|
| 1.00 | 50% |
| 1.50 | 40% |
| 2.00 | 30% |
| 3.00 | 15% |
| 4.00 | 5% |

The tool interpolates linearly between points using `numpy.interp`. Values outside the curve range are clamped to the nearest endpoint.

Failure probability and maintenance haircut are still applied on top:

```
effective_reduction_per_event = interpolated_reduction × (1 - failure) × (1 - maintenance)
```

This mode reflects the reality that roof upgrades are more effective against moderate hail than extreme hail.

### Step 3: Insurance mapping

Mitigated and baseline losses are mapped through the policy layer to produce insured and uninsured (retained) amounts.

**Full policy mode** (default):

```
insured_loss = min(max(gross_loss - deductible, 0), coverage_limit)
uninsured_loss = gross_loss - insured_loss
```

The deductible can be specified as a flat dollar amount or as a percentage of coverage limit (e.g., 2% of $1,350,000 = $27,000).

**Simple insured share mode** (alternative):

```
insured_loss = min(gross_loss × insured_share_pct, coverage_limit)
```

This mode exists for cases where the user doesn't have full policy terms but has an estimate of the fraction that is insured.

Both modes produce six columns:

- `baseline_insured_loss_usd` / `adjusted_insured_loss_usd`
- `baseline_uninsured_loss_usd` / `adjusted_uninsured_loss_usd`
- `avoided_insured_loss_usd` / `avoided_uninsured_loss_usd`

**Coinsurance** is captured as an input but does not alter calculations in the current version.

### Step 4: Metrics

#### Expected Annual Loss (EAL)

EAL is a probability-weighted average: the sum of each event's loss multiplied by its annual probability.

```
EAL = Σ (annual_probability_i × loss_i)
```

This is computed for six quantities:
- Baseline gross, adjusted gross, avoided gross
- Baseline insured, adjusted insured, avoided insured
- Baseline uninsured, adjusted uninsured, avoided uninsured

EAL represents the long-run average annual cost. It is not a prediction for any single year.

#### Exceedance Probability (EP) curves

Events are sorted by loss from largest to smallest, and cumulative probability is computed. The EP curve shows the relationship between severity and likelihood — what loss level is exceeded at each probability threshold.

Two EP curves are produced:
- **Gross loss EP** — total building loss before and after mitigation
- **Insured loss EP** — loss to the insurer before and after mitigation

#### Reduction percentages

- **Hazard-specific reduction:** avoided gross EAL ÷ baseline gross EAL
- **Insured reduction:** avoided insured EAL ÷ baseline insured EAL
- **Total-risk reduction** (optional): if the user provides a hazard share percentage, the tool estimates what the hazard-specific reduction means for total risk across all perils

#### Policy relevance ratio

```
avoided_inside_insured_pct = avoided_insured_EAL ÷ avoided_gross_EAL × 100
```

This answers: *of the total loss avoided by mitigation, what fraction shows up in the insured layer?* A high ratio means the intervention is directly relevant to the insurer. A low ratio means most savings accrue to the property owner's retained risk (below the deductible).

#### Reinsurance layer metrics (optional)

For each excess-of-loss layer defined by the user (attachment point + limit):

```
layer_loss = min(max(gross_loss - attachment, 0), limit)
ELL = Σ (probability × layer_loss)
LOL = ELL ÷ limit
```

Computed for both baseline and mitigated scenarios, yielding ELL reduction percentage per layer.

### Step 5: Plain-language summaries

The tool generates two text outputs:

**Broker/underwriter summary:** A 3–6 sentence paragraph stating the intervention's impact on expected loss, insured loss, policy relevance, and reinsurance (if applicable). Written for an insurance professional.

**Policy relevance note:** A single declarative statement classifying whether the intervention primarily benefits the insurer, the property owner, or both — based on where avoided loss falls relative to the deductible and coverage limit.

**Model scope note** (v3): Declares what is and isn't included in the current model (e.g., "building and roof loss only") and lists any future asset layers that are noted but not yet modeled.

---

## 4. Inputs — complete reference

### 4.1 Event loss CSV

| Column | Type | Constraints |
|--------|------|------------|
| `event_id` | string | Required, unique identifier |
| `annual_probability` | float | Required, > 0 and ≤ 1 |
| `return_period` | float | Required, inverse of probability |
| `hazard_intensity` | float | Required, ≥ 0 (e.g., hail diameter in inches) |
| `gross_loss_usd` | float | Required, ≥ 0 |

### 4.2 Asset

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| Asset name | string | "Sample Commercial Building" | Display label |
| Asset class | enum | sme_commercial | sme_commercial, residential, industrial |
| Occupancy type | string | small_warehouse | small_warehouse, small_retail, office, restaurant, other |
| Replacement value ($) | float | 1,350,000 | Used for loss capping and context |
| Location | string | — | Display only |
| Roof system type | string | tpo | tpo, modified_bitumen, epdm, built_up, metal_standing_seam, asphalt_shingle |
| Roof age (years) | int | 10 | Metadata, not used in calculations |
| Hail share of total risk (%) | float | — | Optional. If provided, used to estimate total-risk reduction |
| Future asset layers | list | — | Passive metadata (e.g., "solar", "HVAC"). Not used in calculations |
| Archetype preset | string | — | Auto-fills asset fields from a predefined profile |

### 4.3 Mitigation / intervention

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| Intervention name | string | "Commercial Roof Upgrade" | Display label |
| Mitigation mode | enum | uniform_scalar | uniform_scalar or hazard_intensity_curve |
| Base loss reduction (%) | float | 35% | Scalar mode only |
| Failure probability (%) | float | 5% | Applied in both modes |
| Maintenance haircut (%) | float | 10% | Applied in both modes |
| Curve points | list | — | Curve mode only. List of (hazard_intensity, reduction_pct) pairs |
| Intervention cost ($) | float | 45,000 | Informational only. Not used in loss calculations |

**Assumption provenance** (metadata, passed through to output):

| Field | Notes |
|-------|-------|
| Source type | expert_judgment, literature, manufacturer_data, engineering_standard |
| Confidence level | low, medium, high |
| Citation note | Free text |
| Notes | Free text |

**Sensitivity cases** (metadata, passed through to output):

| Field | Notes |
|-------|-------|
| Low reduction (%) | Conservative estimate |
| Base reduction (%) | Central estimate |
| High reduction (%) | Optimistic estimate |

### 4.4 Policy

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| Policy mode | enum | full_policy_inputs | full_policy_inputs or simple_insured_share_assumption |
| Coverage limit ($) | float | 1,350,000 | Maximum insured payout per event |
| Deductible type | enum | percent_of_coverage | flat_usd or percent_of_coverage |
| Deductible ($) | float | — | Flat mode only |
| Deductible (%) | float | 2% | Percent mode only. Applied to coverage limit |
| Insured share (%) | float | — | Simple mode only |
| Coinsurance (%) | float | 100% | Captured but not active in current version |
| Premium ($/yr) | float | — | Informational only. Not used in calculations |

### 4.5 Reinsurance (optional)

Each excess-of-loss layer:

| Field | Type | Notes |
|-------|------|-------|
| Attachment ($) | float | Loss level where the layer begins responding |
| Limit ($) | float | Maximum payout from this layer |

---

## 5. Outputs — complete reference

### 5.1 EAL metrics table

| Metric | Baseline | Mitigated | Annual savings |
|--------|----------|-----------|----------------|
| Insured loss | EAL of insured losses | EAL of mitigated insured losses | Difference + % |
| Gross loss | EAL of gross losses | EAL of mitigated gross losses | Difference + % |
| Uninsured / retained | EAL of uninsured losses | EAL of mitigated uninsured losses | Difference |

### 5.2 EP curves

Two side-by-side charts (Plotly.js):
- Gross loss EP: baseline (red) vs. mitigated (blue)
- Insured loss EP: baseline (red) vs. mitigated (blue)

X-axis: exceedance probability (log scale, 0.2% to 50%)
Y-axis: loss in dollars

### 5.3 Reinsurance layer table

Per layer: baseline ELL, mitigated ELL, ELL reduction %, baseline LOL%, mitigated LOL%

### 5.4 Event-level detail table

Full per-event breakdown: event ID, return period, hazard intensity, gross loss, adjusted gross, avoided gross, insured loss, adjusted insured, avoided insured. In curve mode, also shows raw and effective reduction percentages per event.

### 5.5 Text summaries

- Broker/underwriter summary (3–6 sentences)
- Policy relevance note (1 sentence)
- Model scope note (1–2 sentences)
- Assumption provenance card (if provided)

---

## 6. Architecture

### Technology

- **Backend:** Python, FastAPI
- **Frontend:** Vanilla HTML/CSS/JS (no framework, no build tools)
- **Charts:** Plotly.js
- **Deployment:** Vercel (serverless Python)

### Code structure

```
v2/
├── main.py                    # FastAPI app, mounts v2 + v3
├── router_v3.py               # v3 API routes (thin wrappers)
│
├── engine/                    # v2 calculation modules
│   ├── validation.py
│   ├── mitigation.py
│   ├── insurance.py
│   ├── metrics.py
│   └── summaries.py
│
├── engine_v3/                 # v3 calculation modules
│   ├── models.py              # Pydantic request/response models
│   ├── validation.py          # Input validation + warnings
│   ├── mitigation.py          # Scalar + curve mitigation
│   ├── insurance.py           # Policy-layer mapping
│   ├── metrics.py             # EAL, EP curves, reinsurance
│   ├── summaries.py           # Plain-language text generation
│   └── scenario_runner.py     # Orchestration pipeline
│
├── static/                    # v2 frontend
├── static_v3/                 # v3 frontend
├── sample_data/               # v2 sample inputs
└── sample_data_v3/            # v3 sample inputs
```

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v3/analyze` | Run full analysis |
| GET | `/api/v3/sample-data` | Load sample CSV + defaults |
| GET | `/api/v3/archetypes` | List archetype presets |
| GET | `/api/v3/download-sample-csv` | Download sample CSV file |
| GET | `/api/v3/` | Serve v3 frontend page |

### Design pattern

Routes are thin wrappers. All logic lives in `engine_v3/scenario_runner.py`, which calls validation → mitigation → insurance → metrics → summaries in sequence. The scenario runner returns a dict; the route returns it as JSON.

---

## 7. Archetype system

Archetypes are preset building profiles that auto-fill asset fields. Two are included:

| Archetype | Asset class | Occupancy | Roof | Age | Value |
|-----------|------------|-----------|------|-----|-------|
| Small Warehouse (Flat Roof) | sme_commercial | small_warehouse | TPO | 10 yr | $1,350,000 |
| Small Retail (Flat Roof) | sme_commercial | small_retail | modified_bitumen | 15 yr | $950,000 |

Archetypes are stored in `archetypes.json` and loaded into a dropdown. They are starting points, not constraints — all fields remain editable after selection.

---

## 8. Credibility gaps and limitations

This section is the most important for any stakeholder evaluating the tool.

### 8.1 Input data

**Gap:** The sample event losses are illustrative. They were not generated by a catastrophe model, engineering study, or claims analysis. They are plausible but not calibrated.

**What's needed:** Event loss distributions derived from defensible sources — catastrophe model output (AIR, RMS, CoreLogic), historical claims data, or engineering-based loss estimates. The tool's structure is agnostic to the source, but the credibility of outputs depends entirely on the credibility of inputs.

### 8.2 Mitigation assumptions

**Gap:** The mitigation parameters (35% base reduction, 5% failure, 10% maintenance) are expert-judgment placeholders. They are not tied to a specific product test, IBHS rating, or manufacturer specification.

**What's needed:**
- Product-specific performance data from IBHS, FM Global, or manufacturer testing
- Hazard-intensity-conditioned performance curves (not just a single scalar)
- Empirical validation against before-and-after claims data where available
- Transparent provenance: who estimated these numbers, on what basis, and at what confidence level

The tool includes metadata fields for assumption provenance (source type, confidence level, citation) specifically to make this gap visible and trackable.

### 8.3 Mitigation model simplicity

**Gap:** Both mitigation modes are reductive. Uniform scalar applies the same reduction to a $4,000 loss and a $680,000 loss. Hazard-intensity curve is better but still assumes a smooth, monotonic relationship.

**Reality:** Damage is nonlinear. A roof upgrade might eliminate losses entirely below a threshold and provide diminishing benefit above it. Component-level damage (roof vs. siding vs. interior) responds differently to the same intervention. The tool does not model any of this.

**What's needed:** Component-level vulnerability functions that map hazard intensity to damage ratio per building component, with mitigation adjustments per component. This is a significant modeling effort beyond the current scope.

### 8.4 Single-peril, single-asset scope

**Gap:** The tool handles one building, one hazard, one intervention at a time. It cannot aggregate across a portfolio, model correlated losses, or handle multi-peril interactions.

**What's needed for portfolio use:**
- Multi-asset aggregation with spatial correlation
- Multiple hazard support (wind, flood, fire)
- Combined intervention effects
- Portfolio-level EAL and PML metrics

### 8.5 Insurance model simplicity

**Gap:** The policy layer is a simplified deductible-and-limit structure. It does not model:
- Sublimits for specific perils (e.g., wind/hail sublimit)
- Coinsurance penalties
- Aggregate deductibles vs. per-occurrence deductibles
- Waiting periods or time elements
- Business interruption
- Claim adjustment factors or depreciation

**What's needed:** A more realistic policy engine that handles the common coverage structures in commercial property insurance. The current model is directionally correct but may overstate or understate insured loss for policies with complex terms.

### 8.6 No premium estimation

**Gap:** The tool shows how expected loss changes. It does not estimate how premium would change. Premium is influenced by many factors beyond expected loss (expenses, profit load, market conditions, account relationship, regulatory constraints).

**What's needed:** This is intentional. The tool avoids making premium claims it cannot support. However, a future extension could estimate a loss-cost-based premium indication as a reference point, with appropriate caveats.

### 8.7 No temporal dynamics

**Gap:** The tool is static. It does not model how losses change over time due to climate trends, building aging, maintenance schedules, or code changes.

**What's needed:** Time-dependent loss projections incorporating climate scenarios and asset degradation would strengthen the case for upfront investment but require significantly more modeling infrastructure.

### 8.8 Validation

**Gap:** The tool has not been validated against real-world outcomes. Outputs are internally consistent (the math is correct given the inputs) but there is no empirical benchmark.

**What's needed:**
- Backtesting against historical claims data for a known building and known intervention
- Comparison of tool outputs against CAT model loss estimates for the same scenarios
- Peer review of methodology by actuaries or risk engineers

---

## 9. Intended users

| Audience | Use case |
|----------|----------|
| **Insurance brokers** | Quantify the insurance case for a client's mitigation investment. Show an underwriter how EAL and insured loss change. |
| **Underwriters** | Evaluate a risk reduction proposal's impact on expected loss and where savings fall relative to policy structure. |
| **Resilience program managers** | Demonstrate that physical investment translates into financial outcomes. Build the evidence base for incentive programs. |
| **Building owners / risk managers** | Understand how a roof upgrade or similar investment affects both their retained risk and their insured exposure. |
| **Reinsurers** | Assess how mitigation at the asset level affects ceded loss in excess-of-loss layers. |

---

## 10. Roadmap and development path

### Completed (current build)

- [x] Event-based loss distribution input (CSV upload)
- [x] Uniform scalar mitigation with failure + maintenance adjustments
- [x] Hazard-intensity-conditioned mitigation curves
- [x] Full policy mapping (deductible, limit, two modes)
- [x] EAL and EP curve computation and visualization
- [x] Reinsurance layer analysis (ELL, LOL, reduction)
- [x] Plain-language broker/underwriter summaries
- [x] Archetype presets for SME commercial buildings
- [x] Assumption provenance metadata
- [x] Sensitivity case metadata (low/base/high)
- [x] Model scope notes
- [x] Auto-load sample data and run on page load

### Near-term priorities

- [ ] Plug in real catastrophe model loss data for at least one geography and building type
- [ ] Replace illustrative mitigation assumptions with IBHS or manufacturer-backed data
- [ ] Add sensitivity analysis visualization (run low/base/high reduction scenarios and display range)
- [ ] Expand archetype library (more occupancy types, roof systems, regions)
- [ ] Add export functionality (PDF report, CSV download of results)

### Medium-term

- [ ] Multi-peril support (wind, flood)
- [ ] Component-level damage modeling (roof vs. envelope vs. interior)
- [ ] Premium indication module (loss-cost-based, with caveats)
- [ ] Coinsurance and sublimit support in policy engine
- [ ] Portfolio aggregation (multiple assets, spatial correlation)
- [ ] API-only mode for integration with third-party platforms

### Long-term

- [ ] Climate-adjusted loss projections (forward-looking scenarios)
- [ ] Building code effectiveness modeling
- [ ] Integration with catastrophe model APIs
- [ ] Empirical calibration against claims data
- [ ] Multi-stakeholder views (insurer vs. owner vs. lender)

---

## 11. Sample data — current defaults

### Event loss scenario (hail, SME commercial)

10 events from 2-year to 500-year return period. Hail diameters 1.00" to 4.00". Losses $4,200 to $680,000. Roof-damage-centric (not full-building catastrophic).

### Mitigation

Commercial roof upgrade (TPO to impact-resistant). Scalar mode, 35% base reduction, 5% failure, 10% maintenance = 29.9% effective. $45,000 intervention cost.

### Policy

$1,350,000 coverage limit. 2% deductible ($27,000). $8,500 annual premium. One reinsurance layer: $850,000 limit excess $500,000 attachment.

### Sample results with defaults

| Metric | Baseline EAL | Mitigated EAL | Annual Savings |
|--------|-------------|---------------|----------------|
| Gross loss | $25,830 | $18,100 | $7,730 (29.9%) |
| Insured loss | $14,993 | $9,378 | $5,615 (37.5%) |
| Uninsured / retained | $10,837 | $8,722 | $2,115 |

Note: Insured reduction (37.5%) exceeds gross reduction (29.9%) because avoided losses disproportionately fall within the insured layer (above the deductible).

---

## 12. Key formulas — quick reference

**Effective reduction (scalar):**
`eff = base × (1 - failure) × (1 - maintenance)`

**Effective reduction (curve):**
`eff_i = interp(intensity_i, curve) × (1 - failure) × (1 - maintenance)`

**Adjusted loss:**
`adjusted = gross × (1 - eff)`

**Insured loss (full policy):**
`insured = min(max(gross - deductible, 0), coverage_limit)`

**EAL:**
`EAL = Σ(probability_i × loss_i)`

**Reinsurance layer loss:**
`layer_loss = min(max(gross - attachment, 0), limit)`

**Expected Layer Loss:**
`ELL = Σ(probability_i × layer_loss_i)`

**Loss on Line:**
`LOL = ELL ÷ limit`

**Policy relevance ratio:**
`inside_pct = avoided_insured_EAL ÷ avoided_gross_EAL × 100`
