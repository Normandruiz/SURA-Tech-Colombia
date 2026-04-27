/* ============================================================
   SURA Tech Colombia · Dashboard v3 · app.js
   Fuente de verdad: RECIBIDOS (SF) - leads que llegan a Salesforce.
   ============================================================ */

const SURA = { azul: "#00359C", aqua: "#00AEC7", azul_vivo: "#2D6DF6", verde: "#10B981", amarillo: "#F59E0B", rojo: "#DC2626" };
const SEGURO_COLORS = {
  "Autos":         SURA.azul,
  "Motos":         SURA.aqua,
  "Arrendamiento": SURA.azul_vivo,
  "Viajes":        "#9333EA",
};

const fmtCurrency  = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(v);
const fmtCurrencyD = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(v);
const fmtNumber    = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct       = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const fmtDelta     = (v) => v == null ? "" : ((v >= 0 ? "↑" : "↓") + " " + Math.abs(v * 100).toFixed(1) + "% MoM");

let DATA = null;
let MES_ACTIVO_ISO = null;

function semaforoFrom(cumpl, transcurrido = 0.7) {
  if (cumpl == null) return "amarillo";
  const r = cumpl / transcurrido;
  if (r >= 0.9) return "verde";
  if (r >= 0.6) return "amarillo";
  return "rojo";
}

async function loadData() {
  const res = await fetch("assets/data.json", { cache: "no-store" });
  return res.json();
}

/* ---------- selector de mes ---------- */
function renderMesSelector() {
  const sel = document.querySelector("#mes-selector");
  const meses = (DATA.evolucion_mom?.meses || []).slice().reverse();
  const mesesIso = (DATA.evolucion_mom?.meses_iso || []).slice().reverse();
  sel.innerHTML = meses.map((m, i) => `<option value="${mesesIso[i]}">${m}</option>`).join("");
  sel.value = MES_ACTIVO_ISO;
  sel.addEventListener("change", (e) => {
    MES_ACTIVO_ISO = e.target.value;
    renderForMonth();
  });
}

function findMonthData(seguro, mesIso) {
  const serie = DATA.evolucion_mom?.por_seguro?.[seguro] || [];
  return serie.find(s => s.mes_iso === mesIso && !s.vacio);
}

/* ---------- header KPIs ---------- */
function renderHeader() {
  const seguros_p = DATA.meta.scope.seguros_principales;
  let inv = 0, sf = 0, requeridos = 0, pauta = 0, leads_google = 0, leads_meta = 0;
  let sf_prev = 0, requeridos_prev = 0, pauta_prev = 0, inv_prev = 0;

  const mesesIso = DATA.evolucion_mom.meses_iso;
  const idx = mesesIso.indexOf(MES_ACTIVO_ISO);
  const mes_prev_iso = idx > 0 ? mesesIso[idx - 1] : null;

  for (const seguro of seguros_p) {
    const cur = findMonthData(seguro, MES_ACTIVO_ISO);
    if (cur) {
      inv += (cur.consumo_google || 0) + (cur.consumo_meta || 0) + (cur.consumo_bing || 0);
      sf += cur.recibidos_sf || 0;
      requeridos += cur.requeridos || 0;
      pauta += cur.total_pauta || 0;
      leads_google += cur.leads_google || 0;
      leads_meta += cur.leads_meta || 0;
    }
    if (mes_prev_iso) {
      const p = findMonthData(seguro, mes_prev_iso);
      if (p) {
        inv_prev += (p.consumo_google || 0) + (p.consumo_meta || 0) + (p.consumo_bing || 0);
        sf_prev += p.recibidos_sf || 0;
        requeridos_prev += p.requeridos || 0;
        pauta_prev += p.total_pauta || 0;
      }
    }
  }

  const cumpl = requeridos ? sf / requeridos : 0;
  const cumpl_prev = requeridos_prev ? sf_prev / requeridos_prev : 0;
  const cpl = sf ? inv / sf : 0;
  const cpl_prev = sf_prev ? inv_prev / sf_prev : 0;

  const set = (sel, val, prev) => {
    const el = document.querySelector(sel);
    if (!el) return;
    el.querySelector(".value").textContent = val;
    const dEl = el.querySelector(".delta");
    if (prev == null || prev === 0 || isNaN(prev)) { dEl.textContent = ""; return; }
    dEl.textContent = fmtDelta(prev);
    dEl.classList.toggle("up", prev >= 0);
    dEl.classList.toggle("down", prev < 0);
  };

  set("#kpi-inversion",    fmtCurrency(inv),     inv_prev    ? (inv-inv_prev)/inv_prev : null);
  set("#kpi-leads",        fmtNumber(sf),        sf_prev     ? (sf-sf_prev)/sf_prev : null);
  set("#kpi-cumplimiento", fmtPct(cumpl),        cumpl_prev  ? (cumpl-cumpl_prev) : null);
  set("#kpi-cpl",          fmtCurrencyD(cpl),    cpl_prev    ? (cpl-cpl_prev)/cpl_prev : null);
}

