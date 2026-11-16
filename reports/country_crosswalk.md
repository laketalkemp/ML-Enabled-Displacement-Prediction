# Country crosswalk

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

- 243 keys: 193 UN member states, 2 UN observer states, 40 territories, 7 other places that are not UN member states, and Antarctica.
- The index scores 191 of them: 190 UN member states (all but Andorra, Monaco, and San Marino) and the State of Palestine. The IMF indicators cover 188.
- EM-DAT (2000–2025) uses 220 country codes, IDMC 214, and the WDI export 266, including 49 regional and income-group aggregates, which are excluded.

## Display names that change from the index

The index carries World Bank style names. These change on display; every other UN member keeps its name.
Yemen was added on Nov 16 as "Republic of Yemen" (the Nov 11 list missed it).

| Key | Name in the index (World Bank style) | Display name |
|---|---|---|
| BHS | Bahamas, The | The Bahamas |
| BOL | Bolivia | Plurinational State of Bolivia |
| COD | Congo, Dem. Rep. | Democratic Republic of the Congo |
| COG | Congo, Rep. | Republic of the Congo |
| EGY | Egypt, Arab Rep. | Egypt |
| FSM | Micronesia, Fed. Sts. | Federated States of Micronesia |
| GBR | United Kingdom | United Kingdom of Great Britain and Northern Ireland |
| GMB | Gambia, The | The Gambia |
| IRN | Iran, Islamic Rep. | Islamic Republic of Iran |
| KGZ | Kyrgyz Republic | Kyrgyzstan |
| KNA | St. Kitts and Nevis | Saint Kitts and Nevis |
| KOR | Korea, Rep. | Republic of Korea |
| LAO | Lao PDR | Lao People's Democratic Republic |
| LCA | St. Lucia | Saint Lucia |
| MDA | Moldova | Republic of Moldova |
| NLD | Netherlands | Kingdom of the Netherlands |
| PRK | Korea, Dem. People's Rep. | Democratic People's Republic of Korea |
| PSE | West Bank and Gaza | State of Palestine |
| SVK | Slovak Republic | Slovakia |
| TZA | Tanzania | United Republic of Tanzania |
| USA | United States | United States of America |
| VCT | St. Vincent and the Grenadines | Saint Vincent and the Grenadines |
| VEN | Venezuela, RB | Bolivarian Republic of Venezuela |
| VNM | Vietnam | Viet Nam |
| YEM | Yemen, Rep. | Republic of Yemen |

## Places that are not UN member states, and observers

Somaliland and Northern Cyprus have no UN statistical name; LaKeta confirmed their names on Nov 16. The Abyei Area is
drawn on its own and hatched, attributed to neither Sudan nor South Sudan (Nov 16).

