"""Consolidacion: lee raw/<seguro>/google_ads_*.json + raw/sheets_crm/*.json
y produce docs/assets/data.json con el shape que consume el dashboard.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from src.config import (
    ROOT,
    DOCS_DATA,
    SEGUROS_PRINCIPALES,
    SEGUROS_EXTRA_ADS_ONLY,
    GOOGLE_ADS_ACCOUNTS,
)


RAW = ROOT / "raw"


def _num(s, default=0.0):
    """Parser tolerante de numeros formato es-CO."""
    if s is None or s == "":
        return default
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace("US$", "").replace("$", "").replace(" ", "").replace("\u00A0", "")
    if not s or s in ("-", "—"):
        return default
    if "%" in s:
        s = s.replace("%", "")
        try:
            return float(s.replace(".", "").replace(",", ".")) / 100
        except Exception:
            return default
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) <= 2:
        pass
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return default


def _slug(seguro: str) -> str:
    return seguro.lower().replace(" ", "-").replace("ñ", "n").replace("í", "i")\
        .replace("á", "a").replace("é", "e").replace("ó", "o").replace("ú", "u")


def _latest_json(d: Path, prefix: str) -> Path | None:
    files = sorted(d.glob(f"{prefix}*.json"))
    return files[-1] if files else None


def _parse_campaign_row(cells: list[str]) -> dict | None:
    """Mapea las celdas crudas de una fila de campania de Google Ads UI a metricas.

    Layout observado (4 cuentas validadas):
    [0] nombre + 'settings'
    [1] nombre + presupuesto/dia
    [2] estado (Apto / Rechazado / Pausada / etc.)
    [3] optimization score
    [4] tipo (Busqueda / PMax / etc.)
    [5] impresiones
    [6] interacciones con sufijo (ej '8.318clics, implicaciones')
    [7] tasa interaccion (CTR%)
    [8] coste medio (CPC US$)
    [9] coste US$
    [10..13] cuotas impresion / cuotas perdidas por presupuesto / ranking (4 cols %)
    [14] estrategia bid
    [15] clicks puro (numero sin sufijo)
    [16] CTR conversion
    [17] conversiones
    [18] coste medio repetido
    [19] CPA / coste por conversion

    Devuelve None si la fila no es una campania real (totales, expand_more, etc.).
    """
    if not cells or len(cells) < 6:
        return None
    cell0 = (cells[0] or "").strip()

    # Filtros: descartar filas que NO son campanias
    if cell0.lower() in ("", "expand_more", "—", "-", "total"):
        return None
    if "Total: todas" in cell0 or "todas las campañas" in cell0.lower():
        return None
    if "settings" not in cell0.lower():
        return None

    name = re.sub(r"\s*settings\s*$", "", cell0, flags=re.I).strip()
    if not name:
        return None

    presupuesto = ""
    if len(cells) > 1:
        m = re.search(r"([\d\.,]+\s*(?:US\$|\$)/d[ií]a)", cells[1])
        if m:
            presupuesto = m.group(1)

    estado = cells[2] if len(cells) > 2 else ""
    tipo   = cells[4] if len(cells) > 4 else ""

    impresiones = _num(cells[5]) if len(cells) > 5 else 0

    # clicks: priorizar cells[15] (numero limpio) sobre cells[6] (con sufijo 'clics')
    clicks = _num(cells[15]) if len(cells) > 15 else 0
    if not clicks and len(cells) > 6:
        # extraer numero antes de 'clics'
        m = re.match(r"^([\d\.,]+)", cells[6])
        if m:
            clicks = _num(m.group(1))

    ctr_pct      = _num(cells[7])  if len(cells) > 7  else 0
    cpc          = _num(cells[8])  if len(cells) > 8  else 0
    coste        = _num(cells[9])  if len(cells) > 9  else 0
    estrategia   = cells[14]       if len(cells) > 14 else ""
    conversiones = _num(cells[17]) if len(cells) > 17 else 0
    cpa          = _num(cells[19]) if len(cells) > 19 else 0

    return {
        "nombre":       name,
        "presupuesto":  presupuesto,
        "estado":       estado,
        "tipo":         tipo,
        "impresiones":  impresiones,
        "clicks":       clicks,
        "ctr_pct":      ctr_pct,
        "cpc":          cpc,
        "coste":        coste,
        "estrategia":   estrategia,
        "conversiones": conversiones,
        "cpa":          cpa,
    }


def load_google_ads() -> dict:
    """Por cada seguro, lee el ultimo JSON de raw/<slug>/google_ads_*.json
    y devuelve {seguro: {kpis_agregados, campanias[]}}.
    """
    out: dict = {}
    for seguro, info in GOOGLE_ADS_ACCOUNTS.items():
        slug = _slug(seguro)
        d = RAW / slug
        latest = _latest_json(d, "google_ads_")
        if not latest:
            out[seguro] = None
            continue
        data = json.loads(latest.read_text(encoding="utf-8"))
        rows = data.get("campaigns_rows", [])
        campanias = [_parse_campaign_row(r["cells"]) for r in rows if r.get("cells")]
        campanias = [c for c in campanias if c is not None and c["coste"] > 0]
        # Agregados
        sum_imp  = sum(c["impresiones"] for c in campanias)
        sum_clk  = sum(c["clicks"]      for c in campanias)
        sum_cost = sum(c["coste"]       for c in campanias)
        sum_conv = sum(c["conversiones"]for c in campanias)
        ctr  = (sum_clk / sum_imp) if sum_imp else 0
        cpc  = (sum_cost / sum_clk) if sum_clk else 0
        cpa  = (sum_cost / sum_conv) if sum_conv else 0

        out[seguro] = {
            "customer_id":  info["id"],
            "ocid":         info["ocid"],
            "extracted_at": data.get("extracted_at"),
            "campanias_count": len(campanias),
            "kpis": {
                "impresiones":  sum_imp,
                "clicks":       sum_clk,
                "coste_usd":    sum_cost,
                "conversiones": sum_conv,
                "ctr":          ctr,
                "cpc":          cpc,
                "cpa":          cpa,
            },
            "campanias": campanias,
        }
    return out


def load_sheet_crm() -> dict:
    d = RAW / "sheets_crm"
    latest = _latest_json(d, "resumen_mensual_")
    if not latest:
        return {}
    return json.loads(latest.read_text(encoding="utf-8"))


def load_meta() -> dict:
    d = RAW / "meta"
    latest = _latest_json(d, "meta_campaigns_")
    if not latest:
        return {}
    return json.loads(latest.read_text(encoding="utf-8"))


def build() -> dict:
    google_ads = load_google_ads()
    sheet      = load_sheet_crm()
    meta       = load_meta()

    # Mes actual del Sheet (primer bloque)
    months = list(sheet.get("data_por_mes", {}).keys())
    mes_actual = months[0] if months else None
    mes_anterior = months[1] if len(months) > 1 else None
    crm_now  = sheet.get("data_por_mes", {}).get(mes_actual,   {})
    crm_prev = sheet.get("data_por_mes", {}).get(mes_anterior, {}) if mes_anterior else {}

    # Construir bloque por seguro
    seguros_block = []
    total_inversion = 0.0
    total_leads_crm = 0.0
    total_compromiso = 0.0
    cumplimientos = []

    for seguro in SEGUROS_PRINCIPALES + SEGUROS_EXTRA_ADS_ONLY:
        ga = google_ads.get(seguro) or {"kpis": {"coste_usd": 0, "impresiones": 0, "clicks": 0, "conversiones": 0}, "campanias": []}
        c  = crm_now.get(seguro)
        c_prev = crm_prev.get(seguro)

        is_principal = seguro in SEGUROS_PRINCIPALES

        block = {
            "nombre":      seguro,
            "es_principal": is_principal,
            "google_ads":  {
                "kpis":     ga.get("kpis", {}),
                "campanias_count": ga.get("campanias_count", 0),
                "campanias": ga.get("campanias", [])[:50],
            },
            "crm": {
                "compromiso_leads":  c.get("compromiso_leads") if c else None,
                "leads_crm":         c.get("leads_crm")        if c else None,
                "cumplimiento_pct":  c.get("cumplimiento_pct") if c else None,
                "cpl_negocio":       c.get("cpl_negocio")      if c else None,
                "cpl_negocio_total": c.get("cpl_negocio_total")if c else None,
                "leads_total":       c.get("leads_total")      if c else None,
                "inversion_total":   c.get("inversion_total")  if c else None,
                "leads_google_ads":  c.get("leads_google_ads") if c else None,
                "leads_meta":        c.get("leads_meta")       if c else None,
                # MoM
                "leads_crm_prev":          c_prev.get("leads_crm")        if c_prev else None,
                "cumplimiento_pct_prev":   c_prev.get("cumplimiento_pct") if c_prev else None,
                "cpl_negocio_prev":        c_prev.get("cpl_negocio")      if c_prev else None,
            },
        }
        seguros_block.append(block)

        if is_principal and c:
            total_inversion  += (c.get("inversion_total")  or 0) or ga["kpis"].get("coste_usd", 0)
            total_leads_crm  += (c.get("leads_crm") or 0)
            total_compromiso += (c.get("compromiso_leads") or 0)
            if c.get("cumplimiento_pct") is not None:
                cumplimientos.append(c["cumplimiento_pct"])

    cumplimiento_global = (total_leads_crm / total_compromiso) if total_compromiso else 0
    cpl_promedio = (sum(c["crm"]["cpl_negocio"] for c in seguros_block
                        if c["es_principal"] and c["crm"]["cpl_negocio"])
                    / sum(1 for c in seguros_block
                          if c["es_principal"] and c["crm"]["cpl_negocio"])) if cumplimientos else 0

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "periodo": {
                "mes_actual":   mes_actual,
                "mes_anterior": mes_anterior,
                "porcentaje_transcurrido": 0.70,  # del Sheet (header "Transcurrido mes 70%")
            },
            "cliente": "SURA Tech Colombia",
            "agencia": "Beyond Media Agency",
            "scope": {
                "seguros_principales": SEGUROS_PRINCIPALES,
                "seguros_extra_ads_only": SEGUROS_EXTRA_ADS_ONLY,
            },
        },
        "kpis_globales": {
            "inversion_total":      round(total_inversion, 2),
            "leads_crm_totales":    int(total_leads_crm),
            "compromiso_leads_total": int(total_compromiso),
            "cumplimiento_global_pct": round(cumplimiento_global, 4),
            "cpl_negocio_promedio": round(cpl_promedio, 2),
        },
        "alertas_criticas": [
            {
                "tipo": "accounts_not_publishing",
                "severidad": "critica",
                "titulo": "5 cuentas con anuncios que no se están publicando",
                "detalle": "Detectado en el MCC SURATECH - COLOMBIA. Inversión potencial parada.",
                "accion_sugerida": "Revisar el estado y reactivar publicación HOY.",
            },
            {
                "tipo": "financial_services_verification",
                "severidad": "critica",
                "titulo": "Verificación de servicios financieros pendiente en 3 cuentas",
                "detalle": "Bloqueante administrativo de Google Ads para publicar anuncios de seguros.",
                "accion_sugerida": "Enviar documentación esta semana antes que limite delivery.",
            },
        ],
        "seguros": seguros_block,
        "recomendaciones": [],  # Lleno desde analysis/run_all.py
        "discrepancias_y_gaps": {
            "ga4_eventos": "PENDIENTE: el pipeline manual no logra mapear eventos GA4 -> seguro automaticamente. Recomendar migrar a GA4 Data API.",
            "meta_ad_sets": "PARCIAL: solo capturados nombres de 4 campanias (Mensajes_WHATSAPP, Mascotas-Conversiones, Mensajes WhatsApp, Clientes potenciales). Drill-down a ad sets por seguro requiere Meta Marketing API.",
            "salud_para_dos_y_animal": "Sin data CRM en 'Resumen mensual'. Solo tienen actividad en Google Ads / Meta (foco: potenciar).",
        },
        "caso_negocio": {
            "estado_actual": (
                f"Cumplimiento global {round(cumplimiento_global*100,1)}% vs 70% transcurrido del mes. "
                f"Arrendamiento crítico (32%), Viajes (43%), Autos (57%), Motos (55%)."
            ),
            "proyeccion_si_aplicamos_top5": (
                "Aplicando las top 5 recomendaciones (escalar lo que rinde, pausar lo que no, "
                "destrabar 5+3 cuentas con bloqueos administrativos) estimamos +15-25% "
                "leads CRM en los proximos 7 dias y -10-15% CPL Negocio."
            ),
            "proximo_paso": (
                "Aprobar migracion a APIs oficiales (Google Ads API, Meta Marketing API, GA4 Data API) "
                "para pasar a pipeline diario con alertas automaticas."
            ),
        },
    }


def run() -> int:
    data = build()
    DOCS_DATA.parent.mkdir(parents=True, exist_ok=True)
    DOCS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[consolidation] -> {DOCS_DATA}")
    print(f"  seguros principales: {len([s for s in data['seguros'] if s['es_principal']])}")
    print(f"  seguros extra:       {len([s for s in data['seguros'] if not s['es_principal']])}")
    print(f"  cumplimiento global: {data['kpis_globales']['cumplimiento_global_pct']*100:.1f}%")
    print(f"  inversion total:     ${data['kpis_globales']['inversion_total']:,.2f}")
    print(f"  leads CRM totales:   {data['kpis_globales']['leads_crm_totales']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
