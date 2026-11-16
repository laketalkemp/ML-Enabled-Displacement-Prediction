# Changelog

## v1.3.0 (November 16, 2026)

**Country crosswalk** (`src/hvd/crosswalk.py`, `scripts/build_country_crosswalk.py`, `tests/test_crosswalk.py`)
- One key per place: Natural Earth's `ISO_A3_EH`, or `ADM0_A3` where it is −99 (Somaliland, Kosovo, Northern Cyprus, Siachen Glacier). 242 keys.
- Display names: UN short names in natural word order for UN members and observers (Republic of Yemen, Islamic Republic of Iran, State of Palestine); UN statistical names for other places (for example Taiwan Province of China, Hong Kong SAR (China), Kosovo (UNSCR 1244)); Somaliland (Somalia) and Northern Cyprus (Cyprus). 243 keys.
- Every country code in EM-DAT, IDMC and the WDI export has a logged decision (`data/processed/crosswalk/country_aliases.csv`, `reports/country_crosswalk.md`); the build fails on a code without one.
- EM-DAT and IDMC: the Canary Islands, the Azores, France's overseas departments and Svalbard now count with their country; EM-DAT's "Serbia Montenegro" (2000–2006) goes to Montenegro when a record names only Montenegro, otherwise to Serbia; IDMC's the Abyei Area is its own place, attributed to neither Sudan nor South Sudan; XKX is Kosovo.
- Somaliland takes Somalia's score on the map (`data_parent`).

**Map and dashboard** (`src/hvd/viz.py`, `reports/disputed_areas.md`)
- Natural Earth's breakaway and disputed areas are hatched, with neutral names and no sovereignty attributes; a UN-style disclaimer sits under the map. Nagorno-Karabakh is left out (dissolved January 1, 2024).
- The Abyei Area is cut out of Sudan and drawn on its own, gray and hatched.
- The map, the year slider, the top-10 race and the indicator chart show the crosswalk's display names.
- `displacement_tiers.html`: Low-level median 21.1 per 100,000, Severe vs Low 15.9×, 28 countries at the Severe level.
- `imf4` indicator set (the four IMF indicators) for the two-lens comparison.
- December analyses run early: `scripts/stats_cordex_archetypes.py`, `scripts/stats_events.py` (CORDEX outputs only are shareable).

**Effect on the statistics (rerun Nov 16)**
- Median weather displacement at the Low vulnerability level: 19 → 21 per 100,000 a year (France's overseas departments now count with France), so the Severe-to-Low ratio is 16×, not 17×. The Severe median (336) and the per-10-point estimates (×1.34; +28% given any displacement) are unchanged.
- Moran's I for people affected per head: 0.406 → 0.404 (reported as 0.40, not 0.41). Bivariate I (0.36), the 28 high-high countries and their 16-country overlap with the Severe level are unchanged.
- Hazard archetypes: 173 countries, not 176 (separately listed regions merged): 60 flood-led, 61 storm-led and 52 mixed; Cramér's V with the vulnerability levels 0.47 (was 0.48); bootstrap stability 0.71 (was 0.69).
- Deaths per fatal event across all climate hazards: +35% per 10 points (was +36%; 1.356 → 1.355, CI 17–57% unchanged). Storms (+48%) and floods (+29%) and the medians by vulnerability level are unchanged.
- Trends: high-impact storm records +18% a decade (was +17%); all-record trends unchanged (storms +12%, heat +16%). The extreme-temperature trend now needs a restart of the negative binomial fit, because its dispersion sits at zero (`stats/country.py`); q = 0.03 (was 0.02).
- Co-occurrence of extreme temperature and wildfire: 1.23× (was 1.24×); storm-led archetype 52% storms (was 53%).

## v1.2.0 (November 2026)

**Statistics** (`src/hvd/stats/`, `scripts/stats_*.py`, `tests/test_stats.py`)
- Hazard trends (negative binomial with a country fixed effect, high-impact refit), same-year co-occurrence with permutation tests, seasonality (Rayleigh test).
- Vulnerability against disaster impacts with a two-part model on a vulnerability and coping-capacity-gap sub-index (`vc4`), so hazard exposure is a control rather than part of the score.
- IDMC displacement validation (country means, two-part and Poisson models, out-of-sample years) and IDMC displacement placed in provinces; province wealth from the Relative Wealth Index (Philippines and Bangladesh).
- Spatial statistics: Moran's I, LISA, Getis-Ord Gi* and bivariate LISA, with permutation inference and FDR control; hazard archetypes for countries and provinces.
- CORDEX: download script, model evaluation against ERA5-Land, projected change for 2026–2045, 2041–2070 and 2071–2099 under RCP2.6 and RCP8.5 (SPI/SPEI-6, CDD, Rx5day, R95p, hot days, warming), run agreement, a bias-screened sensitivity and hot spots. Outputs in `data/processed/cordex/`.
- New dependencies: statsmodels, esda, libpysal, rasterio.

**Data use**
- Every output derived from EM-DAT stays in the ignored `data/processed/emdat/`. IDMC, WorldPop, WDI and Relative Wealth Index downloads are documented in `data/README.md` and not committed.

## v1.1.2 (November 2, 2026)

**Wording**
- "Vulnerability level" replaces "tier" on the dashboard page, in the map hover text (now "Severe vulnerability level" and "Same level in 80% of refits"), in the t-SNE figure, in `PrelimCaseStudy.html`, the README and the data dictionary. "Tier" read as a ranking of nations; the levels are meant to make each country's situation visible. The four names and score cut-offs are unchanged.
- Data files keep the column names `tier`, `tier_label` and `tier_stability`, so existing code still runs.

## v1.1.0 (October 28, 2026)

**Restructure**
- Notebook pipeline moved into a package (`src/hvd/`) and scripts (`scripts/`).
- Repository-relative paths replace the Google Drive mounts.
- Pinned environment (`requirements.txt`, `environment.yml`).
- `--legacy` mode reproduces v1.0 exactly, and regression tests guard this (`tests/`).

**Index fixes**
- **One row per country.** The merge is keyed on ISO3 codes, not country names. Five countries spelled differently in the two sources had been split into two half-imputed rows each: Côte d'Ivoire, São Tomé and Príncipe, Somalia, Türkiye and Viet Nam. The table goes from 196 rows to 191 countries.
  - Somalia moves from 75.9 and 73.0 to 100, the top of the scale.
  - Türkiye no longer sits at two vulnerability levels at once.
- **Imputation flag.** `imputed`, `n_imputed` and `imputed_indicators` are recorded per country. Cuba, Liechtenstein and North Korea have no IMF values, so 4 of their 8 indicators are imputed.
- **PCA sign fixed.** Higher always means more vulnerable. In v1.0 this held only by chance.
- **Stability of the vulnerability levels.** Bootstrap stability is now reported per country, plus a silhouette score and diagnostics.
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

- Colab notebook: merge of eight INFORM / climate-driven INFORM indicators, mean imputation, PCA score (0–100), K-means vulnerability levels (called tiers in v1.0), t-SNE, folium and plotly dashboard outputs.
