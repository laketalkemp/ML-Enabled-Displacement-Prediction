"""Assign EM-DAT records for the Philippines, Afghanistan and Bangladesh to provinces/districts
and count events per unit and hazard type, 2000-2025.

    python scripts/emdat_province_counts.py

Input: your own EM-DAT export at data/raw/emdat/emdat_public_<date>.xlsx (natural hazards, all countries,
2000 to present). EM-DAT's terms forbid redistribution, so data/raw/emdat/ and data/processed/emdat/ are
git-ignored and never pushed. See data/README.md.

Province source, in order of preference: GADM Admin Units -> GAUL Admin Units (matched by name)
-> province/district names found in the Location text (flagged lower confidence).
"""
import glob
import json
import os
import re
from pathlib import Path

import pandas as pd

os.chdir(Path(__file__).resolve().parents[1])   # paths below are repo-relative
files = sorted(glob.glob("data/raw/emdat/emdat_public_*.xlsx"))
if not files:
    raise SystemExit("No EM-DAT export found in data/raw/emdat/ (see data/README.md for how to download it).")
SRC = files[-1]
OUT = "data/processed/emdat"
os.makedirs(OUT, exist_ok=True)
norm = lambda x: re.sub(r"[^a-z]", "", str(x).lower())  # noqa: E731

full = pd.read_excel(SRC, sheet_name="EM-DAT Data")
df = full[(full["Start Year"] <= 2025) & (full["Disaster Type"] != "Epidemic")]

# GADM gid_1 -> name_1 from the export itself; two Afghan gid_1 never appear with a name (alphabetical GADM order)
g1 = {}
for v in full["GADM Admin Units"].dropna():
    for e in json.loads(v):
        if "gid_1" in e and "name_1" in e:
            g1[e["gid_1"]] = e["name_1"]
g1.update({"AFG.3_1": "Baghlan", "AFG.5_1": "Bamyan"})

# analysis units and their names/aliases
afg = pd.read_csv("data/processed/regions/afg_province_crosswalk.csv")
phl = pd.read_csv("data/processed/regions/phl_province_crosswalk.csv")
bgd = pd.json_normalize(json.load(open("data/external/geoboundaries/geoBoundaries-BGD-ADM2_simplified.geojson"))["features"])
extra = {"AFG": {"AF-HEL": ["Helmand"], "AF-HER": ["Herat"], "AF-JOW": ["Jowzjan", "Jauzjan"], "AF-NIM": ["Nimruz"],
                 "AF-PKA": ["Paktia"], "AF-SAR": ["Sar-e Pol", "Sar-i-Pul", "Saripul"], "AF-DAY": ["Daikundi", "Day Kundi"],
                 "AF-PAN": ["Panjsher"], "AF-URU": ["Urozgan", "Oruzgan"], "AF-WAR": ["Maidan Wardak", "Maydan Wardak"],
                 "AF-KNR": ["Konar"], "AF-BAM": ["Bamiyan"], "AF-NUR": ["Nooristan", "Nouristan"]},
         "PHL": {"PH-NCO": ["North Cotabato"], "PH-00": ["Metropolitan Manila", "Metro Manila", "NCR"],
                 "PH-COM": ["Davao de Oro"], "PH-DAS": ["Davao Occidental"]},   # GADM 4.1 has no Davao Occidental
         "BGD": {}}


def _aliases(al):
    return [a.strip() for a in str(al).split(";") if a.strip()] if al == al else []


units = {"AFG": {u: [n] + _aliases(al) + extra["AFG"].get(u, []) for u, n, al in zip(afg.unit_id, afg.name, afg.aliases)},
         "PHL": {u: [n] + _aliases(al) + extra["PHL"].get(u, []) for u, n, al in zip(phl.unit_id, phl.name, phl.aliases)},
         "BGD": {n: [n] for n in bgd["properties.shapeName"]}}
units["PHL"].pop("PH-DVO", None)   # folded into Davao del Sur for EM-DAT, matching GADM 4.1
lookup = {iso: {norm(a): u for u, al in d.items() for a in al} for iso, d in units.items()}


def assign(row):
    iso = row.ISO
    L = lookup[iso]
    level = 2 if iso == "BGD" else 1
    out = set()
    if isinstance(row["GADM Admin Units"], str):
        for e in json.loads(row["GADM Admin Units"]):
            if level == 1:
                gid = e.get("gid_1") or (re.match(r"^([A-Z]{3}\.\d+)", e.get("gid_2", "")).group(1) + "_1" if "gid_2" in e else None)
                u = L.get(norm(g1.get(gid, "")))
            else:
                u = L.get(norm(e.get("name_2", "")))
            if u:
                out.add(u)
        if out:
            return sorted(out), "GADM"
    if isinstance(row["Admin Units"], str):
        for e in json.loads(row["Admin Units"]):
            u = L.get(norm(e.get("adm1_name", ""))) or L.get(norm(e.get("adm2_name", "")))
            if u:
                out.add(u)
        if out:
            return sorted(out), "GAUL"
    if isinstance(row.Location, str):
        for u, al in units[iso].items():
            if any(re.search(r"\b" + re.escape(a) + r"\b", row.Location, re.I) for a in al):
                out.add(u)
        if out:
            return sorted(out), "Location text"
    return [], "unresolved"


rows = []
for iso in ["PHL", "AFG", "BGD"]:
    s = df[df.ISO == iso].copy()
    s[["units", "unit_source"]] = s.apply(lambda r: pd.Series(assign(r)), axis=1)
    s["n_units"] = s.units.str.len()
    rows.append(s)
    long = s.explode("units").dropna(subset=["units"])
    counts = long.pivot_table(index="units", columns="Disaster Type", values="DisNo.", aggfunc="count", fill_value=0)
    allu = list(units[iso])
    counts = counts.reindex(allu, fill_value=0)
    counts["Total"] = counts.sum(axis=1)
    counts.index.name = "unit_id" if iso != "BGD" else "district"
    counts.to_csv(f"{OUT}/{iso.lower()}_event_counts_by_unit_2000_2025.csv")
    print(f"{iso}: {len(s)} records; source {s.unit_source.value_counts().to_dict()}")
out = pd.concat(rows)
out[["DisNo.", "ISO", "Disaster Type", "Disaster Subtype", "Start Year", "unit_source", "n_units", "units"]].assign(
    units=lambda d: d.units.str.join(";")).to_csv(f"{OUT}/record_unit_assignment_PHL_AFG_BGD.csv", index=False)
print("source file:", SRC)