/* ---------- alertas ---------- */
function renderAlertas() {
  const wrap = document.querySelector("#alertas");
  const items = (DATA.alertas_criticas || []).filter(a => a.severidad === "critica");
  if (!items.length) { wrap.style.display = "none"; return; }
  wrap.innerHTML = `
    <h3>Alertas críticas — requieren acción inmediata</h3>
    <ul>${items.map(a => `<li><strong>${a.titulo}.</strong> ${a.detalle} <em>→ ${a.accion_sugerida}</em></li>`).join("")}</ul>
  `;
}

/* ---------- tarjetas seguros ---------- */
function renderSeguros() {
  const wrap = document.querySelector("#seguros");
  const transcurrido = DATA.meta.periodo.porcentaje_transcurrido || 0.7;

  wrap.innerHTML = DATA.seguros.map(s => {
    const cur = findMonthData(s.nombre, MES_ACTIVO_ISO) || {};
    const ga = s.google_ads || { kpis: {} };
    const isExtra = !s.es_principal;
    const cumpl = cur.cumpl_sf_vs_req;
    const color = semaforoFrom(cumpl, transcurrido);
    const prog = cumpl == null ? 0 : Math.min(100, Math.max(0, cumpl * 100));

    return `
      <div class="seguro-card ${isExtra ? 'extra' : ''}">
        <div class="head">
          <span class="nombre">${s.nombre} ${isExtra ? '<small>(extra)</small>' : ''}</span>
          <span class="semaforo ${color}" title="${fmtPct(cumpl)}"></span>
        </div>
        ${cumpl != null ? `
        <div class="progress-bar"><span style="width:${Math.min(100,prog)}%"></span></div>
        <div class="metric-row"><span>RECIBIDOS (SF) / Req.</span><strong>${fmtNumber(cur.recibidos_sf)} / ${fmtNumber(cur.requeridos)}</strong></div>
        <div class="metric-row"><span>Cumplimiento SF/Req</span><strong>${fmtPct(cumpl)} <small>(meta ${fmtPct(transcurrido)})</small></strong></div>
        <div class="metric-row"><span>Pauta total</span><strong>${fmtNumber(cur.total_pauta)} <small>(${fmtPct(cur.cumpl_pauta_vs_req)})</small></strong></div>
        <div class="metric-row"><span>CPL Negocio (SF)</span><strong>${fmtCurrencyD(cur.cpl_negocio_sf)}</strong></div>
        ` : `
        <div class="empty-state" style="padding:8px 0;background:transparent;border:none;">Sin tracking CRM — solo data Ads</div>
        `}
        <hr style="border:0;border-top:1px solid var(--sura-gris-claro);margin:10px 0;">
        <div class="metric-row"><span>Inversión Google</span><strong>${fmtCurrency(cur.consumo_google)}</strong></div>
        <div class="metric-row"><span>Leads Google</span><strong>${fmtNumber(cur.leads_google)}</strong></div>
        <div class="metric-row"><span>Inversión Meta</span><strong>${fmtCurrency(cur.consumo_meta)}</strong></div>
        <div class="metric-row"><span>Leads Meta</span><strong>${fmtNumber(cur.leads_meta)}</strong></div>
        <div class="metric-row"><span>Campañas Google Ads</span><strong>${ga.campanias_count || 0}</strong></div>
      </div>`;
  }).join("");
}

