---
title: Net Weight vs Gross Weight in a BOM – Why Scrap Changes Your PCF
type: blog
product: carbalyze
url: https://carbalyze.com/en-us/blog/net-vs-gross-weight-bom-pcf
published: 2026-10-06
topic: BOM data, scrap, yield, material input
retrieved: 2026-10-21
---

# Net vs gross weight – summary

**Core idea:** A 1 kg part may need more than 1 kg of material to make. Net weight = material left in the finished part. Gross weight (gross material input) = all material put into production, including scrap. Using only net weight can miss emissions from material that was bought and processed but scrapped.

## Where the numbers come from
Engineering BOM/CAD → net weight. Manufacturing, purchasing or supplier records → gross input, yield, scrap. Neither replaces the other.

## Sources of scrap
Machining chips and offcuts · stamping/blanking skeletons · molding sprues, runners, flash · start-up and changeover losses · rejected parts · trimming/finishing · handling damage.

## Illustrative example (not real factors)
Bracket: net 1.0 kg, scrap 0.5 kg, gross 1.5 kg, factor 2.0 kg CO₂e/kg → 2.0 vs 3.0 kg CO₂e (1.0 kg CO₂e difference).

## Watch the scrap-rate basis
Yield = net ÷ gross = 66.7%. Scrap on gross basis = 33.3%. Scrap on net basis = 50%. Gross = net ÷ (1 − scrap rate on gross basis). Always record the basis.

## Also consider
Process energy spent on scrapped material; how scrap is treated (reused, recycled, disposed) and the recycling method; avoid double counting.

## Common mistakes
Net weight only · scrap % without its basis · one scrap rate for all processes · ignoring rejects · undocumented scrap data · mixed units.

## 8-step workflow
Define system → collect BOM → find losses → collect input/scrap data → calculate consistently → apply factors → document scrap treatment → review.

## Post angles already used on LinkedIn (avoid repeating)
"Your BOM shows what ships. Your PCF may need to show what it took to make it."
