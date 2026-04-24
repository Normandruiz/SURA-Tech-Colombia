"""Extractor Google Ads - MCC SURATECH COLOMBIA (383-039-2811).

Replica el approach de answer-auto-dashboard:
  - launchPersistentContext con .auth-profile/ (userDataDir dentro del repo)
  - URLs con auth_params (ocid, euid, __u, uscid, authuser) que amarran sesion
  - Cada cuenta hija se accede cambiando el parametro __c

Salida:
  raw/<seguro-slug>/google_ads_overview_<ts>.png
  raw/<seguro-slug>/google_ads_campaigns_<ts>.png
  raw/<seguro-slug>/google_ads_campaigns_<ts>.html   (dump DOM)
  raw/<seguro-slug>/google_ads_conversions_<ts>.png
  raw/<seguro-slug>/google_ads_<ts>.json             (data parseada)

Prerequisito: correr `python -m src.extractors.setup_auth` una vez.
"""

from __future__ import annotations

import json
import re
import sys

from src.config import GOOGLE_ADS_ACCOUNTS, GOOGLE_ADS_MCC_ID, GOOGLE_ADS_AUTH_PARAMS
from src.extractors.browser import open_browser
from src.extractors._utils import raw_dir_for, save_screenshot, ts, wait_quiet


def _url(view: str, customer_numeric: str) -> str:
    """Construye URL de una vista (overview/campaigns/conversions) con auth_params."""
    params = {"__c": customer_numeric, **GOOGLE_ADS_AUTH_PARAMS}
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://ads.google.com/aw/{view}?{qs}"


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _extract_kpi_cards(page) -> dict:
    wanted = ["Coste", "Clics", "Impresiones", "Conversiones", "CTR",
              "CPC medio", "Coste/conv", "Tasa de conv", "Valor conv"]
    result: dict[str, str] = {}
    try:
        texts = page.locator(
            "[data-test-id*='kpi'], [role='figure'], material-card, [class*='kpi'], "
            "[class*='scorecard'], [class*='metric']"
        ).all_text_contents()
    except Exception:
        texts = []
    blob = " | ".join(texts)
    for label in wanted:
        m = re.search(rf"{re.escape(label)}[^A-Za-z]{{0,30}}([\d\.,\$%COPUSDX\s]+)", blob, re.I)
        if m:
            result[label] = _clean(m.group(1))[:40]
    return result


def _extract_rows(page, limit: int = 200) -> list[dict]:
    rows: list[dict] = []
    try:
        raw_rows = page.locator("[role='row']").all()
    except Exception:
        raw_rows = []
    for r in raw_rows[:limit]:
        try:
            cells = r.locator("[role='gridcell'], [role='cell']").all_text_contents()
        except Exception:
            cells = []
        cells = [_clean(c) for c in cells if _clean(c)]
        if len(cells) >= 3:
            rows.append({"cells": cells})
    return rows


def extract_account(page, seguro: str, info: dict) -> dict:
    numeric = info["numeric"]
    print(f"\n== {seguro} ({info['id']}) ==")
    out_dir = raw_dir_for(seguro)
    bundle: dict = {
        "seguro": seguro,
        "cuenta": info["name"],
        "customer_id": info["id"],
        "numeric": numeric,
        "extracted_at": ts(),
        "source": "google_ads_ui",
    }

    # ---- Overview ----
    print("  -> overview")
    page.goto(_url("overview", numeric), wait_until="domcontentloaded", timeout=60_000)
    wait_quiet(page, 20_000)
    save_screenshot(page, seguro, "google_ads_overview")
    bundle["overview_kpis"] = _extract_kpi_cards(page)
    bundle["overview_url"]  = page.url

    # Detectar si cayo al login / chooser
    if any(s in page.url for s in ("accounts.google.com", "accountchooser", "selectaccount", "signin")):
        bundle["error"] = "redirigido a login - correr setup_auth.py de nuevo"
        json_path = out_dir / f"google_ads_{ts()}.json"
        json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [FAIL] sesion caida, escribi {json_path.name}")
        return bundle

    # ---- Campaigns ----
    print("  -> campaigns")
    page.goto(_url("campaigns", numeric), wait_until="domcontentloaded", timeout=60_000)
    wait_quiet(page, 20_000)
    save_screenshot(page, seguro, "google_ads_campaigns")
    (out_dir / f"google_ads_campaigns_{ts()}.html").write_text(
        page.content(), encoding="utf-8", errors="ignore"
    )
    bundle["campaigns_rows"] = _extract_rows(page)
    bundle["campaigns_count"] = len(bundle["campaigns_rows"])

    # ---- Conversions (eventos) ----
    print("  -> conversions")
    page.goto(_url("conversions/customconversions", numeric),
              wait_until="domcontentloaded", timeout=60_000)
    wait_quiet(page, 20_000)
    save_screenshot(page, seguro, "google_ads_conversions")
    bundle["conversions_rows"] = _extract_rows(page)

    json_path = out_dir / f"google_ads_{ts()}.json"
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] -> {json_path.name} ({bundle['campaigns_count']} campanias)")
    return bundle


def run(only_seguro: str | None = None, headless: bool = True) -> int:
    print(f"[google_ads] MCC {GOOGLE_ADS_MCC_ID} - {len(GOOGLE_ADS_ACCOUNTS)} cuentas "
          f"(headless={headless})")

    accounts = (
        {only_seguro: GOOGLE_ADS_ACCOUNTS[only_seguro]}
        if only_seguro and only_seguro in GOOGLE_ADS_ACCOUNTS
        else GOOGLE_ADS_ACCOUNTS
    )
    if only_seguro and only_seguro not in GOOGLE_ADS_ACCOUNTS:
        print(f"  [ERROR] seguro '{only_seguro}' no existe. Opciones: {list(GOOGLE_ADS_ACCOUNTS)}")
        return 2

    with open_browser(headless=headless) as page:
        for seguro, info in accounts.items():
            try:
                extract_account(page, seguro, info)
            except Exception as e:
                print(f"  [FAIL] {seguro}: {e.__class__.__name__}: {e}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    target   = None
    headless = True
    for a in args:
        if a == "--headed":
            headless = False
        elif not a.startswith("--"):
            target = a
    raise SystemExit(run(only_seguro=target, headless=headless))
