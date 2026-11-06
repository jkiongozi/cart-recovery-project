"""Cart Recovery Agent.

Run:  python agent.py
Then chat with it, e.g. "Review my 5 most recent carts".

The AI decides which tools to call; Python does the data access and math.
Only the prepared Excel data is used. Visitor IDs and locations never reach the AI.
"""
import csv
import json
import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from agent_data import load_for_app
from prepare_data import BASE, DATA_DIR
from risk import ACTIONS, average_cart, canonical_action, is_non_policy_discount

load_dotenv(os.path.join(BASE, ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
POLICIES = os.path.join(BASE, "prompts", "policies.md")

# ---------- Load the prepared data once at startup ----------
print("Loading carts from the prepared Excel data...")
CHECKOUTS, STATS = load_for_app()
AS_OF = STATS["2016-17"]["as_of_date"]
SIMULATED = all(c["marketing_state"] == "SUBSCRIBED" for c in CHECKOUTS)
BY_ID = {c["cart_id"]: c for c in CHECKOUTS}
AVG_CART = average_cart(CHECKOUTS)  # average of carts above $0
ZERO_CARTS = sum(1 for c in CHECKOUTS if c["cart_value"] <= 0)

# ---------- The agent's instructions ----------
with open(os.path.join(BASE, "prompts", "cart_recovery_system_prompt.md"), encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

SYSTEM_PROMPT += f"""

## Runtime context (added by the code)
- "Today" for this review is {AS_OF}, the last day of the data. Ages are counted from that date.
- Email consent is {"simulated: every cart is treated as subscribed" if SIMULATED else "unknown, so no email action is allowed"}.
- Your only data source is the prepared Excel data. No ML model is connected yet. Do not pretend to check other sources.
- Tools return facts only. Judging risk and choosing the action is YOUR job.
- For questions about all carts, call summarize_all_carts first, then look at the carts that matter.
"""


def safe_view(c):
    """Facts the AI is allowed to see: no visitor IDs or locations, and no verdicts."""
    subscribed = c["marketing_state"] == "SUBSCRIBED"
    orders = c.get("previous_orders", 0)
    return {
        "cart_id": c["cart_id"],
        "session_date": c["created_at"],
        "days_since_abandoned": c["days_since_abandoned"],
        "cart_value": c["cart_value"],
        "item_count": c["item_count"],
        "reached_checkout": bool(c["reached_checkout"]),
        "removed_items": bool(c["removed_from_cart"]),
        "device": c["device_category"],
        "traffic_source": c["traffic_source"],
        "traffic_medium": c["traffic_medium"],
        "pageviews": c["pageviews"],
        "time_on_site_seconds": c["time_on_site"],
        "visit_number": c["visit_number"],
        "email_subscribed": subscribed,
        "consent_is_simulated": subscribed,
        "returning_customer": orders > 0,
        # Policy fact: subscribed first-time buyers automatically get the 10% welcome offer
        "welcome_offer_applies": orders == 0 and subscribed,
        "previous_orders": orders,
        "lifetime_spend": c.get("lifetime_spend", 0.0),
    }


# ---------- Tools ----------
def list_abandoned_checkouts(limit=20, min_value=0, max_days_old=None, reached_checkout_only=False,
                             returning_only=False, sort_by="newest"):
    if not isinstance(limit, int) or limit < 1:
        limit = 20   # never pass a missing or negative limit into the slice
    views = [safe_view(c) for c in CHECKOUTS if c["cart_value"] >= (min_value or 0)]
    if max_days_old is not None:
        views = [v for v in views if v["days_since_abandoned"] <= max_days_old]
    if reached_checkout_only:
        views = [v for v in views if v["reached_checkout"]]
    if returning_only:
        views = [v for v in views if v["returning_customer"]]
    if sort_by == "value":
        views.sort(key=lambda v: (-v["cart_value"], v["cart_id"]))
    else:
        views.sort(key=lambda v: (v["days_since_abandoned"], v["cart_id"]))
    return {
        "total_found": len(views),
        "store_average_cart_value_excluding_zero": AVG_CART,
        "zero_value_carts_in_store": ZERO_CARTS,
        "carts": views[:limit],
    }


def _band(value, edges, labels):
    for edge, label in zip(edges, labels):
        if value <= edge:
            return label
    return labels[-1]


def summarize_all_carts():
    """Plain counts and dollar totals across every open cart. No verdicts."""
    views = [safe_view(c) for c in CHECKOUTS]
    groups = {"by_age": {}, "by_stage": {}, "by_device": {}, "by_customer": {}, "by_cart_value": {}}
    for v in views:
        keys = {
            "by_age": _band(v["days_since_abandoned"], [3, 7, 30],
                            ["0-3 days", "3-7 days", "7-30 days", "over 30 days"]),
            "by_stage": "reached checkout" if v["reached_checkout"] else "left before checkout",
            "by_device": v["device"],
            "by_customer": "returning customer" if v["returning_customer"] else "first-time buyer",
            "by_cart_value": _band(v["cart_value"], [0, 50, 150],
                                   ["$0", "$0.01-50", "$50-150", "over $150"]),
        }
        for group, key in keys.items():
            b = groups[group].setdefault(key, {"carts": 0, "value": 0.0})
            b["carts"] += 1
            b["value"] = round(b["value"] + v["cart_value"], 2)
    return {"total_open_carts": len(views), "total_value": round(sum(v["cart_value"] for v in views), 2),
            "zero_value_carts": ZERO_CARTS, "average_cart_excluding_zero": AVG_CART,
            "as_of_date": AS_OF, **groups}


def compare_datasets():
    """Rates from both files. 2020-21 has no dollar figures: its cart values are unreliable."""
    return {name: {k: v for k, v in s.items() if k != "patterns"} for name, s in STATS.items()}


def analyze_abandonment():
    """Abandonment by group across ALL cart sessions, for both periods. Facts only."""
    keep = 1 - (_policy_numbers()["product_cost_pct"] or 0) / 100
    out = {}
    for name, s in STATS.items():
        groups = {}
        for group, rows in s["patterns"].items():
            groups[group] = {k: ({**r, "store_keeps_on_abandoned_value": round(r["abandoned_value"] * keep, 2)}
                                 if "abandoned_value" in r else r) for k, r in rows.items()}
        out[name] = {"period": s["period"], "overall_abandonment_rate_pct": s["abandonment_rate_pct"],
                     "groups": groups}
    return {**out, "how_to_read": "points_vs_overall above 0 means this group abandons more than average. "
            "Groups under 100 sessions are left out. 2020-21 has no dollar, cart value or product count groups."}


OFFER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:off|discount|coupon|promo)|"
                      r"(?:discount|coupon|promo)\w*\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)", re.I)


def _policy_conflict(text):
    """Offers bigger than the policy allows. 5% (recovery) and 10% (welcome offer) are the only policy sizes."""
    for m in OFFER_RE.finditer(text):
        pct = float(m.group(1) or m.group(2))
        if pct not in (5, 10):
            return f"proposes a {pct:g}% offer; the policies only allow the 5% recovery discount and the 10% welcome offer"
    return None


def submit_recommendations(recommendations, notes=""):
    """Finish a strategy answer: the AI gives ideas; Python adds the evidence and checks the policies."""
    cards, rejected = [], []
    for r in recommendations:
        title = _cell(r.get("title", "Untitled"))
        dataset, group, segment = r.get("dataset"), r.get("group"), r.get("segment")
        row = STATS.get(dataset, {}).get("patterns", {}).get(group, {}).get(segment)
        if row is None:
            rejected.append(f"{title}: no evidence for {dataset} / {group} / {segment}")
            continue
        text = " ".join(str(r.get(k, "")) for k in ("recommendation", "why_it_may_help", "how_to_test"))
        conflict = _policy_conflict(text)
        if conflict:
            rejected.append(f"{title}: {conflict}")
            continue
        value = (f"; ${row['abandoned_value']:,.2f} abandoned" if "abandoned_value" in row else "")
        cards.append("\n".join([
            f"{len(cards) + 1}. **{title}** (effort: {r.get('effort', 'not given')})  ",
            f"   - **Do this:** {_cell(r.get('recommendation', ''))}  ",
            f"   - **Evidence ({dataset}):** {segment}: {row['abandonment_rate_pct']}% abandoned, "
            f"{row['points_vs_overall']:+.1f} points vs. overall, {row['sessions']:,} sessions{value}  ",
            f"   - **Why it may help:** {_cell(r.get('why_it_may_help', ''))}  ",
            f"   - **How to test it:** {_cell(r.get('how_to_test', ''))}",
            ""]))
    if not cards:
        return {"error": f"No recommendation passed the checks: {rejected}. Fix them and call this tool again."}
    report = "\n".join([
        f"Here are {len(cards)} recommendation{'s' if len(cards) != 1 else ''} to reduce cart abandonment:", "",
        *cards,
        *([f"- {_cell(notes)}"] if notes else []),
        "- Evidence figures are computed in code. They show patterns in Google Merchandise Store data, "
        "not causes, and not Jb Prints shoppers.",
        "- The ideas are the AI's. None has been tested, so no improvement is promised.",
        *[f"- Left out: {x}" for x in rejected],
    ])
    global LAST_STRATEGY
    LAST_STRATEGY = report
    return {"report": report}


LAST_STRATEGY = None   # most recent recommendations, saved to data/latest_recommendations.md


def get_checkout(cart_id):
    c = BY_ID.get(str(cart_id))
    if not c:
        return {"error": f"No cart with id {cart_id}"}
    return {**safe_view(c), "store_average_cart_value": AVG_CART}


def get_review_rows(cart_ids):
    """One row per cart, plus exact totals. Facts only."""
    rows, missing = [], []
    for cid in cart_ids:
        c = BY_ID.get(str(cid))
        if c:
            rows.append(safe_view(c))
        else:
            missing.append(cid)
    return {
        "rows": rows,
        "cart_count": len(rows),
        "total_value_of_these_carts": round(sum(r["cart_value"] for r in rows), 2),
        "not_found": missing,
    }


def get_store_policies():
    if not os.path.exists(POLICIES):
        return {"policies": "No policy file found. Policy information is unavailable."}
    with open(POLICIES, encoding="utf-8") as f:
        return {"policies": f.read()}


RECOVERY_ACTIONS = {"Reminder email", "Free shipping", "5% discount"}   # actions that try to win the sale
PASSIVE_ACTIONS = {"No action", "Escalate for human review"}           # margin only if they return on their own


def _policy_numbers():
    """Read the numbers the profit math needs from prompts/policies.md. '?' means unknown (None)."""
    text = get_store_policies()["policies"]

    def find(label):
        for line in text.splitlines():
            if line.strip("- ").lower().startswith(label.lower() + ":"):   # exact label, not "Free shipping threshold"
                value = line.split(":", 1)[-1]
                m = re.search(r"\d+(?:\.\d+)?", value)
                return None if ("?" in value.split("(")[0] or not m) else float(m.group())
        return None

    return {
        "product_cost_pct": find("Average product cost as % of price"),
        "email_cost": find("Cost to send one recovery email"),
        "free_shipping_cost": find("Average shipping cost per order"),
        "max_discount_pct": find("Maximum recovery discount allowed"),
        "rates": {a: find(a) for a in ACTIONS},
    }


def calculate_profit(cart_id, actions=None):
    """Profit math done entirely in Python from the cart and the store policies.
    Returns facts for each action; the AI decides which action to recommend."""
    c = BY_ID.get(str(cart_id))
    if not c:
        return {"error": f"No cart with id {cart_id}"}
    pol = _policy_numbers()
    if pol["product_cost_pct"] is None:
        return {"error": "Product cost % is unknown in policies.md, so profit cannot be calculated."}
    value = c["cart_value"]
    products = value                                     # the data has no shipping, tax or line discounts
    keep = products * (1 - pol["product_cost_pct"] / 100)   # what the store keeps on this cart
    subscribed = c["marketing_state"] == "SUBSCRIBED"
    returning = c.get("previous_orders", 0) > 0
    results = []
    for action in (actions or ACTIONS):
        if action not in ACTIONS:
            results.append({"action": action, "error": f"Unknown action. Use one of {ACTIONS}"})
            continue
        r = {"action": action}
        why_not = None
        if action in RECOVERY_ACTIONS and not subscribed:
            why_not = "Customer is not subscribed to email marketing"
        elif action == "5% discount" and not returning:
            why_not = "First-time buyer: the policy discount is only for returning customers"
        if why_not:
            r.update({"allowed": False, "why_not": why_not})
            results.append(r)
            continue

        unknown = None
        message_cost = pol["email_cost"] if action in RECOVERY_ACTIONS else 0.0
        if message_cost is None:
            unknown = "email cost is missing in policies.md"
        incentive = 0.0
        if action == "Free shipping":
            if pol["free_shipping_cost"] is None:
                unknown = "free-shipping cost is missing in policies.md"
            else:
                incentive = pol["free_shipping_cost"]
        if action == "5% discount":
            if pol["max_discount_pct"] is None:
                unknown = "maximum recovery discount is missing in policies.md"
            else:
                incentive = products * pol["max_discount_pct"] / 100
        r["allowed"] = True
        if action == "5% discount":
            r["discount_pct_from_policy"] = pol["max_discount_pct"]
            r["sale_check"] = "Sale status is not in this data; check before any discount"
        if unknown:
            r.update({"profit_if_recovered": None, "expected_profit": None,
                      "note": f"Profit unknown: {unknown}. Do not estimate it."})
            results.append(r)
            continue
        profit_if_recovered = keep - incentive - (message_cost or 0.0)
        rate = pol["rates"].get(action)
        r.update({
            "store_keeps_before_costs": round(keep, 2),
            "incentive_cost_if_recovered": round(incentive, 2),
            "message_cost": round(message_cost or 0.0, 2),
            "profit_if_recovered": round(profit_if_recovered, 2),
            "purchase_rate": f"{rate:g}%" if rate is not None else "unknown",
            "expected_profit": (round(rate / 100 * (keep - incentive) - (message_cost or 0.0), 2)
                                if rate is not None else None),
        })
        if action in PASSIVE_ACTIONS:
            r["meaning"] = "Full margin if the customer returns on their own; not profit from an action"
        if rate is None:
            r["note"] = "Purchase rate is '?' in policies.md, so expected profit is unknown. Do not estimate it."
        results.append(r)
    return {"cart_id": c["cart_id"], "cart_value": value, "results": results}


def record_recommendation(cart_id, recommended_action, reason, confidence, expected_profit=None):
    # Store policy, enforced in code: only the policy discount, and only for returning customers.
    c = BY_ID.get(str(cart_id))
    action = canonical_action(recommended_action) or recommended_action
    if is_non_policy_discount(recommended_action):
        return {"saved": False,
                "error": "Only the policy discount for returning customers is allowed; "
                         f"'{recommended_action}' is not a store policy action."}
    if c and action == "5% discount" and c.get("previous_orders", 0) == 0:
        return {"saved": False,
                "error": "Policy: this customer has no previous orders, so they are a first-time buyer. "
                         "The policy discount is only for returning customers."}
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "recommendations.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "cart_id", "recommended_action", "reason",
                        "confidence", "expected_profit", "status"])
        w.writerow([datetime.now(timezone.utc).isoformat(), cart_id, action,
                    reason, confidence, expected_profit, "Requires Human Approval"])
    return {"saved": True, "status": "Requires Human Approval"}


