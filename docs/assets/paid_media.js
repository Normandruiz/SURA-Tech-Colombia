/* ============================================================
   Paid Media page · app.js
   ============================================================ */

const SEGURO_COLORS = {
  "Autos":         "#00359C",
  "Motos":         "#00AEC7",
  "Arrendamiento": "#2D6DF6",
  "Viajes":        "#9333EA",
};

const SUBTIPO_COLORS = {
  "PMAX":             "#00359C",
  "SEARCH_SEGMENT":   "#00AEC7",
  "SEARCH_RETENTION": "#2D6DF6",
  "SEARCH_CONQUEST":  "#9333EA",
  "OTRO":             "#6B7280",
};

const fmtCurrency  = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(v);
const fmtCurrencyD = (v) => v == null ? "—" : "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(v);
const fmtNumber    = (v) => v == null ? "—" : new Intl.NumberFormat("es-CO").format(v);
const fmtPct       = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";

let DATA = null;
let CHARTS = {};
let SEGURO_ACTIVO = "all";

async function loadData() {
  const res = await fetch("assets/data_paid_media.json", { cache: "no-store" });
  return res.json();
}

function ymd(d) { return d.toISOString().slice(0, 10); }

function getActiveSeguros() {
  return SEGURO_ACTIVO === "all" ? Object.keys(DATA.seguros) : [SEGURO_ACTIVO];
}

function getFilteredDays() {
  const from = document.querySelector("#date-from").value;
  const to   = document.querySelector("#date-to").value;
  const out = [];
  for (const s of getActiveSeguros()) {
    const dias = DATA.seguros[s]?.serie_diaria || [];
    for (const d of dias) {
      if (from && d.fecha < from) continue;
      if (to && d.fecha > to) continue;
      out.push({ ...d, seguro: s });
    }
  }
  out.sort((a, b) => a.fecha.localeCompare(b.fecha));
  return out;
}

/* ---------- KPIs ---------- */
function renderKPIs(days) {
  const inv = days.reduce((a,d) => a + (d.consumo_google||0) + (d.consumo_meta||0) + (d.consumo_bing||0), 0);
  const leads = days.reduce((a,d) => a + (d.leads_google||0) + (d.leads_meta||0) + (d.leads_bing||0), 0);

  // Conversiones del MCC (totales del mes actual, no del rango). Es la metrica de Google Ads,
  // mientras que leads del Sheet es del cliente. La diferencia es justamente el insight.
  let conv_mcc = 0;
  for (const s of getActiveSeguros()) {
    conv_mcc += DATA.seguros[s]?.totales?.conversiones_google || 0;
  }
  const cpa = conv_mcc > 0 ? days.reduce((a,d) => a + (d.consumo_google||0), 0) / conv_mcc : 0;

  document.querySelector("#kpi-inv-rango .value").textContent   = fmtCurrency(inv);
  document.querySelector("#kpi-conv-rango .value").textContent  = fmtNumber(Math.round(conv_mcc));
  document.querySelector("#kpi-cpa-rango .value").textContent   = fmtCurrencyD(cpa);
  document.querySelector("#kpi-leads-rango .value").textContent = fmtNumber(leads);
}

/* ---------- eventos ---------- */
function renderEventos() {
  const wrap = document.querySelector("#eventos-grid");
  const seguros = getActiveSeguros();
  wrap.innerHTML = seguros.map(s => {
    const e = DATA.seguros[s]?.evento_conversion || {};
    return `
      <div class="evento-card" style="--c:${SEGURO_COLORS[s]}">
        <h4>${s}</h4>
        <div class="evento-row"><span>Evento Google Ads</span><span><code>${e.google_ads_event || "—"}</code></span></div>
        <div class="evento-row"><span>Evento Meta</span><span><code>${e.meta_event || "—"}</code></span></div>
        <div class="evento-row"><span>Valor objetivo</span><span>${e.valor_objetivo || "—"}</span></div>
        <div class="evento-row"><span>Ventana atribución</span><span>${e.ventana_atribucion || "—"}</span></div>
      </div>`;
  }).join("");
}

/* ---------- charts subtipo ---------- */
function chart(canvasId, type, data, options = {}) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  CHARTS[canvasId] = new Chart(ctx, {
    type,
    data,
    options: {
      responsive: true, maintainAspectRatio: false,
      ...options,
    },
  });
}

