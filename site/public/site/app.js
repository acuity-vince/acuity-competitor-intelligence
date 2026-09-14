const state = {
  rows: [], filtered: [], view: "trading-central", search: "", regulator: "",
  confidence: "", vendorStatus: "", companyType: "", sortKey: "brand_name", sortDirection: 1,
  page: 1, pageSize: 50,
};

const elements = {
  body: document.querySelector("#registryBody"), search: document.querySelector("#searchInput"),
  regulator: document.querySelector("#regulatorFilter"), confidence: document.querySelector("#confidenceFilter"),
  companyType: document.querySelector("#companyTypeFilter"),
  vendorStatus: document.querySelector("#vendorStatusFilter"), clear: document.querySelector("#clearFilters"),
  export: document.querySelector("#exportButton"), previous: document.querySelector("#previousPage"),
  next: document.querySelector("#nextPage"), pageLabel: document.querySelector("#pageLabel"),
  rowRange: document.querySelector("#rowRange"), visibleCount: document.querySelector("#visibleCount"),
  viewDescription: document.querySelector("#viewDescription"), dialog: document.querySelector("#detailDialog"),
};

const escapeHtml = (value) => String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const formatNumber = (value) => new Intl.NumberFormat("en-GB").format(value);
const tradingCentral = (profile) => profile.vendor_relationships?.find((item) => item.vendor === "Trading Central");
const canonicalFootprint = (profile) => profile.canonical_regulatory_footprint;
const canonicalLicenses = (profile) => canonicalFootprint(profile)?.legal_entities?.flatMap((entity) => entity.licenses || []) || [];
const regulatorCodes = (profile) => canonicalFootprint(profile)
  ? unique(canonicalFootprint(profile).regulator_claims?.filter((item) => item.status === "VERIFIED_ACTIVE").map((item) => item.regulator_code) || [])
  : profile.regulators?.map((item) => item.code).filter(Boolean) || [];
const profileConfidence = (profile) => tradingCentral(profile)?.confidence || profile.classification_confidence || "LOW";
const verificationStatus = (profile) => profile.verification?.status || "NOT_REVIEWED";
const unique = (values) => [...new Set(values.filter(Boolean))];

