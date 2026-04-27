"""Construye docs/assets/data_crm.json con datos DIARIOS de los 4 seguros.

Se usa en la pagina docs/crm.html (botón "CRM" del informe principal).
Incluye:
  - dias[] por seguro (todas las filas crudas del Sheet)
  - mensual[] por seguro (agregados desde build_dataset)
  - rangos disponibles
  - insights agregados (top dias, peak/valle, estacionalidad) generados aqui
"""

from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from statistics import mean, median

from src.config import ROOT


SHEETS_PARSED = ROOT / "raw" / "sheets_crm" / "parsed"
DOCS = ROOT / "docs"
OUT_PATH = DOCS / "assets" / "data_crm.json"

SEGURO_FILES = {
    "Autos":         "autos",
    "Motos":         "motos",
    "Arrendamiento": "arriendo",
    "Viajes":        "viajes",
}


def _latest(d: Path, prefix: str) -> Path | None:
    files = sorted(d.glob(f"{prefix}*.json"))
    return files[-1] if files else None


def load_seguro(slug: str) -> dict:
    p = _latest(SHEETS_PARSED, f"{slug}_")
    if not p:
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def compute_insights(seguros_data: dict) -> dict:
    insights: list = []

    # Insight 1: caida de cumplimiento por seguro entre pico y mes actual
    for nombre, data in seguros_data.items():
        mensual = data.get("mensual", {})
        if not mensual:
            continue
        rows = sorted(mensual.items())
        # filtrar meses con cumpl_sf_vs_req validos
        valid = [(ym, b) for ym, b in rows if b.get("cumpl_sf_vs_req") and b.get("requeridos", 0) > 0]
        if len(valid) < 6:
            continue
        # pico historico
        peak_ym, peak_b = max(valid, key=lambda x: x[1]["cumpl_sf_vs_req"])
        last_ym, last_b = valid[-1]
        delta_pp = (peak_b["cumpl_sf_vs_req"] - last_b["cumpl_sf_vs_req"]) * 100
        if delta_pp > 30:
            insights.append({
                "seguro": nombre,
                "tipo": "caida_estructural",
                "titulo": f"{nombre}: caída de {delta_pp:.0f}pp desde el pico de {peak_ym}",
                "detalle": (
                    f"Pico {peak_ym}: {peak_b['cumpl_sf_vs_req']*100:.1f}% cumplimiento "
                    f"({int(peak_b['recibidos_sf']):,} leads SF / CPL ${peak_b['cpl_negocio_sf']:.2f}). "
                    f"Hoy {last_ym}: {last_b['cumpl_sf_vs_req']*100:.1f}% "
                    f"({int(last_b['recibidos_sf']):,} leads SF / CPL ${last_b['cpl_negocio_sf']:.2f})."
                ),
                "severidad": "alta" if delta_pp < 80 else "critica",
            })

    # Insight 2: comparativa mismo mes anio anterior
    for nombre, data in seguros_data.items():
        mensual = data.get("mensual", {})
        if not mensual:
            continue
        rows = sorted(mensual.items())
        if not rows:
            continue
        last_ym, last_b = rows[-1]
        # buscar mismo mes año anterior (YYYY-MM -> YYYY-1-MM)
        try:
            y, m = last_ym.split("-")
            prev_year_ym = f"{int(y)-1}-{m}"
        except Exception:
            continue
        prev = mensual.get(prev_year_ym)
        if prev and prev.get("recibidos_sf") and last_b.get("recibidos_sf"):
            delta_pct = (last_b["recibidos_sf"] - prev["recibidos_sf"]) / prev["recibidos_sf"] * 100
            insights.append({
                "seguro": nombre,
                "tipo": "yoy",
                "titulo": f"{nombre}: vs mismo mes año anterior ({prev_year_ym}) → {'+' if delta_pct>=0 else ''}{delta_pct:.1f}%",
                "detalle": (
                    f"{prev_year_ym}: {int(prev['recibidos_sf']):,} SF / cumpl {prev['cumpl_sf_vs_req']*100:.1f}% / CPL ${prev['cpl_negocio_sf']:.2f}. "
                    f"{last_ym}: {int(last_b['recibidos_sf']):,} SF / cumpl {last_b['cumpl_sf_vs_req']*100:.1f}% / CPL ${last_b['cpl_negocio_sf']:.2f}."
                ),
                "severidad": "alta" if delta_pct < -30 else ("media" if delta_pct < 0 else "info"),
            })

    # Insight 3: top 5 mejores y peores días del último mes (por seguro)
    for nombre, data in seguros_data.items():
        diarios = data.get("diarios", [])
        if not diarios: continue
        last_month = diarios[-1]["fecha"][:7]
        ultimo_mes_dias = [d for d in diarios if d["fecha"][:7] == last_month and d.get("recibidos_sf")]
        if len(ultimo_mes_dias) < 3: continue
        ultimo_mes_dias_sorted = sorted(ultimo_mes_dias, key=lambda d: d.get("recibidos_sf") or 0)
        peor = ultimo_mes_dias_sorted[0]
        mejor = ultimo_mes_dias_sorted[-1]
        prom = mean(d["recibidos_sf"] for d in ultimo_mes_dias if d.get("recibidos_sf"))
        insights.append({
            "seguro": nombre,
            "tipo": "rango_diario",
            "titulo": f"{nombre} en {last_month}: rango diario {int(peor['recibidos_sf'])} - {int(mejor['recibidos_sf'])} (prom {prom:.0f})",
            "detalle": (
                f"Mejor día: {peor['fecha']}={int(peor['recibidos_sf'])} | "
                f"Peor: {mejor['fecha']}={int(mejor['recibidos_sf'])} | "
                f"Promedio: {prom:.0f} leads/día. Variabilidad alta puede indicar problemas de tracking en algunos días."
            ),
            "severidad": "info",
        })

    # Recomendaciones generales del CRM
    recos = [
        {
            "titulo": "Auditar el quiebre de mediados de 2025",
            "que_hacer": "Identificar el evento exacto (entre may-jul 2025) que disparó la caída sostenida en los 4 seguros simultáneamente. Cruzar con: cambios de bidding, lanzamiento de PMax, cambios de landing, cambios de oferta SURA, modificaciones del Smart Bidding, o cambios en Salesforce que afectaron el tracking.",
            "por_que": "Que los 4 seguros caigan en la misma ventana sugiere un cambio sistemico (no un problema de campania individual).",
            "impacto": "ALTO - identificar la raiz permite revertir o compensar el efecto",
            "prioridad": "critica",
        },
        {
            "titulo": "Recuperar el ratio Pauta/SF que se perdió",
            "que_hacer": "Comparar los formularios y flows que tenia la pauta cuando rendía vs los actuales. Reactivar landings/ads cuyos UTM aparecían con alto ratio Pauta-vs-SF en el pico de 2025.",
            "por_que": "El ratio Pauta/SF mide cuanto de los leads que efectivamente recibe SF venian de la pauta. Si baja, la pauta se diluye.",
            "impacto": "ALTO - cada punto de ratio recuperado son cientos de leads/mes",
            "prioridad": "alta",
        },
        {
            "titulo": "Validar consistencia diaria de RECIBIDOS (SF)",
            "que_hacer": "Detectar dias con SF=0 que tengan inversión >0 (gap de tracking). Configurar alerta automática para que cualquier dia con SF=0 e inversion>$50 dispare un check.",
            "por_que": "Variabilidad diaria alta sugiere días donde el tracking falla. Sin alertas reactivas, descubrimos rato después que perdimos un dia.",
            "impacto": "MEDIO - reducir días con tracking roto",
            "prioridad": "media",
        },
    ]

    return {
        "insights":         insights,
        "recomendaciones":  recos,
    }


