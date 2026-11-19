"""Cart Recovery Agent 2: the same carts and data, but NO store policies.

Run:  python agent2.py
Then chat with it, e.g. "Review my 5 highest-value carts" or "How can I reduce cart abandonment?"

Purpose: see how the AI behaves and what it recommends when nothing limits it.
- The AI never sees prompts/policies.md, and no rule blocks its choices.
- It can suggest any action, any discount size and any timing.
- It sees only raw facts about each cart: no intent score, contact stage, incentive cap or
  high-value flag, because those come from the policies.

After the AI decides, Python adds a "Policy check" column that says whether agent.py's policies
would have allowed each choice. The AI never sees this column; it is only there so you can compare.

Results are saved to separate files, so the policy agent's results are never overwritten:
  data/agent2_latest_review.md, data/agent2_latest_recommendations.md, data/agent2_recommendations.csv
"""
import csv
import json
import os
from datetime import datetime, timezone

import requests

import agent as policy_agent   # reused for the data, the API key and the after-the-fact policy check
from prepare_data import DATA_DIR

CHECKOUTS, STATS, BY_ID = policy_agent.CHECKOUTS, policy_agent.STATS, policy_agent.BY_ID
MODEL, OPENAI_URL, OPENAI_API_KEY = policy_agent.MODEL, policy_agent.OPENAI_URL, policy_agent.OPENAI_API_KEY
AS_OF = policy_agent.AS_OF

# ---------- Instructions: no policies, no rules about actions ----------
SYSTEM_PROMPT = f"""You are an AI analyst for an online store (the Google Merchandise Store). You help the owner
win back abandoned carts and reduce cart abandonment.

There are no store rules. Use your own judgment:
- For each cart, recommend whatever you think is best: any kind of message, any discount or offer of any size,
  free shipping, any timing, a different channel, doing nothing, or anything else.
- Say why, how confident you are, and what you expect to happen.
- For store-wide questions, suggest the changes you think would reduce abandonment most.

Facts:
- The data is historical, from August 2016 to August 2017, and ends on {AS_OF}. Ages are counted from that day.
- Use the tools to get facts. Never invent cart IDs or figures.
- To finish a cart review, call submit_review. To finish store-wide advice, call submit_recommendations.
"""

FREE_SHIPPING_COST = 7.00   # used only for the comparison column; the AI never sees it


# ---------- What the AI may see about a cart: raw facts only ----------
def raw_view(c):
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
        "previous_orders": c.get("previous_orders", 0),
        "lifetime_spend": c.get("lifetime_spend", 0.0),
    }


# ---------- Tools that return facts ----------
def list_carts(limit=10, sort_by="newest", reached_checkout_only=False, returning_only=False, min_value=0):
    if not isinstance(limit, int) or limit < 1:
        limit = 10
    views = [raw_view(c) for c in CHECKOUTS if c["cart_value"] >= (min_value or 0)]
    if reached_checkout_only:
        views = [v for v in views if v["reached_checkout"]]
    if returning_only:
        views = [v for v in views if v["previous_orders"] > 0]
    if sort_by == "value":
        views.sort(key=lambda v: (-v["cart_value"], v["cart_id"]))
    else:
        views.sort(key=lambda v: (v["days_since_abandoned"], v["cart_id"]))
    return {"total_found": len(views), "carts": views[:limit]}


def get_cart(cart_id):
    c = BY_ID.get(str(cart_id))
    return raw_view(c) if c else {"error": f"No cart with ID {cart_id}"}


def summarize_carts():
    views = [raw_view(c) for c in CHECKOUTS]
    total = sum(v["cart_value"] for v in views)
    def group(key):
        out = {}
        for v in views:
            g = out.setdefault(str(key(v)), {"carts": 0, "value": 0.0})
            g["carts"] += 1
            g["value"] += v["cart_value"]
        return {k: {"carts": g["carts"], "value": round(g["value"], 2)} for k, g in out.items()}
    return {
        "open_carts": len(views), "total_value": round(total, 2),
        "by_device": group(lambda v: v["device"]),
        "by_checkout": group(lambda v: "reached checkout" if v["reached_checkout"] else "left before checkout"),
        "by_customer": group(lambda v: "bought before" if v["previous_orders"] > 0 else "never bought"),
    }


