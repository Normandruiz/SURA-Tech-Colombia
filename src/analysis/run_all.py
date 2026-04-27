"""Genera TOP 10 recomendaciones basadas en RECIBIDOS (SF) - leads reales."""

from __future__ import annotations
import json
from src.config import DOCS_DATA, SEGUROS_PRINCIPALES


def _r(out, **k):
    out.append({
        "titulo":     k["titulo"],
        "seguro":     k.get("seguro", "—"),
        "plataforma": k.get("plataforma", "Google Ads"),
        "que_hacer":  k["que_hacer"],
        "por_que":    k["por_que"],
        "impacto":    k.get("impacto", "—"),
        "esfuerzo":   k.get("esfuerzo", "medio"),
        "prioridad":  k.get("prioridad", "alta"),
        "plazo":      k.get("plazo", "esta semana"),
        "evidencia":  k.get("evidencia", []),
    })


def avg_last_n(serie, n, key):
    valid = [s for s in serie if not s.get("vacio") and s.get(key)]
    if not valid:
        return None
    return sum(s[key] for s in valid[-n:]) / min(n, len(valid))


def find_peak(serie, key):
    valid = [s for s in serie if not s.get("vacio") and s.get(key)]
    if not valid:
        return None
    return max(valid, key=lambda s: s[key])


