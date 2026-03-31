/**
 * Loss Distribution Translator v2 — Frontend
 * ────────────────────────────────────────────
 * Hail · Residential Property · Roof Upgrade Demo
 *
 * Plain vanilla JS.  No build tools, no frameworks.
 * Designed to be served statically and call the FastAPI backend.
 */

// ── API base URL ────────────────────────────────────────────────────────
// When served by FastAPI this is same-origin.
// For future Vercel deployment, change to the backend URL.
const API_BASE = "";

// ── State ───────────────────────────────────────────────────────────────
let csvText = null;   // raw CSV string (from upload or sample)
let csvFileName = ""; // display name

// ── DOM refs ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Utility ─────────────────────────────────────────────────────────────
function fmtUsd(v) {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toFixed(1) + "M";
  return "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtPct(v) {
  if (v == null) return "—";
  return v.toFixed(1) + "%";
}

function b64encode(str) {
  return btoa(unescape(encodeURIComponent(str)));
}


// ═══════════════════════════════════════════════════════════════════════
//  UI interactions
// ═══════════════════════════════════════════════════════════════════════

// ── Policy mode toggle ──────────────────────────────────────────────────
$("insured_share_mode").addEventListener("change", function () {
  const isFull = this.value === "full_policy_inputs";
  $("full_policy_fields").style.display = isFull ? "block" : "none";
  $("simple_share_fields").style.display = isFull ? "none" : "block";
});

// ── Deductible type toggle ──────────────────────────────────────────────
$("deductible_type").addEventListener("change", updateDeductibleFields);

function updateDeductibleFields() {
  const isFlat = $("deductible_type").value === "flat_usd";
  $("deductible_usd_group").style.display = isFlat ? "block" : "none";
  $("deductible_pct_group").style.display = isFlat ? "none" : "block";
  updateDerivedDeductible();
}

// ── Derived deductible ──────────────────────────────────────────────────
function updateDerivedDeductible() {
  const isFlat = $("deductible_type").value === "flat_usd";
  let ded;
  if (isFlat) {
    ded = parseFloat($("deductible_usd").value) || 0;
  } else {
    const pct = (parseFloat($("deductible_pct").value) || 0) / 100;
    const limit = parseFloat($("coverage_limit_usd").value) || 0;
    ded = limit * pct;
  }
  $("derived_deductible").textContent = fmtUsd(ded);
}

$("deductible_usd").addEventListener("input", updateDerivedDeductible);
$("deductible_pct").addEventListener("input", updateDerivedDeductible);
$("coverage_limit_usd").addEventListener("input", updateDerivedDeductible);

// ── Effective reduction ─────────────────────────────────────────────────
function updateEffectiveReduction() {
  const base = (parseFloat($("base_loss_reduction_pct").value) || 0) / 100;
  const fail = (parseFloat($("failure_probability").value) || 0) / 100;
  const maint = (parseFloat($("maintenance_haircut_pct").value) || 0) / 100;
  const eff = base * (1 - fail) * (1 - maint);
  $("effective_reduction_value").textContent = fmtPct(eff * 100);
}

$("base_loss_reduction_pct").addEventListener("input", updateEffectiveReduction);
$("failure_probability").addEventListener("input", updateEffectiveReduction);
$("maintenance_haircut_pct").addEventListener("input", updateEffectiveReduction);

// ── File upload ─────────────────────────────────────────────────────────
$("upload_area").addEventListener("click", () => $("csv_file").click());

$("upload_area").addEventListener("dragover", (e) => {
  e.preventDefault();
  $("upload_area").classList.add("has-file");
});

$("upload_area").addEventListener("dragleave", () => {
  if (!csvText) $("upload_area").classList.remove("has-file");
});

$("upload_area").addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

$("csv_file").addEventListener("change", function () {
  if (this.files[0]) handleFile(this.files[0]);
});

function handleFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    csvText = e.target.result;
    csvFileName = file.name;
    $("upload_area").classList.add("has-file");
    $("file_name").textContent = file.name;
    $("file_name").style.display = "block";
    $("upload_area").querySelector(".upload-text").style.display = "none";
    $("upload_area").querySelector(".upload-icon").style.display = "none";
  };
  reader.readAsText(file);
}

