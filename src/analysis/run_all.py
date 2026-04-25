"""Genera TOP recomendaciones a partir del data.json extendido (v2).

Usa: cruces, optimizaciones, evolucion MoM para ranking serio.
"""

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


def generate(data: dict) -> list:
    out: list = []
    transcurrido = data["meta"]["periodo"].get("porcentaje_transcurrido", 0.7)
    seguros = {s["nombre"]: s for s in data["seguros"]}
    evol    = data.get("evolucion_mom", {}).get("por_seguro", {})
    cruces  = {c["seguro"]: c for c in data.get("cruces", {}).get("por_seguro", [])}
    opt     = data.get("optimizaciones", {})

    # ===== R1-R2: Alertas criticas del MCC =====
    _r(out,
        titulo="Reactivar las 5 cuentas con anuncios sin publicar",
        seguro="TODOS", plataforma="Google Ads",
        que_hacer="Entrar al MCC SURATECH-COLOMBIA, identificar las 5 cuentas con alerta 'anuncios no se publican' y reactivar HOY. Verificar metodo de pago, billing alerts, restricciones de cuenta.",
        por_que="Inversion potencial parada. Cada dia sin publicar = leads imposibles de recuperar.",
        impacto="ALTO - posible recuperar 10-30% del ritmo de leads del mes",
        esfuerzo="bajo", prioridad="critica", plazo="HOY",
        evidencia=["Alerta visible en header del MCC: '5 cuentas cuyos anuncios no se están publicando'"],
    )
    _r(out,
        titulo="Completar verificación de servicios financieros en 3 cuentas",
        seguro="TODOS", plataforma="Google Ads",
        que_hacer="Subir documentacion legal de SURA + cumplir requisitos para anunciantes de seguros. 3 cuentas pendientes.",
        por_que="Bloqueante administrativo. Sin verificación, Google empieza a limitar/pausar delivery automaticamente.",
        impacto="MEDIO - previene caída abrupta de impresiones la semana que viene",
        esfuerzo="medio", prioridad="critica", plazo="esta semana",
    )

    # ===== R3: Tracking roto Motos =====
    motos_cruce = cruces.get("Motos") or {}
    if motos_cruce.get("leads_crm", 0) > 100 and motos_cruce.get("google_ads_conv", 0) == 0:
        _r(out,
            titulo="URGENTE: Tracking de conversiones roto en Motos (Google Ads)",
            seguro="Motos", plataforma="Tracking",
            que_hacer="Revisar el evento de conversion configurado en la cuenta Google Ads de Motos. El tag de conversion no esta disparando. Validar tag manager / GA4 conversion import. Reasignar el evento si fue eliminado.",
            por_que=f"En abril 2026, el CRM registra {int(motos_cruce['leads_crm']):,} leads de Motos pero Google Ads reporta 0 conversiones. Sin tracking, el bidding de Smart Bidding no puede optimizar - cada US$ invertido en Motos esta a ciegas.",
            impacto="ALTO - reactivar bidding optimizado puede bajar CPC -20% en 7 dias",
            esfuerzo="medio", prioridad="critica", plazo="hoy",
            evidencia=[
                f"Sheet abril 2026: Motos = {int(motos_cruce['leads_crm']):,} leads CRM",
                "Google Ads cuenta Motos (331-988-8513): 0 conversiones reportadas en 4 campanias",
            ],
        )

    # ===== R4: Caida abrupta Arrendamiento =====
    arr_serie = evol.get("Arrendamiento", [])
    if len(arr_serie) >= 2:
        actual_mes = arr_serie[-1] if arr_serie[-1].get("cumplimiento") is not None else None
        prev_mes   = arr_serie[-2] if len(arr_serie) > 1 and arr_serie[-2].get("cumplimiento") is not None else None
        if actual_mes and prev_mes:
            cump_now = actual_mes.get("cumplimiento", 0)
            cump_prev = prev_mes.get("cumplimiento", 0)
            cpl_now = actual_mes.get("cpl_negocio", 0)
            cpl_prev = prev_mes.get("cpl_negocio", 0)
            if cump_prev > 0 and (cump_now / cump_prev) < 0.7 and cpl_now > cpl_prev * 1.15:
                _r(out,
                    titulo=f"Investigar caída de Arrendamiento: cumplimiento -{int((1-cump_now/cump_prev)*100)}% MoM y CPL +{int((cpl_now/cpl_prev-1)*100)}% MoM",
                    seguro="Arrendamiento", plataforma="Google Ads",
                    que_hacer="Auditar campanias SURA_ARRIENDO_*: cambios recientes en bidding, presupuesto, audiencias, palabras clave. Comparar landing pages activas vs marzo. Revisar cambios en quality score. Reactivar lo que funcionaba en febrero (CPL $2.65).",
                    por_que=f"Cumplimiento cayó de {cump_prev*100:.1f}% (mes anterior) a {cump_now*100:.1f}% (mes actual). CPL Negocio subió de ${cpl_prev:.2f} a ${cpl_now:.2f}. Esto sugiere algo que se rompió en el funnel: tracking, landing, oferta o quality score.",
                    impacto="ALTO - cerrar el gap de 11.138 leads requiere arreglar la causa raiz",
                    esfuerzo="alto", prioridad="critica", plazo="esta semana",
                    evidencia=[f"{m['mes']}: cumpl {m['cumplimiento']*100:.1f}% / CPL ${m['cpl_negocio']:.2f}" for m in arr_serie[-4:]],
                )

    # ===== R5: Cumplimiento por seguro <60% del transcurrido =====
    for nombre in SEGUROS_PRINCIPALES:
        s = seguros.get(nombre)
        if not s: continue
        cump = s["crm"].get("cumplimiento_pct")
        compr = s["crm"].get("compromiso_leads")
        leads = s["crm"].get("leads_crm")
        if cump is None or compr is None: continue
        if (cump / transcurrido) < 0.85 and nombre != "Arrendamiento":  # Arrendamiento ya cubierto arriba
            gap = int(compr - leads)
            _r(out,
                titulo=f"Inyectar presupuesto en {nombre} - gap {gap:,} leads para cumplir compromiso",
                seguro=nombre, plataforma="Google Ads",
                que_hacer=f"Identificar la mejor campania SURA_{nombre.upper()}_* por CPA y subir presupuesto +30% por 7 dias. Reasignar de campanias low-performance del mismo seguro.",
                por_que=f"Cumplimiento {cump*100:.1f}% vs {transcurrido*100:.0f}% transcurrido. Gap {gap:,} leads. Sin accion no se llega al compromiso de {compr:,}.",
                impacto=f"ALTO - cerrar {min(60, int(gap/compr*100))}% del gap",
                esfuerzo="bajo",
                prioridad="critica" if cump/transcurrido < 0.55 else "alta",
                plazo="hoy",
            )

    # ===== R6: Top destrabar (policy_limited / rejected) =====
    for c in opt.get("destrabar", [])[:3]:
        _r(out,
            titulo=f"Destrabar {c['nombre']} - estado: {c['estado'][:60]}",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer=f"Entrar a la campaña {c['nombre']}, revisar assets/anuncios rechazados, corregir copy o creativos según motivo de rechazo, re-someter a revision. Presupuesto activo ${c['presupuesto_diario']:.2f}/día.",
            por_que=f"Estado actual: '{c['estado']}'. Inversion ya gastada ${c['coste']:,.0f} con limitaciones - hay headroom inmediato al destrabar.",
            impacto="MEDIO - liberar 20-40% de la capacidad de la campania",
            esfuerzo="medio", prioridad="alta", plazo="esta semana",
        )

    # ===== R7-R8: Top escalar (CPA bajo + cuota perdida budget) =====
    for c in opt.get("escalar", [])[:2]:
        _r(out,
            titulo=f"Escalar {c['nombre']} (+30% budget) - CPA ${c['cpa']:.2f} y headroom {c['cuota_perdida_budget']*100:.0f}% por presupuesto",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer=f"Subir presupuesto diario de ${c['presupuesto_diario']:.2f} a ${c['presupuesto_diario']*1.3:.2f} (+30%). La campania pierde {c['cuota_perdida_budget']*100:.0f}% de impresiones por falta de presupuesto.",
            por_que=f"CPA ${c['cpa']:.2f} entre los mejores. {int(c['conversiones'])} conversiones con ${c['coste']:,.0f}. Cuota perdida por presupuesto = {c['cuota_perdida_budget']*100:.0f}% indica que con mas budget escalaria conversiones a CPA similar.",
            impacto=f"ALTO - estimado +{int(c['conversiones']*0.3):,} conversiones extra/mes",
            esfuerzo="bajo", prioridad="alta", plazo="hoy",
        )

    # ===== R9: Top pausar (CPA muy alto) =====
    for c in opt.get("pausar", [])[:1]:
        if c["cpa"] > 20:
            _r(out,
                titulo=f"Pausar/reformular {c['nombre']} - CPA ${c['cpa']:.2f} muy alto",
                seguro=c["seguro"], plataforma="Google Ads",
                que_hacer=f"Bajar presupuesto -50% de ${c['presupuesto_diario']:.2f}. Auditar keywords, landing, ofertas. Si no mejora en 7 dias, pausar y reasignar a campania con mejor CPA del mismo seguro.",
                por_que=f"CPA ${c['cpa']:.2f} muy alto vs benchmark. ${c['coste']:,.0f} invertidos generaron solo {int(c['conversiones'])} conversiones.",
                impacto="MEDIO - liberar ~30% del presupuesto para reasignar",
                esfuerzo="medio", prioridad="alta", plazo="esta semana",
            )

    # ===== R10: Quality issues =====
    for c in opt.get("quality_issues", [])[:1]:
        _r(out,
            titulo=f"Quality Score bajo en {c['nombre']} - cuota perdida ranking {c['cuota_perdida_ranking']*100:.0f}%",
            seguro=c["seguro"], plataforma="Google Ads",
            que_hacer="Revisar keywords con QS bajo, reescribir anuncios para mejorar relevancia, mejorar landing page experience. Considerar separar ad groups por intent.",
            por_que=f"La campania pierde {c['cuota_perdida_ranking']*100:.0f}% de impresiones por ranking - el algoritmo de Google la considera menos relevante que la competencia.",
            impacto="MEDIO - subir QS baja CPC -10/-20%",
            esfuerzo="alto", prioridad="media", plazo="este mes",
        )

    # Limit a top 10
    return out[:10]


def run() -> int:
    data = json.loads(DOCS_DATA.read_text(encoding="utf-8"))
    recos = generate(data)
    data["recomendaciones"] = recos
    DOCS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analysis] -> {len(recos)} recomendaciones")
    for i, r in enumerate(recos, 1):
        print(f"  {i:2d}. [{r['prioridad']:8s}] {r['titulo'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
