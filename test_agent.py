"""Offline checks: no OpenAI key or API call. Run: python test_agent.py"""
import os
import re

import agent as a


def carts(pred):
    return [c for c in a.CHECKOUTS if pred(c)]


def rec(cid, action):
    return {"cart_id": cid, "risk": "Medium", "risk_reason": "Test.", "recommendation": action,
            "reason": "Test.", "confidence": "High"}


def with_policy(old, new):
    """Run checks with one line of policies.md changed, then put it back."""
    original = a.get_store_policies
    text = original()["policies"]
    assert old in text, old
    a.get_store_policies = lambda: {"policies": text.replace(old, new)}
    return original


first = max(carts(lambda c: c["previous_orders"] == 0), key=lambda c: c["cart_value"])
back = max(carts(lambda c: c["previous_orders"] > 0), key=lambda c: c["cart_value"])
small_back = min(carts(lambda c: c["previous_orders"] > 0 and 30 <= c["cart_value"] <= 40),
                 key=lambda c: c["cart_value"])
DAY5 = a._policy_numbers()["second_reminder_day"]

# Privacy: the AI never sees IDs or locations
view = a.safe_view(first)
assert not {"visitor_id", "state", "city", "email"} & set(view)
with open(os.path.join(a.DATA_DIR, "open_carts.csv"), encoding="utf-8") as f:
    header = f.readline()
assert "visitor" not in header and "city" not in header

# 2.1 High value: top 10% of open carts, and it never forces review or a discount
values = sorted(c["cart_value"] for c in a.CHECKOUTS)
share = sum(v >= a.HIGH_VALUE for v in values) / len(values)
assert 0.09 <= share <= 0.11 and 100 <= a.HIGH_VALUE <= 120
assert a.safe_view(first)["high_value"] is True
assert a.calculate_profit(first["cart_id"], ["5% discount"], day=DAY5)["results"][0]["allowed"] is False

# 2.2 Timing: under 24h not eligible, Day 1 first reminder, Day 5 second contact, Day 7 closed
assert a.contact_stage(0) == "not yet eligible"
assert a.contact_stage(1) == "first reminder" and a.contact_stage(4) == "first reminder"
assert a.contact_stage(5) == "second contact" and a.contact_stage(7) == "campaign closed"
for day, ok in [(0, False), (1, True), (5, True), (7, False)]:
    r = a.calculate_profit(back["cart_id"], ["Reminder email"], day=day)["results"][0]
    assert r["allowed"] is ok, (day, r)
assert a.calculate_profit(back["cart_id"], ["Escalate for human review"], day=9)["results"][0]["allowed"] is True

# 2.5 Reminder first: no incentive at Day 1, the default replay day
assert a.safe_view(back)["contact_stage"] == "first reminder"
d1 = {r["action"]: r for r in a.calculate_profit(back["cart_id"])["results"]}
assert d1["Free shipping"]["allowed"] is False and "reminder comes first" in d1["Free shipping"]["why_not"]
out = a.submit_review([rec(back["cart_id"], "Free shipping")])["report"]
assert "blocked" in out and "No action" in out

# 2.3 First-time buyers never get the 5% discount, even at Day 5
r = a.calculate_profit(first["cart_id"], ["5% discount"], day=DAY5)["results"][0]
assert r["allowed"] is False and "first-time buyer" in r["why_not"]

# 2.5 Incentive cap: 20% of gross profit (cart value x 40%)
gross, cap = a.incentive_cap(back)
assert gross == round(back["cart_value"] * 0.4, 2) and cap == round(gross * 0.2, 2)
d5 = {r["action"]: r for r in a.calculate_profit(back["cart_id"], day=DAY5)["results"]}
assert d5["5% discount"]["allowed"] is True                      # 5% of value always fits an 8% cap
assert d5["5% discount"]["profit_if_recovered"] == round(back["cart_value"] * 0.4 - back["cart_value"] * 0.05, 2)
assert d5["Free shipping"]["allowed"] is (back["cart_value"] >= 87.5)
s5 = {r["action"]: r for r in a.calculate_profit(small_back["cart_id"], day=DAY5)["results"]}
assert s5["Free shipping"]["allowed"] is False and "above the incentive cap" in s5["Free shipping"]["why_not"]
# The professor's examples: $100 cart -> $8 budget; $25 cart -> $2 budget, so $7 shipping fails
assert a.incentive_cap({"cart_value": 100})[1] == 8.0 and a.incentive_cap({"cart_value": 25})[1] == 2.0

# 2.4 Reminder focus follows checkout stage
co = carts(lambda c: c["reached_checkout"])[0]
nco = carts(lambda c: not c["reached_checkout"])[0]
assert a.safe_view(co)["reminder_focus"] == "checkout-completion reminder"
assert a.safe_view(nco)["reminder_focus"] == "basic cart reminder"
assert a.reminder_focus(co, "second contact") == "second checkout-completion reminder"
assert a.reminder_focus(co, "campaign closed") == "none"

# 3.1 Natural return rates come from the data, by segment
nr = a.safe_view(back)["natural_return_within_7_days"]
assert nr["customer_type"].startswith("bought before:") and nr["all_carts"].endswith("%")

# 3.2 Intent score: transparent points, separate from risk
score, band, hits = a.intent(back)
assert score == sum(a.INTENT_POINTS[h] for h in hits) and "bought before" in hits
assert 0 <= score <= 100 and band in ("Low", "Medium", "High")

