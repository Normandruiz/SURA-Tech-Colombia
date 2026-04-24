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
GOOGLE_ADS_MCC_ID_NUMERIC = "3830392811"

# Auth params internos de Google Ads que "amarran" la sesion y evitan el chooser.
# Confirmados desde la URL del MCC visible en el screenshot del user (abr 2026).
# Patron equivalente al de answer-auto-dashboard/config.json.
GOOGLE_ADS_AUTH_PARAMS = {
    "ocid":     "1194015290",
    "ascid":    "1194015290",
    "euid":     "325839748",    # norman.ruiz Google user ID
    "__u":      "4137086052",   # user ID secundario
    "uscid":    "705295378",    # user+customer session id MCC
    "authuser": "0",
}

# Cuentas hijas del MCC - Customer IDs confirmados desde la UI (abr 2026).
# 'numeric' es el __c de cada cuenta cuando navegamos a su overview/campaigns.
GOOGLE_ADS_ACCOUNTS = {
    "Arrendamiento":  {"name": "Arrendamiento Digital - SURATECH", "id": "642-211-2433", "numeric": "6422112433"},
    "Salud para Dos": {"name": "Salud para dos - SURATECH",         "id": "248-508-8915", "numeric": "2485088915"},
    "Motos":          {"name": "Motos - SURATECH",                  "id": "331-988-8513", "numeric": "3319888513"},
    "Autos":          {"name": "Autos - SURATECH",                  "id": "375-790-7670", "numeric": "3757907670"},
    "Salud Animal":   {"name": "Salud Animal - SURATECH",           "id": "132-565-6703", "numeric": "1325656703"},
    "Viajes":         {"name": "Viajes - SURATECH",                 "id": "791-087-6723", "numeric": "7910876723"},
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
