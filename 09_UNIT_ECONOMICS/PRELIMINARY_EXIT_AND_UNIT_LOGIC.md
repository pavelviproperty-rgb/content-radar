# Preliminary unit and exit logic

**Purpose:** expose unknowns before quotes. These are not supplier prices or acquisition comparables.

## Channel equations (per consumer unit)

- **DTC contribution before CAC** = net selling price − discounts/refunds − landed COGS − outbound fulfillment/postage − pick/pack − payment/platform fees − breakage.
- **Wholesale brand gross margin** = (brand invoice price − landed COGS − broker/allowances/returns) / brand invoice price.
- **Landed COGS** = ingredients + conversion + primary package + carton allocation + inbound freight + duty/brokerage + QA/testing allocation + expected scrap/breakage.
- **Do not call retail MSRP “revenue.”** At $3.99 MSRP and 40% retailer margin, retailer buy price is approximately $2.39 before distributor/broker/allowances. A distributor margin of 20% on its sell price would leave about $1.91 to the brand before broker/discounts. This illustrative waterfall shows why a $1.20 landed unit is not a 70% margin product.

## Quote grid required

Every shortlisted product/manufacturer must return quotes at 1k, 5k, 10k, 25k, 100k, 500k and 1m units, identifying tooling, MOQ, batch yield, scrap, ingredient minimums, packaging minimums, payment terms, pallet cube, lead time and Incoterm. Populate this grid only with written quotes.

| Units | Ingredients | Conversion | Package | Freight/duty | QA/scrap | Landed COGS | Source/status |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN—pilot quote required |
| 5,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |
| 10,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |
| 25,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |
| 100,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |
| 500,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |
| 1,000,000 | TBD | TBD | TBD | TBD | TBD | TBD | UNKNOWN |

## Product gate before inventory

Pass only if the written quote and tested pack-out support both:

1. **Wholesale:** ≥35% brand gross margin after normal allowances at a credible shelf price; and
2. **DTC:** ≥40% contribution before CAC on a realistic multi-pack including postage and breakage; and
3. Gross profit dollars per shipment can absorb empirically measured CAC; and
4. Packaging survives a parcel test without making dimensional-weight freight uneconomic.

These are internal gates, not industry facts. Change them only in a dated decision log.

## Exit-price sensitivity

Assume debt-free company; subtract transaction cost first. Table shows **founder gross**, before personal tax, at 7% transaction cost and no investor preference.

| Cash equity value | 100% owned | 90% | 80% | 70% | 60% | 50% |
|---:|---:|---:|---:|---:|---:|---:|
| $1.0M | $930k | $837k | $744k | $651k | $558k | $465k |
| $1.5M | $1.395M | $1.256M | $1.116M | $977k | $837k | $698k |
| $2.0M | $1.860M | $1.674M | $1.488M | $1.302M | $1.116M | $930k |
| $3.0M | $2.790M | $2.511M | $2.232M | $1.953M | $1.674M | $1.395M |

**Interpretation:** at 70% ownership, even a $1.5M company sale yields only about $977k founder gross before tax. With preferences or debt, it is less. Therefore preserving ownership and avoiding preference-heavy capital directly serves the liquidity objective.

## Minimum sale value calculator

For a target founder **gross** amount `G`, required equity value is:

`Equity value = G / ((1 − transaction-cost rate) × founder ownership)`

For a target **after-tax** amount `N` with assumed effective founder tax `t`:

`Equity value = N / ((1 − t) × (1 − transaction-cost rate) × founder ownership)`

Example: $1M after tax, 30% illustrative effective tax, 7% costs, 90% ownership requires about **$1.707M** cash equity value, before debt/preferences. Tax rate is an assumption requiring counsel, not a forecast.

## Information needed next

- Packed unit weight and dimensions, servings per case and pallet cube.
- Ingredient BOM by gram and actual delivered ingredient quotes.
- Pilot yield, labor/minute, oven/dryer dwell, energy and scrap.
- Water activity target, shelf-life protocol and packaging barrier specification.
- Domestic and import Incoterm quotes with duty classification by broker.
- Channel-specific refund, breakage, allowance, distributor and broker terms.
- Actual conversion, repeat and CAC from a controlled micro-launch.
