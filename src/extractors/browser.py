"""Conexion Playwright con perfil dedicado DENTRO del repo.

Approach tomado de answer-auto-dashboard: usar launchPersistentContext con
un userDataDir nuevo (.auth-profile/ en la raiz del repo). Chrome SI permite
automation en un userDataDir nuevo (solo lo bloquea cuando es el default del
sistema), y las cookies de la sesion persisten entre corridas.

Flujo:
  1. Primera vez: correr `python -m src.extractors.setup_auth`. Abre Chrome,
     usuario se loguea en Google Ads + Meta + GA4 + Sheets, cierra.
  2. Siguientes corridas: los extractores reusan .auth-profile/ en headless
     o con UI visible, sin pedir re-login.

Uso:
    from src.extractors.browser import open_browser
    with open_browser(headless=True) as page:
        page.goto("https://ads.google.com/...")
"""

from contextlib import contextmanager
from pathlib import Path

from src.config import ROOT

AUTH_DIR = ROOT / ".auth-profile"   # SURA-Tech-Colombia/.auth-profile


@contextmanager
def open_browser(headless: bool = True, viewport=None):
    from playwright.sync_api import sync_playwright

    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(AUTH_DIR),
            channel="chrome",
            headless=headless,
            viewport=viewport or {"width": 1440, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            yield page
        finally:
            ctx.close()
