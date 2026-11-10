# Cart recovery review

*2026-11-05 20:59* · **You asked:** review the  higest cart values

Here are the details and recommendations for your 5 abandoned carts:

1. **Cart ID:** UA-09912  
   - **Value:** $2,801.95  
   - **Risk:** High — Very high cart value with no prior orders.  
   - **Recommendation:** Reminder email  
   - **Reason:** Profitable option given no actions are allowed and full margin if cart is recovered.  
   - **Confidence:** Low

2. **Cart ID:** UA-15598  
   - **Value:** $2,519.72  
   - **Risk:** High — High value cart from a first-time customer without prior orders.  
   - **Recommendation:** Reminder email  
   - **Reason:** Best option despite unknown purchase rate, as this action has no cost.  
   - **Confidence:** Low

3. **Cart ID:** UA-16971  
   - **Value:** $2,346.87  
   - **Risk:** High — Large cart abandoned by a first-time customer with no previous orders.  
   - **Recommendation:** Reminder email  
   - **Reason:** Judgment call due to high cart value and unknown purchase rates.  
   - **Confidence:** Low

4. **Cart ID:** UA-27286  
   - **Value:** $2,127.62  
   - **Risk:** High — Abandoned by a first-time customer, high cart value with no previous orders.  
   - **Recommendation:** Reminder email  
   - **Reason:** Low-cost option that may yield high profit given the situation.  
   - **Confidence:** Low

5. **Cart ID:** UA-22067  
   - **Value:** $2,000.00  
   - **Risk:** High — High-value cart from a first-time customer, no prior orders.  
   - **Recommendation:** Reminder email  
   - **Reason:** This option is cost-effective and could lead to recovery despite unknown purchase rate.  
   - **Confidence:** Low

### Summary of Recommendations:
- **Reminder email:** 5 carts.
- **Total value at risk:** $11,796.16
- **Profit if the carts with a recovery action are recovered:** $4,718.47
- Every recommendation requires your approval. The full table is saved to data/latest_review.md.

---

## Full table

| Cart | Session date | Days old | Products | Cart value | Reached checkout | Device | Traffic | Subscribed | Returning | Risk | AI recommendation | Profit if recovered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UA-09912 | 2016-11-03 | 271 | 88 | $2,801.95 | No | desktop | (none) | Yes (simulated) | No | High | Reminder email | $1,120.78 |
| UA-15598 | 2016-12-29 | 215 | 1 | $2,519.72 | No | mobile | (none) | Yes (simulated) | No | High | Reminder email | $1,007.89 |
| UA-16971 | 2017-01-20 | 193 | 89 | $2,346.87 | No | desktop | (none) | Yes (simulated) | No | High | Reminder email | $938.75 |
| UA-27286 | 2017-05-22 | 71 | 1 | $2,127.62 | No | desktop | (none) | Yes (simulated) | No | High | Reminder email | $851.05 |
| UA-22067 | 2017-03-26 | 128 | 1 | $2,000.00 | No | mobile | referral | Yes (simulated) | No | High | Reminder email | $800.00 |

**Why**

- **UA-09912** (271 days before the end of the data): Very high cart value with no prior orders. → **Reminder email**: Profitable option given no actions are allowed and full margin if cart is recovered. Profit: profit if recovered $1,120.78; expected profit unknown (purchase rate missing). Confidence: Low.
- **UA-15598** (215 days before the end of the data): High value cart from a first-time customer without prior orders. → **Reminder email**: Best option despite unknown purchase rate, as this action has no cost. Profit: profit if recovered $1,007.89; expected profit unknown (purchase rate missing). Confidence: Low.
- **UA-16971** (193 days before the end of the data): Large cart abandoned by a first-time customer with no previous orders. → **Reminder email**: Judgment call due to high cart value and unknown purchase rates. Profit: profit if recovered $938.75; expected profit unknown (purchase rate missing). Confidence: Low.
- **UA-27286** (71 days before the end of the data): Abandoned by a first-time customer, high cart value with no previous orders. → **Reminder email**: Low-cost option that may yield high profit given the situation. Profit: profit if recovered $851.05; expected profit unknown (purchase rate missing). Confidence: Low.
- **UA-22067** (128 days before the end of the data): High-value cart from a first-time customer, no prior orders. → **Reminder email**: This option is cost-effective and could lead to recovery despite unknown purchase rate. Profit: profit if recovered $800.00; expected profit unknown (purchase rate missing). Confidence: Low.

**Summary**

- Carts reviewed: 5 · Total value at risk: **$11,796.16**
- Profit from carts with a recovery action (Reminder email, Free shipping, 5% discount), if they are recovered: **$4,718.47**
- Margin on "No action" and "Escalate for human review" carts if they return on their own (not profit from an action): $0.00
- Recommended actions: Reminder email (5)
- All carts are from first-time customers, making discounts unavailable.
- Profit if recovered = cart value × 40%, minus the action's cost
- Days old are counted from 2017-08-01, the last day of the data
- Email subscription is simulated: the data has no consent field
- Every recommendation: **Requires Human Approval** (saved to data/recommendations.csv)
