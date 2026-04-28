"""Genera outputs/suratech_propuesta_distribucion_mayo2026.xlsx con la propuesta
de redistribucion de presupuesto por seguro x medio x campana.

Constraints:
  - Tope por seguro (provisto por user):
      Auto:      $52.421
      Moto:      $32.642
      Viajes:    $16.900
      Arriendo:  $31.080
  - Bing: dejar en su plan del Flow (no se toca)
  - 70-75% del presupuesto debe ir a Google (mejor calidad de leads)
"""

from __future__ import annotations
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.config import OUTPUTS_DIR, ROOT


SURA_AZUL = "0033A0"
SURA_AQUA = "00AEC7"
GRIS_FONDO = "F0F0F0"
ROJO   = "DC2626"
AMARILLO = "F59E0B"
VERDE  = "10B981"

BORDER = Border(
    left=Side("thin", color="DDDDDD"),
    right=Side("thin", color="DDDDDD"),
    top=Side("thin", color="DDDDDD"),
    bottom=Side("thin", color="DDDDDD"),
)
H1 = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
H_AZUL = PatternFill("solid", fgColor=SURA_AZUL)
NORMAL = Font(name="Calibri", size=10)
BOLD = Font(name="Calibri", size=10, bold=True)


# ============== INPUT: DATA REAL DEL 1-27 ABRIL ==============

BUDGETS = {
    "Auto":      52421,
    "Moto":      32642,
    "Viajes":    16900,
    "Arriendo":  31080,
}

# Spend / leads / CPA del 1-27 abr 2026 (calculado del Sheet)
ACTUAL = {
    "Auto":     {"google": (26132, 4337, 6.03), "meta": (10244, 2544, 4.03), "bing": 1120},
    "Moto":     {"google": (15555, 1117, 13.92), "meta": (6629, 1192, 5.56), "bing": 753},
    "Arriendo": {"google": (28902, 1870, 15.45), "meta": (8083, 1508, 5.36), "bing": 1167},
    "Viajes":   {"google": (6762, 204, 33.01), "meta": (3186, 83, 38.38), "bing": 178},
}

# Campanias Google Ads con metricas reales (extractor MCC)
GOOGLE_CAMPS = {
    "Auto": [
        {"nombre": "SURA_AUTOS_PMAX",            "cpa": 3.90,  "lost_budget": 0.74, "budget_d_actual": 517, "spend": 10672, "conv": 2739.4, "flags": ["policy_limited","budget_constrained"]},
        {"nombre": "SURA_AUTOS_SEARCH_SEGMENT",  "cpa": 6.72,  "lost_budget": 0.15, "budget_d_actual": 326, "spend": 9198, "conv": 1369.1, "flags": []},
        {"nombre": "SURA_AUTOS_SEARCH_RETENTION","cpa": 10.59, "lost_budget": 0.23, "budget_d_actual": 147, "spend": 4194, "conv": 396.1, "flags": ["budget_constrained"]},
        {"nombre": "SURA_AUTOS_SEARCH_CONQUEST", "cpa": 6.41,  "lost_budget": 0.42, "budget_d_actual": 52,  "spend": 2189, "conv": 341.7, "flags": ["budget_constrained","ranking_issue"]},
    ],
    "Moto": [
        {"nombre": "SURA_MOTOS_SEARCH_RETENTION","cpa": 6.46,  "lost_budget": 0.04, "budget_d_actual": 183, "spend": 1994, "conv": 308.8, "flags": []},
        {"nombre": "SURA_MOTOS_PMAX",            "cpa": 12.19, "lost_budget": 0.58, "budget_d_actual": 397, "spend": 7832, "conv": 642.7, "flags": ["policy_limited","rejected","budget_constrained"]},
        {"nombre": "SURA_MOTOS_SEARCH_SEGMENT",  "cpa": 15.66, "lost_budget": 0.66, "budget_d_actual": 357, "spend": 4596, "conv": 293.5, "flags": ["rejected","budget_constrained"]},
        {"nombre": "SURA_MOTOS_SEARCH_CONQUEST", "cpa": 14.00, "lost_budget": 0.73, "budget_d_actual": 75,  "spend": 1366, "conv": 97.6, "flags": ["budget_constrained"]},
    ],
    "Arriendo": [
        {"nombre": "sura-cdd-co-google-search-retention-arriendo", "cpa": 7.32,  "lost_budget": 0.06, "budget_d_actual": 984, "spend": 12383, "conv": 1690.7, "flags": ["rejected"]},
        {"nombre": "SURA_ARRIENDO_SEARCH_SEGMENT","cpa": 25.27, "lost_budget": 0.14, "budget_d_actual": 900, "spend": 8208, "conv": 324.8, "flags": ["rejected"]},
        {"nombre": "SURA_ARRIENDO_PMAX",          "cpa": 23.55, "lost_budget": 0.73, "budget_d_actual": 376, "spend": 7238, "conv": 307.3, "flags": ["policy_limited","budget_constrained"]},
    ],
    "Viajes": [
        {"nombre": "SURA_VIAJES_SEARCH_RETENTION","cpa": 22.67, "lost_budget": 0.20, "budget_d_actual": 251, "spend": 2971, "conv": 131.0, "flags": ["budget_constrained"]},
        {"nombre": "SURA_VIAJES_PMAX",            "cpa": 20.66, "lost_budget": 0.77, "budget_d_actual": 155, "spend": 1959, "conv": 94.8, "flags": ["policy_limited","budget_constrained"]},
        {"nombre": "SURA_VIAJES_SEARCH_SEGMENT",  "cpa": 54.52, "lost_budget": 0.58, "budget_d_actual": 106, "spend": 1775, "conv": 32.5, "flags": ["budget_constrained"]},
    ],
}


