const API = "";  // same-origin
let allSuppliers = [];
let currentSupplierId = null;

// ---------------------------------------------------------------------------
// utils
// ---------------------------------------------------------------------------

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${txt}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function stars(rating) {
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

function bandClass(band) {
  return band || "na";
}

// ---------------------------------------------------------------------------
// list rendering
// ---------------------------------------------------------------------------

async function loadSuppliers() {
  allSuppliers = await api("/v1/suppliers/with-scores");
  renderCards();
}

function renderCards() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const bandFilter = document.getElementById("band-filter").value;
  const sortBy = document.getElementById("sort").value;

  let filtered = allSuppliers.filter(s => {
    if (q && !(s.legal_name.toLowerCase().includes(q) || s.display_name.toLowerCase().includes(q))) return false;
    if (bandFilter && s.band !== bandFilter) return false;
    return true;
  });

  filtered.sort((a, b) => {
    if (sortBy === "score-desc") return (b.score ?? -1) - (a.score ?? -1);
    if (sortBy === "score-asc") return (a.score ?? 9999) - (b.score ?? 9999);
    return a.display_name.localeCompare(b.display_name);
  });

  const container = document.getElementById("cards");
  container.innerHTML = "";

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty">No suppliers match your filters.</div>';
  }

  for (const s of filtered) {
    const card = el(`
      <div class="card" data-id="${s.id}">
        <div class="card-head">
          <div>
            <h3 class="card-name">${escapeHtml(s.display_name)}</h3>
            <div class="card-meta">${escapeHtml(s.category || "—")} · ${escapeHtml(s.pincode || "—")}</div>
            ${s.band ? `<span class="band-tag ${s.band}">${s.band}</span>` : ""}
          </div>
          <div class="score-pill ${bandClass(s.band)}">
            ${s.score ?? "—"}
          </div>
        </div>
        <div class="badges">
          ${s.pan_verified ? '<span class="badge ok">PAN ✓</span>' : '<span class="badge warn">PAN ✗</span>'}
          ${s.gstin_verified ? '<span class="badge ok">GSTIN ✓</span>' : '<span class="badge warn">GSTIN ✗</span>'}
          ${s.cin_verified ? '<span class="badge ok">CIN ✓</span>' : ''}
          ${s.watchlist_hit ? '<span class="badge bad">Watchlist hit</span>' : ''}
          <span class="badge">${s.review_count} review${s.review_count === 1 ? "" : "s"}</span>
        </div>
      </div>
    `);
    card.addEventListener("click", () => openDrawer(s.id));
    container.appendChild(card);
  }

  document.getElementById("counts").textContent =
    `${filtered.length} of ${allSuppliers.length} supplier${allSuppliers.length === 1 ? "" : "s"}`;
}

// ---------------------------------------------------------------------------
// detail drawer
// ---------------------------------------------------------------------------

async function openDrawer(supplierId) {
  currentSupplierId = supplierId;
  document.getElementById("drawer").classList.remove("hidden");
  document.getElementById("drawer-backdrop").classList.remove("hidden");
  await renderDrawer();
}

function closeDrawer() {
  document.getElementById("drawer").classList.add("hidden");
  document.getElementById("drawer-backdrop").classList.add("hidden");
  currentSupplierId = null;
}

