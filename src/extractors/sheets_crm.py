"""Extractor Sheets — Leads CRM ('Resumen mensual').

TODO (Paso 2.3):
- Leer hoja 'Resumen mensual' de SHEETS_CRM_URL.
- Bloques mensuales: Compromiso Leads, Leads CRM, Leads GA4, Cumplimiento, CPL Negocio.
- Fila por seguro + total.
- Validar nombres exactos de seguros contra config.SEGUROS y mostrar al usuario.
"""
from src.config import SHEETS_CRM_URL, SHEETS_CRM_TAB


def run() -> None:
    print(f"[sheets] {SHEETS_CRM_URL} · hoja '{SHEETS_CRM_TAB}' — Paso 2.3 pendiente.")


if __name__ == "__main__":
    run()
