"""Extractor GA4 — property 279239939 'Seguros SURA - Sitio web'.

TODO (Paso 2.4):
- Listar eventos de conversión y proponer mapeo evento→seguro antes de extraer.
- Por seguro: usuarios, sesiones, tasa conversión por canal, volumen de evento,
  utm_source/utm_campaign, rutas de conversión, top landing pages.
"""
from src.config import GA4_PROPERTY_ID, GA4_PROPERTY_NAME


def run() -> None:
    print(f"[ga4] property={GA4_PROPERTY_ID} ({GA4_PROPERTY_NAME}) — Paso 2.4 pendiente.")


if __name__ == "__main__":
    run()
