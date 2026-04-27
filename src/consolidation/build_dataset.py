"""Consolidacion v3: dataset basado en RECIBIDOS (SF) — leads reales SF.

Reemplaza al modelo anterior que usaba 'Total Pauta' del Resumen mensual.
Fuente: raw/sheets_crm/parsed/mensual_consolidado_*.json (16+ meses x 4 seguros).

Output: docs/assets/data.json con shape:
  meta            -> info de generacion + alcance temporal
  kpis_globales   -> totales mes actual basados en SF
  alertas_criticas
  seguros[]       -> snapshot mes actual con SF + Pauta + Google + Meta + Bing
  evolucion_mom[] -> serie temporal por seguro (todos los meses disponibles)
  campanias[]     -> Google Ads por seguro
  cruces          -> SF vs Pauta vs Google Ads conv (gap de tracking)
  optimizaciones  -> escalar/pausar/destrabar/quality
  recomendaciones -> generadas por analysis/run_all.py
  discrepancias_y_gaps
  caso_negocio
"""

from __future__ import annotations

import json
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
SHEETS_PARSED = RAW / "sheets_crm" / "parsed"


def _slug(seguro: str) -> str:
    return seguro.lower().replace(" ", "-").replace("ñ", "n").replace("í", "i")\
        .replace("á", "a").replace("é", "e").replace("ó", "o").replace("ú", "u")


def _latest_json(d: Path, prefix: str) -> Path | None:
    files = sorted(d.glob(f"{prefix}*.json"))
    return files[-1] if files else None


