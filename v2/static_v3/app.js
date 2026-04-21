/**
 * Loss Distribution Translator v3 — Frontend
 * ────────────────────────────────────────────
 * Hail · SME Commercial Property · Roof Upgrade Demo
 *
 * Plain vanilla JS.  No build tools, no frameworks.
 * Based on v2 with SME-specific fields: archetype selector,
 * asset class, occupancy, roof system, mitigation mode toggle,
 * hazard-intensity curve input, provenance display.
 */

// ── API base URL ────────────────────────────────────────────────────────
const API_BASE = "";

// ── State ───────────────────────────────────────────────────────────────
let csvText = null;
let csvFileName = "";
let archetypes = [];  // loaded from /api/v3/archetypes

// ── DOM refs ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Utility ─────────────────────────────────────────────────────────────
function fmtUsd(v) {
  if (v == null) return "\u2014";
  if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toFixed(1) + "M";
  return "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtPct(v) {
  if (v == null) return "\u2014";
  return v.toFixed(1) + "%";
}

function b64encode(str) {
  return btoa(unescape(encodeURIComponent(str)));
}


// ═══════════════════════════════════════════════════════════════════════
//  UI interactions
// ═══════════════════════════════════════════════════════════════════════

// ── Archetype selector ─────────────────────────────────────────────────
$("archetype_selector").addEventListener("change", function () {
  const id = this.value;
  if (!id) return;  // "Custom" selected
  const arch = archetypes.find((a) => a.archetype_id === id);
  if (!arch) return;

  // Fill asset fields from archetype
  $("asset_name").value = arch.display_label || "";
  $("asset_class").value = arch.asset_class || "sme_commercial";
  $("occupancy_type").value = arch.occupancy_type || "small_warehouse";
  $("roof_system_type").value = arch.roof_system_type || "tpo";
  $("roof_age_years").value = arch.roof_age_years != null ? arch.roof_age_years : "";
  $("asset_value_usd").value = arch.asset_value_usd || "";

  // Update coverage limit to match asset value
  $("coverage_limit_usd").value = arch.asset_value_usd || "";
  updateDerivedDeductible();
});

// ── Mitigation mode toggle ─────────────────────────────────────────────
$("mitigation_mode").addEventListener("change", function () {
  const isScalar = this.value === "uniform_scalar";
  $("scalar_mode_fields").style.display = isScalar ? "block" : "none";
  $("curve_mode_fields").style.display = isScalar ? "none" : "block";
});

// ── Policy mode toggle ─────────────────────────────────────────────────
$("insured_share_mode").addEventListener("change", function () {
  const isFull = this.value === "full_policy_inputs";
  $("full_policy_fields").style.display = isFull ? "block" : "none";
  $("simple_share_fields").style.display = isFull ? "none" : "block";
});

// ── Deductible type toggle ─────────────────────────────────────────────
$("deductible_type").addEventListener("change", updateDeductibleFields);

function updateDeductibleFields() {
  const isFlat = $("deductible_type").value === "flat_usd";
  $("deductible_usd_group").style.display = isFlat ? "block" : "none";
  $("deductible_pct_group").style.display = isFlat ? "none" : "block";
  updateDerivedDeductible();
}

// ── Derived deductible ─────────────────────────────────────────────────
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

// ── Effective reduction (scalar mode) ──────────────────────────────────
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

// ── File upload ────────────────────────────────────────────────────────
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

