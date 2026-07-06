# NagaForge Global Engineering Platform Direction

NagaForge should grow as a global engineering calculator platform, not a single-country calculator clone.

## Product Position

NagaForge combines:

- Structural engineering calculators
- Project controls
- RFIs and drawing registers
- Change orders
- Documents
- Billing
- QC and safety workflows
- PDF calculation sheets

This lets NagaForge compete differently from pure calculator libraries: every calculation can belong to a project, a drawing, an RFI, a change order, or a report.

## Country / Code Packs

Each region should be a code pack with a consistent user experience:

- Canada: NBC, CSA A23.3, CSA S16, CSA O86
- India: NBC India, IS 456, IS 800, IS 875, IS 1893
- United States: ASCE 7, ACI 318, AISC 360, NDS
- Europe: Eurocode 0/1/2/3/5/7/8
- Australia / New Zealand: NCC, AS/NZS 1170, AS 3600, AS 4100, AS 1720
- Gulf / Middle East: local authority workflows plus ACI/AISC/BS/Eurocode variants

## Shared Engineering Primitives

Avoid duplicating the same logic inside every code pack. Build shared primitives for:

- Units and conversions
- Load combinations
- Section properties
- Material libraries
- Member demand/resistance checks
- Utilization and pass/revise reporting
- Calculation step formatting
- PDF sheet generation
- Validation examples

## Calculator Quality Levels

Each calculator should carry a maturity level:

- Draft: preliminary engineering workflow
- Verified: checked against worked examples
- Production: validated, PDF-ready, saved history, edge cases handled

This keeps the platform honest and helps engineers trust what they are using.

## Proof And Legal Source Policy

Every calculator result must include a machine-readable `proof` object. This is part of the product contract, not optional UI decoration.

- Link to government or regulator sources when the law, code adoption notice, climate data, seismic data, or hazard map is published by government.
- Link to the official standards publisher when the adopted technical standard is copyrighted or sold by a standards body, such as CSA, ASTM, ACI, AISC, BIS, BSI, CEN, Standards Australia, or ISO.
- Label each link by authority type: `Government`, `Regulator`, `Official standards publisher`, or `Local authority`.
- Include clause/table references, assumptions, validation maturity, and a legal note that local amendments may govern.
- Never cite blogs, screenshots, copied PDFs, or unofficial mirrors as proof for engineering calculations.
- Never imply that a preliminary calculator is a stamped design. Every final project must still be reviewed by the responsible licensed engineer under the local jurisdiction.

Minimum response shape:

```json
{
  "proof": {
    "code_basis": "NBC 2020",
    "clauses": ["NBC Division B Part 4, Cl. 4.1.6"],
    "sources": [
      {
        "label": "National Building Code of Canada 2020",
        "authority": "Government of Canada",
        "publisher": "National Research Council Canada",
        "url": "https://nrc.canada.ca/..."
      }
    ],
    "assumptions": "Project-specific assumptions used by this calculation.",
    "validation_status": "Formula trace and official source link included; requires project review by a licensed engineer.",
    "legal_note": "Verify locally adopted edition and amendments."
  }
}
```

## Competitive Roadmap

To become globally competitive:

1. Finish Canadian parity with Jabacus-style breadth.
2. Add PDF calculation sheets for every calculator.
3. Add saved/project-linked calculation history.
4. Add validation examples and test fixtures.
5. Convert code packs into reusable modules.
6. Add more countries without changing the overall UX.

## Canada Near-Term Gaps

Still needed for stronger Canadian parity:

- More CSA O86 fastener cases and spacing checks
- CSA S16 detailed connection workflows
- CSA S136 cold-formed steel
- Better NBC wind geometry and cladding zones
- Validated climatic/location database workflow
- Worked examples for every calculator