async function renderDrawer() {
  const id = currentSupplierId;
  if (!id) return;

  const content = document.getElementById("drawer-content");
  content.innerHTML = '<div class="empty">Loading...</div>';

  const [sup, score, reviews, ledger] = await Promise.all([
    api(`/v1/suppliers/${id}`),
    api(`/v1/suppliers/${id}/trust-score`).catch(() => null),
    api(`/v1/suppliers/${id}/reviews`),
    api(`/v1/suppliers/${id}/ledger`),
  ]);

  const band = score?.band || "na";
  const factors = score?.factors || [];

  content.innerHTML = `
    <div class="detail-head">
      <h2>${escapeHtml(sup.display_name)}</h2>
      <div class="meta">${escapeHtml(sup.legal_name)} · ${escapeHtml(sup.category || "—")}</div>
    </div>

    <div class="detail-score-row">
      <div class="big-score ${band}">${score?.score ?? "—"}</div>
      <div>
        <div><strong>${(band || "no score").toUpperCase()}</strong></div>
        <div style="color: var(--muted); font-size: 12px;">
          Model ${score?.model_version || "—"} · ${score ? fmtDate(score.computed_at) : ""}
        </div>
      </div>
      <div style="margin-left: auto; display: flex; gap: 6px;">
        <button class="btn small" id="btn-reverify">Re-verify</button>
        <button class="btn small" id="btn-recompute">Recompute</button>
      </div>
    </div>

    <div class="tabs">
      <button class="tab active" data-tab="score">Score & factors</button>
      <button class="tab" data-tab="reviews">Reviews (${reviews.length})</button>
      <button class="tab" data-tab="ledger">Ledger (${ledger.length})</button>
      <button class="tab" data-tab="overview">Overview</button>
    </div>

    <div class="tab-panel" data-panel="score">
      ${factors.length === 0 ? '<div class="empty">No score yet.</div>' : factors.map(f => `
        <div class="factor-row ${f.contribution > 0 ? "pos" : f.contribution < 0 ? "neg" : "neutral"}">
          <div>
            <div class="name">${escapeHtml(f.name)}</div>
            <div class="detail">${escapeHtml(f.detail)}</div>
          </div>
          <div class="contrib ${f.contribution > 0 ? "pos" : f.contribution < 0 ? "neg" : ""}">
            ${f.contribution > 0 ? "+" : ""}${f.contribution}
          </div>
        </div>
      `).join("")}
    </div>

    <div class="tab-panel hidden" data-panel="reviews">
      <form class="review-form" id="review-form">
        <strong style="font-size: 13px;">Add a buyer review</strong>
        <div class="form-row">
          <label>Buyer name<input name="buyer_name" required /></label>
          <label>Rating
            <select name="rating">
              <option value="5">★★★★★ (5)</option>
              <option value="4">★★★★☆ (4)</option>
              <option value="3" selected>★★★☆☆ (3)</option>
              <option value="2">★★☆☆☆ (2)</option>
              <option value="1">★☆☆☆☆ (1)</option>
            </select>
          </label>
        </div>
        <label>Comment<textarea name="comment" rows="2"></textarea></label>
        <div class="checks">
          <label><input type="checkbox" name="on_time_delivery" checked /> On-time delivery</label>
          <label><input type="checkbox" name="dispute" /> Dispute filed</label>
        </div>
        <button class="btn primary small" type="submit" style="align-self: flex-start;">Submit review</button>
      </form>
      ${reviews.length === 0 ? '<div class="empty">No reviews yet.</div>' : reviews.map(r => `
        <div class="review">
          <div class="review-head">
            <span class="review-buyer">${escapeHtml(r.buyer_name)}</span>
            <span class="stars">${stars(r.rating)}</span>
          </div>
          ${r.comment ? `<div class="review-comment">${escapeHtml(r.comment)}</div>` : ""}
          <div class="review-flags">
            <span class="badge ${r.on_time_delivery ? "ok" : "warn"}">
              ${r.on_time_delivery ? "On time" : "Late"}
            </span>
            ${r.dispute ? '<span class="badge bad">Dispute</span>' : ""}
            <span class="badge">${fmtDate(r.created_at)}</span>
          </div>
        </div>
      `).join("")}
    </div>

    <div class="tab-panel hidden" data-panel="ledger">
      <div style="margin-bottom: 12px;">
        <button class="btn small" id="btn-verify-chain">Verify chain integrity</button>
        <div id="verify-result"></div>
      </div>
      ${ledger.map(ev => `
        <div class="ledger-event">
          <div class="event-type">${escapeHtml(ev.event_type)} <span style="color: var(--muted); font-weight: normal;">· ${escapeHtml(ev.actor)} · ${fmtDate(ev.occurred_at)}</span></div>
          <div class="ledger-payload">${escapeHtml(JSON.stringify(ev.payload, null, 2))}</div>
          <div class="ledger-meta">
            chain_hash: ${ev.chain_hash.substring(0, 20)}…
          </div>
        </div>
      `).join("")}
    </div>

    <div class="tab-panel hidden" data-panel="overview">
      <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
        <tbody>
          ${[
            ["Status", sup.status],
            ["PAN", sup.pan || "—"],
            ["GSTIN", sup.gstin || "—"],
            ["CIN", sup.cin || "—"],
            ["Category", sup.category || "—"],
            ["Address", sup.address || "—"],
            ["Pincode", sup.pincode || "—"],
            ["Incorporated on", fmtDate(sup.incorporated_on)],
            ["GST registered on", fmtDate(sup.gst_registered_on)],
            ["Onboarded at", fmtDate(sup.onboarded_at)],
            ["GST filings on time", `${sup.gst_filings_on_time}/${sup.gst_filings_total}`],
            ["Director changes (12m)", sup.director_changes_12m],
            ["Suppliers at same pincode", sup.shared_address_count],
            ["Watchlist hit", sup.watchlist_hit ? "Yes ⚠️" : "No"],
          ].map(([k, v]) => `
            <tr style="border-bottom: 1px solid var(--border);">
              <td style="padding: 8px 8px 8px 0; color: var(--muted);">${k}</td>
              <td style="padding: 8px 0;">${escapeHtml(v)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  // tab switching
  content.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      content.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      content.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
      tab.classList.add("active");
      content.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.remove("hidden");
    });
  });

  // re-verify
  document.getElementById("btn-reverify").addEventListener("click", async () => {
    await api(`/v1/suppliers/${id}/verify`, { method: "POST" });
    await loadSuppliers();
    await renderDrawer();
  });

  // recompute
  document.getElementById("btn-recompute").addEventListener("click", async () => {
    await api(`/v1/suppliers/${id}/trust-score/recompute`, { method: "POST" });
    await loadSuppliers();
    await renderDrawer();
  });

  // verify chain
  document.getElementById("btn-verify-chain").addEventListener("click", async () => {
    const r = await api(`/v1/suppliers/${id}/ledger/verify`);
    const div = document.getElementById("verify-result");
    if (r.valid) {
      div.innerHTML = `<div class="verify-status valid">✓ Chain valid · ${r.events_verified} events verified</div>`;
    } else {
      div.innerHTML = `<div class="verify-status invalid">✗ Tamper detected at event ${r.broken_at_event_id} — ${r.reason}</div>`;
    }
  });

  // add review
  document.getElementById("review-form").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = {
      buyer_name: fd.get("buyer_name"),
      rating: parseInt(fd.get("rating"), 10),
      comment: fd.get("comment") || null,
      on_time_delivery: fd.get("on_time_delivery") === "on",
      dispute: fd.get("dispute") === "on",
    };
    await api(`/v1/suppliers/${id}/reviews`, {
      method: "POST", body: JSON.stringify(body),
    });
    await loadSuppliers();
    await renderDrawer();
  });
}

