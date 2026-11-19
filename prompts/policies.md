# Cart recovery policies

These policies follow the professor's suggestions. Lines with a number after a colon are read by the code, so keep the wording before the colon unchanged when you edit a number. Margin, shipping cost and discount size are simulation assumptions, not Google's real figures.

## 2.1 Cart value and prioritization
- High-value carts: top 10% of the prepared cart values (the code works out the dollar cut-off, about $110)
- High value raises review priority only. It never triggers a discount or human review on its own.

## 2.2 Abandonment age and contact timing
- Recovery eligibility starts after hours of inactivity: 24
- First reminder on day: 1
- Second reminder (optional) on day: 5
- Campaign closes on day: 7
- Stop all follow-ups after a verified purchase (carts whose shopper bought later are already removed from the open list)
- Exact timing is a team assumption to be tested, not an industry standard.

## 2.3 Customer type and relationship
- Maximum recovery discount allowed: 5%
- The 5% discount is only for returning customers (customers who have bought before)
- First-time buyers get a reminder only, never the 5% discount
- Store restrictions always override an AI recommendation

## 2.4 Checkout-stage behavior
- Cart added but checkout not reached: basic reminder
- Checkout reached but not purchased: reminder that focuses on completing checkout
- These signals shape the reminder; they do not show why the shopper left

## 2.5 Recovery cost
- Use a reminder first. Incentives (free shipping or the 5% discount) are considered only at the second contact
- Before any incentive, compare the 5% discount with the free-shipping cost and choose the cheaper allowed one
- Incentive cap as % of estimated gross profit: 20%
- Average product cost as % of price: 60% (estimated gross profit = 40% of cart value)
- Average shipping cost per order: $7.00 (what free shipping costs per recovered order; simulated)
- Cost to send one recovery email: $0.00

## 2.6 Product category and seasonality (conditional)
- Apply category or seasonal rules only when reliable product labels exist. This data has none, so general rules apply. Never guess a category.

## 3.1 Natural-return awareness
- Use how often each segment bought later on its own (measured in the data) to avoid paying for incentives too early
- A segment that often returns on its own gets a reminder before any offer, even when the cart is high value
- This is an association, not proof that a given shopper would return

## 3.2 Purchase-intent score
- A transparent score from 0 to 100, kept separate from abandonment risk. Points: reached checkout 35, bought before 25, repeat visit 15, 20 or more pageviews 15, 10 or more minutes on site 10, removed an item -10
- Bands: High 60 and above, Medium 30 to 59, Low under 30
- It is a heuristic for follow-up priority, not a calibrated probability

## 3.3 Explainable decisions
- Every recommendation shows the policy checks, the incentive cost and why each alternative was rejected, all computed in code

## 3.4 Human review
- Escalate only when an important eligibility or cost input is missing, policies conflict, or the case is exceptional
- Never escalate only because the cart value is high

## 3.5 Limited-budget prioritization (optional demonstration)
- Default simulated incentive budget: $50
- Rank eligible carts by intent score, then cart value, and offer the cheapest allowed incentive until the budget is used. This is a heuristic ranking, not profit-maximizing

## Estimated purchase rates per action (not measured yet)
- No action: ?%
- Reminder email: ?%
- Free shipping: ?%
- 5% discount: ?%

## Simulation settings (Excel data only; these are not store policies)
- Assume carts are subscribed to email: yes (the Google data has no email or consent field; set to "no" and every email action is blocked)
- Evaluate each cart this many days after it was left: 1 (historical replay. Use 5 to see the second contact, or 7 to see closed campaigns)
- Anonymous data only: visitor IDs, state and city never reach the AI
