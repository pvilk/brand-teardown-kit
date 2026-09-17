# Revenue model: formulas, benchmarks, traps

Every row is gross. Label each input VERIFIED (read off a loaded source), INFERRED (arithmetic shown) or ASSUMPTION (no source). Channels add; they do not cross-check each other.

## Retail (per retailer)
```
units/week      = verified_doors × units_per_store_per_week (u/s/w)
brand $/year    = units/week × 52 × wholesale_price
shelf $/year    = units/week × 52 × regular_shelf_price
since launch    = verified_doors × u/s/w × weeks_since_launch
swing           = +1.0 u/s/w adds verified_doors × 52 × wholesale_price per year
```
**Inputs and where they came from on Drizzy:**
- **Doors:** brand Stockist locator (500) → verified store by store on the retailer's own shop (483). Never use the founder's rounded claim.
- **Wholesale price:** a hidden B2B product in the brand's Shopify `/products.json` ("KeHE Case Pack (6 units) $32.10" = $5.35/unit). That SKU also names the distributor and case pack.
- **Shelf price:** the retailer's online shop, per store (Sprouts: $11.49 regular, $9.99 promo). Use regular price for the steady state.
- **u/s/w low/base/high (Sprouts):** 1.0 / 1.5 / 2.4.
  - 2.4 = Sprouts condiment category average; new items start at 1.3-1.5 and should reach the average within a year ([Social Nature](https://business.socialnature.com/how-to-exceed-buyer-expectations-at-sprouts/)).
  - 1.2 = a real Sprouts launch (Else Nutrition) after ten months ([Stock Titan](https://www.stocktitan.net/news/BABYF/sprouts-farmers-market-adds-else-kids-nutrition-products-to-its-j3kfsjhi1ea6.html)).
  - Nut-butter-specific and Australian velocities: not public (SPINS/Circana are paid). Say so.
- **Launch-promo ceiling:** 3.5 u/s/w while a sweepstakes or temporary price cut runs. Present as a ceiling, never the base.

## One-time stocking order (pipeline fill)
```
store fill      = doors × 1 to 2 cases × case_pack
distributor DC  = 2 to 4 weeks of base demand (ASSUMPTION)
gross           = (store fill + DC) × wholesale
net             = gross − free fill (first case per store × wholesale)
```
Sprouts' [vendor policies](https://about.sprouts.com/vendor-policies-2/) require a free fill per new store and guarantee placement for six months, so the first keep-or-cut decision lands ~6 months after launch.

## TikTok Shop
```
base   = average daily GMV since day 2 × 365
low    = decayed daily GMV (Drizzy used ~half) × 365
high   = latest strong day × 365
to date = public PDP sold_count × averageSellingPrice
```
GMV is gross of TikTok referral fees, affiliate commissions and seller-funded coupons.

## DTC (weakest row; label it)
- With a review app: total reviews ÷ review rate (1-3% for food) × AOV. Pull monthly review counts for a curve.
- Without one (Drizzy): the site's "Loved by N+" claim × 1.2-1.8 orders × AOV range, spread over months live. It is a floor claim, often stale.
- A brand-new store with no reviews, no ads and no pixel: do not estimate. Say "not estimated".

## Funding (when undisclosed)
- EDGAR full-text search `"<Brand> SPV"` and `"<Brand>"`: syndicate SPVs (Sydecar, AngelList) file Form Ds the company never does. It is a floor.
- The lead's stated first-cheque range (its website) + SPV floors + named angels = a band. Pre-seed single-SKU CPG: usually $0.6M to $2M.
- ImportYeti consignee address can match an investor's office (lead signal).
- NY Department of State JSON API exposes a Delaware corp's formation date without Delaware's captcha.

## Why other estimates look bigger (always include)
1. Shelf dollars vs brand dollars: shelf ÷ wholesale (Drizzy 11.49 ÷ 5.35 = 2.1×).
2. Gross vs net: free fill, trade promotions, distributor fees, platform commissions.
3. The velocity swing: one extra unit per store per week, in dollars.