// ---------------------------------------------------------------------------
// onboard modal
// ---------------------------------------------------------------------------

function openModal() { document.getElementById("onboard-modal").classList.remove("hidden"); }
function closeModal() {
  document.getElementById("onboard-modal").classList.add("hidden");
  document.getElementById("onboard-form").reset();
}

async function submitOnboard(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {};
  for (const [k, v] of fd.entries()) {
    if (v) body[k] = v;
  }
  // dates → ISO
  if (body.incorporated_on) body.incorporated_on = new Date(body.incorporated_on).toISOString();
  if (body.gst_registered_on) body.gst_registered_on = new Date(body.gst_registered_on).toISOString();

  const newSup = await api("/v1/suppliers", {
    method: "POST", body: JSON.stringify(body),
  });
  closeModal();
  await loadSuppliers();
  openDrawer(newSup.id);
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("search").addEventListener("input", renderCards);
  document.getElementById("band-filter").addEventListener("change", renderCards);
  document.getElementById("sort").addEventListener("change", renderCards);
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
  document.getElementById("btn-new-supplier").addEventListener("click", openModal);
  document.getElementById("onboard-cancel").addEventListener("click", closeModal);
  document.getElementById("onboard-form").addEventListener("submit", submitOnboard);
  loadSuppliers();
});