/* ---------- TOP 10 recos ---------- */
function renderRecos() {
  const list = document.querySelector("#reco-list");
  const recos = DATA.recomendaciones || [];
  if (!recos.length) { list.innerHTML = `<div class="empty-state">Sin recomendaciones.</div>`; return; }

  const filterChips = document.querySelectorAll("#reco-filters .chip");
  let activeFilter = "all";
  filterChips.forEach(c => c.addEventListener("click", () => {
    filterChips.forEach(x => x.classList.remove("active"));
    c.classList.add("active");
    activeFilter = c.dataset.f;
    drawList();
  }));

  function drawList() {
    const items = recos.filter(r => {
      if (activeFilter === "all") return true;
      if (["critica","alta","media"].includes(activeFilter)) return r.prioridad === activeFilter;
      return (r.plataforma || "").includes(activeFilter);
    });
    list.innerHTML = items.map(r => {
      const realIdx = recos.indexOf(r) + 1;
      const evidencia = (r.evidencia || []).map(e => `<li>${e}</li>`).join("");
      return `
        <details class="reco-item">
          <summary>
            <div class="rank">${realIdx}</div>
            <div class="title-block">
              <div class="title">${r.titulo}</div>
              <div class="meta">${r.seguro} · ${r.plataforma} · esfuerzo ${r.esfuerzo} · plazo ${r.plazo}</div>
            </div>
            <span class="priority ${r.prioridad}">${r.prioridad}</span>
          </summary>
          <div class="reco-detail">
            <p><strong>Qué hacer:</strong> ${r.que_hacer}</p>
            <p><strong>Por qué:</strong> ${r.por_que}</p>
            <p><strong>Impacto esperado:</strong> ${r.impacto}</p>
            ${evidencia ? `<p><strong>Evidencia:</strong></p><ul class="evidence">${evidencia}</ul>` : ""}
          </div>
        </details>`;
    }).join("");
  }
  drawList();
}

/* ---------- gráficos ---------- */
let CHARTS = {};
function lineChart(canvasId, datasets, yMode = "number") {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  const labels = DATA.evolucion_mom.meses;
  const yFmt = (v) => yMode === "pct" ? (v*100).toFixed(0)+"%"
                  : yMode === "currency" ? "$"+fmtNumber(v)
                  : fmtNumber(v);
  CHARTS[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { font: { family: "Inter", size: 11 } } },
        tooltip: { callbacks: { label: (it) => `${it.dataset.label}: ${yFmt(it.parsed.y)}` } },
      },
      scales: {
        y: { ticks: { callback: yFmt, font: { family: "Inter" } }, grid: { color: "rgba(0,53,156,0.05)" } },
        x: { ticks: { font: { family: "Inter", size: 10 }, maxRotation: 50 }, grid: { display: false } },
      },
    },
  });
}

function renderCharts() {
  const seguros_p = DATA.meta.scope.seguros_principales;
  const buildDataset = (key) => seguros_p.map(seg => ({
    label: seg,
    data: (DATA.evolucion_mom.por_seguro[seg] || []).map(p => p.vacio ? null : (p[key] || 0)),
    borderColor: SEGURO_COLORS[seg], backgroundColor: SEGURO_COLORS[seg] + "22",
    tension: 0.3, borderWidth: 2.5, pointRadius: 3, pointHoverRadius: 6, spanGaps: true,
  }));
  lineChart("chart-cumpl", buildDataset("cumpl_sf_vs_req"),  "pct");
  lineChart("chart-cpl",   buildDataset("cpl_negocio_sf"),   "currency");
  lineChart("chart-leads", buildDataset("recibidos_sf"),     "number");
  lineChart("chart-inv",   buildDataset("consumo_google"),   "currency");
}

