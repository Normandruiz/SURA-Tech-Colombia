"""Extractor de las 4 hojas individuales del Sheet CRM (Autos, Motos, Arriendo, Viajes).

Cada hoja tiene data DIARIA con las metricas reales del cliente. La columna
RECIBIDOS (SF) es la fuente de verdad: leads que efectivamente llegan a
Salesforce de SURA (no la pauta interna del agencia).

Output:
  raw/sheets_crm/full/<seguro>_YYYYMMDD.csv  (input - downloaded)
  raw/sheets_crm/parsed/<seguro>_<ts>.json   (output diario)
  raw/sheets_crm/parsed/mensual_<ts>.json    (output mensual agregado)
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from src.config import ROOT

RAW_FULL   = ROOT / "raw" / "sheets_crm" / "full"
RAW_PARSED = ROOT / "raw" / "sheets_crm" / "parsed"

# Columnas que queremos extraer, mapeadas por nombre canonico
WANTED_COLS = {
    "fecha":              ["Fecha"],
    "recibidos_sf":       ["RECIBIDOS (SF)"],
    "recibidos_ga":       ["RECIBIDOS (GA)"],
    "requeridos":         ["REQUERIDOS"],
    "total_pauta":        ["Total Pauta"],
    "cumpl_crm_vs_pauta": ["Cumplimiento (CRM Vs Pauta)"],
    "cumpl_pauta_vs_req": ["Cumplimiento (Pauta Vs Requeridos)"],
    "leads_google":       ["Total \nLeads Google", "Total Leads Google"],
    "consumo_google":     ["Consumo Google"],
    "cpl_google":         ["CPL Google"],
    "leads_meta":         ["Total \nLeads Meta", "Total Leads Meta"],
    "meta_conv_web":      ["Meta - Conversion web"],
    "meta_lead_pot":      ["Meta - Cliente potencial"],
    "consumo_meta":       ["Consumo Meta"],
    "leads_bing":         ["Total \nLeads Bing", "Total Leads Bing"],
    "consumo_bing":       ["Consumo Bing"],
    "cpl_bing":           ["CPL Bing"],
    "sel":                ["Autos SEL", "Motos SEL", "Arriendo SEL", "Viajes SEL"],
    "suraco":             ["Autos SURA.CO", "Motos SURA.CO", "Arriendo SURA.CO", "Viajes SURA.CO"],
}


def _num(s, default=None):
    if s is None or s == "":
        return default
    s = str(s).strip().replace("US$", "").replace("$", "").replace(" ", "").replace(" ", "")
    if not s or s in ("-", "—", "N/A", "#DIV/0!"):
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


def _parse_date(s: str) -> str | None:
    """Devuelve fecha ISO 'YYYY-MM-DD' o None si no parseable."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    return None


def find_header_row(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """Encuentra la fila header (la que tiene 'RECIBIDOS (SF)' en alguna celda)
    y devuelve (idx, mapping {canonical_col_name: csv_col_idx})."""
    for i, r in enumerate(rows[:30]):
        if any("RECIBIDOS" in (c or "").upper() for c in r):
            mapping: dict[str, int] = {}
            for canonical, candidates in WANTED_COLS.items():
                for j, cell in enumerate(r):
                    if not cell:
                        continue
                    if any(cell.strip() == cand.strip() for cand in candidates):
                        mapping[canonical] = j
                        break
            return i, mapping
    return -1, {}


def parse_seguro(csv_path: Path, seguro_canonical: str) -> dict:
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header_idx, col_map = find_header_row(rows)
    if header_idx < 0:
        raise ValueError(f"No encontrado RECIBIDOS (SF) en {csv_path.name}")

    fecha_col = col_map.get("fecha", 1)
    diarios = []
    for r in rows[header_idx + 1:]:
        if len(r) <= fecha_col:
            continue
        date_iso = _parse_date(r[fecha_col])
        if not date_iso:
            continue
        rec = {"fecha": date_iso}
        for canonical, csv_idx in col_map.items():
            if canonical == "fecha":
                continue
            if csv_idx >= len(r):
                continue
            rec[canonical] = _num(r[csv_idx])
        diarios.append(rec)

    return {
        "seguro": seguro_canonical,
        "source_file": csv_path.name,
        "header_row": header_idx,
        "col_mapping": col_map,
        "total_dias": len(diarios),
        "rango_fechas": (
            (diarios[0]["fecha"], diarios[-1]["fecha"]) if diarios else (None, None)
        ),
        "diarios": diarios,
    }


def aggregate_monthly(diarios: list[dict]) -> dict:
    """Agrega diarios a {YYYY-MM: {totales}}."""
    out: dict = {}
    for d in diarios:
        ym = d["fecha"][:7]  # YYYY-MM
        if ym not in out:
            out[ym] = {
                "recibidos_sf": 0, "recibidos_ga": 0, "requeridos": 0, "total_pauta": 0,
                "leads_google": 0, "consumo_google": 0, "leads_meta": 0, "consumo_meta": 0,
                "leads_bing": 0, "consumo_bing": 0,
                "meta_conv_web": 0, "meta_lead_pot": 0,
                "sel": 0, "suraco": 0,
                "dias": 0,
            }
        b = out[ym]
        b["dias"] += 1
        for k in ("recibidos_sf","recibidos_ga","requeridos","total_pauta",
                  "leads_google","consumo_google","leads_meta","consumo_meta",
                  "leads_bing","consumo_bing","meta_conv_web","meta_lead_pot",
                  "sel","suraco"):
            v = d.get(k)
            if v is not None:
                b[k] += v
    # Calcular CPL agregados
    for ym, b in out.items():
        b["cpl_negocio_sf"]    = (b["consumo_google"] + b["consumo_meta"] + b.get("consumo_bing",0)) / b["recibidos_sf"] if b["recibidos_sf"] else None
        b["cpl_pauta"]         = (b["consumo_google"] + b["consumo_meta"] + b.get("consumo_bing",0)) / b["total_pauta"] if b["total_pauta"] else None
        b["cumpl_pauta_vs_req"] = b["total_pauta"] / b["requeridos"] if b["requeridos"] else None
        b["cumpl_sf_vs_req"]    = b["recibidos_sf"] / b["requeridos"] if b["requeridos"] else None
        b["cumpl_sf_vs_pauta"]  = b["recibidos_sf"] / b["total_pauta"] if b["total_pauta"] else None
    return out


SEGURO_NAMES = {
    "autos":    "Autos",
    "motos":    "Motos",
    "arriendo": "Arrendamiento",
    "viajes":   "Viajes",
}


def run() -> int:
    RAW_PARSED.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    todos: dict = {}

    for slug, canonical in SEGURO_NAMES.items():
        files = sorted(RAW_FULL.glob(f"{slug}_*.csv"))
        if not files:
            print(f"  [SKIP] no hay CSV de {slug} en {RAW_FULL}")
            continue
        latest = files[-1]
        print(f"  parsing {canonical} <- {latest.name}")
        try:
            data = parse_seguro(latest, canonical)
        except Exception as e:
            print(f"    [FAIL] {e}")
            continue
        data["mensual"] = aggregate_monthly(data["diarios"])
        todos[canonical] = data
        out = RAW_PARSED / f"{slug}_{ts}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    [OK] {data['total_dias']} dias  rango {data['rango_fechas']}  -> {out.name}")

    # Resumen mensual conjunto
    summary: dict = {}
    for nombre, data in todos.items():
        summary[nombre] = data["mensual"]
    out_sum = RAW_PARSED / f"mensual_consolidado_{ts}.json"
    out_sum.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] mensual consolidado -> {out_sum.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
