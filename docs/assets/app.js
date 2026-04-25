/* ============================================================
   SURA Tech Colombia · Dashboard v2 · app.js
   ============================================================ */

const SURA = { azul: "#00359C", aqua: "#00AEC7", azul_vivo: "#2D6DF6", verde: "#10B981", amarillo: "#F59E0B", rojo: "#DC2626" };
const SEGURO_COLORS = {
  "Autos":         SURA.azul,
  "Motos":         SURA.aqua,
  "Arrendamiento": SURA.azul_vivo,
  "Viajes":        "#9333EA",
};

const fmtCurrency = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(v);
const fmtCurrencyD = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(v);
const fmtNumber = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const fmtDelta = (v) => v == null ? "" : ((v >= 0 ? "↑" : "↓") + " " + Math.abs(v * 100).toFixed(1) + "% MoM");

let DATA = null;
let MES_ACTIVO = null;

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
  sel.innerHTML = meses.map(m => `<option value="${m}">${m}</option>`).join("");
  sel.value = MES_ACTIVO;
  sel.addEventListener("change", (e) => {
    MES_ACTIVO = e.target.value;
    renderForMonth();
  });
}

function findMonthData(seguro, mes) {
  const serie = DATA.evolucion_mom?.por_seguro?.[seguro] || [];
  return serie.find(s => s.mes === mes && !s.vacio);
}

/* ---------- header KPIs (recalculados por mes activo) ---------- */
function renderHeader() {
  const seguros_p = DATA.meta.scope.seguros_principales;
  let inv = 0, leads = 0, compromiso = 0;
  const cpls = [];
  let inv_prev = 0, leads_prev = 0, compromiso_prev = 0;
  const cpls_prev = [];

  const meses = DATA.evolucion_mom.meses; // antiguo->nuevo
  const idx = meses.indexOf(MES_ACTIVO);
  const mes_prev = idx > 0 ? meses[idx - 1] : null;

  for (const seguro of seguros_p) {
    const cur = findMonthData(seguro, MES_ACTIVO);
    if (cur) {
      inv += cur.inversion_total || 0;
      leads += cur.leads_crm || 0;
      compromiso += cur.compromiso || 0;
      if (cur.cpl_negocio) cpls.push(cur.cpl_negocio);
    }
    if (mes_prev) {
      const p = findMonthData(seguro, mes_prev);
      if (p) {
        inv_prev += p.inversion_total || 0;
        leads_prev += p.leads_crm || 0;
        compromiso_prev += p.compromiso || 0;
        if (p.cpl_negocio) cpls_prev.push(p.cpl_negocio);
      }
    }
  }

  const cumpl = compromiso ? leads / compromiso : 0;
  const cumpl_prev = compromiso_prev ? leads_prev / compromiso_prev : 0;
  const cpl_avg = cpls.length ? cpls.reduce((a,b)=>a+b)/cpls.length : 0;
  const cpl_avg_prev = cpls_prev.length ? cpls_prev.reduce((a,b)=>a+b)/cpls_prev.length : 0;

  const set = (sel, val, prev) => {
    const el = document.querySelector(sel);
    if (!el) return;
    el.querySelector(".value").textContent = val;
    const dEl = el.querySelector(".delta");
    if (prev == null || prev === 0) { dEl.textContent = ""; return; }
    dEl.textContent = fmtDelta(prev);
    dEl.classList.toggle("up", prev >= 0);
    dEl.classList.toggle("down", prev < 0);
  };

  set("#kpi-inversion",     fmtCurrency(inv),    inv_prev    ? (inv-inv_prev)/inv_prev : null);
  set("#kpi-leads",         fmtNumber(leads),    leads_prev  ? (leads-leads_prev)/leads_prev : null);
  set("#kpi-cumplimiento",  fmtPct(cumpl),       cumpl_prev  ? (cumpl-cumpl_prev) : null);
  set("#kpi-cpl",           fmtCurrencyD(cpl_avg),cpl_avg_prev? (cpl_avg-cpl_avg_prev)/cpl_avg_prev : null);
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
    const cur = findMonthData(s.nombre, MES_ACTIVO) || {};
    const ga = s.google_ads || { kpis: {} };
    const isExtra = !s.es_principal;
    const cump = cur.cumplimiento;
    const color = semaforoFrom(cump, transcurrido);
    const prog = cump == null ? 0 : Math.min(100, Math.max(0, cump * 100));

    return `
      <div class="seguro-card ${isExtra ? 'extra' : ''}">
        <div class="head">
          <span class="nombre">${s.nombre} ${isExtra ? '<small>(extra)</small>' : ''}</span>
          <span class="semaforo ${color}" title="${fmtPct(cump)}"></span>
        </div>
        ${cump != null ? `
        <div class="progress-bar"><span style="width:${prog}%"></span></div>
        <div class="metric-row"><span>Leads CRM / Compromiso</span><strong>${fmtNumber(cur.leads_crm)} / ${fmtNumber(cur.compromiso)}</strong></div>
        <div class="metric-row"><span>Cumplimiento</span><strong>${fmtPct(cump)} <small>(meta ${fmtPct(transcurrido)})</small></strong></div>
        <div class="metric-row"><span>CPL Negocio</span><strong>${fmtCurrencyD(cur.cpl_negocio)}</strong></div>
        <div class="metric-row"><span>Inversión total</span><strong>${fmtCurrency(cur.inversion_total)}</strong></div>
        ` : `
        <div class="empty-state" style="padding:8px 0;background:transparent;border:none;">Sin tracking CRM — solo data Ads</div>
        `}
        <hr style="border:0;border-top:1px solid var(--sura-gris-claro);margin:10px 0;">
        <div class="metric-row"><span>Google Ads inv.</span><strong>${fmtCurrency(ga.kpis.coste_usd)}</strong></div>
        <div class="metric-row"><span>Google Ads conv.</span><strong>${fmtNumber(Math.round(ga.kpis.conversiones || 0))}</strong></div>
        <div class="metric-row"><span>Campañas activas</span><strong>${ga.campanias_count || 0}</strong></div>
      </div>`;
  }).join("");
}