def _parse_campaign_row(cells: list) -> dict | None:
    """Parser robusto de filas de Google Ads UI.

    Estrategia: usa el indice de la celda que contiene la estrategia de bidding
    ("Maximiza las conversiones" / "Manual" / etc.) como ancla. A partir de ahi
    las siguientes columnas son [clicks, ctr_conv, conversiones, cpc_avg, cpa].

    Las columnas de "cuotas perdidas" entre la celda 10 y la estrategia pueden
    venir vacias (mostrando '—') lo cual desplaza indices fijos - por eso el
    parser viejo fallaba en Motos y otras cuentas.
    """
    import re
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
    if not name: return None

    def num(s, default=0.0):
        if s is None or s == "": return default
        s = str(s).strip().replace("US$","").replace("$","").replace(" ","")
        if not s or s in ("-","—"): return default
        if "%" in s:
            s = s.replace("%","")
            try: return float(s.replace(".","").replace(",",".")) / 100
            except: return default
        if "," in s and "." in s: s = s.replace(".","").replace(",",".")
        elif "," in s: s = s.replace(",",".")
        elif s.count(".")==1 and len(s.split(".")[1])<=2: pass
        else: s = s.replace(".","")
        try: return float(s)
        except: return default

    # Presupuesto
    presupuesto_num = 0
    presupuesto_str = ""
    if len(cells) > 1:
        m = re.search(r"([\d\.,]+)\s*(?:US\$|\$)/d[ií]a", cells[1])
        if m:
            presupuesto_num = num(m.group(1))
            presupuesto_str = f"${presupuesto_num:.2f}/día"

    # Posiciones FIJAS y consistentes en todas las cuentas
    estado      = cells[2] if len(cells) > 2 else ""
    tipo        = cells[4] if len(cells) > 4 else ""
    impresiones = num(cells[5]) if len(cells) > 5 else 0
    # cells[6] = "X.XXXclics" -> extraer numero
    clicks_interaccion = 0
    if len(cells) > 6:
        m2 = re.match(r"^([\d\.,]+)", cells[6])
        if m2: clicks_interaccion = num(m2.group(1))
    ctr_pct = num(cells[7])  if len(cells) > 7  else 0
    cpc     = num(cells[8])  if len(cells) > 8  else 0
    coste   = num(cells[9])  if len(cells) > 9  else 0

    # ANCLA: estrategia de bidding. Buscar dinamicamente.
    BIDDING_KEYWORDS = ["Maximiza", "Maximizar", "Manual", "Smart Bidding",
                        "Target ", "Maximum ", "Lance", "tCPA", "tROAS",
                        "Generar el m"]  # "Generar el máximo de..."
    strat_idx = -1
    for i in range(10, len(cells)):
        cell_text = cells[i] or ""
        if any(kw in cell_text for kw in BIDDING_KEYWORDS):
            strat_idx = i
            break

    # Cuotas perdidas: estan en cells[10..strat_idx-1] pero pueden ser '—' (None)
    # Pattern observado: 4 columnas %.
    # cell[10] = cuota impr search
    # cell[11] = cuota perdida budget
    # cell[12] = cuota impr search abs
    # cell[13] = cuota perdida ranking
    cuota_imp_search        = num(cells[10]) if len(cells) > 10 else 0
    cuota_perdida_budget    = num(cells[11]) if len(cells) > 11 else 0
    cuota_imp_abs           = num(cells[12]) if len(cells) > 12 else 0
    cuota_perdida_ranking   = num(cells[13]) if len(cells) > 13 else 0

    # Despues del ancla buscamos hacia atras: CPA es siempre la ULTIMA celda con
    # patron "X,XX US$" (numero + US$). Antes esta CPC medio (otro US$),
    # antes conversiones (decimal con coma), antes CTR conv (%), antes clicks (entero).
    estrategia = cells[strat_idx] if strat_idx >= 0 else ""
    clicks_post = 0
    ctr_conv    = 0
    conversiones= 0
    cpc_avg     = 0
    cpa         = 0

    if strat_idx >= 0:
        # Recolectar celdas no vacias despues del ancla, preservando indices
        post = [(i, (cells[i] or "").strip()) for i in range(strat_idx + 1, len(cells))]
        non_empty = [(i, v) for i, v in post if v and v not in ("-", "—")]

        # CPA: ultima celda que matchea "X,XX US$" o "X.XX US$"
        cpa_pos = -1
        for j in range(len(non_empty) - 1, -1, -1):
            v = non_empty[j][1]
            if re.match(r"^[\d][\d\.,]*\s*US\$\s*$", v):
                cpa = num(v)
                cpa_pos = j
                break

        if cpa_pos >= 0:
            # CPC medio: penultima celda US$ antes del CPA, si existe y no es CPA mismo
            for j in range(cpa_pos - 1, -1, -1):
                v = non_empty[j][1]
                if re.match(r"^[\d][\d\.,]*\s*US\$\s*$", v):
                    cpc_avg = num(v)
                    break

            # Conversiones: ultimo numero decimal SIN US$ SIN % antes del CPA
            for j in range(cpa_pos - 1, -1, -1):
                v = non_empty[j][1]
                if "US$" in v or "%" in v:
                    continue
                if re.match(r"^[\d\.,]+$", v):
                    conversiones = num(v)
                    conv_pos = j
                    break

            # CTR conv: ultima celda con % antes de las conversiones
            for j in range(non_empty.index(non_empty[cpa_pos]) - 1, -1, -1):
                v = non_empty[j][1]
                if "%" in v and "US$" not in v:
                    ctr_conv = num(v)
                    break

            # clicks: primera celda numerica entera/decimal sin US$/% en el bloque
            for i, v in non_empty[:cpa_pos]:
                if "US$" in v or "%" in v:
                    continue
                if re.match(r"^[\d\.,]+$", v):
                    clicks_post = num(v)
                    break

            # Si clicks_post coincide con conversiones (layout degradado sin clicks puro),
            # descartarlo para usar el de cells[6] como fallback.
            if conversiones and clicks_post and abs(clicks_post - conversiones) < 0.5:
                clicks_post = 0
        else:
            # fallback: no hay US$ post-ancla. Layout muy degradado (ej Salud Animal)
            # Tomar primer numero como clicks o conv segun orden
            if non_empty:
                clicks_post = num(non_empty[0][1])
                if len(non_empty) > 1: ctr_conv = num(non_empty[1][1])
                if len(non_empty) > 2: conversiones = num(non_empty[2][1])

    # clicks definitivos: priorizar post-ancla. Si no hay, usar fallback solo si es coherente (clicks <= impresiones).
    if clicks_post:
        clicks = clicks_post
    elif clicks_interaccion and clicks_interaccion <= impresiones * 1.05:
        clicks = clicks_interaccion
    else:
        clicks = 0  # mejor 0 que dato incoherente

    # Salud Animal y otros casos: si no hay clicks_post, conv puede no estar.
    # Recomputar CPA si tenemos coste y conv pero no cpa explicito
    if not cpa and conversiones and coste:
        cpa = coste / conversiones

    name_up = name.upper()
    subtipo = "OTRO"
    if "PMAX" in name_up: subtipo = "PMAX"
    elif "SEARCH_SEGMENT" in name_up or "search-segment" in name.lower(): subtipo = "SEARCH_SEGMENT"
    elif "SEARCH_RETENTION" in name_up or "search-retention" in name.lower(): subtipo = "SEARCH_RETENTION"
    elif "SEARCH_CONQUEST" in name_up: subtipo = "SEARCH_CONQUEST"

    flags = []
    if "limit" in (estado or "").lower() or "polít" in (estado or "").lower(): flags.append("policy_limited")
    if "rechaz" in (estado or "").lower(): flags.append("rejected")
    if cuota_perdida_budget > 0.20: flags.append("budget_constrained")
    if cuota_perdida_ranking > 0.30: flags.append("ranking_issue")

    # optimization_score: cells[3] suele ser "add_add 85,1 %" o "84 %" o "—"
    opt_raw = cells[3] if len(cells) > 3 else ""
    m_opt = re.search(r"(\d{1,3}(?:[\.,]\d+)?)\s*%", opt_raw or "")
    optimization_score = num(m_opt.group(1) + "%") if m_opt else 0

    return {
        "nombre": name, "subtipo": subtipo,
        "presupuesto_diario": presupuesto_num, "presupuesto_str": presupuesto_str,
        "estado": estado, "tipo": tipo,
        "optimization_score": optimization_score,
        "impresiones": impresiones, "clicks": clicks, "ctr_pct": ctr_pct,
        "cpc": cpc, "coste": coste,
        "cuota_imp_search": cuota_imp_search,
        "cuota_perdida_budget": cuota_perdida_budget,
        "cuota_perdida_ranking": cuota_perdida_ranking,
        "estrategia": estrategia, "conversiones": conversiones, "cpa": cpa,
        "flags": flags,
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
        sum_imp  = sum(c["impresiones"] for c in campanias)
        sum_clk  = sum(c["clicks"]      for c in campanias)
        sum_cost = sum(c["coste"]       for c in campanias)
        sum_conv = sum(c["conversiones"]for c in campanias)
        por_subtipo: dict = {}
        for c in campanias:
            t = c["subtipo"]
            por_subtipo.setdefault(t, {"coste":0,"conv":0,"imp":0,"clicks":0,"n":0})
            por_subtipo[t]["coste"]  += c["coste"]
            por_subtipo[t]["conv"]   += c["conversiones"]
            por_subtipo[t]["imp"]    += c["impresiones"]
            por_subtipo[t]["clicks"] += c["clicks"]
            por_subtipo[t]["n"]      += 1
        for t, v in por_subtipo.items():
            v["cpa"] = (v["coste"] / v["conv"]) if v["conv"] else 0
        out[seguro] = {
            "customer_id":  info["id"],
            "ocid":         info["ocid"],
            "extracted_at": data.get("extracted_at"),
            "campanias_count": len(campanias),
            "kpis": {
                "impresiones":  sum_imp, "clicks": sum_clk,
                "coste_usd": sum_cost, "conversiones": sum_conv,
                "ctr": (sum_clk/sum_imp) if sum_imp else 0,
                "cpc": (sum_cost/sum_clk) if sum_clk else 0,
                "cpa": (sum_cost/sum_conv) if sum_conv else 0,
            },
            "por_subtipo": por_subtipo,
            "campanias":  campanias,
        }
    return out


# ====================== SHEETS (FUENTE VERDAD: SF) ======================

MES_LABELS = {
    "01": "ene", "02": "feb", "03": "mar", "04": "abr",
    "05": "may", "06": "jun", "07": "jul", "08": "ago",
    "09": "sep", "10": "oct", "11": "nov", "12": "dic",
}


def label_mes(ym: str) -> str:
    """'2026-04' -> 'abr 2026'"""
    if not ym or "-" not in ym:
        return ym
    y, m = ym.split("-")
    return f"{MES_LABELS.get(m, m)} {y}"


def load_sheets_per_seguro() -> dict:
    """Carga el mensual_consolidado_*.json de raw/sheets_crm/parsed/."""
    latest = _latest_json(SHEETS_PARSED, "mensual_consolidado_")
    if not latest:
        return {}
    return json.loads(latest.read_text(encoding="utf-8"))


def build_evolucion_mom(sheets: dict, year_filter: str | None = None) -> dict:
    """Construye serie temporal MoM por seguro.

    Si year_filter='2026' filtra solo ese año. Si None, devuelve todo.
    """
    # Recolectar todos los meses disponibles (union de todos los seguros)
    all_months: set = set()
    for seguro, mensual in sheets.items():
        for ym in mensual.keys():
            if year_filter is None or ym.startswith(year_filter):
                all_months.add(ym)
    meses_sorted = sorted(all_months)  # antiguo -> nuevo

    out = {"meses": [label_mes(m) for m in meses_sorted], "meses_iso": meses_sorted, "por_seguro": {}}
    for seguro in SEGUROS_PRINCIPALES:
        mensual = sheets.get(seguro, {})
        serie = []
        for ym in meses_sorted:
            b = mensual.get(ym)
            if not b:
                serie.append({"mes": label_mes(ym), "mes_iso": ym, "vacio": True})
                continue
            serie.append({
                "mes":            label_mes(ym),
                "mes_iso":        ym,
                "recibidos_sf":   int(b.get("recibidos_sf") or 0),
                "recibidos_ga":   int(b.get("recibidos_ga") or 0),
                "requeridos":     int(b.get("requeridos") or 0),
                "total_pauta":    int(b.get("total_pauta") or 0),
                "leads_google":   int(b.get("leads_google") or 0),
                "consumo_google": round(b.get("consumo_google") or 0, 2),
                "leads_meta":     int(b.get("leads_meta") or 0),
                "consumo_meta":   round(b.get("consumo_meta") or 0, 2),
                "leads_bing":     int(b.get("leads_bing") or 0),
                "consumo_bing":   round(b.get("consumo_bing") or 0, 2),
                "cumpl_sf_vs_req":   round(b.get("cumpl_sf_vs_req") or 0, 4),
                "cumpl_pauta_vs_req":round(b.get("cumpl_pauta_vs_req") or 0, 4),
                "cumpl_sf_vs_pauta": round(b.get("cumpl_sf_vs_pauta") or 0, 4),
                "cpl_negocio_sf":    round(b.get("cpl_negocio_sf") or 0, 2),
                "cpl_pauta":         round(b.get("cpl_pauta") or 0, 2),
            })
        out["por_seguro"][seguro] = serie
    return out


def build_cruces(google_ads: dict, sheets: dict, mes_iso: str) -> dict:
    cruces = []
    for seguro in SEGUROS_PRINCIPALES:
        ga = google_ads.get(seguro) or {"kpis": {}}
        b  = (sheets.get(seguro) or {}).get(mes_iso) or {}
        ga_conv = ga["kpis"].get("conversiones") or 0
        sf_leads = b.get("recibidos_sf") or 0
        pauta = b.get("total_pauta") or 0
        ga_inv_extr = ga["kpis"].get("coste_usd") or 0
        ga_inv_sheet = b.get("consumo_google") or 0
        cruces.append({
            "seguro":              seguro,
            "recibidos_sf":        int(sf_leads),
            "total_pauta":         int(pauta),
            "google_ads_conv":     int(ga_conv),
            "leads_google_sheet":  int(b.get("leads_google") or 0),
            "leads_meta_sheet":    int(b.get("leads_meta") or 0),
            "leads_bing_sheet":    int(b.get("leads_bing") or 0),
            "ratio_ga_conv_vs_sf":  round((ga_conv / sf_leads), 3) if sf_leads else 0,
            "ratio_pauta_vs_sf":    round((pauta / sf_leads), 3) if sf_leads else 0,
            "gap_conv_vs_sf":      int(sf_leads - ga_conv),
            "inversion_ga_extractor": round(ga_inv_extr, 2),
            "inversion_ga_sheet":  round(ga_inv_sheet, 2),
            "delta_inversion":     round(ga_inv_extr - ga_inv_sheet, 2),
        })
    return {"mes": label_mes(mes_iso), "mes_iso": mes_iso, "por_seguro": cruces}


def build_optimizaciones(google_ads: dict) -> dict:
    todas = []
    for seguro, ga in google_ads.items():
        if not ga: continue
        for c in ga["campanias"]:
            todas.append({"seguro": seguro, **c})

    escalar = sorted(
        [c for c in todas if c["cpa"] > 0 and c["conversiones"] > 50 and c["cuota_perdida_budget"] > 0.10],
        key=lambda c: (c["cpa"], -c["cuota_perdida_budget"]),
    )[:5]
    pausar = sorted(
        [c for c in todas if c["coste"] > 1000 and c["cpa"] > 15],
        key=lambda c: c["cpa"], reverse=True,
    )[:5]
    destrabar = [c for c in todas if "policy_limited" in c["flags"] or "rejected" in c["flags"]]
    destrabar.sort(key=lambda c: c["coste"], reverse=True)
    destrabar = destrabar[:8]
    ranking_issues = sorted(
        [c for c in todas if "ranking_issue" in c["flags"]],
        key=lambda c: c["cuota_perdida_ranking"], reverse=True,
    )[:5]

    def compact(c):
        return {
            "seguro": c["seguro"], "nombre": c["nombre"], "subtipo": c["subtipo"],
            "estado": c["estado"], "presupuesto_diario": c["presupuesto_diario"],
            "coste": c["coste"], "conversiones": c["conversiones"], "cpa": c["cpa"],
            "cuota_perdida_budget": c["cuota_perdida_budget"],
            "cuota_perdida_ranking": c["cuota_perdida_ranking"],
            "flags": c["flags"],
        }
    return {
        "escalar":        [compact(c) for c in escalar],
        "pausar":         [compact(c) for c in pausar],
        "destrabar":      [compact(c) for c in destrabar],
        "quality_issues": [compact(c) for c in ranking_issues],
    }


def build() -> dict:
    google_ads = load_google_ads()
    sheets     = load_sheets_per_seguro()

    # Detectar meses disponibles (todos)
    all_months = set()
    for s, mensual in sheets.items():
        all_months.update(mensual.keys())
    months_sorted = sorted(all_months)
    mes_actual_iso = months_sorted[-1] if months_sorted else None
    mes_anterior_iso = months_sorted[-2] if len(months_sorted) > 1 else None

    # Snapshot por seguro (mes actual)
    seguros_block = []
    total_inv_google = 0.0
    total_inv_meta = 0.0
    total_inv_bing = 0.0
    total_recibidos = 0
    total_requeridos = 0
    total_pauta = 0

    for seguro in SEGUROS_PRINCIPALES + SEGUROS_EXTRA_ADS_ONLY:
        ga = google_ads.get(seguro) or {"kpis": {}, "campanias": [], "campanias_count": 0, "por_subtipo": {}}
        sheet_mensual = sheets.get(seguro, {})
        b_now  = sheet_mensual.get(mes_actual_iso, {})
        b_prev = sheet_mensual.get(mes_anterior_iso, {}) if mes_anterior_iso else {}

        is_principal = seguro in SEGUROS_PRINCIPALES

        block = {
            "nombre":      seguro,
            "es_principal": is_principal,
            "google_ads":  {
                "kpis":            ga.get("kpis", {}),
                "campanias_count": ga.get("campanias_count", 0),
                "por_subtipo":     ga.get("por_subtipo", {}),
                "campanias":       ga.get("campanias", []),
            },
            "crm": {
                "recibidos_sf":     int(b_now.get("recibidos_sf") or 0),
                "recibidos_ga":     int(b_now.get("recibidos_ga") or 0),
                "requeridos":       int(b_now.get("requeridos") or 0),
                "total_pauta":      int(b_now.get("total_pauta") or 0),
                "leads_google":     int(b_now.get("leads_google") or 0),
                "consumo_google":   round(b_now.get("consumo_google") or 0, 2),
                "leads_meta":       int(b_now.get("leads_meta") or 0),
                "consumo_meta":     round(b_now.get("consumo_meta") or 0, 2),
                "leads_bing":       int(b_now.get("leads_bing") or 0),
                "consumo_bing":     round(b_now.get("consumo_bing") or 0, 2),
                "cumpl_sf_vs_req":  round(b_now.get("cumpl_sf_vs_req") or 0, 4),
                "cumpl_pauta_vs_req": round(b_now.get("cumpl_pauta_vs_req") or 0, 4),
                "cumpl_sf_vs_pauta":  round(b_now.get("cumpl_sf_vs_pauta") or 0, 4),
                "cpl_negocio_sf":   round(b_now.get("cpl_negocio_sf") or 0, 2),
                "cpl_pauta":        round(b_now.get("cpl_pauta") or 0, 2),
                # MoM
                "recibidos_sf_prev":     int(b_prev.get("recibidos_sf") or 0),
                "cumpl_sf_vs_req_prev":  round(b_prev.get("cumpl_sf_vs_req") or 0, 4),
                "cpl_negocio_sf_prev":   round(b_prev.get("cpl_negocio_sf") or 0, 2),
            },
        }
        seguros_block.append(block)
        if is_principal:
            total_inv_google += b_now.get("consumo_google") or 0
            total_inv_meta   += b_now.get("consumo_meta") or 0
            total_inv_bing   += b_now.get("consumo_bing") or 0
            total_recibidos  += b_now.get("recibidos_sf") or 0
            total_requeridos += b_now.get("requeridos") or 0
            total_pauta      += b_now.get("total_pauta") or 0

    inv_total = total_inv_google + total_inv_meta + total_inv_bing
    cumpl_global_sf    = (total_recibidos / total_requeridos) if total_requeridos else 0
    cumpl_global_pauta = (total_pauta / total_requeridos) if total_requeridos else 0
    cpl_negocio_avg    = (inv_total / total_recibidos) if total_recibidos else 0

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "periodo": {
                "mes_actual":     label_mes(mes_actual_iso),
                "mes_actual_iso": mes_actual_iso,
                "mes_anterior":   label_mes(mes_anterior_iso) if mes_anterior_iso else None,
                "mes_anterior_iso": mes_anterior_iso,
                "porcentaje_transcurrido": 0.70,
                "meses_disponibles": [label_mes(m) for m in months_sorted],
                "meses_disponibles_iso": months_sorted,
                "rango_total": {
                    "desde": months_sorted[0] if months_sorted else None,
                    "hasta": months_sorted[-1] if months_sorted else None,
                },
            },
            "cliente": "SURA Tech Colombia",
            "agencia": "Beyond Media Agency",
            "fuente_de_verdad": "RECIBIDOS (SF) - leads que llegan a Salesforce de SURA",
            "scope": {
                "seguros_principales": SEGUROS_PRINCIPALES,
                "seguros_extra_ads_only": SEGUROS_EXTRA_ADS_ONLY,
            },
        },
        "kpis_globales": {
            "inversion_total":          round(inv_total, 2),
            "inversion_google":         round(total_inv_google, 2),
            "inversion_meta":           round(total_inv_meta, 2),
            "inversion_bing":           round(total_inv_bing, 2),
            "leads_recibidos_sf":       int(total_recibidos),
            "leads_pauta_total":        int(total_pauta),
            "leads_requeridos":         int(total_requeridos),
            "cumpl_sf_vs_req":          round(cumpl_global_sf, 4),
            "cumpl_pauta_vs_req":       round(cumpl_global_pauta, 4),
            "cpl_negocio_promedio":     round(cpl_negocio_avg, 2),
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
        "evolucion_mom":    build_evolucion_mom(sheets),
        "cruces":           build_cruces(google_ads, sheets, mes_actual_iso) if mes_actual_iso else {},
        "optimizaciones":   build_optimizaciones(google_ads),
        "recomendaciones":  [],
        "discrepancias_y_gaps": {
            "ga4_eventos": "GA4 Data API no integrada en MVP. Mapeo evento -> seguro requiere intervencion manual.",
            "meta_ad_sets": "Solo nombres de 4 campanias capturadas; drill-down a ad sets requiere Meta Marketing API.",
            "salud_para_dos_y_animal": "Sin data CRM. Solo Google Ads (foco: setear tracking + potenciar).",
        },
        "caso_negocio": {
            "estado_actual": "",  # llenado por analysis
            "proyeccion_si_aplicamos_top5": "",
            "proximo_paso": "Migrar a APIs oficiales (Google Ads API, Meta Marketing API, GA4 Data API) para pipeline diario con alertas automaticas.",
        },
    }


