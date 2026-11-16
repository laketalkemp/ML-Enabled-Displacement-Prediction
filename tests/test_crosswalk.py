"""Country crosswalk: keys, display names, and source-code decisions (reports/country_crosswalk.md).

Run with:  pytest -q
"""
import pandas as pd
import pytest

from hvd import crosswalk as X, paths


@pytest.fixture(scope="module")
def cw():
    return X.load().set_index("iso3")


@pytest.fixture(scope="module")
def aliases():
    return pd.read_csv(X.ALIASES_CSV, keep_default_na=False)


def test_keys_cover_un_members_observers_and_index(cw):
    assert len(X.UN_MEMBERS) == 193
    assert X.UN_MEMBERS | X.UN_OBSERVERS <= set(cw.index)
    idx = pd.read_csv(paths.INDEX_DIR / "vulnerability_index_v1.1.csv")
    assert set(idx.iso3) <= set(cw.index)
    assert set(cw.index[cw.in_inform]) == set(idx.iso3)
    assert cw.index.is_unique and not cw.index.str.contains("-99").any()


def test_fallback_keys(cw):
    for k in ["SOL", "KOS", "CYN", "KAS"]:
        assert cw.at[k, "key_from_adm0_a3"]


def test_display_names(cw):
    assert cw.display_name.notna().all() and cw.display_name.is_unique
    assert cw.at["IRN", "display_name"] == "Islamic Republic of Iran"
    assert cw.at["PSE", "display_name"] == "State of Palestine"
    assert cw.at["YEM", "display_name"] == "Republic of Yemen"
    assert cw.at["AB9", "display_name"] == "Abyei Area" and cw.at["AB9", "has_geometry"]
    assert cw.at["TWN", "display_name"] == "Taiwan Province of China"
    assert cw.at["KOS", "display_name"] == "Kosovo (UNSCR 1244)"
    assert cw.at["AFG", "display_name"] == "Afghanistan"
    assert cw.at["SOL", "data_parent"] == "SOM"


def test_every_source_code_has_a_decision(cw, aliases):
    assert set(aliases.action) <= {"key", "region_of", "same_place", "split", "exclude"}
    targets = set(aliases.key.str.split("|").explode()) - {""}
    assert targets <= set(cw.index)
    assert (aliases.loc[aliases.action.eq("exclude"), "key"] == "").all()


def test_to_key():
    em = X.to_key(pd.Series(["PHL", "AZO", "SPI", "REU", "SCG", "SCG", "SCG"]), "emdat",
                  location=pd.Series(["", "", "", "",
                                      "Danilovgrad, Kotor, Podgorica provinces (Montenegro)",
                                      "Novi Sad town (Juzno-backi province) (Serbia)",
                                      "Andrijevica, Berane, Grad Beograd provinces (Serbia & Montenegro)"]))
    assert em.tolist() == ["PHL", "PRT", "ESP", "FRA", "MNE", "SRB", "SRB"]
    idmc = X.to_key(pd.Series(["XKX", "AB9", "SJM", "GUF", "SOM"]), "idmc")
    assert idmc.tolist() == ["KOS", "AB9", "NOR", "FRA", "SOM"]
    wdi = X.to_key(pd.Series(["WLD", "CHI", "XKX", "FRA"]), "wdi")
    assert pd.isna(wdi.iloc[0]) and pd.isna(wdi.iloc[1]) and wdi.iloc[2:].tolist() == ["KOS", "FRA"]
