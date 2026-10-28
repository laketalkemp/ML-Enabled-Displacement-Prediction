# Data dictionary

Version 1.1, October 28, 2026.

## 1. The eight index inputs (`data/raw/inform/`)

All eight are World Bank Data360 extracts in SDMX layout: one row per country and year. Each file has 38–39 columns, but only four vary.
- **Kept by the pipeline:** `REF_AREA` (ISO 3166-1 alpha-3), `REF_AREA_LABEL` (country name), `TIME_PERIOD` (year) and `OBS_VALUE` (score). `INDICATOR` and `INDICATOR_LABEL` are also read; they are constant within a file and identify it.
- **Dropped (constant within each file):** the remaining metadata columns, such as `SEX`, `AGE`, `URBANISATION`, `COMP_BREAKDOWN_1–3`, `UNIT_*`, `OBS_STATUS` (all "A", normal value), `OBS_CONF` (all "PU", public) and their `*_LABEL` twins. They carry no information for the index.
- **Scale and quality:** all scores run 0–10, with higher meaning more risk. There are no missing `OBS_VALUE` entries in any file.

| File | Short name in code | Indicator (`INDICATOR_LABEL`) | Database | Countries | Years | Latest year used |
|---|---|---|---|---|---|---|
| `IMF_CDIR_ECFRMC.csv` | `cdi_lack_coping_capacity` | Index for Risk Management; Lack of Coping Capacity | Climate-driven INFORM Risk (IMF) | 188 | 2013–2022 | 2022 |
| `IMF_CDIR_ECFRMH.csv` | `cdi_hazard_exposure` | Climate-Driven Hazard & Exposure | Climate-driven INFORM Risk (IMF) | 188 | 2013–2022 | 2022 |
| `IMF_CDIR_ECFRMR.csv` | `cdi_risk` | Climate-Driven Inform Risk Indicator | Climate-driven INFORM Risk (IMF) | 188 | 2013–2022 | 2022 |
| `IMF_CDIR_ECFRMV.csv` | `cdi_vulnerability` | Index for Risk Management; Vulnerability | Climate-driven INFORM Risk (IMF) | 188 | 2013–2022 | 2022 |
| `INFORM_CC.csv` | `inform_lack_coping_capacity` | Index for Risk Management: Lack of coping capacity index | INFORM Risk Index (JRC DRMKC) | 191 | 2016–2025 | 2025 |
| `INFORM_HA.csv` | `inform_hazard_exposure` | Index for Risk Management: Hazard and exposure index | INFORM Risk Index (JRC DRMKC) | 191 | 2016–2025 | 2025 |
| `INFORM_OVRL.csv` | `inform_risk` | Index for Risk Management (INFORM Risk) | INFORM Risk Index (JRC DRMKC) | 191 | 2016–2025 | 2025 |
| `INFORM_VU.csv` | `inform_vulnerability` | Index for Risk Management: Vulnerability index | INFORM Risk Index (JRC DRMKC) | 191 | 2016–2025 | 2025 |

The JRC files have no country missing from the IMF files. Three countries appear only in the JRC files: Cuba, Liechtenstein and North Korea.

### Known issues found in Week 2

1. **Country names differ between the two sources for five countries, which split each into two rows in the original notebook.**
   - The affected countries:

     | ISO3 | Spellings |
     |---|---|
     | CIV | Cote d'Ivoire / Côte d'Ivoire |
     | STP | Sao Tome and Principe / São Tomé and Príncipe |
     | SOM | Somalia / Somalia, Federal Republic of |
     | TUR | Turkiye / Türkiye |
     | VNM | Viet Nam / Vietnam |
   - The notebook merged on code *and* name. Each country therefore became two half-empty rows, each filled with column means.
   - Türkiye ended up in two different tiers (Mild and Moderate). Somalia scored 75.9 and 73.0, when its full data put it at the top of the scale.
   - **v1.1 merges on the ISO3 code only, giving 191 countries.**
2. **The two sources come from different years.** The latest IMF values are from 2022 and the latest JRC values from 2025, and the index combines them. The `*_year` columns in the output record this.
3. **The two sources overlap.** Correlations between matching indicators, latest year:

   | Pair | Pearson r |
   |---|---|
   | Lack of coping capacity: IMF vs JRC | 0.93 |
   | Vulnerability: IMF vs JRC | 0.94 |
   | Risk: IMF vs JRC | 0.90 |
   | Hazard & exposure: IMF (climate-driven) vs JRC (all hazards) | 0.63 |

   `inform_risk` is itself built from hazard (r = 0.85), vulnerability (0.92) and coping capacity (0.84). Using all eight indicators therefore counts vulnerability and coping capacity about twice.
   - The pipeline keeps all eight by default, for comparability with v1.0.
   - `--feature-set inform4` (JRC only) and `--feature-set inform3` (JRC hazard, vulnerability and coping capacity, no composite) are sensitivity options. Each moves 27–28 of 191 countries by one tier (score correlation 0.98).
   - **Which set to use is a Workshop 1 decision.**