function renderSubtipoCharts() {
  const seguros = getActiveSeguros();
  // Agregar por subtipo cross seguros
  const acc = {};
  for (const s of seguros) {
    const sub = DATA.seguros[s]?.por_subtipo || {};
    for (const [t, v] of Object.entries(sub)) {
      acc[t] = acc[t] || { coste: 0, conv: 0 };
      acc[t].coste += v.coste;
      acc[t].conv  += v.conv;
    }
  }
  const subtipos = Object.keys(acc);
  const colores = subtipos.map(t => SUBTIPO_COLORS[t] || "#888");

  // Inversion (donut)
  chart("chart-subtipo-inv", "doughnut", {
    labels: subtipos,
    datasets: [{
      data: subtipos.map(t => acc[t].coste),
      backgroundColor: colores,
      borderWidth: 0,
    }],
  }, {
    plugins: {
      legend: { position: "bottom", labels: { font: { family: "Inter", size: 11 } } },
      tooltip: { callbacks: { label: (it) => `${it.label}: ${fmtCurrency(it.parsed)} (${(it.parsed/acc[subtipos[it.dataIndex]].coste*100).toFixed(0)}% conv: ${fmtNumber(Math.round(acc[it.label].conv))})` } },
    },
  });

  // CPA por subtipo (bar)
  chart("chart-subtipo-cpa", "bar", {
    labels: subtipos,
    datasets: [{
      label: "CPA (USD)",
      data: subtipos.map(t => acc[t].conv ? acc[t].coste/acc[t].conv : 0),
      backgroundColor: colores,
      borderRadius: 6,
    }],
  }, {
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (it) => `CPA: ${fmtCurrencyD(it.parsed.y)}` } },
    },
    scales: {
      y: { ticks: { callback: v => "$" + v }, grid: { color: "rgba(0,53,156,0.05)" } },
      x: { grid: { display: false } },
    },
  });
}

/* ---------- tabla campañas ---------- */
function determineAccion(c) {
  if ((c.flags || []).includes("policy_limited") || (c.flags || []).includes("rejected"))
    return { type: "destrabar", text: "Destrabar" };
  if (c.cuota_perdida_budget > 0.20 && c.cpa > 0 && c.cpa < 12)
    return { type: "escalar", text: "Escalar +30%" };
  if (c.cpa > 15 && c.coste > 1000)
    return { type: "pausar", text: "Recortar -50%" };
  if (c.cuota_perdida_ranking > 0.30)
    return { type: "quality", text: "Mejorar QS" };
  return { type: "ok", text: "Mantener" };
}

function renderCampanasTable() {
  const tbody = document.querySelector("#campanias-table tbody");
  const seguros = getActiveSeguros();
  const todas = [];
  for (const s of seguros) {
    for (const c of (DATA.seguros[s]?.campanias || [])) {
      todas.push({ seguro: s, ...c });
    }
  }
  todas.sort((a,b) => b.coste - a.coste);
  if (!todas.length) { tbody.innerHTML = `<tr><td colspan="14" style="text-align:center;padding:20px;">Sin campañas</td></tr>`; return; }
  tbody.innerHTML = todas.map(c => {
    const acc = determineAccion(c);
    return `
      <tr>
        <td><span class="badge" style="background:${SEGURO_COLORS[c.seguro]}">${c.seguro}</span></td>
        <td><code>${c.nombre}</code></td>
        <td><span class="badge" style="background:${SUBTIPO_COLORS[c.subtipo]}">${c.subtipo}</span></td>
        <td title="${c.estado}">${(c.estado||'').slice(0,28)}${(c.estado||'').length>28?'…':''}</td>
        <td>${fmtCurrencyD(c.presupuesto_diario)}</td>
        <td>${fmtCurrency(c.coste)}</td>
        <td>${fmtNumber(c.impresiones)}</td>
        <td>${(c.ctr_pct*100).toFixed(2)}%</td>
        <td>${fmtCurrencyD(c.cpc)}</td>
        <td>${fmtNumber(Math.round(c.conversiones))}</td>
        <td><strong>${c.cpa ? fmtCurrencyD(c.cpa) : "—"}</strong></td>
        <td class="${c.cuota_perdida_budget>0.20?'flag-warn':''}">${(c.cuota_perdida_budget*100).toFixed(0)}%</td>
        <td class="${c.cuota_perdida_ranking>0.30?'flag-warn':''}">${(c.cuota_perdida_ranking*100).toFixed(0)}%</td>
        <td><span class="accion ${acc.type}">${acc.text}</span></td>
      </tr>`;
  }).join("");
}

