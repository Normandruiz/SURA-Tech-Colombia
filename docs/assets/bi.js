/* ============================================================
   BI page · logica
   Funnel Leads -> Polizas -> Prima emitida (COP)
   ============================================================ */

(function () {
  'use strict';

  // ----------------------------------------------------------
  // Config
  // ----------------------------------------------------------
  const SOL_COLORS = {
    Autos:    '#00359C',
    Motos:    '#00AEC7',
    Arriendo: '#2D6DF6',
    Viajes:   '#9333EA',
  };
  const CHANNEL_COLORS = {
    'google-ads':  '#4285F4',
    'meta-ads':    '#1877F2',
    'facebook':    '#1877F2',
    'ig':          '#E1306C',
    'bing-ads':    '#00A4EF',
    'bing':        '#00A4EF',
    'youtube':     '#FF0000',
    'sura-co':     '#0033A0',
    'sura.co':     '#0033A0',
    'app':         '#00AEC7',
    'app_sura':    '#00AEC7',
    'whatsapp':    '#25D366',
    'email':       '#FBBC05',
    'sfmc':        '#FBBC05',
    'chatgpt.com': '#10A37F',
    'asesores':    '#9CA3AF',
    'blog':        '#A78BFA',
    'clientes-soat-autos': '#9CA3AF',
    '(directo)':   '#9CA3AF',
  };
  const CHANNEL_FALLBACK = '#9CA3AF';

  // ----------------------------------------------------------
  // State
  // ----------------------------------------------------------
  let DATA = null;
  let allRows = [];               // todas las filas (todos los meses)
  let filterSol   = 'all';        // all | Autos | Motos | Arriendo | Viajes
  let filterMonth = 'all';        // all | Enero | Febrero | Marzo | Abril
  let detalleSearch = '';
  let detalleSortKey = 'prima';
  let detalleSortDir = 'desc';
  let charts = {};                // chart instances

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------
  const fmtInt = n => (n || 0).toLocaleString('es-CO');
  const fmtCOP = n => '$' + (n || 0).toLocaleString('es-CO');
  // Colombian financial format: always in millones (M) - NO "B" para evitar
  // confusion con billon espanol (10^12). Para valores >= 1.000 M se muestran
  // como "$1.740 M" (= 1.740 millones COP).
  const fmtCOPshort = n => {
    n = n || 0;
    const abs = Math.abs(n);
    if (abs >= 1e6) {
      const m = n / 1e6;
      const opts = abs >= 1e9
        ? { maximumFractionDigits: 0 }       // 1.740 M
        : { maximumFractionDigits: 1 };       // 290,4 M
      return '$' + m.toLocaleString('es-CO', opts) + ' M';
    }
    if (abs >= 1e3) return '$' + Math.round(n / 1e3).toLocaleString('es-CO') + 'k';
    return '$' + Math.round(n).toLocaleString('es-CO');
  };
  const fmtPct = (num, den, digits = 1) => {
    if (!den) return '—';
    return (100 * num / den).toFixed(digits) + '%';
  };

  function tasaClass(tasa) {
    if (tasa === null || tasa === undefined) return 'zero';
    if (tasa >= 0.20) return 'good';
    if (tasa >= 0.05) return 'warn';
    return 'bad';
  }

  function channelColor(src) {
    return CHANNEL_COLORS[src] || CHANNEL_FALLBACK;
  }

  // ----------------------------------------------------------
  // Aggregation
  // ----------------------------------------------------------
  function getFilteredRows() {
    const months = filterMonth === 'all'
      ? Object.keys(DATA.months)
      : [filterMonth];
    let rows = [];
    months.forEach(m => {
      const list = DATA.months[m] || [];
      list.forEach(r => rows.push({ ...r, month: m }));
    });
    if (filterSol !== 'all') {
      rows = rows.filter(r => r.sol === filterSol);
    }
    return rows;
  }

  function totals(rows) {
    let leads = 0, pol = 0, prima = 0;
    rows.forEach(r => { leads += r.leads; pol += r.pol; prima += r.prima; });
    return { leads, pol, prima };
  }

  function aggregateBySolucion(rows) {
    const out = {};
    rows.forEach(r => {
      const a = out[r.sol] || (out[r.sol] = { leads: 0, pol: 0, prima: 0 });
      a.leads += r.leads; a.pol += r.pol; a.prima += r.prima;
    });
    return out;
  }

  function aggregateBySource(rows) {
    const out = {};
    rows.forEach(r => {
      const k = r.src || '(directo)';
      const a = out[k] || (out[k] = { leads: 0, pol: 0, prima: 0 });
      a.leads += r.leads; a.pol += r.pol; a.prima += r.prima;
    });
    return out;
  }

  function aggregateByMonth(rows) {
    const order = ['Enero', 'Febrero', 'Marzo', 'Abril'];
    const out = {};
    order.forEach(m => out[m] = { leads: 0, pol: 0, prima: 0 });
    rows.forEach(r => {
      const a = out[r.month];
      if (a) { a.leads += r.leads; a.pol += r.pol; a.prima += r.prima; }
    });
    return out;
  }

  function topChannelForSol(rows, sol) {
    // Excluye '(directo)' (filas sin source) para que el "canal #1" sea
    // un canal accionable con UTM real
    const filtered = rows.filter(r => r.sol === sol && r.src);
    const ag = aggregateBySource(filtered);
    let best = null;
    Object.entries(ag).forEach(([src, v]) => {
      if (!best || v.prima > best.prima) best = { src, ...v };
    });
    return best;
  }

  // ----------------------------------------------------------
  // Render KPIs
  // ----------------------------------------------------------
  function renderKPIs(rows) {
    const t = totals(rows);
    const tasa = t.leads ? (t.pol / t.leads) : 0;
    const arpu = t.pol ? (t.prima / t.pol) : 0;

    document.querySelector('#kpi-leads .value').textContent = fmtInt(t.leads);
    document.querySelector('#kpi-polizas .value').textContent = fmtInt(t.pol);
    document.querySelector('#kpi-prima .value').textContent = fmtCOPshort(t.prima);
    document.querySelector('#kpi-prima .delta').textContent = fmtCOP(t.prima);
    document.querySelector('#kpi-tasa .value').textContent = (tasa * 100).toFixed(2) + '%';
    document.querySelector('#kpi-arpu .value').textContent = fmtCOPshort(arpu);
    document.querySelector('#kpi-arpu .delta').textContent = arpu ? fmtCOP(Math.round(arpu)) : '—';
  }

  // ----------------------------------------------------------
  // Render Solucion cards
  // ----------------------------------------------------------
  function renderSolCards(rows) {
    const grid = document.getElementById('bi-sol-grid');
    const ag = aggregateBySolucion(rows);

    const order = filterSol === 'all'
      ? ['Autos', 'Motos', 'Arriendo', 'Viajes']
      : [filterSol];

    grid.innerHTML = order.map(sol => {
      const a = ag[sol] || { leads: 0, pol: 0, prima: 0 };
      const tasa = a.leads ? (a.pol / a.leads) : 0;
      const arpu = a.pol ? (a.prima / a.pol) : 0;
      const cls  = tasaClass(tasa);
      const top  = topChannelForSol(rows, sol);

      const topBlock = top && top.prima > 0
        ? `<div class="top-channel">
             Canal #1 por prima: <strong>${top.src} — ${fmtCOPshort(top.prima)}</strong>
           </div>`
        : '';

      return `
        <div class="bi-sol-card" style="--c:${SOL_COLORS[sol]}">
          <h3>${sol} <span class="pill">${filterMonth === 'all' ? 'Q1+Abr' : filterMonth}</span></h3>
          <div class="funnel-row"><span class="label">Leads</span><span class="value">${fmtInt(a.leads)}</span></div>
          <div class="funnel-row"><span class="label">Pólizas</span><span class="value">${fmtInt(a.pol)}</span></div>
          <div class="funnel-row tasa"><span class="label">Tasa Lead → Póliza</span><span class="value ${cls}">${(tasa*100).toFixed(2)}%</span></div>
          <div class="funnel-row"><span class="label">Prima emitida</span><span class="value">${fmtCOPshort(a.prima)}</span></div>
          <div class="funnel-row"><span class="label">Prima / Póliza</span><span class="value">${fmtCOPshort(arpu)}</span></div>
          ${topBlock}
        </div>
      `;
    }).join('');
  }

  // ----------------------------------------------------------
  // Charts
  // ----------------------------------------------------------
  function destroyChart(key) {
    if (charts[key]) { charts[key].destroy(); delete charts[key]; }
  }

  function renderMixCharts(rows) {
    const ag = aggregateBySource(rows);
    // sort by prima desc but keep top N + "Otros"
    const entries = Object.entries(ag).sort((a, b) => b[1].prima - a[1].prima);
    const TOP_N = 8;
    let displayed = entries.slice(0, TOP_N);
    if (entries.length > TOP_N) {
      const otros = entries.slice(TOP_N).reduce((acc, [, v]) => {
        acc.leads += v.leads; acc.pol += v.pol; acc.prima += v.prima; return acc;
      }, { leads: 0, pol: 0, prima: 0 });
      displayed.push(['Otros', otros]);
    }

    const labels = displayed.map(([k]) => k);
    const colors = labels.map(channelColor);

    destroyChart('mixLeads');
    charts.mixLeads = new Chart(document.getElementById('chart-mix-leads'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: displayed.map(([, v]) => v.leads),
          backgroundColor: colors,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: ctx => {
                const tot = ctx.dataset.data.reduce((s, x) => s + x, 0);
                const pct = tot ? (100 * ctx.parsed / tot).toFixed(1) : 0;
                return `${ctx.label}: ${fmtInt(ctx.parsed)} (${pct}%)`;
              },
            },
          },
        },
      },
    });

    destroyChart('mixPrima');
    charts.mixPrima = new Chart(document.getElementById('chart-mix-prima'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: displayed.map(([, v]) => v.prima),
          backgroundColor: colors,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: ctx => {
                const tot = ctx.dataset.data.reduce((s, x) => s + x, 0);
                const pct = tot ? (100 * ctx.parsed / tot).toFixed(1) : 0;
                return `${ctx.label}: ${fmtCOPshort(ctx.parsed)} (${pct}%)`;
              },
            },
          },
        },
      },
    });
  }

  function renderEvolCharts() {
    // Evolucion siempre muestra los 4 meses (ignora filterMonth para esta seccion)
    const monthOrder = ['Enero', 'Febrero', 'Marzo', 'Abril'];
    const allRowsRaw = [];
    monthOrder.forEach(m => {
      (DATA.months[m] || []).forEach(r => allRowsRaw.push({ ...r, month: m }));
    });
    const filtered = filterSol === 'all' ? allRowsRaw : allRowsRaw.filter(r => r.sol === filterSol);

    const byMonth = aggregateByMonth(filtered);
    const labels = monthOrder;
    const leads = labels.map(m => byMonth[m].leads);
    const pol   = labels.map(m => byMonth[m].pol);
    const prima = labels.map(m => byMonth[m].prima);

    destroyChart('evolFunnel');
    charts.evolFunnel = new Chart(document.getElementById('chart-evol-funnel'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Leads',
            data: leads,
            backgroundColor: 'rgba(45, 109, 246, 0.7)',
            yAxisID: 'y',
          },
          {
            label: 'Pólizas',
            data: pol,
            type: 'line',
            borderColor: '#00AEC7',
            backgroundColor: '#00AEC7',
            yAxisID: 'y1',
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtInt(ctx.parsed.y)}` } } },
        scales: {
          y:  { type: 'linear', position: 'left',  title: { display: true, text: 'Leads' } },
          y1: { type: 'linear', position: 'right', title: { display: true, text: 'Pólizas' }, grid: { drawOnChartArea: false } },
        },
      },
    });

    destroyChart('evolPrima');
    charts.evolPrima = new Chart(document.getElementById('chart-evol-prima'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Prima emitida',
          data: prima,
          backgroundColor: 'rgba(0, 51, 160, 0.85)',
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => fmtCOP(ctx.parsed.y) } },
        },
        scales: {
          y: { ticks: { callback: v => fmtCOPshort(v) } },
        },
      },
    });
  }

  // ----------------------------------------------------------
  // Top campañas table
  // ----------------------------------------------------------
  function renderTopTable(rows) {
    const sorted = [...rows].filter(r => r.prima > 0).sort((a, b) => b.prima - a.prima).slice(0, 15);
    const tbody = document.querySelector('#bi-top-table tbody');
    tbody.innerHTML = sorted.map((r, i) => {
      const tasa = r.leads ? (r.pol / r.leads) : 0;
      const arpu = r.pol ? (r.prima / r.pol) : 0;
      const tCls = tasaClass(tasa);
      return `
        <tr>
          <td>${i + 1}</td>
          <td><span class="sol-pill ${r.sol}">${r.sol}</span></td>
          <td>${r.src || '—'}</td>
          <td>${r.camp || '—'}</td>
          <td>${r.cont || '—'}</td>
          <td class="num">${fmtInt(r.leads)}</td>
          <td class="num">${fmtInt(r.pol)}</td>
          <td class="num"><span class="tasa-pill ${tCls}">${(tasa*100).toFixed(1)}%</span></td>
          <td class="num">${fmtCOPshort(r.prima)}</td>
          <td class="num">${arpu ? fmtCOPshort(arpu) : '—'}</td>
        </tr>
      `;
    }).join('');
  }

  // ----------------------------------------------------------
  // Detalle table (filtered + sortable)
  // ----------------------------------------------------------
  function renderDetalleTable(rows) {
    let filtered = rows.slice();
    const q = detalleSearch.trim().toLowerCase();
    if (q) {
      filtered = filtered.filter(r => {
        const blob = (r.src + ' ' + r.med + ' ' + r.camp + ' ' + r.cont + ' ' + r.sol).toLowerCase();
        return blob.includes(q);
      });
    }

    // sort
    filtered.sort((a, b) => {
      const k = detalleSortKey;
      let av, bv;
      if (k === 'tasa') {
        av = a.leads ? a.pol / a.leads : -1;
        bv = b.leads ? b.pol / b.leads : -1;
      } else if (['leads', 'pol', 'prima'].includes(k)) {
        av = a[k]; bv = b[k];
      } else {
        av = (a[k] || '').toString().toLowerCase();
        bv = (b[k] || '').toString().toLowerCase();
      }
      if (av < bv) return detalleSortDir === 'asc' ? -1 : 1;
      if (av > bv) return detalleSortDir === 'asc' ?  1 : -1;
      return 0;
    });

    document.getElementById('bi-detalle-count').textContent = fmtInt(filtered.length) + ' filas';

    const tbody = document.querySelector('#bi-detalle-table tbody');
    // Limitar render a 500 para no colgar el browser
    const MAX_RENDER = 500;
    const truncated = filtered.length > MAX_RENDER;
    const display = truncated ? filtered.slice(0, MAX_RENDER) : filtered;

    tbody.innerHTML = display.map(r => {
      const tasa = r.leads ? (r.pol / r.leads) : 0;
      const tCls = tasaClass(tasa);
      return `
        <tr>
          <td><span class="sol-pill ${r.sol}">${r.sol}</span></td>
          <td>${r.src || '—'}</td>
          <td>${r.med || '—'}</td>
          <td>${r.camp || '—'}</td>
          <td>${r.cont || '—'}</td>
          <td class="num">${fmtInt(r.leads)}</td>
          <td class="num">${fmtInt(r.pol)}</td>
          <td class="num">${r.leads ? `<span class="tasa-pill ${tCls}">${(tasa*100).toFixed(1)}%</span>` : '—'}</td>
          <td class="num">${r.prima ? fmtCOPshort(r.prima) : '—'}</td>
        </tr>
      `;
    }).join('');

    if (truncated) {
      tbody.innerHTML += `
        <tr>
          <td colspan="9" style="text-align:center;padding:14px;color:var(--sura-gris-medio);font-style:italic">
            … ${fmtInt(filtered.length - MAX_RENDER)} filas adicionales ocultas. Refiná la búsqueda o aplicá filtros para verlas.
          </td>
        </tr>
      `;
    }

    // Update sort indicator on headers
    document.querySelectorAll('#bi-detalle-table th[data-sort]').forEach(th => {
      th.removeAttribute('aria-sort');
      if (th.dataset.sort === detalleSortKey) {
        th.setAttribute('aria-sort', detalleSortDir === 'asc' ? 'ascending' : 'descending');
      }
    });
  }

  // ----------------------------------------------------------
  // Master render
  // ----------------------------------------------------------
  function renderAll() {
    const rows = getFilteredRows();
    renderKPIs(rows);
    renderSolCards(rows);
    renderMixCharts(rows);
    renderEvolCharts();
    renderTopTable(rows);
    renderDetalleTable(rows);
  }

  // ----------------------------------------------------------
  // Event wiring
  // ----------------------------------------------------------
  function wireEvents() {
    document.querySelectorAll('#bi-sol-buttons button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#bi-sol-buttons button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterSol = btn.dataset.sol;
        renderAll();
      });
    });

    document.querySelectorAll('#bi-month-buttons button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#bi-month-buttons button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterMonth = btn.dataset.month;
        renderAll();
      });
    });

    const search = document.getElementById('bi-detalle-search');
    search.addEventListener('input', e => {
      detalleSearch = e.target.value;
      renderDetalleTable(getFilteredRows());
    });

    document.querySelectorAll('#bi-detalle-table th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.sort;
        if (detalleSortKey === k) {
          detalleSortDir = detalleSortDir === 'asc' ? 'desc' : 'asc';
        } else {
          detalleSortKey = k;
          detalleSortDir = ['leads', 'pol', 'prima', 'tasa'].includes(k) ? 'desc' : 'asc';
        }
        renderDetalleTable(getFilteredRows());
      });
    });
  }

  // ----------------------------------------------------------
  // Boot
  // ----------------------------------------------------------
  fetch('assets/data_bi.json', { cache: 'no-cache' })
    .then(r => r.json())
    .then(data => {
      DATA = data;
      // build flat allRows once
      Object.entries(DATA.months).forEach(([m, list]) => {
        list.forEach(r => allRows.push({ ...r, month: m }));
      });
      wireEvents();
      renderAll();
    })
    .catch(err => {
      console.error('Failed to load data_bi.json', err);
      document.body.insertAdjacentHTML(
        'afterbegin',
        `<div style="padding:20px;background:#fee2e2;color:#991b1b;text-align:center;font-weight:600">
           Error cargando data_bi.json: ${err.message}
         </div>`,
      );
    });
})();