// ── Load sample data ───────────────────────────────────────────────────
$("load_sample_btn").addEventListener("click", async () => {
  try {
    const resp = await fetch(API_BASE + "/api/v3/sample-data");
    const data = await resp.json();

    // Load CSV
    csvText = data.csv;
    csvFileName = "sample_hail_sme_scenario.csv";
    $("upload_area").classList.add("has-file");
    $("file_name").textContent = csvFileName;
    $("file_name").style.display = "block";
    $("upload_area").querySelector(".upload-text").style.display = "none";
    $("upload_area").querySelector(".upload-icon").style.display = "none";

    // Load archetypes into selector
    if (data.archetypes && data.archetypes.archetypes) {
      loadArchetypes(data.archetypes.archetypes);
    }

    // Load mitigation defaults
    const m = data.mitigation;
    $("intervention_name").value = m.intervention_name || "";
    $("mitigation_mode").value = m.mitigation_mode || "uniform_scalar";
    $("mitigation_mode").dispatchEvent(new Event("change"));
    $("base_loss_reduction_pct").value = (m.base_loss_reduction_pct * 100).toFixed(0);
    $("failure_probability").value = (m.failure_probability * 100).toFixed(0);
    $("maintenance_haircut_pct").value = (m.maintenance_haircut_pct * 100).toFixed(0);
    $("failure_probability_curve").value = (m.failure_probability * 100).toFixed(0);
    $("maintenance_haircut_curve").value = (m.maintenance_haircut_pct * 100).toFixed(0);
    $("intervention_cost_usd").value = m.intervention_cost_usd || "";

    // Load curve points if present
    if (m.curve_points && m.curve_points.length > 0) {
      const lines = m.curve_points.map(
        (p) => `${p.hazard_intensity}, ${p.reduction_pct}`
      );
      $("curve_points_input").value = lines.join("\n");
    }

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

    // Load reinsurance layers
    $("reins_layers").innerHTML = "";
    if (p.reinsurance_layers && p.reinsurance_layers.length > 0) {
      p.reinsurance_layers.forEach((l) => addReinsLayer(l.attach_usd, l.limit_usd));
    }

  } catch (e) {
    alert("Failed to load sample data: " + e.message);
  }
});

// ── Load archetypes into selector ──────────────────────────────────────
function loadArchetypes(list) {
  archetypes = list;
  const sel = $("archetype_selector");
  // Keep "Custom" as first option, clear the rest
  sel.innerHTML = '<option value="">-- Custom / No preset --</option>';
  list.forEach((a) => {
    const opt = document.createElement("option");
    opt.value = a.archetype_id;
    opt.textContent = a.display_label;
    sel.appendChild(opt);
  });
}

// ── FAQ toggle ─────────────────────────────────────────────────────────
$("faq_toggle").addEventListener("click", function () {
  const wrap = $("faq_wrap");
  const visible = wrap.classList.toggle("visible");
  this.innerHTML = (visible ? "&#9660;" : "&#9654;") + " Technical FAQ";
});

// ── Download sample CSV ────────────────────────────────────────────────
$("download_sample_btn").addEventListener("click", () => {
  window.location.href = API_BASE + "/api/v3/download-sample-csv";
});

// ── Event table toggle ─────────────────────────────────────────────────
$("toggle_event_table").addEventListener("click", function () {
  const wrap = $("event_table_wrap");
  const visible = wrap.classList.toggle("visible");
  this.innerHTML = (visible ? "&#9660;" : "&#9654;") + " " +
    (visible ? "Hide" : "Show") + " event-level detail";
});


// ── Reinsurance layer inputs ───────────────────────────────────────────
let reinsLayerId = 0;

function addReinsLayer(attach = "", limit = "") {
  const id = reinsLayerId++;
  const row = document.createElement("div");
  row.className = "reins-row";
  row.id = `reins_row_${id}`;
  row.innerHTML = `
    <input type="number" placeholder="Attachment ($)" class="reins-attach" value="${attach}" min="0" step="1000" />
    <input type="number" placeholder="Limit ($)" class="reins-limit" value="${limit}" min="0" step="1000" />
    <button type="button" class="btn-sm btn-ghost reins-remove" data-id="${id}">&times;</button>
  `;
  $("reins_layers").appendChild(row);
  row.querySelector(".reins-remove").addEventListener("click", () => row.remove());
}

$("add_reins_layer").addEventListener("click", () => addReinsLayer());

function getReinsLayers() {
  const rows = $("reins_layers").querySelectorAll(".reins-row");
  const layers = [];
  rows.forEach((row) => {
    const a = parseFloat(row.querySelector(".reins-attach").value);
    const l = parseFloat(row.querySelector(".reins-limit").value);
    if (a >= 0 && l > 0) layers.push({ attach_usd: a, limit_usd: l });
  });
  return layers.length > 0 ? layers : null;
}


