"""Repository-relative paths. Nothing here depends on Google Drive or Colab."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INFORM_DIR = RAW / "inform"
NATURAL_EARTH_DIR = RAW / "natural_earth"
ERA5LAND_DIR = RAW / "era5land"
EMDAT_DIR = RAW / "emdat"                      # restricted: never committed (see data/README.md)
EXTERNAL = DATA / "external"
GEOBOUNDARIES_DIR = EXTERNAL / "geoboundaries"
PROCESSED = DATA / "processed"
REGIONS_DIR = PROCESSED / "regions"
DROUGHT_DIR = PROCESSED / "drought"
EMDAT_DERIVED_DIR = PROCESSED / "emdat"        # restricted: never committed
INDEX_DIR = PROCESSED / "index"
BASELINE_DIR = ROOT / "baseline" / "v1.0_notebook"
DOCS = ROOT / "docs"
OUTPUTS = DOCS   # served at laketalkemp.github.io/ML-Enabled-Displacement-Prediction/<file>.html (URLs unchanged from v1.0)

# The eight World Bank Data360 extracts used by the index, in the order the original notebook read them.
INFORM_FILES = [
    "IMF_CDIR_ECFRMC.csv",   # Climate-driven INFORM: lack of coping capacity (IMF, 2013-2022)
    "IMF_CDIR_ECFRMH.csv",   # Climate-driven INFORM: hazard & exposure
    "IMF_CDIR_ECFRMR.csv",   # Climate-driven INFORM: risk
    "IMF_CDIR_ECFRMV.csv",   # Climate-driven INFORM: vulnerability
    "INFORM_CC.csv",         # INFORM Risk (JRC DRMKC): lack of coping capacity (2016-2025)
    "INFORM_HA.csv",         # INFORM Risk: hazard & exposure
    "INFORM_OVRL.csv",       # INFORM Risk: overall risk
    "INFORM_VU.csv",         # INFORM Risk: vulnerability
]