def generate(data: dict) -> list:
    out: list = []
    transcurrido = data["meta"]["periodo"].get("porcentaje_transcurrido", 0.7)
    seguros = {s["nombre"]: s for s in data["seguros"]}
    evol    = data.get("evolucion_mom", {}).get("por_seguro", {})
    cruces  = {c["seguro"]: c for c in data.get("cruces", {}).get("por_seguro", [])}
    opt     = data.get("optimizaciones", {})

    # Computar caso de negocio dinamico
    k = data["kpis_globales"]
    cumpl_global = k["cumpl_sf_vs_req"]
    estado = (
        f"Cumplimiento global {cumpl_global*100:.1f}% (RECIBIDOS SF / REQUERIDOS) vs {transcurrido*100:.0f}% transcurrido del mes. "
        f"{k['leads_recibidos_sf']:,} leads reales recibidos de {k['leads_requeridos']:,} requeridos. "
        f"Inversion ${k['inversion_total']:,.0f} (Google {k['inversion_google']/k['inversion_total']*100:.0f}% / Meta {k['inversion_meta']/k['inversion_total']*100:.0f}%). "
        f"CPL Negocio ${k['cpl_negocio_promedio']:.2f}."
    )
    data["caso_negocio"]["estado_actual"] = estado

    # ===== R1-R2: Alertas criticas del MCC =====
    _r(out,
        titulo="Reactivar las 5 cuentas con anuncios sin publicar",
        seguro="TODOS", plataforma="Google Ads",
        que_hacer="Entrar al MCC SURATECH-COLOMBIA, identificar las 5 cuentas con alerta 'anuncios no se publican' y reactivar HOY. Verificar billing, restricciones y método de pago.",
        por_que="Inversion potencial parada. Cada dia sin publicar = leads imposibles de recuperar.",
        impacto="ALTO - posible recuperar 10-30% del ritmo de leads del mes",
        esfuerzo="bajo", prioridad="critica", plazo="HOY",
        evidencia=["Alerta visible en header del MCC: '5 cuentas con anuncios sin publicar'"],
    )
    _r(out,
        titulo="Completar verificación de servicios financieros en 3 cuentas",
        seguro="TODOS", plataforma="Google Ads",
        que_hacer="Subir documentación legal de SURA + cumplir requisitos para anunciantes de seguros. 3 cuentas pendientes.",
        por_que="Bloqueante administrativo. Sin verificación, Google va a empezar a limitar/pausar delivery.",
        impacto="MEDIO - previene caída abrupta de impresiones la semana que viene",
        esfuerzo="medio", prioridad="critica", plazo="esta semana",
    )

    # ===== R3-R6: Caída histórica por seguro (insight tipo "qué cambió") =====
    for nombre in SEGUROS_PRINCIPALES:
        serie = evol.get(nombre, [])
        valid = [s for s in serie if not s.get("vacio")]
        if len(valid) < 4:
            continue
        actual = valid[-1]
        peak = find_peak(valid, "cumpl_sf_vs_req")
        avg_last_3 = avg_last_n(valid, 3, "cumpl_sf_vs_req")
        cumpl_now = actual.get("cumpl_sf_vs_req", 0)

        if peak and cumpl_now and (cumpl_now / peak["cumpl_sf_vs_req"]) < 0.6:
            drop_pp = (peak["cumpl_sf_vs_req"] - cumpl_now) * 100
            cpl_now = actual.get("cpl_negocio_sf", 0)
            cpl_peak = peak.get("cpl_negocio_sf", 0)
            evidencia = [f"{s['mes']}: cumpl {s['cumpl_sf_vs_req']*100:.1f}% / SF {s['recibidos_sf']:,} / CPL ${s['cpl_negocio_sf']:.2f}" for s in valid[-6:]]
            _r(out,
                titulo=f"Investigar caída sostenida en {nombre}: -{drop_pp:.0f}pp desde el pico ({peak['mes']})",
                seguro=nombre, plataforma="Google Ads + Meta",
                que_hacer=f"Auditar todo lo que cambió desde {peak['mes']}: bidding, presupuestos, audiencias, keywords, landing pages, ofertas, quality score. Comparar mix de canales (Google vs Meta vs Bing) y detectar cuál se rompió. Reactivar configuraciones que rendían cuando estaba en pico.",
                por_que=f"En {peak['mes']} el cumplimiento fue {peak['cumpl_sf_vs_req']*100:.1f}% con CPL ${cpl_peak:.2f}. Hoy ({actual['mes']}) está en {cumpl_now*100:.1f}% con CPL ${cpl_now:.2f}. La caída es estructural (>5 meses), no estacional.",
                impacto=f"ALTO - recuperar {drop_pp/2:.0f}pp del cumplimiento implica +{int((peak['cumpl_sf_vs_req']-cumpl_now)/2 * actual.get('requeridos',0)):,} leads/mes",
                esfuerzo="alto",
                prioridad="critica" if cumpl_now < transcurrido*0.6 else "alta",
                plazo="esta semana",
                evidencia=evidencia,
            )

    # ===== R7: Tracking GA vs SF gap =====
    for nombre in SEGUROS_PRINCIPALES:
        s = seguros.get(nombre)
        if not s: continue
        sf = s["crm"].get("recibidos_sf", 0)
        ga = s["crm"].get("recibidos_ga", 0)
        if sf > 100 and ga > 0 and (ga / sf) < 0.4:
            _r(out,
                titulo=f"Auditar tracking GA en {nombre}: GA detecta solo {(ga/sf)*100:.0f}% de los SF",
                seguro=nombre, plataforma="Tracking",
                que_hacer="Validar que todos los formularios de pauta envien evento de conversion a GA4 + GTM. Verificar landing pages que SURA recibe leads pero GA no los registra.",
                por_que=f"SURA recibe {sf:,} leads (SF) pero GA solo registra {ga:,} ({(ga/sf)*100:.1f}%). Hay {sf-ga:,} leads sin atribución correcta - bidding ciego.",
                impacto="MEDIO/ALTO - tracking correcto habilita Smart Bidding por conversiones reales",
                esfuerzo="medio", prioridad="alta", plazo="esta semana",
                evidencia=[f"{nombre} {s['nombre']}: SF={sf:,} / GA={ga:,} / ratio={ga/sf*100:.1f}%"],
            )
            break  # uno solo de tracking en el top10

    # ===== R8: Top destrabar (policy_limited / rejected) =====
    for c in opt.get("destrabar", [])[:2]:
        _r(out,
            titulo=f"Destrabar {c['nombre']} - {c['estado'][:50]}",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer=f"Entrar a {c['nombre']}, revisar assets/anuncios rechazados, corregir copy o creativos según motivo, re-someter a revisión. Presupuesto activo ${c['presupuesto_diario']:.2f}/día.",
            por_que=f"Estado: '{c['estado']}'. Inversion ya gastada ${c['coste']:,.0f} con limitaciones - hay headroom inmediato al destrabar.",
            impacto="MEDIO - liberar 20-40% de la capacidad de la campania",
            esfuerzo="medio", prioridad="alta", plazo="esta semana",
        )

    # ===== R9: Top escalar (CPA bajo + cuota perdida budget) =====
    for c in opt.get("escalar", [])[:1]:
        new_budget = c['presupuesto_diario'] * 1.3
        _r(out,
            titulo=f"Escalar {c['nombre']} (+30% budget) - CPA ${c['cpa']:.2f} y headroom {c['cuota_perdida_budget']*100:.0f}%",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer=f"Subir presupuesto diario de ${c['presupuesto_diario']:.2f} a ${new_budget:.2f} (+30%). La campania pierde {c['cuota_perdida_budget']*100:.0f}% de impresiones por falta de presupuesto.",
            por_que=f"CPA ${c['cpa']:.2f} entre los mejores. {int(c['conversiones']):,} conversiones con ${c['coste']:,.0f}. Cuota perdida por presupuesto = {c['cuota_perdida_budget']*100:.0f}% indica que con mas budget escalaria a CPA similar.",
            impacto=f"ALTO - estimado +{int(c['conversiones']*0.3):,} conversiones extra/mes",
            esfuerzo="bajo", prioridad="alta", plazo="hoy",
        )

    # ===== R10: Top pausar / quality issues =====
    if opt.get("quality_issues"):
        c = opt["quality_issues"][0]
        _r(out,
            titulo=f"Quality Score bajo en {c['nombre']} - cuota perdida ranking {c['cuota_perdida_ranking']*100:.0f}%",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer="Revisar keywords con QS bajo, reescribir anuncios para mejorar relevancia, mejorar landing page experience. Considerar separar ad groups por intent.",
            por_que=f"La campania pierde {c['cuota_perdida_ranking']*100:.0f}% de impresiones por ranking - el algoritmo de Google la considera menos relevante que la competencia.",
            impacto="MEDIO - subir QS baja CPC -10/-20%",
            esfuerzo="alto", prioridad="media", plazo="este mes",
        )
    elif opt.get("pausar"):
        c = opt["pausar"][0]
        if c["cpa"] > 20:
            _r(out,
                titulo=f"Pausar/reformular {c['nombre']} - CPA ${c['cpa']:.2f} muy alto",
                seguro=c["seguro"], plataforma="Google Ads",
                que_hacer=f"Bajar presupuesto -50% de ${c['presupuesto_diario']:.2f}. Auditar keywords, landing, ofertas. Si no mejora en 7 dias, pausar y reasignar.",
                por_que=f"CPA ${c['cpa']:.2f} muy alto. ${c['coste']:,.0f} invertidos generaron solo {int(c['conversiones'])} conversiones.",
                impacto="MEDIO - liberar ~30% del presupuesto para reasignar",
                esfuerzo="medio", prioridad="alta", plazo="esta semana",
            )

    # Proyeccion del caso de negocio
    top5_recos = out[:5]
    proyeccion_pp = 8 + 4 * len([r for r in top5_recos if r["prioridad"] == "critica"])
    data["caso_negocio"]["proyeccion_si_aplicamos_top5"] = (
        f"Aplicando las top 5 recomendaciones (focalizadas en destrabar bloqueos administrativos, "
        f"recuperar configuraciones que rendían en el pico de Q4 2025 y arreglar tracking) "
        f"estimamos +{proyeccion_pp}pp de cumplimiento global en 4 semanas (de {cumpl_global*100:.0f}% a "
        f"{cumpl_global*100+proyeccion_pp:.0f}%) y {int(k['leads_requeridos']*proyeccion_pp/100):,} leads SF adicionales/mes."
    )

    return out[:10]