/* ---------- TOP 10 recomendaciones ---------- */
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
      return r.plataforma === activeFilter;
    });
    list.innerHTML = items.map((r, i) => {
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

/* ---------- gráficos MoM ---------- */
let CHARTS = {};
function lineChart(canvasId, datasets, yPctOrCurrency = "number") {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  const meses = DATA.evolucion_mom.meses;
  const yFmt = (v) => yPctOrCurrency === "pct" ? (v*100).toFixed(0)+"%"
                  : yPctOrCurrency === "currency" ? "$"+fmtNumber(v)
                  : fmtNumber(v);
  CHARTS[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: meses, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { font: { family: "Inter", size: 11 } } },
        tooltip: {
          callbacks: { label: (it) => `${it.dataset.label}: ${yFmt(it.parsed.y)}` },
        },
      },
      scales: {
        y: { ticks: { callback: yFmt, font: { family: "Inter" } }, grid: { color: "rgba(0,53,156,0.05)" } },
        x: { ticks: { font: { family: "Inter" } }, grid: { display: false } },
      },
    },
  });
}

function renderCharts() {
  const seguros_p = DATA.meta.scope.seguros_principales;
  const buildDataset = (key, factor=1) => seguros_p.map(seg => ({
    label: seg,
    data: (DATA.evolucion_mom.por_seguro[seg] || []).map(p => p.vacio ? null : (p[key] || 0) * factor),
    borderColor: SEGURO_COLORS[seg], backgroundColor: SEGURO_COLORS[seg] + "22",
    tension: 0.3, borderWidth: 2.5, pointRadius: 4, pointHoverRadius: 6,
  }));
  lineChart("chart-cumpl", buildDataset("cumplimiento"), "pct");
  lineChart("chart-cpl",   buildDataset("cpl_negocio"),  "currency");
  lineChart("chart-leads", buildDataset("leads_crm"),    "number");
  lineChart("chart-inv",   buildDataset("inversion_total"), "currency");
}

/* ---------- cruces ---------- */
function renderCruces() {
  const wrap = document.querySelector("#cruces");
  const data = DATA.cruces?.por_seguro || [];
  wrap.innerHTML = data.map(c => {
    const ratio = c.ratio_ga_conv_vs_crm;
    const flag = ratio === 0 ? "rojo" : (ratio < 0.5 ? "amarillo" : "verde");
    const flagText = ratio === 0
      ? "TRACKING ROTO"
      : (ratio < 0.5 ? "Google Ads minoritario" : "OK");
    return `
      <div class="cruce-card cruce-${flag}">
        <div class="cruce-head">
          <strong>${c.seguro}</strong>
          <span class="cruce-flag flag-${flag}">${flagText}</span>
        </div>
        <div class="cruce-row"><span>Leads CRM</span><strong>${fmtNumber(c.leads_crm)}</strong></div>
        <div class="cruce-row"><span>Conversiones Google Ads</span><strong>${fmtNumber(c.google_ads_conv)}</strong></div>
        <div class="cruce-row"><span>Ratio GA / CRM</span><strong>${(ratio*100).toFixed(0)}%</strong></div>
        <div class="cruce-row"><span>Leads via Meta (CRM)</span><strong>${fmtNumber(c.leads_meta_crm)}</strong></div>
        <div class="cruce-row"><span>Leads via otros canales</span><strong>${fmtNumber(c.leads_otros)}</strong></div>
        <div class="cruce-row"><span>Inv. Google (extractor)</span><strong>${fmtCurrency(c.inversion_ga_extractor)}</strong></div>
        <div class="cruce-row"><span>Inv. Google (CRM)</span><strong>${fmtCurrency(c.inversion_ga_crm)}</strong></div>
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

/* ---------- discrepancias y caso negocio ---------- */
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

/* ---------- render por mes ---------- */
function renderForMonth() {
  renderHeader();
  renderSeguros();
}

/* ---------- main ---------- */
(async function main() {
  try {
    DATA = await loadData();
    MES_ACTIVO = DATA.meta.periodo.mes_actual;
    renderMesSelector();
    renderForMonth();
    renderAlertas();
    renderRecos();
    renderCharts();
    renderCruces();
    renderOptimizaciones();
    renderDiscrepancias();
    renderCasoNegocio();
  } catch (e) {
    console.error(e);
    document.querySelector("#seguros").innerHTML =
      `<div class="empty-state">Error cargando data.json — ${e.message}</div>`;
  }
})();