/* ---------- cruces ---------- */
function renderCruces() {
  const wrap = document.querySelector("#cruces");
  const data = DATA.cruces?.por_seguro || [];
  wrap.innerHTML = data.map(c => {
    const ratio = c.ratio_ga_conv_vs_sf;
    const flag = ratio === 0 ? "rojo" : (ratio < 0.5 ? "amarillo" : "verde");
    const flagText = ratio === 0 ? "TRACKING ROTO" : (ratio < 0.5 ? "Google minoritario" : "OK");
    return `
      <div class="cruce-card cruce-${flag}">
        <div class="cruce-head">
          <strong>${c.seguro}</strong>
          <span class="cruce-flag flag-${flag}">${flagText}</span>
        </div>
        <div class="cruce-row"><span>RECIBIDOS (SF)</span><strong>${fmtNumber(c.recibidos_sf)}</strong></div>
        <div class="cruce-row"><span>Total Pauta</span><strong>${fmtNumber(c.total_pauta)} (${(c.ratio_pauta_vs_sf*100).toFixed(0)}% del SF)</strong></div>
        <div class="cruce-row"><span>Conv. Google Ads</span><strong>${fmtNumber(c.google_ads_conv)} (${(ratio*100).toFixed(0)}% del SF)</strong></div>
        <div class="cruce-row"><span>Leads Google (Sheet)</span><strong>${fmtNumber(c.leads_google_sheet)}</strong></div>
        <div class="cruce-row"><span>Leads Meta (Sheet)</span><strong>${fmtNumber(c.leads_meta_sheet)}</strong></div>
        <div class="cruce-row"><span>Leads Bing (Sheet)</span><strong>${fmtNumber(c.leads_bing_sheet)}</strong></div>
        <div class="cruce-row"><span>Inv. Google extractor</span><strong>${fmtCurrency(c.inversion_ga_extractor)}</strong></div>
        <div class="cruce-row"><span>Inv. Google Sheet</span><strong>${fmtCurrency(c.inversion_ga_sheet)}</strong></div>
      </div>`;
  }).join("");
}

