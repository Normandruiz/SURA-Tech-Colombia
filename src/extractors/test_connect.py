"""Test de conexion Paso 1 - abrir el MCC SURATECH COLOMBIA en Google Ads.

Prerequisito: correr `scripts\\launch_chrome_debug.bat` una vez para que Chrome
quede escuchando en http://localhost:9222 con el perfil Norman (Persona 1).

Despues:
    .venv\\Scripts\\python.exe -m src.extractors.test_connect
"""

from datetime import datetime

from src.extractors.browser import open_browser, ChromeNotReachableError
from src.config import GOOGLE_ADS_MCC_ID, RAW_DIR

DEBUG_DIR = RAW_DIR / "debug"
MCC_URL_TEMPLATE = "https://ads.google.com/aw/accounts?__e={mcc}"


def main() -> int:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    mcc_numeric = GOOGLE_ADS_MCC_ID.replace("-", "")
    url = MCC_URL_TEMPLATE.format(mcc=mcc_numeric)

    print(f"-> Abriendo MCC {GOOGLE_ADS_MCC_ID} ({url})")
    try:
        with open_browser() as page:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass

            title = page.title()
            current_url = page.url
            print(f"  title: {title}")
            print(f"  url  : {current_url}")

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = DEBUG_DIR / f"mcc_connect_{stamp}.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"  screenshot -> {shot}")

            if "accounts.google.com" in current_url:
                print("  [!] Redirigido a login - el perfil no tiene sesion activa.")
                return 2

            print("  [OK] Sesion activa en el MCC.")
    except ChromeNotReachableError as e:
        print(f"  [ERROR] {e}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
