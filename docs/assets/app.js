/* ============================================================
   SURA Tech Colombia · Dashboard · app.js
   Lee docs/assets/data.json y renderiza KPIs, seguros, recos.
   ============================================================ */

const SEGUROS_ORDER = [
  "Arrendamiento", "Salud para Dos", "Motos",
  "Autos", "Salud Animal", "Viajes"
];

const fmtCurrency = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO", {
  style: "currency", currency: "COP", maximumFractionDigits: 0
}).format(v);
const fmtNumber = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const fmtDelta = (v) => {
  if (v == null) return "";
  const sign = v >= 0 ? "↑" : "↓";
  return `${sign} ${Math.abs(v * 100).toFixed(1)}% MoM`;
};

function semaforoFrom(cumplimiento) {
  if (cumplimiento == null) return "amarillo";
  if (cumplimiento >= 0.90) return "verde";
  if (cumplimiento >= 0.60) return "amarillo";
  return "rojo";
}

async function loadData() {
  const res = await fetch("assets/data.json", { cache: "no-store" });
  return res.json();
}

function renderHeader(data) {
  const m = data.meta?.periodo?.mes_actual || "—";
  document.querySelector("#periodo").textContent = m;

  const k = data.kpis_globales || {};
  const d = k.variacion_mom || {};
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
  set("#kpi-inversion", fmtCurrency(k.inversion_total), d.inversion_total);
  set("#kpi-leads", fmtNumber(k.leads_crm_totales), d.leads_crm_totales);
  set("#kpi-cumplimiento", fmtPct(k.cumplimiento_global_pct), d.cumplimiento_global_pct);
  set("#kpi-cpl", fmtCurrency(k.cpl_negocio_promedio), d.cpl_negocio_promedio);
}

function renderAlertas(data) {
  const wrap = document.querySelector("#alertas");
  const items = (data.alertas_criticas || []).filter(a => a.severidad === "critica");
  if (!items.length) { wrap.style.display = "none"; return; }
  wrap.innerHTML = `
    <h3>Alertas críticas — requieren acción inmediata</h3>
    <ul>${items.map(a => `<li><strong>${a.titulo}.</strong> ${a.detalle} <em>→ ${a.accion_sugerida}</em></li>`).join("")}</ul>
  `;
}

function renderSeguros(data) {
  const wrap = document.querySelector("#seguros");
  const bySeguro = Object.fromEntries((data.seguros || []).map(s => [s.nombre, s]));
  wrap.innerHTML = SEGUROS_ORDER.map(nombre => {
    const s = bySeguro[nombre];
    if (!s) {
      return `
        <div class="seguro-card">
          <div class="head">
            <span class="nombre">${nombre}</span>
            <span class="semaforo amarillo" title="Sin datos aún"></span>
          </div>
          <div class="empty-state" style="padding:12px;border:none;background:transparent;">Sin datos — correr extractor</div>
        </div>`;
    }
    const cump = s.cumplimiento_pct;
    const color = semaforoFrom(cump);
    const prog = cump == null ? 0 : Math.min(100, Math.max(0, cump * 100));
    return `
      <div class="seguro-card" onclick="location.hash='#seguro-${nombre.replace(/ /g,'-').toLowerCase()}'">
        <div class="head">
          <span class="nombre">${nombre}</span>
          <span class="semaforo ${color}" title="${fmtPct(cump)}"></span>
        </div>
        <div class="progress-bar"><span style="width:${prog}%"></span></div>
        <div class="metric-row"><span>Leads CRM</span><strong>${fmtNumber(s.leads_crm)} / ${fmtNumber(s.compromiso_leads)}</strong></div>
        <div class="metric-row"><span>CPL Negocio</span><strong>${fmtCurrency(s.cpl_negocio)}</strong></div>
        <div class="metric-row"><span>Inversión</span><strong>${fmtCurrency(s.inversion)}</strong></div>
      </div>`;
  }).join("");
}

function renderRecos(data) {
  const list = document.querySelector("#reco-list");
  const recos = (data.recomendaciones || []).slice(0, 10);
  if (!recos.length) {
    list.innerHTML = `<div class="empty-state">TOP 10 de recomendaciones se completará después del análisis (Paso 5).</div>`;
    return;
  }
  list.innerHTML = recos.map((r, i) => `
    <div class="reco-item">
      <div class="rank">${i+1}</div>
      <div>
        <div class="title">${r.titulo}</div>
        <div class="meta">${r.seguro} · ${r.plataforma} · Impacto: ${r.impacto_esperado || "—"} · Esfuerzo: ${r.esfuerzo || "—"} · Plazo: ${r.plazo || "—"}</div>
      </div>
      <span class="priority ${r.prioridad || "media"}">${r.prioridad || "media"}</span>
    </div>
  `).join("");
}

(async function main() {
  try {
    const data = await loadData();
    renderHeader(data);
    renderAlertas(data);
    renderSeguros(data);
    renderRecos(data);
  } catch (e) {
    console.error(e);
    document.querySelector("#seguros").innerHTML = `<div class="empty-state">Error cargando data.json — ${e.message}</div>`;
  }
})();