// ── Load sample data ────────────────────────────────────────────────────
$("load_sample_btn").addEventListener("click", async () => {
  try {
    const resp = await fetch(API_BASE + "/api/v2/sample-data");
    const data = await resp.json();

    // Load CSV
    csvText = data.csv;
    csvFileName = "sample_hail_scenario.csv";
    $("upload_area").classList.add("has-file");
    $("file_name").textContent = csvFileName;
    $("file_name").style.display = "block";
    $("upload_area").querySelector(".upload-text").style.display = "none";
    $("upload_area").querySelector(".upload-icon").style.display = "none";

    // Load mitigation defaults
    const m = data.mitigation;
    $("intervention_name").value = m.intervention_name || "";
    $("base_loss_reduction_pct").value = (m.base_loss_reduction_pct * 100).toFixed(0);
    $("failure_probability").value = (m.failure_probability * 100).toFixed(0);
    $("maintenance_haircut_pct").value = (m.maintenance_haircut_pct * 100).toFixed(0);
    $("intervention_cost_usd").value = m.intervention_cost_usd || "";
    updateEffectiveReduction();

    // Load policy defaults
    const p = data.policy;
    $("coverage_limit_usd").value = p.coverage_limit_usd || "";
    $("insured_share_mode").value = p.insured_share_mode || "full_policy_inputs";
    $("insured_share_mode").dispatchEvent(new Event("change"));
    $("deductible_type").value = p.deductible_type || "percent_of_coverage";
    updateDeductibleFields();
    if (p.deductible_type === "flat_usd") {
      $("deductible_usd").value = p.deductible_usd || "";
    } else {
      $("deductible_pct").value = ((p.deductible_pct || 0) * 100).toFixed(0);
    }
    $("coinsurance_pct").value = ((p.coinsurance_pct || 1) * 100).toFixed(0);
    $("premium_usd_current").value = p.premium_usd_current || "";
    updateDerivedDeductible();

  } catch (e) {
    alert("Failed to load sample data: " + e.message);
  }
});

// ── FAQ toggle ──────────────────────────────────────────────────────────
$("faq_toggle").addEventListener("click", function () {
  const wrap = $("faq_wrap");
  const visible = wrap.classList.toggle("visible");
  this.innerHTML = (visible ? "&#9660;" : "&#9654;") + " Technical FAQ";
});

// ── Download sample CSV ─────────────────────────────────────────────────
$("download_sample_btn").addEventListener("click", () => {
  window.location.href = API_BASE + "/api/v2/download-sample-csv";
});

// ── Event table toggle ──────────────────────────────────────────────────
$("toggle_event_table").addEventListener("click", function () {
  const wrap = $("event_table_wrap");
  const visible = wrap.classList.toggle("visible");
  this.innerHTML = (visible ? "&#9660;" : "&#9654;") + " " +
    (visible ? "Hide" : "Show") + " event-level detail";
});


// ═══════════════════════════════════════════════════════════════════════
//  Run analysis
// ═══════════════════════════════════════════════════════════════════════

$("run_btn").addEventListener("click", runAnalysis);

