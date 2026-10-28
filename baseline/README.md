# Baseline: v1.0 notebook outputs

These are the outputs of the original Colab notebook (`notebooks/00_original_colab_notebook_v1.0.ipynb`), saved October 2026. They are the reference for the regression tests.

| File | Rows | Contents |
|---|---|---|
| `v1.0_notebook/merged_raw_inform_data.csv` | 196 | Merged latest-year values of the eight indicators |
| `v1.0_notebook/processed_vulnerability_tiers.csv` | 196 | The above, plus PCA score, cluster ID, tier and t-SNE coordinates |

The table has 196 rows because five countries appear twice (see `reports/data_dictionary.md`, "Known issues").

`python scripts/run_index.py --legacy` reproduces this table from `data/raw/inform/`:
- scores within 3e-14;
- identical tiers, cluster IDs and t-SNE coordinates.

`tests/test_index.py` checks this on every run.

The v1.0 interactive HTML outputs and cluster figure, which this repository served from its root until October 2026, are archived in `v1.0_notebook/html/`. Regenerated v1.1 versions are in `docs/`, at the same web addresses.
