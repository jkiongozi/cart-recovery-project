"""Cart Recovery dashboard.

Run:  streamlit run dashboard.py
Opens in your web browser. Data comes from the prepared Excel files and stays on this computer.
"""
import os

import pandas as pd
import streamlit as st

from agent_data import load_for_app
from prepare_data import DATA_DIR
from risk import assess_all, canonical_action

st.set_page_config(page_title="Cart Recovery Dashboard", page_icon="🛒", layout="wide")


@st.cache_data(show_spinner="Loading carts...")
def load_data():
    carts, stats = load_for_app()
    carts, _ = assess_all(carts)  # adds risk level + recommendation to every cart
    df = pd.DataFrame(carts)
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["reached_checkout"] = df["reached_checkout"].astype(bool)
    df["returning"] = df["previous_orders"] > 0
    return df, stats


df_all, stats = load_data()

st.title("🛒 Cart Recovery — Abandoned Carts")
ua, ga4 = stats["2016-17"], stats["2020-21"]
st.caption(f"Google Merchandise Store, US, {ua['period']}, with Jb Prints policies applied as a simulation. "
           f"Ages are counted from {ua['as_of_date']}. Email subscription is simulated.")

if df_all.empty:
    st.info("No open carts found.")
    st.stop()

# ---------- Filters (left sidebar) ----------
with st.sidebar:
    st.header("Filters")
    if st.button("🔄 Reload data"):
        load_data.clear()
        st.rerun()
    hide_zero = st.checkbox("Hide $0 carts", value=True)
    min_date, max_date = df_all["date"].min(), df_all["date"].max()
    date_range = st.date_input("Session date between", (min_date, max_date),
                               min_value=min_date, max_value=max_date)
    min_value = st.number_input("Minimum cart value ($)", min_value=0.0, value=0.0, step=10.0)
    risk_filter = st.multiselect("Risk level", ["Low", "Medium", "High"],
                                 default=["Low", "Medium", "High"])
    action_options = sorted(df_all["recommended_action"].unique())
    action_filter = st.multiselect("Recommended action", action_options, default=action_options)
    checkout_only = st.checkbox("Only carts that reached checkout", value=False)
    returning_only = st.checkbox("Only returning customers", value=False)

df = df_all.copy()
if hide_zero:
    df = df[df["cart_value"] > 0]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    df = df[(df["date"] >= date_range[0]) & (df["date"] <= date_range[1])]
df = df[df["cart_value"] >= min_value]
if checkout_only:
    df = df[df["reached_checkout"]]
if returning_only:
    df = df[df["returning"]]
df = df[df["risk_level"].isin(risk_filter) & df["recommended_action"].isin(action_filter)]
zero_count = int((df_all["cart_value"] == 0).sum())
st.caption(f"{len(df_all):,} open carts · {zero_count} are $0 · "
           f"showing {len(df):,} after filters")

if df.empty:
    st.warning("No carts match these filters. The AI review and the AI vs. rules comparison are still shown below.")