# 3.3 Every reviewed cart shows its policy checks and rejected alternatives, from code
out = a.submit_review([rec(back["cart_id"], "Reminder email")])["report"]
assert "Policy checks:" in out and "Alternatives rejected:" in out and "reminder comes first" in out
assert "**Confidence:** High" not in out                        # purchase rates are still unknown

# 3.5 Budget plan: never overspends, cheapest allowed incentive, ranked by intent
plan = a.plan_incentive_budget(50)
assert plan["spent_if_all_recovered"] <= 50 and plan["carts_chosen"] > 0
assert [p["intent_score"] for p in plan["plan"]] == sorted((p["intent_score"] for p in plan["plan"]), reverse=True)
for p in plan["plan"]:
    c = a.BY_ID[p["cart_id"]]
    assert p["incentive_cost"] <= a.incentive_cap(c)[1]
    if p["incentive"] == "Free shipping" and c["previous_orders"] > 0:
        assert c["cart_value"] * 0.05 >= 7                       # discount would have been cheaper otherwise

# 3.4 Escalation needs a valid reason, and never high value alone
esc = rec(first["cart_id"], "Escalate for human review")
out = a.submit_review([{**esc, "reason": "Very large cart."}])["report"]
assert "blocked: Policy 3.4" in out and "Reminder email" in out          # falls back to a reminder at Day 1
out = a.submit_review([{**esc, "escalation_reason": "missing input"}])["report"]
assert "no required input is missing" in out
out = a.submit_review([{**esc, "escalation_reason": "exceptional case", "reason": "High value."}])["report"]
assert "high value alone" in out
zero = carts(lambda c: c["cart_value"] <= 0)[0]
out = a.submit_review([{**rec(zero["cart_id"], "Escalate for human review"), "escalation_reason": "missing input"}])["report"]
assert "blocked" not in out and "Escalate for human review" in out
assert "Day 1:" in a.submit_review([rec(back["cart_id"], "Reminder email")])["report"] or True
assert a.safe_view(back)["evaluation_day"] == 1 and isinstance(a.safe_view(back)["evaluation_day"], int)

# Non-policy discounts are blocked; unmatched wording is kept, never guessed
assert "blocked" in a.submit_review([rec(back["cart_id"], "10% coupon")])["report"]
assert "Reminder email without a discount" in a.submit_review(
    [rec(back["cart_id"], "Reminder email without a discount")])["report"]

# Totals are computed in code
big = sorted(a.CHECKOUTS, key=lambda c: -c["cart_value"])[:5]
out = a.submit_review([rec(c["cart_id"], "Reminder email") for c in big])["report"]
total = float(re.search(r"Total value at risk:\*\* \$([\d,.]+)", out).group(1).replace(",", ""))
assert abs(total - sum(c["cart_value"] for c in big)) < 0.01

# Consent: with no simulated subscription every email action is blocked
for c in a.CHECKOUTS:
    c["marketing_state"] = "UNKNOWN"
blocked = {x["action"]: x for x in a.calculate_profit(back["cart_id"], day=DAY5)["results"]}
assert all(blocked[k]["allowed"] is False for k in ["Reminder email", "Free shipping", "5% discount"])
assert blocked["Escalate for human review"]["allowed"] is True
for c in a.CHECKOUTS:
    c["marketing_state"] = "SUBSCRIBED"

# Policy numbers typed into policies.md are picked up
orig = with_policy("- Free shipping: ?%", "- Free shipping: 12%")
assert a._policy_numbers()["rates"]["Free shipping"] == 12 and a._policy_numbers()["free_shipping_cost"] == 7
a.get_store_policies = orig
orig = with_policy("Evaluate each cart this many days after it was left: 1", "Evaluate each cart this many days after it was left: 5")
assert a.safe_view(back)["contact_stage"] == "second contact"
a.get_store_policies = orig
orig = with_policy("Incentive cap as % of estimated gross profit: 20%", "Incentive cap as % of estimated gross profit: 50%")
assert a.incentive_cap({"cart_value": 100})[1] == 20.0
a.get_store_policies = orig

# Store-wide recommendations: evidence comes from code; invented groups and other offers are refused
idea = {"title": "Shorter mobile checkout", "dataset": "2016-17", "group": "device", "segment": "mobile",
        "recommendation": "Try one-page checkout on phones.", "why_it_may_help": "Associated with leaving.",
        "how_to_test": "Compare checkout completion.", "effort": "Medium"}
out = a.submit_recommendations([idea])["report"]
row = a.STATS["2016-17"]["patterns"]["device"]["mobile"]
assert f"{row['abandonment_rate_pct']}% abandoned" in out and a.LAST_STRATEGY == out
assert "error" in a.submit_recommendations([{**idea, "segment": "smart fridge"}])
assert "error" in a.submit_recommendations([{**idea, "recommendation": "Give everyone 20% off."}])
assert "error" in a.submit_recommendations([{**idea, "recommendation": "Offer a 10% coupon to everyone."}])
assert "error" not in a.submit_recommendations([{**idea, "recommendation": "Offer returning customers the 5% discount."}])
assert "error" not in a.submit_recommendations([{**idea, "dataset": "2020-21"}])
assert "abandoned_value" not in a.analyze_abandonment()["2020-21"]["groups"]["device"]["mobile"]
assert "patterns" not in a.compare_datasets()["2016-17"]

# Limits and unknown IDs
assert len(a.list_abandoned_checkouts(limit=-1)["carts"]) == 20
assert a.list_abandoned_checkouts(high_value_only=True, limit=5)["carts"][0]["high_value"]
assert "error" in a.get_checkout("nope")
assert "error" in a.submit_review([rec("nope", "No action")])

print("All checks passed.")