function setMetrics(generatedAt) {
  const tools = state.rows.filter((row) => tradingCentral(row));
  const priority = state.rows.filter((row) => row.priority_tier === "PRIORITY_100");
  const review = state.rows.filter((row) => row.needs_review === "YES");
  const pilot = state.rows.filter((row) => row.verification?.scope === "PRIORITY_25");
  const verified = pilot.filter((row) => ["READY", "READY_WITH_UNRESOLVED"].includes(canonicalFootprint(row)?.readiness));
  document.querySelector("#metricRecords").textContent = formatNumber(state.rows.length);
  document.querySelector("#metricTargets").textContent = formatNumber(tools.length);
  document.querySelector("#metricVerified").textContent = `${verified.length}/${pilot.length}`;
  document.querySelector("#metricReview").textContent = formatNumber(review.length);
  document.querySelector("#tradingCentralTabCount").textContent = formatNumber(tools.length);
  document.querySelector("#verifiedPilotTabCount").textContent = formatNumber(pilot.length);
  document.querySelector("#priorityTabCount").textContent = formatNumber(priority.length);
  document.querySelector("#reviewTabCount").textContent = formatNumber(review.length);
  document.querySelector("#allTabCount").textContent = formatNumber(state.rows.length);
  const parsed = generatedAt ? new Date(`${generatedAt}T00:00:00`) : null;
  document.querySelector("#lastUpdated").textContent = parsed && !Number.isNaN(parsed.valueOf())
    ? `Profiles updated ${parsed.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
    : "Profile date unavailable";
}

function populateRegulators() {
  for (const regulator of unique(state.rows.flatMap(regulatorCodes)).sort()) {
    const option = document.createElement("option");
    option.value = regulator;
    option.textContent = regulator;
    elements.regulator.append(option);
  }
}

function populateCompanyTypes() {
  for (const companyType of unique(state.rows.map((row) => row.company_type)).sort()) {
    const option = document.createElement("option");
    option.value = companyType;
    option.textContent = companyType;
    elements.companyType.append(option);
  }
}

function sortValue(row, key) {
  if (key === "research_tools") return tradingCentral(row)?.vendor || "";
  if (key === "regulator_sort") return regulatorCodes(row).join(" ");
  if (key === "profile_confidence") return profileConfidence(row);
  if (key === "verification_status") return verificationStatus(row);
  return row[key] || "";
}

function applyFilters() {
  const needle = state.search.trim().toLowerCase();
  state.filtered = state.rows.filter((row) => {
    const tool = tradingCentral(row);
    if (state.view === "trading-central" && !tool) return false;
    if (state.view === "priority" && row.priority_tier !== "PRIORITY_100") return false;
    if (state.view === "verified-pilot" && row.verification?.scope !== "PRIORITY_25") return false;
    if (state.view === "review" && row.needs_review !== "YES") return false;
    if (state.regulator && !regulatorCodes(row).includes(state.regulator)) return false;
    if (state.confidence && profileConfidence(row) !== state.confidence) return false;
    if (state.companyType && row.company_type !== state.companyType) return false;
    if (state.vendorStatus && !(row.vendor_relationships || []).some((item) => item.status === state.vendorStatus)) return false;
    if (needle) {
      const haystack = [row.brand_name, row.broker_group, ...(row.aliases || []), row.company_type, row.sales_relevance, row.primary_domain, row.primary_market,
        ...regulatorCodes(row), verificationStatus(row), ...(row.verification?.verified_regulators || []), ...(row.verification?.unresolved_regulators || []), ...(canonicalLicenses(row).length ? canonicalLicenses(row) : (row.licenses || [])).flatMap((item) => [item.legal_name, item.license_number, item.jurisdiction]),
        ...(row.vendor_relationships || []).flatMap((item) => [item.vendor, item.status, item.products?.join(" "), item.summary]),
        ...(row.technology_assessment || []).flatMap((item) => [item.vendor, item.status, item.note]),
        ...(row.people || []).flatMap((item) => [item.name, item.title, item.status]),
        ...(row.offices || []).flatMap((item) => [item.city, item.country]),
        row.sales_intelligence?.why_now, row.sales_intelligence?.discovery_angle].join(" ").toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
  state.filtered.sort((left, right) => String(sortValue(left, state.sortKey)).toLowerCase()
    .localeCompare(String(sortValue(right, state.sortKey)).toLowerCase(), undefined, { numeric: true }) * state.sortDirection);
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  renderTable();
}

function toolBadge(tool, compact = false) {
  if (!tool) return '<span class="muted-dash">Not recorded</span>';
  const statusClass = tool.status === "CONFIRMED_ACTIVE" ? "confirmed" : tool.status === "LIKELY_ACTIVE" || tool.status === "DIRECTORY_REPORTED" ? "likely" : "caution";
  const vendorClass = tool.vendor.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="tool-badge ${statusClass} ${vendorClass}">${escapeHtml(tool.vendor)}</span>${compact ? "" : `<small class="tool-status">${escapeHtml(tool.status.replaceAll("_", " ").toLowerCase())}</small>`}`;
}

function regulatorBadges(profile) {
  const codes = regulatorCodes(profile);
  if (!codes.length) return '<span class="muted-dash">To enrich</span>';
  const badges = codes.slice(0, 3).map((code) => `<span class="regulator-badge ${code === "FCA" ? "fca" : ""}">${escapeHtml(code)}</span>`).join(" ");
  return `${badges}${codes.length > 3 ? `<span class="more-badge">+${codes.length - 3}</span>` : ""}`;
}

function verificationBadge(profile, compact = true) {
  const status = verificationStatus(profile);
  const labels = { VERIFIED: "Verified", PARTIAL: "Partial", UNVERIFIED: "Unverified", NOT_REVIEWED: "Not reviewed" };
  const verified = profile.verification?.verified_regulators?.length || 0;
  const reported = profile.verification?.reported_regulators?.length || 0;
  const detail = compact || status === "NOT_REVIEWED" ? "" : `<small class="verification-count">${verified}/${reported} core regulator claims confirmed</small>`;
  return `<span class="verification-badge ${status.toLowerCase().replaceAll("_", "-")}">${labels[status] || escapeHtml(status)}</span>${detail}`;
}

