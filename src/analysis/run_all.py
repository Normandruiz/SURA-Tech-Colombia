"""Genera el TOP 10 de recomendaciones accionables a partir de docs/assets/data.json.

Reglas (ordenadas por impacto):
  R1. Si hay alertas criticas (cuentas no publicando / verificacion) -> prioridad maxima.
  R2. PMax con grupos de recursos limitados -> destrabar. Alto impacto.
  R3. Campanias con CPA bajo + presupuesto bajo (cumplimiento bajo) -> escalar +20-30%.
  R4. Campanias con CPA muy alto y conversiones bajas -> pausar o reasignar.
  R5. Cumplimiento por seguro <50% del transcurrido -> redistribuir presupuesto a esa cuenta.
  R6. Discrepancia leads_crm vs conversiones Google Ads >30% -> revisar tracking.
  R7. Seguros sin tracking conversion (Salud para Dos / Salud Animal en CRM) -> setear conversion goal.
"""

from __future__ import annotations

import json
from src.config import DOCS_DATA, SEGUROS_PRINCIPALES


def _add_reco(out: list, **k) -> None:
    out.append({
        "titulo":         k["titulo"],
        "seguro":         k.get("seguro", "—"),
        "plataforma":     k.get("plataforma", "Google Ads"),
        "que_hacer":      k["que_hacer"],
        "por_que":        k["por_que"],
        "impacto":        k.get("impacto", "—"),
        "esfuerzo":       k.get("esfuerzo", "medio"),
        "prioridad":      k.get("prioridad", "alta"),
        "plazo":          k.get("plazo", "esta semana"),
    })


