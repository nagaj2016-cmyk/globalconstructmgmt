"""
NagaForge — i18n + country code-pack seed & bundle builder.

Everything the user reads is DB-driven:
  - Locale / LocaleString  -> UI + engineering terminology per language
  - Country                -> default locale, currency, timezone
  - CodePack               -> per-country engineering standards + clause labels
  - ProofSource            -> official government / standards-publisher links

`seed_platform_i18n(db)` is idempotent (safe to run on every boot).
`build_bundle(db, locale)` returns the JSON the frontend loads instead of any
hardcoded strings.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from platform_models import Locale, LocaleString, Country, CodePack, ProofSource


# ── Languages ─────────────────────────────────────────────────────────────────
SEED_LOCALES = [
    # code, name, native, direction, order
    ("en", "English",  "English",  "ltr", 10),
    ("fr", "French",   "Français", "ltr", 20),
    ("hi", "Hindi",    "हिन्दी",     "ltr", 30),
    ("ar", "Arabic",   "العربية",   "rtl", 40),
]

# ── Countries -> default locale, currency, timezone ───────────────────────────
SEED_COUNTRIES = [
    # code, name, default_locale, currency, tz, order
    ("IN", "India",                 "hi", "INR", "Asia/Kolkata",     10),
    ("CA", "Canada",                "fr", "CAD", "America/Toronto",  20),
    ("US", "United States",         "en", "USD", "America/New_York", 30),
    ("AE", "United Arab Emirates",  "ar", "AED", "Asia/Dubai",       40),
    ("GB", "United Kingdom",        "en", "GBP", "Europe/London",    50),
    ("AU", "Australia",             "en", "AUD", "Australia/Sydney", 60),
]

# ── Africa — all 54 sovereign states ──────────────────────────────────────────
# (code, name, default_locale, currency, timezone).  Locale is limited to the
# languages currently seeded (en / fr / ar); Portuguese/Swahili/Amharic markets
# fall back to English per-string until those bundles are added.
AFRICA_COUNTRIES = [
    ("DZ", "Algeria", "ar", "DZD", "Africa/Algiers"),
    ("AO", "Angola", "en", "AOA", "Africa/Luanda"),
    ("BJ", "Benin", "fr", "XOF", "Africa/Porto-Novo"),
    ("BW", "Botswana", "en", "BWP", "Africa/Gaborone"),
    ("BF", "Burkina Faso", "fr", "XOF", "Africa/Ouagadougou"),
    ("BI", "Burundi", "fr", "BIF", "Africa/Bujumbura"),
    ("CV", "Cabo Verde", "en", "CVE", "Atlantic/Cape_Verde"),
    ("CM", "Cameroon", "fr", "XAF", "Africa/Douala"),
    ("CF", "Central African Republic", "fr", "XAF", "Africa/Bangui"),
    ("TD", "Chad", "fr", "XAF", "Africa/Ndjamena"),
    ("KM", "Comoros", "ar", "KMF", "Indian/Comoro"),
    ("CG", "Congo (Republic)", "fr", "XAF", "Africa/Brazzaville"),
    ("CD", "Congo (DRC)", "fr", "CDF", "Africa/Kinshasa"),
    ("CI", "Côte d'Ivoire", "fr", "XOF", "Africa/Abidjan"),
    ("DJ", "Djibouti", "fr", "DJF", "Africa/Djibouti"),
    ("EG", "Egypt", "ar", "EGP", "Africa/Cairo"),
    ("GQ", "Equatorial Guinea", "en", "XAF", "Africa/Malabo"),
    ("ER", "Eritrea", "ar", "ERN", "Africa/Asmara"),
    ("SZ", "Eswatini", "en", "SZL", "Africa/Mbabane"),
    ("ET", "Ethiopia", "en", "ETB", "Africa/Addis_Ababa"),
    ("GA", "Gabon", "fr", "XAF", "Africa/Libreville"),
    ("GM", "Gambia", "en", "GMD", "Africa/Banjul"),
    ("GH", "Ghana", "en", "GHS", "Africa/Accra"),
    ("GN", "Guinea", "fr", "GNF", "Africa/Conakry"),
    ("GW", "Guinea-Bissau", "en", "XOF", "Africa/Bissau"),
    ("KE", "Kenya", "en", "KES", "Africa/Nairobi"),
    ("LS", "Lesotho", "en", "LSL", "Africa/Maseru"),
    ("LR", "Liberia", "en", "LRD", "Africa/Monrovia"),
    ("LY", "Libya", "ar", "LYD", "Africa/Tripoli"),
    ("MG", "Madagascar", "fr", "MGA", "Indian/Antananarivo"),
    ("MW", "Malawi", "en", "MWK", "Africa/Blantyre"),
    ("ML", "Mali", "fr", "XOF", "Africa/Bamako"),
    ("MR", "Mauritania", "ar", "MRU", "Africa/Nouakchott"),
    ("MU", "Mauritius", "en", "MUR", "Indian/Mauritius"),
    ("MA", "Morocco", "ar", "MAD", "Africa/Casablanca"),
    ("MZ", "Mozambique", "en", "MZN", "Africa/Maputo"),
    ("NA", "Namibia", "en", "NAD", "Africa/Windhoek"),
    ("NE", "Niger", "fr", "XOF", "Africa/Niamey"),
    ("NG", "Nigeria", "en", "NGN", "Africa/Lagos"),
    ("RW", "Rwanda", "en", "RWF", "Africa/Kigali"),
    ("ST", "São Tomé and Príncipe", "en", "STN", "Africa/Sao_Tome"),
    ("SN", "Senegal", "fr", "XOF", "Africa/Dakar"),
    ("SC", "Seychelles", "en", "SCR", "Indian/Mahe"),
    ("SL", "Sierra Leone", "en", "SLE", "Africa/Freetown"),
    ("SO", "Somalia", "ar", "SOS", "Africa/Mogadishu"),
    ("ZA", "South Africa", "en", "ZAR", "Africa/Johannesburg"),
    ("SS", "South Sudan", "en", "SSP", "Africa/Juba"),
    ("SD", "Sudan", "ar", "SDG", "Africa/Khartoum"),
    ("TZ", "Tanzania", "en", "TZS", "Africa/Dar_es_Salaam"),
    ("TG", "Togo", "fr", "XOF", "Africa/Lome"),
    ("TN", "Tunisia", "ar", "TND", "Africa/Tunis"),
    ("UG", "Uganda", "en", "UGX", "Africa/Kampala"),
    ("ZM", "Zambia", "en", "ZMW", "Africa/Lusaka"),
    ("ZW", "Zimbabwe", "en", "ZWL", "Africa/Harare"),
]
# Append Africa to the master country list (sort order 100+ so they group after
# the anchor markets but stay alphabetical among themselves).
for _i, (_c, _n, _l, _cur, _tz) in enumerate(sorted(AFRICA_COUNTRIES, key=lambda x: x[1])):
    SEED_COUNTRIES.append((_c, _n, _l, _cur, _tz, 100 + _i))

# Set of African ISO codes — used to give a correct regional fallback pointer.
AFRICA_CODES = {c[0] for c in AFRICA_COUNTRIES}

# ── Official proof sources (government / regulator / standards publisher) ──────
# Migrated from proof_sources.OFFICIAL_SOURCES and tagged by country.
# (key, label, publisher, authority, url, country) — all URLs verified against
# the official government / standards-publisher domains.
SEED_PROOF_SOURCES = [
    # India — Government of India / BIS
    ("india_bis", "Bureau of Indian Standards (BIS)", "Bureau of Indian Standards",
     "Government of India / National Standards Body", "https://www.bis.gov.in/", "IN"),
    ("india_nbc", "National Building Code of India 2016 (NBC 2016)", "Bureau of Indian Standards",
     "Government of India / National Standards Body",
     "https://www.bis.gov.in/standards/technical-department/national-building-code/", "IN"),
    ("india_mohua", "Ministry of Housing & Urban Affairs (model building bye-laws)",
     "Government of India", "Government of India / Regulator", "https://mohua.gov.in/", "IN"),
    # United States
    ("aci_318", "ACI 318 Building Code Requirements for Structural Concrete",
     "American Concrete Institute", "Official standards publisher", "https://www.concrete.org/", "US"),
    ("aisc_360", "AISC 360 Specification for Structural Steel Buildings",
     "American Institute of Steel Construction", "Official standards publisher",
     "https://www.aisc.org/publications/steel-standards/", "US"),
    ("asce_7", "ASCE/SEI 7 Minimum Design Loads and Associated Criteria",
     "American Society of Civil Engineers", "Official standards publisher",
     "https://www.asce.org/publications-and-news/asce-7", "US"),
    ("icc_ibc", "International Building Code (IBC)", "International Code Council",
     "Model code developer", "https://codes.iccsafe.org/", "US"),
    ("usgs_hazard", "USGS Seismic Design Ground Motions / hazard web services",
     "U.S. Geological Survey", "United States Government",
     "https://earthquake.usgs.gov/hazards/designmaps/", "US"),
    ("asce_hazard_tool", "ASCE 7 Hazard Tool (wind / seismic / snow parameters)",
     "American Society of Civil Engineers", "Official standards publisher",
     "https://ascehazardtool.org/", "US"),
    # Canada — Government of Canada / CSA
    ("nbc_2020", "National Building Code of Canada 2020", "National Research Council Canada",
     "Government of Canada",
     "https://nrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-building-code-canada-2020", "CA"),
    ("nrc_pub_archive", "NRC Publications Archive (free electronic Codes Canada)",
     "National Research Council Canada", "Government of Canada",
     "https://nrc-publications.canada.ca/eng/view/object/?id=515340b5-f4e0-4798-be69-692e4ec423e8", "CA"),
    ("eccc_climate", "Engineering Climate Datasets (design climate data)",
     "Environment and Climate Change Canada", "Government of Canada",
     "https://climate.weather.gc.ca/prods_servs/engineering_e.html", "CA"),
    ("nrcan_seismic", "2020 National Seismic Hazard Model / hazard values",
     "Natural Resources Canada — Earthquakes Canada", "Government of Canada",
     "https://earthquakescanada.nrcan.gc.ca/", "CA"),
    ("csa_a23_3", "CSA A23.3:19 Design of concrete structures", "CSA Group",
     "Official standards publisher", "https://www.csagroup.org/store/product/CSA%20A23.3%3A19/", "CA"),
    ("csa_s16", "CSA S16:19 Design of steel structures", "CSA Group",
     "Official standards publisher", "https://www.csagroup.org/store/product/CSA%20S16%3A19/", "CA"),
    ("csa_o86", "CSA O86:19 Engineering design in wood", "CSA Group",
     "Official standards publisher", "https://www.csagroup.org/store/product/CSA%20O86%3A19/", "CA"),
    # Europe / United Kingdom
    ("eurocodes_jrc", "EN Eurocodes (official European Commission portal)",
     "European Commission — Joint Research Centre", "European Commission",
     "https://eurocodes.jrc.ec.europa.eu/", "GB"),
    ("ec_construction", "Eurocodes — EC Internal Market (Construction)", "European Commission",
     "European Commission", "https://single-market-economy.ec.europa.eu/sectors/construction/eurocodes_en", "GB"),
    ("cen", "CEN European Standards (EN)", "European Committee for Standardization",
     "Official standards publisher",
     "https://www.cencenelec.eu/european-standardization/european-standards/", "GB"),
    ("bsi", "BSI — British Standards (BS EN + UK National Annexes)", "British Standards Institution",
     "National Standards Body (United Kingdom)", "https://www.bsigroup.com/", "GB"),
    ("gov_uk_building_regs", "UK Building Regulations — Approved Documents", "UK Government (MHCLG)",
     "Government (United Kingdom) / Regulator",
     "https://www.gov.uk/government/collections/approved-documents", "GB"),
    # Australia
    ("standards_au", "Standards Australia (AS / AS/NZS)", "Standards Australia",
     "Official standards publisher", "https://www.standards.org.au/", "AU"),
    ("abcb_ncc", "National Construction Code (NCC)", "Australian Building Codes Board",
     "Government of Australia / Regulator", "https://ncc.abcb.gov.au/", "AU"),
    # UAE / Gulf
    ("uae_moiat", "UAE codes — Ministry of Industry & Advanced Technology / Civil Defence",
     "Government of the UAE", "Local authority / Regulator", "https://www.moiat.gov.ae/", "AE"),
    # ── Africa ────────────────────────────────────────────────────────────────
    ("arso", "African Organisation for Standardisation (ARSO)", "ARSO (African Union)",
     "Continental standards body", "https://www.arso-oran.org/", ""),
    ("sabs", "South African Bureau of Standards (SANS 10100/10160/10162/10400)",
     "South African Bureau of Standards", "Government of South Africa / National Standards Body",
     "https://www.sabs.co.za/", "ZA"),
    ("son_ng", "Standards Organisation of Nigeria (National Building Code)",
     "Standards Organisation of Nigeria", "Government of Nigeria / National Standards Body",
     "https://son.gov.ng/", "NG"),
    ("kebs", "Kenya Bureau of Standards (Kenya Building Code / Eurocode adoption)",
     "Kenya Bureau of Standards", "Government of Kenya / National Standards Body",
     "https://www.kebs.org/", "KE"),
    ("hbrc_eg", "Housing & Building National Research Center — Egyptian Codes (ECP)",
     "Housing and Building National Research Center", "Government of Egypt / Regulator",
     "https://www.hbrc.edu.eg/en/activities/codes", "EG"),
    ("imanor_ma", "Institut Marocain de Normalisation (IMANOR) — RPS seismic regulation",
     "IMANOR", "Government of Morocco / National Standards Body", "https://www.imanor.gov.ma/", "MA"),
]

# (country, discipline, code, edition, title, maturity, clause_labels, proof_keys, notes)
# Notes capture the edition in force. Maturity: draft / verified / production.
SEED_CODE_PACKS = [
    # ── India (Government of India / BIS) ──────────────────────────────────────
    ("IN", "concrete", "IS 456", "2000", "Plain and Reinforced Concrete — Code of Practice", "verified",
     {"flexure": "Cl. 38", "shear": "Cl. 40", "deflection": "Cl. 23.2", "development": "Cl. 26.2"},
     ["india_bis", "india_nbc"], "IS 456:2000 (4th revision) is in force; latest Amendment No. 6 (2024)."),
    ("IN", "steel", "IS 800", "2007", "General Construction in Steel (Limit State)", "verified",
     {"tension": "Sec. 6", "compression": "Sec. 7", "flexure": "Sec. 8", "connections": "Sec. 10"},
     ["india_bis"], "IS 800:2007 introduced limit-state design; current edition."),
    ("IN", "loads", "IS 875", "1987/2015", "Design Loads for Buildings (Parts 1–5)", "verified",
     {"dead": "Part 1", "live": "Part 2", "wind": "Part 3 (2015)", "snow": "Part 4"},
     ["india_bis"], "Parts 1,2,4,5:1987; Part 3 (wind) revised 2015."),
    ("IN", "seismic", "IS 1893", "Part 1 : 2016", "Criteria for Earthquake Resistant Design", "verified",
     {"base_shear": "Cl. 7.6", "zone_factor": "Table 3", "response": "Cl. 6.4"},
     ["india_bis"], "IS 1893(Part 1):2016 is the code IN FORCE. The 2025 revision was withdrawn by BIS after MoHUA concerns."),
    ("IN", "ductile_detailing", "IS 13920", "2016", "Ductile Detailing of RC Structures (Seismic)", "draft",
     {"beams": "Cl. 6", "columns": "Cl. 7", "joints": "Cl. 9"},
     ["india_bis"], "IS 13920:2016 — reference code pack (no dedicated calculator yet); mandatory for seismic zones III–V."),
    # ── United States ──────────────────────────────────────────────────────────
    ("US", "concrete", "ACI 318", "-19", "Building Code Requirements for Structural Concrete", "draft",
     {"flexure": "Ch. 22", "shear": "Ch. 22", "detailing": "Ch. 25"}, ["aci_318", "icc_ibc"],
     "ACI 318-19 referenced by IBC. Confirm the edition adopted by the local jurisdiction."),
    ("US", "steel", "AISC 360", "-22", "Specification for Structural Steel Buildings", "draft",
     {"tension": "Ch. D", "compression": "Ch. E", "flexure": "Ch. F", "connections": "Ch. J"},
     ["aisc_360", "icc_ibc"], "AISC 360-22 is the current specification."),
    ("US", "loads", "ASCE 7", "-22", "Minimum Design Loads and Associated Criteria", "draft",
     {"combinations": "Ch. 2", "wind": "Ch. 26-31", "seismic": "Ch. 11-23", "snow": "Ch. 7"},
     ["asce_7", "usgs_hazard", "asce_hazard_tool"], "ASCE/SEI 7-22; seismic/wind parameters from USGS + ASCE Hazard Tool."),
    ("US", "building", "IBC", "2024", "International Building Code", "draft",
     {"structural": "Ch. 16", "concrete": "Ch. 19", "steel": "Ch. 22"}, ["icc_ibc"],
     "IBC is a model code; the enforceable edition is set by each state/municipality."),
    # ── Canada (Government of Canada / CSA) ────────────────────────────────────
    ("CA", "loads", "NBC", "2020", "National Building Code of Canada — Part 4 Structural", "draft",
     {"snow": "Cl. 4.1.6", "wind": "Cl. 4.1.7", "seismic": "Cl. 4.1.8", "combinations": "Cl. 4.1.3"},
     ["nbc_2020", "nrc_pub_archive", "eccc_climate", "nrcan_seismic"],
     "NBC 2020 is a model code; provinces adopt/amend (e.g., OBC, ABC). Free PDF via NRC archive."),
    ("CA", "concrete", "CSA A23.3", ":19", "Design of Concrete Structures", "draft",
     {"flexure": "Cl. 10", "shear": "Cl. 11", "columns": "Cl. 10.9"}, ["csa_a23_3", "nbc_2020"],
     "CSA A23.3:19 referenced by NBC 2020."),
    ("CA", "steel", "CSA S16", ":19", "Design of Steel Structures", "draft",
     {"tension": "Cl. 13.2", "compression": "Cl. 13.3", "flexure": "Cl. 13.5"}, ["csa_s16", "nbc_2020"],
     "CSA S16:19 referenced by NBC 2020."),
    ("CA", "wood", "CSA O86", ":19", "Engineering Design in Wood", "draft",
     {"bending": "Cl. 6", "compression": "Cl. 6.5", "fasteners": "Cl. 12"}, ["csa_o86", "nbc_2020"],
     "CSA O86:19 referenced by NBC 2020."),
    # ── United Kingdom / Europe (Eurocodes) ───────────────────────────────────
    ("GB", "basis", "Eurocode 0", "EN 1990", "Basis of Structural Design", "draft",
     {"combinations": "Sec. 6", "partial_factors": "Table A1.2"}, ["eurocodes_jrc", "cen", "bsi"],
     "Use with the UK National Annex (BSI). 2nd-generation Eurocodes are being published."),
    ("GB", "loads", "Eurocode 1", "EN 1991", "Actions on Structures", "draft",
     {"dead": "Part 1-1", "wind": "Part 1-4", "snow": "Part 1-3"}, ["eurocodes_jrc", "cen", "bsi"],
     "Apply UK National Annex nationally determined parameters."),
    ("GB", "concrete", "Eurocode 2", "EN 1992", "Design of Concrete Structures", "draft",
     {"flexure": "Sec. 6.1", "shear": "Sec. 6.2", "detailing": "Sec. 8"}, ["eurocodes_jrc", "cen", "bsi"],
     "EN 1992 + UK National Annex."),
    ("GB", "steel", "Eurocode 3", "EN 1993", "Design of Steel Structures", "draft",
     {"tension": "Sec. 6.2", "buckling": "Sec. 6.3", "connections": "EN 1993-1-8"},
     ["eurocodes_jrc", "cen", "bsi"], "EN 1993 + UK National Annex."),
    ("GB", "geotechnical", "Eurocode 7", "EN 1997", "Geotechnical Design", "draft",
     {"design_approaches": "Sec. 2.4"}, ["eurocodes_jrc", "cen", "bsi"], "EN 1997 + UK National Annex."),
    ("GB", "seismic", "Eurocode 8", "EN 1998", "Design for Earthquake Resistance", "draft",
     {"response_spectrum": "Sec. 3.2", "behaviour_factor": "Sec. 5"}, ["eurocodes_jrc", "cen", "bsi"],
     "EN 1998; UK is low-seismicity — confirm National Annex applicability."),
    ("GB", "building", "Approved Documents", "current", "UK Building Regulations (Approved Docs A–S)", "draft",
     {"structure": "Part A"}, ["gov_uk_building_regs", "bsi"],
     "Statutory guidance for England; Scotland/Wales/NI have their own regulations."),
    # ── Australia ──────────────────────────────────────────────────────────────
    ("AU", "concrete", "AS 3600", "2018", "Concrete Structures", "draft",
     {"flexure": "Sec. 8", "shear": "Sec. 8.2", "columns": "Sec. 10"}, ["standards_au", "abcb_ncc"],
     "AS 3600:2018 (incl. Amendment 1); referenced by the NCC."),
    ("AU", "steel", "AS 4100", "2020", "Steel Structures", "draft",
     {"tension": "Sec. 7", "compression": "Sec. 6", "flexure": "Sec. 5"}, ["standards_au", "abcb_ncc"],
     "AS 4100:2020; referenced by the NCC."),
    ("AU", "loads", "AS/NZS 1170", "2002+", "Structural Design Actions", "draft",
     {"permanent_imposed": "Part 1", "wind": "Part 2", "snow": "Part 3", "seismic": "Part 4 (AS 1170.4)"},
     ["standards_au", "abcb_ncc"], "AS/NZS 1170 Parts 0–3; earthquake actions per AS 1170.4:2007."),
    ("AU", "timber", "AS 1720", "1", "Timber Structures", "draft",
     {"design": "AS 1720.1"}, ["standards_au", "abcb_ncc"], "AS 1720.1 design methods; referenced by the NCC."),
    ("AU", "building", "NCC", "2022", "National Construction Code", "draft",
     {"structure": "Vol. 1 Part B1"}, ["abcb_ncc"], "NCC is the regulatory code; free access via ABCB."),
    # ── UAE / Gulf ─────────────────────────────────────────────────────────────
    ("AE", "concrete", "ACI 318", "-19", "Structural Concrete (commonly adopted)", "draft",
     {"flexure": "Ch. 22"}, ["aci_318", "uae_moiat"],
     "UAE authorities commonly adopt ACI/ASCE; requirements vary by emirate (e.g., Dubai, Abu Dhabi)."),
    ("AE", "loads", "ASCE 7", "-22", "Design Loads (commonly adopted)", "draft",
     {"wind": "Ch. 26-31"}, ["asce_7", "uae_moiat"],
     "Confirm the emirate authority's adopted loading basis and wind/seismic parameters."),
    # ── South Africa (SABS / SANS) ─────────────────────────────────────────────
    ("ZA", "loads", "SANS 10160", "2011", "Basis of Structural Design and Actions", "draft",
     {"basis": "Part 1", "self_weight_imposed": "Part 2", "wind": "Part 3", "seismic": "Part 4"},
     ["sabs", "arso"], "SANS 10160 (8 parts) — the SA loading/actions code."),
    ("ZA", "concrete", "SANS 10100", "1", "Structural Use of Concrete", "draft",
     {"design": "Part 1"}, ["sabs", "arso"], "SANS 10100-1 concrete design; SANS 10400 is the building regulation."),
    ("ZA", "steel", "SANS 10162", "1", "Structural Use of Steel (limit states)", "draft",
     {"design": "Part 1"}, ["sabs", "arso"], "SANS 10162-1 hot-rolled steelwork."),
    ("ZA", "building", "SANS 10400", "current", "National Building Regulations", "draft",
     {"structure": "Part B"}, ["sabs"], "SANS 10400 series — deemed-to-satisfy building regulations."),
    # ── Nigeria (SON) ──────────────────────────────────────────────────────────
    ("NG", "building", "National Building Code", "2006", "Nigeria National Building Code", "draft",
     {"structure": "Part 3"}, ["son_ng", "arso"],
     "Nigeria commonly designs to BS/Eurocode; confirm the state's adopted structural basis."),
    ("NG", "concrete", "BS/Eurocode 2", "adopted", "Concrete (adopted basis)", "draft",
     {"flexure": "EN 1992 Sec. 6"}, ["eurocodes_jrc", "bsi", "son_ng"],
     "Commonly BS 8110 / Eurocode 2 with SON oversight — verify local adoption."),
    # ── Kenya (KEBS) ───────────────────────────────────────────────────────────
    ("KE", "loads", "Eurocode (Kenya adoption)", "EN 1991", "Actions (Kenya Building Code)", "draft",
     {"actions": "EN 1991"}, ["kebs", "eurocodes_jrc", "arso"],
     "Kenya's revised Building Code adopts the Eurocodes via KEBS — confirm National Annex/NDPs."),
    ("KE", "concrete", "Eurocode 2 (Kenya adoption)", "EN 1992", "Concrete Design", "draft",
     {"flexure": "Sec. 6.1"}, ["kebs", "eurocodes_jrc"], "EN 1992 as adopted by KEBS."),
    # ── Egypt (HBRC) ───────────────────────────────────────────────────────────
    ("EG", "concrete", "ECP 203", "2018", "Egyptian Code for Design & Construction of RC Structures", "draft",
     {"flexure": "Ch. 4", "shear": "Ch. 4"}, ["hbrc_eg", "arso"], "ECP 203 (HBRC), latest edition; confirm current print."),
    ("EG", "loads", "ECP 201", "current", "Egyptian Loads Code (incl. seismic)", "draft",
     {"wind": "Ch. 3", "seismic": "Ch. 8"}, ["hbrc_eg", "arso"],
     "ECP 201 — equivalent static + response spectrum seismic method."),
    # ── Ethiopia (EBCS / ES — Eurocode based) ──────────────────────────────────
    ("ET", "concrete", "EBCS EN 1992", "2013", "Design of Concrete Structures (ES EN)", "draft",
     {"flexure": "Sec. 6.1"}, ["eurocodes_jrc", "arso"],
     "Ethiopia's EBCS/ES adopt the Eurocodes (EBCS EN 1992). EBCS-8 governs seismic. Confirm current ES edition."),
    ("ET", "seismic", "EBCS 8 / EN 1998", "adopted", "Design for Earthquake Resistance", "draft",
     {"response_spectrum": "EN 1998 Sec. 3"}, ["eurocodes_jrc", "arso"],
     "Ethiopian seismic design per EBCS-8 (Eurocode 8 based)."),
    # ── Morocco (RPS) ──────────────────────────────────────────────────────────
    ("MA", "seismic", "RPS 2000 (rev. 2011)", "2011", "Règlement de Construction Parasismique", "draft",
     {"seismic": "RPS 2011"}, ["imanor_ma", "arso"],
     "Morocco's earthquake-resistant regulation RPS 2000, revised RPS 2011 (Eurocode 8 informed)."),
    ("MA", "concrete", "BAEL / Eurocode 2", "adopted", "Concrete (adopted basis)", "draft",
     {"flexure": "EN 1992 / BAEL"}, ["imanor_ma", "eurocodes_jrc"],
     "Concrete commonly BAEL or Eurocode 2 — confirm adoption with IMANOR."),
    # ── Algeria (RPA) ──────────────────────────────────────────────────────────
    ("DZ", "seismic", "RPA 99 (v. 2003)", "2003", "Règles Parasismiques Algériennes", "draft",
     {"seismic": "RPA99/2003"}, ["arso"],
     "Algeria seismic design per RPA 99 / version 2003 (RPA 2024 revision emerging), issued via CGS. Confirm current text."),
    ("DZ", "concrete", "CBA 93 / BAEL", "adopted", "Concrete (adopted basis)", "draft",
     {"flexure": "CBA 93"}, ["arso", "eurocodes_jrc"],
     "Concrete commonly CBA 93 / BAEL; confirm nationally adopted edition."),
]

# ── UI + engineering strings, per locale ──────────────────────────────────────
# namespace -> key -> {locale: value}
STRINGS: Dict[str, Dict[str, Dict[str, str]]] = {
    "nav": {
        "dashboard":  {"en": "Dashboard",       "fr": "Tableau de bord", "hi": "डैशबोर्ड",       "ar": "لوحة التحكم"},
        "company":    {"en": "Company",         "fr": "Entreprise",      "hi": "कंपनी",           "ar": "الشركة"},
        "projects":   {"en": "Projects",        "fr": "Projets",         "hi": "परियोजनाएँ",       "ar": "المشاريع"},
        "tasks":      {"en": "Tasks",           "fr": "Tâches",          "hi": "कार्य",            "ar": "المهام"},
        "workers":    {"en": "Workers",         "fr": "Travailleurs",    "hi": "श्रमिक",           "ar": "العمال"},
        "clients":    {"en": "Clients",         "fr": "Clients",         "hi": "ग्राहक",           "ar": "العملاء"},
        "finance":    {"en": "Finance",         "fr": "Finances",        "hi": "वित्त",            "ar": "المالية"},
        "documents":  {"en": "Documents",       "fr": "Documents",       "hi": "दस्तावेज़",         "ar": "المستندات"},
        "inventory":  {"en": "Inventory",       "fr": "Inventaire",      "hi": "इन्वेंटरी",        "ar": "المخزون"},
        "safety":     {"en": "Safety",          "fr": "Sécurité",        "hi": "सुरक्षा",          "ar": "السلامة"},
        "structural": {"en": "Structural",      "fr": "Structure",       "hi": "संरचनात्मक",       "ar": "الإنشائي"},
        "intlcodes":  {"en": "Intl Codes",      "fr": "Codes intl.",     "hi": "अंतर. कोड",        "ar": "الأكواد الدولية"},
        "steel":      {"en": "Steel",           "fr": "Acier",           "hi": "इस्पात",           "ar": "الصلب"},
        "nbc":        {"en": "NBC Canada",      "fr": "CNB Canada",      "hi": "एनबीसी कनाडा",     "ar": "كود كندا"},
        "scheduling": {"en": "Scheduling",      "fr": "Planification",   "hi": "अनुसूची",          "ar": "الجدولة"},
        "commercial": {"en": "Commercial",      "fr": "Commercial",      "hi": "वाणिज्यिक",        "ar": "التجاري"},
        "controls":   {"en": "Controls",        "fr": "Contrôles",       "hi": "नियंत्रण",         "ar": "الضوابط"},
        "siteops":    {"en": "Site Ops",        "fr": "Ops. chantier",   "hi": "साइट ऑप्स",        "ar": "عمليات الموقع"},
        "attendance": {"en": "Attendance",      "fr": "Présence",        "hi": "उपस्थिति",         "ar": "الحضور"},
        "quality":    {"en": "Quality",         "fr": "Qualité",         "hi": "गुणवत्ता",         "ar": "الجودة"},
        "reports":    {"en": "Reports",         "fr": "Rapports",        "hi": "रिपोर्ट",          "ar": "التقارير"},
        "bim":        {"en": "BIM",             "fr": "BIM",             "hi": "बीआईएम",           "ar": "نمذجة BIM"},
        "team_roles": {"en": "Team & Roles",    "fr": "Équipe & rôles",  "hi": "टीम और भूमिकाएँ",   "ar": "الفريق والأدوار"},
        "saas":       {"en": "Subscription",    "fr": "Abonnement",      "hi": "सदस्यता",          "ar": "الاشتراك"},
        "users":      {"en": "Users",           "fr": "Utilisateurs",    "hi": "उपयोगकर्ता",       "ar": "المستخدمون"},
    },
    "common": {
        "save":     {"en": "Save",      "fr": "Enregistrer", "hi": "सहेजें",   "ar": "حفظ"},
        "cancel":   {"en": "Cancel",    "fr": "Annuler",     "hi": "रद्द करें", "ar": "إلغاء"},
        "delete":   {"en": "Delete",    "fr": "Supprimer",   "hi": "हटाएँ",    "ar": "حذف"},
        "add":      {"en": "Add",       "fr": "Ajouter",     "hi": "जोड़ें",    "ar": "إضافة"},
        "edit":     {"en": "Edit",      "fr": "Modifier",    "hi": "संपादित करें", "ar": "تعديل"},
        "search":   {"en": "Search",    "fr": "Rechercher",  "hi": "खोजें",    "ar": "بحث"},
        "loading":  {"en": "Loading…",  "fr": "Chargement…", "hi": "लोड हो रहा है…", "ar": "جارٍ التحميل…"},
        "logout":   {"en": "Log out",   "fr": "Déconnexion", "hi": "लॉग आउट",  "ar": "تسجيل الخروج"},
        "language": {"en": "Language",  "fr": "Langue",      "hi": "भाषा",     "ar": "اللغة"},
    },
    "auth": {
        "login":    {"en": "Log in",   "fr": "Connexion",   "hi": "लॉग इन",   "ar": "تسجيل الدخول"},
        "username": {"en": "Username",  "fr": "Nom d'utilisateur", "hi": "उपयोगकर्ता नाम", "ar": "اسم المستخدم"},
        "password": {"en": "Password",  "fr": "Mot de passe", "hi": "पासवर्ड",  "ar": "كلمة المرور"},
    },
    "demo": {
        "load":    {"en": "Load demo data",   "fr": "Charger les données de démo", "hi": "डेमो डेटा लोड करें",  "ar": "تحميل بيانات العرض"},
        "reset":   {"en": "Delete demo data", "fr": "Supprimer les données de démo", "hi": "डेमो डेटा हटाएँ", "ar": "حذف بيانات العرض"},
        "banner":  {"en": "Demo workspace — data is illustrative only.",
                    "fr": "Espace de démonstration — données à titre indicatif.",
                    "hi": "डेमो कार्यक्षेत्र — डेटा केवल उदाहरण है।",
                    "ar": "مساحة عرض — البيانات توضيحية فقط."},
    },
    "engineering": {
        "flexure":     {"en": "Flexure",        "fr": "Flexion",       "hi": "बंकन",       "ar": "الانحناء"},
        "shear":       {"en": "Shear",          "fr": "Cisaillement",  "hi": "अपरूपण",     "ar": "القص"},
        "deflection":  {"en": "Deflection",     "fr": "Flèche",        "hi": "विक्षेपण",    "ar": "الانحراف"},
        "utilization": {"en": "Utilization",    "fr": "Taux d'utilisation", "hi": "उपयोग अनुपात", "ar": "نسبة الاستخدام"},
        "pass":        {"en": "Pass",           "fr": "Conforme",      "hi": "उत्तीर्ण",    "ar": "مطابق"},
        "revise":      {"en": "Revise",         "fr": "À revoir",      "hi": "संशोधित करें", "ar": "يحتاج مراجعة"},
        "proof":       {"en": "Proof & sources","fr": "Preuve & sources", "hi": "प्रमाण और स्रोत", "ar": "الإثبات والمصادر"},
    },
}


def seed_platform_i18n(db: Session) -> dict:
    """Idempotently load languages, countries, code packs, proofs and strings."""
    counts = {"locales": 0, "countries": 0, "proofs": 0, "code_packs": 0, "strings": 0}

    for code, name, native, direction, order in SEED_LOCALES:
        if not db.query(Locale).filter_by(code=code).first():
            db.add(Locale(code=code, name=name, native_name=native,
                          direction=direction, sort_order=order, enabled=True))
            counts["locales"] += 1

    for code, name, loc, cur, tz, order in SEED_COUNTRIES:
        if not db.query(Country).filter_by(code=code).first():
            db.add(Country(code=code, name=name, default_locale=loc, currency=cur,
                           timezone=tz, sort_order=order, enabled=True))
            counts["countries"] += 1

    # Upsert proof sources so verified official links replace any older values.
    for key, label, pub, auth, url, cc in SEED_PROOF_SOURCES:
        row = db.query(ProofSource).filter_by(key=key).first()
        if row:
            row.label, row.publisher, row.authority = label, pub, auth
            row.url, row.country_code = url, cc
        else:
            db.add(ProofSource(key=key, label=label, publisher=pub, authority=auth,
                               url=url, country_code=cc))
            counts["proofs"] += 1

    # Upsert code packs so edition / clauses / notes / proof links stay current.
    for cc, disc, code, ed, title, mat, clauses, proofs, notes in SEED_CODE_PACKS:
        row = db.query(CodePack).filter_by(country_code=cc, discipline=disc, code_name=code).first()
        if row:
            row.edition, row.title, row.maturity = ed, title, mat
            row.clause_labels, row.proof_keys, row.notes = clauses, proofs, notes
            row.enabled = True
        else:
            db.add(CodePack(country_code=cc, discipline=disc, code_name=code, edition=ed,
                            title=title, maturity=mat, clause_labels=clauses,
                            proof_keys=proofs, notes=notes, enabled=True))
            counts["code_packs"] += 1

    for ns, keys in STRINGS.items():
        for key, values in keys.items():
            for locale, value in values.items():
                exists = db.query(LocaleString).filter_by(
                    locale=locale, namespace=ns, skey=key).first()
                if not exists:
                    db.add(LocaleString(locale=locale, namespace=ns, skey=key, value=value))
                    counts["strings"] += 1
    db.commit()
    return counts


def build_bundle(db: Session, locale: str) -> dict:
    """Return the full i18n bundle for a locale, falling back to English per key."""
    loc = db.query(Locale).filter_by(code=locale, enabled=True).first()
    if not loc:
        locale = "en"
        loc = db.query(Locale).filter_by(code="en").first()

    # Build en base then overlay requested locale.
    def rows(code):
        out: Dict[str, Dict[str, str]] = {}
        for r in db.query(LocaleString).filter_by(locale=code).all():
            out.setdefault(r.namespace, {})[r.skey] = r.value
        return out

    base = rows("en")
    if locale != "en":
        for ns, kv in rows(locale).items():
            base.setdefault(ns, {}).update(kv)

    return {
        "locale": locale,
        "direction": loc.direction if loc else "ltr",
        "strings": base,
    }


def list_locales(db: Session) -> List[dict]:
    return [
        {"code": l.code, "name": l.name, "native_name": l.native_name,
         "direction": l.direction}
        for l in db.query(Locale).filter_by(enabled=True).order_by(Locale.sort_order).all()
    ]


def country_bundle(db: Session, country_code: str) -> dict:
    """Country profile + its code packs with resolved proof sources."""
    c = db.query(Country).filter_by(code=country_code).first()
    if not c:
        return {"error": f"Unknown country {country_code}"}
    packs = db.query(CodePack).filter_by(country_code=country_code, enabled=True).all()
    proof_by_key = {p.key: p for p in db.query(ProofSource).all()}

    def resolve(keys):
        out = []
        for k in keys or []:
            p = proof_by_key.get(k)
            if p:
                out.append({"key": p.key, "label": p.label, "publisher": p.publisher,
                            "authority": p.authority, "url": p.url})
        return out

    code_packs = [
        {"discipline": p.discipline, "code_name": p.code_name, "edition": p.edition,
         "title": p.title, "maturity": p.maturity, "clause_labels": p.clause_labels,
         "notes": getattr(p, "notes", None), "sources": resolve(p.proof_keys)}
        for p in packs
    ]

    # Honest fallback: if a country has no nationally-developed structural code
    # registered, we do NOT invent clauses. We point to the national/continental
    # standards body and the commonly-adopted basis, and flag that the engineer
    # must confirm local adoption.
    fallback = False
    if not code_packs:
        fallback = True
        is_africa = country_code in AFRICA_CODES
        keys = (["arso", "eurocodes_jrc", "bsi"] if is_africa else ["eurocodes_jrc", "bsi"])
        code_packs = [{
            "discipline": "regional",
            "code_name": "Adopted basis — confirm with national standards body",
            "edition": "", "title": "No nationally-developed structural code registered",
            "maturity": "draft", "clause_labels": {},
            "notes": ("This jurisdiction commonly adopts Eurocodes or British Standards "
                      "through its national standards body. Confirm the code and edition in "
                      "force with the national body"
                      + (" and ARSO (African Organisation for Standardisation)." if is_africa else ".")),
            "sources": resolve(keys),
        }]

    return {
        "country": {"code": c.code, "name": c.name, "default_locale": c.default_locale,
                    "currency": c.currency, "timezone": c.timezone},
        "code_packs": code_packs,
        "uses_adopted_basis_fallback": fallback,
        "legal_note": ("Building law is adopted by the project jurisdiction. Verify local "
                       "amendments, national annexes, authority requirements and the enforced "
                       "edition. Preliminary calculators require review by a licensed engineer."),
    }
