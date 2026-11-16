"""Build the country crosswalk and its decision log.

    python scripts/build_country_crosswalk.py

Inputs: Natural Earth 1:50m admin-0 (committed), the index (committed), and, when present, the EM-DAT, IDMC and WDI
exports in data/raw/ (not committed). Without them, the source codes are read back from the committed alias table,
so the crosswalk rebuilds on a fresh clone.

Outputs (committed; country codes and names only, no records):
- data/processed/crosswalk/country_crosswalk.csv: one row per key, with the display name, status, data coverage
  and Natural Earth units;
- data/processed/crosswalk/country_aliases.csv: every country code each source uses, and what it maps to;
- reports/country_crosswalk.md: the rules and every decision.
Fails if any source code has no decision.
"""
import glob
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from hvd import crosswalk as X, paths  # noqa: E402

X.CROSSWALK_DIR.mkdir(parents=True, exist_ok=True)
REPORT = ROOT / "reports" / "country_crosswalk.md"

# ------------------------------------------------------------------ Natural Earth units, grouped by key ----
ne = gpd.read_file(f"zip://{paths.NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
ne["iso3"] = ne.ISO_A3_EH.where(ne.ISO_A3_EH != "-99", ne.ADM0_A3)
ne["fallback"] = ne.ISO_A3_EH == "-99"
ne["primary"] = ne.ADM0_A3.eq(ne.iso3) | ne.groupby("iso3").ADM0_A3.transform("size").eq(1)
g = ne.sort_values("primary", ascending=False).groupby("iso3")
units = pd.DataFrame({
    "ne_units": g.ADM0_A3.agg(lambda s: ";".join(sorted(s))),
    "ne_name": g.NAME_LONG.first(),
    "ne_type": g.TYPE.first(),
    "ne_sovereign": g.SOVEREIGNT.first(),
    "key_from_adm0_a3": g.fallback.any(),
})

# ------------------------------------------------------------------ index coverage ----
idx = pd.read_csv(paths.INDEX_DIR / "vulnerability_index_v1.1.csv").set_index("iso3")
inform_name = idx["country"]
imf_missing = idx.imputed_indicators.fillna("").str.contains("cdi_")

# ------------------------------------------------------------------ source codes ----
def observed():
    """(source, code, source_name) for every country code used by EM-DAT (2000-2025), IDMC and WDI."""
    rows = []
    em = sorted(glob.glob(str(paths.EMDAT_DIR / "emdat_public_*.xlsx")))
    if em:
        e = pd.read_excel(em[-1], sheet_name="EM-DAT Data", usecols=["ISO", "Country", "Start Year"])
        e = e[e["Start Year"].between(2000, 2025)].drop_duplicates(["ISO", "Country"])
        rows += [("emdat", c, n) for c, n in zip(e.ISO, e.Country)]
    idmc = sorted(glob.glob(str(paths.RAW / "idmc" / "*.xlsx")))
    if idmc:
        d = pd.concat([pd.read_excel(f, usecols=["ISO3", "Country"]) for f in idmc]).drop_duplicates()
        rows += [("idmc", c, n) for c, n in zip(d.ISO3, d.Country)]
    wdi = sorted(glob.glob(str(paths.RAW / "wdi" / "*_Data.csv")))
    if wdi:
        w = pd.read_csv(wdi[-1], usecols=["Country Name", "Country Code"]).dropna().drop_duplicates()
        rows += [("wdi", c, n) for c, n in zip(w["Country Code"], w["Country Name"])]
    have = {r[0] for r in rows}
    if X.ALIASES_CSV.exists():   # sources whose raw files are absent: reuse the committed list
        old = pd.read_csv(X.ALIASES_CSV, keep_default_na=False)
        old = old[~old.source.isin(have)]
        rows += list(old[["source", "code", "source_name"]].itertuples(index=False, name=None))
    return pd.DataFrame(rows, columns=["source", "code", "source_name"]).drop_duplicates(["source", "code"])


obs = observed()
al = X._alias_table().set_index(["source", "code"])
keys = set(units.index) | set(X.OTHER_NAMES) | set(X.PREFERRED)
rows, unresolved = [], []
for s, c, n in obs.itertuples(index=False):
    if (s, c) in al.index:
        a = al.loc[(s, c)]
        rows.append((s, c, n, a.key, a.action, a.reason))
    elif s == "wdi" and c in X.wdi_aggregates():
        rows.append((s, c, n, "", "exclude", "World Bank regional or income-group aggregate."))
    elif c in keys:
        rows.append((s, c, n, c, "key", ""))
    else:
        unresolved.append((s, c, n))
if unresolved:
    raise SystemExit(f"Source codes with no decision: {unresolved}")
aliases = pd.DataFrame(rows, columns=["source", "code", "source_name", "key", "action", "reason"]).sort_values(["source", "code"])
aliases.to_csv(X.ALIASES_CSV, index=False)

# ------------------------------------------------------------------ one row per key ----
def name_in(source):
    a = aliases[(aliases.source == source) & aliases.action.isin(["key", "same_place"])]
    return a.drop_duplicates("key").set_index("key").source_name


all_keys = sorted(set(units.index) | {k for k in aliases.key.str.split("|").explode() if k})
cw = pd.DataFrame(index=pd.Index(all_keys, name="iso3")).join(units)


def status(k):
    if k in X.UN_MEMBERS:
        return "UN member state"
    if k in X.UN_OBSERVERS:
        return "UN observer state"
    if k == "ATA":
        return "Antarctica"
    if k in {"KOS", "TWN", "SOL", "CYN", "ESH", "KAS", "AB9"}:
        return "Other place, not a UN member state"
    return "Territory"


cw["status"] = [status(k) for k in cw.index]
name = pd.Series(X.PREFERRED).combine_first(pd.Series(X.OTHER_NAMES))
cw["display_name"] = name.reindex(cw.index).fillna(inform_name.reindex(cw.index).str.replace("’", "'"))
missing = cw.index[cw.display_name.isna()].tolist()
if missing:
    raise SystemExit(f"Keys with no display name: {missing}")
dups = cw.display_name[cw.display_name.duplicated()].tolist()
if dups:
    raise SystemExit(f"Duplicate display names: {dups}")
cw["name_changed_from_index"] = cw.index.isin(idx.index) & (cw.display_name != inform_name.reindex(cw.index).str.replace("’", "'"))
cw["name_needs_review"] = cw.index.isin(X.DERIVED_NAMES)
cw["axis_label"] = cw.index          # crowded chart axes use the key, with the full name on hover (Nov 12)
cw["data_parent"] = pd.Series(X.DATA_PARENT).reindex(cw.index)
cw["index_name"] = inform_name.reindex(cw.index)
cw["in_inform"] = cw.index.isin(idx.index)
cw["in_imf"] = cw.in_inform & ~imf_missing.reindex(cw.index).fillna(True).astype(bool)
for s in ["emdat", "idmc", "wdi"]:
    mapped = set(aliases[(aliases.source == s) & aliases.key.ne("")].key.str.split("|").explode())
    cw[f"in_{s}"] = cw.index.isin(mapped)
    cw[f"{s}_name"] = name_in(s).reindex(cw.index)
for k, brk in X.DISPUTED_LAYER_UNITS.items():
    cw.loc[k, "ne_units"] = f"{brk} (disputed-areas layer)"
cw["has_geometry"] = cw.ne_units.notna()
cw["key_from_adm0_a3"] = cw.key_from_adm0_a3.fillna(False).astype(bool)
cw["note"] = pd.Series(X.NOTES).reindex(cw.index)
cols = ["display_name", "status", "axis_label", "in_inform", "in_imf", "in_emdat", "in_idmc", "in_wdi", "data_parent",
        "has_geometry", "ne_units", "ne_name", "ne_type", "ne_sovereign", "key_from_adm0_a3", "index_name",
        "emdat_name", "idmc_name", "wdi_name", "name_changed_from_index", "name_needs_review", "note"]
cw = cw[cols].reset_index()
cw.to_csv(X.CROSSWALK_CSV, index=False)

# ------------------------------------------------------------------ checks ----
assert len(X.UN_MEMBERS) == 193
assert X.UN_MEMBERS <= set(cw.iso3), sorted(X.UN_MEMBERS - set(cw.iso3))
assert set(idx.index) <= set(cw.iso3)
assert set(idx.index) == (X.UN_MEMBERS - {"AND", "MCO", "SMR"}) | {"PSE"}
assert not cw.iso3.eq("-99").any()

# ------------------------------------------------------------------ report ----
def md(df):
    df = df.fillna("").replace({True: "yes", False: ""})
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join(str(v) for v in r) + " |\n" for r in df.itertuples(index=False))


