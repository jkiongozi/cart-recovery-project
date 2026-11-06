"""Offline checks: no OpenAI key or API call. Run: python test_agent.py"""
import os
import re

import agent as a


def carts(pred):
    return [c for c in a.CHECKOUTS if pred(c)]


first = max(carts(lambda c: c["previous_orders"] == 0), key=lambda c: c["cart_value"])
back = max(carts(lambda c: c["previous_orders"] > 0), key=lambda c: c["cart_value"])


def rec(cid, action):
    return {"cart_id": cid, "risk": "Medium", "risk_reason": "Test.", "recommendation": action,
            "reason": "Test.", "confidence": "High"}


# Privacy: the AI never sees IDs or locations
view = a.safe_view(first)
assert not {"visitor_id", "state", "city", "email"} & set(view)
with open(os.path.join(a.DATA_DIR, "open_carts.csv"), encoding="utf-8") as f:
    header = f.readline()
assert "visitor" not in header and "city" not in header

# Profit: cart value x 40%, free shipping costs $7, the discount costs 5%
p = {r["action"]: r for r in a.calculate_profit(back["cart_id"])["results"]}
keep = back["cart_value"] * 0.4
assert p["Reminder email"]["profit_if_recovered"] == round(keep, 2)
assert p["Free shipping"]["profit_if_recovered"] == round(keep - 7, 2)
assert p["5% discount"]["profit_if_recovered"] == round(keep - back["cart_value"] * 0.05, 2)
assert p["Reminder email"]["expected_profit"] is None    # purchase rate is "?": never guessed

# Policy: the 5% discount is refused for first-time buyers
r = {x["action"]: x for x in a.calculate_profit(first["cart_id"])["results"]}
assert r["5% discount"]["allowed"] is False
out = a.submit_review([rec(first["cart_id"], "5% discount")])
assert "blocked" in out["report"] and "No action" in out["report"]

# Policy: non-policy discounts are blocked; unmatched wording is kept, never guessed
assert "blocked" in a.submit_review([rec(back["cart_id"], "10% welcome offer")])["report"]
assert "Reminder email without a discount" in a.submit_review(
    [rec(back["cart_id"], "Reminder email without a discount")])["report"]

# Confidence stays Low while purchase rates are unknown
assert "**Confidence:** High" not in a.submit_review([rec(back["cart_id"], "Reminder email")])["report"]

# Totals are computed in code
big = sorted(a.CHECKOUTS, key=lambda c: -c["cart_value"])[:5]
out = a.submit_review([rec(c["cart_id"], "Reminder email") for c in big])["report"]
total = float(re.search(r"Total value at risk:\*\* \$([\d,.]+)", out).group(1).replace(",", ""))
assert abs(total - sum(c["cart_value"] for c in big)) < 0.01

# Consent: with no simulated subscription every email action is blocked
for c in a.CHECKOUTS:
    c["marketing_state"] = "UNKNOWN"
blocked = {x["action"]: x for x in a.calculate_profit(back["cart_id"])["results"]}
assert all(blocked[k]["allowed"] is False for k in ["Reminder email", "Free shipping", "5% discount"])
assert blocked["Escalate for human review"]["allowed"] is True
for c in a.CHECKOUTS:
    c["marketing_state"] = "SUBSCRIBED"

# A purchase rate typed into policies.md is picked up, including Free shipping
original = a.get_store_policies
text = original()["policies"]
a.get_store_policies = lambda: {"policies": text.replace("- Free shipping: ?%", "- Free shipping: 12%")}
assert a._policy_numbers()["rates"]["Free shipping"] == 12
assert a._policy_numbers()["free_shipping_cost"] == 7
a.get_store_policies = original

# Store-wide recommendations: evidence comes from code, invented groups and bigger offers are refused
idea = {"title": "Shorter mobile checkout", "dataset": "2016-17", "group": "device", "segment": "mobile",
        "recommendation": "Try one-page checkout on phones.", "why_it_may_help": "Associated with leaving.",
        "how_to_test": "Compare checkout completion.", "effort": "Medium"}
out = a.submit_recommendations([idea])["report"]
row = a.STATS["2016-17"]["patterns"]["device"]["mobile"]
assert f"{row['abandonment_rate_pct']}% abandoned" in out and a.LAST_STRATEGY == out
assert "error" in a.submit_recommendations([{**idea, "segment": "smart fridge"}])
assert "error" in a.submit_recommendations([{**idea, "recommendation": "Give everyone 20% off."}])
assert "error" in a.submit_recommendations([{**idea, "recommendation": "Send a discount of 15%."}])
assert "error" not in a.submit_recommendations([{**idea, "recommendation": "Point to the 10% welcome offer."}])
assert "error" not in a.submit_recommendations([{**idea, "dataset": "2020-21"}])
assert "abandoned_value" not in a.analyze_abandonment()["2020-21"]["groups"]["device"]["mobile"]
assert "patterns" not in a.compare_datasets()["2016-17"]

# Limits and unknown IDs
assert len(a.list_abandoned_checkouts(limit=-1)["carts"]) == 20
assert "error" in a.get_checkout("nope")
assert "error" in a.submit_review([rec("nope", "No action")])

print("All checks passed.")
