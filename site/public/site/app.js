const state = {
  rows: [],
  filtered: [],
  view: "targets",
  search: "",
  regulator: "",
  confidence: "",
  sortKey: "legal_name",
  sortDirection: 1,
  page: 1,
  pageSize: 50,
};

const elements = {
  body: document.querySelector("#registryBody"),
  search: document.querySelector("#searchInput"),
  regulator: document.querySelector("#regulatorFilter"),
  confidence: document.querySelector("#confidenceFilter"),
  clear: document.querySelector("#clearFilters"),
  export: document.querySelector("#exportButton"),
  previous: document.querySelector("#previousPage"),
  next: document.querySelector("#nextPage"),
  pageLabel: document.querySelector("#pageLabel"),
  rowRange: document.querySelector("#rowRange"),
  visibleCount: document.querySelector("#visibleCount"),
  viewDescription: document.querySelector("#viewDescription"),
  dialog: document.querySelector("#detailDialog"),
};

function parseCsv(text) {
  const output = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      field += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(field);
      if (row.some((value) => value.length)) output.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    output.push(row);
  }
  const headers = output.shift().map((header) => header.replace(/^\uFEFF/, ""));
  return output.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
}

const escapeHtml = (value) => String(value || "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

const formatNumber = (value) => new Intl.NumberFormat("en-GB").format(value);

function setMetrics() {
  const targets = state.rows.filter((row) => row.forex_broker === "YES");
  const review = state.rows.filter((row) => row.needs_review === "YES");
  const verified = state.rows.filter((row) => row.evidence_url && row.evidence_status);
  document.querySelector("#metricRecords").textContent = formatNumber(state.rows.length);
  document.querySelector("#metricTargets").textContent = formatNumber(targets.length);
  document.querySelector("#metricVerified").textContent = formatNumber(verified.length);
  document.querySelector("#metricReview").textContent = formatNumber(review.length);
  document.querySelector("#targetTabCount").textContent = formatNumber(targets.length);
  document.querySelector("#reviewTabCount").textContent = formatNumber(review.length);
  document.querySelector("#allTabCount").textContent = formatNumber(state.rows.length);

  const timestamps = state.rows.map((row) => Date.parse(row.last_checked)).filter(Number.isFinite);
  const latest = timestamps.length ? new Date(Math.max(...timestamps)) : null;
  document.querySelector("#lastUpdated").textContent = latest
    ? `Data checked ${latest.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
    : "Source date unavailable";
}

function populateRegulators() {
  const regulators = [...new Set(state.rows.map((row) => row.regulator_code).filter(Boolean))].sort();
  for (const regulator of regulators) {
    const option = document.createElement("option");
    option.value = regulator;
    option.textContent = regulator;
    elements.regulator.append(option);
  }
}

function applyFilters() {
  const needle = state.search.trim().toLowerCase();
  state.filtered = state.rows.filter((row) => {
    if (state.view === "targets" && row.forex_broker !== "YES") return false;
    if (state.view === "review" && row.needs_review !== "YES") return false;
    if (state.regulator && row.regulator_code !== state.regulator) return false;
    if (state.confidence && row.classification_confidence !== state.confidence) return false;
    if (needle) {
      const haystack = [
        row.legal_name, row.regulator_code, row.regulator, row.jurisdiction,
        row.license_number, row.approved_domains, row.classification_reason,
      ].join(" ").toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });

  state.filtered.sort((left, right) => {
    const a = String(left[state.sortKey] || "").toLowerCase();
    const b = String(right[state.sortKey] || "").toLowerCase();
    return a.localeCompare(b, undefined, { numeric: true }) * state.sortDirection;
  });

  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  renderTable();
}

function renderTable() {
  const start = (state.page - 1) * state.pageSize;
  const pageRows = state.filtered.slice(start, start + state.pageSize);
  if (!pageRows.length) {
    elements.body.replaceChildren(document.querySelector("#emptyState").content.cloneNode(true));
  } else {
    elements.body.innerHTML = pageRows.map((row, index) => `
      <tr>
        <td class="entity-cell"><strong title="${escapeHtml(row.legal_name)}">${escapeHtml(row.legal_name)}</strong><small>${escapeHtml(row.license_type || "Regulated entity")}</small></td>
        <td><span class="regulator-badge ${row.regulator_code === "FCA" ? "fca" : ""}">${escapeHtml(row.regulator_code)}</span></td>
        <td>${escapeHtml(row.jurisdiction)}</td>
        <td>${escapeHtml(row.license_number || "—")}</td>
        <td><span class="confidence-badge ${(row.classification_confidence || "low").toLowerCase()}">${escapeHtml(row.classification_confidence || "UNRATED")}</span></td>
        <td>${row.evidence_url ? `<a class="evidence-link" href="${escapeHtml(row.evidence_url)}" target="_blank" rel="noreferrer">Official source ↗</a>` : "—"}</td>
        <td><button class="row-button" data-row-index="${start + index}" aria-label="View ${escapeHtml(row.legal_name)} details">→</button></td>
      </tr>
    `).join("");
  }

  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  elements.visibleCount.textContent = formatNumber(state.filtered.length);
  elements.pageLabel.textContent = `Page ${state.page} of ${pages}`;
  elements.rowRange.textContent = state.filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, state.filtered.length)}` : "0–0";
  elements.previous.disabled = state.page === 1;
  elements.next.disabled = state.page === pages;
  elements.export.disabled = !state.filtered.length;
}

function openDetails(row) {
  document.querySelector("#detailRegulator").textContent = `${row.regulator_code} · ${row.jurisdiction}`;
  document.querySelector("#detailName").textContent = row.legal_name;
  document.querySelector("#detailContent").innerHTML = `
    <div class="detail-grid">
      <div class="detail-field"><span>Status</span><strong>${escapeHtml(row.status || "—")}</strong></div>
      <div class="detail-field"><span>Forex / CFD target</span><strong>${escapeHtml(row.forex_broker || "—")}</strong></div>
      <div class="detail-field"><span>Licence number</span><strong>${escapeHtml(row.license_number || "—")}</strong></div>
      <div class="detail-field"><span>Confidence</span><strong>${escapeHtml(row.classification_confidence || "—")}</strong></div>
      <div class="detail-field"><span>Approved domains</span><strong>${escapeHtml(row.approved_domains || "—")}</strong></div>
      <div class="detail-field"><span>Needs review</span><strong>${escapeHtml(row.needs_review || "—")}</strong></div>
    </div>
    <div class="detail-reason"><strong>Classification rationale</strong><br>${escapeHtml(row.classification_reason || "No rationale recorded.")}</div>
    ${row.evidence_url ? `<div class="detail-actions"><a href="${escapeHtml(row.evidence_url)}" target="_blank" rel="noreferrer">Open official evidence ↗</a></div>` : ""}
  `;
  elements.dialog.showModal();
}

function exportCurrentView() {
  const headers = Object.keys(state.rows[0] || {});
  const quote = (value) => `"${String(value || "").replaceAll('"', '""')}"`;
  const csv = [headers.map(quote).join(","), ...state.filtered.map((row) => headers.map((header) => quote(row[header])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `acuity-broker-registry-${state.view}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

document.querySelectorAll(".view-tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".view-tab").forEach((item) => item.classList.remove("active"));
  tab.classList.add("active");
  state.view = tab.dataset.view;
  state.page = 1;
  elements.viewDescription.textContent = {
    targets: "Showing potential forex and CFD sales targets.",
    review: "Showing records that need human validation.",
    all: "Showing every active regulatory record in the current baseline.",
  }[state.view];
  applyFilters();
}));

elements.search.addEventListener("input", (event) => { state.search = event.target.value; state.page = 1; applyFilters(); });
elements.regulator.addEventListener("change", (event) => { state.regulator = event.target.value; state.page = 1; applyFilters(); });
elements.confidence.addEventListener("change", (event) => { state.confidence = event.target.value; state.page = 1; applyFilters(); });
elements.clear.addEventListener("click", () => {
  state.search = ""; state.regulator = ""; state.confidence = ""; state.page = 1;
  elements.search.value = ""; elements.regulator.value = ""; elements.confidence.value = "";
  applyFilters();
});
elements.previous.addEventListener("click", () => { state.page -= 1; renderTable(); });
elements.next.addEventListener("click", () => { state.page += 1; renderTable(); });
elements.export.addEventListener("click", exportCurrentView);
document.querySelector("#closeDialog").addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) elements.dialog.close(); });
elements.body.addEventListener("click", (event) => {
  const button = event.target.closest("[data-row-index]");
  if (button) openDetails(state.filtered[Number(button.dataset.rowIndex)]);
});
document.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => {
  if (state.sortKey === button.dataset.sort) state.sortDirection *= -1;
  else { state.sortKey = button.dataset.sort; state.sortDirection = 1; }
  applyFilters();
}));
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== elements.search) {
    event.preventDefault();
    elements.search.focus();
  }
});

async function initialise() {
  try {
    const response = await fetch("./data/registry.csv", { cache: "no-store" });
    if (!response.ok) throw new Error(`Registry request failed: ${response.status}`);
    state.rows = parseCsv(await response.text());
    setMetrics();
    populateRegulators();
    applyFilters();
  } catch (error) {
    console.error(error);
    elements.body.innerHTML = `<tr><td colspan="7" class="empty-cell"><strong>Registry unavailable</strong><span>Start the site through its local server so the data file can load.</span></td></tr>`;
    document.querySelector("#lastUpdated").textContent = "Data connection unavailable";
  }
}

initialise();
