const form = document.querySelector("#brief-form");
const result = document.querySelector("#result");
const split = (id) => document.querySelector(id).value.split(",").map(v => v.trim()).filter(Boolean);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  button.querySelector("span").textContent = "Building provenance chain…";
  const claims = document.querySelector("#claims").value.split("\n").map(v => v.trim()).filter(Boolean);
  const body = {
    title: document.querySelector("#title").value,
    audience: document.querySelector("#audience").value,
    claims: claims.map((text, index) => ({claim_id: `c${index + 1}`, text, priority: index < 2 ? "required" : "supporting"})),
    required_labels: split("#labels"),
    forbidden_elements: split("#forbidden"),
    style: document.querySelector("#style").value,
    aspect_ratio: "16:9"
  };
  try {
    const response = await fetch("/api/runs", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
    if (!response.ok) throw new Error(`Run failed (${response.status})`);
    const data = await response.json();
    result.classList.remove("empty");
    result.innerHTML = `<div class="section-label">REPRODUCIBILITY RESULT</div>
      <div class="result-card"><img src="${data.asset_url}" alt="Generated evidence-bound visual">
      <div class="metrics"><div class="metric"><b>${Math.round(data.score * 100)}%</b><span>GUARDRAIL SCORE</span></div>
      <div class="metric"><b>${data.attempts}</b><span>ATTEMPTS</span></div><div class="metric"><b>${data.status === "accepted" ? "PASS" : "REVIEW"}</b><span>STATUS</span></div></div>
      <div class="hash">sha256:${data.canonical_sha256}</div>
      <div class="links"><a href="${data.asset_url}" target="_blank">Open asset</a><a href="${data.manifest_url}" target="_blank">Inspect manifest</a></div></div>`;
  } catch (error) {
    result.innerHTML = `<div class="section-label">RUN ERROR</div><div class="placeholder"><p>${error.message}</p></div>`;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Generate with evidence guardrails";
  }
});

