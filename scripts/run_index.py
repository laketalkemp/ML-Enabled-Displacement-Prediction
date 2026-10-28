"""Build the composite vulnerability index (v1.1) and the dashboard outputs.

    python scripts/run_index.py                 # v1.1, all eight indicators
    python scripts/run_index.py --feature-set inform4
    python scripts/run_index.py --legacy        # reproduce the October 2026 notebook output

Writes data/processed/index/ (tables + diagnostics) and docs/ (HTML for GitHub Pages).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hvd import index, inform, longitudinal, paths, viz  # noqa: E402

LABELS = {
    "cdi_lack_coping_capacity": "Climate-driven INFORM: lack of coping capacity",
    "cdi_hazard_exposure": "Climate-driven INFORM: hazard & exposure",
    "cdi_risk": "Climate-driven INFORM: risk",
    "cdi_vulnerability": "Climate-driven INFORM: vulnerability",
    "inform_lack_coping_capacity": "INFORM: lack of coping capacity",
    "inform_hazard_exposure": "INFORM: hazard & exposure",
    "inform_risk": "INFORM: risk",
    "inform_vulnerability": "INFORM: vulnerability",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-set", default="all8", choices=list(index.FEATURE_SETS))
    ap.add_argument("--impute", default="mean", choices=["mean", "median"])
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--legacy", action="store_true", help="reproduce the notebook (v1.0) table only")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    paths.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if a.legacy:
        out = paths.INDEX_DIR / "vulnerability_index_v1.0_legacy.csv"
        index.build_index_legacy().to_csv(out, index=False)
        print("wrote", out)
        return

    df, diag = index.build_index(a.feature_set, a.impute, a.bootstrap)
    suffix = "" if a.feature_set == "all8" and a.impute == "mean" else f"_{a.feature_set}_{a.impute}"
    df.to_csv(paths.INDEX_DIR / f"vulnerability_index_v1.1{suffix}.csv", index=False)
    diag["label_variants_merged"] = inform.label_variants().assign(labels=lambda d: d["labels"].str.join(" | ")).to_dict("records")
    (paths.INDEX_DIR / f"diagnostics_v1.1{suffix}.json").write_text(json.dumps(diag, indent=2, ensure_ascii=False))
    print(json.dumps({k: diag[k] for k in ("n_countries", "n_imputed_countries", "tier_counts",
                                           "silhouette_tiers_on_score", "mean_tier_stability")}, indent=1))

    if a.no_figures or suffix:
        return
    paths.OUTPUTS.mkdir(parents=True, exist_ok=True)
    m = viz.vulnerability_map(df, paths.OUTPUTS / "vulnerability_map.html")
    long = longitudinal.longitudinal_scores(overlap_only=True)
    long.to_csv(paths.INDEX_DIR / "vulnerability_index_longitudinal_2016_2022.csv", index=False)
    viz.temporal_slider(long, paths.OUTPUTS / "temporal_vulnerability_slider.html")
    viz.top10_race(long, paths.OUTPUTS / "top_10_inform_risk.html")
    viz.comparative_metrics(df, LABELS, paths.OUTPUTS / "comparative_risk_metrics.html")
    viz.tsne_png(df, paths.DOCS / "assets" / "vulnerability_tiers_tsne.png")
    # compatibility copy: the portfolio page embeds this image from the repository root by its v1.0 name
    shutil.copyfile(paths.DOCS / "assets" / "vulnerability_tiers_tsne.png", paths.ROOT / "unhcr_vulnerability_clusters.png")
    print("map:", m, "| figures written to", paths.OUTPUTS)


if __name__ == "__main__":
    main()