# ============== ALGORITMO DE PROPUESTA ==============

# Reglas:
#  - Cumplir 70-75% Google del total por seguro
#  - Bing fijo (lo del Flow)
#  - Por campania Google: clasificar en escalar / mantener / recortar segun CPA + lost_budget
#  - Asignar el budget Google priorizando las que tienen mejor CPA y mas lost_budget

def clasificar(c):
    """Devuelve (accion, factor) donde factor es el multiplicador del budget actual."""
    cpa = c["cpa"]; lb = c["lost_budget"]
    if cpa <= 7 and lb >= 0.50:
        return "ESCALAR FUERTE", 1.80
    if cpa <= 10 and lb >= 0.30:
        return "ESCALAR", 1.40
    if cpa <= 10 and lb >= 0.10:
        return "ESCALAR LEVE", 1.20
    if cpa <= 15 and lb >= 0.50:
        return "ESCALAR MODERADO", 1.20
    if cpa > 25:
        return "RECORTAR FUERTE", 0.40
    if cpa > 15:
        return "RECORTAR", 0.65
    if cpa > 10 and lb < 0.10:
        return "MANTENER", 1.0
    return "MANTENER", 1.0


def proponer(seguro: str):
    actual = ACTUAL[seguro]
    budget_total = BUDGETS[seguro]
    bing = actual["bing"]
    spend_g, leads_g, cpa_g = actual["google"]
    spend_m, leads_m, cpa_m = actual["meta"]

    # Target Google = 72% del budget total (rango 70-75)
    google_target = round(budget_total * 0.72)
    meta_target   = budget_total - google_target - bing

    # Distribucion entre campanias Google
    camps = GOOGLE_CAMPS[seguro]
    rows = []
    # Calculo inicial usando el factor sugerido por la regla
    sum_propuesto = 0
    for c in camps:
        accion, factor = clasificar(c)
        nuevo = round(c["spend"] * factor)
        sum_propuesto += nuevo
        rows.append({**c, "accion": accion, "factor_inicial": factor, "spend_propuesto_pre": nuevo})

    # Reescalar para cuadrar con google_target (proporcional)
    if sum_propuesto > 0:
        ratio = google_target / sum_propuesto
        for r in rows:
            r["spend_propuesto"] = round(r["spend_propuesto_pre"] * ratio)
            r["budget_d_propuesto"] = round(r["spend_propuesto"] / 27, 0)  # 27 dias
            r["delta"] = r["spend_propuesto"] - r["spend"]
            r["delta_pct"] = (r["delta"] / r["spend"] * 100) if r["spend"] else 0

    return {
        "seguro":          seguro,
        "budget_total":    budget_total,
        "actual": {
            "google_spend":  spend_g,
            "google_leads":  leads_g,
            "google_cpa":    cpa_g,
            "meta_spend":    spend_m,
            "meta_leads":    leads_m,
            "meta_cpa":      cpa_m,
            "bing_spend":    bing,
            "total":         spend_g + spend_m + bing,
        },
        "propuesta": {
            "google_total":  sum(r["spend_propuesto"] for r in rows),
            "meta_total":    meta_target,
            "bing":          bing,
            "google_pct":    sum(r["spend_propuesto"] for r in rows) / budget_total * 100,
            "meta_pct":      meta_target / budget_total * 100,
            "bing_pct":      bing / budget_total * 100,
        },
        "campanias_google": rows,
    }


