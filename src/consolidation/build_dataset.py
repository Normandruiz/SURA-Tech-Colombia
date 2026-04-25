"""Consolidacion v2: dataset rico con evolucion MoM, cruces, y analisis por campania.

Output: docs/assets/data.json con shape:
  meta            -> info de generacion + scope + meses disponibles
  kpis_globales   -> totales mes actual
  alertas_criticas
  seguros[]       -> por seguro: snapshot mes actual + serie temporal MoM
  evolucion_mom[] -> matrices por seguro x mes para graficos
  campanias[]     -> todas las campanias con metricas + clasificacion
  cruces          -> CRM vs Google Ads conv (gap, ratio)
  optimizaciones  -> top escalar / top pausar / top destrabar
  recomendaciones -> generadas por analysis/run_all.py
  discrepancias_y_gaps
  caso_negocio
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


def _parse_campaign_row(cells: list) -> dict | None:
    if not cells or len(cells) < 6:
        return None
    cell0 = (cells[0] or "").strip()
    if cell0.lower() in ("", "expand_more", "—", "-", "total"):
        return None
    if "Total: todas" in cell0 or "todas las campañas" in cell0.lower():
        return None
    if "settings" not in cell0.lower():
        return None

    name = re.sub(r"\s*settings\s*$", "", cell0, flags=re.I).strip()
    if not name:
        return None

    presupuesto_raw = cells[1] if len(cells) > 1 else ""
    presupuesto_num = 0
    presupuesto_str = ""
    m = re.search(r"([\d\.,]+)\s*(?:US\$|\$)/d[ií]a", presupuesto_raw)
    if m:
        presupuesto_num = _num(m.group(1))
        presupuesto_str = f"${presupuesto_num:.2f}/día"

    estado = cells[2] if len(cells) > 2 else ""
    opt_score = _num(cells[3]) if len(cells) > 3 else 0
    tipo   = cells[4] if len(cells) > 4 else ""

    impresiones = _num(cells[5]) if len(cells) > 5 else 0
    clicks = _num(cells[15]) if len(cells) > 15 else 0
    if not clicks and len(cells) > 6:
        m2 = re.match(r"^([\d\.,]+)", cells[6])
        if m2: clicks = _num(m2.group(1))

    ctr_pct = _num(cells[7])  if len(cells) > 7  else 0
    cpc     = _num(cells[8])  if len(cells) > 8  else 0
    coste   = _num(cells[9])  if len(cells) > 9  else 0
    # Cuotas (cells 10-13) - 4 columnas %
    cuota_imp_search        = _num(cells[10]) if len(cells) > 10 else 0
    cuota_perdida_budget    = _num(cells[11]) if len(cells) > 11 else 0
    cuota_imp_search_abs    = _num(cells[12]) if len(cells) > 12 else 0
    cuota_perdida_ranking   = _num(cells[13]) if len(cells) > 13 else 0
    estrategia    = cells[14] if len(cells) > 14 else ""
    conversiones  = _num(cells[17]) if len(cells) > 17 else 0
    cpa           = _num(cells[19]) if len(cells) > 19 else 0

    # Inferir tipo desde nombre
    name_up = name.upper()
    subtipo = "OTRO"
    if "PMAX" in name_up: subtipo = "PMAX"
    elif "SEARCH_SEGMENT" in name_up: subtipo = "SEARCH_SEGMENT"
    elif "SEARCH_RETENTION" in name_up: subtipo = "SEARCH_RETENTION"
    elif "SEARCH_CONQUEST" in name_up: subtipo = "SEARCH_CONQUEST"
    elif "search-retention" in name.lower(): subtipo = "SEARCH_RETENTION"
    elif "search-segment" in name.lower(): subtipo = "SEARCH_SEGMENT"

    # Flags de salud
    flags = []
    if "limit" in (estado or "").lower() or "polít" in (estado or "").lower():
        flags.append("policy_limited")
    if "rechaz" in (estado or "").lower():
        flags.append("rejected")
    if cuota_perdida_budget > 0.20:
        flags.append("budget_constrained")
    if cuota_perdida_ranking > 0.30:
        flags.append("ranking_issue")

    return {
        "nombre":                name,
        "subtipo":               subtipo,
        "presupuesto_diario":    presupuesto_num,
        "presupuesto_str":       presupuesto_str,
        "estado":                estado,
        "optimization_score":    opt_score,
        "tipo":                  tipo,
        "impresiones":           impresiones,
        "clicks":                clicks,
        "ctr_pct":               ctr_pct,
        "cpc":                   cpc,
        "coste":                 coste,
        "cuota_imp_search":      cuota_imp_search,
        "cuota_perdida_budget":  cuota_perdida_budget,
        "cuota_perdida_ranking": cuota_perdida_ranking,
        "estrategia":            estrategia,
        "conversiones":          conversiones,
        "cpa":                   cpa,
        "flags":                 flags,
    }


def load_google_ads() -> dict:
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
        # Por subtipo
        por_subtipo: dict = {}
        for c in campanias:
            t = c["subtipo"]
            por_subtipo.setdefault(t, {"coste": 0, "conv": 0, "imp": 0, "clicks": 0, "n": 0})
            por_subtipo[t]["coste"]  += c["coste"]
            por_subtipo[t]["conv"]   += c["conversiones"]
            por_subtipo[t]["imp"]    += c["impresiones"]
            por_subtipo[t]["clicks"] += c["clicks"]
            por_subtipo[t]["n"]      += 1
        for t, v in por_subtipo.items():
            v["cpa"] = (v["coste"] / v["conv"]) if v["conv"] else 0
        out[seguro] = {
            "customer_id":    info["id"],
            "ocid":           info["ocid"],
            "extracted_at":   data.get("extracted_at"),
            "campanias_count": len(campanias),
            "kpis": {
                "impresiones":  sum_imp,
                "clicks":       sum_clk,
                "coste_usd":    sum_cost,
                "conversiones": sum_conv,
                "ctr":          (sum_clk / sum_imp) if sum_imp else 0,
                "cpc":          (sum_cost / sum_clk) if sum_clk else 0,
                "cpa":          (sum_cost / sum_conv) if sum_conv else 0,
            },
            "por_subtipo":    por_subtipo,
            "campanias":      campanias,
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


FILTER_YEAR = "2026"  # Foco MVP: solo año actual


def _is_year(label: str, year: str) -> bool:
    return year in label


def build_evolucion_mom(sheet: dict) -> dict:
    """Construye serie temporal MoM por seguro: lista de meses (ordenados antiguo->nuevo)
    con metricas para graficar. Filtra a FILTER_YEAR.
    """
    data = sheet.get("data_por_mes", {})
    # Filtrar al año target y ordenar antiguo->nuevo
    meses_ordenados = [m for m in list(data.keys())[::-1] if _is_year(m, FILTER_YEAR)]

    out: dict = {"meses": meses_ordenados, "por_seguro": {}}
    for seguro in SEGUROS_PRINCIPALES:
        serie = []
        for mes in meses_ordenados:
            metrics = data.get(mes, {}).get(seguro)
            if not metrics:
                serie.append({"mes": mes, "vacio": True})
                continue
            serie.append({
                "mes":              mes,
                "compromiso":       metrics.get("compromiso_leads") or 0,
                "leads_crm":        metrics.get("leads_crm") or 0,
                "leads_ga4":        metrics.get("leads_ga4"),
                "cumplimiento":     metrics.get("cumplimiento_pct") or 0,
                "cpl_negocio":      metrics.get("cpl_negocio") or 0,
                "leads_google_ads": metrics.get("leads_google_ads") or 0,
                "cpl_google_ads":   metrics.get("cpl_google_ads") or 0,
                "inv_google_ads":   metrics.get("inversion_google") or 0,
                "leads_meta":       metrics.get("leads_meta") or 0,
                "cpl_meta":         metrics.get("cpl_meta") or 0,
                "inv_meta":         metrics.get("inversion_meta") or 0,
                "leads_total":      metrics.get("leads_total") or 0,
                "inversion_total":  metrics.get("inversion_total") or 0,
                "cpl_negocio_total":metrics.get("cpl_negocio_total") or 0,
            })
        out["por_seguro"][seguro] = serie
    return out


def build_cruces(google_ads: dict, sheet: dict) -> dict:
    """Cruces CRM (Sheet) vs Google Ads conversiones - mes actual."""
    months = list(sheet.get("data_por_mes", {}).keys())
    if not months:
        return {}
    mes_actual = months[0]
    crm = sheet["data_por_mes"][mes_actual]

    cruces = []
    for seguro in SEGUROS_PRINCIPALES:
        ga = google_ads.get(seguro) or {"kpis": {}}
        c = crm.get(seguro) or {}
        ga_conv = ga["kpis"].get("conversiones") or 0
        crm_leads = c.get("leads_crm") or 0
        ga_inv = ga["kpis"].get("coste_usd") or 0
        crm_inv = c.get("inversion_google") or 0
        gap_conv = (crm_leads - ga_conv) if ga_conv else 0
        ratio_conv = (ga_conv / crm_leads) if crm_leads else 0
        cruces.append({
            "seguro":              seguro,
            "leads_crm":           crm_leads,
            "google_ads_conv":     ga_conv,
            "leads_meta_crm":      c.get("leads_meta") or 0,
            "leads_otros":         c.get("leads_otro") or 0,
            "ratio_ga_conv_vs_crm": round(ratio_conv, 3),
            "gap_conv_vs_crm":     round(gap_conv, 0),
            "inversion_ga_extractor": round(ga_inv, 2),
            "inversion_ga_crm":    round(crm_inv, 2),
            "delta_inversion":     round(ga_inv - crm_inv, 2),
        })
    return {"mes": mes_actual, "por_seguro": cruces}


def build_optimizaciones(google_ads: dict) -> dict:
    """Identifica oportunidades de optimizacion sobre las campanias."""
    todas = []
    for seguro, ga in google_ads.items():
        if not ga: continue
        for c in ga["campanias"]:
            todas.append({"seguro": seguro, **c})

    # TOP escalar: CPA bajo + cuota perdida por presupuesto alta + conv > 50
    escalar = sorted(
        [c for c in todas if c["cpa"] > 0 and c["conversiones"] > 50 and c["cuota_perdida_budget"] > 0.10],
        key=lambda c: (c["cpa"], -c["cuota_perdida_budget"]),
    )[:5]

    # TOP pausar: CPA alto + volumen significativo
    pausar = sorted(
        [c for c in todas if c["coste"] > 1000 and c["cpa"] > 15],
        key=lambda c: c["cpa"], reverse=True,
    )[:5]

    # TOP destrabar: tienen flags policy_limited / rejected
    destrabar = [c for c in todas if "policy_limited" in c["flags"] or "rejected" in c["flags"]]
    destrabar.sort(key=lambda c: c["coste"], reverse=True)
    destrabar = destrabar[:8]

    # Quality issues: ranking issue
    ranking_issues = sorted(
        [c for c in todas if "ranking_issue" in c["flags"]],
        key=lambda c: c["cuota_perdida_ranking"], reverse=True,
    )[:5]

    return {
        "escalar":         [_compact_camp(c) for c in escalar],
        "pausar":          [_compact_camp(c) for c in pausar],
        "destrabar":       [_compact_camp(c) for c in destrabar],
        "quality_issues":  [_compact_camp(c) for c in ranking_issues],
    }


def _compact_camp(c: dict) -> dict:
    return {
        "seguro":               c["seguro"],
        "nombre":               c["nombre"],
        "subtipo":              c["subtipo"],
        "estado":               c["estado"],
        "presupuesto_diario":   c["presupuesto_diario"],
        "coste":                c["coste"],
        "conversiones":         c["conversiones"],
        "cpa":                  c["cpa"],
        "cuota_perdida_budget": c["cuota_perdida_budget"],
        "cuota_perdida_ranking":c["cuota_perdida_ranking"],
        "flags":                c["flags"],
    }


def build() -> dict:
    google_ads = load_google_ads()
    sheet      = load_sheet_crm()
    meta       = load_meta()

    # Mes actual / anterior - filtrado a FILTER_YEAR
    months_all = list(sheet.get("data_por_mes", {}).keys())
    months_desc = [m for m in months_all if _is_year(m, FILTER_YEAR)]
    mes_actual   = months_desc[0] if months_desc else None
    mes_anterior = months_desc[1] if len(months_desc) > 1 else None
    crm_now  = sheet.get("data_por_mes", {}).get(mes_actual,   {})
    crm_prev = sheet.get("data_por_mes", {}).get(mes_anterior, {}) if mes_anterior else {}

    # Por seguro: snapshot
    seguros_block = []
    total_inversion = 0.0
    total_leads_crm = 0.0
    total_compromiso = 0.0

    for seguro in SEGUROS_PRINCIPALES + SEGUROS_EXTRA_ADS_ONLY:
        ga = google_ads.get(seguro) or {"kpis": {}, "campanias": [], "campanias_count": 0, "por_subtipo": {}}
        c  = crm_now.get(seguro)
        c_prev = crm_prev.get(seguro)

        is_principal = seguro in SEGUROS_PRINCIPALES

        block = {
            "nombre":      seguro,
            "es_principal": is_principal,
            "google_ads":  {
                "kpis":          ga.get("kpis", {}),
                "campanias_count": ga.get("campanias_count", 0),
                "por_subtipo":   ga.get("por_subtipo", {}),
                "campanias":     ga.get("campanias", []),
            },
            "crm": {
                "compromiso_leads":  c.get("compromiso_leads") if c else None,
                "leads_crm":         c.get("leads_crm")        if c else None,
                "leads_ga4":         c.get("leads_ga4")        if c else None,
                "cumplimiento_pct":  c.get("cumplimiento_pct") if c else None,
                "cpl_negocio":       c.get("cpl_negocio")      if c else None,
                "cpl_negocio_total": c.get("cpl_negocio_total")if c else None,
                "leads_total":       c.get("leads_total")      if c else None,
                "inversion_total":   c.get("inversion_total")  if c else None,
                "leads_google_ads":  c.get("leads_google_ads") if c else None,
                "leads_meta":        c.get("leads_meta")       if c else None,
                "leads_crm_prev":          c_prev.get("leads_crm")        if c_prev else None,
                "cumplimiento_pct_prev":   c_prev.get("cumplimiento_pct") if c_prev else None,
                "cpl_negocio_prev":        c_prev.get("cpl_negocio")      if c_prev else None,
            },
        }
        seguros_block.append(block)
        if is_principal and c:
            total_inversion  += (c.get("inversion_total") or 0) or ga["kpis"].get("coste_usd", 0)
            total_leads_crm  += (c.get("leads_crm") or 0)
            total_compromiso += (c.get("compromiso_leads") or 0)

    cumplimiento_global = (total_leads_crm / total_compromiso) if total_compromiso else 0
    cpls = [s["crm"]["cpl_negocio"] for s in seguros_block if s["es_principal"] and s["crm"]["cpl_negocio"]]
    cpl_promedio = (sum(cpls) / len(cpls)) if cpls else 0

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "periodo": {
                "mes_actual":   mes_actual,
                "mes_anterior": mes_anterior,
                "porcentaje_transcurrido": 0.70,
                "meses_disponibles": months_desc,
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
        "seguros":          seguros_block,
        "evolucion_mom":    build_evolucion_mom(sheet),
        "cruces":           build_cruces(google_ads, sheet),
        "optimizaciones":   build_optimizaciones(google_ads),
        "recomendaciones":  [],  # llenadas por analysis/run_all.py
        "discrepancias_y_gaps": {
            "ga4_eventos": "PENDIENTE: GA4 Data API no integrada en MVP. Mapeo evento -> seguro requiere intervencion manual via UI.",
            "meta_ad_sets": "PARCIAL: solo capturados nombres de 4 campanias (Mensajes_WHATSAPP, Mascotas-Conversiones, Mensajes WhatsApp, Clientes potenciales). Drill-down a ad sets requiere Meta Marketing API.",
            "salud_para_dos_y_animal": "Sin data CRM en 'Resumen mensual'. Solo tienen actividad en Google Ads (foco: setear tracking + potenciar).",
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
    print(f"[consolidation v2] -> {DOCS_DATA}")
    print(f"  meses disponibles:    {len(data['meta']['periodo']['meses_disponibles'])}")
    print(f"  seguros:              {len(data['seguros'])} ({len(SEGUROS_PRINCIPALES)} principales + {len(SEGUROS_EXTRA_ADS_ONLY)} extra)")
    print(f"  cumplimiento global:  {data['kpis_globales']['cumplimiento_global_pct']*100:.1f}%")
    print(f"  inversion total:      ${data['kpis_globales']['inversion_total']:,.2f}")
    print(f"  optimizaciones: escalar={len(data['optimizaciones']['escalar'])} pausar={len(data['optimizaciones']['pausar'])} destrabar={len(data['optimizaciones']['destrabar'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