/* ---------- optimizaciones ---------- */
function renderOptimizaciones() {
  const tabs = document.querySelectorAll(".opt-tab");
  let activeCat = "escalar";
  tabs.forEach(t => t.addEventListener("click", () => {
    tabs.forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    activeCat = t.dataset.cat;
    drawTable();
  }));
  function drawTable() {
    const tbody = document.querySelector("#opt-table tbody");
    const items = DATA.optimizaciones?.[activeCat] || [];
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--sura-gris-medio);">Sin items en esta categoría.</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map(c => `
      <tr>
        <td>${c.seguro}</td>
        <td><code>${c.nombre}</code></td>
        <td><span class="badge">${c.subtipo}</span></td>
        <td>${fmtCurrencyD(c.presupuesto_diario)}</td>
        <td>${fmtCurrency(c.coste)}</td>
        <td>${fmtNumber(Math.round(c.conversiones))}</td>
        <td>${c.cpa ? fmtCurrencyD(c.cpa) : "—"}</td>
        <td class="${c.cuota_perdida_budget>0.20?'flag-warn':''}">${(c.cuota_perdida_budget*100).toFixed(0)}%</td>
        <td class="${c.cuota_perdida_ranking>0.30?'flag-warn':''}">${(c.cuota_perdida_ranking*100).toFixed(0)}%</td>
        <td title="${c.estado}">${c.estado.length>30?c.estado.slice(0,30)+'…':c.estado}</td>
      </tr>`).join("");
  }
  drawTable();
}

/* ---------- discrepancias / caso negocio ---------- */
function renderDiscrepancias() {
  const wrap = document.querySelector("#discrepancias");
  const d = DATA.discrepancias_y_gaps || {};
  wrap.innerHTML = `
    <ul class="gap-list">
      <li><strong>GA4 eventos:</strong> ${d.ga4_eventos || "—"}</li>
      <li><strong>Meta ad sets:</strong> ${d.meta_ad_sets || "—"}</li>
      <li><strong>Salud para Dos / Animal:</strong> ${d.salud_para_dos_y_animal || "—"}</li>
    </ul>
  `;
}
function renderCasoNegocio() {
  const wrap = document.querySelector("#caso-negocio");
  const c = DATA.caso_negocio || {};
  wrap.innerHTML = `
    <div class="caso-block">
      <h4>Estado actual</h4><p>${c.estado_actual || "—"}</p>
      <h4>Proyección si aplicamos las top 5 recomendaciones</h4><p>${c.proyeccion_si_aplicamos_top5 || "—"}</p>
      <h4>Próximo paso</h4><p>${c.proximo_paso || "—"}</p>
    </div>
  `;
}

function renderForMonth() {
  renderHeader();
  renderSeguros();
  renderMixCanales();
}

/* ---------- Oportunidades cross-canal ---------- */
function renderOportunidades() {
  const wrap = document.querySelector("#oportunidades");
  if (!wrap) return;
  const items = DATA.oportunidades_cross_canal || [];
  if (!items.length) { wrap.innerHTML = `<div class="empty-state">Sin oportunidades detectadas.</div>`; return; }
  wrap.innerHTML = items.map(o => `
    <div class="oport-card">
      <div class="oport-icon">${o.icono || "💡"}</div>
      <div class="oport-content">
        <div class="oport-tipo">${o.tipo}</div>
        <div class="oport-titulo">${o.titulo}</div>
        <div class="oport-detalle">${o.detalle}</div>
        <div class="oport-impacto">
          <div><span class="label">Δ Leads</span><strong>${o.delta_leads || "—"}</strong></div>
          <div><span class="label">Δ CPL</span><strong>${o.delta_cpl || "—"}</strong></div>
        </div>
      </div>
    </div>
  `).join("");
}

/* ---------- Mix de canales ---------- */
function renderMixCanales() {
  const seguros_p = DATA.meta.scope.seguros_principales;
  // leads y inv por canal por seguro
  const dataLeads = {Google: [], Meta: [], Bing: []};
  const dataInv   = {Google: [], Meta: [], Bing: []};
  seguros_p.forEach(s => {
    const cur = findMonthData(s, MES_ACTIVO_ISO) || {};
    dataLeads.Google.push(cur.leads_google || 0);
    dataLeads.Meta.push(cur.leads_meta || 0);
    dataLeads.Bing.push(cur.leads_bing || 0);
    dataInv.Google.push(cur.consumo_google || 0);
    dataInv.Meta.push(cur.consumo_meta || 0);
    dataInv.Bing.push(cur.consumo_bing || 0);
  });
  const C = {
    Google: "#0033A0",
    Meta:   "#9333EA",
    Bing:   "#00AEC7",
  };
  const lineChartBar = (canvasId, datasets, valueFmt) => {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
    CHARTS[canvasId] = new Chart(ctx, {
      type: "bar",
      data: { labels: seguros_p, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { font: { family: "Inter", size: 11 } } },
          tooltip: { callbacks: { label: (it) => `${it.dataset.label}: ${valueFmt(it.parsed.y)}` } },
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, ticks: { callback: valueFmt } },
        },
      },
    });
  };
  lineChartBar("chart-mix-leads", Object.entries(dataLeads).map(([k, v]) => ({
    label: k, data: v, backgroundColor: C[k], borderRadius: 4,
  })), v => fmtNumber(v));
  lineChartBar("chart-mix-inv", Object.entries(dataInv).map(([k, v]) => ({
    label: k, data: v, backgroundColor: C[k], borderRadius: 4,
  })), v => "$" + fmtNumber(v));
}

(async function main() {
  try {
    DATA = await loadData();
    MES_ACTIVO_ISO = DATA.meta.periodo.mes_actual_iso;
    renderMesSelector();
    renderForMonth();
    renderAlertas();
    renderOportunidades();
    renderRecos();
    renderCharts();
    renderCruces();
    if (typeof renderOptimizaciones === "function") renderOptimizaciones();
    renderDiscrepancias();
    renderCasoNegocio();
  } catch (e) {
    console.error(e);
    document.querySelector("#seguros").innerHTML =
      `<div class="empty-state">Error cargando data.json — ${e.message}</div>`;
  }
})();