/* ---------- charts daily ---------- */
function lineChart(canvasId, labels, datasets, yMode = "number") {
  chart(canvasId, "line", { labels, datasets }, {
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "bottom", labels: { font: { family: "Inter", size: 11 } } },
      tooltip: { callbacks: { label: (it) => `${it.dataset.label}: ${yMode==="currency"?"$"+fmtNumber(it.parsed.y):fmtNumber(it.parsed.y)}` } },
    },
    scales: {
      y: { ticks: { callback: v => yMode==="currency"?"$"+fmtNumber(v):fmtNumber(v) }, grid: { color: "rgba(0,53,156,0.05)" } },
      x: { ticks: { font: { family: "Inter", size: 10 }, autoSkipPadding: 30, maxRotation: 50 }, grid: { display: false } },
    },
  });
}

function renderDailyCharts(days) {
  const dates = [...new Set(days.map(d => d.fecha))].sort();
  const sumByDate = (key) => dates.map(date => days.filter(x => x.fecha === date).reduce((a,d) => a + (d[key] || 0), 0));

  lineChart("chart-leads-canal", dates, [
    { label: "Google", data: sumByDate("leads_google"), borderColor: "#00359C", backgroundColor: "#00359C22", tension: 0.3, borderWidth: 2, pointRadius: 1 },
    { label: "Meta",   data: sumByDate("leads_meta"),   borderColor: "#9333EA", backgroundColor: "#9333EA22", tension: 0.3, borderWidth: 2, pointRadius: 1 },
    { label: "Bing",   data: sumByDate("leads_bing"),   borderColor: "#00AEC7", backgroundColor: "#00AEC722", tension: 0.3, borderWidth: 2, pointRadius: 1 },
  ], "number");

  lineChart("chart-inv-canal", dates, [
    { label: "Google", data: sumByDate("consumo_google"), borderColor: "#00359C", backgroundColor: "#00359C44", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
    { label: "Meta",   data: sumByDate("consumo_meta"),   borderColor: "#9333EA", backgroundColor: "#9333EA44", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
    { label: "Bing",   data: sumByDate("consumo_bing"),   borderColor: "#00AEC7", backgroundColor: "#00AEC744", tension: 0.3, fill: true, borderWidth: 2, pointRadius: 0 },
  ], "currency");
}

/* ---------- TOP 10 ---------- */
function renderTop10() {
  const list = document.querySelector("#reco-pm-list");
  const recos = DATA.top10_recos || [];
  let activeFilter = "all";
  document.querySelectorAll("#reco-pm-filters .chip").forEach(c => c.addEventListener("click", () => {
    document.querySelectorAll("#reco-pm-filters .chip").forEach(x => x.classList.remove("active"));
    c.classList.add("active");
    activeFilter = c.dataset.f;
    draw();
  }));
  function draw() {
    const filtered = recos.filter(r => activeFilter === "all" ? true : r.tipo === activeFilter);
    list.innerHTML = filtered.map(r => {
      const i = recos.indexOf(r) + 1;
      return `
        <details class="reco-item">
          <summary>
            <div class="rank">${i}</div>
            <div class="title-block">
              <div class="title">${r.titulo}</div>
              <div class="meta">${r.seguro} · ${r.subtipo || r.tipo} · esfuerzo ${r.esfuerzo} · plazo ${r.plazo}</div>
            </div>
            <span class="priority ${r.prioridad}">${r.prioridad}</span>
          </summary>
          <div class="reco-detail">
            <p><strong>Qué hacer:</strong> ${r.que_hacer}</p>
            <p><strong>Por qué:</strong> ${r.por_que}</p>
            <div class="reco-impact">
              <div><div class="label">Impacto en CPL</div><div class="value">${r.impacto_cpl || "—"}</div></div>
              <div><div class="label">Impacto en conversiones</div><div class="value">${r.impacto_conv || "—"}</div></div>
            </div>
          </div>
        </details>`;
    }).join("");
  }
  draw();
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
  renderKPIs(days);
  renderEventos();
  renderSubtipoCharts();
  renderCampanasTable();
  renderDailyCharts(days);
}

/* ---------- main ---------- */
(async function main() {
  try {
    DATA = await loadData();
    const max = DATA.meta.rango_global.hasta;
    const today = new Date(max + "T00:00:00");
    const monthStart = new Date(today); monthStart.setDate(1);
    document.querySelector("#date-from").value = ymd(monthStart);
    document.querySelector("#date-to").value = max;
    document.querySelector("#date-from").min = DATA.meta.rango_global.desde;
    document.querySelector("#date-from").max = max;
    document.querySelector("#date-to").min = DATA.meta.rango_global.desde;
    document.querySelector("#date-to").max = max;

    document.querySelector("#date-from").addEventListener("change", refreshAll);
    document.querySelector("#date-to").addEventListener("change", refreshAll);
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
    renderTop10();
  } catch (e) {
    console.error(e);
    alert("Error: " + e.message);
  }
})();