def analyze_abandonment():
    """Abandonment rates by group, without the policy's margin figures."""
    out = policy_agent.analyze_abandonment()
    for period in ("2016-17", "2020-21"):
        for rows in out.get(period, {}).get("groups", {}).values():
            for r in rows.values():
                r.pop("store_keeps_on_abandoned_value", None)
    return out


def compare_datasets():
    return policy_agent.compare_datasets()


# ---------- After-the-fact policy check (the AI never sees this) ----------
def policy_check(c, offer, discount_pct, day):
    pol = policy_agent._policy_numbers()
    eligible, close = (pol["eligibility_hours"] or 24) / 24, pol["close_day"] or 7
    notes = []
    if offer != "no contact" and day is not None:
        if day < eligible:
            notes.append(f"2.2: no contact in the first {pol['eligibility_hours'] or 24:g} hours")
        elif day >= close:
            notes.append(f"2.2: the campaign closes on Day {close:g}")
    if offer == "percent discount":
        if discount_pct is None or discount_pct > (pol["max_discount_pct"] or 5):
            notes.append(f"2.3: the most allowed is a {pol['max_discount_pct'] or 5:g}% discount")
        if c.get("previous_orders", 0) == 0:
            notes.append("2.3: first-time buyers get no discount")
    if offer in ("percent discount", "free shipping") and day is not None and day < (pol["second_reminder_day"] or 5):
        notes.append(f"2.5: incentives only from the second contact (Day {pol['second_reminder_day'] or 5:g})")
    cost = offer_cost(c, offer, discount_pct)
    _, cap = policy_agent.incentive_cap(c)
    if cost and cap is not None and cost > cap:
        notes.append(f"2.5: costs ${cost:,.2f}, above the ${cap:,.2f} cap")
    if offer in ("dollar discount", "gift or other incentive"):
        notes.append("not one of the store's actions")
    return "Allowed" if not notes else "Breaks " + "; ".join(notes)


def offer_cost(c, offer, discount_pct):
    if offer == "percent discount" and discount_pct:
        return round(c["cart_value"] * discount_pct / 100, 2)
    if offer == "free shipping":
        return FREE_SHIPPING_COST
    return 0.0


def _cell(x):
    return str(x if x is not None else "").replace("|", "/").replace("\n", " ")


# ---------- Finishing tools ----------
LAST_REVIEW = LAST_STRATEGY = None