def generate_recos(data: dict) -> list:
    out: list = []
    seguros = {s["nombre"]: s for s in data["seguros"]}
    transcurrido = data["meta"]["periodo"].get("porcentaje_transcurrido", 0.70)

    # R1 - Alertas criticas del MCC
    _add_reco(out,
        titulo="Reactivar las 5 cuentas con anuncios sin publicar",
        seguro="TODOS",
        plataforma="Google Ads",
        que_hacer="Entrar al MCC SURATECH-COLOMBIA, identificar las 5 cuentas con alerta 'anuncios no se publican' y reactivar inmediatamente. Si hay payment issue, sumar metodo de pago.",
        por_que="Inversion potencial parada. La alerta esta visible en el header del MCC. Cada dia sin publicar = leads perdidos imposibles de recuperar.",
        impacto="ALTO - posible recuperar 10-30% del ritmo de leads del mes",
        esfuerzo="bajo",
        prioridad="critica",
        plazo="HOY",
    )
    _add_reco(out,
        titulo="Completar verificación de servicios financieros en 3 cuentas",
        seguro="TODOS",
        plataforma="Google Ads",
        que_hacer="Subir documentación legal de SURA + cumplir requisitos de Google Ads para anunciantes de seguros. Hay 3 cuentas con esta alerta pendiente.",
        por_que="Bloqueante administrativo. Sin verificación, Google va a empezar a limitar/pausar delivery automaticamente.",
        impacto="MEDIO - previene caida abrupta de impresiones la semana que viene",
        esfuerzo="medio",
        prioridad="critica",
        plazo="esta semana",
    )

    # R por cumplimiento (seguro principal con cumplimiento <50% del transcurrido => critico)
    rojos = []
    for nombre in SEGUROS_PRINCIPALES:
        s = seguros.get(nombre)
        if not s: continue
        cump = s["crm"].get("cumplimiento_pct")
        compr = s["crm"].get("compromiso_leads")
        leads = s["crm"].get("leads_crm")
        if cump is None or compr is None: continue
        # ratio entre cumplimiento real y transcurrido del mes
        ratio = cump / transcurrido if transcurrido else 0
        if ratio < 0.6:
            rojos.append((nombre, cump, leads, compr))

    # Ordenar por gap mayor primero
    rojos.sort(key=lambda x: x[1])
    for nombre, cump, leads, compr in rojos:
        gap = int(compr - leads)
        _add_reco(out,
            titulo=f"Inyectar presupuesto en {nombre} - gap de {gap:,} leads para cumplir",
            seguro=nombre,
            plataforma="Google Ads",
            que_hacer=f"Identificar la mejor campaña SURA_{nombre.upper()}_* por CPA y subir presupuesto +30% por 7 dias. Reasignar de campañas low-performance del mismo seguro.",
            por_que=f"Cumplimiento {cump*100:.1f}% vs {transcurrido*100:.0f}% transcurrido del mes. Gap de {gap:,} leads CRM. Sin accion, no se llega al compromiso de {compr:,}.",
            impacto=f"ALTO - cerrar {min(60, int(gap/compr*100))}% del gap",
            esfuerzo="bajo",
            prioridad="critica" if cump/transcurrido < 0.55 else "alta",
            plazo="hoy",
        )

    # R por campañas concretas: ordenar por CPA bajo (escalar) y CPA alto (revisar)
    todas_campanias = []
    for s in data["seguros"]:
        for c in s["google_ads"]["campanias"]:
            if c["coste"] > 0:
                todas_campanias.append({"seguro": s["nombre"], **c})

    # PMax con grupos limitados
    for c in todas_campanias:
        if "limitado" in c["estado"].lower() or "rechazado" in c["estado"].lower() or "polít" in c["estado"].lower():
            _add_reco(out,
                titulo=f"Destrabar {c['nombre']} - grupos limitados por política",
                seguro=c["seguro"],
                plataforma="Google Ads",
                que_hacer=f"Entrar a la campaña {c['nombre']}, revisar los assets/anuncios rechazados, corregir copy o creativos según motivo de rechazo, re-someter a revision.",
                por_que=f"Estado actual: '{c['estado']}'. Presupuesto ${c['presupuesto']} parcialmente sin entregar.",
                impacto="MEDIO - liberar 20-40% de la capacidad de la campaña",
                esfuerzo="medio",
                prioridad="alta",
                plazo="esta semana",
            )

    # Top 3 campañas con MEJOR CPA y presupuesto chico -> escalar
    elegibles = [c for c in todas_campanias if c["conversiones"] > 50 and c["cpa"] > 0]
    elegibles.sort(key=lambda c: c["cpa"])
    for c in elegibles[:2]:
        _add_reco(out,
            titulo=f"Escalar {c['nombre']} (+30% budget) - CPA bajo ${c['cpa']:.2f}",
            seguro=c["seguro"],
            plataforma="Google Ads",
            que_hacer=f"Subir presupuesto diario de {c['presupuesto']} a +30%. Estrategia ya optimizada ({c['estrategia']}).",
            por_que=f"CPA ${c['cpa']:.2f} entre los mejores del MCC. {int(c['conversiones'])} conversiones con ${c['coste']:,.0f} de inversion. Hay headroom para escalar antes de ver fatiga.",
            impacto=f"ALTO - +{int(c['conversiones']*0.3):,} conversiones extra/mes a CPA similar",
            esfuerzo="bajo",
            prioridad="alta",
            plazo="hoy",
        )

    # Top 2 campañas con PEOR CPA y volumen alto -> pausar o reformular
    no_buenas = [c for c in todas_campanias if c["coste"] > 1000 and c["cpa"] > 0]
    no_buenas.sort(key=lambda c: c["cpa"], reverse=True)
    for c in no_buenas[:1]:
        if c["cpa"] > 20:
            _add_reco(out,
                titulo=f"Pausar o reformular {c['nombre']} - CPA muy alto ${c['cpa']:.2f}",
                seguro=c["seguro"],
                plataforma="Google Ads",
                que_hacer=f"Bajar presupuesto -50% de {c['presupuesto']} mientras se revisa: keywords, landing, ofertas. Si no mejora en 7 dias, pausar y reasignar a campaña con mejor CPA del mismo seguro.",
                por_que=f"CPA ${c['cpa']:.2f} muy alto vs benchmark del MCC. ${c['coste']:,.0f} invertidos generaron solo {int(c['conversiones'])} conversiones.",
                impacto="MEDIO - liberar ~30% del presupuesto para reasignar",
                esfuerzo="medio",
                prioridad="alta",
                plazo="esta semana",
            )

    # R Tracking GA4
    _add_reco(out,
        titulo="Activar y mapear eventos de conversión GA4 por seguro",
        seguro="TODOS",
        plataforma="Tracking",
        que_hacer="En GA4 (property 279239939): listar eventos de conversion existentes, crear los que falten para cada seguro (lead_form_autos, lead_form_motos, etc.), exportar a Google Ads para usar como goal.",
        por_que="Sin tracking GA4 mapeado, no se puede medir bien la atribucion ni alimentar el bidding de Google Ads. Es el dato que el equipo identificó como 'el más difícil de conseguir'.",
        impacto="ALTO largo plazo - habilita optimizacion automatica del bidding por conversion real",
        esfuerzo="medio",
        prioridad="alta",
        plazo="esta semana",
    )

    # R Meta - migrar a API
    _add_reco(out,
        titulo="Cotizar y aprobar Meta Marketing API para extracción automatica",
        seguro="TODOS",
        plataforma="Meta",
        que_hacer="Habilitar Meta Marketing API a nivel BM 549601551075021 + token long-lived. Reescribir el extractor Meta para usar la API en lugar de scraping de UI.",
        por_que="El scraping del Ads Manager es fragil y lento (no permite drill a ad sets). La API da granularidad por ad set en segundos.",
        impacto="MEDIO - habilita pipeline diario confiable",
        esfuerzo="medio",
        prioridad="media",
        plazo="este mes",
    )

    # R por seguros extra (Salud para Dos / Salud Animal sin CRM)
    for nombre in ("Salud para Dos", "Salud Animal"):
        s = seguros.get(nombre)
        if not s: continue
        coste = s["google_ads"]["kpis"].get("coste_usd", 0)
        if coste > 500:
            _add_reco(out,
                titulo=f"Setear tracking + compromiso CRM para {nombre}",
                seguro=nombre,
                plataforma="Tracking",
                que_hacer=f"Definir goal de leads CRM mensual para {nombre}. Setear conversion event en Google Ads + GA4. Agregar columna en el Sheet 'Resumen mensual'.",
                por_que=f"Hoy hay ${coste:,.0f} invertidos sin tracking de leads CRM. No se puede medir CPL Negocio ni cumplimiento.",
                impacto="ALTO descubrimiento - habilita medir ROI real de inversion ya activa",
                esfuerzo="medio",
                prioridad="media",
                plazo="este mes",
            )

    # Limit a top 10 (manteniendo orden)
    return out[:10]


def run() -> int:
    data = json.loads(DOCS_DATA.read_text(encoding="utf-8"))
    recos = generate_recos(data)
    data["recomendaciones"] = recos
    DOCS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analysis] -> {len(recos)} recomendaciones generadas")
    for i, r in enumerate(recos, 1):
        print(f"  {i:2d}. [{r['prioridad']:8s}] {r['titulo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
