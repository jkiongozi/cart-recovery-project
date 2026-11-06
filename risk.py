"""RULES BASELINE: fixed risk scoring and recommendations.

This is deliberately NOT the agent. It is a plain set of if-then rules used by the
dashboard, so the AI agent's judgments can be compared against what simple rules
would do. The agent never sees these verdicts; it only gets facts and decides itself.

Risk here = the risk of losing the sale for good. It is a RULE-BASED score
(not a machine-learning prediction).

Every number below is a setting you can change.
"""
import re

# ---------- Shared by the agent, the rules and the dashboard ----------
# The five canonical action names. The agent, the rules and the dashboard all use these.
ACTIONS = ["No action", "Reminder email", "Free shipping", "5% discount", "Escalate for human review"]

# Exact phrases (after lower-casing and trimming punctuation) that mean each action.
# Matching is exact: "no reminder" or "without a discount" never become a reminder or a discount.
ACTION_ALIASES = {
    "No action": ["no action", "none", "do nothing", "wait", "wait and monitor", "monitor",
                  "leave it", "leave alone", "do not email", "dont email", "don't email",
                  "no reminder", "no email"],
    "Reminder email": ["reminder email", "reminder", "send reminder", "send reminder email",
                       "send a reminder email", "send a reminder", "email reminder",
                       "reminder email with shipping and delivery info"],
    "Free shipping": ["free shipping", "offer free shipping", "free shipping offer"],
    "5% discount": ["5% discount", "offer 5% discount", "offer a 5% discount", "5 percent discount",
                    "5% off", "recovery discount", "policy discount"],
    "Escalate for human review": ["escalate for human review", "escalate", "human review",
                                  "escalate to owner", "escalate for review"],
}
_ALIAS_LOOKUP = {alias: action for action, aliases in ACTION_ALIASES.items() for alias in aliases}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower().strip(".!:;,")).strip()


def canonical_action(text):
    """Return the canonical action for an exact alias, or None if the text matches nothing."""
    return _ALIAS_LOOKUP.get(_norm(text))


def is_non_policy_discount(text):
    """True for discount offers that are not the policy discount (e.g. '10% welcome offer', '15% off').
    Negations such as 'no discount' or 'without a discount' are not discounts."""
    t = _norm(text)
    if canonical_action(t):
        return False
    if re.search(r"\b(no|without|not)\b[^.]*\b(discount|offer|off)\b", t):
        return False
    return bool(re.search(r"\bdiscount\b|\d+\s*%\s*off\b|\bwelcome offer\b|\bcoupon\b|\bpromo", t))


# ---------- Settings you can change ----------
# Points added for how long ago the cart was abandoned (older = harder to win back)
AGE_POINTS = [            # (up to this many days, points)
    (1, 10),
    (3, 25),
    (7, 40),
    (30, 55),
    (float("inf"), 70),
]
NOT_SUBSCRIBED_POINTS = 20    # we may not send marketing

LOW_MAX = 39                  # 0-39   = Low risk
MEDIUM_MAX = 69               # 40-69  = Medium risk, 70-100 = High risk

# Recommended action for subscribed customers, by days since abandonment
REMINDER_DAYS = 3             # up to 3 days: plain reminder email
INFO_DAYS = 7                 # 3-7 days: reminder + shipping/delivery info
                              # 7-30 days: free shipping (if cart is big enough)
TOO_OLD_DAYS = 30             # older than this: not worth a message
FREE_SHIPPING_MIN_CART = 50   # only offer free shipping on carts worth at least this
FREE_SHIPPING_COST = 7.00     # what free shipping costs you per recovered order
ESCALATE_MULTIPLE = 3         # carts worth more than 3x the average go to you for review


def average_cart(carts):
    """Average of carts above $0 ($0 carts would drag the average down)."""
    values = [c["cart_value"] for c in carts if c["cart_value"] > 0]
    return round(sum(values) / len(values), 2) if values else 0.0


def risk_level(score):
    if score <= LOW_MAX:
        return "Low"
    if score <= MEDIUM_MAX:
        return "Medium"
    return "High"


def assess(cart, avg_cart):
    """Return risk score, level, factors and a recommended action for one cart."""
    value = cart["cart_value"]
    age = cart["days_since_abandoned"]
    subscribed = cart.get("marketing_state") == "SUBSCRIBED"

    # ----- Risk score -----
    score, factors = 0, []
    for max_days, points in AGE_POINTS:
        if age <= max_days:
            score += points
            break
    factors.append(f"Abandoned {age:.0f} day{'s' if age != 1 else ''} before the end of the data")
    if not subscribed:
        score += NOT_SUBSCRIBED_POINTS
        factors.append("Not subscribed to email marketing")
    else:
        factors.append("Subscribed to email marketing (simulated)")
    score = min(score, 100)
    level = risk_level(score)

    # ----- Recommended action (first rule that applies wins) -----
    if value <= 0:
        action, reason = "No action", "$0 cart: nothing to recover."
    elif avg_cart and value > ESCALATE_MULTIPLE * avg_cart:
        action, reason = "Escalate for human review", (
            f"Cart is worth more than {ESCALATE_MULTIPLE}x the average (${avg_cart:,.2f}).")
    elif not subscribed:
        action, reason = "No action", "Customer is not subscribed; store policy allows recovery emails only to subscribers."
    elif age > TOO_OLD_DAYS:
        action, reason = "No action", f"Abandoned over {TOO_OLD_DAYS} days ago; a message is unlikely to help."
    elif age <= REMINDER_DAYS:
        action, reason = "Reminder email", (
            "Recent cart and customer is subscribed; a free reminder is the cheapest step.")
    elif age <= INFO_DAYS:
        action, reason = "Reminder email", (
            "A few days have passed; include shipping and delivery info before considering any incentive.")
    elif value >= FREE_SHIPPING_MIN_CART:
        action, reason = "Free shipping", (
            f"Over {INFO_DAYS} days old and cart is ${value:,.2f}; free shipping costs about "
            f"${FREE_SHIPPING_COST:.2f}, cheaper than a percentage discount.")
    else:
        action, reason = "Reminder email", (
            f"Over {INFO_DAYS} days old but cart is under ${FREE_SHIPPING_MIN_CART}; a "
            f"${FREE_SHIPPING_COST:.2f} free-shipping offer would eat most of the margin.")

    return {"risk_score": score, "risk_level": level, "risk_factors": "; ".join(factors),
            "recommended_action": action, "reason": reason}


def assess_all(carts):
    avg = average_cart(carts)
    return [{**c, **assess(c, avg)} for c in carts], avg


if __name__ == "__main__":
    # python risk.py  ->  scores every cart and saves data/cart_recommendations.csv
    import os
    import pandas as pd
    from agent_data import load_for_app

    carts, _ = load_for_app()
    rows, avg = assess_all(carts)
    df = pd.DataFrame(rows)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cart_recommendations.csv")
    df.sort_values("cart_value", ascending=False).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nAverage cart (excluding $0 carts): ${avg:,.2f}")
    print("\nCarts by risk level:")
    print(df["risk_level"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0).astype(int).to_string())
    print("\nRecommended actions:")
    print(df["recommended_action"].value_counts().to_string())
    print(f"\nSaved to {path}")
