"""
Official-source metadata for NagaForge engineering calculations.

Every URL here points to a government body, a regulator, or the official
standards publisher that owns the code. The link is EVIDENCE of the governing
publication or official data authority — it does not reproduce copyrighted
standard text. Links were verified against the official domains.

Authority labels: "Government", "Regulator", "Official standards publisher",
"Local authority".
"""
from typing import Optional


OFFICIAL_SOURCES = {
    # ── India — Government of India / BIS ─────────────────────────────────────
    "india_bis": {
        "label": "Bureau of Indian Standards (BIS)",
        "publisher": "Bureau of Indian Standards",
        "authority": "Government of India / National Standards Body",
        "url": "https://www.bis.gov.in/",
    },
    "india_nbc": {
        "label": "National Building Code of India 2016 (NBC 2016)",
        "publisher": "Bureau of Indian Standards",
        "authority": "Government of India / National Standards Body",
        "url": "https://www.bis.gov.in/standards/technical-department/national-building-code/",
    },
    "india_mohua": {
        "label": "Ministry of Housing and Urban Affairs (model building bye-laws)",
        "publisher": "Government of India",
        "authority": "Government of India / Regulator",
        "url": "https://mohua.gov.in/",
    },

    # ── United States — publishers + USGS ─────────────────────────────────────
    "aci_318": {
        "label": "ACI 318 Building Code Requirements for Structural Concrete",
        "publisher": "American Concrete Institute",
        "authority": "Official standards publisher",
        "url": "https://www.concrete.org/",
    },
    "aisc_360": {
        "label": "AISC 360 Specification for Structural Steel Buildings",
        "publisher": "American Institute of Steel Construction",
        "authority": "Official standards publisher",
        "url": "https://www.aisc.org/publications/steel-standards/",
    },
    "asce_7": {
        "label": "ASCE/SEI 7 Minimum Design Loads and Associated Criteria",
        "publisher": "American Society of Civil Engineers",
        "authority": "Official standards publisher",
        "url": "https://www.asce.org/publications-and-news/asce-7",
    },
    "icc_ibc": {
        "label": "International Building Code (IBC)",
        "publisher": "International Code Council",
        "authority": "Model code developer",
        "url": "https://codes.iccsafe.org/",
    },
    "usgs_hazard": {
        "label": "USGS Seismic Design Ground Motions / hazard web services",
        "publisher": "U.S. Geological Survey",
        "authority": "United States Government",
        "url": "https://earthquake.usgs.gov/hazards/designmaps/",
    },
    "asce_hazard_tool": {
        "label": "ASCE 7 Hazard Tool (wind/seismic/snow design parameters)",
        "publisher": "American Society of Civil Engineers",
        "authority": "Official standards publisher",
        "url": "https://ascehazardtool.org/",
    },

    # ── Canada — Government of Canada / CSA ────────────────────────────────────
    "nbc_2020": {
        "label": "National Building Code of Canada 2020",
        "publisher": "National Research Council Canada",
        "authority": "Government of Canada",
        "url": "https://nrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-building-code-canada-2020",
    },
    "nrc_pub_archive": {
        "label": "NRC Publications Archive (free electronic Codes Canada)",
        "publisher": "National Research Council Canada",
        "authority": "Government of Canada",
        "url": "https://nrc-publications.canada.ca/eng/view/object/?id=515340b5-f4e0-4798-be69-692e4ec423e8",
    },
    "eccc_climate": {
        "label": "Engineering Climate Datasets (design climate data)",
        "publisher": "Environment and Climate Change Canada",
        "authority": "Government of Canada",
        "url": "https://climate.weather.gc.ca/prods_servs/engineering_e.html",
    },
    "nrcan_seismic": {
        "label": "2020 National Seismic Hazard Model / hazard values",
        "publisher": "Natural Resources Canada — Earthquakes Canada",
        "authority": "Government of Canada",
        "url": "https://earthquakescanada.nrcan.gc.ca/",
    },
    "csa_a23_3": {
        "label": "CSA A23.3:19 Design of concrete structures",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20A23.3%3A19/",
    },
    "csa_s16": {
        "label": "CSA S16:19 Design of steel structures",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20S16%3A19/",
    },
    "csa_o86": {
        "label": "CSA O86:19 Engineering design in wood",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20O86%3A19/",
    },

    # ── Europe / United Kingdom ───────────────────────────────────────────────
    "eurocodes_jrc": {
        "label": "EN Eurocodes (official European Commission portal)",
        "publisher": "European Commission — Joint Research Centre",
        "authority": "European Commission",
        "url": "https://eurocodes.jrc.ec.europa.eu/",
    },
    "ec_construction": {
        "label": "Eurocodes — EC Internal Market (Construction)",
        "publisher": "European Commission",
        "authority": "European Commission",
        "url": "https://single-market-economy.ec.europa.eu/sectors/construction/eurocodes_en",
    },
    "cen": {
        "label": "CEN European Standards (EN)",
        "publisher": "European Committee for Standardization",
        "authority": "Official standards publisher",
        "url": "https://www.cencenelec.eu/european-standardization/european-standards/",
    },
    "bsi": {
        "label": "BSI — British Standards (BS EN + UK National Annexes)",
        "publisher": "British Standards Institution",
        "authority": "National Standards Body (United Kingdom)",
        "url": "https://www.bsigroup.com/",
    },
    "gov_uk_building_regs": {
        "label": "UK Building Regulations — Approved Documents",
        "publisher": "UK Government (MHCLG)",
        "authority": "Government (United Kingdom) / Regulator",
        "url": "https://www.gov.uk/government/collections/approved-documents",
    },

    # ── Australia ─────────────────────────────────────────────────────────────
    "standards_au": {
        "label": "Standards Australia (AS / AS/NZS)",
        "publisher": "Standards Australia",
        "authority": "Official standards publisher",
        "url": "https://www.standards.org.au/",
    },
    "abcb_ncc": {
        "label": "National Construction Code (NCC)",
        "publisher": "Australian Building Codes Board",
        "authority": "Government of Australia / Regulator",
        "url": "https://ncc.abcb.gov.au/",
    },

    # ── UAE / Gulf ────────────────────────────────────────────────────────────
    "uae_moiat": {
        "label": "UAE codes — Ministry of Industry & Advanced Technology / Civil Defence",
        "publisher": "Government of the UAE",
        "authority": "Local authority / Regulator",
        "url": "https://www.moiat.gov.ae/",
    },
}


def proof_block(
    code_basis: str,
    clauses: list[str],
    source_keys: list[str],
    assumptions: Optional[str] = None,
    maturity: str = "Preliminary design calculator",
):
    return {
        "code_basis": code_basis,
        "clauses": clauses,
        "sources": [OFFICIAL_SOURCES[k] for k in source_keys if k in OFFICIAL_SOURCES],
        "assumptions": assumptions or "Use project-specific inputs and confirm the locally adopted code edition before final design.",
        "validation_status": "Formula trace and official source link included; requires project review by a licensed engineer before construction.",
        "maturity": maturity,
        "legal_note": "Building law is adopted by the project jurisdiction. Verify local amendments, national annexes, authority requirements, and the enforced edition.",
    }


def attach_proof(result, proof):
    if isinstance(result, dict) and "error" not in result:
        return {**result, "proof": proof}
    return result
