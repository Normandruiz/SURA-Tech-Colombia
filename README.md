# SURA Tech Colombia · Informe mensual

MVP de informe estratégico mensual que cruza datos de **Google Ads**, **Meta Ads**, **Leads CRM** (Google Sheets) y **GA4** para los 6 seguros de SURA Tech Colombia:

- Arrendamiento
- Salud para Dos
- Motos
- Autos
- Salud Animal
- Viajes

El entregable principal es un **dashboard web** con branding SURA publicado vía GitHub Pages, más un **informe ejecutivo** `.docx` y un Excel consolidado.

> Elaborado por **Beyond Media Agency** para SURA Tech Colombia.

---

## Dashboard público

Una vez activado GitHub Pages sobre `/docs`:

`https://normandruiz.github.io/SURA-Tech-Colombia/`

La sección más importante del dashboard es el **TOP 10 de Recomendaciones Accionables** para optimizar campañas en Google Ads y Meta en pro de cumplir los **Compromisos de Leads del CRM**.

---

## Estructura del repo

```
SURA-Tech-Colombia/
├── README.md
├── .gitignore
├── requirements.txt
├── src/
│   ├── extractors/      # Google Ads, Meta, Sheets, GA4 vía Playwright
│   ├── consolidation/   # Unificación a dataset maestro
│   ├── analysis/        # KPIs, semáforos, recomendaciones
│   └── reporting/       # Generación de .docx, .xlsx, data.json
├── docs/                # Dashboard servido por GitHub Pages
│   ├── index.html
│   ├── assets/
│   │   ├── styles.css
│   │   ├── app.js
│   │   └── data.json    # Dataset consolidado que lee el dashboard
│   └── img/
├── outputs/
│   ├── suratech_informe_ejecutivo.docx
│   └── suratech_data_consolidado.xlsx
└── raw/                 # IGNORADO en git — snapshots crudos por fuente
```

---

## Cómo correr

### Requisitos
- Python 3.11+
- Chrome instalado con sesión activa de `norman.ruiz@beyondmediaagency.com`
- Acceso a: MCC Google Ads `383-039-2811`, Meta BM `549601551075021`, Sheet de Leads CRM, GA4 property `279239939`.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
playwright install chromium
```

### Pipeline

```bash
# 1. Cerrar Chrome antes de correr
python -m src.extractors.google_ads
python -m src.extractors.meta
python -m src.extractors.sheets_crm
python -m src.extractors.ga4

# 2. Consolidar
python -m src.consolidation.build_dataset

# 3. Análisis + recomendaciones
python -m src.analysis.run_all

# 4. Reporting
python -m src.reporting.build_dashboard_json
python -m src.reporting.build_docx
python -m src.reporting.build_xlsx
```

Abrir `docs/index.html` en el navegador para ver el dashboard local.

---

## Privacidad

- `raw/` **nunca** se versiona (datos del cliente).
- Credenciales, cookies, `storage_state.json` y perfiles de Chrome están en `.gitignore`.
- El dashboard público muestra agregados y benchmarks, no datos personales.

---

## Stack

- **Extracción**: Playwright (Python) con `launchPersistentContext` al perfil de Chrome.
- **Análisis**: pandas.
- **Dashboard**: HTML + CSS + JS vanilla, Chart.js desde CDN. Sin backend.
- **Reporting**: python-docx, openpyxl.

---

## Branding

Paleta SURA aplicada en todo el proyecto:

| Color              | Hex       |
|--------------------|-----------|
| Azul Grupo SURA    | `#00359C` |
| Aqua SURA          | `#00AEC7` |
| Azul vivo          | `#2D6DF6` |
| Verde (semáforo)   | `#10B981` |
| Amarillo (semáforo)| `#F59E0B` |
| Rojo (semáforo)    | `#DC2626` |