c = cw.set_index("iso3")
changed = c[c.name_changed_from_index][["index_name", "display_name"]].reset_index()
changed.columns = ["Key", "Name in the index (World Bank style)", "Display name"]
other = c[c.status.isin(["Other place, not a UN member state", "UN observer state"])].copy()
other["display_name"] = other.display_name + other.index.map(lambda k: " *" if k in X.DERIVED_NAMES else "")
other = other[["display_name", "status", "in_inform", "data_parent", "note"]].reset_index()
other.columns = ["Key", "Display name", "Status", "INFORM score", "Map shading from", "Note"]
alias_tab = aliases[aliases.action.isin(["region_of", "same_place", "split", "exclude"]) & ~aliases.reason.str.startswith("World Bank regional")]
alias_tab = alias_tab[["source", "code", "source_name", "key", "action", "reason"]].replace(
    {"action": {"region_of": "Part of the country", "same_place": "Same place", "split": "Split by location",
                "exclude": "Excluded"}, "source": {"emdat": "EM-DAT", "idmc": "IDMC", "wdi": "WDI"}})
alias_tab.columns = ["Source", "Code", "Name in the source", "Key", "Decision", "Reason"]
terr = c[c.status.eq("Territory")]
terr_src = terr[terr.in_emdat | terr.in_idmc][["display_name", "ne_sovereign", "in_emdat", "in_idmc", "in_wdi"]].reset_index()
terr_src.columns = ["Key", "Display name", "Natural Earth sovereign", "EM-DAT", "IDMC", "WDI"]
counts = c.status.value_counts()
n_agg = int((aliases.reason.str.startswith("World Bank regional")).sum())