def _cell(x):
    return str(x).replace("|", "/").replace("\n", " ")


def submit_review(carts, notes=""):
    """Finish a review: the AI gives judgments only; Python builds the table, profit figures and totals,
    applies the policy checks and records every recommendation."""
    rows, why, skipped = [], [], []
    total = recovery_profit = passive_margin = 0.0
    unknown_profit_carts = []
    actions_count, cards = {}, []
    seen = set()
    for j in carts:
        cid = str(j.get("cart_id"))
        c = BY_ID.get(cid)
        if not c or cid in seen:
            skipped.append(cid)
            continue
        seen.add(cid)
        v = safe_view(c)
        total += c["cart_value"]
        suggested = (j.get("recommendation") or "").strip()
        blocked_reason = None

        key = canonical_action(suggested)
        if key is None and is_non_policy_discount(suggested):
            blocked_reason = "only the policy discount for returning customers is allowed"
            key = "No action"
        profit = None
        if key:
            profit = calculate_profit(cid, [key])["results"][0]
            if profit.get("allowed") is False:
                blocked_reason = profit.get("why_not")
                key = "No action"
                profit = calculate_profit(cid, ["No action"])["results"][0]
        action = key or suggested or "not given"   # unmatched text is kept as written, never guessed

        if profit and profit.get("profit_if_recovered") is not None:
            p = profit["profit_if_recovered"]
            profit_cell = f"${p:,.2f}"
            if key in RECOVERY_ACTIONS:
                recovery_profit += p
                label = "profit if recovered"
            else:
                passive_margin += p
                label = "margin if they return on their own"
            profit_txt = (f"{label} ${p:,.2f}; expected profit "
                          + (f"${profit['expected_profit']:,.2f}" if profit.get("expected_profit") is not None
                             else "unknown (purchase rate missing)"))
            known = profit.get("expected_profit") is not None
        elif profit:
            profit_cell, known = "unknown", False
            profit_txt = profit.get("note", "unknown")
            unknown_profit_carts.append(cid)
        else:
            profit_cell, known = "n/a", False
            profit_txt = "n/a (action not in the standard list)"
        confidence = j.get("confidence") or "Low"
        if not known:
            confidence = "Low"   # cannot be higher while expected profit is unknown

        saved = record_recommendation(cid, action, blocked_reason or j.get("reason", ""), confidence,
                                      profit.get("expected_profit") if profit else None)
        if not saved.get("saved"):
            blocked_reason = saved.get("error", "blocked by policy")
            action = "No action"
            record_recommendation(cid, action, blocked_reason, "Low")
        actions_count[action] = actions_count.get(action, 0) + 1
        shown_action = f"{action} (AI suggested {suggested}, blocked: {blocked_reason})" \
            if blocked_reason else action

        rows.append((c["cart_value"], "| " + " | ".join(_cell(x) for x in [
            cid, v["session_date"], v["days_since_abandoned"], v["item_count"], f"${c['cart_value']:,.2f}",
            "Yes" if v["reached_checkout"] else "No", v["device"], v["traffic_medium"],
            ("Yes (simulated)" if SIMULATED else "No"), "Yes" if v["returning_customer"] else "No",
            j.get("risk", ""), shown_action, profit_cell]) + " |"))
        days = v["days_since_abandoned"]
        cards.append((c["cart_value"], cid, j.get("risk", ""), _cell(j.get("risk_reason", "")),
                      shown_action, _cell(blocked_reason or j.get("reason", "")), confidence))
        why.append(f"- **{cid}** ({days} day{'' if days == 1 else 's'} before the end of the data): "
                   f"{_cell(j.get('risk_reason', ''))} → **{_cell(shown_action)}**: {_cell(j.get('reason', ''))} "
                   f"Profit: {profit_txt}. Confidence: {confidence}.")

    if not rows:
        return {"error": f"No valid cart IDs: {skipped}. Use IDs returned by the tools."}
    rows.sort(key=lambda r: -r[0])
    cards.sort(key=lambda x: -x[0])
    card_lines = [f"Here are the details and recommendations for your {len(cards)} "
                  f"abandoned cart{'s' if len(cards) != 1 else ''}:", ""]
    for n, (value, cid, risk, risk_reason, act, reason, conf) in enumerate(cards, start=1):
        card_lines += [
            f"{n}. **Cart ID:** {cid}  ",
            f"   - **Value:** ${value:,.2f}  ",
            f"   - **Risk:** {risk} — {risk_reason}  ",
            f"   - **Recommendation:** {act}  ",
            f"   - **Reason:** {reason}  ",
            f"   - **Confidence:** {conf}",
            "",
        ]
    card_lines += ["### Summary of Recommendations:"]
    card_lines += [f"- **{a}:** {n} cart{'s' if n != 1 else ''}." for a, n in actions_count.items()]
    card_lines += [
        f"- **Total value at risk:** ${total:,.2f}",
        f"- **Profit if the carts with a recovery action are recovered:** ${recovery_profit:,.2f}",
        "- Every recommendation requires your approval. The full table is saved to data/latest_review.md.",
    ]
    cards_md = "\n".join(card_lines)
    report = "\n".join([
        "| Cart | Session date | Days old | Products | Cart value | Reached checkout | Device | Traffic "
        "| Subscribed | Returning | Risk | AI recommendation | Profit if recovered |",
        "|" + " --- |" * 13,
        *[r[1] for r in rows], "", "**Why**", "", *why, "", "**Summary**", "",
        f"- Carts reviewed: {len(seen)} · Total value at risk: **${total:,.2f}**",
        f"- Profit from carts with a recovery action (Reminder email, Free shipping, 5% discount), "
        f"if they are recovered: **${recovery_profit:,.2f}**",
        f"- Margin on \"No action\" and \"Escalate for human review\" carts if they return on their own "
        f"(not profit from an action): ${passive_margin:,.2f}",
        *([f"- Profit unknown for: {', '.join(unknown_profit_carts)} (missing numbers in policies.md)"]
          if unknown_profit_carts else []),
        "- Recommended actions: " + ", ".join(f"{a} ({n})" for a, n in actions_count.items()),
        *([f"- {_cell(notes)}"] if notes else []),
        "- Profit if recovered = cart value × 40%, minus the action's cost",
        f"- Days old are counted from {AS_OF}, the last day of the data",
        *(["- Email subscription is simulated: the data has no consent field"] if SIMULATED else []),
        "- Every recommendation: **Requires Human Approval** (saved to data/recommendations.csv)",
        *([f"- Skipped unknown or repeated IDs: {skipped}"] if skipped else []),
    ])
    global LAST_REVIEW
    LAST_REVIEW = cards_md + "\n\n---\n\n## Full table\n\n" + report
    return {"report": cards_md}