def generate_oportunidades(data: dict) -> list:
    """Top oportunidades CROSS-CANAL basadas en gap entre lo actual y el potencial.

    Cada oportunidad calcula:
      - tipo (escalar / migrar canal / arreglar tracking / mejorar funnel)
      - seguro afectado
      - delta esperado en leads SF
      - delta esperado en CPL
    """
    out: list = []
    seguros = {s["nombre"]: s for s in data["seguros"]}

    for nombre, s in seguros.items():
        if not s.get("es_principal"):
            continue
        crm = s["crm"]
        ga  = s["google_ads"]["kpis"]
        leads_sf = crm.get("recibidos_sf") or 0
        if not leads_sf:
            continue

        leads_google_sheet = crm.get("leads_google") or 0
        leads_meta = crm.get("leads_meta") or 0
        leads_bing = crm.get("leads_bing") or 0
        total_canales = leads_google_sheet + leads_meta + leads_bing
        share_google = (leads_google_sheet / total_canales) if total_canales else 0
        share_meta   = (leads_meta / total_canales) if total_canales else 0

        inv_google = crm.get("consumo_google") or 0
        inv_meta   = crm.get("consumo_meta") or 0
        cpl_google_canal = (inv_google / leads_google_sheet) if leads_google_sheet else 0
        cpl_meta_canal   = (inv_meta / leads_meta) if leads_meta else 0

        # Oportunidad 1: si un canal tiene CPL mucho menor que el otro -> reasignar budget
        if cpl_google_canal > 0 and cpl_meta_canal > 0:
            ratio = max(cpl_google_canal, cpl_meta_canal) / min(cpl_google_canal, cpl_meta_canal)
            if ratio > 2:
                mejor_canal = "Google" if cpl_google_canal < cpl_meta_canal else "Meta"
                peor_canal = "Meta" if mejor_canal == "Google" else "Google"
                cpl_mejor = min(cpl_google_canal, cpl_meta_canal)
                cpl_peor = max(cpl_google_canal, cpl_meta_canal)
                out.append({
                    "seguro":      nombre,
                    "tipo":        "Reasignación de canal",
                    "icono":       "🔄",
                    "titulo":      f"{nombre}: reasignar budget de {peor_canal} a {mejor_canal}",
                    "detalle":     f"En {nombre}, {mejor_canal} convierte a CPL ${cpl_mejor:.2f} vs {peor_canal} a ${cpl_peor:.2f} (ratio {ratio:.1f}x). Reasignando 30% del budget de {peor_canal} → {mejor_canal} podríamos sumar leads SF al mismo gasto.",
                    "delta_leads": f"+{int(leads_sf*0.10):,} leads SF/mes estimado",
                    "delta_cpl":   f"-{int((cpl_peor-cpl_mejor)/cpl_peor*15)}% en CPL global del seguro",
                })

        # Oportunidad 2: gap conv Google Ads vs leads SF (tracking)
        ga_conv = ga.get("conversiones") or 0
        if leads_sf > 100 and ga_conv == 0:
            out.append({
                "seguro":      nombre,
                "tipo":        "Tracking",
                "icono":       "🔧",
                "titulo":      f"{nombre}: tracking de conversiones Google Ads roto",
                "detalle":     f"El CRM registra {leads_sf:,} leads SF pero Google Ads reporta 0 conversiones. Sin tracking, Smart Bidding está optimizando ciego. Importar evento desde Salesforce o configurar GA4 conversion import.",
                "delta_leads": "+15-25% volumen estimado al optimizar correctamente",
                "delta_cpl":   "-20% al activar Smart Bidding con datos reales",
            })

        # Oportunidad 3: cumplimiento bajo + budget headroom (cuota perdida budget)
        cumpl = crm.get("cumpl_sf_vs_req")
        if cumpl is not None and cumpl < 0.7:
            requeridos = crm.get("requeridos") or 0
            gap = max(0, requeridos - leads_sf)
            out.append({
                "seguro":      nombre,
                "tipo":        "Escalar Google Ads",
                "icono":       "📈",
                "titulo":      f"{nombre}: cerrar gap de {gap:,} leads para cumplir compromiso",
                "detalle":     f"Cumplimiento actual {cumpl*100:.1f}% vs target. Hay headroom en cuota perdida por presupuesto en Google Ads. Subir budget +30% en la(s) campaña(s) con mejor CPA del seguro.",
                "delta_leads": f"+{int(gap*0.4):,} leads SF en 4 semanas (cierra ~40% del gap)",
                "delta_cpl":   "Estable o ligera mejora",
            })

        # Oportunidad 4: concentración de canal extrema (riesgo)
        if share_google > 0.85:
            out.append({
                "seguro":      nombre,
                "tipo":        "Diversificación",
                "icono":       "⚖",
                "titulo":      f"{nombre}: dependencia extrema de Google ({share_google*100:.0f}%)",
                "detalle":     f"El {share_google*100:.0f}% de los leads vienen de Google. Riesgo: cualquier ajuste de Google (alza CPC, cambio algoritmo) impacta directo. Sumar 15-20% a Meta para diversificar.",
                "delta_leads": "Estable inicialmente; +reducción de riesgo",
                "delta_cpl":   "Posible alza temporal mientras Meta encuentra eficiencia",
            })

    # Cross-seguro: detección de tracking ROTO en Motos (caso especifico)
    motos = seguros.get("Motos")
    if motos:
        ga_conv = motos["google_ads"]["kpis"].get("conversiones") or 0
        leads = motos["crm"].get("recibidos_sf") or 0
        if leads > 100 and ga_conv > 0 and ga_conv / leads < 0.4:
            # ya cubierto arriba
            pass

    # Sort por impacto: las que dicen 'critica' o tracking primero
    PRIO = {"Tracking": 0, "Escalar Google Ads": 1, "Reasignación de canal": 2, "Diversificación": 3}
    out.sort(key=lambda o: PRIO.get(o["tipo"], 99))
    return out[:6]


def run() -> int:
    data = json.loads(DOCS_DATA.read_text(encoding="utf-8"))
    recos = generate(data)
    data["recomendaciones"] = recos
    data["oportunidades_cross_canal"] = generate_oportunidades(data)
    DOCS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analysis v3] -> {len(recos)} recomendaciones + {len(data['oportunidades_cross_canal'])} oportunidades cross-canal")
    for i, r in enumerate(recos, 1):
        print(f"  {i:2d}. [{r['prioridad']:8s}] {r['titulo'][:95]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
