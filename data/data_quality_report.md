# Data quality report

Built by prepare_data.py from the two Excel files.

## 2016-17 file: used for cart review
- Cart sessions in the file: 33,725; after joining 19 sessions split across midnight: 33,706
- Abandoned: 24,091; visitor bought in a later session: 3,674; open carts for review: 20,417
- Cart value check on 9,580 paid sessions: value added to cart / amount paid has a median of 1.00, and 62% fall between half and double. Usable, but approximate.
- Cart value counts every add-to-cart, so repeated adds count twice and removed items are not taken off. 3,361 open carts had a removal.
- $0 carts in the open list: 6
- Purchased sessions showing $0 revenue: 35
- Sessions with no pageview count: 21; no time on site: 14
- State shows "not available in demo dataset" on 14,578 rows. State and city are not used.

## 2020-21 (GA4) file: rates and comparison only
- Cart value check on 1,130 paid sessions: value added to cart / amount paid has a median of 20.1, and only 5% fall between half and double.
- Largest value in the file: $282,130,908,643. The largest amount actually paid: $865.
- The file comes from Google's obfuscated sample, and the median session shows 12 products added. Its cart values are not treated as dollars.
- Purchases with no revenue recorded: 138
- Traffic source is hidden on many rows ("(data deleted)" or "<Other>"): 2,340

## Not in either file
Email address, email consent, product names, fabric, size, quantity, unit price, sale status, shipping and tax.

## Limits of purchase history
previous_orders and lifetime_spend only see inside each file's dates, and a visitor is a browser cookie. A customer on a new device looks new, so returning customers are undercounted.
