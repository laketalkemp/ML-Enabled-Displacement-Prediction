"""Country crosswalk: one key per place, the name shown for it, and how each source's country codes map to it.

Decisions (workplan/terminology.md and reports/country_crosswalk.md):
- Key (Nov 11, 2026): Natural Earth's ISO_A3_EH, falling back to ADM0_A3 where it is -99 (Somaliland SOL, Kosovo KOS,
  Northern Cyprus CYN, Siachen Glacier KAS). Natural Earth units that share a key (Australia and two of its external
  territories) are one place.
- Names: UN member states and observer states use their UN short name in natural word order, with the four judgment
  calls of Nov 12 (The Bahamas, The Gambia, Republic of the Congo, State of Palestine). Places that are not UN member
  states use UN statistical names (Nov 16): Taiwan Province of China, Hong Kong SAR (China), Kosovo (UNSCR 1244).
- Sources (Nov 16): parts of a country that a source lists separately (Canary Islands, Azores, French overseas
  departments, Svalbard) count with that country; EM-DAT's "Serbia Montenegro" (2000-2006) goes to Montenegro when a
  record names only Montenegro, otherwise to Serbia; dependent territories keep their own key and have no INFORM score.
- Map (Nov 16): Somaliland is shaded with Somalia's score (DATA_PARENT), because INFORM, EM-DAT and IDMC count it
  within Somalia; it is hatched as disputed.

Every source code is either a key, an alias below, or an explicit exclusion; scripts/build_country_crosswalk.py fails
on anything else.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import paths

CROSSWALK_DIR = paths.PROCESSED / "crosswalk"
CROSSWALK_CSV = CROSSWALK_DIR / "country_crosswalk.csv"
ALIASES_CSV = CROSSWALK_DIR / "country_aliases.csv"

# The 193 UN member states (ISO 3166-1 alpha-3).
UN_MEMBERS = frozenset("""
AFG ALB DZA AND AGO ATG ARG ARM AUS AUT AZE BHS BHR BGD BRB BLR BEL BLZ BEN BTN BOL BIH BWA BRA BRN BGR BFA BDI CPV KHM
CMR CAN CAF TCD CHL CHN COL COM COG CRI CIV HRV CUB CYP CZE PRK COD DNK DJI DMA DOM ECU EGY SLV GNQ ERI EST SWZ ETH FJI
FIN FRA GAB GMB GEO DEU GHA GRC GRD GTM GIN GNB GUY HTI HND HUN ISL IND IDN IRN IRQ IRL ISR ITA JAM JPN JOR KAZ KEN KIR
KWT KGZ LAO LVA LBN LSO LBR LBY LIE LTU LUX MDG MWI MYS MDV MLI MLT MHL MRT MUS MEX FSM MCO MNG MNE MAR MOZ MMR NAM NRU
NPL NLD NZL NIC NER NGA MKD NOR OMN PAK PLW PAN PNG PRY PER PHL POL PRT QAT KOR MDA ROU RUS RWA KNA LCA VCT WSM SMR STP
SAU SEN SRB SYC SLE SGP SVK SVN SLB SOM ZAF SSD ESP LKA SDN SUR SWE CHE SYR TJK THA TLS TGO TON TTO TUN TUR TKM TUV UGA
UKR ARE GBR TZA USA URY UZB VUT VEN VNM YEM ZMB ZWE""".split())
UN_OBSERVERS = frozenset({"PSE", "VAT"})

# Preferred names where they differ from the World Bank style names the INFORM extracts carry (terminology.md, Nov 11-12;
# Yemen added Nov 16 as "Republic of Yemen", the natural order of "Yemen, Rep."). Every other UN member keeps the INFORM name, which already matches its UN short name.
PREFERRED = {
    "BHS": "The Bahamas", "BOL": "Plurinational State of Bolivia", "COD": "Democratic Republic of the Congo",
    "COG": "Republic of the Congo", "EGY": "Egypt", "FSM": "Federated States of Micronesia",
    "GBR": "United Kingdom of Great Britain and Northern Ireland", "GMB": "The Gambia",
    "IRN": "Islamic Republic of Iran", "KGZ": "Kyrgyzstan", "KNA": "Saint Kitts and Nevis", "KOR": "Republic of Korea",
    "LAO": "Lao People's Democratic Republic", "LCA": "Saint Lucia", "MDA": "Republic of Moldova",
    "NLD": "Kingdom of the Netherlands", "PRK": "Democratic People's Republic of Korea", "PSE": "State of Palestine",
    "SVK": "Slovakia", "TZA": "United Republic of Tanzania", "USA": "United States of America",
    "VCT": "Saint Vincent and the Grenadines", "VEN": "Bolivarian Republic of Venezuela", "VNM": "Viet Nam",
    "YEM": "Republic of Yemen",
    # UN members and observers that INFORM does not score
    "AND": "Andorra", "MCO": "Monaco", "SMR": "San Marino", "VAT": "Holy See",
}

# Places that are not UN member states: UN statistical names (Nov 16). Somaliland and Northern Cyprus have no UN
# statistical name; LaKeta confirmed "Somaliland (Somalia)" and "Northern Cyprus (Cyprus)" on Nov 16.
OTHER_NAMES = {
    "TWN": "Taiwan Province of China", "HKG": "Hong Kong SAR (China)", "MAC": "Macao SAR (China)",
    "KOS": "Kosovo (UNSCR 1244)", "ESH": "Western Sahara", "SOL": "Somaliland (Somalia)",
    "CYN": "Northern Cyprus (Cyprus)", "KAS": "Siachen Glacier", "ATA": "Antarctica", "AB9": "Abyei Area",
    "ABW": "Aruba", "AIA": "Anguilla", "ALA": "Åland Islands", "ASM": "American Samoa",
    "ATF": "French Southern Territories", "BLM": "Saint Barthélemy", "BMU": "Bermuda", "COK": "Cook Islands",
    "CUW": "Curaçao", "CYM": "Cayman Islands", "FLK": "Falkland Islands (Malvinas)", "FRO": "Faroe Islands",
    "GGY": "Guernsey", "GRL": "Greenland", "GUM": "Guam", "HMD": "Heard Island and McDonald Islands",
    "IMN": "Isle of Man", "IOT": "British Indian Ocean Territory", "JEY": "Jersey",
    "MAF": "Saint Martin (French Part)", "MNP": "Northern Mariana Islands", "MSR": "Montserrat",
    "NCL": "New Caledonia", "NFK": "Norfolk Island", "NIU": "Niue", "PCN": "Pitcairn", "PRI": "Puerto Rico",
    "PYF": "French Polynesia", "SGS": "South Georgia and the South Sandwich Islands", "SHN": "Saint Helena",
    "SPM": "Saint Pierre and Miquelon", "SXM": "Sint Maarten (Dutch part)", "TCA": "Turks and Caicos Islands",
    "VGB": "British Virgin Islands", "VIR": "United States Virgin Islands", "WLF": "Wallis and Futuna Islands",
    # in a source but not drawn at Natural Earth's 1:50m scale
    "TKL": "Tokelau", "GIB": "Gibraltar",
}
DERIVED_NAMES: set = set()          # names with no UN source still to confirm (Somaliland, Northern Cyprus confirmed Nov 16)

# Places drawn from Natural Earth's disputed-areas layer rather than admin-0: key -> BRK_A3 in that layer.
# Abyei is carved out of Sudan on the map and attributed to neither Sudan nor South Sudan (LaKeta, Nov 16).
DISPUTED_LAYER_UNITS = {"AB9": "B13"}

# Map shading: the key whose data cover this unit. Somaliland is counted within Somalia by INFORM, EM-DAT and IDMC.
DATA_PARENT = {"SOL": "SOM"}

NOTES = {
    "KOS": "UN usage: references to Kosovo are in the context of Security Council resolution 1244 (1999). No INFORM score.",
    "SOL": "Drawn separately by Natural Earth (de facto); INFORM, EM-DAT and IDMC count it within Somalia, so the map "
           "shades it with Somalia's score and hatches it as disputed.",
    "CYN": "Drawn separately by Natural Earth (de facto); no source scores it. Hatched as disputed.",
    "KAS": "Indeterminate in Natural Earth; no source scores it. Hatched as disputed.",
    "AB9": "Special administrative status between Sudan and South Sudan; final status not yet determined. Drawn on its "
           "own (Natural Earth's disputed-areas layer, carved out of Sudan) and hatched, attributed to neither country "
           "(LaKeta, Nov 16). No INFORM score; IDMC records displacement here, outside the country analyses.",
    "ESH": "Non-self-governing territory (UN); no INFORM score. Partly administered by Morocco; hatched as disputed.",
    "PSE": "UN non-member observer state; scored by INFORM. Also covered by the disputed-area policy.",
    "VAT": "UN non-member observer state; not scored by INFORM.",
    "TWN": "Not a UN member state; no INFORM score. EM-DAT and IDMC report it separately.",
    "AUS": "Natural Earth gives Australia's Indian Ocean Territories and Ashmore and Cartier Islands the key AUS.",
    "FRA": "Includes the overseas departments (French Guiana, Guadeloupe, Martinique, Mayotte, Réunion), as Natural "
           "Earth and the World Bank do; EM-DAT and IDMC list them separately and are mapped here.",
    "ESP": "Includes the Canary Islands, which EM-DAT lists separately.",
    "PRT": "Includes the Azores, which EM-DAT lists separately.",
    "NOR": "Includes Svalbard and Jan Mayen, which IDMC lists separately.",
    "SRB": "Takes EM-DAT's 'Serbia Montenegro' records (2000-2006) except one that names only Montenegro. EM-DAT "
           "places some later records in Kosovo under Serbia; they stay with Serbia.",
    "MNE": "Takes the one EM-DAT 'Serbia Montenegro' record (2000) that names only Montenegro.",
}

# Source codes that are not keys. action: region_of (part of a country), same_place (another code for the place),
# split (by the record's location), exclude (not one place; no key).
ALIASES = [
    # EM-DAT
    ("emdat", "AZO", "PRT", "region_of", "The Azores are an autonomous region of Portugal."),
    ("emdat", "SPI", "ESP", "region_of", "The Canary Islands are an autonomous community of Spain."),
    ("emdat", "GLP", "FRA", "region_of", "Overseas department of France."),
    ("emdat", "GUF", "FRA", "region_of", "Overseas department of France."),
    ("emdat", "MTQ", "FRA", "region_of", "Overseas department of France."),
    ("emdat", "MYT", "FRA", "region_of", "Overseas department of France."),
    ("emdat", "REU", "FRA", "region_of", "Overseas department of France."),
    ("emdat", "SCG", "SRB|MNE", "split", "Serbia and Montenegro (2000-2006): Montenegro when the record names only "
                                         "Montenegro, otherwise Serbia, the continuing state."),
    # IDMC
    ("idmc", "GLP", "FRA", "region_of", "Overseas department of France."),
    ("idmc", "GUF", "FRA", "region_of", "Overseas department of France."),
    ("idmc", "MTQ", "FRA", "region_of", "Overseas department of France."),
    ("idmc", "MYT", "FRA", "region_of", "Overseas department of France."),
    ("idmc", "REU", "FRA", "region_of", "Overseas department of France."),
    ("idmc", "SJM", "NOR", "region_of", "Svalbard and Jan Mayen are part of Norway."),
    ("idmc", "XKX", "KOS", "same_place", "IDMC's code for Kosovo."),
    # World Bank (WDI)
    ("wdi", "XKX", "KOS", "same_place", "The World Bank's code for Kosovo."),
    ("wdi", "CHI", "", "exclude", "Channel Islands: Jersey and Guernsey combined; each has its own key."),
]
WDI_AGGREGATE = "exclude"   # regional and income-group rows in WDI exports; recognized by name in wdi_aggregates()

_SCG_MONTENEGRO = re.compile(r"\(Montenegro\)\s*$")


def _alias_table() -> pd.DataFrame:
    return pd.DataFrame(ALIASES, columns=["source", "code", "key", "action", "reason"])


def load() -> pd.DataFrame:
    """The committed crosswalk, one row per key."""
    return pd.read_csv(CROSSWALK_CSV, keep_default_na=False, na_values=[""])


def to_key(codes: pd.Series, source: str, location: pd.Series | None = None) -> pd.Series:
    """Map a source's country codes to crosswalk keys. Excluded codes become NaN. For EM-DAT's SCG, pass the
    Location column so each record can be split between Serbia and Montenegro."""
    codes = codes.astype("string").str.strip()
    al = _alias_table()
    al = al[al.source == source].set_index("code")
    out = codes.copy()
    for code, row in al.iterrows():
        hit = codes == code
        if not hit.any():
            continue
        if row.action == "exclude":
            out[hit] = pd.NA
        elif row.action == "split":
            if location is None:
                raise ValueError(f"{source} code {code} is split by location; pass location=")
            loc = location.astype("string").fillna("")
            mne = hit & loc.str.contains(_SCG_MONTENEGRO) & ~loc.str.contains("Serbia")
            out[hit] = "SRB"
            out[mne] = "MNE"
        else:
            out[hit] = row.key
    if source == "wdi":
        out[codes.isin(wdi_aggregates())] = pd.NA
    return out


def display_name(keys: pd.Series, fallback: pd.Series | None = None) -> pd.Series:
    """Preferred display names for keys, from the committed crosswalk."""
    names = load().set_index("iso3")["display_name"]
    out = keys.map(names)
    return out if fallback is None else out.fillna(fallback)


# World Bank aggregate codes (regions, income and lending groups) in the WDI export.
_WDI_AGGREGATES = frozenset("""
AFE AFW ARB CEB CSS EAP EAR EAS ECA ECS EMU EUU FCS FCV HIC HPC IBD IBT IDA IDB IDX INX LAC LCN LDC LIC LMC LMY LTE MEA MIC
MNA NAC OED OSS PRE PSS PST SAS SSA SSF SST TEA TEC TLA TMN TSA TSS UMC WLD""".split())


def wdi_aggregates() -> frozenset:
    return _WDI_AGGREGATES