LAST_REVIEW = None   # list + full table of the most recent review, saved to data/latest_review.md


FUNCTIONS = {
    "list_abandoned_checkouts": list_abandoned_checkouts,
    "get_checkout": get_checkout,
    "summarize_all_carts": summarize_all_carts,
    "get_review_rows": get_review_rows,
    "compare_datasets": compare_datasets,
    "analyze_abandonment": analyze_abandonment,
    "submit_recommendations": submit_recommendations,
    "get_store_policies": get_store_policies,
    "calculate_profit": calculate_profit,
    "submit_review": submit_review,
}

TOOLS = [
    {"type": "function", "function": {
        "name": "list_abandoned_checkouts",
        "description": "List open abandoned carts: value, number of products, age, device, traffic source, checkout stage and purchase history. No personal data.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max carts to return"},
            "min_value": {"type": "number", "description": "Only carts worth at least this much"},
            "max_days_old": {"type": "number", "description": "Only carts within this many days of the end of the data"},
            "reached_checkout_only": {"type": "boolean", "description": "Only carts that reached checkout"},
            "returning_only": {"type": "boolean", "description": "Only returning customers"},
            "sort_by": {"type": "string", "enum": ["newest", "value"]}}}}},
    {"type": "function", "function": {
        "name": "summarize_all_carts",
        "description": "Counts and dollar totals across ALL open carts, grouped by age, checkout stage, device, customer type and cart value.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "compare_datasets",
        "description": "Abandonment, checkout and device rates, and how often shoppers came back on their own, for 2016-17 and 2020-21. No dollar figures for 2020-21.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "analyze_abandonment",
        "description": "Abandonment across ALL cart sessions, by device, traffic, visit type, customer type, day, checkout stage and, for 2016-17, cart value, products and removals. Call it before giving advice on reducing abandonment.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "submit_recommendations",
        "description": ("Finish every answer about reducing abandonment. Give 3 to 5 ideas, most important first. "
                        "Point each one at a group from analyze_abandonment. The code adds the evidence figures, "
                        "checks the store policies and shows the owner the result."),
        "parameters": {"type": "object", "properties": {
            "recommendations": {"type": "array", "items": {"type": "object", "properties": {
                "title": {"type": "string", "description": "A few words"},
                "dataset": {"type": "string", "enum": ["2016-17", "2020-21"]},
                "group": {"type": "string", "description": "Group name exactly as in analyze_abandonment, e.g. device"},
                "segment": {"type": "string", "description": "Value exactly as in analyze_abandonment, e.g. mobile"},
                "recommendation": {"type": "string", "description": "The specific change to make. No numbers about the data"},
                "why_it_may_help": {"type": "string", "description": "One sentence. Say associated, never caused"},
                "how_to_test": {"type": "string", "description": "One sentence: what to compare and what to measure"},
                "effort": {"type": "string", "enum": ["Low", "Medium", "High"]}},
                "required": ["title", "dataset", "group", "segment", "recommendation", "why_it_may_help",
                             "how_to_test", "effort"]}},
            "notes": {"type": "string", "description": "Optional one-line observation"}},
            "required": ["recommendations"]}}},
    {"type": "function", "function": {
        "name": "get_review_rows",
        "description": "For a list of carts: one row per cart and the exact total value of those carts.",
        "parameters": {"type": "object", "properties": {
            "cart_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["cart_ids"]}}},
    {"type": "function", "function": {
        "name": "get_checkout",
        "description": "Get one abandoned cart.",
        "parameters": {"type": "object", "properties": {
            "cart_id": {"type": "string"}}, "required": ["cart_id"]}}},
    {"type": "function", "function": {
        "name": "get_store_policies",
        "description": "Read the store's discount, shipping and cost policies and estimated purchase rates.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "calculate_profit",
        "description": ("Exact profit figures for one cart, computed in Python from the store policies: "
                        "for each action, whether it is allowed, the profit if the cart is recovered, and the "
                        "expected profit (only when the purchase rate is known). Never calculate profit yourself."),
        "parameters": {"type": "object", "properties": {
            "cart_id": {"type": "string"},
            "actions": {"type": "array", "items": {"type": "string", "enum": ACTIONS},
                        "description": "Actions to compare; leave out to compare all"}},
            "required": ["cart_id"]}}},
    {"type": "function", "function": {
        "name": "submit_review",
        "description": ("Finish a cart review. Give ONLY your judgments for each cart. The code adds every "
                        "fact, the profit figures and the totals, checks the store policies, records each "
                        "recommendation and shows the owner the table."),
        "parameters": {"type": "object", "properties": {
            "carts": {"type": "array", "items": {"type": "object", "properties": {
                "cart_id": {"type": "string"},
                "risk": {"type": "string", "enum": ["Low", "Medium", "High"]},
                "risk_reason": {"type": "string", "description": "One short sentence"},
                "recommendation": {"type": "string", "enum": ACTIONS,
                                   "description": "Exactly one of the five store actions"},
                "reason": {"type": "string", "description": "One short sentence: why this action"},
                "confidence": {"type": "string", "enum": ["Low", "Medium", "High"]}},
                "required": ["cart_id", "risk", "risk_reason", "recommendation", "reason", "confidence"]}},
            "notes": {"type": "string", "description": "Optional one-line observation for the summary"}},
            "required": ["carts"]}}},
]


# ---------- Talking to OpenAI ----------
def call_openai(messages, force_tool=None):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS}
    if force_tool:  # make the model call this specific tool next
        body["tool_choice"] = {"type": "function", "function": {"name": force_tool}}
    resp = requests.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    if resp.status_code != 200:
        detail = resp.json().get("error", {}).get("message", resp.text) if resp.text else ""
        hints = {
            401: "Check OPENAI_API_KEY in .env.",
            404: f"The model '{MODEL}' was not found. Set OPENAI_MODEL in .env to a model listed on platform.openai.com.",
            429: "Rate limit or no credit. Check Settings -> Billing on platform.openai.com.",
        }
        raise RuntimeError(f"OpenAI error {resp.status_code}: {detail}\n{hints.get(resp.status_code, '')}")
    return resp.json()["choices"][0]["message"]


# ---------- The agent loop ----------
def _looks_like_review_table(text):
    """True if the model wrote a cart table itself instead of calling submit_review."""
    table = "|" in text and "Cart" in text and "---" in text
    card_list = "Cart ID" in text and "Recommendation" in text
    return bool(text) and (table or card_list)


def run_agent(messages, max_steps=25):
    force = None
    for _ in range(max_steps):
        report = None
        msg = call_openai(messages, force_tool=force)
        force = None
        messages.append({k: v for k, v in msg.items() if v is not None})
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            text = msg.get("content") or ""
            if _looks_like_review_table(text):
                # Guard: tables are built by Python, never typed by the model.
                print("  [The agent wrote its own table; sending it back to use submit_review]")
                messages.append({"role": "user", "content": (
                    "Do not write the review yourself and do not ask for confirmation. Call submit_review now with your "
                    "judgments (risk, risk_reason, recommendation, reason, confidence) for each of these carts.")})
                force = "submit_review"
                continue
            return text
        for call in tool_calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                print(f"  [Agent is using: {name} {args if args else ''}]")
                result = FUNCTIONS[name](**args)
            except Exception as e:
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, default=str)})
            if name in ("submit_review", "submit_recommendations") and isinstance(result, dict) and "report" in result:
                report = result["report"]
        if report:
            return report   # the table Python built is the answer
    return "I stopped after too many steps. Try a narrower request, such as one cart at a time."


