"""Configuración central — mapeos confirmados de SURA Tech Colombia."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
OUTPUTS_DIR = ROOT / "outputs"
DOCS_DATA = ROOT / "docs" / "assets" / "data.json"

SEGUROS = [
    "Arrendamiento",
    "Salud para Dos",
    "Motos",
    "Autos",
    "Salud Animal",
    "Viajes",
]

GOOGLE_ADS_MCC_ID = "383-039-2811"
GOOGLE_ADS_ACCOUNTS = {
    "Arrendamiento":  "Arrendamiento Digital - SURATECH",
    "Salud para Dos": "Salud para dos - SURATECH",
    "Motos":          "Motos - SURATECH",
    "Autos":          "Autos - SURATECH",
    "Salud Animal":   "Salud Animal - SURATECH",
    "Viajes":         "Viajes - SURATECH",
}

CAMPAIGN_TOKEN_BY_SEGURO = {
    "Arrendamiento":  "ARRIENDO",
    "Salud para Dos": "SALUDPARADOS",
    "Motos":          "MOTOS",
    "Autos":          "AUTOS",
    "Salud Animal":   "SALUD_MASCOTAS",
    "Viajes":         "VIAJES",
}
CAMPAIGN_TYPES = ["SEARCH_SEGMENT", "SEARCH_RETENTION", "SEARCH_CONQUEST", "PMAX"]

META_BUSINESS_MANAGER_ID = "549601551075021"
META_ACCOUNT_NAME = "SURATECH - CDD - COL"

SHEETS_CRM_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1a4rI2X3fW9JD-cZZDYD1umTRpAmL5ZZjtPpGjYkAyRw/edit"
)
SHEETS_CRM_TAB = "Resumen mensual"

GA4_PROPERTY_ID = "279239939"
GA4_ACCOUNT = "1. COLOMBIA SEGUROS"
GA4_PROPERTY_NAME = "Seguros SURA - Sitio web"

SEMAFORO = {
    "verde":    {"min": 0.90, "color": "#10B981", "label": "En objetivo"},
    "amarillo": {"min": 0.60, "color": "#F59E0B", "label": "En riesgo"},
    "rojo":     {"min": 0.00, "color": "#DC2626", "label": "Crítico"},
}

BRAND = {
    "azul":       "#00359C",
    "aqua":       "#00AEC7",
    "azul_vivo":  "#2D6DF6",
    "blanco":     "#FFFFFF",
    "gris_oscuro":"#1A1A1A",
    "gris_medio": "#6B7280",
    "gris_claro": "#F3F4F6",
}