4. **Imputation.** After the ISO3 fix, three countries are missing all four IMF indicators: Cuba, Liechtenstein and North Korea. They are mean-imputed and flagged (`imputed`, `n_imputed`, `imputed_indicators`).

## 2. Index output (`data/processed/index/vulnerability_index_v1.1.csv`)

| Column | Type | Description |
|---|---|---|
| `iso3` | str | ISO 3166-1 alpha-3 code (join key everywhere) |
| `country` | str | Display name (INFORM spelling; "Somalia" overridden) |
| `cdi_*`, `inform_*` | float | The eight indicator scores (0–10), latest year available |
| `*_year` | int | Year of each value |
| `n_imputed` | int | Number of the eight indicators that were imputed (0 or 4) |
| `imputed` | bool | True if any indicator was imputed |
| `imputed_indicators` | str | Semicolon-separated list of imputed indicators |
| `vulnerability_score` | float | PC1 of the standardised indicators, rescaled to 0–100. The sign is fixed so that higher means more vulnerable |
| `tier` | int | 1–4 from K-means (k = 4) on the score, numbered by cluster centroid, so tiers are ordinal |
| `tier_label` | str | "1 - Low" … "4 - Severe Vulnerability" (labels unchanged from v1.0, pending Week 3 wording review) |
| `tier_stability` | float | Share of 500 bootstrap refits that put the country in the same tier |
| `tsne_1`, `tsne_2` | float | 2-D t-SNE coordinates (perplexity 30, seed 42), for display only |

`diagnostics_v1.1.json` reports the explained variance, PC1 loadings, tier centroids and counts, the silhouette score and bootstrap stability.

For v1.1 (all eight indicators):
- PC1 explains 74.4% of the variance.
- The silhouette score is 0.56.
- Mean tier stability is 0.93, and 17 countries fall below 0.80 (`countries_below_80pct_stability` in the diagnostics).

`vulnerability_index_longitudinal_2016_2022.csv` has one row per country and year for 2016–2022, the years both sources cover. Scores come from one PCA fitted on all country-years, so values are comparable across years.

## 3. Province layers (`data/processed/regions/`)

See `reports/poc_regions.md`.
- `poc_provinces.gpkg` has two layers: `phl_provinces` (82) and `afg_provinces` (34). The key is `unit_id`, the ISO 3166-2 code (Metro Manila is `PH-00`).
- The crosswalks list aliases, Natural Earth codes, geoBoundaries IDs and overlap shares.
- Bangladesh districts (64) come from `data/external/geoboundaries/geoBoundaries-BGD-ADM2_simplified.geojson`. The key is the district name.

## 4. Drought indices (`data/processed/drought/`)

See `reports/era5land_drought_layer.md`. The files are `{phl,afg,bgd}_monthly_drought_indices_1991_2025.csv`, `*_drought_annual_2000_2025.csv` and `*_drought_summary_2000_2025.csv`.

| Column | Description |
|---|---|
| `unit_id` | Province or district key, matching the EM-DAT tables. The Philippines has 81 units, with Davao Occidental folded into Davao del Sur |
| `precip_mm`, `t2m_c`, `pet_mm` | Monthly precipitation, 2 m temperature, and Thornthwaite potential evaporation |
| `spi3`, `spi6`, `spi12` | Standardised Precipitation Index over 3, 6 and 12 months (gamma, calibrated 1991–2020) |
| `spei6`, `spei12` | Standardised Precipitation-Evapotranspiration Index (Pearson III, calibrated 1991–2020) |
| `drought_months_spi6` | Months with SPI-6 ≤ −1.0 |
| `severe_months_spi6` | Months with SPI-6 ≤ −1.5 |
| `drought_events_spi6` | Runs of 3 or more consecutive months with SPI-6 ≤ −1.0 |
| `longest_event_months`, `worst_event_severity` | Longest run, and the most negative sum of SPI-6 over a run |
| `nearest_cell_fallback` | True when the unit has no ERA5-Land land cell and took the nearest one (Batanes) |