def save_review(question, answer):
    """Save the latest answer as a formatted file (open it in VS Code with Ctrl+Shift+V, or in the dashboard)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(DATA_DIR, "latest_review.md"), "w", encoding="utf-8") as f:
        f.write(f"# Cart recovery review\n\n*{stamp}* · **You asked:** {question}\n\n{answer}\n")
    print("  [Formatted copy saved to data/latest_review.md]\n")


def save_recommendations(question, answer):
    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(DATA_DIR, "latest_recommendations.md"), "w", encoding="utf-8") as f:
        f.write(f"# How to reduce cart abandonment\n\n*{stamp}* · **You asked:** {question}\n\n{answer}\n")
    print("  [Formatted copy saved to data/latest_recommendations.md]\n")


if __name__ == "__main__":
    if not OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is missing from .env")
    print(f"Cart Recovery Agent ready. {len(CHECKOUTS):,} open carts loaded "
          f"(average cart excluding $0: ${AVG_CART:,.2f}; {ZERO_CARTS} carts are $0). Model: {MODEL}. Type 'quit' to exit.")
    print(f"Ages are counted from {AS_OF}. Email subscription: {'simulated' if SIMULATED else 'unknown, email actions blocked'}.\n")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        user = input("You: ").strip()
        if user.lower() in ("quit", "exit"):
            break
        if not user:
            continue
        before = len(messages)
        messages.append({"role": "user", "content": user})
        try:
            LAST_REVIEW = LAST_STRATEGY = None
            answer = run_agent(messages)
            print("\nAgent:", answer, "\n")
            if LAST_REVIEW:   # only a new review overwrites the saved file (list + full table)
                save_review(user, LAST_REVIEW)
            if LAST_STRATEGY:
                save_recommendations(user, LAST_STRATEGY)
        except Exception as e:
            print(f"\n[Error] {e}\n")
            del messages[before:]  # forget the failed turn so you can retry
