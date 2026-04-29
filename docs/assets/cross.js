/* ============================================================
   Cross page · logica
   Cruce Google + Meta + Sheet BI
   ============================================================ */

(function () {
  'use strict';

  const PROD_COLORS = {
    Autos:    '#00359C',
    Motos:    '#00AEC7',
    Arriendo: '#2D6DF6',
    Viajes:   '#9333EA',
  };

  const PRODUCTS = ['Autos', 'Motos', 'Arriendo', 'Viajes'];
  const MONTHS_ORDER = ['Enero', 'Febrero', 'Marzo', 'Abril'];
  const MONTHS_SHORT = ['Ene', 'Feb', 'Mar', 'Abr'];
  const SEV_LABEL = { CRITICO: '🔴 CRÍTICO', 'CRÍTICO': '🔴 CRÍTICO', ALTO: '🟠 ALTO', MEDIO: '🟡 MEDIO', OK: '🟢 OK' };

  let DATA = null;
  let filterProd = 'all';
  let filterMonth = 'all';
  let searchQuery = '';
  let sortKey = 'spend';
  let sortDir = 'desc';
  let charts = {};

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------
  const fmtUSD = n => '$' + (Math.round(n) || 0).toLocaleString('es-CO');
  const fmtUSD2 = n => '$' + ((n || 0).toFixed(2)).replace('.', ',');
  const fmtInt = n => (n || 0).toLocaleString('es-CO');
  const fmtCOPshort = n => {
    n = n || 0;
    const abs = Math.abs(n);
    if (abs >= 1e6) {
      const m = n / 1e6;
      const opts = abs >= 1e9 ? { maximumFractionDigits: 0 } : { maximumFractionDigits: 1 };
      return '$' + m.toLocaleString('es-CO', opts) + ' M';
    }
    if (abs >= 1e3) return '$' + Math.round(n / 1e3).toLocaleString('es-CO') + 'k';
    return '$' + Math.round(n).toLocaleString('es-CO');
  };
  const fmtPct = (v, digits = 1) => ((v || 0) * 100).toFixed(digits) + '%';
  const fmtDelta = v => {
    if (!v) return '0%';
    const sign = v > 0 ? '+' : '';
    return sign + v.toFixed(0) + '%';
  };

  function destroyChart(k) { if (charts[k]) { charts[k].destroy(); delete charts[k]; } }

  // ----------------------------------------------------------
  // Aggregation
  // ----------------------------------------------------------
  function aggregateForFilter() {
    const products = filterProd === 'all' ? PRODUCTS : [filterProd];
    const months = filterMonth === 'all' ? MONTHS_ORDER : [filterMonth];
    const out = { spend: 0, conv: 0, leads_sf: 0, polizas: 0, prima_cop: 0,
                  google: { spend: 0, conv: 0, leads_sf: 0, polizas: 0 },
                  meta:   { spend: 0, conv: 0, leads_sf: 0, polizas: 0 } };
    products.forEach(p => {
      months.forEach(m => {
        const mo = DATA.by_product_month[p][m];
        ['google', 'meta'].forEach(plat => {
          const d = mo[plat];
          out.spend += d.spend; out.conv += d.conv;
          out.leads_sf += d.leads_sf; out.polizas += d.polizas; out.prima_cop += d.prima_cop;
          out[plat].spend += d.spend; out[plat].conv += d.conv;
          out[plat].leads_sf += d.leads_sf; out[plat].polizas += d.polizas;
        });
      });
    });
    out.cpa = out.conv ? out.spend / out.conv : 0;
    out.cpl_negocio = out.leads_sf ? out.spend / out.leads_sf : 0;
    out.cac = out.polizas ? out.spend / out.polizas : 0;
    return out;
  }

  // ----------------------------------------------------------
  // Render KPIs
  // ----------------------------------------------------------
  function renderKPIs() {
    const t = aggregateForFilter();
    document.querySelector('#kpi-spend .value').textContent = fmtUSD(t.spend);
    document.querySelector('#kpi-conv .value').textContent = fmtInt(Math.round(t.conv));
    document.querySelector('#kpi-leads .value').textContent = fmtInt(t.leads_sf);
    document.querySelector('#kpi-cpl .value').textContent = t.cpl_negocio ? fmtUSD2(t.cpl_negocio) : '—';
    document.querySelector('#kpi-cac .value').textContent = t.cac ? fmtUSD(t.cac) : '—';
  }

  // ----------------------------------------------------------
  // Render product cards
  // ----------------------------------------------------------
  function renderProductCards() {
    const grid = document.getElementById('cross-prod-grid');
    const products = filterProd === 'all' ? PRODUCTS : [filterProd];
    const months = filterMonth === 'all' ? MONTHS_ORDER : [filterMonth];

    grid.innerHTML = products.map(prod => {
      const blocks = ['google', 'meta'].map(plat => {
        let spend = 0, conv = 0, leads_sf = 0, polizas = 0, prima_cop = 0;
        months.forEach(m => {
          const d = DATA.by_product_month[prod][m][plat];
          spend += d.spend; conv += d.conv; leads_sf += d.leads_sf;
          polizas += d.polizas; prima_cop += d.prima_cop;
        });
        const cpa = conv ? spend / conv : 0;
        const cpl = leads_sf ? spend / leads_sf : 0;
        const cac = polizas ? spend / polizas : 0;
        const ratio = conv ? leads_sf / conv : 0;
        const ratioCls = ratio > 0.8 ? 'good' : (ratio > 0.4 ? 'warn' : 'bad');
        const platCls = plat === 'meta' ? 'meta' : '';
        const platName = plat === 'meta' ? 'Meta' : 'Google';
        const platColor = plat === 'meta' ? '#1877F2' : '#4285F4';
        return `
          <div class="cross-plat-block ${platCls}" style="--p:${platColor}">
            <h4>${platName}</h4>
            <div class="row"><span class="label">Inversión</span><span class="value">${fmtUSD(spend)}</span></div>
            <div class="row"><span class="label">Conv. plat.</span><span class="value">${fmtInt(Math.round(conv))}</span></div>
            <div class="row"><span class="label">CPA</span><span class="value">${cpa ? fmtUSD2(cpa) : '—'}</span></div>
            <div class="row"><span class="label">Leads SF</span><span class="value">${fmtInt(leads_sf)}</span></div>
            <div class="row"><span class="label">CPL Negocio</span><span class="value ${ratioCls}">${cpl ? fmtUSD2(cpl) : '—'}</span></div>
            <div class="row"><span class="label">Pólizas</span><span class="value">${fmtInt(polizas)}</span></div>
            <div class="row"><span class="label">CAC</span><span class="value ${cac > 1000 ? 'bad' : (cac > 0 ? 'good' : '')}">${cac ? fmtUSD(cac) : '—'}</span></div>
            <div class="row"><span class="label">Prima emitida</span><span class="value">${fmtCOPshort(prima_cop)}</span></div>
          </div>
        `;
      }).join('');
      return `
        <div class="cross-prod-card" style="--c:${PROD_COLORS[prod]}">
          <h3>${prod} <span class="pill">${filterMonth === 'all' ? 'Q1+Abr' : filterMonth}</span></h3>
          <div class="cross-platforms">${blocks}</div>
        </div>
      `;
    }).join('');
  }

  // ----------------------------------------------------------
  // Charts
  // ----------------------------------------------------------
  function renderCharts() {
    const products = filterProd === 'all' ? PRODUCTS : [filterProd];

    // CPA Google por producto (líneas)
    const datasetsG = products.map(p => ({
      label: p,
      data: MONTHS_ORDER.map(m => DATA.by_product_month[p][m].google.cpa || 0),
      borderColor: PROD_COLORS[p],
      backgroundColor: PROD_COLORS[p],
      tension: 0.3,
      fill: false,
    }));
    destroyChart('cpaG');
    charts.cpaG = new Chart(document.getElementById('chart-cpa-google'), {
      type: 'line',
      data: { labels: MONTHS_SHORT, datasets: datasetsG },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtUSD2(ctx.parsed.y)}` } } },
        scales: { y: { ticks: { callback: v => '$' + v }, title: { display: true, text: 'CPA US$' } } },
      },
    });

    const datasetsM = products.map(p => ({
      label: p,
      data: MONTHS_ORDER.map(m => DATA.by_product_month[p][m].meta.cpa || 0),
      borderColor: PROD_COLORS[p],
      backgroundColor: PROD_COLORS[p],
      tension: 0.3,
      fill: false,
    }));
    destroyChart('cpaM');
    charts.cpaM = new Chart(document.getElementById('chart-cpa-meta'), {
      type: 'line',
      data: { labels: MONTHS_SHORT, datasets: datasetsM },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtUSD2(ctx.parsed.y)}` } } },
        scales: { y: { ticks: { callback: v => '$' + v }, title: { display: true, text: 'CPA US$' } } },
      },
    });

    // Inversión Google vs Meta (barras agrupadas)
    const sumByMonth = (plat) => MONTHS_ORDER.map(m =>
      products.reduce((s, p) => s + DATA.by_product_month[p][m][plat].spend, 0));
    destroyChart('spend');
    charts.spend = new Chart(document.getElementById('chart-spend'), {
      type: 'bar',
      data: {
        labels: MONTHS_SHORT,
        datasets: [
          { label: 'Google',  data: sumByMonth('google'), backgroundColor: '#4285F4' },
          { label: 'Meta',    data: sumByMonth('meta'),   backgroundColor: '#1877F2' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtUSD(ctx.parsed.y)}` } } },
        scales: { y: { ticks: { callback: v => '$' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v) } } },
      },
    });

    // Leads SF vs Conv plataforma (barras agrupadas)
    const conv_g = MONTHS_ORDER.map(m => products.reduce((s,p) => s + DATA.by_product_month[p][m].google.conv, 0));
    const conv_m = MONTHS_ORDER.map(m => products.reduce((s,p) => s + DATA.by_product_month[p][m].meta.conv, 0));
    const ldsf_g = MONTHS_ORDER.map(m => products.reduce((s,p) => s + DATA.by_product_month[p][m].google.leads_sf, 0));
    const ldsf_m = MONTHS_ORDER.map(m => products.reduce((s,p) => s + DATA.by_product_month[p][m].meta.leads_sf, 0));
    destroyChart('lvc');
    charts.lvc = new Chart(document.getElementById('chart-leads-vs-conv'), {
      type: 'bar',
      data: {
        labels: MONTHS_SHORT,
        datasets: [
          { label: 'Conv. Google', data: conv_g.map(Math.round), backgroundColor: '#4285F4' },
          { label: 'Leads SF (Google)', data: ldsf_g, backgroundColor: '#93C5FD' },
          { label: 'Conv. Meta', data: conv_m.map(Math.round), backgroundColor: '#1877F2' },
          { label: 'Leads SF (Meta)', data: ldsf_m, backgroundColor: '#FBBF24' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtInt(ctx.parsed.y)}` } } },
      },
    });
  }

  // ----------------------------------------------------------
  // Diagnóstico
  // ----------------------------------------------------------
  function renderDiagnostics() {
    const grid = document.getElementById('cross-diag-grid');
    let diags = DATA.diagnostics;
    if (filterProd !== 'all') diags = diags.filter(d => d.producto === filterProd);
    // sort by severity DESC: CRITICO > ALTO > MEDIO > OK
    const sevOrder = { 'CRÍTICO': 4, 'CRITICO': 4, 'ALTO': 3, 'MEDIO': 2, 'OK': 1 };
    diags = diags.slice().sort((a, b) => (sevOrder[b.severity] || 0) - (sevOrder[a.severity] || 0));

    grid.innerHTML = diags.map(d => {
      const sevKey = d.severity.replace('Í', 'I'); // CRÍTICO → CRITICO for class
      const upDown = (v) => v > 0 ? 'up' : 'down';
      const dl = d.deltas;
      const isMeta = d.plataforma === 'Meta';
      const metricsHtml = isMeta ? `
        <div class="metric"><div class="label">CPA</div><div class="value ${upDown(dl.cpa)}">${fmtDelta(dl.cpa)}</div></div>
        <div class="metric"><div class="label">CPM</div><div class="value ${upDown(dl.cpm)}">${fmtDelta(dl.cpm)}</div></div>
        <div class="metric"><div class="label">Spend</div><div class="value">${fmtDelta(dl.spend)}</div></div>
        <div class="metric"><div class="label">Conv</div><div class="value ${dl.conv >= 0 ? 'down' : 'up'}">${fmtDelta(dl.conv)}</div></div>
      ` : `
        <div class="metric"><div class="label">CPA</div><div class="value ${upDown(dl.cpa)}">${fmtDelta(dl.cpa)}</div></div>
        <div class="metric"><div class="label">CPC</div><div class="value ${upDown(dl.cpc)}">${fmtDelta(dl.cpc)}</div></div>
        <div class="metric"><div class="label">CTR</div><div class="value ${dl.ctr >= 0 ? 'down' : 'up'}">${fmtDelta(dl.ctr)}</div></div>
        <div class="metric"><div class="label">Tasa Conv</div><div class="value ${dl.tasa_conv >= 0 ? 'down' : 'up'}">${fmtDelta(dl.tasa_conv)}</div></div>
      `;

      const cpa_delta_cls = dl.cpa > 0 ? 'up' : 'down';
      const driversHtml = d.drivers.length
        ? `<div class="drivers"><div class="title">🔬 Causas raíz</div><ul>${d.drivers.map(x => `<li>${x}</li>`).join('')}</ul></div>`
        : '';
      const actionsHtml = d.actions.length
        ? `<div class="actions"><div class="title">🎯 Plan de acción</div><ul>${d.actions.map(x => `<li>${x}</li>`).join('')}</ul></div>`
        : '';

      return `
        <div class="diag-card sev-${sevKey}">
          <div class="head">
            <h3>${d.producto} · ${d.plataforma}</h3>
            <span class="sev-badge">${SEV_LABEL[d.severity] || d.severity}</span>
          </div>
          <div class="delta-cpl">
            CPL: <strong>${fmtUSD2(d.ene.cpa)}</strong> → <strong>${fmtUSD2(d.abr.cpa)}</strong>
            <span class="delta ${cpa_delta_cls}">${fmtDelta(dl.cpa)}</span>
          </div>
          <div class="metrics-row">${metricsHtml}</div>
          ${driversHtml}
          ${actionsHtml}
        </div>
      `;
    }).join('');
  }

  // ----------------------------------------------------------
  // ROI cero
  // ----------------------------------------------------------
  function renderRoiZero() {
    const list = document.getElementById('cross-roi-zero');
    let items = DATA.roi_zero;
    if (filterProd !== 'all') items = items.filter(x => x.producto === filterProd);
    if (!items.length) {
      list.innerHTML = '<p style="color:var(--verde);font-weight:600;margin:0;padding:18px;background:#ecfdf5;border-radius:12px">✅ No hay campañas con ROI cero en el filtro activo. Toda la inversión genera leads en el CRM.</p>';
      return;
    }
    list.innerHTML = items.map(it => `
      <div class="roi-zero-card">
        <div class="head">
          <span class="nombre">${it.nombre}</span>
          <span class="meta">${it.producto} · ${it.plataforma}</span>
        </div>
        <div class="nums">
          <div><div class="label">Spend</div><div class="value">${fmtUSD(it.spend)}</div></div>
          <div><div class="label">Conv. plat.</div><div class="value">${fmtInt(Math.round(it.conv))}</div></div>
          <div><div class="label">Leads SF</div><div class="value">0</div></div>
          <div><div class="label">Estado</div><div class="value">${it.estado || '—'}</div></div>
        </div>
      </div>
    `).join('');
  }

  // ----------------------------------------------------------
  // Match Campañas table
  // ----------------------------------------------------------
  function renderCampTable() {
    const tbody = document.querySelector('#cross-camp-table tbody');
    let rows = DATA.campaigns.slice();
    if (filterProd !== 'all') rows = rows.filter(r => r.producto === filterProd);
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      rows = rows.filter(r => (r.nombre + ' ' + r.producto + ' ' + r.plataforma).toLowerCase().includes(q));
    }

    rows.sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      const an = (typeof av === 'number') ? av : (av || '').toString().toLowerCase();
      const bn = (typeof bv === 'number') ? bv : (bv || '').toString().toLowerCase();
      if (an < bn) return sortDir === 'asc' ? -1 : 1;
      if (an > bn) return sortDir === 'asc' ?  1 : -1;
      return 0;
    });

    document.getElementById('cross-count').textContent = fmtInt(rows.length) + ' filas';

    const MAX = 200;
    const truncated = rows.length > MAX;
    const display = truncated ? rows.slice(0, MAX) : rows;

    tbody.innerHTML = display.map(r => {
      const isRoi0 = r.spend > 50 && r.leads_sf === 0;
      const estadoCls = (r.estado || '').toLowerCase().includes('act') || (r.estado || '').toLowerCase().includes('habil') ? 'active' :
                       (r.estado || '').toLowerCase().includes('paus') ? 'pausada' : 'inactive';
      return `
        <tr class="${isRoi0 ? 'roi-zero' : ''}">
          <td>${r.producto}</td>
          <td>${r.plataforma}</td>
          <td style="font-size:11px;color:var(--sura-gris-oscuro)">${r.nombre}</td>
          <td><span class="estado-pill ${estadoCls}">${r.estado || '—'}</span></td>
          <td class="num">${fmtUSD(r.spend)}</td>
          <td class="num">${fmtInt(Math.round(r.conv))}</td>
          <td class="num">${r.cpa ? fmtUSD2(r.cpa) : '—'}</td>
          <td class="num">${fmtInt(r.leads_sf)}</td>
          <td class="num">${r.cpl_negocio ? fmtUSD2(r.cpl_negocio) : '—'}</td>
          <td class="num">${fmtInt(r.polizas)}</td>
          <td class="num">${r.cac ? fmtUSD(r.cac) : '—'}</td>
        </tr>
      `;
    }).join('');

    if (truncated) {
      tbody.innerHTML += `
        <tr><td colspan="11" style="text-align:center;padding:14px;color:var(--sura-gris-medio);font-style:italic">
          … ${fmtInt(rows.length - MAX)} filas adicionales ocultas. Filtrá para verlas.
        </td></tr>
      `;
    }

    document.querySelectorAll('#cross-camp-table th[data-sort]').forEach(th => {
      th.removeAttribute('aria-sort');
      if (th.dataset.sort === sortKey) {
        th.setAttribute('aria-sort', sortDir === 'asc' ? 'ascending' : 'descending');
      }
    });
  }

  // ----------------------------------------------------------
  // Master render
  // ----------------------------------------------------------
  function renderAll() {
    renderKPIs();
    renderProductCards();
    renderCharts();
    renderDiagnostics();
    renderRoiZero();
    renderCampTable();
  }

  // ----------------------------------------------------------
  // Wire events
  // ----------------------------------------------------------
  function wire() {
    document.querySelectorAll('#cross-prod-buttons button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#cross-prod-buttons button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterProd = btn.dataset.prod;
        renderAll();
      });
    });
    document.querySelectorAll('#cross-month-buttons button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#cross-month-buttons button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterMonth = btn.dataset.month;
        renderAll();
      });
    });
    document.getElementById('cross-search').addEventListener('input', e => {
      searchQuery = e.target.value;
      renderCampTable();
    });
    document.querySelectorAll('#cross-camp-table th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.sort;
        if (sortKey === k) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        else { sortKey = k; sortDir = ['spend','conv','cpa','leads_sf','cpl_negocio','polizas','cac'].includes(k) ? 'desc' : 'asc'; }
        renderCampTable();
      });
    });
  }

  // ----------------------------------------------------------
  // Boot
  // ----------------------------------------------------------
  fetch('assets/data_cross.json', { cache: 'no-cache' })
    .then(r => r.json())
    .then(data => { DATA = data; wire(); renderAll(); })
    .catch(err => {
      console.error('Failed to load data_cross.json', err);
      document.body.insertAdjacentHTML('afterbegin',
        `<div style="padding:20px;background:#fee2e2;color:#991b1b;text-align:center;font-weight:600">
          Error cargando data_cross.json: ${err.message}
        </div>`);
    });
})();
