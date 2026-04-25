/* ============================================================
   SURA Tech Colombia - Dashboard - app.js
   ============================================================ */

const fmtCurrency = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", {
  maximumFractionDigits: 0, minimumFractionDigits: 0,
}).format(v);
const fmtNumber = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const fmtDelta = (v) => {
  if (v == null) return "";
  const sign = v >= 0 ? "↑" : "↓";
  return `${sign} ${Math.abs(v * 100).toFixed(1)}% MoM`;
};

function semaforoFrom(cumpl, transcurrido = 0.7) {
  if (cumpl == null) return "amarillo";
  const ratio = cumpl / transcurrido;
  if (ratio >= 0.9) return "verde";
  if (ratio >= 0.6) return "amarillo";
  return "rojo";
}

async function loadData() {
  const res = await fetch("assets/data.json", { cache: "no-store" });
  return res.json();
}

function renderHeader(data) {
  document.querySelector("#periodo").textContent = data.meta.periodo.mes_actual || "—";
  const k = data.kpis_globales || {};
  const set = (sel, val, delta) => {
    const el = document.querySelector(sel);
    if (!el) return;
    el.querySelector(".value").textContent = val;
    const dEl = el.querySelector(".delta");
    if (delta == null || delta === "") { dEl.textContent = ""; return; }
    dEl.textContent = fmtDelta(delta);
    dEl.classList.toggle("up", delta >= 0);
    dEl.classList.toggle("down", delta < 0);
  };
  set("#kpi-inversion", fmtCurrency(k.inversion_total));
  set("#kpi-leads", fmtNumber(k.leads_crm_totales));
  set("#kpi-cumplimiento", fmtPct(k.cumplimiento_global_pct));
  set("#kpi-cpl", fmtCurrency(k.cpl_negocio_promedio));
}

function renderAlertas(data) {
  const wrap = document.querySelector("#alertas");
  const items = (data.alertas_criticas || []).filter(a => a.severidad === "critica");
  if (!items.length) { wrap.style.display = "none"; return; }
  wrap.innerHTML = `
    <h3>Alertas críticas — requieren acción inmediata</h3>
    <ul>${items.map(a =>
      `<li><strong>${a.titulo}.</strong> ${a.detalle} <em>→ ${a.accion_sugerida}</em></li>`
    ).join("")}</ul>
  `;
}

function renderSeguros(data) {
  const wrap = document.querySelector("#seguros");
  const transcurrido = data.meta.periodo.porcentaje_transcurrido || 0.7;

  const cards = data.seguros.map(s => {
    const c = s.crm || {};
    const ga = s.google_ads || { kpis: {} };
    const cump = c.cumplimiento_pct;
    const color = semaforoFrom(cump, transcurrido);
    const prog = cump == null ? 0 : Math.min(100, Math.max(0, cump * 100));
    const isExtra = !s.es_principal;

    return `
      <div class="seguro-card ${isExtra ? 'extra' : ''}">
        <div class="head">
          <span class="nombre">${s.nombre} ${isExtra ? '<small>(extra)</small>' : ''}</span>
          <span class="semaforo ${color}" title="${fmtPct(cump)}"></span>
        </div>
        ${cump != null ? `
        <div class="progress-bar"><span style="width:${prog}%"></span></div>
        <div class="metric-row"><span>Leads CRM</span><strong>${fmtNumber(c.leads_crm)} / ${fmtNumber(c.compromiso_leads)}</strong></div>
        <div class="metric-row"><span>Cumplimiento</span><strong>${fmtPct(cump)} <small>(meta ${fmtPct(transcurrido)})</small></strong></div>
        <div class="metric-row"><span>CPL Negocio</span><strong>${fmtCurrency(c.cpl_negocio)}</strong></div>
        ` : `
        <div class="empty-state" style="padding:8px 0;background:transparent;border:none;">Sin tracking CRM — solo data Ads</div>
        `}
        <div class="metric-row"><span>Google Ads inv.</span><strong>${fmtCurrency(ga.kpis.coste_usd)}</strong></div>
        <div class="metric-row"><span>Google Ads conv.</span><strong>${fmtNumber(Math.round(ga.kpis.conversiones || 0))}</strong></div>
        <div class="metric-row"><span>Campañas activas</span><strong>${ga.campanias_count || 0}</strong></div>
      </div>`;
  }).join("");

  wrap.innerHTML = cards;
}

function renderRecos(data) {
  const list = document.querySelector("#reco-list");
  const recos = data.recomendaciones || [];
  if (!recos.length) {
    list.innerHTML = `<div class="empty-state">Sin recomendaciones generadas todavía.</div>`;
    return;
  }
  list.innerHTML = recos.map((r, i) => `
    <details class="reco-item">
      <summary>
        <div class="rank">${i+1}</div>
        <div class="title-block">
          <div class="title">${r.titulo}</div>
          <div class="meta">${r.seguro} · ${r.plataforma} · Esfuerzo: ${r.esfuerzo} · Plazo: ${r.plazo}</div>
        </div>
        <span class="priority ${r.prioridad}">${r.prioridad}</span>
      </summary>
      <div class="reco-detail">
        <p><strong>¿Qué hacer?</strong> ${r.que_hacer}</p>
        <p><strong>¿Por qué?</strong> ${r.por_que}</p>
        <p><strong>Impacto esperado:</strong> ${r.impacto}</p>
      </div>
    </details>
  `).join("");
}

function renderDiscrepancias(data) {
  const wrap = document.querySelector("#discrepancias");
  if (!wrap) return;
  const d = data.discrepancias_y_gaps || {};
  wrap.innerHTML = `
    <ul class="gap-list">
      <li><strong>GA4 eventos:</strong> ${d.ga4_eventos || "—"}</li>
      <li><strong>Meta ad sets:</strong> ${d.meta_ad_sets || "—"}</li>
      <li><strong>Salud para Dos / Animal:</strong> ${d.salud_para_dos_y_animal || "—"}</li>
    </ul>
  `;
}

function renderCasoNegocio(data) {
  const wrap = document.querySelector("#caso-negocio");
  if (!wrap) return;
  const c = data.caso_negocio || {};
  wrap.innerHTML = `
    <div class="caso-block">
      <h4>Estado actual</h4>
      <p>${c.estado_actual || "—"}</p>
      <h4>Proyección si aplicamos top 5 recomendaciones</h4>
      <p>${c.proyeccion_si_aplicamos_top5 || "—"}</p>
      <h4>Próximo paso</h4>
      <p>${c.proximo_paso || "—"}</p>
    </div>
  `;
}

(async function main() {
  try {
    const data = await loadData();
    renderHeader(data);
    renderAlertas(data);
    renderSeguros(data);
    renderRecos(data);
    renderDiscrepancias(data);
    renderCasoNegocio(data);
  } catch (e) {
    console.error(e);
    document.querySelector("#seguros").innerHTML =
      `<div class="empty-state">Error cargando data.json — ${e.message}</div>`;
  }
})();
