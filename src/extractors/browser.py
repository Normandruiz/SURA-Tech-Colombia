"""Conexión Playwright al perfil de Chrome del usuario.

Uso:
    from src.extractors.browser import open_browser
    with open_browser() as page:
        page.goto("https://ads.google.com/...")
"""

from contextlib import contextmanager
from pathlib import Path
import os

CHROME_PROFILE_DIR_ENV = "SURATECH_CHROME_PROFILE"


def _default_profile_dir() -> Path:
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "Usuario"
    return Path(f"C:/Users/{user}/AppData/Local/Google/Chrome/User Data")


@contextmanager
def open_browser(headless: bool = False, profile_dir: str | None = None):
    from playwright.sync_api import sync_playwright

    profile = Path(profile_dir) if profile_dir else Path(
        os.environ.get(CHROME_PROFILE_DIR_ENV, str(_default_profile_dir()))
    )
    if not profile.exists():
        raise FileNotFoundError(
            f"Perfil Chrome no existe: {profile}. "
            f"Seteá {CHROME_PROFILE_DIR_ENV} o pasá profile_dir."
        )

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=headless,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        try:
            yield page
        finally:
            ctx.close()
