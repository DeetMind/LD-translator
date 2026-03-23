# Loss Distribution Translator

A local prototype that translates a physical flood mitigation intervention into insurance-relevant metrics.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

Open **http://127.0.0.1:8000** in your browser.

## Usage

1. Click **"Load Sample Scenario"** to pre-fill all inputs with the bundled example data, OR upload your own CSV.
2. Adjust mitigation parameters and insurance structure as needed.
3. Click **"Run Analysis"**.
4. Export results via **"Export Event CSV"** or **"Export Summary JSON"**.

## Required CSV columns

| Column | Type | Description |
|---|---|---|
| `event_id` | string | Unique event identifier |
| `annual_probability` | float | Annual frequency of occurrence (e.g. 0.01 for 1-in-100) |
| `return_period` | int | Return period in years |
| `flood_depth_ft` | float | Peak flood depth at the site in feet |
| `gross_loss_usd` | float | Unmitigated loss in USD |

See `sample_data/example_events.csv` for a 10-event example.

## Sample data files

| File | Description |
|---|---|
| `sample_data/example_events.csv` | 10-event loss table spanning 2-yr to 1000-yr return periods |
| `sample_data/sample_mitigation.json` | Riverside Flood Barrier Phase 1 parameters |
| `sample_data/sample_insurance.json` | Example insurance structure with 3 reinsurance layers |

## Mitigation logic (summary)

```
# Depth-conditional reduction
if flood_depth <= design_height:
    adjusted_loss = gross_loss * (1 - protected_loss_reduction_pct)
else:
    adjusted_loss = gross_loss * (1 - overtop_loss_reduction_pct)

# Failure probability blend
effective_loss = (1 - failure_prob) * adjusted_loss + failure_prob * gross_loss

# Maintenance haircut
benefit        = gross_loss - effective_loss
haircut_benefit = benefit * (1 - maintenance_haircut_pct)
final_loss     = gross_loss - haircut_benefit
```

## Metrics computed

- **EAL** — Expected Annual Loss
- **EP curve** — Exceedance Probability curve (baseline vs mitigated)
- **PML** — Probable Maximum Loss at 1-in-100 and 1-in-250 return periods
- **Attachment probabilities** — per attachment point
- **Expected layer loss** — per reinsurance layer, with loss-on-line %
- **Capital threshold exceedance** — probability of exceeding each threshold
