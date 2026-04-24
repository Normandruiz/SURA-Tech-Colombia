"""Setup de autenticacion - correr UNA VEZ para guardar la sesion.

Abre Chrome con el perfil dedicado (.auth-profile/). Va paso a paso:
1 pestana por plataforma. Espera a que te loguees (detecta por URL).
Cuando completas las 4 cierra y persiste cookies.

Uso:
    .venv\\Scripts\\python.exe -u -m src.extractors.setup_auth
"""

from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

from src.config import (
    GOOGLE_ADS_MCC_ID_NUMERIC,
    GOOGLE_ADS_AUTH_PARAMS,
    META_BUSINESS_MANAGER_ID,
    SHEETS_CRM_URL,
    GA4_PROPERTY_ID,
)
from src.extractors.browser import AUTH_DIR


def say(msg: str) -> None:
    print(msg, flush=True)
    sys.stdout.flush()


def _mcc_url() -> str:
    params = {"__c": GOOGLE_ADS_MCC_ID_NUMERIC, **GOOGLE_ADS_AUTH_PARAMS}
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://ads.google.com/aw/accounts?{qs}"


STEPS = [
    {
        "label": "1/4 Google Ads - MCC SURATECH",
        "url":   None,
        "ok":    "ads.google.com/aw",
        "bad":   ("accounts.google.com", "accountchooser", "signin"),
    },
    {
        "label": "2/4 Meta Business Manager",
        "url":   f"https://business.facebook.com/latest/home?business_id={META_BUSINESS_MANAGER_ID}",
        "ok":    "business.facebook.com/latest",
        "bad":   ("facebook.com/login", "login.php", "checkpoint"),
    },
    {
        "label": "3/4 Google Analytics 4",
        "url":   f"https://analytics.google.com/analytics/web/#/p{GA4_PROPERTY_ID}/reports/intelligenthome",
        "ok":    "analytics.google.com",
        "bad":   ("accounts.google.com",),
    },
    {
        "label": "4/4 Google Sheet Leads CRM",
        "url":   SHEETS_CRM_URL,
        "ok":    "docs.google.com/spreadsheets",
        "bad":   ("accounts.google.com",),
    },
]


def wait_for_login(page, step: dict, max_s: int = 600, poll_s: float = 2.0) -> bool:
    waited = 0.0
    last_url = ""
    while waited < max_s:
        try:
            page.bring_to_front()
        except Exception:
            pass
        try:
            url = page.url or ""
        except Exception:
            url = ""
        if url != last_url:
            say(f"      url -> {url[:100]}")
            last_url = url
        ok  = step["ok"] in url
        bad = any(b in url for b in step["bad"])
        if ok and not bad:
            return True
        time.sleep(poll_s)
        waited += poll_s
    return False


def main() -> int:
    STEPS[0]["url"] = _mcc_url()
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    say("=" * 60)
    say("  SURA TECH - SETUP AUTH")
    say("=" * 60)
    say(f"  Perfil dedicado: {AUTH_DIR}")
    say("  Chrome va a abrir una pestana a la vez.")
    say("  Logueate con norman.ruiz@beyondmediaagency.com en cada una.")
    say("  El script detecta cuando completas login y avanza solo.")
    say("=" * 60)
    say("")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(AUTH_DIR),
            channel="chrome",
            headless=False,
            viewport=None,
            args=["--start-maximized", "--new-window"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, step in enumerate(STEPS):
            say(f">>> {step['label']}")
            say(f"    URL: {step['url']}")
            if i == 0:
                page.goto(step["url"], wait_until="domcontentloaded", timeout=60_000)
            else:
                page = ctx.new_page()
                page.goto(step["url"], wait_until="domcontentloaded", timeout=60_000)
            say(f"    esperando login...")
            if wait_for_login(page, step, max_s=600):
                say(f"    [OK] logueado\n")
            else:
                say(f"    [TIMEOUT] sin login tras 10 min\n")

        say("Guardando sesion y cerrando browser...")
        ctx.close()
    say(f"[DONE] sesion persistida en {AUTH_DIR}")
    say("       Siguiente: python -m src.extractors.google_ads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
