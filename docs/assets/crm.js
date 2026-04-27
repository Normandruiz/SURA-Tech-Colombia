/* ============================================================
   CRM page · app.js
   Datos diarios + filtros por fecha + insights
   ============================================================ */

const SEGURO_COLORS = {
  "Autos":         "#00359C",
  "Motos":         "#00AEC7",
  "Arrendamiento": "#2D6DF6",
  "Viajes":        "#9333EA",
};

const fmtCurrency  = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(v);
const fmtCurrencyD = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(v);
const fmtNumber    = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct       = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";

let DATA = null;
let CHARTS = {};

async function loadData() {
  const res = await fetch("assets/data_crm.json", { cache: "no-store" });
  return res.json();
}

/* ---------- helpers ---------- */
function ymd(date) {
  return date.toISOString().slice(0, 10);
}

function parseISO(s) {
  return new Date(s + "T00:00:00");
}

/* ---------- filtrado ---------- */
let SEGURO_ACTIVO = "all";

function getFilteredDays() {
  const from   = document.querySelector("#date-from").value;
  const to     = document.querySelector("#date-to").value;
  const seguro = SEGURO_ACTIVO;

  const seguros = (seguro === "all")
    ? Object.keys(DATA.seguros)
    : [seguro];

  const out = [];
  for (const s of seguros) {
    const dias = DATA.seguros[s]?.diarios || [];
    for (const d of dias) {
      if (from && d.fecha < from) continue;
      if (to && d.fecha > to) continue;
      // Filtrar dias vacios (futuros sin data: requeridos > 0 pero todo lo demas null/0)
      const tieneData = (d.recibidos_sf || 0) > 0
                     || (d.total_pauta || 0) > 0
                     || (d.consumo_google || 0) > 0
                     || (d.consumo_meta || 0) > 0
                     || (d.leads_google || 0) > 0
                     || (d.leads_meta || 0) > 0;
      if (!tieneData) continue;
      out.push({ ...d, seguro: s });
    }
  }
  out.sort((a, b) => a.fecha.localeCompare(b.fecha));
  return out;
}

/* ---------- KPIs del rango ---------- */
function renderRangeKPIs(days) {
  const sf = days.reduce((a,d) => a + (d.recibidos_sf || 0), 0);
  const pauta = days.reduce((a,d) => a + (d.total_pauta || 0), 0);
  const requeridos = days.reduce((a,d) => a + (d.requeridos || 0), 0);
  const inv_g = days.reduce((a,d) => a + (d.consumo_google || 0), 0);
  const inv_m = days.reduce((a,d) => a + (d.consumo_meta || 0), 0);
  const inv_b = days.reduce((a,d) => a + (d.consumo_bing || 0), 0);
  const inv_total = inv_g + inv_m + inv_b;

  const cumpl = requeridos ? sf / requeridos : 0;
  const cpl   = sf ? inv_total / sf : 0;

  document.querySelector("#kpi-rango-sf .value")    .textContent = fmtNumber(sf);
  document.querySelector("#kpi-rango-pauta .value") .textContent = fmtNumber(pauta);
  document.querySelector("#kpi-rango-cumpl .value") .textContent = fmtPct(cumpl);
  document.querySelector("#kpi-rango-cpl .value")   .textContent = fmtCurrencyD(cpl);
}

/* ---------- charts ---------- */
function lineChart(canvasId, labels, datasets, yMode = "number") {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
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
        x: { ticks: { font: { family: "Inter", size: 10 }, maxRotation: 50, autoSkipPadding: 30 }, grid: { display: false } },
      },
    },
  });
}

