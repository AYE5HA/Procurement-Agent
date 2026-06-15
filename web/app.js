const config = window.PROCUREMENT_AGENT_CONFIG || {};
const state = {
  apiBaseUrl: sessionStorage.getItem("apiBaseUrl") || config.apiBaseUrl || "",
  apiToken: sessionStorage.getItem("apiToken") || "",
  result: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const elements = {
  text: $("#contractText"),
  file: $("#contractFile"),
  uploadZone: $("#uploadZone"),
  count: $("#characterCount"),
  analyze: $("#analyzeButton"),
  clear: $("#clearButton"),
  sample: $("#sampleButton"),
  empty: $("#emptyResult"),
  loading: $("#loadingResult"),
  error: $("#errorResult"),
  results: $("#results"),
  errorMessage: $("#errorMessage"),
  retry: $("#retryButton"),
  status: $("#systemStatus"),
  analysisId: $("#analysisId"),
  settings: $("#settingsDialog"),
  apiUrl: $("#apiUrlInput"),
  apiToken: $("#apiTokenInput"),
  toast: $("#toast"),
};

const sampleContract = `PROCUREMENT SERVICES AGREEMENT

1. SERVICES
Supplier will provide implementation and managed support services described in each statement of work.

2. PAYMENT
Buyer will pay undisputed invoices within thirty days.

3. LIABILITY
Supplier's liability shall be unlimited for any breach, claim, loss, or failure arising from this Agreement.

4. INTELLECTUAL PROPERTY
Supplier retains ownership of its pre-existing materials. Buyer receives a limited license to use deliverables.

5. TERM
This Agreement remains effective for twelve months and renews by mutual written agreement.`;

function setView(view) {
  [elements.empty, elements.loading, elements.error, elements.results].forEach((element) => {
    element.classList.add("hidden");
  });
  elements[view].classList.remove("hidden");
}

function updateCount() {
  const count = elements.text.value.length;
  elements.count.textContent = `${count.toLocaleString()} characters`;
}

function activateTabs(buttons, paneSuffix) {
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const key = button.dataset.tab || button.dataset.result;
      const pane = paneSuffix === "Pane" ? `#${key}Pane` : `#${key}Result`;
      $$(paneSuffix === "Pane" ? ".tab-pane" : ".result-pane").forEach((item) => {
        item.classList.remove("active");
      });
      $(pane).classList.add("active");
    });
  });
}

async function checkHealth() {
  if (!state.apiBaseUrl) {
    setServiceStatus("offline", "API not configured");
    return;
  }
  try {
    const response = await fetch(`${state.apiBaseUrl.replace(/\/$/, "")}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error("Unavailable");
    setServiceStatus("online", "Service operational");
  } catch {
    setServiceStatus("offline", "Service unavailable");
  }
}

function setServiceStatus(className, label) {
  elements.status.className = `system-status ${className}`;
  elements.status.querySelector("span:last-child").textContent = label;
}

async function analyze() {
  const contractText = elements.text.value.trim();
  if (contractText.length < 100) {
    showToast("Enter at least 100 characters of contract text.");
    elements.text.focus();
    return;
  }
  if (!state.apiBaseUrl) {
    openSettings();
    showToast("Configure the deployed API before analysis.");
    return;
  }

  setView("loading");
  elements.analyze.disabled = true;
  elements.analysisId.textContent = "Processing";
  animateProcessing();

  try {
    const headers = { "Content-Type": "application/json" };
    if (state.apiToken) headers.Authorization = `Bearer ${state.apiToken}`;
    const response = await fetch(
      `${state.apiBaseUrl.replace(/\/$/, "")}/api/v1/analyses`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ contract_text: contractText }),
      },
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed with status ${response.status}`);
    }
    state.result = payload;
    renderResults(payload);
    setView("results");
  } catch (error) {
    elements.errorMessage.textContent = error.message;
    elements.analysisId.textContent = "Request failed";
    setView("error");
  } finally {
    elements.analyze.disabled = false;
  }
}

function animateProcessing() {
  const steps = $$(".processing-step");
  steps.forEach((step, index) => {
    step.classList.toggle("active", index < 2);
    if (index >= 2) {
      setTimeout(() => step.classList.add("active"), 900 + index * 650);
    }
  });
}