report = f"""# Country crosswalk

Built by `scripts/build_country_crosswalk.py` from the rules in `src/hvd/crosswalk.py`. Outputs:
`data/processed/crosswalk/country_crosswalk.csv` (one row per key) and `country_aliases.csv` (every country code each
source uses). The build fails if a source code has no decision.

## Rules

- **Key.** Natural Earth's `ISO_A3_EH`, falling back to `ADM0_A3` where it is −99: Somaliland (`SOL`), Kosovo (`KOS`),
  Northern Cyprus (`CYN`), and Siachen Glacier (`KAS`). Decided Nov 11, 2026. Natural Earth gives Australia's Indian
  Ocean Territories and Ashmore and Cartier Islands the key `AUS`, so they count as Australia.
- **Display names.** UN member states and observer states use their UN short name in natural word order
  (`workplan/terminology.md`), with the judgment calls confirmed Nov 12: The Bahamas, The Gambia, Republic of the
  Congo, and State of Palestine. Places that are not UN member states use UN statistical names (Nov 16).
- **Chart axes.** Crowded axes use the key, with the display name on hover or in the caption (Nov 12).
- **Parts of a country listed separately.** The Canary Islands, the Azores, France's overseas departments, and
  Svalbard count with their country (Nov 16), as they do in Natural Earth's geometry and the World Bank's population.
- **Dependent territories** (Puerto Rico, Guam, Hong Kong, and others) keep their own key. INFORM does not score
  them, so they are outside the country analyses and appear on the map as having no score.
- **Serbia and Montenegro.** EM-DAT's 12 records for 2000–2006 go to Montenegro when a record names only Montenegro
  (1 record) and to Serbia, the continuing state, otherwise (11). Decided Nov 16.
- **Abyei Area** is drawn on its own and hatched, attributed to neither Sudan nor South Sudan (Nov 16). IDMC
  records displacement there; it has no INFORM score, so it stays outside the country analyses.
- **Somaliland** is shaded with Somalia's score on the map, because INFORM, EM-DAT, and IDMC count it within Somalia,
  and is hatched as disputed (Nov 16). Northern Cyprus, Kosovo, Western Sahara, and Siachen Glacier stay unshaded,
  because no source scores them.

## Coverage

- {len(c)} keys: {counts.get('UN member state', 0)} UN member states, {counts.get('UN observer state', 0)} UN observer states, {counts.get('Territory', 0)} territories, {counts.get('Other place, not a UN member state', 0)} other places that are not UN member states, and Antarctica.
- The index scores {int(c.in_inform.sum())} of them: 190 UN member states (all but Andorra, Monaco, and San Marino) and the State of Palestine. The IMF indicators cover {int(c.in_imf.sum())}.
- EM-DAT (2000–2025) uses {int((aliases.source == 'emdat').sum())} country codes, IDMC {int((aliases.source == 'idmc').sum())}, and the WDI export {int((aliases.source == 'wdi').sum())}, including {n_agg} regional and income-group aggregates, which are excluded.

## Display names that change from the index

The index carries World Bank style names. These change on display; every other UN member keeps its name.
Yemen was added on Nov 16 as "Republic of Yemen" (the Nov 11 list missed it).

{md(changed)}
## Places that are not UN member states, and observers

Somaliland and Northern Cyprus have no UN statistical name; LaKeta confirmed their names on Nov 16. The Abyei Area is
drawn on its own and hatched, attributed to neither Sudan nor South Sudan (Nov 16).

{md(other)}
## Source codes that are not keys

{md(alias_tab)}
## Territories with source data but no INFORM score

These keep their own key and stay out of the country analyses.

{md(terr_src)}"""
REPORT.write_text(report, encoding="utf-8")
print(f"{len(cw)} keys; {len(aliases)} source codes; report: {REPORT.relative_to(ROOT)}")
