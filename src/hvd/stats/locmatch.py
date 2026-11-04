"""Province / district name matching for EM-DAT records (Location text), used by
scripts/emdat_province_counts.py. Reads only public repository files (crosswalks, geoBoundaries)."""
import json
import re
from pathlib import Path

import pandas as pd

# Extra names and spellings found in EM-DAT, by unit
extra = {"AFG": {"AF-HEL": ["Helmand"], "AF-HER": ["Herat"], "AF-JOW": ["Jowzjan", "Jauzjan"], "AF-NIM": ["Nimruz"],
                 "AF-PKA": ["Paktia"], "AF-SAR": ["Sar-e Pol", "Sar-i-Pul", "Saripul"], "AF-DAY": ["Daikundi", "Day Kundi"],
                 "AF-PAN": ["Panjsher"], "AF-URU": ["Urozgan", "Oruzgan"], "AF-WAR": ["Maidan Wardak", "Maydan Wardak"],
                 "AF-KNR": ["Konar"], "AF-BAM": ["Bamiyan"], "AF-NUR": ["Nooristan", "Nouristan"]},
         "PHL": {"PH-NCO": ["North Cotabato"], "PH-00": ["Metropolitan Manila", "Metro Manila", "NCR"],
                 "PH-COM": ["Davao de Oro"], "PH-DAS": ["Davao Occidental"],   # GADM 4.1 has no Davao Occidental
                 "PH-MAG": ["Maguindanao del Sur", "Maguindanao del Norte", "Maguidanao"]},
         "BGD": {"Chittagong": ["Chattogram"], "Comilla": ["Cumilla"], "Bogra": ["Bogura"], "Barisal": ["Barishal"],
                 "Jessore": ["Jashore"], "Netrakona": ["Netrokona"], "Maulvibazar": ["Moulvibazar", "Moulvi Bazar"],
                 "Nawabganj": ["Chapainawabganj", "Chapai Nawabganj", "Chapaiwabganj"], "Jhalokati": ["Jhalokathi", "Jhalokath", "Jhalakati"],
                 "Khagrachhari": ["Khagrachari"], "Brahamanbaria": ["Brahmanbaria"], "Bandarban": ["Banderban"],
                 "Narsingdi": ["Narshingdi"]}}
extra["AFG"].update({"AF-SAR": ["Sar-e Pol", "Sar-i-Pul", "Saripul", "Sar-e-Pul", "Sar-e-Pol"], "AF-HER": ["Herat", "Hirat"],
                     "AF-JOW": ["Jowzjan", "Jauzjan", "Jawzjan"], "AF-BDS": ["Badakshan"], "AF-DAY": ["Daikundi", "Day Kundi", "Daykundi"]})

# Location text, version 2 (Oct 28, 2026), after a review of the 89 text-based assignments:
# - cities whose names contain a province name are mapped to the province they sit in, before matching;
# - Philippine regions (by name or number) expand to their provinces, unless the text already names one of
#   that region's provinces (then the region is only describing where that province is);
# - names followed by "upazila", "division(s)" or "region" are not read as a district/province.
PHL_CITY = {r"Quezon City": "Metro Manila", r"Cagayan de Oro( City)?": "Misamis Oriental", r"Davao City": "Davao del Sur",
            r"General Santos( City)?": "South Cotabato", r"Baguio( City)?": "Benguet", r"Zamboanga City": "Zamboanga del Sur",
            r"Cebu City": "Cebu", r"Iloilo City": "Iloilo", r"\bManill?a\b": "Metro Manila", r"Cagayan Valley": "Region II"}