def run() -> int:
    data = build()
    DOCS_DATA.parent.mkdir(parents=True, exist_ok=True)
    DOCS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[consolidation v3] -> {DOCS_DATA}")
    print(f"  meses disponibles: {len(data['meta']['periodo']['meses_disponibles'])}")
    print(f"  rango: {data['meta']['periodo']['rango_total']['desde']} -> {data['meta']['periodo']['rango_total']['hasta']}")
    print(f"  mes actual: {data['meta']['periodo']['mes_actual']}")
    k = data["kpis_globales"]
    print(f"  RECIBIDOS (SF): {k['leads_recibidos_sf']:,} de {k['leads_requeridos']:,} req")
    print(f"  Cumplimiento SF/Req: {k['cumpl_sf_vs_req']*100:.1f}%")
    print(f"  Pauta:    {k['leads_pauta_total']:,}")
    print(f"  Cumplimiento Pauta/Req: {k['cumpl_pauta_vs_req']*100:.1f}%")
    print(f"  Inversion: ${k['inversion_total']:,.0f} (Google ${k['inversion_google']:,.0f} / Meta ${k['inversion_meta']:,.0f} / Bing ${k['inversion_bing']:,.0f})")
    print(f"  CPL Negocio (sf): ${k['cpl_negocio_promedio']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
