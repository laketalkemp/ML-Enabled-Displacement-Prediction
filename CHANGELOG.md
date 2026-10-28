# Changelog

## v1.1.0 (October 28, 2026)

**Restructure**
- Notebook pipeline moved into a package (`src/hvd/`) and scripts (`scripts/`).
- Repository-relative paths replace the Google Drive mounts.
- Pinned environment (`requirements.txt`, `environment.yml`).
- `--legacy` mode reproduces v1.0 exactly, and regression tests guard this (`tests/`).

**Index fixes**
- **One row per country.** The merge is keyed on ISO3 codes, not country names. Five countries spelled differently in the two sources had been split into two half-imputed rows each: Côte d'Ivoire, São Tomé and Príncipe, Somalia, Türkiye and Viet Nam. The table goes from 196 rows to 191 countries.
  - Somalia moves from 75.9 and 73.0 to 100, the top of the scale.
  - Türkiye no longer sits in two tiers at once.
- **Imputation flag.** `imputed`, `n_imputed` and `imputed_indicators` are recorded per country. Cuba, Liechtenstein and North Korea have no IMF values, so 4 of their 8 indicators are imputed.
- **PCA sign fixed.** Higher always means more vulnerable. In v1.0 this held only by chance.
- **Tier stability.** Bootstrap stability is now reported per country, plus a silhouette score and diagnostics.
- **Feature-set options** for Workshop 1 (`--feature-set inform4|inform3`), because the IMF and JRC files carry overlapping versions of the same INFORM components.

**Dashboard outputs (`docs/`, served by GitHub Pages from `/docs`; the web addresses are unchanged)**
- **Maps join on ISO3 codes** against Natural Earth geometry, not country names. All 191 scored countries now match.
- **Territories without an INFORM score** are shown in grey and labelled "No INFORM score". v1.0 filled some of them by copying a sovereign or neighbour's value (Puerto Rico from the United States, Northern Cyprus from Cyprus).
- **The temporal slider covers 2016–2022,** the years both sources report. Before 2016 and after 2022 every row was missing half its indicators.
- **Plotly loads from its CDN,** shrinking each output from about 4.5 MB to 1.1 MB or less.

**New layers from Week 1**
- Province and district layers for the Philippines (82), Afghanistan (34) and Bangladesh (64).
- ERA5-Land SPI/SPEI drought indices, with the fix for the Sep 2022 – Feb 2024 data error.
- EM-DAT province assignment script (data stays local).

## v1.0.0 (October 2026)

- Colab notebook: merge of eight INFORM / climate-driven INFORM indicators, mean imputation, PCA score (0–100), K-means tiers, t-SNE, folium and plotly dashboard outputs.