def run() -> int:
    seguros_data: dict = {}
    for canonical, slug in SEGURO_FILES.items():
        d = load_seguro(slug)
        if not d:
            print(f"  [SKIP] no hay parsed para {canonical}")
            continue
        seguros_data[canonical] = {
            "diarios":     d.get("diarios", []),
            "mensual":     d.get("mensual", {}),
            "rango_fechas":d.get("rango_fechas"),
            "total_dias":  d.get("total_dias", 0),
        }
    insights_block = compute_insights(seguros_data)

    # Rangos globales
    all_dates = []
    for s in seguros_data.values():
        for d in s["diarios"]:
            all_dates.append(d["fecha"])
    fecha_min = min(all_dates) if all_dates else None
    fecha_max = max(all_dates) if all_dates else None

    out = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "fuente_de_verdad": "RECIBIDOS (SF) - leads que llegan a Salesforce de SURA",
            "seguros": list(seguros_data.keys()),
            "rango_global": {"desde": fecha_min, "hasta": fecha_max},
        },
        "seguros":         seguros_data,
        "insights":        insights_block["insights"],
        "recomendaciones": insights_block["recomendaciones"],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    total_dias = sum(len(s["diarios"]) for s in seguros_data.values())
    print(f"[crm dataset] -> {OUT_PATH}")
    print(f"  seguros:       {len(seguros_data)}")
    print(f"  total dias:    {total_dias:,}")
    print(f"  rango:         {fecha_min} -> {fecha_max}")
    print(f"  insights:      {len(insights_block['insights'])}")
    print(f"  recos:         {len(insights_block['recomendaciones'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