PHL_REGIONS = {
    "I": (r"Ilocos Region|\bIlocos\b(?!\s+(Norte|Sur))", ["PH-ILN", "PH-ILS", "PH-LUN", "PH-PAN"]),
    "II": (r"Cagayan Valley", ["PH-BTN", "PH-CAG", "PH-ISA", "PH-NUV", "PH-QUI"]),
    "III": (r"Central Luzon", ["PH-AUR", "PH-BAN", "PH-BUL", "PH-NUE", "PH-PAM", "PH-TAR", "PH-ZMB"]),
    "IV-A": (r"Calabarzon", ["PH-BTG", "PH-CAV", "PH-LAG", "PH-QUE", "PH-RIZ"]),
    "IV-B": (r"Mimaropa", ["PH-MAD", "PH-MDC", "PH-MDR", "PH-PLW", "PH-ROM"]),
    "V": (r"\bBicol\b", ["PH-ALB", "PH-CAN", "PH-CAS", "PH-CAT", "PH-MAS", "PH-SOR"]),
    "VI": (r"Western Visayas", ["PH-AKL", "PH-ANT", "PH-CAP", "PH-GUI", "PH-ILI", "PH-NEC"]),
    "VII": (r"Central Visayas", ["PH-BOH", "PH-CEB", "PH-NER", "PH-SIG"]),
    "VIII": (r"E(a|s)s?(t|a)tern Visayas", ["PH-BIL", "PH-EAS", "PH-LEY", "PH-NSA", "PH-WSA", "PH-SLE"]),
    "IX": (r"Zamboanga Peninsula", ["PH-ZAN", "PH-ZAS", "PH-ZSI"]),
    "X": (r"Northern Mindanao", ["PH-BUK", "PH-CAM", "PH-LAN", "PH-MSC", "PH-MSR"]),
    "XI": (r"Davao Region|Dava Region", ["PH-COM", "PH-DAV", "PH-DAS", "PH-DAO"]),
    "XII": (r"Soccsksargen", ["PH-NCO", "PH-SAR", "PH-SCO", "PH-SUK"]),
    "XIII": (r"\bCaraga\b", ["PH-AGN", "PH-AGS", "PH-DIN", "PH-SUN", "PH-SUR"]),
    "CAR": (r"Cordillera|\bCAR\b", ["PH-ABR", "PH-APA", "PH-BEN", "PH-IFU", "PH-KAL", "PH-MOU"]),
    "BARMM": (r"BARMM|\bARMM\b|Bangsamoro|Muslim Mindanao", ["PH-BAS", "PH-LAS", "PH-MAG", "PH-SLU", "PH-TAW"]),
    "NCR": (r"\bNCR\b|National Capital", ["PH-00"]),
}
ROMAN = {"1": "I", "2": "II", "3": "III", "4A": "IV-A", "4-A": "IV-A", "IV-A": "IV-A", "4B": "IV-B", "5": "V", "6": "VI", "7": "VII",
         "8": "VIII", "9": "IX", "10": "X", "11": "XI", "12": "XII", "13": "XIII", "I": "I", "II": "II", "III": "III", "V": "V",
         "VI": "VI", "VII": "VII", "VIII": "VIII", "IX": "IX", "X": "X", "XI": "XI", "XII": "XII", "XIII": "XIII"}
SKIP_AFTER = re.compile(r"^\s*(and\s+\w+\s+)?(upazila|upazilla|divisions?)\b", re.I)


def location_units(iso, text, units):
    t = text.replace("\u2019", "'").replace("\u2018", "'")
    regions = set()
    if iso == "PHL":
        for pat, rep in PHL_CITY.items():
            t = re.sub(pat, rep, t, flags=re.I)
        for code, (pat, _) in PHL_REGIONS.items():
            if re.search(pat, t, re.I):
                regions.add(code)
        for m in re.finditer(r"Regions?\s+((?:[IVX]+(?:-[AB])?|\d+[AB]?)(?:\s*(?:\([^)]*\))?\s*(?:,|and|&)\s*(?:[IVX]+(?:-[AB])?|\d+[AB]?))*)", t):
            for tok in re.findall(r"[IVX]+(?:-[AB])?|\d+[AB]?", m.group(1)):
                if tok.upper() in ROMAN:
                    regions.add(ROMAN[tok.upper()])
        t = re.sub(r"Region II\b", "", t)
    out = set()
    # longest names first, and each match is blanked out, so "South Cotabato" is not also read as "Cotabato"
    # and "Eastern Samar" not also as "Samar"
    for a, u in sorted(((a, u) for u, al in units[iso].items() for a in al), key=lambda x: -len(x[0])):
        for m in list(re.finditer(r"\b" + re.escape(a) + r"\b", t, re.I)):
            if SKIP_AFTER.match(t[m.end():m.end() + 30]):
                continue
            out.add(u)
            t = t[:m.start()] + "#" * (m.end() - m.start()) + t[m.end():]
    expanded = set()
    for code in regions:
        provs = PHL_REGIONS[code][1]
        if not out.intersection(provs):
            expanded.update(provs)
    return out | expanded, bool(expanded)


def build_units(root="."):
    """Analysis units and their names/aliases: {iso: {unit_id: [names...]}}."""
    root = Path(root)
    afg = pd.read_csv(root / "data/processed/regions/afg_province_crosswalk.csv")
    phl = pd.read_csv(root / "data/processed/regions/phl_province_crosswalk.csv")
    bgd = pd.json_normalize(json.load(open(root / "data/external/geoboundaries/geoBoundaries-BGD-ADM2_simplified.geojson"))["features"])
    def _aliases(al):
        return [a.strip() for a in str(al).split(";") if a.strip()] if al == al else []
    units = {"AFG": {u: [n] + _aliases(al) + extra["AFG"].get(u, []) for u, n, al in zip(afg.unit_id, afg.name, afg.aliases)},
             "PHL": {u: [n] + _aliases(al) + extra["PHL"].get(u, []) for u, n, al in zip(phl.unit_id, phl.name, phl.aliases)},
             "BGD": {n: [n] + extra["BGD"].get(n, []) for n in bgd["properties.shapeName"]}}
    units["PHL"].pop("PH-DVO", None)   # folded into Davao del Sur for EM-DAT, matching GADM 4.1
    return units