function primaryEvidence(profile) {
  const tool = tradingCentral(profile);
  if (tool?.evidence_url) return { url: tool.evidence_url, label: "Tool evidence ↗" };
  const license = profile.licenses?.find((item) => item.evidence_url);
  return license ? { url: license.evidence_url, label: "Regulator source ↗" } : null;
}

function renderTable() {
  const start = (state.page - 1) * state.pageSize;
  const pageRows = state.filtered.slice(start, start + state.pageSize);
  if (!pageRows.length) elements.body.replaceChildren(document.querySelector("#emptyState").content.cloneNode(true));
  else elements.body.innerHTML = pageRows.map((row, index) => {
    const tool = tradingCentral(row);
    const evidence = primaryEvidence(row);
    const entityCount = row.legal_entities?.length || 0;
    return `<tr class="broker-row" data-row-index="${start + index}" tabindex="0" role="button" aria-label="Open ${escapeHtml(row.brand_name)} profile">
      <td class="entity-cell"><strong title="${escapeHtml(row.brand_name)}">${escapeHtml(row.brand_name)}</strong><small>${escapeHtml(row.primary_domain || `${entityCount} legal ${entityCount === 1 ? "entity" : "entities"}`)}</small></td>
      <td><span class="type-badge ${row.sales_relevance.toLowerCase()}">${escapeHtml(row.company_type)}</span></td>
      <td class="tool-cell">${row.vendor_relationships?.length ? `<div class="tool-stack">${row.vendor_relationships.slice(0, 3).map((item) => toolBadge(item, true)).join("")}</div>` : toolBadge(tool)}</td><td class="regulator-cell">${regulatorBadges(row)}</td>
      <td>${escapeHtml(row.primary_market || "—")}</td><td class="verification-cell">${verificationBadge(row)}</td><td><span class="confidence-badge ${profileConfidence(row).toLowerCase()}">${escapeHtml(profileConfidence(row))}</span></td>
      <td>${evidence ? `<a class="evidence-link" href="${escapeHtml(evidence.url)}" target="_blank" rel="noreferrer">${evidence.label}</a>` : "—"}</td>
      <td><button class="row-button" type="button" tabindex="-1" aria-hidden="true">→</button></td></tr>`;
  }).join("");
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  elements.visibleCount.textContent = formatNumber(state.filtered.length);
  elements.pageLabel.textContent = `Page ${state.page} of ${pages}`;
  elements.rowRange.textContent = state.filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, state.filtered.length)}` : "0–0";
  elements.previous.disabled = state.page === 1; elements.next.disabled = state.page === pages; elements.export.disabled = !state.filtered.length;
}

function detailField(label, value, link = "") {
  const content = link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${escapeHtml(value)} ↗</a>` : escapeHtml(value || "—");
  return `<div class="detail-field"><span>${escapeHtml(label)}</span><strong>${content}</strong></div>`;
}

