"""Construye docs/assets/data_paid_media.json para la pagina paid_media.html.

Foco: datos ACCIONABLES para mejorar performance de conversiones y bajar CPL,
no resultados (los resultados estan en index.html).

Incluye:
  - Por seguro: campanias Google (con metricas de eficiencia, cuotas perdidas, QS)
  - Por seguro: distribucion de inversion por subtipo (PMax / Search / Meta)
  - Por seguro: serie diaria de leads + consumo (Google y Meta) desde Sheet
  - Eventos de conversion mapeados por seguro (Google + Meta)
  - Recomendaciones especificas para potenciar conversiones / bajar CPL (top 10)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config import (
    ROOT,
    GOOGLE_ADS_ACCOUNTS,
    SEGUROS_PRINCIPALES,
)


SHEETS_PARSED = ROOT / "raw" / "sheets_crm" / "parsed"
DOCS = ROOT / "docs"
OUT_PATH = DOCS / "assets" / "data_paid_media.json"

SEGURO_FILES = {
    "Autos":         "autos",
    "Motos":         "motos",
    "Arrendamiento": "arriendo",
    "Viajes":        "viajes",
}


def _latest(d: Path, prefix: str) -> Path | None:
    files = sorted(d.glob(f"{prefix}*.json"))
    return files[-1] if files else None


def _slug(seguro: str) -> str:
    return seguro.lower().replace(" ", "-").replace("ñ", "n").replace("í", "i")\
        .replace("á", "a").replace("é", "e").replace("ó", "o").replace("ú", "u")


def load_google_ads_campaigns_for_seguro(seguro: str) -> list[dict]:
    """Lee el ultimo google_ads_*.json de la cuenta hija y devuelve campanias parseadas."""
    slug = _slug(seguro)
    d = ROOT / "raw" / slug
    latest = _latest(d, "google_ads_")
    if not latest:
        return []
    data = json.loads(latest.read_text(encoding="utf-8"))

    # Reusar el parser de build_dataset
    from src.consolidation.build_dataset import _parse_campaign_row
    rows = data.get("campaigns_rows", [])
    campanias = [_parse_campaign_row(r["cells"]) for r in rows if r.get("cells")]
    return [c for c in campanias if c is not None and c["coste"] > 0]


def load_sheet_diarios(slug: str) -> list[dict]:
    p = _latest(SHEETS_PARSED, f"{slug}_")
    if not p:
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("diarios", [])


# Eventos de conversion principales (confirmados por el cliente, abr 2026).
# OBSERVACION CLAVE: cada seguro optimiza contra un paso DISTINTO del funnel,
# lo cual genera trade-off entre volumen y calidad del lead.
EVENTOS_CONVERSION = {
    "Autos": {
        "google_ads_event":  "SURA.CO/AUTOS - Paso 1",
        "meta_event":        "SURA.CO/AUTOS - Paso 1",
        "etapa_funnel":      "Paso 1 (top of funnel)",
        "implicancia":       "Volumen alto, calidad baja - el evento es muy temprano en el flujo",
        "ventana_atribucion":"7 dias clic / 1 dia view",
    },
    "Motos": {
        "google_ads_event":  "SURA.CO/MOTOS - Paso 3",
        "meta_event":        "SURA.CO/MOTOS - Paso 3 - Planes",
        "etapa_funnel":      "Paso 3 (mid-bottom funnel)",
        "implicancia":       "Lead cualificado, ya vio planes - bidding mas conservador",
        "ventana_atribucion":"7 dias clic / 1 dia view",
    },
    "Arrendamiento": {
        "google_ads_event":  "SURA.CO/Arriendo - Paso 2 - Datos Propietario",
        "meta_event":        "SURA.CO/AD - Paso 3",
        "etapa_funnel":      "Google: Paso 2 / Meta: Paso 3",
        "implicancia":       "Inconsistencia: Google y Meta optimizan a etapas distintas - puede explicar diferencias de CPA",
        "ventana_atribucion":"7 dias clic / 1 dia view",
    },
    "Viajes": {
        "google_ads_event":  "SURA.CO/VIAJES - Paso 3",
        "meta_event":        "SURA.CO/VIAJES - Paso 4",
        "etapa_funnel":      "Google: Paso 3 / Meta: Paso 4",
        "implicancia":       "Inconsistencia: Meta optimiza al Paso 4 (mas profundo) que Google al Paso 3",
        "ventana_atribucion":"7 dias clic / 1 dia view",
    },
}

# Observacion cross-seguros para mostrar en el dashboard
EVENTOS_OBSERVACION_GLOBAL = (
    "Cada seguro optimiza contra un paso distinto del funnel: Autos = Paso 1 (temprano, "
    "alto volumen y baja calidad), Motos = Paso 3 (cualificado), Arrendamiento = Paso 2-3, "
    "Viajes = Paso 3-4 (mas profundo). En Arrendamiento y Viajes hay INCONSISTENCIA entre "
    "Google y Meta optimizando a pasos distintos - revisar si es intencional o si conviene "
    "alinear para tener metrica comparable."
)


def build_seguro_block(seguro: str) -> dict:
    campanias = load_google_ads_campaigns_for_seguro(seguro)
    slug = SEGURO_FILES[seguro]
    diarios = load_sheet_diarios(slug)

    # Distribucion por subtipo
    por_subtipo: dict = {}
    for c in campanias:
        t = c["subtipo"]
        por_subtipo.setdefault(t, {"coste": 0, "conv": 0, "imp": 0, "clicks": 0, "n": 0,
                                    "cuota_perdida_budget_acc": 0, "cuota_perdida_ranking_acc": 0})
        por_subtipo[t]["coste"]   += c["coste"]
        por_subtipo[t]["conv"]    += c["conversiones"]
        por_subtipo[t]["imp"]     += c["impresiones"]
        por_subtipo[t]["clicks"]  += c["clicks"]
        por_subtipo[t]["n"]       += 1
        por_subtipo[t]["cuota_perdida_budget_acc"]  += c["cuota_perdida_budget"]
        por_subtipo[t]["cuota_perdida_ranking_acc"] += c["cuota_perdida_ranking"]
    for t, v in por_subtipo.items():
        v["cpa"]  = (v["coste"] / v["conv"]) if v["conv"] else 0
        v["ctr"]  = (v["clicks"] / v["imp"]) if v["imp"] else 0
        v["cpc"]  = (v["coste"] / v["clicks"]) if v["clicks"] else 0
        v["avg_cuota_perdida_budget"]  = v["cuota_perdida_budget_acc"]  / v["n"] if v["n"] else 0
        v["avg_cuota_perdida_ranking"] = v["cuota_perdida_ranking_acc"] / v["n"] if v["n"] else 0

    # Totales del seguro
    total_coste = sum(c["coste"] for c in campanias)
    total_conv  = sum(c["conversiones"] for c in campanias)
    total_clicks = sum(c["clicks"] for c in campanias)
    total_imp = sum(c["impresiones"] for c in campanias)

    # Cuotas/oportunidades agregadas (promedio ponderado por impresiones)
    if total_imp:
        cuota_imp_search_w  = sum((c.get("cuota_imp_search", 0) or 0) * c["impresiones"] for c in campanias) / total_imp
        cuota_p_budget_w    = sum((c.get("cuota_perdida_budget", 0) or 0) * c["impresiones"] for c in campanias) / total_imp
        cuota_p_ranking_w   = sum((c.get("cuota_perdida_ranking", 0) or 0) * c["impresiones"] for c in campanias) / total_imp
    else:
        cuota_imp_search_w = cuota_p_budget_w = cuota_p_ranking_w = 0
    opt_score_avg = (sum(c.get("optimization_score", 0) or 0 for c in campanias) / len(campanias)) if campanias else 0

    # Daily series (consumo + leads por canal)
    serie_diaria = []
    for d in diarios:
        serie_diaria.append({
            "fecha":           d["fecha"],
            "leads_google":    d.get("leads_google") or 0,
            "consumo_google":  d.get("consumo_google") or 0,
            "leads_meta":      d.get("leads_meta") or 0,
            "consumo_meta":    d.get("consumo_meta") or 0,
            "leads_bing":      d.get("leads_bing") or 0,
            "consumo_bing":    d.get("consumo_bing") or 0,
        })

    # Mejor y peor campania por CPA (excluyendo low volume)
    elegibles = [c for c in campanias if c["conversiones"] > 30 and c["cpa"] > 0]
    mejor_cpa = min(elegibles, key=lambda c: c["cpa"]) if elegibles else None
    peor_cpa  = max(elegibles, key=lambda c: c["cpa"]) if elegibles else None

    return {
        "seguro":             seguro,
        "evento_conversion":  EVENTOS_CONVERSION.get(seguro, {}),
        "totales": {
            "coste_google":   round(total_coste, 2),
            "conversiones_google": round(total_conv, 1),
            "clicks":         total_clicks,
            "impresiones":    total_imp,
            "ctr":            round(total_clicks/total_imp, 4) if total_imp else 0,
            "cpc":            round(total_coste/total_clicks, 2) if total_clicks else 0,
            "cpa":            round(total_coste/total_conv, 2) if total_conv else 0,
            "campanias_count": len(campanias),
            "cuota_imp_search":     round(cuota_imp_search_w, 4),
            "cuota_perdida_budget": round(cuota_p_budget_w, 4),
            "cuota_perdida_ranking":round(cuota_p_ranking_w, 4),
            "optimization_score":   round(opt_score_avg, 4),
            # Oportunidad disponible: cuota maxima posible si se destraban budget+ranking
            "cuota_max_alcanzable": round(min(1.0, cuota_imp_search_w + cuota_p_budget_w + cuota_p_ranking_w), 4),
        },
        "por_subtipo":         por_subtipo,
        "campanias":           campanias,
        "mejor_cpa":           {"nombre": mejor_cpa["nombre"], "cpa": mejor_cpa["cpa"], "subtipo": mejor_cpa["subtipo"]} if mejor_cpa else None,
        "peor_cpa":            {"nombre": peor_cpa["nombre"], "cpa": peor_cpa["cpa"], "subtipo": peor_cpa["subtipo"]} if peor_cpa else None,
        "serie_diaria":        serie_diaria,
    }


def generate_top10_recos(seguros: dict) -> list[dict]:
    """Top 10 enfocado en POTENCIAR CONVERSIONES y BAJAR CPL."""
    recos: list = []

    # Recolectar todas las campanias
    todas = []
    for nombre, b in seguros.items():
        for c in b["campanias"]:
            todas.append({"seguro": nombre, **c})

    # === Bloque 1: ESCALAR (CPA bajo + budget constrained) ===
    candidatos_escalar = sorted(
        [c for c in todas if c["cpa"] > 0 and c["conversiones"] > 30 and c["cuota_perdida_budget"] > 0.10],
        key=lambda c: (c["cpa"], -c["cuota_perdida_budget"]),
    )[:3]
    for c in candidatos_escalar:
        nuevo_budget = c["presupuesto_diario"] * 1.30
        upside_conv  = int(c["conversiones"] * 0.30)
        recos.append({
            "tipo":        "escalar",
            "titulo":      f"Escalar {c['nombre']} (+30% budget) — CPA ${c['cpa']:.2f} y headroom {c['cuota_perdida_budget']*100:.0f}% por presupuesto",
            "seguro":      c["seguro"],
            "subtipo":     c["subtipo"],
            "que_hacer":   f"Subir presupuesto diario de ${c['presupuesto_diario']:.2f} a ${nuevo_budget:.2f}. La campania pierde {c['cuota_perdida_budget']*100:.0f}% de impresiones por falta de presupuesto - hay headroom directo.",
            "por_que":     f"CPA ${c['cpa']:.2f} (de los mejores). {int(c['conversiones']):,} conversiones en el periodo a {c['cuota_perdida_budget']*100:.0f}% de cuota perdida por budget significa que SI hay demanda y el sistema convierte bien, solo le falta budget.",
            "impacto_cpl": "Estable o ligera mejora (mas eficiencia con mas volumen)",
            "impacto_conv":f"+{upside_conv:,} conversiones/mes estimado",
            "esfuerzo":    "bajo",
            "prioridad":   "alta",
            "plazo":       "hoy",
        })

    # === Bloque 2: PAUSAR / RECORTAR (CPA alto + volumen alto) ===
    candidatos_pausar = sorted(
        [c for c in todas if c["coste"] > 1000 and c["cpa"] > 12],
        key=lambda c: c["cpa"], reverse=True,
    )[:2]
    for c in candidatos_pausar:
        promedio_cpa_seguro = seguros[c["seguro"]]["totales"]["cpa"]
        ratio_cpa = c["cpa"] / promedio_cpa_seguro if promedio_cpa_seguro else 0
        recos.append({
            "tipo":        "pausar",
            "titulo":      f"Recortar {c['nombre']} (-50% budget) — CPA ${c['cpa']:.2f} es {ratio_cpa:.1f}x el promedio del seguro",
            "seguro":      c["seguro"],
            "subtipo":     c["subtipo"],
            "que_hacer":   f"Bajar presupuesto -50% de ${c['presupuesto_diario']:.2f}. Auditar keywords (palabras de bajo intent), copy del anuncio y landing. Si en 7 dias no baja CPA, pausar y reasignar a la mejor campania del seguro.",
            "por_que":     f"CPA ${c['cpa']:.2f} vs promedio del seguro ${promedio_cpa_seguro:.2f}. Esta campania consume sin convertir bien. ${c['coste']:,.0f} invertidos = {int(c['conversiones'])} conversiones.",
            "impacto_cpl": f"-{int((c['cpa']-promedio_cpa_seguro)/c['cpa']*30)}% en el promedio del seguro al reasignar",
            "impacto_conv":"Neutro a positivo (depende donde se reasigne)",
            "esfuerzo":    "medio",
            "prioridad":   "alta",
            "plazo":       "esta semana",
        })

    # === Bloque 3: DESTRABAR (policy_limited / rejected) ===
    bloqueadas = [c for c in todas if "policy_limited" in c["flags"] or "rejected" in c["flags"]]
    bloqueadas.sort(key=lambda c: c["coste"], reverse=True)
    for c in bloqueadas[:2]:
        recos.append({
            "tipo":        "destrabar",
            "titulo":      f"Destrabar {c['nombre']} — {c['estado'][:60]}",
            "seguro":      c["seguro"],
            "subtipo":     c["subtipo"],
            "que_hacer":   f"Entrar a la campania, identificar assets/anuncios rechazados, corregir copy o creativo y re-someter a revision. Presupuesto activo ${c['presupuesto_diario']:.2f}/dia.",
            "por_que":     f"Estado: '{c['estado']}'. Inversion ya gastada ${c['coste']:,.0f} con limitaciones. Al destrabar liberamos 20-40% de capacidad sin gastar mas.",
            "impacto_cpl": "Estable (mismo CPA, mas conversiones)",
            "impacto_conv":"+20-40% del volumen actual de la campania",
            "esfuerzo":    "medio",
            "prioridad":   "alta",
            "plazo":       "esta semana",
        })

    # === Bloque 4: QUALITY SCORE bajo ===
    qs_issues = sorted(
        [c for c in todas if "ranking_issue" in c["flags"]],
        key=lambda c: c["cuota_perdida_ranking"], reverse=True,
    )[:1]
    for c in qs_issues:
        recos.append({
            "tipo":        "quality",
            "titulo":      f"Mejorar Quality Score en {c['nombre']} — pierde {c['cuota_perdida_ranking']*100:.0f}% por ranking",
            "seguro":      c["seguro"],
            "subtipo":     c["subtipo"],
            "que_hacer":   "Revisar keywords con QS<5, reescribir anuncios para mejorar CTR esperado y relevancia, mejorar landing experience (velocidad mobile, contenido alineado con keyword). Considerar partir ad groups por intent.",
            "por_que":     f"La campania pierde {c['cuota_perdida_ranking']*100:.0f}% de impresiones por ranking. Google la considera menos relevante que la competencia - subir QS baja CPC -10/-25%.",
            "impacto_cpl": f"-15-25% de CPC, lo cual baja CPA proporcional",
            "impacto_conv":"+10-20% de impresiones disponibles",
            "esfuerzo":    "alto",
            "prioridad":   "media",
            "plazo":       "este mes",
        })

    # === Bloque 5: MEJOR SUBTIPO POR SEGURO (reasignar budget) ===
    for nombre, b in seguros.items():
        subtipos = b["por_subtipo"]
        if not subtipos: continue
        # Encontrar el subtipo con mejor CPA y el peor para reasignar
        elegibles = [(t, v) for t, v in subtipos.items() if v["cpa"] > 0 and v["conv"] > 30]
        if len(elegibles) < 2: continue
        elegibles.sort(key=lambda x: x[1]["cpa"])
        mejor_t, mejor_v = elegibles[0]
        peor_t, peor_v   = elegibles[-1]
        if peor_v["cpa"] / mejor_v["cpa"] < 1.5: continue
        recos.append({
            "tipo":        "reasignar",
            "titulo":      f"{nombre}: reasignar budget de {peor_t} (CPA ${peor_v['cpa']:.2f}) a {mejor_t} (CPA ${mejor_v['cpa']:.2f})",
            "seguro":      nombre,
            "subtipo":     f"{peor_t} → {mejor_t}",
            "que_hacer":   f"Bajar -25% del presupuesto en campanias {peor_t} (consumo total ${peor_v['coste']:,.0f}, CPA ${peor_v['cpa']:.2f}) y reasignarlo a campanias {mejor_t} (CPA ${mejor_v['cpa']:.2f}).",
            "por_que":     f"En {nombre}, {peor_t} convierte a CPA {peor_v['cpa']/mejor_v['cpa']:.1f}x el de {mejor_t}. Cada US$ que sale de {peor_t} y entra a {mejor_t} = mas conversiones al mismo gasto.",
            "impacto_cpl": f"-{int((peor_v['cpa']-mejor_v['cpa'])/peor_v['cpa']*25)}% promedio del seguro",
            "impacto_conv":"+10-20% de conversiones al mismo gasto",
            "esfuerzo":    "medio",
            "prioridad":   "alta",
            "plazo":       "esta semana",
        })
        if len(recos) >= 9: break

    # === Bloque 6: TRACKING / EVENTOS DE CONVERSION ===
    recos.append({
        "tipo":        "tracking",
        "titulo":      "Auditar y validar eventos de conversión Google + Meta por seguro",
        "seguro":      "TODOS",
        "subtipo":     "Tracking",
        "que_hacer":   "Para cada seguro: confirmar que el evento de conversion en Google Ads esta importado desde Salesforce (no desde GA4 web), que en Meta esta configurada la 'Cliente potencial' o 'Mensaje' segun el seguro, y que la ventana de atribucion sea 7d-click/1d-view.",
        "por_que":     "Si el evento de conversion no es 'Lead SF' real, el Smart Bidding optimiza por una proxy (ej. clic en boton, scroll de landing) que no correlaciona con leads reales. Eso explica por que algunas campanias gastan y no llegan a SF.",
        "impacto_cpl": "Variable - en cuentas mal configuradas, ajustar evento puede bajar CPA -30%",
        "impacto_conv":"Hasta +25% de conversiones realmente medibles",
        "esfuerzo":    "medio",
        "prioridad":   "critica",
        "plazo":       "esta semana",
    })

    # Limit to 10
    return recos[:10]


def run() -> int:
    seguros: dict = {}
    for nombre in SEGUROS_PRINCIPALES:
        if nombre in SEGURO_FILES:
            seguros[nombre] = build_seguro_block(nombre)

    out = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "fuente": "Google Ads MCC SURATECH-COLOMBIA + Sheet diario por seguro",
            "seguros": list(seguros.keys()),
            "rango_global": {
                "desde": min((s["serie_diaria"][0]["fecha"] for s in seguros.values() if s["serie_diaria"]), default=None),
                "hasta": max((s["serie_diaria"][-1]["fecha"] for s in seguros.values() if s["serie_diaria"]), default=None),
            },
        },
        "seguros":         seguros,
        "top10_recos":     generate_top10_recos(seguros),
        "eventos_observacion": EVENTOS_OBSERVACION_GLOBAL,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[paid_media dataset] -> {OUT_PATH}")
    print(f"  seguros:  {len(seguros)}")
    print(f"  rango:    {out['meta']['rango_global']['desde']} -> {out['meta']['rango_global']['hasta']}")
    print(f"  top10 recos: {len(out['top10_recos'])}")
    for i, r in enumerate(out["top10_recos"], 1):
        print(f"    {i:2d}. [{r['tipo']:10s}] {r['titulo'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