else:
    # ---------- Headline numbers ----------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Open carts", f"{len(df):,}")
    c2.metric("Value at risk", f"${df['cart_value'].sum():,.2f}")
    c3.metric("Average cart", f"${df['cart_value'].mean():,.2f}")
    c4.metric("Middle (median) cart", f"${df['cart_value'].median():,.2f}")
    c5.metric("Reached checkout", f"{int(df['reached_checkout'].sum()):,} of {len(df):,}")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("🟢 Low risk", int((df["risk_level"] == "Low").sum()))
    r2.metric("🟠 Medium risk", int((df["risk_level"] == "Medium").sum()))
    r3.metric("🔴 High risk", int((df["risk_level"] == "High").sum()))
    act = df["recommended_action"] != "No action"
    r4.metric("Carts to act on", f"{int(act.sum()):,} (${df.loc[act, 'cart_value'].sum():,.2f})")
    st.caption("RULES BASELINE (risk.py): fixed if-then rules, not the AI. Risk = risk of losing the sale "
               "for good, scored 0–100 from days since abandonment and email subscription. "
               "Low 0–39 · Medium 40–69 · High 70–100. Compare with the AI agent's own judgments at the bottom.")

    st.divider()

    # ---------- Risk and recommendations ----------
    left, right = st.columns(2)
    with left:
        st.subheader("Carts by risk level")
        risk_counts = df["risk_level"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0).astype(int)
        st.bar_chart(pd.DataFrame({"Carts": risk_counts}), y_label="Carts")
    with right:
        st.subheader("Recommended actions")
        st.bar_chart(df["recommended_action"].value_counts(), horizontal=True,
                     x_label="Carts", y_label="")

    # ---------- One order in detail ----------
    st.subheader("🔍 Look at one order")
    options = df.sort_values("cart_value", ascending=False)
    options = options.head(500)   # the list is long; the highest-value carts are offered
    labels = {row.cart_id: f"{row.cart_id} · ${row.cart_value:,.2f} · {row.date} · {row.risk_level} risk"
              for row in options.itertuples()}
    picked = st.selectbox("Choose an order", list(labels), format_func=lambda k: labels[k])
    if picked:
        cart = df[df["cart_id"] == picked].iloc[0]
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Cart value", f"${cart['cart_value']:,.2f}")
        d2.metric("Risk", f"{cart['risk_level']} ({cart['risk_score']}/100)")
        d3.metric("Days old", f"{cart['days_since_abandoned']:.0f}")
        d4.metric("Returning customer", "Yes" if cart["returning"] else "No")
        st.markdown(f"**Recommended action:** {cart['recommended_action']}  \n"
                    f"**Why:** {cart['reason']}  \n"
                    f"**Risk factors:** {cart['risk_factors']}  \n"
                    f"**Products in cart:** {cart['item_count']}, on {cart['device_category']}, "
                    f"from {cart['traffic_medium']}")
        st.caption("For a detailed, AI-written review of this order, run `python agent.py` and ask: "
                   f"Review cart {picked}")

    st.divider()

    # ---------- Charts ----------
    left, right = st.columns(2)

    with left:
        st.subheader("Abandoned carts per week")
        weekly = (df.set_index("created_at")
                    .resample("W")
                    .agg(carts=("cart_id", "count"), value=("cart_value", "sum")))
        weekly.index = weekly.index.date
        st.bar_chart(weekly["carts"], y_label="Carts")

    with right:
        st.subheader("Value at risk per week ($)")
        st.line_chart(weekly["value"], y_label="Dollars")

    left, right = st.columns(2)

    with left:
        st.subheader("How big are the carts?")
        bins = [0, 10, 25, 50, 100, 200, 500, float("inf")]
        labels = ["$0–10", "$10–25", "$25–50", "$50–100", "$100–200", "$200–500", "$500+"]
        sizes = pd.cut(df["cart_value"], bins=bins, labels=labels, include_lowest=True)
        size_counts = sizes.value_counts().reindex(labels).fillna(0).astype(int)
        st.bar_chart(pd.DataFrame({"Carts": size_counts}), x_label="Cart value", y_label="Carts")

    with right:
        st.subheader("Where shoppers came from")
        st.bar_chart(df["traffic_medium"].value_counts(), horizontal=True, x_label="Carts", y_label="")

    # ---------- Two periods ----------
    st.subheader("2016-17 vs. 2020-21")
    st.dataframe(pd.DataFrame({
        "Measure": ["Cart sessions", "Abandonment rate %", "Reached checkout %",
                    "Left at checkout % of checkouts", "Came back and bought within 30 days %"],
        "2016-17": [ua["cart_sessions"], ua["abandonment_rate_pct"], ua["reached_checkout_pct"],
                    ua["left_at_checkout_pct_of_checkouts"], ua["came_back_and_bought_within_30_days"]["rate_pct"]],
        "2020-21": [ga4["cart_sessions"], ga4["abandonment_rate_pct"], ga4["reached_checkout_pct"],
                    ga4["left_at_checkout_pct_of_checkouts"], ga4["came_back_and_bought_within_30_days"]["rate_pct"]],
    }), hide_index=True)
    st.caption("2020-21 covers three holiday-season months and its cart values are not reliable dollars, "
               "so it has no dollar figures here. See data/data_quality_report.md.")

    # ---------- Cart list ----------
    st.subheader("All orders with risk and recommendation")
    cols = ["date", "cart_value", "risk_level", "risk_score", "recommended_action", "reason",
            "item_count", "reached_checkout", "device_category", "traffic_medium", "previous_orders"]
    table = df.sort_values("cart_value", ascending=False)[["cart_id"] + cols]
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "cart_id": "Cart",
            "date": "Session date",
            "cart_value": st.column_config.NumberColumn("Cart value", format="$%.2f"),
            "risk_level": "Risk",
            "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%d"),
            "recommended_action": "Recommended action",
            "reason": "Why",
            "item_count": "Products",
            "reached_checkout": st.column_config.CheckboxColumn("Reached checkout"),
            "device_category": "Device",
            "traffic_medium": "Traffic",
            "previous_orders": "Previous orders",
        },
    )
    st.download_button("⬇️ Download these carts (CSV)", table.to_csv(index=False).encode("utf-8-sig"),
                       file_name="abandoned_carts.csv", mime="text/csv")

