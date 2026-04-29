"""
Build BI dataset for the new BI page.

Source: Google Sheet "Abril 2026 - Power Bi"
        https://docs.google.com/spreadsheets/d/1FMN-jx8ziDVnhLtpUiHUmHLe_MpcLANQeIi12efDMLc

Reads 4 monthly tabs (Enero, Febrero, Marzo, Abril Parcial) exported as CSV
in raw/sheets/ and generates docs/assets/data_bi.json.

Each row: Solucion, Source, Medium, Campaign, Content, Leads, Polizas, Prima_emitida

Output JSON structure:
{
  "meta": { "generated_at": "2026-04-29T...", "source": "Sheet ID ..." },
  "months": {
    "Enero":   [ {sol, src, med, camp, cont, leads, pol, prima}, ... ],
    "Febrero": [...],
    "Marzo":   [...],
    "Abril":   [...]
  },
  "totals_by_solucion_month": {
    "Enero":   { "Arriendo": {leads, pol, prima}, ... },
    ...
  },
  "totals_q1_plus_abril": { "Arriendo": {...}, "Autos": {...}, ... },
  "channels_by_solucion": {        # rollup por canal source-medium
    "Arriendo": {
      "google-ads/paid": {leads, pol, prima},
      ...
    },
    ...
  }
}
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "raw" / "sheets"
OUT_PATH = ROOT / "docs" / "assets" / "data_bi.json"

# Map filename -> month key
MONTHS = [
    ("Enero",   "Abril 2026  - Power Bi - Enero.csv"),
    ("Febrero", "Abril 2026  - Power Bi - Febrero.csv"),
    ("Marzo",   "Abril 2026  - Power Bi - Marzo.csv"),
    ("Abril",   "Abril 2026  - Power Bi - Abril (Parcial).csv"),
]

SOLUCIONES_VALID = {"Arriendo", "Autos", "Motos", "Viajes"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_int_es(s: str) -> int:
    """ES format: '3.526' -> 3526. Empty -> 0."""
    if s is None:
        return 0
    s = s.strip()
    if not s:
        return 0
    # remove thousands separator (.) -- es-CO uses '.' for thousands
    s = s.replace(".", "").replace(",", "")
    try:
        return int(s)
    except ValueError:
        # could be a float-shaped string
        try:
            return int(float(s))
        except ValueError:
            return 0


def parse_money_cop(s: str) -> int:
    """ '$404.409.698,' -> 404409698. Empty -> 0."""
    if s is None:
        return 0
    s = s.strip()
    if not s:
        return 0
    # keep only digits
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


def normalize_row(row: dict) -> dict | None:
    """Return normalized dict or None if row should be skipped (Total / empty)."""
    sol = (row.get("Solución") or "").strip()
    if sol == "Total" or not sol:
        return None
    if sol not in SOLUCIONES_VALID:
        # ignore noisy rows
        return None
    return {
        "sol":   sol,
        "src":   (row.get("Source")   or "").strip(),
        "med":   (row.get("Medium")   or "").strip(),
        "camp":  (row.get("Campaign") or "").strip(),
        "cont":  (row.get("Content")  or "").strip(),
        "leads": parse_int_es(row.get("Leads") or ""),
        "pol":   parse_int_es(row.get("Pólizas") or ""),
        "prima": parse_money_cop(row.get("Prima_emitida") or ""),
    }


def read_month_csv(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            r = normalize_row(raw)
            if r is None:
                continue
            # skip rows where everything is zero
            if r["leads"] == 0 and r["pol"] == 0 and r["prima"] == 0:
                continue
            rows.append(r)
    return rows


def aggregate_by_solucion(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        sol = r["sol"]
        agg = out.setdefault(sol, {"leads": 0, "pol": 0, "prima": 0})
        agg["leads"] += r["leads"]
        agg["pol"]   += r["pol"]
        agg["prima"] += r["prima"]
    return out


def aggregate_channels_by_solucion(rows: list[dict]) -> dict:
    """For each solucion, group by source/medium combo."""
    out = {}
    for r in rows:
        sol = r["sol"]
        src = r["src"] or "(directo)"
        med = r["med"] or "(s/medium)"
        ch_key = f"{src}/{med}"
        ch_dict = out.setdefault(sol, {})
        agg = ch_dict.setdefault(ch_key, {"leads": 0, "pol": 0, "prima": 0})
        agg["leads"] += r["leads"]
        agg["pol"]   += r["pol"]
        agg["prima"] += r["prima"]
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    months_data: dict[str, list[dict]] = {}
    for month_key, fname in MONTHS:
        path = RAW_DIR / fname
        if not path.exists():
            print(f"[WARN] missing {path}")
            months_data[month_key] = []
            continue
        rows = read_month_csv(path)
        months_data[month_key] = rows
        print(f"[OK] {month_key:10s}: {len(rows):3d} filas")

    # Totals by solucion per month
    totals_by_sol_month = {
        m: aggregate_by_solucion(rows) for m, rows in months_data.items()
    }

    # Q1 + Abril (rollup)
    all_rows = []
    for rows in months_data.values():
        all_rows.extend(rows)
    totals_total = aggregate_by_solucion(all_rows)

    # Channels by solucion (using all rows)
    channels = aggregate_channels_by_solucion(all_rows)

    # Sort channels by prima desc within each solucion
    channels_sorted = {}
    for sol, chmap in channels.items():
        items = sorted(chmap.items(), key=lambda kv: -kv[1]["prima"])
        channels_sorted[sol] = [
            {"channel": k, **v} for k, v in items
        ]

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_sheet_id": "1FMN-jx8ziDVnhLtpUiHUmHLe_MpcLANQeIi12efDMLc",
            "source_sheet_name": "Abril 2026 - Power Bi",
            "tabs_used": [m[0] for m in MONTHS],
            "soluciones": sorted(SOLUCIONES_VALID),
        },
        "months": months_data,
        "totals_by_solucion_month": totals_by_sol_month,
        "totals_total": totals_total,
        "channels_by_solucion": channels_sorted,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] dataset: {OUT_PATH}  ({OUT_PATH.stat().st_size/1024:.1f} kB)")

    # Quick verification print
    print("\nResumen totales (Q1 + Abril parcial):")
    for sol, agg in sorted(totals_total.items()):
        print(f"  {sol:10s}  leads={agg['leads']:>6}  pol={agg['pol']:>5}  prima=${agg['prima']:>14,}".replace(",", "."))


if __name__ == "__main__":
    main()
