"""
Genera docs/assets/data_cross.json para la nueva página Cross.

Cruza:
  - CSVs Google: raw/google/2026_ene_abr/{Autos,Motos,Viajes,Arriendo}.csv
  - CSV Meta:    raw/meta/2026_ene_abr/Meta.csv
  - Sheet BI:    docs/assets/data_bi.json

Reutiliza la lógica de build_costos_conversion_xlsx.py para no duplicar parsing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse helpers from the existing script
THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent))
from build_costos_conversion_xlsx import (  # noqa: E402
    GOOGLE_DIR, META_PATH, BI_PATH, GOOGLE_FILES, PRODUCTS, MONTHS_ORDER, MONTH_KEY,
    SOURCES_GOOGLE, SOURCES_META, SOURCES_BING,
    parse_google_csv, parse_meta_csv,
    aggregate_google_full, aggregate_meta_full,
    diagnose_cpl_change, index_bi_by_campaign, match_campaign_to_bi,
)

ROOT = THIS.parents[2]
OUT_PATH = ROOT / "docs" / "assets" / "data_cross.json"


def main() -> None:
    # 1) Parse all sources
    rows_by_product = {p: parse_google_csv(GOOGLE_DIR / fname) for p, fname in GOOGLE_FILES.items()}
    meta_rows = parse_meta_csv(META_PATH)
    bi_data = json.loads(BI_PATH.read_text(encoding="utf-8")) if BI_PATH.exists() else {}
    bi_index = index_bi_by_campaign(bi_data) if bi_data else {}

    # 2) Aggregates with full metrics
    g_full = aggregate_google_full(rows_by_product)
    m_full = aggregate_meta_full(meta_rows)

    # 3) Build by_product_month structure
    def serialize_full(p: str, m: str, plat_full: dict):
        a = plat_full[p][m]
        return {
            "spend":     round(a["coste"], 2),
            "conv":      round(a["conv"], 2),
            "impr":      a["impr"],
            "clics":     a.get("clics", 0),
            "cpa":       round(a["cpa"], 2) if a["cpa"] else 0,
            "cpc":       round(a.get("cpc", 0), 2),
            "ctr":       round(a.get("ctr", 0), 4),
            "cpm":       round(a.get("cpm", 0), 2),
            "tasa_conv": round(a.get("tasa_conv", 0), 4),
        }

    by_product_month = {}
    for prod in PRODUCTS:
        by_product_month[prod] = {}
        for mes in MONTHS_ORDER:
            by_product_month[prod][mes] = {
                "google": serialize_full(prod, mes, g_full),
                "meta":   serialize_full(prod, mes, m_full),
            }

    # 4) Build leads SF per (producto, mes, plataforma) and pólizas per (producto, mes, plataforma)
    leads_pms = {p: {m: {"google": 0, "meta": 0, "bing": 0, "otros": 0} for m in MONTHS_ORDER} for p in PRODUCTS}
    pol_pms   = {p: {m: {"google": 0, "meta": 0, "bing": 0, "otros": 0} for m in MONTHS_ORDER} for p in PRODUCTS}
    prima_pms = {p: {m: {"google": 0, "meta": 0, "bing": 0, "otros": 0} for m in MONTHS_ORDER} for p in PRODUCTS}

    for mes, rows in bi_data.get("months", {}).items():
        if mes not in MONTHS_ORDER:
            continue
        for r in rows:
            sol = r.get("sol")
            if sol not in PRODUCTS:
                continue
            src = (r.get("src") or "").lower()
            leads = int(r.get("leads") or 0)
            pol = int(r.get("pol") or 0)
            prima = int(r.get("prima") or 0)
            if src in SOURCES_GOOGLE:
                bucket = "google"
            elif src in SOURCES_META:
                bucket = "meta"
            elif src in SOURCES_BING:
                bucket = "bing"
            else:
                bucket = "otros"
            leads_pms[sol][mes][bucket] += leads
            pol_pms[sol][mes][bucket]   += pol
            prima_pms[sol][mes][bucket] += prima

    # Inject leads_sf / polizas / prima into by_product_month
    for prod in PRODUCTS:
        for mes in MONTHS_ORDER:
            for plat in ("google", "meta"):
                d = by_product_month[prod][mes][plat]
                d["leads_sf"] = leads_pms[prod][mes][plat]
                d["polizas"] = pol_pms[prod][mes][plat]
                d["prima_cop"] = prima_pms[prod][mes][plat]
                d["cpl_negocio"] = round(d["spend"] / d["leads_sf"], 2) if d["leads_sf"] else 0
                d["cac"] = round(d["spend"] / d["polizas"], 2) if d["polizas"] else 0

    # 5) Totals per product (Ene-Abr)
    totals = {}
    for prod in PRODUCTS:
        totals[prod] = {}
        for plat in ("google", "meta"):
            tot = {"spend": 0.0, "conv": 0.0, "impr": 0, "clics": 0,
                   "leads_sf": 0, "polizas": 0, "prima_cop": 0}
            for mes in MONTHS_ORDER:
                d = by_product_month[prod][mes][plat]
                tot["spend"] += d["spend"]
                tot["conv"]  += d["conv"]
                tot["impr"]  += d["impr"]
                tot["clics"] += d["clics"]
                tot["leads_sf"] += d["leads_sf"]
                tot["polizas"]  += d["polizas"]
                tot["prima_cop"]+= d["prima_cop"]
            tot["cpa"] = round(tot["spend"] / tot["conv"], 2) if tot["conv"] else 0
            tot["cpl_negocio"] = round(tot["spend"] / tot["leads_sf"], 2) if tot["leads_sf"] else 0
            tot["cac"] = round(tot["spend"] / tot["polizas"], 2) if tot["polizas"] else 0
            tot["spend"] = round(tot["spend"], 2)
            tot["conv"]  = round(tot["conv"], 0)
            totals[prod][plat] = tot

    # 6) Diagnósticos CEO por (producto, plataforma): comparar Ene vs Abr
    diagnostics = []
    for prod in PRODUCTS:
        for plat_key, agg in [("Google", g_full), ("Meta", m_full)]:
            ene = agg[prod]["Enero"]
            abr = agg[prod]["Abril"]
            d = diagnose_cpl_change(ene, abr, plat_key)
            diagnostics.append({
                "producto": prod,
                "plataforma": plat_key,
                "severity": d["severity"],
                "ene": {
                    "cpa":       round(ene["cpa"], 2) if ene["cpa"] else 0,
                    "spend":     round(ene["coste"], 2),
                    "conv":      round(ene["conv"], 2),
                    "cpc":       round(ene.get("cpc", 0), 2),
                    "ctr":       round(ene.get("ctr", 0), 4),
                    "cpm":       round(ene.get("cpm", 0), 2),
                    "tasa_conv": round(ene.get("tasa_conv", 0), 4),
                    "impr":      ene["impr"],
                },
                "abr": {
                    "cpa":       round(abr["cpa"], 2) if abr["cpa"] else 0,
                    "spend":     round(abr["coste"], 2),
                    "conv":      round(abr["conv"], 2),
                    "cpc":       round(abr.get("cpc", 0), 2),
                    "ctr":       round(abr.get("ctr", 0), 4),
                    "cpm":       round(abr.get("cpm", 0), 2),
                    "tasa_conv": round(abr.get("tasa_conv", 0), 4),
                    "impr":      abr["impr"],
                },
                "deltas": {
                    "cpa":       round(d["cpa"], 1),
                    "spend":     round(d["spend"], 1),
                    "conv":      round(d["conv"], 1),
                    "impr":      round(d["impr"], 1),
                    "cpc":       round(d.get("cpc", 0), 1),
                    "ctr":       round(d.get("ctr", 0), 1),
                    "cpm":       round(d.get("cpm", 0), 1),
                    "tasa_conv": round(d.get("tasa_conv", 0), 1),
                },
                "drivers": d["drivers"],
                "actions": d["actions"],
            })

    # 7) Match a nivel campaña para tabla
    from collections import defaultdict
    google_by_camp = defaultdict(lambda: {"spend": 0, "conv": 0, "estado": ""})
    for prod, rows in rows_by_product.items():
        for r in rows:
            k = (prod, r["campana"])
            google_by_camp[k]["spend"] += r["coste"]
            google_by_camp[k]["conv"]  += r["conversiones"]
            google_by_camp[k]["estado"] = r["estado"] or google_by_camp[k]["estado"]

    meta_by_adset = defaultdict(lambda: {"spend": 0, "conv": 0, "estado": ""})
    for r in meta_rows:
        if r["producto"] not in PRODUCTS:
            continue
        k = (r["producto"], r["adset"])
        meta_by_adset[k]["spend"] += r["spend"]
        meta_by_adset[k]["conv"]  += r["results"]
        meta_by_adset[k]["estado"] = r["estado"] or meta_by_adset[k]["estado"]

    campaigns = []
    roi_zero = []
    for (prod, camp), v in google_by_camp.items():
        matched = match_campaign_to_bi(prod, camp, bi_index)
        leads_sf = sum(d["leads"] for d in matched.values())
        polizas  = sum(d["pol"]   for d in matched.values())
        prima    = sum(d["prima"] for d in matched.values())
        spend = v["spend"]
        conv = v["conv"]
        item = {
            "producto":    prod,
            "plataforma":  "Google",
            "nombre":      camp,
            "estado":      v["estado"],
            "spend":       round(spend, 2),
            "conv":        round(conv, 1),
            "cpa":         round(spend / conv, 2) if conv > 0 else 0,
            "leads_sf":    leads_sf,
            "cpl_negocio": round(spend / leads_sf, 2) if leads_sf > 0 else 0,
            "polizas":     polizas,
            "cac":         round(spend / polizas, 2) if polizas > 0 else 0,
            "prima_cop":   prima,
        }
        campaigns.append(item)
        if spend > 50 and leads_sf == 0:
            roi_zero.append(item)

    for (prod, adset), v in meta_by_adset.items():
        matched = match_campaign_to_bi(prod, adset, bi_index)
        leads_sf = sum(d["leads"] for d in matched.values())
        polizas  = sum(d["pol"]   for d in matched.values())
        prima    = sum(d["prima"] for d in matched.values())
        spend = v["spend"]
        conv = v["conv"]
        item = {
            "producto":    prod,
            "plataforma":  "Meta",
            "nombre":      adset,
            "estado":      v["estado"],
            "spend":       round(spend, 2),
            "conv":        round(conv, 1),
            "cpa":         round(spend / conv, 2) if conv > 0 else 0,
            "leads_sf":    leads_sf,
            "cpl_negocio": round(spend / leads_sf, 2) if leads_sf > 0 else 0,
            "polizas":     polizas,
            "cac":         round(spend / polizas, 2) if polizas > 0 else 0,
            "prima_cop":   prima,
        }
        campaigns.append(item)
        if spend > 50 and leads_sf == 0:
            roi_zero.append(item)

    # Sort campaigns by spend desc
    campaigns.sort(key=lambda x: -x["spend"])
    roi_zero.sort(key=lambda x: -x["spend"])

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "periodo": "2026-01-01 a 2026-04-28",
            "fuentes": {
                "google_ads": "Google Ads MCC SURATECH (CSV export segmentado por mes)",
                "meta_ads":   "Meta Ads Manager (CSV export desglose mensual)",
                "sheet_bi":   "Sheet 'Abril 2026 - Power Bi' (data_bi.json)",
            },
            "productos": PRODUCTS,
            "meses": MONTHS_ORDER,
            "tc_referencial_cop_usd": 4000,
        },
        "totals_per_product": totals,
        "by_product_month": by_product_month,
        "diagnostics": diagnostics,
        "campaigns": campaigns,
        "roi_zero": roi_zero,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] dataset: {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} kB)")
    print(f"     productos: {len(PRODUCTS)}, meses: {len(MONTHS_ORDER)}, campañas: {len(campaigns)}, ROI cero: {len(roi_zero)}, diagnostics: {len(diagnostics)}")


if __name__ == "__main__":
    main()
