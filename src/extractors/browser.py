"""Conexión Playwright al Chrome real del usuario vía CDP.

Chrome con el perfil por defecto del sistema no permite que Playwright lo lance
directamente (se bloquea por --remote-debugging-pipe sobre User Data default).

Workflow alternativo:
    1. Usuario abre Chrome con `scripts/launch_chrome_debug.bat` una vez.
       Ese .bat lanza Chrome con --remote-debugging-port=9222 y Profile 1.
    2. Playwright se conecta por CDP a ese Chrome ya abierto.
    3. Trabajamos sobre las mismas pestañas que el usuario ve.

Ventajas:
    - Usa la sesión logueada actual sin copiar el perfil.
    - Chrome queda usable durante la extracción (aunque evitar navegar).

Uso:
    from src.extractors.browser import open_browser
    with open_browser() as page:
        page.goto("https://ads.google.com/...")
"""

from contextlib import contextmanager
import os

CDP_ENDPOINT_ENV = "SURATECH_CDP_ENDPOINT"
DEFAULT_CDP_ENDPOINT = "http://localhost:9222"


class ChromeNotReachableError(RuntimeError):
    pass


@contextmanager
def open_browser(cdp_endpoint: str | None = None):
    from playwright.sync_api import sync_playwright

    endpoint = cdp_endpoint or os.environ.get(CDP_ENDPOINT_ENV, DEFAULT_CDP_ENDPOINT)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(endpoint, timeout=10_000)
        except Exception as e:
            raise ChromeNotReachableError(
                f"No pude conectarme a Chrome en {endpoint}. "
                f"Asegurate de haber corrido 'scripts\\launch_chrome_debug.bat' "
                f"y que Chrome este abierto. Detalle: {e}"
            ) from e

        if not browser.contexts:
            raise ChromeNotReachableError(
                f"Chrome en {endpoint} no expone contextos. Cerrá y reabrí con el .bat."
            )

        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})

        try:
            yield page
        finally:
            browser.close()