// ── Parse curve points from textarea ───────────────────────────────────
function parseCurvePoints() {
  const raw = $("curve_points_input").value.trim();
  if (!raw) return null;

  const points = [];
  const lines = raw.split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("hazard")) continue;
    const parts = trimmed.split(/[,\t]+/);
    if (parts.length >= 2) {
      const intensity = parseFloat(parts[0]);
      const reduction = parseFloat(parts[1]);
      if (!isNaN(intensity) && !isNaN(reduction)) {
        points.push({ hazard_intensity: intensity, reduction_pct: reduction });
      }
    }
  }
  return points.length >= 2 ? points : null;
}


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
  const isCurveMode = $("mitigation_mode").value === "hazard_intensity_curve";

  // Parse future_asset_layers
  const layersRaw = $("future_asset_layers").value.trim();
  const futureAssetLayers = layersRaw
    ? layersRaw.split(",").map((s) => s.trim()).filter(Boolean)
    : null;

  // Build intervention payload
  const intervention = {
    intervention_name: $("intervention_name").value,
    mitigation_mode: $("mitigation_mode").value,
    intervention_cost_usd: parseFloat($("intervention_cost_usd").value) || null,
  };

  if (isCurveMode) {
    // Curve mode: use curve-specific failure/maint fields
    intervention.base_loss_reduction_pct = 0;  // Not used in curve mode
    intervention.failure_probability = (parseFloat($("failure_probability_curve").value) || 0) / 100;
    intervention.maintenance_haircut_pct = (parseFloat($("maintenance_haircut_curve").value) || 0) / 100;
    intervention.curve_points = parseCurvePoints();
    if (!intervention.curve_points) {
      $("errors_area").innerHTML =
        '<div class="alert alert-error">Curve mode requires at least 2 valid curve points (intensity, reduction).</div>';
      btn.disabled = false;
      btn.textContent = "Run Analysis";
      return;
    }
  } else {
    // Scalar mode
    intervention.base_loss_reduction_pct = (parseFloat($("base_loss_reduction_pct").value) || 0) / 100;
    intervention.failure_probability = (parseFloat($("failure_probability").value) || 0) / 100;
    intervention.maintenance_haircut_pct = (parseFloat($("maintenance_haircut_pct").value) || 0) / 100;
    intervention.curve_points = null;
  }

  const payload = {
    events_csv_b64: b64encode(csvText),
    asset: {
      asset_name: $("asset_name").value,
      asset_class: $("asset_class").value,
      occupancy_type: $("occupancy_type").value,
      asset_value_usd: parseFloat($("asset_value_usd").value) || 0,
      location_name: $("location_name").value,
      roof_system_type: $("roof_system_type").value,
      roof_age_years: parseInt($("roof_age_years").value) || null,
      hazard_share_pct: hazardShare,
      future_asset_layers: futureAssetLayers,
      archetype_id: $("archetype_selector").value || null,
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
      reinsurance_layers: getReinsLayers(),
    },
    intervention: intervention,
    apply_asset_cap: $("apply_asset_cap").checked,
  };

  try {
    const resp = await fetch(API_BASE + "/api/v3/analyze", {
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

  // ── Broker summary ──────────────────────────────────────────────────
  $("broker_summary_text").textContent = data.broker_summary;

  // ── Model scope note ────────────────────────────────────────────────
  if (data.model_scope_note) {
    $("card_scope").style.display = "block";
    $("model_scope_text").textContent = data.model_scope_note;
  } else {
    $("card_scope").style.display = "none";
  }

  // ── Consolidated metrics table ──────────────────────────────────────
  $("metrics_table_body").innerHTML = `
    <tr class="row-highlight">
      <td class="row-label">Insured Loss</td>
      <td>${fmtUsd(m.baseline_insured_eal_usd)}</td>
      <td>${fmtUsd(m.adjusted_insured_eal_usd)}</td>
      <td class="delta-good">${fmtUsd(m.avoided_insured_eal_usd)} <span class="tbl-sub">(${fmtPct(m.insured_reduction_pct)})</span></td>
    </tr>
    <tr>
      <td class="row-label">Gross Loss</td>
      <td>${fmtUsd(m.baseline_gross_eal_usd)}</td>
      <td>${fmtUsd(m.adjusted_gross_eal_usd)}</td>
      <td class="delta-good">${fmtUsd(m.avoided_gross_eal_usd)} <span class="tbl-sub">(${fmtPct(m.hazard_specific_reduction_pct)})</span></td>
    </tr>
    <tr>
      <td class="row-label">Uninsured / Retained</td>
      <td>${fmtUsd(m.baseline_uninsured_eal_usd)}</td>
      <td>${fmtUsd(m.adjusted_uninsured_eal_usd)}</td>
      <td class="${m.avoided_uninsured_eal_usd >= 0 ? 'delta-good' : 'delta-neutral'}">${fmtUsd(m.avoided_uninsured_eal_usd)}</td>
    </tr>`;

  // ── Policy relevance ────────────────────────────────────────────────
  $("policy_relevance_text").textContent = data.policy_relevance_note;

  // ── Reinsurance layer results ───────────────────────────────────────
  if (data.reinsurance_layers && data.reinsurance_layers.length > 0) {
    $("card_reinsurance").style.display = "block";
    $("reins_table_body").innerHTML = data.reinsurance_layers.map((l) => {
      const label = fmtUsd(l.limit_usd) + " xs " + fmtUsd(l.attach_usd);
      return `<tr>
        <td class="row-label">${label}</td>
        <td>${fmtUsd(l.baseline_ell_usd)}</td>
        <td>${fmtUsd(l.mitigated_ell_usd)}</td>
        <td class="delta-good">${fmtPct(l.ell_reduction_pct)}</td>
        <td>${fmtPct(l.baseline_lol_pct)}</td>
        <td>${fmtPct(l.mitigated_lol_pct)}</td>
      </tr>`;
    }).join("");
  } else {
    $("card_reinsurance").style.display = "none";
  }

  // ── Assumption provenance ───────────────────────────────────────────
  if (data.assumption_provenance) {
    const prov = data.assumption_provenance;
    $("card_provenance").style.display = "block";
    let html = '<div class="provenance-grid">';
    if (prov.source_type) {
      html += `<span class="prov-label">Source</span><span class="prov-value">${prov.source_type.replace(/_/g, " ")}</span>`;
    }
    if (prov.confidence_level) {
      html += `<span class="prov-label">Confidence</span><span class="prov-value">${prov.confidence_level}</span>`;
    }
    if (prov.citation_note) {
      html += `<span class="prov-label">Citation</span><span class="prov-value">${prov.citation_note}</span>`;
    }
    if (prov.notes) {
      html += `<span class="prov-label">Notes</span><span class="prov-value">${prov.notes}</span>`;
    }
    html += "</div>";
    $("provenance_content").innerHTML = html;
  } else {
    $("card_provenance").style.display = "none";
  }

  // ── EP curves ───────────────────────────────────────────────────────
  renderEpChart("chart_gross_ep", m.ep_curves.gross_baseline, m.ep_curves.gross_adjusted, "Gross Loss");
  renderEpChart("chart_insured_ep", m.ep_curves.insured_baseline, m.ep_curves.insured_adjusted, "Insured Loss");

  // ── Event table ─────────────────────────────────────────────────────
  renderEventTable(data.event_table, data.mitigation_mode);

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
    margin: { t: 10, r: 15, b: 45, l: 60 },
    xaxis: {
      title: { text: "Exceedance Probability", font: { size: 10 } },
      type: "log",
      autorange: true,
      gridcolor: "#eee",
      automargin: true,
      tickvals: [0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5],
      ticktext: ["0.2%", "0.5%", "1%", "2%", "5%", "10%", "20%", "50%"],
    },
    yaxis: {
      title: { text: title + " ($)", font: { size: 10 } },
      tickprefix: "$",
      gridcolor: "#eee",
      automargin: true,
    },
    legend: { x: 0.95, y: 0.85, xanchor: "right", yanchor: "top", bgcolor: "rgba(255,255,255,0.85)", bordercolor: "#e0e3e8", borderwidth: 1, font: { size: 9 } },
    font: { family: "-apple-system, BlinkMacSystemFont, sans-serif", size: 10 },
    plot_bgcolor: "#fff",
    paper_bgcolor: "#fff",
  };
  const el = document.getElementById(elId);
  Plotly.newPlot(el, [traceBase, traceAdj], layout, { responsive: true }).then(() => {
    Plotly.Plots.resize(el);
  });
}


function renderEventTable(events, mitigationMode) {
  if (!events || events.length === 0) return;

  const columns = [
    { key: "event_id", label: "Event" },
    { key: "return_period", label: "Return Period" },
    { key: "hazard_intensity", label: "Hail Size (in)" },
    { key: "gross_loss_usd", label: "Gross Loss", fmt: fmtUsd },
    { key: "adjusted_gross_loss_usd", label: "Adj. Gross", fmt: fmtUsd },
    { key: "avoided_gross_loss_usd", label: "Avoided Gross", fmt: fmtUsd },
  ];

  // Add per-event reduction columns if curve mode
  if (mitigationMode === "hazard_intensity_curve") {
    columns.push(
      { key: "raw_reduction_pct", label: "Raw Red. %", fmt: (v) => v != null ? (v * 100).toFixed(1) + "%" : "\u2014" },
      { key: "effective_reduction_pct", label: "Eff. Red. %", fmt: (v) => v != null ? (v * 100).toFixed(1) + "%" : "\u2014" },
    );
  }

  columns.push(
    { key: "baseline_insured_loss_usd", label: "Insured Loss", fmt: fmtUsd },
    { key: "adjusted_insured_loss_usd", label: "Adj. Insured", fmt: fmtUsd },
    { key: "avoided_insured_loss_usd", label: "Avoided Insured", fmt: fmtUsd },
  );

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


// ── Init ───────────────────────────────────────────────────────────────
updateDeductibleFields();
updateEffectiveReduction();

// Load archetypes on page load
(async function loadArchetypesOnInit() {
  try {
    const resp = await fetch(API_BASE + "/api/v3/archetypes");
    const data = await resp.json();
    if (data && data.archetypes) {
      loadArchetypes(data.archetypes);
    }
  } catch (e) {
    console.warn("Failed to load archetypes:", e);
  }
})();

// Auto-load sample scenario and run analysis on page load
(async function autoLoad() {
  try {
    const resp = await fetch(API_BASE + "/api/v3/sample-data");
    const data = await resp.json();

    csvText = data.csv;
    csvFileName = "sample_hail_sme_scenario.csv";
    $("upload_area").classList.add("has-file");
    $("file_name").textContent = csvFileName;
    $("file_name").style.display = "block";
    $("upload_area").querySelector(".upload-text").style.display = "none";
    $("upload_area").querySelector(".upload-icon").style.display = "none";

    // Load archetypes
    if (data.archetypes && data.archetypes.archetypes) {
      loadArchetypes(data.archetypes.archetypes);
    }

    // Load mitigation
    const m = data.mitigation;
    $("intervention_name").value = m.intervention_name || "";
    $("mitigation_mode").value = m.mitigation_mode || "uniform_scalar";
    $("mitigation_mode").dispatchEvent(new Event("change"));
    $("base_loss_reduction_pct").value = (m.base_loss_reduction_pct * 100).toFixed(0);
    $("failure_probability").value = (m.failure_probability * 100).toFixed(0);
    $("maintenance_haircut_pct").value = (m.maintenance_haircut_pct * 100).toFixed(0);
    $("failure_probability_curve").value = (m.failure_probability * 100).toFixed(0);
    $("maintenance_haircut_curve").value = (m.maintenance_haircut_pct * 100).toFixed(0);
    $("intervention_cost_usd").value = m.intervention_cost_usd || "";
    updateEffectiveReduction();

    // Load policy
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

    // Load reinsurance layers
    $("reins_layers").innerHTML = "";
    if (p.reinsurance_layers && p.reinsurance_layers.length > 0) {
      p.reinsurance_layers.forEach((l) => addReinsLayer(l.attach_usd, l.limit_usd));
    }

    // Auto-run analysis
    await runAnalysis();
  } catch (e) {
    console.warn("Auto-load failed:", e);
  }
})();
