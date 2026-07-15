const form = document.querySelector("#brief-form");
const result = document.querySelector("#result");
const history = document.querySelector("#history");
const runtimeStatus = document.querySelector("#runtime-status");
const split = (id) => document.querySelector(id).value.split(",").map(v => v.trim()).filter(Boolean);

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);

const safeUrl = (value) => {
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
};

const formatDate = (value) => new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium", timeStyle: "short"
}).format(new Date(value));

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { detail = (await response.json()).detail || detail; } catch { /* response was not JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function renderRun(summary, details) {
  const manifest = details.manifest;
  const verification = details.verification;
  const finalAttempt = manifest.attempts[manifest.final_attempt - 1];
  const attemptCards = manifest.attempts.map(attempt => {
    const feedback = attempt.evaluation.feedback.length
      ? attempt.evaluation.feedback.map(escapeHtml).join(" · ")
      : "All deterministic checks passed.";
    return `<article class="attempt"><header><b>Attempt ${attempt.index}</b>
      <span>${Math.round(attempt.evaluation.score * 100)}% · ${escapeHtml(attempt.asset.provider)} / ${escapeHtml(attempt.asset.model)}</span></header>
      <p>${feedback}</p></article>`;
  }).join("");
  const reviewState = details.review
    ? `${escapeHtml(details.review.decision)} by ${escapeHtml(details.review.reviewer)} · ${escapeHtml(details.review.note)}`
    : "No human decision has been recorded. A server-side review token is required.";
  result.classList.remove("empty");
  result.innerHTML = `<div class="section-label">REPRODUCIBILITY RESULT</div>
    <div class="result-card"><img src="${safeUrl(finalAttempt.asset.url)}" alt="Generated evidence-bound visual">
    <div class="metrics"><div class="metric"><b>${Math.round(summary.score * 100)}%</b><span>GUARDRAIL SCORE</span></div>
    <div class="metric"><b>${summary.attempts}</b><span>ATTEMPTS</span></div>
    <div class="metric"><b>${summary.status === "accepted" ? "PASS" : "REVIEW"}</b><span>AUTO GATE</span></div>
    <div class="metric"><b>${verification.valid ? "VERIFIED" : "CHECK"}</b><span>STORED BYTES</span></div></div>
    <div class="hash">sha256:${escapeHtml(summary.canonical_sha256)}</div>
    <div class="links"><a href="${safeUrl(finalAttempt.asset.url)}" target="_blank" rel="noopener">Open asset</a>
    <a href="${safeUrl(summary.manifest_url)}" target="_blank" rel="noopener">Inspect manifest</a>
    <a href="/api/runs/${summary.run_id}/bundle">Download proof bundle</a></div>
    <section class="attempts"><h3>ATTEMPT COMPARISON</h3>${attemptCards}</section>
    <section class="review-panel"><h3>EXPLICIT HUMAN ACCEPTANCE</h3>
      <div class="review-controls"><input id="review-token" type="password" autocomplete="off" placeholder="Server-side review token">
      <button type="button" data-review="accepted" data-run="${summary.run_id}">Accept</button>
      <button type="button" data-review="needs_changes" data-run="${summary.run_id}">Needs changes</button></div>
      <p class="review-state">${reviewState}</p></section></div>`;
  result.scrollIntoView({behavior: "smooth", block: "start"});
}

async function loadRun(runId) {
  const details = await api(`/api/runs/${runId}`);
  const manifest = details.manifest;
  const finalAttempt = manifest.attempts[manifest.final_attempt - 1];
  renderRun({
    run_id: manifest.run_id,
    title: manifest.brief.title,
    created_at: manifest.created_at,
    status: manifest.status,
    score: finalAttempt.evaluation.score,
    attempts: manifest.attempts.length,
    asset_url: finalAttempt.asset.url,
    manifest_url: finalAttempt.asset.url.startsWith("/api/artifacts/")
      ? `/api/artifacts/${manifest.run_id}/manifest.json`
      : `/artifacts/${manifest.run_id}/manifest.json`,
    canonical_sha256: manifest.canonical_sha256
  }, details);
}

async function loadHistory() {
  try {
    const runs = await api("/api/runs?limit=12");
    if (!runs.length) {
      history.innerHTML = '<div class="history-empty">No durable runs yet. Generate one above.</div>';
      return;
    }
    history.innerHTML = runs.map(run => `<article class="history-card">
      <h3>${escapeHtml(run.title)}</h3><div class="history-meta"><span>${formatDate(run.created_at)}</span>
      <span>${Math.round(run.score * 100)}% · ${run.attempts} attempt${run.attempts === 1 ? "" : "s"}</span></div>
      <button type="button" data-open-run="${run.run_id}"><span>Inspect evidence</span><b>↗</b></button></article>`).join("");
  } catch (error) {
    history.innerHTML = `<div class="history-empty">${escapeHtml(error.message)}</div>`;
  }
}

async function loadRuntime() {
  try {
    const health = await api("/health");
    runtimeStatus.innerHTML = `<i></i>${escapeHtml(health.mode)} · ${escapeHtml(health.version)}`;
  } catch {
    runtimeStatus.textContent = "runtime unavailable";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  button.querySelector("span").textContent = "Building provenance chain…";
  const claims = document.querySelector("#claims").value.split("\n").map(v => v.trim()).filter(Boolean);
  const body = {
    title: document.querySelector("#title").value,
    audience: document.querySelector("#audience").value,
    claims: claims.map((text, index) => ({
      claim_id: `c${index + 1}`, text, priority: index < 2 ? "required" : "supporting"
    })),
    required_labels: split("#labels"),
    forbidden_elements: split("#forbidden"),
    style: document.querySelector("#style").value,
    aspect_ratio: "16:9"
  };
  try {
    const summary = await api("/api/runs", {
      method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)
    });
    const details = await api(`/api/runs/${summary.run_id}`);
    renderRun(summary, details);
    await loadHistory();
  } catch (error) {
    result.innerHTML = `<div class="section-label">RUN ERROR</div><div class="placeholder"><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Generate with evidence guardrails";
  }
});

document.addEventListener("click", async (event) => {
  const openButton = event.target.closest("[data-open-run]");
  if (openButton) {
    openButton.disabled = true;
    try { await loadRun(openButton.dataset.openRun); }
    catch (error) { window.alert(error.message); }
    finally { openButton.disabled = false; }
    return;
  }
  const reviewButton = event.target.closest("[data-review]");
  if (!reviewButton) return;
  const token = document.querySelector("#review-token").value;
  if (!token) { window.alert("Enter the server-side human-review token first."); return; }
  reviewButton.disabled = true;
  try {
    await api(`/api/runs/${reviewButton.dataset.run}/review`, {
      method: "POST",
      headers: {"content-type": "application/json", "X-ReproFrame-Review-Token": token},
      body: JSON.stringify({decision: reviewButton.dataset.review, reviewer: "authorized-human"})
    });
    await loadRun(reviewButton.dataset.run);
  } catch (error) { window.alert(error.message); }
  finally { reviewButton.disabled = false; }
});

loadRuntime();
loadHistory();
