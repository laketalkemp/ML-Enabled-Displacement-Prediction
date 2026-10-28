# ML-Enabled-Displacement-Prediction

Composite climate-vulnerability index, subnational hazard layers and displacement validation for the **Extreme Weather and Environmental Displacement and Health** project (Strategic Convene and Influence Award). LaKeta Kemp, Halıcıoğlu Data Science Institute, UC San Diego.

**Dashboard:** https://laketalkemp.github.io/ML-Enabled-Displacement-Prediction/

## What is here

| Component | Status | Where |
|---|---|---|
| Country vulnerability index (INFORM + climate-driven INFORM, PCA score, 4 tiers) | v1.1: one row per ISO3, imputation flags, tier stability | `src/hvd/`, `scripts/run_index.py` |
| Reproduction of the original notebook (v1.0) | Exact (tested) | `scripts/run_index.py --legacy`, `tests/` |
| Dashboard (GitHub Pages) | Regenerated on ISO3 keys | `docs/` |
| Province layers, proof-of-concept regions | Philippines (82), Afghanistan (34), Bangladesh (64) | `data/processed/regions/`, `data/external/` |
| Observed drought layer (ERA5-Land SPI/SPEI, 1991–2025) | Done | `data/processed/drought/`, `scripts/drought_indices.py` |
| EM-DAT events by province | Script only (data is restricted) | `scripts/emdat_province_counts.py` |
| Hazard signatures, spatial statistics, validation | Planned (Dec–Jan) | |

## Quick start

```bash
git clone https://github.com/laketalkemp/ML-Enabled-Displacement-Prediction.git
cd ML-Enabled-Displacement-Prediction
python -m venv .venv && source .venv/bin/activate      # or: conda env create -f environment.yml
python -m pip install -r requirements.txt && python -m pip install -e .

python scripts/run_index.py            # index v1.1 + dashboard outputs (about 15 s)
python scripts/run_index.py --legacy   # reproduce the v1.0 notebook table
pytest -q                              # 9 tests, including the v1.0 reproduction
```

The steps that need restricted or large data are documented in `data/README.md`:
- `scripts/fetch_natural_earth.py`
- `scripts/download_era5land.py` and `scripts/download_era5land_tp_fix.py` (CDS API key)
- `scripts/drought_indices.py`
- `scripts/emdat_province_counts.py` (your own EM-DAT export)
- `scripts/build_poc_regions.py`

## Layout

```
src/hvd/          inform.py (load/merge), index.py (score, tiers), longitudinal.py, viz.py, paths.py
scripts/          run_index.py and the data-preparation scripts above
data/             raw/, external/, processed/ — see data/README.md for sources, licences, checksums
baseline/         v1.0 notebook outputs used by the regression tests
notebooks/        archived original Colab notebook (outputs stripped)
reports/          data dictionary, Week 1 findings, region screening, EM-DAT profile, drought layer
docs/             GitHub Pages site (index.html, PrelimCaseStudy.html, the four interactive outputs, assets/)
tests/            pytest suite
```

## Repository history

- **September 2026 (v1.0):** this repository served the Colab notebook's interactive outputs and `PrelimCaseStudy.html` from its root.
- **October 2026 (v1.1):** the pipeline moved into the repository.
  - The v1.0 outputs are archived in `baseline/v1.0_notebook/html/`.
  - GitHub Pages now serves `docs/`, under the same file names, so existing links still work.
  - `unhcr_vulnerability_clusters.png` stays at the root because the portfolio page embeds it from there. `scripts/run_index.py` regenerates it.

## Data use

- **EM-DAT records and GADM boundaries are never committed;** their licences forbid redistribution.
- **EM-DAT on the public dashboard:** only country × year aggregates appear, until CRED confirms that finer aggregates are allowed.
- **Attribution:** other data keeps its source licence and requires attribution. See `data/README.md`.

Code is MIT-licensed (`LICENSE`). Please cite the repository using `CITATION.cff`, and cite the data sources.

## Methods notes and caveats

- **The two sources overlap and differ in year.** The IMF and JRC indicators overlap (r = 0.90–0.94 for vulnerability, coping capacity and risk) and come from different years (2022 vs 2025). Which indicator set to use is open for Workshop 1. See `reports/data_dictionary.md`.
- **Tiers are ordinal but not crisp.** They are K-means clusters on the score, numbered by centroid. Mean bootstrap stability is 0.93, and 17 countries sit near tier boundaries (stability < 0.80).
- **Subnational results combine scales.** They pair subnational hazard exposure with national vulnerability and should be labelled that way.