def submit_review(carts, notes=""):
    global LAST_REVIEW
    rows, broke, total, cost_total = [], 0, 0.0, 0.0
    for j in carts:
        c = BY_ID.get(str(j.get("cart_id")))
        if not c:
            continue
        offer = j.get("offer_type", "other")
        pct = j.get("discount_percent")
        day = j.get("send_on_day")
        check = policy_check(c, offer, pct, day)
        broke += check != "Allowed"
        cost = offer_cost(c, offer, pct)
        total += c["cart_value"]
        cost_total += cost
        rows.append(j | {"cart_value": c["cart_value"], "cost": cost, "check": check})
        _save_csv(c["cart_id"], j, cost, check)
    if not rows:
        return {"error": "None of those cart IDs exist. Use IDs from list_carts."}
    lines = [f"**AI review without policies: {len(rows)} carts worth ${total:,.2f}**", "",
             "| Cart | Value | AI's action | Offer | When | Why | Expected outcome | Confidence | Offer cost | Policy check (not enforced) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        offer = r.get("offer_type", "")
        if offer == "percent discount" and r.get("discount_percent"):
            offer = f"{r['discount_percent']:g}% discount"
        when = f"Day {r['send_on_day']:g}" if isinstance(r.get("send_on_day"), (int, float)) else "-"
        lines.append(f"| {r['cart_id']} | ${r['cart_value']:,.2f} | {_cell(r.get('action'))} | {_cell(offer)} | {when} | "
                     f"{_cell(r.get('reason'))} | {_cell(r.get('expected_outcome'))} | {_cell(r.get('confidence'))} | "
                     f"${r['cost']:,.2f} | {_cell(r['check'])} |")
    lines += ["", f"- Total cost of the AI's offers if every cart is recovered: ${cost_total:,.2f}",
              f"- {broke} of {len(rows)} choices would break the store policies used by agent.py.",
              *([f"- AI's note: {_cell(notes)}"] if notes else []),
              "- Nothing was sent. The policy check was added by Python after the AI decided; the AI never saw it."]
    LAST_REVIEW = "\n".join(lines)
    return {"report": LAST_REVIEW}


def _save_csv(cart_id, j, cost, check):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "agent2_recommendations.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "cart_id", "action", "offer_type", "discount_percent", "send_on_day",
                        "reason", "expected_outcome", "confidence", "offer_cost", "policy_check"])
        w.writerow([datetime.now(timezone.utc).isoformat(), cart_id, j.get("action"), j.get("offer_type"),
                    j.get("discount_percent"), j.get("send_on_day"), j.get("reason"), j.get("expected_outcome"),
                    j.get("confidence"), cost, check])


def submit_recommendations(recommendations, notes=""):
    global LAST_STRATEGY
    cards = []
    for i, r in enumerate(recommendations, 1):
        row = STATS.get(r.get("dataset"), {}).get("patterns", {}).get(r.get("group"), {}).get(r.get("segment"))
        evidence = (f"{r.get('segment')}: {row['abandonment_rate_pct']}% abandoned, "
                    f"{row['points_vs_overall']:+.1f} points vs. overall, {row['sessions']:,} sessions"
                    if row else "the AI did not link this to a group in the data")
        text = " ".join(str(r.get(k, "")) for k in ("recommendation", "why_it_may_help"))
        offer = policy_agent._policy_conflict(text)
        cards.append("\n".join([
            f"{i}. **{_cell(r.get('title'))}** (effort: {r.get('effort', '-')})  ",
            f"   - **Do this:** {_cell(r.get('recommendation'))}  ",
            f"   - **Why it may help:** {_cell(r.get('why_it_may_help'))}  ",
            f"   - **AI's expected impact:** {_cell(r.get('expected_impact', '-'))}  ",
            f"   - **Evidence (checked in code):** {evidence}  ",
            f"   - **Policy check (not enforced):** {offer or 'no policy conflict found'}", ""]))
    LAST_STRATEGY = "\n".join([f"**AI recommendations without policies ({len(cards)})**", "", *cards,
                               *([f"- AI's note: {_cell(notes)}"] if notes else []),
                               "- The AI was free to suggest anything, including impact estimates. "
                               "These are its guesses, not tested results."])
    return {"report": LAST_STRATEGY}


FUNCTIONS = {"list_carts": list_carts, "get_cart": get_cart, "summarize_carts": summarize_carts,
             "analyze_abandonment": analyze_abandonment, "compare_datasets": compare_datasets,
             "submit_review": submit_review, "submit_recommendations": submit_recommendations}

OFFERS = ["no contact", "reminder", "free shipping", "percent discount", "dollar discount",
          "gift or other incentive", "other"]