function licenseCards(profile) {
  const licenses = canonicalLicenses(profile).length ? canonicalLicenses(profile) : profile.licenses || [];
  if (!licenses.length) return '<p class="empty-note">No official regulatory licences are linked yet. This profile remains in the resolution queue.</p>';
  return licenses.map((item) => `<article class="record-card ${item.source === "Official regulator registry" ? "official-record" : "reported-record"}"><div><span class="regulator-badge ${item.regulator_code === "FCA" ? "fca" : ""}">${escapeHtml(item.regulator_code || item.regulator_name)}</span><strong>${escapeHtml(item.legal_name || "Reported broker relationship")}</strong></div>
    <p>${escapeHtml(item.license_number ? `Licence ${item.license_number}` : item.license_type)} · ${escapeHtml(item.status || "Status unavailable")} · ${item.source === "Official regulator registry" ? "Official regulator record" : "Directory reported"}</p>
    ${item.evidence_url ? `<a href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">View source ↗</a>` : ""}</article>`).join("");
}

function verificationPanel(profile) {
  const verification = profile.verification || {};
  if (verification.scope !== "PRIORITY_25") return '<p class="empty-note">This profile is outside the current Priority 25 verification pilot.</p>';
  const verified = verification.verified_regulators || [];
  const unresolved = verification.unresolved_regulators || [];
  const footprint = canonicalFootprint(profile);
  const claimRows = footprint?.regulator_claims?.map((claim) => `<div><span>${escapeHtml(claim.regulator_code)}</span><strong>${escapeHtml(claim.status.replaceAll("_", " ").toLowerCase())}</strong></div>`).join("") || "";
  return `<div class="verification-summary"><div>${verificationBadge(profile, false)}</div><p>Official evidence confirms <strong>${verified.length}</strong> of <strong>${verification.reported_regulators?.length || 0}</strong> core regulator claims in this pilot.</p>
    <div class="verification-groups"><div><span>Officially verified</span><strong>${verified.length ? escapeHtml(verified.join(" · ")) : "None yet"}</strong></div><div><span>Still unresolved</span><strong>${unresolved.length ? escapeHtml(unresolved.join(" · ")) : "None"}</strong></div></div>
    ${footprint ? `<p class="verification-note">Canonical footprint: ${escapeHtml(footprint.readiness.toLowerCase())} · ${footprint.legal_entities.length} mapped legal entities · ${footprint.official_license_count} official licences.</p><div class="verification-groups">${claimRows}</div>` : ""}
    ${verification.notes?.length ? `<p class="verification-note">${escapeHtml(verification.notes.join(" "))}</p>` : ""}</div>`;
}

function relationshipCards(profile) {
  if (!profile.vendor_relationships?.length) {
    const scan = profile.research_scan || {};
    const note = scan.status === "none-found" ? "The supplied directory scan found no Acuity, Trading Central, or Autochartist relationship on the pages checked." : "No research-tool relationship has been recorded yet.";
    return `<p class="empty-note">${escapeHtml(note)}</p>`;
  }
  return profile.vendor_relationships.map((item) => {
    const products = item.products?.length ? item.products.join(" · ") : "Not specified";
    const integration = item.integration_types?.length ? item.integration_types.join(" · ") : "Not specified";
    return `<article class="vendor-card"><div class="vendor-heading"><div>${toolBadge(item)}</div><span class="confidence-badge ${item.confidence.toLowerCase()}">${escapeHtml(item.confidence)} · ${item.confidence_score}/100</span></div>
      <p>${escapeHtml(item.summary || item.description || "Relationship recorded in the supplied directory research.")}</p><dl><div><dt>Products</dt><dd>${escapeHtml(products)}</dd></div><div><dt>Integration</dt><dd>${escapeHtml(integration)}</dd></div></dl>
      ${item.evidence_url ? `<a href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">Open evidence ↗</a>` : ""}</article>`;
  }).join("");
}

function technologyAssessmentCards(profile) {
  const assessments = profile.technology_assessment || [];
  if (!assessments.length) return '<p class="empty-note">No structured technology assessment is available yet.</p>';
  return assessments.map((item) => {
    const statusClass = item.status === "CONFIRMED_ACTIVE" ? "confirmed" : item.status === "LIKELY_ACTIVE" || item.status === "DIRECTORY_REPORTED" ? "likely" : "caution";
    const status = item.status?.replaceAll("_", " ").toLowerCase() || "unknown";
    return `<article class="assessment-card"><div><span class="tool-badge ${statusClass}">${escapeHtml(item.vendor)}</span><span class="assessment-status">${escapeHtml(status)}</span></div>
      <p>${escapeHtml(item.note || (item.status === "UNKNOWN" ? "No current first-party evidence was located in this pass." : "Evidence recorded."))}</p>
      <footer><span>${escapeHtml(item.confidence || "LOW")} confidence${item.checked_date ? ` · checked ${escapeHtml(item.checked_date)}` : ""}</span>${item.evidence_url ? `<a href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">Source ↗</a>` : ""}</footer></article>`;
  }).join("");
}

function salesPanel(profile) {
  const intel = profile.sales_intelligence || {};
  if (!intel.why_now && !intel.discovery_angle) return '<p class="empty-note">Sales intelligence is pending review for this Priority 100 account.</p>';
  return `<div class="sales-panel"><div><span>Why now</span><p>${escapeHtml(intel.why_now)}</p></div><div><span>Discovery angle</span><p>${escapeHtml(intel.discovery_angle)}</p></div>
    <footer><span>${intel.hypothesis ? "Sales hypothesis. Validate in discovery." : "Evidence-backed finding"}${intel.last_checked ? ` · checked ${escapeHtml(intel.last_checked)}` : ""}</span>${intel.sources?.length ? `<a href="${escapeHtml(intel.sources[0])}" target="_blank" rel="noreferrer">Primary source ↗</a>` : ""}</footer></div>`;
}

function leadershipAndOffices(profile) {
  const confirmed = (profile.people || []).filter((item) => item.name && item.status !== "UNRESOLVED");
  const unresolved = (profile.people || []).find((item) => item.status === "UNRESOLVED");
  const people = confirmed.length ? confirmed.map((item) => `<article class="person-card"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.title)}</span>${item.evidence_url ? `<a href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">First-party source ↗</a>` : ""}</article>`).join("") : `<p class="empty-note">${escapeHtml(unresolved?.note || "No current first-party leadership disclosure was located in this pass.")}</p>`;
  const offices = (profile.offices || []).length ? profile.offices.map((item) => `<span class="office-chip">${escapeHtml([item.city, item.country].filter(Boolean).join(", "))}</span>`).join("") : '<p class="empty-note">No current office evidence is recorded.</p>';
  return `<div class="enrichment-columns"><div><h5>Decision-makers</h5><div class="person-list">${people}</div></div><div><h5>Offices</h5><div class="office-list">${offices}</div></div></div>`;
}

function historyCards(profile) {
  if (!profile.change_history?.length) return '<p class="empty-note">No material change has been recorded since monitoring began.</p>';
  return profile.change_history.map((item) => `<article class="history-card"><time>${escapeHtml(item.date)}</time><div><strong>${escapeHtml(item.category?.replaceAll("_", " ").toLowerCase())}</strong><p>${escapeHtml(item.summary)}</p></div>${item.evidence_url ? `<a href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">Source ↗</a>` : ""}</article>`).join("");
}

function openDetails(row, updateHash = true) {
  document.querySelector("#detailRegulator").textContent = `${regulatorCodes(row).length || "No"} regulator${regulatorCodes(row).length === 1 ? "" : "s"} · ${row.vendor_relationships?.length || 0} research tool`;
  document.querySelector("#detailName").textContent = row.brand_name;
  document.querySelector("#detailContent").innerHTML = `<section class="detail-section"><h4>Profile overview</h4><div class="detail-grid">
    ${detailField("Website", row.primary_domain || "Not recorded", row.website_url)}${detailField("Primary market", row.primary_market || "Not recorded")}
    ${detailField("Company type", row.company_type)}${detailField("Sales relevance", row.sales_relevance)}
    ${detailField("Headquarters", row.headquarters || "Not recorded")}${detailField("Founded", row.founded_year || "Not recorded")}
    ${detailField("Priority rank", row.priority_rank ? `#${row.priority_rank}` : "Not ranked")}${detailField("Identity status", row.identity_status === "CANONICAL" ? "Canonical profile" : "Needs identity review")}</div>
    <p class="identity-note">${escapeHtml(row.company_type_reason || row.identity_note)}</p></section>
    <section class="detail-section"><h4>Regulatory verification <span>${escapeHtml(verificationStatus(row).replaceAll("_", " ").toLowerCase())}</span></h4>${verificationPanel(row)}</section>
    <section class="detail-section"><h4>Sales brief <span>${escapeHtml(row.intelligence_scope?.replaceAll("_", " ").toLowerCase() || "not ranked")}</span></h4>${salesPanel(row)}</section>
    <section class="detail-section"><h4>Technology assessment <span>3 tracked vendors</span></h4><div class="assessment-grid">${technologyAssessmentCards(row)}</div></section>
    <section class="detail-section"><h4>Relationship evidence <span>${row.vendor_relationships?.length || 0} records</span></h4><div class="vendor-list">${relationshipCards(row)}</div></section>
    <section class="detail-section"><h4>Canonical regulatory footprint <span>${canonicalLicenses(row).length || row.licenses?.length || 0} records</span></h4><div class="record-list">${licenseCards(row)}</div></section>
    <section class="detail-section"><h4>Domains <span>${row.domains?.length || 0}</span></h4><div class="tag-list">${row.domains?.length ? row.domains.map((item) => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.domain)} ↗</a>`).join("") : '<span class="empty-note">No domains linked.</span>'}</div></section>
    <section class="detail-section"><h4>Leadership &amp; offices</h4>${leadershipAndOffices(row)}</section>
    <section class="detail-section"><h4>Change history <span>material changes only</span></h4><div class="history-list">${historyCards(row)}</div></section>`;
  if (!elements.dialog.open) elements.dialog.showModal();
  if (updateHash && location.hash !== `#broker=${row.slug}`) history.pushState(null, "", `#broker=${row.slug}`);
}

function closeDetails(updateHash = true) {
  if (elements.dialog.open) elements.dialog.close();
  if (updateHash && location.hash.startsWith("#broker=")) history.pushState(null, "", location.pathname + location.search);
}

function exportCurrentView() {
  const headers = ["priority_rank", "brand_name", "company_type", "sales_relevance", "primary_domain", "forex_broker", "research_tools", "trading_central_status", "trading_central_confidence", "regulators", "verified_regulators", "unresolved_regulators", "verification_status", "license_numbers", "primary_market", "headquarters", "decision_makers", "offices", "trading_central_assessment", "autochartist_assessment", "acuity_assessment", "why_now", "discovery_angle", "intelligence_scope", "identity_status", "needs_review", "last_checked"];
  const flattened = state.filtered.map((row) => { const tool = tradingCentral(row); return {
    priority_rank: row.priority_rank || "", brand_name: row.brand_name, company_type: row.company_type, sales_relevance: row.sales_relevance, primary_domain: row.primary_domain, forex_broker: row.forex_broker,
    research_tools: row.vendor_relationships?.map((item) => item.vendor).join("; ") || "", trading_central_status: tool?.status || "",
    trading_central_confidence: tool?.confidence_score ?? "", regulators: regulatorCodes(row).join("; "), verified_regulators: row.verification?.verified_regulators?.join("; ") || "", unresolved_regulators: row.verification?.unresolved_regulators?.join("; ") || "", verification_status: verificationStatus(row),
    license_numbers: unique((canonicalLicenses(row).length ? canonicalLicenses(row) : row.licenses || []).map((item) => item.license_number)).join("; "), primary_market: row.primary_market,
    headquarters: row.headquarters, decision_makers: row.people?.filter((item) => item.name).map((item) => `${item.name} | ${item.title}`).join("; ") || "Unresolved", offices: row.offices?.map((item) => [item.city, item.country].filter(Boolean).join(", ")).join("; ") || "",
    trading_central_assessment: row.technology_assessment?.find((item) => item.vendor === "Trading Central")?.status || "UNKNOWN", autochartist_assessment: row.technology_assessment?.find((item) => item.vendor === "Autochartist")?.status || "UNKNOWN", acuity_assessment: row.technology_assessment?.find((item) => item.vendor === "Acuity Trading")?.status || "UNKNOWN",
    why_now: row.sales_intelligence?.why_now || "", discovery_angle: row.sales_intelligence?.discovery_angle || "", intelligence_scope: row.intelligence_scope || "",
    identity_status: row.identity_status, needs_review: row.needs_review, last_checked: row.last_checked,
  }; });
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [headers.map(quote).join(","), ...flattened.map((row) => headers.map((header) => quote(row[header])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = `acuity-broker-profiles-${state.view}.csv`; link.click(); URL.revokeObjectURL(url);
}

document.querySelectorAll(".view-tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".view-tab").forEach((item) => item.classList.remove("active")); tab.classList.add("active");
  state.view = tab.dataset.view; state.page = 1;
  elements.viewDescription.textContent = { "trading-central": "Showing brokers with documented Trading Central relationships.", "verified-pilot": "Showing the Priority 25 gold set: every core claim is classified and unresolved gaps remain explicit.", priority: "Showing the 100 highest-ranked sales opportunities with a consistent intelligence structure.", review: "Showing profiles that need human validation or enrichment.", all: "Showing every broker and regulated entity in the current intelligence layer." }[state.view];
  applyFilters();
}));
elements.search.addEventListener("input", (event) => { state.search = event.target.value; state.page = 1; applyFilters(); });
elements.regulator.addEventListener("change", (event) => { state.regulator = event.target.value; state.page = 1; applyFilters(); });
elements.confidence.addEventListener("change", (event) => { state.confidence = event.target.value; state.page = 1; applyFilters(); });
elements.companyType.addEventListener("change", (event) => { state.companyType = event.target.value; state.page = 1; applyFilters(); });
elements.vendorStatus.addEventListener("change", (event) => { state.vendorStatus = event.target.value; state.page = 1; applyFilters(); });
elements.clear.addEventListener("click", () => { state.search = ""; state.regulator = ""; state.confidence = ""; state.vendorStatus = ""; state.companyType = ""; state.page = 1;
  elements.search.value = ""; elements.regulator.value = ""; elements.confidence.value = ""; elements.vendorStatus.value = ""; elements.companyType.value = ""; applyFilters(); });
elements.previous.addEventListener("click", () => { state.page -= 1; renderTable(); });
elements.next.addEventListener("click", () => { state.page += 1; renderTable(); });
elements.export.addEventListener("click", exportCurrentView);
document.querySelector("#closeDialog").addEventListener("click", () => closeDetails());
elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) closeDetails(); });
elements.dialog.addEventListener("cancel", (event) => { event.preventDefault(); closeDetails(); });
elements.body.addEventListener("click", (event) => { if (event.target.closest("a, input, select, textarea")) return; const row = event.target.closest("tr[data-row-index]"); if (row) openDetails(state.filtered[Number(row.dataset.rowIndex)]); });
elements.body.addEventListener("keydown", (event) => { if (!["Enter", " "].includes(event.key) || event.target.closest("a, input, select, textarea")) return; const row = event.target.closest("tr[data-row-index]"); if (!row) return; event.preventDefault(); openDetails(state.filtered[Number(row.dataset.rowIndex)]); });
document.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => { if (state.sortKey === button.dataset.sort) state.sortDirection *= -1; else { state.sortKey = button.dataset.sort; state.sortDirection = 1; } applyFilters(); }));
document.addEventListener("keydown", (event) => { if (event.key === "/" && document.activeElement !== elements.search) { event.preventDefault(); elements.search.focus(); } });
window.addEventListener("hashchange", () => { const slug = location.hash.startsWith("#broker=") ? decodeURIComponent(location.hash.slice(8)) : ""; const profile = slug ? state.rows.find((row) => row.slug === slug) : null; if (profile) openDetails(profile, false); else closeDetails(false); });

async function initialise() {
  try {
    let payload = window.__ACUITY_BROKER_DATA__;
    if (!payload) {
      const response = await fetch("/site/data/brokers.json", { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) throw new Error(`Profile request failed: ${response.status}`);
      payload = await response.json();
    }
    state.rows = payload.profiles || [];
    delete window.__ACUITY_BROKER_DATA__;
    setMetrics(payload.generated_at); populateRegulators(); populateCompanyTypes(); applyFilters();
    if (location.hash.startsWith("#broker=")) { const profile = state.rows.find((row) => row.slug === decodeURIComponent(location.hash.slice(8))); if (profile) openDetails(profile, false); }
  } catch (error) {
    console.error(error); elements.body.innerHTML = '<tr><td colspan="9" class="empty-cell"><strong>Broker profiles unavailable</strong><span>Start the site through its local server so the data file can load.</span></td></tr>';
    document.querySelector("#lastUpdated").textContent = "Data connection unavailable";
  }
}

initialise();