async function runAnalysis() {
  // Clear previous
  $("warnings_area").innerHTML = "";
  $("errors_area").innerHTML = "";
  $("results_area").classList.remove("visible");

  if (!csvText) {
    $("errors_area").innerHTML =
      '<div class="alert alert-error">Please upload an event-loss CSV or load the sample scenario.</div>';
    return;
  }

  const btn = $("run_btn");
  btn.disabled = true;
  btn.textContent = "Running...";

  // Gather inputs
  const hazardShareRaw = parseFloat($("hazard_share_pct").value);
  const hazardShare = (hazardShareRaw > 0 && hazardShareRaw <= 100)
    ? hazardShareRaw / 100 : null;

  const isFullPolicy = $("insured_share_mode").value === "full_policy_inputs";
  const isFlat = $("deductible_type").value === "flat_usd";

  const payload = {
    events_csv_b64: b64encode(csvText),
    asset: {
      asset_name: $("asset_name").value,
      asset_value_usd: parseFloat($("asset_value_usd").value) || 0,
      location_name: $("location_name").value,
      hazard_share_pct: hazardShare,
    },
    policy: {
      coverage_limit_usd: parseFloat($("coverage_limit_usd").value) || 0,
      deductible_type: $("deductible_type").value,
      deductible_usd: isFlat ? (parseFloat($("deductible_usd").value) || 0) : null,
      deductible_pct: !isFlat ? (parseFloat($("deductible_pct").value) || 0) / 100 : null,
      insured_share_mode: $("insured_share_mode").value,
      insured_share_pct: !isFullPolicy ? (parseFloat($("insured_share_pct").value) || 0) / 100 : null,
      coinsurance_pct: (parseFloat($("coinsurance_pct").value) || 100) / 100,
      premium_usd_current: parseFloat($("premium_usd_current").value) || null,
    },
    intervention: {
      intervention_name: $("intervention_name").value,
      base_loss_reduction_pct: (parseFloat($("base_loss_reduction_pct").value) || 0) / 100,
      failure_probability: (parseFloat($("failure_probability").value) || 0) / 100,
      maintenance_haircut_pct: (parseFloat($("maintenance_haircut_pct").value) || 0) / 100,
      intervention_cost_usd: parseFloat($("intervention_cost_usd").value) || null,
    },
    apply_asset_cap: $("apply_asset_cap").checked,
  };

  try {
    const resp = await fetch(API_BASE + "/api/v2/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await resp.json();

    if (!resp.ok) {
      const msgs = data.errors || [data.detail || "Unknown error"];
      $("errors_area").innerHTML = msgs
        .map((m) => `<div class="alert alert-error">${m}</div>`)
        .join("");

      if (data.warnings && data.warnings.length) {
        $("warnings_area").innerHTML = data.warnings
          .map((m) => `<div class="alert alert-warning">${m}</div>`)
          .join("");
      }
      return;
    }

    // Show warnings
    if (data.warnings && data.warnings.length) {
      $("warnings_area").innerHTML = data.warnings
        .map((m) => `<div class="alert alert-warning">${m}</div>`)
        .join("");
    }

    renderResults(data);

  } catch (e) {
    $("errors_area").innerHTML =
      `<div class="alert alert-error">Request failed: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Analysis";
  }
}


// ═══════════════════════════════════════════════════════════════════════
//  Render results
// ═══════════════════════════════════════════════════════════════════════

function renderResults(data) {
  const m = data.metrics;

  // ── Card 1 — Broker summary ──────────────────────────────────────────
  $("broker_summary_text").textContent = data.broker_summary;

  // ── Card 2 — Insurance effect ────────────────────────────────────────
  $("insurance_kpis").innerHTML = kpiRow([
    { label: "Baseline Insured EAL", value: fmtUsd(m.baseline_insured_eal_usd) },
    { label: "Adjusted Insured EAL", value: fmtUsd(m.adjusted_insured_eal_usd) },
    {
      label: "Avoided Insured Loss",
      value: fmtUsd(m.avoided_insured_eal_usd),
      sub: fmtPct(m.insured_reduction_pct) + " reduction",
      delta: "good",
    },
  ]);

  // ── Card 3 — Physical effect ─────────────────────────────────────────
  $("physical_kpis").innerHTML = kpiRow([
    { label: "Baseline Gross EAL", value: fmtUsd(m.baseline_gross_eal_usd) },
    { label: "Adjusted Gross EAL", value: fmtUsd(m.adjusted_gross_eal_usd) },
    {
      label: "Avoided Gross Loss",
      value: fmtUsd(m.avoided_gross_eal_usd),
      sub: fmtPct(m.hazard_specific_reduction_pct) + " reduction",
      delta: "good",
    },
  ]);

  // ── Card 4 — Uninsured / retained ───────────────────────────────────
  $("uninsured_kpis").innerHTML = kpiRow([
    { label: "Baseline Uninsured EAL", value: fmtUsd(m.baseline_uninsured_eal_usd) },
    { label: "Adjusted Uninsured EAL", value: fmtUsd(m.adjusted_uninsured_eal_usd) },
    {
      label: "Change in Uninsured EAL",
      value: fmtUsd(m.avoided_uninsured_eal_usd),
      delta: m.avoided_uninsured_eal_usd >= 0 ? "good" : "neutral",
    },
  ]);

  // ── Card 5 — Policy relevance ───────────────────────────────────────
  $("policy_relevance_text").textContent = data.policy_relevance_note;

  // ── Card 6 — EP curves ──────────────────────────────────────────────
  renderEpChart("chart_gross_ep", m.ep_curves.gross_baseline, m.ep_curves.gross_adjusted, "Gross Loss");
  renderEpChart("chart_insured_ep", m.ep_curves.insured_baseline, m.ep_curves.insured_adjusted, "Insured Loss");

  // ── Card 7 — Event table ────────────────────────────────────────────
  renderEventTable(data.event_table);

  // ── Cap notice ──────────────────────────────────────────────────────
  $("cap_notice").style.display = data.was_capped_by_asset_value ? "block" : "none";

  // Show results, hide placeholder
  $("results_area").classList.add("visible");
  if ($("results_placeholder")) $("results_placeholder").style.display = "none";
  $("results_area").scrollIntoView({ behavior: "smooth", block: "start" });
}


// ═══════════════════════════════════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════════════════════════════════

function kpiRow(items) {
  return items.map((item) => {
    const deltaClass = item.delta ? `delta-${item.delta}` : "";
    const sub = item.sub ? `<div class="kpi-sub ${deltaClass}">${item.sub}</div>` : "";
    return `
      <div class="kpi">
        <div class="kpi-label">${item.label}</div>
        <div class="kpi-value ${deltaClass}">${item.value}</div>
        ${sub}
      </div>`;
  }).join("");
}


function renderEpChart(elId, baseline, adjusted, title) {
  const traceBase = {
    x: baseline.exceedance_probability,
    y: baseline.loss_usd,
    mode: "lines+markers",
    name: "Baseline",
    line: { color: "#e02424", width: 2 },
    marker: { size: 5 },
  };
  const traceAdj = {
    x: adjusted.exceedance_probability,
    y: adjusted.loss_usd,
    mode: "lines+markers",
    name: "Mitigated",
    line: { color: "#1a56db", width: 2 },
    marker: { size: 5 },
  };
  const layout = {
    margin: { t: 10, r: 20, b: 50, l: 70 },
    xaxis: {
      title: "Exceedance Probability",
      type: "log",
      autorange: true,
      gridcolor: "#eee",
    },
    yaxis: {
      title: title + " ($)",
      tickprefix: "$",
      gridcolor: "#eee",
    },
    legend: { x: 0.01, y: 0.99, bgcolor: "rgba(255,255,255,0.8)" },
    font: { family: "-apple-system, BlinkMacSystemFont, sans-serif", size: 11 },
    plot_bgcolor: "#fff",
    paper_bgcolor: "#fff",
  };
  Plotly.newPlot(elId, [traceBase, traceAdj], layout, { responsive: true });
}


function renderEventTable(events) {
  if (!events || events.length === 0) return;

  const columns = [
    { key: "event_id", label: "Event" },
    { key: "return_period", label: "Return Period" },
    { key: "hazard_intensity", label: "Hail Size (in)" },
    { key: "gross_loss_usd", label: "Gross Loss", fmt: fmtUsd },
    { key: "adjusted_gross_loss_usd", label: "Adj. Gross", fmt: fmtUsd },
    { key: "avoided_gross_loss_usd", label: "Avoided Gross", fmt: fmtUsd },
    { key: "baseline_insured_loss_usd", label: "Insured Loss", fmt: fmtUsd },
    { key: "adjusted_insured_loss_usd", label: "Adj. Insured", fmt: fmtUsd },
    { key: "avoided_insured_loss_usd", label: "Avoided Insured", fmt: fmtUsd },
  ];

  $("event_table_head").innerHTML = "<tr>" +
    columns.map((c) => `<th>${c.label}</th>`).join("") + "</tr>";

  $("event_table_body").innerHTML = events.map((row) => {
    return "<tr>" + columns.map((c) => {
      const val = row[c.key];
      const display = c.fmt ? c.fmt(val) : val;
      return `<td>${display}</td>`;
    }).join("") + "</tr>";
  }).join("");
}


// ── Init ────────────────────────────────────────────────────────────────
updateDeductibleFields();
updateEffectiveReduction();
