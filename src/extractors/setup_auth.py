"""Setup de autenticacion - correr UNA VEZ para guardar la sesion.

Abre Chrome (no headless) con el perfil dedicado del repo, te deja loguearte
manualmente en Google Ads / Meta / GA4 / Sheets, y cuando apretas ENTER en
la terminal cierra el browser con las cookies persistidas.

Uso:
    .venv\\Scripts\\python.exe -m src.extractors.setup_auth

Repetir solo si la sesion expira (Google suele durar semanas si marcas
"Mantener sesion iniciada").
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from src.config import (
    GOOGLE_ADS_MCC_ID_NUMERIC,
    GOOGLE_ADS_AUTH_PARAMS,
    META_BUSINESS_MANAGER_ID,
    SHEETS_CRM_URL,
    GA4_PROPERTY_ID,
)
from src.extractors.browser import AUTH_DIR


def _mcc_url() -> str:
    params = {"__c": GOOGLE_ADS_MCC_ID_NUMERIC, **GOOGLE_ADS_AUTH_PARAMS}
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://ads.google.com/aw/accounts?{qs}"


def _meta_url() -> str:
    return f"https://business.facebook.com/latest/home?business_id={META_BUSINESS_MANAGER_ID}"


def _ga4_url() -> str:
    return f"https://analytics.google.com/analytics/web/#/p{GA4_PROPERTY_ID}/reports/intelligenthome"


def main() -> int:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[setup-auth] perfil dedicado: {AUTH_DIR}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(AUTH_DIR),
            channel="chrome",
            headless=False,
            viewport=None,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        steps = [
            ("Google Ads (MCC SURATECH)",    _mcc_url()),
            ("Meta Business Manager",        _meta_url()),
            ("GA4 - Seguros SURA",           _ga4_url()),
            ("Google Sheet Leads CRM",       SHEETS_CRM_URL),
        ]

        for i, (label, url) in enumerate(steps, 1):
            print(f"\n[{i}/{len(steps)}] -> {label}")
            print(f"          {url}")
            tab = page if i == 1 else ctx.new_page()
            tab.goto(url)
            input(f"  Logueate y confirma acceso. Cuando veas el contenido real, apreta ENTER... ")

        print("\nGuardando sesion...")
        ctx.close()
        print(f"[OK] sesion persistida en {AUTH_DIR}")
        print("     Ahora podes correr los extractores: python -m src.extractors.google_ads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