/* dias filtrados -> grafico SF por dia, una linea por seguro */
function renderCharts(days) {
  // Agrupar por fecha y por seguro
  const dates = [...new Set(days.map(d => d.fecha))].sort();
  const seguros = [...new Set(days.map(d => d.seguro))];

  // SF por seguro por dia
  const sfDatasets = seguros.map(s => ({
    label: s,
    data: dates.map(date => {
      const d = days.find(x => x.fecha === date && x.seguro === s);
      return d ? (d.recibidos_sf || 0) : null;
    }),
    borderColor: SEGURO_COLORS[s] || "#888",
    backgroundColor: (SEGURO_COLORS[s] || "#888") + "22",
    tension: 0.3, borderWidth: 2, pointRadius: 1.5, pointHoverRadius: 5, spanGaps: true,
  }));
  lineChart("chart-sf-daily", dates, sfDatasets, "number");

  // SF total vs Pauta total por dia (suma todos seguros)
  const sumByDate = (key) => dates.map(date => days.filter(x=>x.fecha===date).reduce((a,d)=>a+(d[key]||0),0));
  lineChart("chart-sf-vs-pauta", dates, [
    { label: "RECIBIDOS (SF)", data: sumByDate("recibidos_sf"), borderColor: "#00359C", backgroundColor: "#00359C22", tension: 0.3, borderWidth: 2.5, pointRadius: 1.5, pointHoverRadius: 5 },
    { label: "Total Pauta",    data: sumByDate("total_pauta"),  borderColor: "#00AEC7", backgroundColor: "#00AEC722", tension: 0.3, borderWidth: 2, pointRadius: 1.5, pointHoverRadius: 5, borderDash: [4,4] },
    { label: "Requeridos",     data: sumByDate("requeridos"),    borderColor: "#9333EA", backgroundColor: "transparent", tension: 0.0, borderWidth: 1.5, pointRadius: 0, borderDash: [2,3] },
  ], "number");

  // Inversion diaria total
  const invDates = sumByDate("consumo_google").map((_, i) =>
    (sumByDate("consumo_google")[i] || 0) + (sumByDate("consumo_meta")[i] || 0) + (sumByDate("consumo_bing")[i] || 0));
  lineChart("chart-inversion-daily", dates, [
    { label: "Google",   data: sumByDate("consumo_google"), borderColor: "#00359C", backgroundColor: "#00359C44", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
    { label: "Meta",     data: sumByDate("consumo_meta"),   borderColor: "#9333EA", backgroundColor: "#9333EA44", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
    { label: "Bing",     data: sumByDate("consumo_bing"),   borderColor: "#00AEC7", backgroundColor: "#00AEC744", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
  ], "currency");

  // Cumplimiento mensual (independiente del filtro de fechas para tener historico)
  const meses = {};
  for (const s of Object.keys(DATA.seguros)) {
    for (const [ym, b] of Object.entries(DATA.seguros[s].mensual || {})) {
      if (!b.cumpl_sf_vs_req) continue;
      meses[ym] = meses[ym] || {};
      meses[ym][s] = b.cumpl_sf_vs_req;
    }
  }
  const monthsSorted = Object.keys(meses).sort();
  const cumplDatasets = Object.keys(DATA.seguros).map(s => ({
    label: s,
    data: monthsSorted.map(m => meses[m]?.[s] != null ? meses[m][s] : null),
    borderColor: SEGURO_COLORS[s] || "#888",
    backgroundColor: (SEGURO_COLORS[s] || "#888") + "22",
    tension: 0.3, borderWidth: 2.5, pointRadius: 2, spanGaps: true,
  }));
  lineChart("chart-cumpl-monthly", monthsSorted, cumplDatasets, "pct");
}

/* ---------- tabla resumen por seguro ---------- */
function renderResumenRango(days) {
  const tbody = document.querySelector("#resumen-rango-table tbody");
  const seguros = [...new Set(days.map(d => d.seguro))];
  if (!seguros.length) { tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:20px;">Sin datos en el rango</td></tr>`; return; }
  tbody.innerHTML = seguros.map(s => {
    const sd = days.filter(d => d.seguro === s);
    const sf = sd.reduce((a,d) => a + (d.recibidos_sf || 0), 0);
    const pauta = sd.reduce((a,d) => a + (d.total_pauta || 0), 0);
    const req = sd.reduce((a,d) => a + (d.requeridos || 0), 0);
    const ig = sd.reduce((a,d) => a + (d.consumo_google || 0), 0);
    const im = sd.reduce((a,d) => a + (d.consumo_meta || 0), 0);
    const ib = sd.reduce((a,d) => a + (d.consumo_bing || 0), 0);
    const cumpl_sf  = req ? sf / req : null;
    const cumpl_p   = req ? pauta / req : null;
    const cpl = sf ? (ig+im+ib) / sf : null;
    return `
      <tr>
        <td><strong>${s}</strong></td>
        <td>${sd.length}</td>
        <td>${fmtNumber(sf)}</td>
        <td>${fmtNumber(pauta)}</td>
        <td>${fmtNumber(req)}</td>
        <td class="${cumpl_sf && cumpl_sf < 0.6 ? 'flag-warn' : ''}">${fmtPct(cumpl_sf)}</td>
        <td>${fmtPct(cumpl_p)}</td>
        <td>${fmtCurrency(ig)}</td>
        <td>${fmtCurrency(im)}</td>
        <td>${fmtCurrency(ib)}</td>
        <td>${cpl ? fmtCurrencyD(cpl) : "—"}</td>
      </tr>`;
  }).join("");
}

/* ---------- tabla diaria ---------- */
function renderDailyTable(days) {
  const tbody = document.querySelector("#daily-table tbody");
  const slice = days.slice(-200).reverse();
  if (!slice.length) { tbody.innerHTML = `<tr><td colspan="15" style="text-align:center;padding:20px;">Sin datos en el rango</td></tr>`; return; }
  tbody.innerHTML = slice.map(d => {
    const cumpl_sf_pauta = d.total_pauta ? (d.recibidos_sf || 0) / d.total_pauta : null;
    return `
      <tr>
        <td>${d.fecha}</td>
        <td><span class="badge" style="background:${SEGURO_COLORS[d.seguro]}">${d.seguro}</span></td>
        <td><strong>${fmtNumber(d.recibidos_sf)}</strong></td>
        <td>${fmtNumber(d.recibidos_ga)}</td>
        <td>${fmtNumber(d.requeridos)}</td>
        <td>${fmtNumber(d.total_pauta)}</td>
        <td>${fmtPct(cumpl_sf_pauta)}</td>
        <td>${fmtNumber(d.leads_google)}</td>
        <td>${fmtCurrency(d.consumo_google)}</td>
        <td>${fmtNumber(d.leads_meta)}</td>
        <td>${fmtCurrency(d.consumo_meta)}</td>
        <td>${fmtNumber(d.leads_bing)}</td>
        <td>${fmtCurrency(d.consumo_bing)}</td>
        <td>${fmtNumber(d.sel)}</td>
        <td>${fmtNumber(d.suraco)}</td>
      </tr>`;
  }).join("");
}

/* ---------- insights / recos ---------- */
function renderInsights() {
  const wrap = document.querySelector("#insights-list");
  const items = DATA.insights || [];
  if (!items.length) { wrap.innerHTML = `<div class="empty-state">Sin insights.</div>`; return; }
  wrap.innerHTML = items.map(i => `
    <div class="insight-card severity-${i.severidad}">
      <span class="seguro-tag">${i.seguro}</span>
      <div class="insight-text">
        <div class="insight-title">${i.titulo}</div>
        <div class="insight-detail">${i.detalle}</div>
      </div>
      <span class="severity severity-${i.severidad}">${i.severidad}</span>
    </div>
  `).join("");
}

function renderRecosCRM() {
  const wrap = document.querySelector("#recos-crm");
  const items = DATA.recomendaciones || [];
  wrap.innerHTML = items.map((r, i) => `
    <details class="reco-item">
      <summary>
        <div class="rank">${i+1}</div>
        <div class="title-block">
          <div class="title">${r.titulo}</div>
          <div class="meta">Recomendación CRM · prioridad ${r.prioridad}</div>
        </div>
        <span class="priority ${r.prioridad}">${r.prioridad}</span>
      </summary>
      <div class="reco-detail">
        <p><strong>Qué hacer:</strong> ${r.que_hacer}</p>
        <p><strong>Por qué:</strong> ${r.por_que}</p>
        <p><strong>Impacto:</strong> ${r.impacto}</p>
      </div>
    </details>
  `).join("");
}

/* ---------- presets ---------- */
function applyQuickRange(range) {
  const max = DATA.meta.rango_global.hasta;
  const min = DATA.meta.rango_global.desde;
  const today = new Date(max + "T00:00:00");
  let from, to;
  if (range === "all") { from = min; to = max; }
  else if (range === "7")  { const d = new Date(today); d.setDate(d.getDate()-7);  from = ymd(d); to = max; }
  else if (range === "30") { const d = new Date(today); d.setDate(d.getDate()-30); from = ymd(d); to = max; }
  else if (range === "month") {
    const d = new Date(today); d.setDate(1); from = ymd(d); to = max;
  }
  else if (range === "prev-month") {
    const d = new Date(today); d.setDate(1); d.setMonth(d.getMonth()-1);
    const dEnd = new Date(d.getFullYear(), d.getMonth()+1, 0);
    from = ymd(d); to = ymd(dEnd);
  }
  else if (range === "ytd") {
    const d = new Date(today.getFullYear(), 0, 1); from = ymd(d); to = max;
  }
  document.querySelector("#date-from").value = from;
  document.querySelector("#date-to").value = to;
  refreshAll();
}

function refreshAll() {
  const days = getFilteredDays();
  renderRangeKPIs(days);
  renderCharts(days);
  renderResumenRango(days);
  renderDailyTable(days);
}

/* ---------- main ---------- */
(async function main() {
  try {
    DATA = await loadData();
    // setear input con rango global por default = mes actual
    const max = DATA.meta.rango_global.hasta;
    const today = new Date(max + "T00:00:00");
    const monthStart = new Date(today); monthStart.setDate(1);
    document.querySelector("#date-from").value = ymd(monthStart);
    document.querySelector("#date-to").value = max;
    document.querySelector("#date-from").min = DATA.meta.rango_global.desde;
    document.querySelector("#date-from").max = max;
    document.querySelector("#date-to").min = DATA.meta.rango_global.desde;
    document.querySelector("#date-to").max = max;

    // listeners
    document.querySelector("#date-from").addEventListener("change", refreshAll);
    document.querySelector("#date-to").addEventListener("change", refreshAll);
    // Botones por seguro
    document.querySelectorAll(".seguro-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".seguro-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        SEGURO_ACTIVO = btn.dataset.seguro;
        refreshAll();
      });
    });
    document.querySelectorAll(".quick-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".quick-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        applyQuickRange(btn.dataset.range);
      });
    });
    document.querySelector('.quick-btn[data-range="month"]').classList.add("active");

    refreshAll();
    renderInsights();
    renderRecosCRM();
  } catch (e) {
    console.error(e);
    alert("Error cargando data_crm.json: " + e.message);
  }
})();
