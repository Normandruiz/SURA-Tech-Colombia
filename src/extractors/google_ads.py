"""Extractor Google Ads — MCC SURATECH COLOMBIA (383-039-2811).

TODO (Paso 2.1):
- Iterar 6 cuentas hijas (ver config.GOOGLE_ADS_ACCOUNTS)
- Por cada cuenta:
    * totales de cuenta (mes actual + mes anterior)
    * campañas: nombre, tipo, presupuesto, estado, optimización, impresiones,
      interacciones, tasa, coste, cuota impr., cuota perdida por presupuesto,
      cuota perdida por ranking, estrategia
    * eventos de conversión: estado + asignación
    * flags: rechazados, limitada por presupuesto, grupos de recursos PMax
- Guardar crudos en raw/<seguro>/google_ads_<YYYYMMDD>.json
"""
from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime

from src.config import GOOGLE_ADS_MCC_ID, GOOGLE_ADS_ACCOUNTS, RAW_DIR


def run() -> None:
    today = datetime.now().strftime("%Y%m%d")
    RAW_DIR.mkdir(exist_ok=True)
    print(f"[google_ads] MCC={GOOGLE_ADS_MCC_ID} — placeholder. Paso 2.1 pendiente.")
    for seguro, cuenta in GOOGLE_ADS_ACCOUNTS.items():
        print(f"  - {seguro}: {cuenta}")


if __name__ == "__main__":
    run()
