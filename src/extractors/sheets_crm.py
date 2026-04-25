"""Extractor Sheet 'Leads CRM' - hoja 'Resumen mensual'.

Estrategia: el CSV se descarga via Claude in Chrome (ver instrucciones en README).
Este modulo parsea el CSV y produce un JSON estructurado por seguro y mes.

El Sheet tiene SOLO 4 productos activos:
  Carros (= Autos), Motos, Arriendo (= Arrendamiento), Viaje (= Viajes)
+ total agregado "Movilidad". NO hay Salud para Dos ni Salud Animal aqui.

Columnas (inferidas del header de 'Resumen mensual'):
  col  1: Producto
  col  2: Compromiso Leads del mes
  col  3: Leads CRM (resultado real)
  col  4: Leads GA4 (a veces '-')
  col  5: Cumplimiento %
  col  6: CPL Negocio promedio
  col  7: Leads GA Ads
  col  8: CPL GA Ads
  col  9: Inversion GA Ads
  col 10: Leads Meta
  col 11: CPL Meta
  col 12: Inversion Meta
  col 13: Leads otro canal
  col 14: CPL otro canal
  col 15: Inversion otro canal
  col 16: Leads totales (suma plataformas)
  col 17: Inversion total
  col 18: CPL Negocio total

Nota: el mapping de columnas necesita validacion del usuario.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime

from src.config import ROOT, OUTPUTS_DIR

RAW_DIR = ROOT / "raw" / "sheets_crm"

# Mapping nombre Sheet -> nombre canonico SURA Tech Colombia
SEGURO_ALIASES = {
    "carros":     "Autos",
    "motos":      "Motos",
    "arriendo":   "Arrendamiento",
    "viaje":      "Viajes",
    "viajes":     "Viajes",
    "movilidad":  "_TOTAL_MOVILIDAD",  # agregado
}


def _num(s: str) -> float | None:
    """Parser tolerante para numeros con formato es-CO ($, ., , %)."""
    if s is None:
        return None
    s = s.strip().replace("$", "").replace(" ", "")
    if not s or s == "-":
        return None
    if "%" in s:
        s = s.replace("%", "")
        m = re.match(r"^-?[\d\.,]+$", s)
        if not m:
            return None
        # 56,64 -> 56.64 -> 0.5664
        return float(s.replace(".", "").replace(",", ".")) / 100
    if "," in s and "." in s:
        # Formato es: 9.823,45
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) <= 2:
        pass  # 9.50 -> 9.50 (ambiguo, dejamos)
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return None


def parse_csv(csv_path: Path) -> dict:
    """Lee el CSV y devuelve estructura {periodo: {seguro: {metricas}}}.

    El CSV tiene bloques mensuales. Cada bloque comienza con una celda mes
    (ej. 'abril 2026') en col 2 de la fila header del bloque, seguido de filas
    para Carros, Motos, Arriendo, Viaje, Totales (Movilidad).
    """
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # Detectar bloques: una fila con solo col 2 con texto mes + año
    month_re = re.compile(r"^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
                          r"octubre|noviembre|diciembre)\s+\d{4}$", re.I)
    block_starts: list[tuple[int, str]] = []
    for i, r in enumerate(rows):
        cell = (r[2].strip() if len(r) > 2 else "")
        if month_re.match(cell):
            block_starts.append((i, cell))

    out: dict[str, dict] = {}
    for k, (start, label) in enumerate(block_starts):
        end = block_starts[k + 1][0] if k + 1 < len(block_starts) else len(rows)
        block_rows = rows[start:end]
        seguros: dict[str, dict] = {}
        for r in block_rows:
            if len(r) < 19:
                continue
            name = (r[1] or "").strip().lower()
            if name not in SEGURO_ALIASES or SEGURO_ALIASES[name] == "_TOTAL_MOVILIDAD":
                continue
            canonical = SEGURO_ALIASES[name]
            seguros[canonical] = {
                "compromiso_leads":   _num(r[2]),
                "leads_crm":          _num(r[3]),
                "leads_ga4":          _num(r[4]),
                "cumplimiento_pct":   _num(r[5]),
                "cpl_negocio":        _num(r[6]),
                "leads_google_ads":   _num(r[7]),
                "cpl_google_ads":     _num(r[8]),
                "inversion_google":   _num(r[9]),
                "leads_meta":         _num(r[10]),
                "cpl_meta":           _num(r[11]),
                "inversion_meta":     _num(r[12]),
                "leads_otro":         _num(r[13]),
                "cpl_otro":           _num(r[14]),
                "inversion_otro":     _num(r[15]),
                "leads_total":        _num(r[16]),
                "inversion_total":    _num(r[17]),
                "cpl_negocio_total":  _num(r[18]),
                "raw_cells":          r[:20],
            }
        out[label] = seguros

    return {
        "source": "google_sheets",
        "sheet_id": "1a4rI2X3fW9JD-cZZDYD1umTRpAmL5ZZjtPpGjYkAyRw",
        "tab": "Resumen mensual",
        "extracted_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "csv_file": str(csv_path.name),
        "total_rows": len(rows),
        "blocks_found": len(block_starts),
        "seguros_disponibles": ["Autos", "Motos", "Arrendamiento", "Viajes"],
        "seguros_NO_disponibles": ["Salud para Dos", "Salud Animal"],
        "data_por_mes": out,
    }


def run() -> int:
    csvs = sorted(RAW_DIR.glob("resumen_mensual_*.csv"))
    if not csvs:
        print(f"[sheets_crm] no hay CSV en {RAW_DIR}. Descargar primero via Claude in Chrome.")
        return 2

    latest = csvs[-1]
    print(f"[sheets_crm] parseando {latest.name}")
    data = parse_csv(latest)
    print(f"  bloques mensuales: {data['blocks_found']}")
    print(f"  seguros disponibles: {data['seguros_disponibles']}")
    print(f"  seguros NO disponibles: {data['seguros_NO_disponibles']}")

    # Mostrar el mes actual y los datos por seguro
    if data["data_por_mes"]:
        last_month = list(data["data_por_mes"].keys())[0]
        print(f"\n  --- {last_month} ---")
        for seguro, metrics in data["data_por_mes"][last_month].items():
            print(f"    {seguro:18s} compromiso={metrics['compromiso_leads']} "
                  f"leads_crm={metrics['leads_crm']} cumpl={metrics['cumplimiento_pct']} "
                  f"cpl_neg={metrics['cpl_negocio']}")

    # Guardar JSON
    out_path = RAW_DIR / f"resumen_mensual_{data['extracted_at']}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [OK] -> {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