| Key | Display name | Status | INFORM score | Map shading from | Note |
|---|---|---|---|---|---|
| AB9 | Abyei Area | Other place, not a UN member state |  |  | Special administrative status between Sudan and South Sudan; final status not yet determined. Drawn on its own (Natural Earth's disputed-areas layer, carved out of Sudan) and hatched, attributed to neither country (LaKeta, Nov 16). No INFORM score; IDMC records displacement here, outside the country analyses. |
| CYN | Northern Cyprus (Cyprus) | Other place, not a UN member state |  |  | Drawn separately by Natural Earth (de facto); no source scores it. Hatched as disputed. |
| ESH | Western Sahara | Other place, not a UN member state |  |  | Non-self-governing territory (UN); no INFORM score. Partly administered by Morocco; hatched as disputed. |
| KAS | Siachen Glacier | Other place, not a UN member state |  |  | Indeterminate in Natural Earth; no source scores it. Hatched as disputed. |
| KOS | Kosovo (UNSCR 1244) | Other place, not a UN member state |  |  | UN usage: references to Kosovo are in the context of Security Council resolution 1244 (1999). No INFORM score. |
| PSE | State of Palestine | UN observer state | yes |  | UN non-member observer state; scored by INFORM. Also covered by the disputed-area policy. |
| SOL | Somaliland (Somalia) | Other place, not a UN member state |  | SOM | Drawn separately by Natural Earth (de facto); INFORM, EM-DAT and IDMC count it within Somalia, so the map shades it with Somalia's score and hatches it as disputed. |
| TWN | Taiwan Province of China | Other place, not a UN member state |  |  | Not a UN member state; no INFORM score. EM-DAT and IDMC report it separately. |
| VAT | Holy See | UN observer state |  |  | UN non-member observer state; not scored by INFORM. |

## Source codes that are not keys

| Source | Code | Name in the source | Key | Decision | Reason |
|---|---|---|---|---|---|
| EM-DAT | AZO | Azores Islands | PRT | Part of the country | The Azores are an autonomous region of Portugal. |
| EM-DAT | GLP | Guadeloupe | FRA | Part of the country | Overseas department of France. |
| EM-DAT | GUF | French Guiana | FRA | Part of the country | Overseas department of France. |
| EM-DAT | MTQ | Martinique | FRA | Part of the country | Overseas department of France. |
| EM-DAT | MYT | Mayotte | FRA | Part of the country | Overseas department of France. |
| EM-DAT | REU | Réunion | FRA | Part of the country | Overseas department of France. |
| EM-DAT | SCG | Serbia Montenegro | SRB|MNE | Split by location | Serbia and Montenegro (2000-2006): Montenegro when the record names only Montenegro, otherwise Serbia, the continuing state. |
| EM-DAT | SPI | Canary Islands | ESP | Part of the country | The Canary Islands are an autonomous community of Spain. |
| IDMC | GLP | Guadeloupe | FRA | Part of the country | Overseas department of France. |
| IDMC | GUF | French Guiana | FRA | Part of the country | Overseas department of France. |
| IDMC | MTQ | Martinique | FRA | Part of the country | Overseas department of France. |
| IDMC | MYT | Mayotte | FRA | Part of the country | Overseas department of France. |
| IDMC | REU | Réunion | FRA | Part of the country | Overseas department of France. |
| IDMC | SJM | Svalbard and Jan Mayen Islands | NOR | Part of the country | Svalbard and Jan Mayen are part of Norway. |
| IDMC | XKX | Kosovo | KOS | Same place | IDMC's code for Kosovo. |
| WDI | CHI | Channel Islands |  | Excluded | Channel Islands: Jersey and Guernsey combined; each has its own key. |
| WDI | XKX | Kosovo | KOS | Same place | The World Bank's code for Kosovo. |

## Territories with source data but no INFORM score

These keep their own key and stay out of the country analyses.

| Key | Display name | Natural Earth sovereign | EM-DAT | IDMC | WDI |
|---|---|---|---|---|---|
| AIA | Anguilla | United Kingdom | yes | yes |  |
| ASM | American Samoa | United States of America | yes | yes | yes |
| ATF | French Southern Territories | France |  | yes |  |
| BLM | Saint Barthélemy | France | yes |  |  |
| BMU | Bermuda | United Kingdom | yes | yes | yes |
| COK | Cook Islands | New Zealand | yes | yes |  |
| CYM | Cayman Islands | United Kingdom | yes | yes | yes |
| GRL | Greenland | Denmark |  | yes | yes |
| GUM | Guam | United States of America | yes | yes | yes |
| HKG | Hong Kong SAR (China) | China | yes | yes | yes |
| IMN | Isle of Man | United Kingdom |  | yes | yes |
| JEY | Jersey | United Kingdom |  | yes |  |
| MAC | Macao SAR (China) | China | yes | yes | yes |
| MAF | Saint Martin (French Part) | France | yes | yes | yes |
| MNP | Northern Mariana Islands | United States of America | yes | yes | yes |
| MSR | Montserrat | United Kingdom | yes |  |  |
| NCL | New Caledonia | France | yes | yes | yes |
| NIU | Niue | New Zealand | yes |  |  |
| PRI | Puerto Rico | United States of America | yes | yes | yes |
| PYF | French Polynesia | France | yes | yes | yes |
| SHN | Saint Helena | United Kingdom | yes |  |  |
| SXM | Sint Maarten (Dutch part) | Netherlands | yes | yes | yes |
| TCA | Turks and Caicos Islands | United Kingdom | yes | yes | yes |
| TKL | Tokelau |  | yes |  |  |
| VGB | British Virgin Islands | United Kingdom | yes | yes | yes |
| VIR | United States Virgin Islands | United States of America | yes | yes | yes |
| WLF | Wallis and Futuna Islands | France | yes |  |  |