# ---------- Agent recommendations ----------
st.subheader("🤖 Latest AI review")
review_path = os.path.join(DATA_DIR, "latest_review.md")
if os.path.exists(review_path):
    with open(review_path, encoding="utf-8") as f:
        st.markdown(f.read())
else:
    st.info("No AI review yet. Run `python agent.py` and ask: Review my 5 highest-value carts")

st.subheader("💡 AI recommendations to reduce abandonment")
strategy_path = os.path.join(DATA_DIR, "latest_recommendations.md")
if os.path.exists(strategy_path):
    with open(strategy_path, encoding="utf-8") as f:
        st.markdown(f.read())
else:
    st.info("No recommendations yet. Run `python agent.py` and ask: How can I reduce cart abandonment?")

st.subheader("AI agent vs. rules")
rec_path = os.path.join(DATA_DIR, "recommendations.csv")
if os.path.exists(rec_path):
    history = pd.read_csv(rec_path, dtype={"cart_id": str})
    # Latest recommendation per cart only, so re-running a review does not double-count
    recs = (history.sort_values("timestamp")
                   .drop_duplicates("cart_id", keep="last")
                   .copy())
    rules = df_all[["cart_id", "recommended_action", "risk_level"]].rename(
        columns={"recommended_action": "rules_action", "risk_level": "rules_risk"})
    recs = recs.merge(rules, on="cart_id", how="left")
    recs["ai_canonical"] = recs["recommended_action"].map(lambda a: canonical_action(str(a)) or str(a))
    recs["rules_canonical"] = recs["rules_action"].map(lambda a: canonical_action(str(a)) or str(a))
    recs["agrees_with_rules"] = recs["ai_canonical"] == recs["rules_canonical"]
    disagree = int((~recs["agrees_with_rules"]).sum())
    st.caption(f"The AI agent disagreed with the fixed rules on {disagree} of {len(recs)} carts it reviewed "
               f"(latest recommendation per cart; {len(history)} rows of history in the file). "
               "Those rows show where the AI's judgment adds something the rules can't.")
    st.dataframe(recs.sort_values("timestamp", ascending=False)
                     .drop(columns=["ai_canonical", "rules_canonical"]), hide_index=True,
                 column_config={"recommended_action": "AI action", "rules_action": "Rules action",
                                "rules_risk": "Rules risk", "agrees_with_rules": "Same?"})
else:
    st.info("No recommendations yet. Run `python agent.py` and ask the agent to review some carts.")