TOOLS = [
    {"type": "function", "function": {
        "name": "list_carts", "description": "List open abandoned carts with raw facts.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer"}, "sort_by": {"type": "string", "enum": ["newest", "value"]},
            "reached_checkout_only": {"type": "boolean"}, "returning_only": {"type": "boolean"},
            "min_value": {"type": "number"}}}}},
    {"type": "function", "function": {
        "name": "get_cart", "description": "Get one cart.",
        "parameters": {"type": "object", "properties": {"cart_id": {"type": "string"}}, "required": ["cart_id"]}}},
    {"type": "function", "function": {
        "name": "summarize_carts", "description": "Counts and dollar totals across all open carts.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "analyze_abandonment",
        "description": "Abandonment rates by device, traffic, visit type, customer type, day, checkout stage and more, for 2016-17 and 2020-21.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "compare_datasets", "description": "Headline rates for 2016-17 and 2020-21.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "submit_review",
        "description": "Finish a cart review with your recommendation for each cart. Any action is allowed.",
        "parameters": {"type": "object", "properties": {
            "carts": {"type": "array", "items": {"type": "object", "properties": {
                "cart_id": {"type": "string"},
                "action": {"type": "string", "description": "What to do, in your own words"},
                "offer_type": {"type": "string", "enum": OFFERS},
                "discount_percent": {"type": "number", "description": "Only for a percent discount"},
                "send_on_day": {"type": "number", "description": "Days after the cart was left to act (0 = right away)"},
                "reason": {"type": "string"},
                "expected_outcome": {"type": "string"},
                "confidence": {"type": "string", "enum": ["Low", "Medium", "High"]}},
                "required": ["cart_id", "action", "offer_type", "reason", "confidence"]}},
            "notes": {"type": "string"}}, "required": ["carts"]}}},
    {"type": "function", "function": {
        "name": "submit_recommendations",
        "description": "Finish store-wide advice on reducing abandonment. Give as many ideas as you think useful.",
        "parameters": {"type": "object", "properties": {
            "recommendations": {"type": "array", "items": {"type": "object", "properties": {
                "title": {"type": "string"},
                "recommendation": {"type": "string"},
                "why_it_may_help": {"type": "string"},
                "expected_impact": {"type": "string", "description": "Your own estimate, if you have one"},
                "effort": {"type": "string", "enum": ["Low", "Medium", "High"]},
                "dataset": {"type": "string", "enum": ["2016-17", "2020-21"], "description": "Optional"},
                "group": {"type": "string", "description": "Optional: group name from analyze_abandonment"},
                "segment": {"type": "string", "description": "Optional: segment name from analyze_abandonment"}},
                "required": ["title", "recommendation", "why_it_may_help"]}},
            "notes": {"type": "string"}}, "required": ["recommendations"]}}},
]


# ---------- Talking to OpenAI and the loop ----------
def call_openai(messages):
    resp = requests.post(OPENAI_URL, headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                                              "Content-Type": "application/json"},
                         json={"model": MODEL, "messages": messages, "tools": TOOLS}, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]


def run_agent(messages, max_steps=25):
    for _ in range(max_steps):
        msg = call_openai(messages)
        messages.append({k: v for k, v in msg.items() if v is not None})
        if not msg.get("tool_calls"):
            return msg.get("content") or ""
        report = None
        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                print(f"  [Agent 2 is using: {name} {args if args else ''}]")
                result = FUNCTIONS[name](**args)
            except Exception as e:
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, default=str)})
            if isinstance(result, dict) and "report" in result:
                report = result["report"]
        if report:
            return report
    return "I stopped after too many steps. Try a narrower request."


def save(name, title, question, answer):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n*{datetime.now():%Y-%m-%d %H:%M}* · **You asked:** {question}\n\n{answer}\n")
    print(f"  [Saved to data/{name}]\n")


if __name__ == "__main__":
    if not OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is missing from .env")
    print(f"Cart Recovery Agent 2 (NO policies). {len(CHECKOUTS):,} open carts. Model: {MODEL}. Type 'quit' to exit.\n")
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
            print("\nAgent 2:", answer, "\n")
            if LAST_REVIEW:
                save("agent2_latest_review.md", "Cart review without policies", user, LAST_REVIEW)
            if LAST_STRATEGY:
                save("agent2_latest_recommendations.md", "Recommendations without policies", user, LAST_STRATEGY)
        except Exception as e:
            print(f"\n[Error] {e}\n")
            del messages[before:]
