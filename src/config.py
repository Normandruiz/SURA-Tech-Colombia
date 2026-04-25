"""Configuración central — mapeos confirmados de SURA Tech Colombia."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
OUTPUTS_DIR = ROOT / "outputs"
DOCS_DATA = ROOT / "docs" / "assets" / "data.json"

# Foco MVP confirmado por el cliente (24-abr-2026):
# - SEGUROS_PRINCIPALES: cumplimiento compromiso CRM, full data (4)
# - SEGUROS_EXTRA: solo ads (Google + Meta) para identificar oportunidades de potenciar
SEGUROS_PRINCIPALES = [
    "Autos",
    "Motos",
    "Arrendamiento",
    "Viajes",
]
SEGUROS_EXTRA_ADS_ONLY = [
    "Salud para Dos",
    "Salud Animal",
]
SEGUROS = SEGUROS_PRINCIPALES + SEGUROS_EXTRA_ADS_ONLY  # los 6 totales

GOOGLE_ADS_MCC_ID = "383-039-2811"
GOOGLE_ADS_MCC_ID_NUMERIC = "3830392811"

# Auth params del USER (norman.ruiz) - sirven para cualquier cuenta del MCC.
# Estos amarran la sesion al user correcto sin pedir chooser de cuenta Google.
GOOGLE_ADS_USER_PARAMS = {
    "euid":     "325839748",    # Google user ID (effective)
    "__u":      "4137086052",   # secondary user ID
    "authuser": "0",
}

# Auth params especificos del MCC - usar SOLO al navegar al MCC, no a cuentas hijas.
# Cada cuenta hija tiene su propio uscid/ocid que no conozco hasta entrar.
GOOGLE_ADS_MCC_PARAMS = {
    **GOOGLE_ADS_USER_PARAMS,
    "ocid":  "1194015290",
    "ascid": "1194015290",
    "uscid": "705295378",
}

# Alias retrocompatible
GOOGLE_ADS_AUTH_PARAMS = GOOGLE_ADS_MCC_PARAMS

# MCC __c (queda fijo en todas las URLs - identifica el contexto MCC activo).
GOOGLE_ADS_MCC_INTERNAL_C = "8322065922"

# Cuentas hijas del MCC.
# Lo que CAMBIA por cuenta es el 'ocid' (= ascid). El __c queda en el MCC.
# OCIDs descubiertos via debug_mcc_links.py contra el MCC SURATECH (abr 2026).
GOOGLE_ADS_ACCOUNTS = {
    "Arrendamiento":  {"name": "Arrendamiento Digital - SURATECH", "id": "642-211-2433", "ocid": "1294729847"},
    "Salud para Dos": {"name": "Salud para dos - SURATECH",        "id": "248-508-8915", "ocid": "7354551308"},
    "Motos":          {"name": "Motos - SURATECH",                 "id": "331-988-8513", "ocid": "1294745033"},
    "Autos":          {"name": "Autos - SURATECH",                 "id": "375-790-7670", "ocid": "1294555918"},
    "Salud Animal":   {"name": "Salud Animal - SURATECH",          "id": "132-565-6703", "ocid": "1466566994"},
    "Viajes":         {"name": "Viajes - SURATECH",                "id": "791-087-6723", "ocid": "1294562092"},
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