function renderResults(result) {
  const score = Math.round(result.overall_risk_score);
  $("#riskScore").textContent = score;
  const risk = score >= 75 ? "Material exposure identified" : score >= 45 ? "Negotiation required" : "Limited exposure";
  $("#riskLabel").textContent = risk;
  $("#riskHeadline").textContent = `${result.liability_findings.length + result.indemnity_findings.length} contractual gaps resolved`;
  $("#riskSummary").textContent = "Corrected language is available for legal review.";
  elements.analysisId.textContent = `ID ${result.contract_id.slice(0, 8).toUpperCase()}`;

  renderFindingGroup("liabilityFindings", result.liability_findings, "business_impact");
  renderFindingGroup("indemnityFindings", result.indemnity_findings, "third_party_exposure");
  $("#liabilityCount").textContent = countLabel(result.liability_findings.length);
  $("#indemnityCount").textContent = countLabel(result.indemnity_findings.length);
  $("#correctedText").textContent = result.corrected_text;
  $("#auditContractId").textContent = result.contract_id;
  $("#auditCompleted").textContent = new Date(result.completed_at).toLocaleString();
  $("#auditDrift").textContent = `${result.processing_drift_seconds.toFixed(3)} seconds`;
  $("#auditIntegrity").textContent = result.baseline_integrity_verified ? "Verified" : "Failed";
  $("#legalReviewNotes").textContent = result.legal_review_notes;
  $("#changesApplied").innerHTML = result.changes_applied
    .map((change) => `<li>${escapeHtml(change)}</li>`)
    .join("");
}

function renderFindingGroup(id, findings, impactKey) {
  const container = $(`#${id}`);
  if (!findings.length) {
    container.innerHTML = '<div class="finding-card"><p>No material gaps identified.</p></div>';
    return;
  }
  container.innerHTML = findings
    .map(
      (finding) => `
        <article class="finding-card">
          <div class="finding-card-header">
            <strong>${escapeHtml(finding.clause_reference)}</strong>
            <span class="severity ${finding.risk_level}">${finding.risk_level}</span>
          </div>
          <p>${escapeHtml(finding.issue)}</p>
          <p>${escapeHtml(finding[impactKey])}</p>
          <details>
            <summary>View recommended language</summary>
            <p>${escapeHtml(finding.recommended_language)}</p>
          </details>
        </article>`,
    )
    .join("");
}

function countLabel(count) {
  return `${count} ${count === 1 ? "finding" : "findings"}`;
}

function handleFile(file) {
  if (!file) return;
  if (!["text/plain", "text/markdown", ""].includes(file.type)) {
    showToast("Only TXT and MD files are supported.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    elements.text.value = String(reader.result).slice(0, 100000);
    updateCount();
    $('[data-tab="paste"]').click();
    showToast(`${file.name} loaded.`);
  };
  reader.onerror = () => showToast("The selected file could not be read.");
  reader.readAsText(file);
}

function openSettings() {
  elements.apiUrl.value = state.apiBaseUrl;
  elements.apiToken.value = state.apiToken;
  elements.settings.showModal();
}

function saveSettings(event) {
  event.preventDefault();
  state.apiBaseUrl = elements.apiUrl.value.trim().replace(/\/$/, "");
  state.apiToken = elements.apiToken.value.trim();
  sessionStorage.setItem("apiBaseUrl", state.apiBaseUrl);
  sessionStorage.setItem("apiToken", state.apiToken);
  elements.settings.close();
  showToast("API connection updated.");
  checkHealth();
}

function downloadResult() {
  if (!state.result) return;
  const report = [
    "PROCUREMENT CONTRACT ANALYSIS",
    `Contract ID: ${state.result.contract_id}`,
    `Risk index: ${state.result.overall_risk_score}`,
    "",
    "CORRECTED CONTRACT",
    state.result.corrected_text,
    "",
    "LEGAL REVIEW NOTE",
    state.result.legal_review_notes,
  ].join("\n");
  const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `procurement-analysis-${state.result.contract_id.slice(0, 8)}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.classList.remove("visible"), 2600);
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value || "";
  return node.innerHTML;
}

activateTabs($$(".input-tab"), "Pane");
activateTabs($$(".result-tab"), "Result");
elements.text.addEventListener("input", updateCount);
elements.analyze.addEventListener("click", analyze);
elements.retry.addEventListener("click", analyze);
elements.clear.addEventListener("click", () => {
  elements.text.value = "";
  state.result = null;
  updateCount();
  elements.analysisId.textContent = "Awaiting contract";
  setView("empty");
});
elements.sample.addEventListener("click", () => {
  elements.text.value = sampleContract;
  updateCount();
  elements.text.focus();
});
elements.file.addEventListener("change", (event) => handleFile(event.target.files[0]));
elements.uploadZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  elements.uploadZone.classList.add("dragging");
});
elements.uploadZone.addEventListener("dragleave", () => elements.uploadZone.classList.remove("dragging"));
elements.uploadZone.addEventListener("drop", (event) => {
  event.preventDefault();
  elements.uploadZone.classList.remove("dragging");
  handleFile(event.dataTransfer.files[0]);
});
$("#settingsButton").addEventListener("click", openSettings);
$("#saveSettingsButton").addEventListener("click", saveSettings);
$("#copyButton").addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.result?.corrected_text || "");
  showToast("Corrected contract copied.");
});
$("#downloadButton").addEventListener("click", downloadResult);

updateCount();
checkHealth();