# ============== EXCEL WRITER ==============

def header(ws, row, headers, widths=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = H1; c.fill = H_AZUL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def write_resumen(wb: Workbook, props: list[dict]) -> None:
    ws = wb.create_sheet("Resumen")
    ws["A1"] = "SURA Tech Colombia · Propuesta distribución Mayo 2026"
    ws["A1"].font = Font(bold=True, size=16, color=SURA_AZUL)
    ws.merge_cells("A1:I1")
    ws["A2"] = "Beyond Media Agency · 70-75% Google · respetando topes por seguro · Bing fijo en plan"
    ws["A2"].font = Font(italic=True, size=10, color="768692")
    ws.merge_cells("A2:I2")
    r = 4
    headers = ["Seguro", "Budget total", "Google ahora", "Google propuesto", "Δ Google",
               "Meta ahora", "Meta propuesto", "Δ Meta", "Bing fijo"]
    widths = [16, 13, 14, 16, 13, 13, 14, 13, 11]
    header(ws, r, headers, widths)
    r += 1
    tot = {"budget":0, "g_now":0, "g_new":0, "m_now":0, "m_new":0, "b":0}
    for p in props:
        a = p["actual"]; pr = p["propuesta"]
        row = [p["seguro"], p["budget_total"],
               a["google_spend"], pr["google_total"], pr["google_total"] - a["google_spend"],
               a["meta_spend"], pr["meta_total"], pr["meta_total"] - a["meta_spend"],
               pr["bing"]]
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER; c.font = NORMAL
            if i == 1: c.font = BOLD
            if i in (5, 8):
                if isinstance(v, (int, float)):
                    if v > 0:
                        c.font = Font(name="Calibri", size=10, bold=True, color=VERDE)
                    elif v < 0:
                        c.font = Font(name="Calibri", size=10, bold=True, color=ROJO)
            if i in (2, 3, 4, 6, 7, 9):
                c.number_format = '"$"#,##0'
            if i == 5 or i == 8:
                c.number_format = '"$"#,##0;[RED]"-$"#,##0'
        tot["budget"] += p["budget_total"]
        tot["g_now"]  += a["google_spend"]
        tot["g_new"]  += pr["google_total"]
        tot["m_now"]  += a["meta_spend"]
        tot["m_new"]  += pr["meta_total"]
        tot["b"]      += pr["bing"]
        r += 1
    # Fila TOTAL
    ws.cell(row=r, column=1, value="TOTAL").font = BOLD
    ws.cell(row=r, column=2, value=tot["budget"])
    ws.cell(row=r, column=3, value=tot["g_now"])
    ws.cell(row=r, column=4, value=tot["g_new"])
    ws.cell(row=r, column=5, value=tot["g_new"] - tot["g_now"])
    ws.cell(row=r, column=6, value=tot["m_now"])
    ws.cell(row=r, column=7, value=tot["m_new"])
    ws.cell(row=r, column=8, value=tot["m_new"] - tot["m_now"])
    ws.cell(row=r, column=9, value=tot["b"])
    for col in range(1, 10):
        c = ws.cell(row=r, column=col)
        c.font = BOLD; c.border = BORDER
        c.fill = PatternFill("solid", fgColor=GRIS_FONDO)
        if col in (2, 3, 4, 5, 6, 7, 8, 9):
            c.number_format = '"$"#,##0'

    # Bloque 2: % Google / Meta / Bing por seguro (validacion del 70-75)
    r += 3
    ws.cell(row=r, column=1, value="% del total por canal").font = Font(bold=True, color=SURA_AZUL, size=12)
    r += 1
    header(ws, r, ["Seguro", "% Google", "% Meta", "% Bing", "Suma", "Cumple 70-75% Google?"],
           [16, 12, 12, 12, 12, 22])
    r += 1
    for p in props:
        pr = p["propuesta"]
        suma = pr["google_pct"] + pr["meta_pct"] + pr["bing_pct"]
        cumple = "✓ Sí" if 68 <= pr["google_pct"] <= 77 else "⚠ Revisar"
        row = [p["seguro"],
               f"{pr['google_pct']:.1f}%",
               f"{pr['meta_pct']:.1f}%",
               f"{pr['bing_pct']:.1f}%",
               f"{suma:.1f}%",
               cumple]
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER; c.font = NORMAL
            if i == 1: c.font = BOLD
            if i == 6 and "⚠" in str(v):
                c.font = Font(color=AMARILLO, bold=True)
            elif i == 6:
                c.font = Font(color=VERDE, bold=True)
        r += 1


def write_campanias_google(wb: Workbook, props: list[dict]) -> None:
    ws = wb.create_sheet("Detalle Google")
    ws["A1"] = "Detalle por campaña Google Ads"
    ws["A1"].font = Font(bold=True, size=14, color=SURA_AZUL)
    ws.merge_cells("A1:K1")
    r = 3
    headers = ["Seguro", "Campaña", "CPA actual", "% Lost Budget",
               "Budget/día actual", "Spend actual",
               "Conversiones actuales", "Acción", "Spend propuesto", "Δ Spend", "Δ %"]
    widths = [14, 50, 12, 13, 16, 13, 14, 22, 16, 14, 10]
    header(ws, r, headers, widths)
    r += 1
    for p in props:
        for c in p["campanias_google"]:
            row = [p["seguro"], c["nombre"], c["cpa"], c["lost_budget"],
                   c["budget_d_actual"], c["spend"], c["conv"],
                   c["accion"], c["spend_propuesto"], c["delta"], c["delta_pct"]]
            for i, v in enumerate(row, 1):
                cell = ws.cell(row=r, column=i, value=v)
                cell.border = BORDER; cell.font = NORMAL
                if i == 1: cell.font = BOLD
                if i == 3: cell.number_format = '"$"#,##0.00'
                if i == 4: cell.number_format = "0.0%"
                if i in (5, 6, 9): cell.number_format = '"$"#,##0'
                if i == 7: cell.number_format = "#,##0.0"
                if i == 10: cell.number_format = '"$"#,##0;[RED]"-$"#,##0'
                if i == 11: cell.number_format = '+0.0%;[RED]-0.0%'
                # Color de la accion
                if i == 8:
                    if "RECORTAR FUERTE" in str(v):
                        cell.fill = PatternFill("solid", fgColor="FEE2E2"); cell.font = Font(name="Calibri", size=10, bold=True, color=ROJO)
                    elif "RECORTAR" in str(v):
                        cell.fill = PatternFill("solid", fgColor="FEF3C7"); cell.font = Font(name="Calibri", size=10, bold=True, color=AMARILLO)
                    elif "ESCALAR FUERTE" in str(v):
                        cell.fill = PatternFill("solid", fgColor="D1FAE5"); cell.font = Font(name="Calibri", size=10, bold=True, color=VERDE)
                    elif "ESCALAR" in str(v):
                        cell.fill = PatternFill("solid", fgColor="ECFDF5"); cell.font = Font(name="Calibri", size=10, bold=True, color=VERDE)
                    elif "MANTENER" in str(v):
                        cell.fill = PatternFill("solid", fgColor=GRIS_FONDO); cell.font = NORMAL
            r += 1
        r += 1


def write_meta(wb: Workbook, props: list[dict]) -> None:
    ws = wb.create_sheet("Detalle Meta")
    ws["A1"] = "Detalle Meta (a nivel seguro · ad sets requieren CSV exportado)"
    ws["A1"].font = Font(bold=True, size=14, color=SURA_AZUL)
    ws.merge_cells("A1:G1")
    ws["A2"] = "Para detalle por ad set: en Meta Ads Manager → Reports → Export Reports (CSV)"
    ws["A2"].font = Font(italic=True, size=10, color="768692")
    ws.merge_cells("A2:G2")
    r = 4
    headers = ["Seguro", "Spend actual", "Leads actuales", "CPA actual",
               "Spend propuesto", "Δ Spend", "Recomendación"]
    widths = [14, 14, 14, 12, 16, 14, 60]
    header(ws, r, headers, widths)
    r += 1
    for p in props:
        a = p["actual"]; pr = p["propuesta"]
        cpa = a["meta_cpa"]
        delta = pr["meta_total"] - a["meta_spend"]
        # Recomendacion textual
        if cpa < 6:
            rec = f"Meta convierte excelente (CPA ${cpa:.2f}). Mantener mix 70-75% Google + escalar Meta moderado."
        elif cpa < 12:
            rec = f"Meta CPA aceptable (${cpa:.2f}). Mantener nivel actual."
        else:
            rec = f"Meta CPA alto (${cpa:.2f}). Revisar ad sets - posible recorte."
        if delta > 0:
            rec += f" → +${delta:,} respecto del actual."
        elif delta < 0:
            rec += f" → −${-delta:,} respecto del actual."

        row = [p["seguro"], a["meta_spend"], a["meta_leads"], cpa,
               pr["meta_total"], delta, rec]
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER; c.font = NORMAL
            if i == 1: c.font = BOLD
            if i in (2, 3, 5):
                c.number_format = '"$"#,##0' if i != 3 else "#,##0"
            if i == 4: c.number_format = '"$"#,##0.00'
            if i == 6: c.number_format = '"$"#,##0;[RED]"-$"#,##0'
            if i == 7: c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 50
        r += 1


def write_metodologia(wb: Workbook) -> None:
    ws = wb.create_sheet("Metodología")
    ws["A1"] = "Metodología de la propuesta"
    ws["A1"].font = Font(bold=True, size=14, color=SURA_AZUL)
    ws.merge_cells("A1:B1")
    rows = [
        ("Datos base", "Performance real del 1-27 abril 2026 cruzado con Sheet Leads CRM"),
        ("Constraint 1", "Tope por seguro provisto por el cliente (Auto $52.421, Moto $32.642, Arriendo $31.080, Viajes $16.900)"),
        ("Constraint 2", "70-75% del presupuesto en Google (mejor calidad de leads SF según cliente)"),
        ("Constraint 3", "Bing se mantiene en presupuesto del Flow"),
        ("", ""),
        ("Reglas de clasificación de campañas Google", ""),
        ("ESCALAR FUERTE (×1.80)", "CPA ≤ $7 y % Lost Budget ≥ 50% — palanca #1"),
        ("ESCALAR (×1.40)", "CPA ≤ $10 y % Lost Budget ≥ 30%"),
        ("ESCALAR LEVE (×1.20)", "CPA ≤ $10 y % Lost Budget ≥ 10%"),
        ("ESCALAR MODERADO (×1.20)", "CPA ≤ $15 y % Lost Budget ≥ 50%"),
        ("RECORTAR (×0.65)", "CPA entre $15 y $25"),
        ("RECORTAR FUERTE (×0.40)", "CPA > $25"),
        ("MANTENER (×1.00)", "Resto"),
        ("", ""),
        ("Ajuste fino", "Después del factor inicial, los presupuestos de Google se reescalan proporcionalmente para alcanzar exactamente el 72% del total por seguro."),
        ("", ""),
        ("Limitaciones honestas", ""),
        ("Meta", "Detalle por ad set requiere CSV exportado del Ads Manager (Reports → Export Reports). Esta propuesta optimiza Meta a nivel seguro."),
        ("Bing", "No se modificó (sin acceso desde el extractor)."),
        ("Estacionalidad", "Asume ritmo similar a abril. Si hay cambios estacionales, ajustar."),
    ]
    r = 3
    for k, v in rows:
        a = ws.cell(row=r, column=1, value=k)
        b = ws.cell(row=r, column=2, value=v)
        a.font = Font(bold=True, color=SURA_AZUL, size=10) if k and not v else BOLD if k else NORMAL
        b.font = NORMAL
        b.alignment = Alignment(wrap_text=True)
        if k and not v:
            a.font = Font(bold=True, color=SURA_AZUL, size=11)
        r += 1
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 90


def run() -> int:
    props = [proponer(s) for s in ["Auto", "Moto", "Arriendo", "Viajes"]]

    wb = Workbook()
    wb.remove(wb.active)
    write_resumen(wb, props)
    write_campanias_google(wb, props)
    write_meta(wb, props)
    write_metodologia(wb)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / "suratech_propuesta_distribucion_mayo2026.xlsx"
    wb.save(out)
    print(f"[propuesta] -> {out}")

    # Tambien dump JSON
    out_json = OUTPUTS_DIR / "suratech_propuesta_distribucion_mayo2026.json"
    out_json.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[propuesta json] -> {out_json}")

    # Stdout summary
    for p in props:
        pr = p["propuesta"]; a = p["actual"]
        print(f"\n=== {p['seguro']} (budget ${p['budget_total']:,}) ===")
        print(f"  Actual:    Google ${a['google_spend']:,} ({a['google_spend']/p['budget_total']*100:.0f}%) / Meta ${a['meta_spend']:,} / Bing ${a['bing_spend']:,}")
        print(f"  Propuesto: Google ${pr['google_total']:,} ({pr['google_pct']:.0f}%) / Meta ${pr['meta_total']:,} ({pr['meta_pct']:.0f}%) / Bing ${pr['bing']:,} ({pr['bing_pct']:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
