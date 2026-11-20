"""Agent 2 (no policies) in your browser: ask it questions and explore its results.

Run:  streamlit run ask_agent2.py     (or double-click run_ask_agent2.bat)
Uses the same AI and tools as `python agent2.py`. The chat needs OPENAI_API_KEY in .env;
the Results and Compare tabs work without it, from the files agent2 has already saved.
"""
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agent 2 · No policies", page_icon="🧪", layout="wide")

VIOLET, CORAL, MINT, AMBER, GREY = "#8B7BFF", "#FF7A59", "#2DD4BF", "#FBBF24", "#7C8499"
OFFER_COLOURS = {"no contact": GREY, "reminder": VIOLET, "free shipping": MINT, "percent discount": CORAL,
                 "dollar discount": AMBER, "gift or other incentive": "#F472B6", "other": "#465066"}
MONEY = {"cart_value": st.column_config.NumberColumn("Cart value", format="$%.2f"),
         "value": st.column_config.NumberColumn("Value", format="$%.2f"),
         "offer_cost": st.column_config.NumberColumn("Offer cost", format="$%.2f"),
         "lifetime_spend": st.column_config.NumberColumn("Lifetime spend", format="$%.2f")}

st.markdown("""<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.hero2 {padding: 1.5rem 1.8rem; border-radius: 20px; margin-bottom: 1.1rem;
        background: linear-gradient(135deg, rgba(255,122,89,.16), rgba(20,25,39,.6) 50%, rgba(139,123,255,.14));
        border: 1px solid rgba(255,122,89,.3);}
.hero2 h1 {font-size: 2rem; font-weight: 800; margin: 0 0 .3rem 0; letter-spacing: -.02em;
           background: linear-gradient(90deg, #fff, #FFB49F 60%, #C9C1FF); -webkit-background-clip: text;
           background-clip: text; color: transparent;}
.hero2 p {margin: 0; color: #A3A9BC; font-size: .93rem;}
.tag2 {display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
       padding: .25rem .7rem; border-radius: 999px; color: #FFB49F; background: rgba(255,122,89,.14);
       border: 1px solid rgba(255,122,89,.35); margin-bottom: .6rem;}
.stTabs [data-baseweb="tab-list"] {gap: .3rem; padding: .3rem; border-radius: 14px; background: #10141F;
                                   border: 1px solid #232A3B; width: fit-content;}
.stTabs [data-baseweb="tab"] {border-radius: 10px; padding: .45rem 1.1rem; font-weight: 600; height: auto;}
.stTabs [aria-selected="true"] {background: linear-gradient(135deg, #E8603F, #FF7A59) !important; color: #fff !important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display: none;}
[data-testid="stMetric"] {background: #141927; border: 1px solid #232A3B; border-radius: 14px; padding: .8rem 1rem;}
[data-testid="stChatMessage"] {border-radius: 16px; border: 1px solid #1E2434; background: rgba(20,25,39,.6);}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading carts...")
def load_agent2():
    import agent2   # loads the prepared data once
    return agent2


agent2 = load_agent2()
CSV2 = os.path.join(agent2.DATA_DIR, "agent2_recommendations.csv")
CSV1 = os.path.join(agent2.DATA_DIR, "recommendations.csv")


# ---------- Chart helpers ----------
def style(chart, height=260):
    return (chart.properties(height=height).configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor="#232A3B", gridDash=[2, 4], domain=False, tickSize=0, labelPadding=6,
                            labelColor="#9AA1B5", titleColor="#9AA1B5", titleFontWeight="normal")
            .configure_legend(labelColor="#C3C8D6", titleColor="#9AA1B5")
            .configure_text(color="#E7E9F0"))


def show(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def table(df, **kw):
    try:
        st.dataframe(df, hide_index=True, width="stretch", column_config=MONEY, **kw)
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True, column_config=MONEY, **kw)


def offer_bar(df, title="Offer type"):
    counts = df["offer_type"].fillna("other").value_counts().rename_axis("offer").reset_index(name="carts")
    return alt.Chart(counts).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, size=22).encode(
        y=alt.Y("offer:N", title=None, sort="-x"), x=alt.X("carts:Q", title="Carts"),
        color=alt.Color("offer:N", legend=None, scale=alt.Scale(domain=list(OFFER_COLOURS),
                                                               range=list(OFFER_COLOURS.values()))),
        tooltip=["offer:N", "carts:Q"]).properties(title=title)


def policy_donut(df):
    counts = (df["policy_check"].fillna("").str.startswith("Allowed")
              .map({True: "Allowed", False: "Breaks a policy"}).value_counts()
              .rename_axis("result").reset_index(name="carts"))
    return alt.Chart(counts).mark_arc(innerRadius=62, cornerRadius=6, padAngle=.02).encode(
        theta="carts:Q",
        color=alt.Color("result:N", title=None, scale=alt.Scale(domain=["Allowed", "Breaks a policy"],
                                                               range=[MINT, CORAL]),
                        legend=alt.Legend(orient="bottom")),
        tooltip=["result:N", "carts:Q"]).properties(title="Would agent.py's policies allow it?")


def rules_bar(df):
    broken = (df["policy_check"].fillna("").str.removeprefix("Breaks ").str.split("; ").explode())
    broken = broken[broken.str.match(r"^\d\.\d|^not one")]
    if broken.empty:
        return None
    rules = broken.str.extract(r"^(\d\.\d|not one of the store's actions)")[0].fillna("other")
    names = {"2.2": "2.2 Timing", "2.3": "2.3 Customer type / discount size", "2.5": "2.5 Recovery cost",
             "not one of the store's actions": "Not a store action"}
    counts = rules.map(lambda r: names.get(r, r)).value_counts().rename_axis("rule").reset_index(name="times")
    return alt.Chart(counts).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, size=22, color=CORAL).encode(
        y=alt.Y("rule:N", title=None, sort="-x"), x=alt.X("times:Q", title="Times broken"),
        tooltip=["rule:N", "times:Q"]).properties(title="Which policies the AI broke")


def discount_hist(df):
    d = df[(df["offer_type"] == "percent discount") & df["discount_percent"].notna()]
    if d.empty:
        return None
    counts = d["discount_percent"].astype(float).value_counts().sort_index().rename_axis("pct").reset_index(name="carts")
    counts["label"] = counts["pct"].map(lambda x: f"{x:g}%")
    rule = alt.Chart(pd.DataFrame({"x": ["5%"]})).mark_rule(color=MINT, strokeDash=[5, 4], strokeWidth=2).encode(x="x:N")
    bars = alt.Chart(counts).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=34, color=CORAL).encode(
        x=alt.X("label:N", title="Discount size (dashed line = the 5% policy limit)",
                sort=list(counts["label"]), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("carts:Q", title="Carts"), tooltip=["label:N", "carts:Q"])
    return (bars + rule).properties(title="Discounts the AI chose")


def cost_scatter(df):
    d = df[df["offer_cost"].fillna(0) > 0]
    if d.empty:
        return None
    d = d.assign(allowed=d["policy_check"].fillna("").str.startswith("Allowed").map({True: "Allowed",
                                                                                     False: "Breaks a policy"}))
    return alt.Chart(d).mark_circle(size=140, opacity=.9, stroke="#0A0D14", strokeWidth=1.5).encode(
        x=alt.X("cart_value:Q", title="Cart value", axis=alt.Axis(format="$,.0f")),
        y=alt.Y("offer_cost:Q", title="Offer cost", axis=alt.Axis(format="$,.0f")),
        color=alt.Color("allowed:N", title=None, scale=alt.Scale(domain=["Allowed", "Breaks a policy"],
                                                                range=[MINT, CORAL]),
                        legend=alt.Legend(orient="bottom")),
        tooltip=["cart_id:N", alt.Tooltip("cart_value:Q", format="$,.2f"), "action:N",
                 alt.Tooltip("offer_cost:Q", format="$,.2f"), "policy_check:N"]).properties(
        title="What the AI's offers would cost")


def charts_for(df):
    """The full set of charts for a set of agent2 recommendations."""
    a, b = st.columns(2)
    with a:
        show(style(offer_bar(df)))
    with b:
        show(style(policy_donut(df)))
    extra = [c for c in (rules_bar(df), discount_hist(df), cost_scatter(df)) if c is not None]
    for col, chart in zip(st.columns(len(extra)) if extra else [], extra):
        with col:
            show(style(chart))


# ---------- Saved results ----------
def load_results():
    if not os.path.exists(CSV2):
        return None
    df = pd.read_csv(CSV2)
    values = {c["cart_id"]: c["cart_value"] for c in agent2.CHECKOUTS}
    df["cart_value"] = df["cart_id"].map(values)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp", ascending=False)


# ---------- Chat ----------
def tool_results(messages):
    calls = {}
    for m in messages:
        for c in m.get("tool_calls") or []:
            calls[c["id"]] = (c["function"]["name"], json.loads(c["function"].get("arguments") or "{}"))
    return [(*calls[m["tool_call_id"]], json.loads(m["content"]))
            for m in messages if m.get("role") == "tool" and m["tool_call_id"] in calls]


def ask(question):
    messages = st.session_state.messages2
    before = len(messages)
    messages.append({"role": "user", "content": question})
    agent2.LAST_REVIEW = agent2.LAST_STRATEGY = None
    try:
        answer = agent2.run_agent(messages)
    except Exception as e:
        del messages[before:]
        return {"question": question, "error": str(e)}
    if agent2.LAST_REVIEW:
        agent2.save("agent2_latest_review.md", "Cart review without policies", question, agent2.LAST_REVIEW)
    if agent2.LAST_STRATEGY:
        agent2.save("agent2_latest_recommendations.md", "Recommendations without policies", question,
                    agent2.LAST_STRATEGY)
    return {"question": question, "answer": answer, "data": tool_results(messages[before:])}


def show_turn(turn):
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant", avatar="🧪"):
        if turn.get("error"):
            st.error(turn["error"])
            return
        st.markdown(turn["answer"])
        for name, args, result in turn["data"]:
            if isinstance(result, dict) and "error" in result:
                continue
            if name == "submit_review":
                rows = []
                for j in args.get("carts", []):
                    c = agent2.BY_ID.get(str(j.get("cart_id")))
                    if c:
                        rows.append(j | {"cart_value": c["cart_value"],
                                         "offer_cost": agent2.offer_cost(c, j.get("offer_type"), j.get("discount_percent")),
                                         "policy_check": agent2.policy_check(c, j.get("offer_type"),
                                                                             j.get("discount_percent"), j.get("send_on_day"))})
                if rows:
                    with st.expander("📊 Charts for this review", expanded=True):
                        charts_for(pd.DataFrame(rows).reindex(columns=[
                            "cart_id", "cart_value", "action", "offer_type", "discount_percent", "send_on_day",
                            "offer_cost", "policy_check"]))
            elif name == "list_carts":
                with st.expander(f"📊 Carts the AI looked at ({result['total_found']:,} matched)"):
                    table(pd.DataFrame(result["carts"]))
            elif name == "analyze_abandonment":
                with st.expander("📊 Abandonment by group (2016-17)"):
                    g = result.get("2016-17", {}).get("groups", {})
                    for group, rows in g.items():
                        df = pd.DataFrame(rows).T.rename_axis("segment").reset_index()
                        st.markdown(f"**{group.replace('_', ' ').capitalize()}**")
                        show(style(alt.Chart(df).mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5,
                                                          color=VIOLET).encode(
                            y=alt.Y("segment:N", title=None, sort="-x"),
                            x=alt.X("abandonment_rate_pct:Q", title="Abandonment %"),
                            tooltip=["segment:N", "abandonment_rate_pct:Q", "sessions:Q"]), 30 * len(df) + 20))


# ---------- Page ----------
st.markdown(f"""<div class="hero2"><span class="tag2">Experiment · no store policies</span>
<h1>🧪 Agent 2: the AI without rules</h1>
<p>Same {len(agent2.CHECKOUTS):,} carts and same AI ({agent2.MODEL}) as the main agent, but no policies.
Python checks each choice against the policies afterwards, for comparison only. Nothing is sent.</p></div>""",
            unsafe_allow_html=True)

EXAMPLES = ["Review my 5 highest-value carts", "Review my 5 most recent carts",
            "Review 5 carts from returning customers", "Review 5 carts that reached checkout",
            "How can I reduce cart abandonment?"]
question = None
with st.sidebar:
    st.markdown("### 💡 Try a question")
    for i, q in enumerate(EXAMPLES):
        if st.button(q, key=f"ex{i}", use_container_width=True):
            question = q
    st.divider()
    if st.button("🗑️ New conversation", use_container_width=True):
        st.session_state.pop("messages2", None)
        st.session_state.pop("turns2", None)
        st.rerun()

if "messages2" not in st.session_state:
    st.session_state.messages2 = [{"role": "system", "content": agent2.SYSTEM_PROMPT}]
    st.session_state.turns2 = []

chat_tab, results_tab, compare_tab = st.tabs(["💬 Ask agent 2", "📊 All saved results", "⚖️ Compare with agent.py"])

with chat_tab:
    if not agent2.OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is missing from .env. The other two tabs still work.")
    else:
        typed = st.chat_input("Ask agent 2, e.g. Review my 5 highest-value carts")
        question = typed or question
        for turn in st.session_state.turns2:
            show_turn(turn)
        if question:
            with st.spinner("Agent 2 is working (this can take up to a minute)..."):
                turn = ask(question)
            st.session_state.turns2.append(turn)
            show_turn(turn)

with results_tab:
    df = load_results()
    if df is None or df.empty:
        st.info("No saved results yet. Ask agent 2 to review some carts first.")
    else:
        latest = df.drop_duplicates("cart_id")   # most recent recommendation per cart
        allowed = latest["policy_check"].fillna("").str.startswith("Allowed").sum()
        k = st.columns(4)
        k[0].metric("Carts reviewed", f"{len(latest):,}")
        k[1].metric("Would break a policy", f"{len(latest) - allowed:,}",
                    f"{(len(latest) - allowed) / len(latest):.0%} of carts", delta_color="off")
        k[2].metric("Offer cost if all recovered", f"${latest['offer_cost'].fillna(0).sum():,.2f}")
        disc = latest.loc[latest["offer_type"] == "percent discount", "discount_percent"].dropna()
        k[3].metric("Average discount chosen", f"{disc.mean():.1f}%" if not disc.empty else "none")
        st.write("")
        charts_for(latest)
        st.markdown("**Every recommendation agent 2 has saved**")
        table(df.drop(columns=["timestamp"]).assign(time=df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")))
        if os.path.exists(os.path.join(agent2.DATA_DIR, "agent2_latest_recommendations.md")):
            with st.expander("💡 Latest store-wide ideas from agent 2"):
                with open(os.path.join(agent2.DATA_DIR, "agent2_latest_recommendations.md"), encoding="utf-8") as f:
                    st.markdown(f.read())

with compare_tab:
    df2 = load_results()
    if df2 is None or not os.path.exists(CSV1):
        st.info("Ask both agents to review the same carts (for example 'Review my 5 highest-value carts' "
                "in agent.py and here), then come back.")
    else:
        a1 = pd.read_csv(CSV1).drop_duplicates("cart_id", keep="last")[["cart_id", "recommended_action", "reason"]]
        a2 = df2.drop_duplicates("cart_id")[["cart_id", "cart_value", "action", "offer_type", "discount_percent",
                                             "offer_cost", "policy_check", "reason"]]
        both = a1.merge(a2, on="cart_id", suffixes=(" (agent.py)", " (agent 2)"))
        if both.empty:
            st.info("No cart has been reviewed by both agents yet. Ask both the same question to compare.")
        else:
            st.caption(f"{len(both)} carts reviewed by both agents (latest recommendation from each).")
            c1, c2 = st.columns(2)
            p1 = both["recommended_action"].value_counts().rename_axis("action").reset_index(name="carts")
            with c1:
                show(style(alt.Chart(p1).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, size=22,
                                                  color=MINT).encode(
                    y=alt.Y("action:N", title=None, sort="-x"), x=alt.X("carts:Q", title="Carts"),
                    tooltip=["action:N", "carts:Q"]).properties(title="agent.py (with policies)")))
            with c2:
                show(style(offer_bar(both, "Agent 2 (no policies)")))
            table(both)
