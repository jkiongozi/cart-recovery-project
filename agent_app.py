"""Cart Recovery Agent: chat with the agent and explore the carts, policies and budget as interactive charts.

Run:  streamlit run agent_app.py     (or double-click run_agent_app.bat)
Uses the same agent, tools and policies as `python agent.py`. The chat needs OPENAI_API_KEY in .env;
the charts work without it.
"""
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cart Recovery Agent", page_icon="🛒", layout="wide")
alt.data_transformers.disable_max_rows()

# ---------- Colours: one fixed role per meaning, used in every chart ----------
BLUE, ORANGE, AQUA, AMBER = "#8B7BFF", "#FF7A59", "#2DD4BF", "#FBBF24"   # violet, coral, mint, amber
SEQ = ["#1B1F3A", "#2A2A5E", "#3D3A86", "#5549B0", "#6F5FD6", "#8B7BFF", "#B4A9FF"]   # dark to bright, for a dark page
INTENT = {"Low": "#4A4290", "Medium": "#7566E8", "High": "#B4A9FF"}
GREY, GREY_DARK = "#7C8499", "#465066"
BG = "#0A0D14"   # page background, used for marker outlines
STAGE_COLOURS = {"not yet eligible": GREY, "first reminder": BLUE, "second contact": ORANGE,
                 "campaign closed": GREY_DARK}
ACTION_COLOURS = {"Reminder email": BLUE, "Free shipping": ORANGE, "5% discount": AQUA,
                  "Escalate for human review": AMBER, "No action": GREY, "Blocked by policy": GREY_DARK}
VALUE_BANDS = ["under $10", "$10–25", "$25–50", "$50–HV", "HV–$250", "$250–500", "$500+"]
INTENT_BINS = ["0–19", "20–39", "40–59", "60–79", "80–100"]

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1440px;}
[data-testid="stAppViewContainer"] {
    background: radial-gradient(900px 500px at 10% -10%, rgba(139,123,255,.14), transparent 60%),
                radial-gradient(700px 400px at 100% 0%, rgba(45,212,191,.08), transparent 60%), #0A0D14;}
[data-testid="stHeader"] {background: transparent;}
h1, h2, h3 {letter-spacing: -.02em;}

/* Hero */
.hero {position: relative; overflow: hidden; padding: 1.8rem 2rem; border-radius: 22px; margin-bottom: 1.3rem;
       background: linear-gradient(135deg, rgba(139,123,255,.16), rgba(20,25,39,.6) 45%, rgba(255,122,89,.10));
       border: 1px solid rgba(139,123,255,.28); box-shadow: 0 20px 60px -30px rgba(139,123,255,.55);}
.hero:after {content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px; border-radius: 50%;
             background: radial-gradient(circle, rgba(45,212,191,.22), transparent 70%);}
.hero h1 {font-size: 2.2rem; font-weight: 800; margin: 0 0 .35rem 0; line-height: 1.1;
          background: linear-gradient(90deg, #FFFFFF 0%, #C9C1FF 55%, #FFB49F 100%);
          -webkit-background-clip: text; background-clip: text; color: transparent;}
.hero p {margin: 0; color: #A3A9BC; font-size: .95rem;}
.hero .tag {display: inline-flex; align-items: center; gap: .45rem; font-size: .7rem; font-weight: 700;
            letter-spacing: .1em; text-transform: uppercase; padding: .28rem .75rem; border-radius: 999px;
            color: #C9C1FF; background: rgba(139,123,255,.14); border: 1px solid rgba(139,123,255,.35); margin-bottom: .7rem;}
.hero .tag:before {content: ""; width: 7px; height: 7px; border-radius: 50%; background: #2DD4BF;
                   box-shadow: 0 0 0 0 rgba(45,212,191,.7); animation: pulse 2s infinite;}
@keyframes pulse {0% {box-shadow: 0 0 0 0 rgba(45,212,191,.6);} 70% {box-shadow: 0 0 0 8px rgba(45,212,191,0);}
                  100% {box-shadow: 0 0 0 0 rgba(45,212,191,0);}}

/* KPI cards */
.kpi {position: relative; border-radius: 16px; padding: 1rem 1.1rem .95rem; height: 100%; overflow: hidden;
      background: linear-gradient(180deg, rgba(23,29,45,.95), rgba(15,19,32,.95));
      border: 1px solid #232A3B; transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;}
.kpi:hover {transform: translateY(-3px); border-color: var(--accent);
            box-shadow: 0 14px 34px -18px var(--accent);}
.kpi:before {content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px;
             background: linear-gradient(90deg, var(--accent), transparent);}
.kpi:after {content: ""; position: absolute; right: -30px; bottom: -40px; width: 110px; height: 110px; border-radius: 50%;
            background: var(--accent); opacity: .08; filter: blur(4px);}
.kpi .label {font-size: .68rem; text-transform: uppercase; letter-spacing: .1em; color: #8A91A6; font-weight: 700;}
.kpi .value {font-size: 1.75rem; font-weight: 800; letter-spacing: -.03em; margin-top: .2rem; color: #F4F5FA;
             font-variant-numeric: tabular-nums;}
.kpi .note {font-size: .76rem; color: #7C8499; margin-top: .1rem;}

/* Section titles */
.section {font-size: 1.05rem; font-weight: 700; margin: .9rem 0 .1rem 0; display: flex; align-items: center; gap: .55rem;}
.section:before {content: ""; width: 4px; height: 1.05rem; border-radius: 4px;
                 background: linear-gradient(180deg, #8B7BFF, #2DD4BF);}
.sub {font-size: .84rem; color: #8A91A6; margin: 0 0 .55rem .95rem;}

/* Chips */
.chip {display: inline-block; padding: .22rem .7rem; border-radius: 999px; font-size: .74rem; font-weight: 500;
       border: 1px solid #2A3247; margin: 0 .3rem .4rem 0; background: #171D2D; color: #C3C8D6;}

/* Tabs as a segmented control */
.stTabs [data-baseweb="tab-list"] {gap: .3rem; padding: .3rem; border-radius: 14px; background: #10141F;
                                   border: 1px solid #232A3B; width: fit-content;}
.stTabs [data-baseweb="tab"] {border-radius: 10px; padding: .45rem 1.1rem; background: transparent; color: #9AA1B5;
                              font-weight: 600; height: auto;}
.stTabs [data-baseweb="tab"]:hover {color: #E7E9F0; background: rgba(139,123,255,.08);}
.stTabs [aria-selected="true"] {background: linear-gradient(135deg, #6F5FD6, #8B7BFF) !important; color: #fff !important;
                                box-shadow: 0 6px 18px -8px rgba(139,123,255,.8);}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display: none;}

/* Buttons */
.stButton > button {border-radius: 12px; border: 1px solid #2A3247; background: #141927; color: #D5D9E4;
                    font-weight: 500; text-align: left; justify-content: flex-start; transition: all .15s ease;}
.stButton > button:hover {border-color: #8B7BFF; color: #fff; background: rgba(139,123,255,.12);
                          transform: translateX(2px);}

/* Sidebar */
[data-testid="stSidebar"] h3 {font-size: .78rem; text-transform: uppercase; letter-spacing: .12em; color: #8A91A6;}

/* Chat */
[data-testid="stChatMessage"] {border-radius: 16px; border: 1px solid #1E2434; background: rgba(20,25,39,.6);
                               padding: .9rem 1rem;}
[data-testid="stChatInput"] textarea {font-size: .95rem;}
[data-testid="stChatInput"] > div {border-radius: 16px; border: 1px solid #2A3247;
                                   box-shadow: 0 10px 30px -18px rgba(139,123,255,.6);}

/* Tables, expanders, charts */
div[data-testid="stExpander"] details {border-radius: 14px; border: 1px solid #232A3B; background: #10141F;}
[data-testid="stDataFrame"] {border-radius: 14px; overflow: hidden; border: 1px solid #232A3B;}
[data-testid="stVegaLiteChart"] {background: #10141F; border: 1px solid #1E2434; border-radius: 16px; padding: .8rem;}
</style>""", unsafe_allow_html=True)


# ---------- Streamlit-version-safe helpers ----------
def show(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def table(df, **kw):
    try:
        st.dataframe(df, hide_index=True, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True, **kw)


def wide_button(label, key=None):
    try:
        return st.button(label, key=key, width="stretch")
    except TypeError:
        return st.button(label, key=key, use_container_width=True)


def when(selection, yes, no):
    """alt.when in new Altair, alt.condition in older versions."""
    if hasattr(alt, "when"):
        return alt.when(selection).then(yes).otherwise(no)
    return alt.condition(selection, yes, no)


def clean(chart, height=None):
    chart = chart.properties(height=height) if height else chart
    return (chart.configure(background="transparent", font="Plus Jakarta Sans")
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor="#232A3B", gridDash=[2, 4], gridOpacity=1, domain=False, tickSize=0,
                            labelPadding=8, labelColor="#9AA1B5", titleColor="#9AA1B5", titleFontWeight="normal")
            .configure_legend(labelColor="#C3C8D6", titleColor="#9AA1B5")
            .configure_text(color="#E7E9F0")
            .configure_title(anchor="start", fontSize=13, fontWeight=700, offset=10, color="#E7E9F0"))


def kpi(col, label, value, note="", accent=BLUE):
    col.markdown(f'<div class="kpi" style="--accent:{accent}"><div class="label">{label}</div>'
                 f'<div class="value">{value}</div><div class="note">{note}</div></div>', unsafe_allow_html=True)


def heading(title, sub=""):
    st.markdown(f'<div class="section">{title}</div>' + (f'<div class="sub">{sub}</div>' if sub else ""),
                unsafe_allow_html=True)


def money(x):
    return f"${x:,.2f}"


# ---------- Data (loaded once, rebuilt when policies.md changes) ----------
@st.cache_resource(show_spinner="Loading carts...")
def load_agent():
    import agent   # loads the prepared data once
    return agent


agent = load_agent()
HV = agent.HIGH_VALUE


def value_band(v):
    edges = [10, 25, 50, HV, 250, 500]
    return next((VALUE_BANDS[i] for i, e in enumerate(edges) if v < e), VALUE_BANDS[-1])


def intent_bin(s):
    return INTENT_BINS[min(int(s) // 20, 4)]


@st.cache_data(show_spinner="Working out the policy facts for every cart...")
def cart_table(policy_stamp):
    pol = agent._policy_numbers()
    day5 = int(pol["second_reminder_day"] or 5)
    rows = []
    for c in agent.CHECKOUTS:
        v = agent.safe_view(c)
        fits = [a for a in agent.INCENTIVES if agent._why_not(c, a, day5, pol) is None]
        rows.append({
            "cart_id": v["cart_id"], "date": v["session_date"], "cart_value": v["cart_value"],
            "high_value": v["high_value"], "intent_score": v["intent_score"], "intent_band": v["intent_band"],
            "reached_checkout": v["reached_checkout"], "returning_customer": v["returning_customer"],
            "device": v["device"], "contact_stage": v["contact_stage"], "reminder_focus": v["reminder_focus"],
            "incentive_cap": v["incentive_cap"],
            "incentive_at_day5": ("5% discount" if "5% discount" in fits else
                                  "Free shipping" if "Free shipping" in fits else "Reminder only"),
        })
    df = pd.DataFrame(rows)
    df["value_band"] = df["cart_value"].map(value_band)
    df["intent_bin"] = df["intent_score"].map(intent_bin)
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    return df


carts = cart_table(os.path.getmtime(agent.POLICIES) if os.path.exists(agent.POLICIES) else 0)
pol = agent._policy_numbers()
BAND_LABELS = {b: b.replace("HV", f"${HV:,.0f}") for b in VALUE_BANDS}


# ---------- Header ----------
st.markdown(f"""<div class="hero"><span class="tag">AI agent · historical simulation</span>
<h1>🛒 Cart Recovery Agent</h1>
<p>Google Merchandise Store, US, Aug 2016 – Aug 2017 · nothing is sent · every recommendation needs your approval ·
model {agent.MODEL}</p></div>""", unsafe_allow_html=True)

k = st.columns(5)
kpi(k[0], "Open carts", f"{len(carts):,}", "abandoned, not bought later", BLUE)
kpi(k[1], "Value at risk", money(carts["cart_value"].sum()), f"average {money(agent.AVG_CART)} excl. $0", BLUE)
kpi(k[2], "High-value carts", f"{int(carts['high_value'].sum()):,}", f"{money(HV)} or more · top 10%", ORANGE)
kpi(k[3], "High purchase intent", f"{int((carts['intent_band'] == 'High').sum()):,}", "score 60+ · follow up first",
    INTENT["High"])
kpi(k[4], "Incentive fits the cap", f"{int((carts['incentive_at_day5'] != 'Reminder only').sum()):,}",
    f"at Day {int(pol['second_reminder_day'] or 5)} · ≤ {pol['incentive_cap_pct'] or 0:g}% of gross profit", AQUA)
st.write("")

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### ⚙️ Policy snapshot")
    day = pol["evaluation_day"]
    st.markdown(
        f'<span class="chip">Replay: {"data end" if day is None else f"Day {day:g}"}</span>'
        f'<span class="chip">Day 1 → Day {pol["second_reminder_day"] or 5:g} → closes Day {pol["close_day"] or 7:g}</span>'
        f'<span class="chip">Cap {pol["incentive_cap_pct"] or 0:g}% of gross profit</span>'
        f'<span class="chip">Margin {100 - (pol["product_cost_pct"] or 0):g}%</span>'
        f'<span class="chip">Free shipping {money(pol["free_shipping_cost"] or 0)}</span>'
        f'<span class="chip">{pol["max_discount_pct"] or 0:g}% discount · returning only</span>'
        f'<span class="chip">High value ≥ {money(HV)}</span>', unsafe_allow_html=True)
    st.caption("Edit prompts/policies.md and refresh to change these.")
    st.divider()
    st.markdown("### 💡 Try a question")
    EXAMPLES = ["Review my 5 highest-value carts", "Review my 5 carts with the highest purchase intent",
                "Summarize all my carts", "How can I reduce cart abandonment?",
                "How should I spend a $50 incentive budget?", "How does 2016-17 compare with 2020-21?"]
    picked = None
    for i, q in enumerate(EXAMPLES):
        if wide_button(q, key=f"ex{i}"):
            picked = q
    st.divider()
    if wide_button("🗑️ New conversation", key="reset"):
        st.session_state.pop("messages", None)
        st.session_state.pop("turns", None)
        st.rerun()

chat_tab, insight_tab, budget_tab, policy_tab = st.tabs(
    ["💬 Ask the agent", "📊 Cart insights", "💰 Budget planner", "📋 Policies"])


# ---------- Tab: Cart insights ----------
def linked_dashboard(df):
    """Drag across the timeline or click an intent bar: the other charts filter to that selection."""
    agg = (df.groupby(["week", "intent_band", "device", "value_band", "incentive_at_day5"], observed=True)
             .agg(carts=("cart_id", "size"), value=("cart_value", "sum")).reset_index())
    agg["value"] = agg["value"].round(2)
    agg["value_label"] = agg["value_band"].map(BAND_LABELS)
    brush = alt.selection_interval(encodings=["x"], name="brush")
    pick = alt.selection_point(fields=["intent_band"], name="pick")
    base = alt.Chart(agg)

    timeline = base.mark_area(
        line={"color": BLUE, "strokeWidth": 2}, interpolate="monotone",
        color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color="rgba(139,123,255,0.02)", offset=0),
                                                     alt.GradientStop(color="rgba(139,123,255,0.45)", offset=1)],
                           x1=1, x2=1, y1=1, y2=0)
    ).encode(
        x=alt.X("week:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)),
        y=alt.Y("sum(value):Q", title="Value at risk per week", axis=alt.Axis(format="$,.0f")),
        tooltip=[alt.Tooltip("week:T", title="Week of", format="%b %d, %Y"),
                 alt.Tooltip("sum(value):Q", title="Value at risk", format="$,.2f"),
                 alt.Tooltip("sum(carts):Q", title="Carts", format=",")]
    ).transform_filter(pick).add_params(brush).properties(width=1060, height=170,
                                                           title="Drag across the timeline to filter · click an intent bar")

    intent = base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, size=46).encode(
        x=alt.X("intent_band:N", title=None, sort=list(INTENT), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("sum(carts):Q", title="Carts"),
        color=alt.Color("intent_band:N", legend=None, scale=alt.Scale(domain=list(INTENT), range=list(INTENT.values()))),
        opacity=when(pick, alt.value(1), alt.value(.3)),
        tooltip=[alt.Tooltip("intent_band:N", title="Intent"), alt.Tooltip("sum(carts):Q", title="Carts", format=","),
                 alt.Tooltip("sum(value):Q", title="Value", format="$,.2f")]
    ).transform_filter(brush).add_params(pick).properties(width=240, height=230, title="Purchase intent")

    incentive = base.mark_arc(innerRadius=58, outerRadius=95, cornerRadius=4, padAngle=.02).encode(
        theta=alt.Theta("sum(carts):Q"),
        color=alt.Color("incentive_at_day5:N", title=None,
                        scale=alt.Scale(domain=["Reminder only", "Free shipping", "5% discount"],
                                        range=[GREY, BLUE, ORANGE]),
                        legend=alt.Legend(orient="bottom", direction="vertical")),
        tooltip=[alt.Tooltip("incentive_at_day5:N", title="At the second contact"),
                 alt.Tooltip("sum(carts):Q", title="Carts", format=","),
                 alt.Tooltip("sum(value):Q", title="Value", format="$,.2f")]
    ).transform_filter(brush).transform_filter(pick).properties(width=230, height=230,
                                                                title="Incentive the cap allows")

    sizes = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=16).encode(
        y=alt.Y("value_label:N", title=None, sort=[BAND_LABELS[b] for b in VALUE_BANDS]),
        x=alt.X("sum(carts):Q", title="Carts"),
        color=when(f"indexof({json.dumps([BAND_LABELS[b] for b in VALUE_BANDS[4:]])}, datum.value_label) >= 0",
                            alt.value(ORANGE), alt.value(BLUE)),
        tooltip=[alt.Tooltip("value_label:N", title="Cart value"), alt.Tooltip("sum(carts):Q", title="Carts", format=","),
                 alt.Tooltip("sum(value):Q", title="Value", format="$,.2f")]
    ).transform_filter(brush).transform_filter(pick).properties(width=330, height=230,
                                                                title="Cart sizes (orange = high value)")

    devices = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=18, color=BLUE).encode(
        y=alt.Y("device:N", title=None, sort="-x"), x=alt.X("sum(carts):Q", title="Carts"),
        tooltip=[alt.Tooltip("device:N"), alt.Tooltip("sum(carts):Q", title="Carts", format=",")]
    ).transform_filter(brush).transform_filter(pick).properties(width=160, height=230, title="Device")

    return alt.vconcat(timeline, alt.hconcat(intent, incentive, sizes, devices, spacing=28), spacing=22)


def opportunity_map(df):
    grid = (df.groupby(["value_band", "intent_bin"], observed=True)
              .agg(carts=("cart_id", "size"), value=("cart_value", "sum")).reset_index())
    grid["value_label"] = grid["value_band"].map(BAND_LABELS)
    grid["value"] = grid["value"].round(2)
    order_y = [BAND_LABELS[b] for b in reversed(VALUE_BANDS)]
    base = alt.Chart(grid).encode(
        x=alt.X("intent_bin:O", title="Purchase-intent score →", sort=INTENT_BINS,
                scale=alt.Scale(paddingInner=.08), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value_label:O", title="Cart value →", sort=order_y, scale=alt.Scale(paddingInner=.08)))
    cells = base.mark_rect(cornerRadius=5).encode(
        color=alt.Color("value:Q", title="Value at risk", scale=alt.Scale(range=SEQ[1:], type="sqrt"),
                        legend=alt.Legend(format="$,.0f", orient="right", gradientLength=180)),
        tooltip=[alt.Tooltip("value_label:N", title="Cart value"), alt.Tooltip("intent_bin:N", title="Intent"),
                 alt.Tooltip("carts:Q", title="Carts", format=","), alt.Tooltip("value:Q", title="Value", format="$,.2f")])
    labels = base.mark_text(fontSize=11, fontWeight=600).encode(
        text=alt.Text("carts:Q", format=","),
        color=when(f"datum.value > {grid['value'].quantile(.7):.2f}", alt.value("#0A0D14"), alt.value("#E7E9F0")))
    focus = alt.Chart(pd.DataFrame([{"x": b, "y": y} for b in INTENT_BINS[3:] for y in order_y[:3]])).mark_rect(
        fill=None, stroke=ORANGE, strokeWidth=2.5, cornerRadius=5).encode(
        x=alt.X("x:O", sort=INTENT_BINS), y=alt.Y("y:O", sort=order_y))
    return clean(cells + labels + focus, 330)


def natural_lollipop():
    nr = pd.DataFrame([{"segment": seg, "group": g.replace("_", " "), "rate": r["came_back_pct"], "carts": r["carts"]}
                       for g, segs in agent.NATURAL["segments"].items() for seg, r in segs.items()])
    overall = agent.NATURAL["overall_pct"]
    nr = nr.sort_values("rate")
    nr["above"] = nr["rate"] >= overall
    y = alt.Y("segment:N", title=None, sort=list(nr["segment"]))
    stems = alt.Chart(nr).mark_rule(strokeWidth=2.5).encode(
        y=y, x=alt.X("base:Q", title="% bought within 7 days with no action"), x2="rate:Q",
        color=when("datum.above", alt.value(BLUE), alt.value(GREY))).transform_calculate(base=str(overall))
    dots = alt.Chart(nr).mark_circle(size=170, opacity=1).encode(
        y=y, x="rate:Q", color=when("datum.above", alt.value(BLUE), alt.value(GREY)),
        tooltip=[alt.Tooltip("segment:N"), alt.Tooltip("group:N"), alt.Tooltip("rate:Q", title="Came back %", format=".1f"),
                 alt.Tooltip("carts:Q", title="Carts measured", format=",")])
    text = alt.Chart(nr).mark_text(dx=12, fontSize=11, align="left").encode(y=y, x="rate:Q",
                                                                          text=alt.Text("rate:Q", format=".1f"))
    rule = alt.Chart(pd.DataFrame({"x": [overall], "t": [f"all carts {overall}%"]})).mark_rule(
        strokeDash=[4, 4], color=ORANGE).encode(x="x:Q")
    note = alt.Chart(pd.DataFrame({"x": [overall], "t": [f"all carts {overall}%"]})).mark_text(
        align="left", dx=5, dy=-6, color=ORANGE, fontSize=11).encode(x="x:Q", y=alt.value(0), text="t:N")
    return clean(stems + dots + text + rule + note, 300)


with insight_tab:
    heading("Linked overview",
            "Every chart below the timeline shows the weeks you select. Double-click a chart to clear its selection.")
    show(clean(linked_dashboard(carts)))

    left, right = st.columns([1.15, 1])
    with left:
        heading("Opportunity map",
                "Where the value sits by intent and cart size. The orange box is follow-up-first: high intent and high value.")
        show(opportunity_map(carts))
    with right:
        heading("Who comes back on their own",
                f"Share of similar carts bought within {agent.NATURAL['window_days']} days with no action. "
                "Blue segments return more than average, so a reminder should come before any paid offer.")
        show(natural_lollipop())

    heading("Explore the carts", "Filter, then ask the agent to review any cart ID.")
    f = st.columns(4)
    bands = f[0].multiselect("Intent", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    hv_only = f[1].toggle("High value only")
    co_only = f[2].toggle("Reached checkout only")
    back_only = f[3].toggle("Returning customers only")
    view = carts[carts["intent_band"].isin(bands)]
    for on, colname in [(hv_only, "high_value"), (co_only, "reached_checkout"), (back_only, "returning_customer")]:
        if on:
            view = view[view[colname]]
    st.caption(f"{len(view):,} carts · {money(view['cart_value'].sum())} · top 500 by intent, then value")
    table(view.sort_values(["intent_score", "cart_value"], ascending=False).head(500)[
              ["cart_id", "date", "cart_value", "intent_score", "intent_band", "high_value", "reached_checkout",
               "returning_customer", "device", "reminder_focus", "incentive_cap", "incentive_at_day5"]],
          height=360, column_config={
              "cart_id": "Cart", "date": "Session date",
              "cart_value": st.column_config.NumberColumn("Value", format="$%.2f"),
              "intent_score": st.column_config.ProgressColumn("Intent", min_value=0, max_value=100, format="%d"),
              "intent_band": "Band", "high_value": st.column_config.CheckboxColumn("High value"),
              "reached_checkout": st.column_config.CheckboxColumn("Checkout"),
              "returning_customer": st.column_config.CheckboxColumn("Returning"), "device": "Device",
              "reminder_focus": "Reminder", "incentive_cap": st.column_config.NumberColumn("Cap", format="$%.2f"),
              "incentive_at_day5": "At Day 5"})


# ---------- Tab: Budget planner ----------
with budget_tab:
    heading("Spend a limited incentive budget (policy 3.5)",
            "Carts eligible for an incentive at the second contact, ranked by intent then value; each gets the cheaper "
            "allowed incentive until the budget runs out. A heuristic, not profit-maximizing.")
    c1, c2 = st.columns([3, 1])
    budget = c1.slider("Incentive budget ($)", 10, 500, int(pol["budget"] or 50), step=10)
    max_carts = c2.number_input("Most carts", 5, 200, 60, step=5)
    plan = agent.plan_incentive_budget(budget, int(max_carts))
    pdf = pd.DataFrame(plan["plan"])
    p = st.columns(4)
    kpi(p[0], "Budget", money(plan["budget"]), "simulated", BLUE)
    kpi(p[1], "Spent if all recovered", money(plan["spent_if_all_recovered"]),
        f"{plan['spent_if_all_recovered'] / plan['budget'] * 100:.0f}% of budget", ORANGE)
    kpi(p[2], "Carts chosen", f"{plan['carts_chosen']:,}", f"of {plan['carts_eligible_for_an_incentive']:,} eligible", AQUA)
    kpi(p[3], "Value covered", money(pdf["cart_value"].sum()) if not pdf.empty else "$0.00",
        "cart value of the chosen carts", INTENT["High"])
    st.write("")
    if pdf.empty:
        st.info("No cart is eligible for an incentive with these policies.")
    else:
        pdf["rank"] = range(1, len(pdf) + 1)
        pdf["spent"] = pdf["incentive_cost"].cumsum().round(2)
        left, right = st.columns(2)
        colour = alt.Color("incentive:N", title=None, scale=alt.Scale(domain=["Free shipping", "5% discount"],
                                                                     range=[BLUE, ORANGE]),
                           legend=alt.Legend(orient="top"))
        tips = [alt.Tooltip("rank:Q", title="Priority"), alt.Tooltip("cart_id:N", title="Cart"),
                alt.Tooltip("cart_value:Q", title="Value", format="$,.2f"), alt.Tooltip("intent_score:Q", title="Intent"),
                alt.Tooltip("incentive:N"), alt.Tooltip("incentive_cost:Q", title="Cost", format="$,.2f"),
                alt.Tooltip("spent:Q", title="Spent so far", format="$,.2f")]
        with left:
            heading("Budget burn-down", "Cumulative cost as carts are added, against the budget line.")
            line = alt.Chart(pdf).mark_line(interpolate="step-after", strokeWidth=2, color=BLUE).encode(
                x=alt.X("rank:Q", title="Priority (1 = first)", scale=alt.Scale(domain=[0.5, len(pdf) + .5])),
                y=alt.Y("spent:Q", title="Spent if all recovered", axis=alt.Axis(format="$,.0f"),
                        scale=alt.Scale(domain=[0, budget * 1.08])))
            pts = alt.Chart(pdf).mark_circle(size=80, opacity=1, stroke=BG, strokeWidth=1.5).encode(
                x="rank:Q", y="spent:Q", color=colour, tooltip=tips)
            cap = alt.Chart(pd.DataFrame({"y": [budget], "t": [f"budget {money(budget)}"]}))
            show(clean(line + pts + cap.mark_rule(strokeDash=[5, 4], color=ORANGE).encode(y="y:Q")
                       + cap.mark_text(align="left", dx=4, dy=-7, color=ORANGE, fontSize=11)
                       .encode(y="y:Q", x=alt.value(4), text="t:N"), 300))
        with right:
            heading("Who gets the budget", "Each bubble is a chosen cart; size = incentive cost.")
            bubbles = alt.Chart(pdf).mark_circle(opacity=.85, stroke=BG, strokeWidth=1.5).encode(
                x=alt.X("intent_score:Q", title="Purchase-intent score", scale=alt.Scale(domain=[0, 105])),
                y=alt.Y("cart_value:Q", title="Cart value", scale=alt.Scale(type="log"), axis=alt.Axis(format="$,.0f")),
                size=alt.Size("incentive_cost:Q", legend=None, scale=alt.Scale(range=[60, 420])),
                color=colour, tooltip=tips)
            show(clean(bubbles, 300))
        table(pdf[["rank", "cart_id", "cart_value", "intent_score", "intent_band", "incentive", "incentive_cost", "spent"]],
              column_config={"rank": "Priority", "cart_id": "Cart",
                             "cart_value": st.column_config.NumberColumn("Value", format="$%.2f"),
                             "intent_score": st.column_config.ProgressColumn("Intent", min_value=0, max_value=100,
                                                                             format="%d"),
                             "intent_band": "Band", "incentive": "Incentive",
                             "incentive_cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                             "spent": st.column_config.NumberColumn("Spent so far", format="$%.2f")})
    st.caption(plan["note"])


# ---------- Tab: Policies ----------
with policy_tab:
    heading("Contact timeline (policy 2.2)", "What each cart may receive, by days since it was left.")
    close = float(pol["close_day"] or 7)
    second = float(pol["second_reminder_day"] or 5)
    timeline = pd.DataFrame([
        {"stage": "not yet eligible", "start": 0.0, "end": (pol["eligibility_hours"] or 24) / 24, "what": "Wait 24 hours"},
        {"stage": "first reminder", "start": 1.0, "end": second, "what": "Reminder only"},
        {"stage": "second contact", "start": second, "end": close,
         "what": "Second reminder, or the cheaper incentive within the cap"},
        {"stage": "campaign closed", "start": close, "end": close + 2, "what": "No more contact"}])
    timeline["label"] = timeline["stage"].str.capitalize()
    timeline["mid"] = (timeline["start"] + timeline["end"]) / 2
    tl = alt.Chart(timeline).encode(y=alt.value(30))
    bars = tl.mark_bar(height=44, cornerRadius=6).encode(
        x=alt.X("start:Q", title="Days after the cart was left", scale=alt.Scale(domain=[0, close + 2]),
                axis=alt.Axis(values=list(range(0, int(close) + 3)), grid=False)), x2="end:Q",
        color=alt.Color("stage:N", legend=None, scale=alt.Scale(domain=list(STAGE_COLOURS),
                                                               range=list(STAGE_COLOURS.values()))),
        tooltip=[alt.Tooltip("label:N", title="Stage"), alt.Tooltip("what:N", title="What happens")])
    words = tl.mark_text(color="#FFFFFF", fontSize=11, fontWeight=600).encode(
        x="mid:Q", text=when("datum.end - datum.start >= 1.5", "label:N", alt.value("")))
    show(clean(bars + words, 70))
    with st.expander("📄 Full policy text", expanded=True):
        st.markdown(agent.get_store_policies()["policies"])


# ---------- Tab: Ask the agent ----------
TITLES = {"list_abandoned_checkouts": "Carts found", "get_review_rows": "Carts looked at",
          "get_checkout": "Cart details", "calculate_profit": "Policy checks and profit",
          "summarize_all_carts": "Summary of all open carts", "compare_datasets": "2016-17 vs. 2020-21",
          "analyze_abandonment": "Abandonment by group", "plan_incentive_budget": "Incentive budget plan",
          "get_store_policies": "Policies used"}
OPEN = {"summarize_all_carts", "compare_datasets", "analyze_abandonment", "plan_incentive_budget"}
DROP = {"natural_return_within_7_days", "intent_signals", "lifetime_spend", "traffic_source",
        "time_on_site_seconds", "consent_is_simulated"}


def hbar(df, value, category, height=None, fmt=",", colour=BLUE, tip=None):
    base = alt.Chart(df).encode(y=alt.Y(f"{category}:N", title=None, sort="-x"),
                                x=alt.X(f"{value}:Q", title=None), tooltip=tip or [category, value])
    bars = base.mark_bar(size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=colour)
    text = base.mark_text(align="left", dx=4, fontSize=11).encode(text=alt.Text(f"{value}:Q", format=fmt))
    return clean(bars + text, height or 34 * len(df) + 20)


def tool_data(name, result):
    if not isinstance(result, dict) or "error" in result:
        st.warning(f"{name}: {result.get('error') if isinstance(result, dict) else result}")
        return
    if name in ("list_abandoned_checkouts", "get_review_rows"):
        rows = result.get("carts", result.get("rows", []))
        total = result.get("total_found", result.get("cart_count"))
        st.caption(f"{total:,} carts" + (f" · total value {money(result['total_value_of_these_carts'])}"
                                          if "total_value_of_these_carts" in result else ""))
        table(pd.DataFrame(rows).drop(columns=list(DROP), errors="ignore"))
    elif name == "get_checkout":
        st.json(result, expanded=False)
    elif name == "calculate_profit":
        st.caption(f"Cart {result['cart_id']} · value {money(result['cart_value'])} · Day {result['evaluation_day']} "
                   f"({result['contact_stage']}) · incentive cap {money(result['incentive_cap'] or 0)}")
        table(pd.DataFrame(result["results"]))
    elif name == "summarize_all_carts":
        groups = [k for k in result if k.startswith("by_")]
        for row in range(0, len(groups), 4):
            cols = st.columns(4)
            for col, key in zip(cols, groups[row:row + 4]):
                with col:
                    df = pd.DataFrame(result[key]).T.rename_axis("group").reset_index()
                    st.markdown(f"**{key[3:].replace('_', ' ').capitalize()}**")
                    show(hbar(df, "carts", "group", tip=["group:N", alt.Tooltip("carts:Q", format=","),
                                                         alt.Tooltip("value:Q", format="$,.2f")]))
    elif name == "compare_datasets":
        rates = pd.DataFrame([{"period": p, "measure": m, "percent": v} for p, s in result.items()
                              for m, v in [("Abandonment", s["abandonment_rate_pct"]),
                                           ("Reached checkout", s["reached_checkout_pct"]),
                                           ("Left at checkout", s["left_at_checkout_pct_of_checkouts"]),
                                           ("Came back in 30 days",
                                            s["came_back_and_bought_within_30_days"]["rate_pct"])]])
        dumbbell = alt.Chart(rates).encode(y=alt.Y("measure:N", title=None))
        show(clean(dumbbell.mark_line(color=GREY, strokeWidth=3).encode(x=alt.X("percent:Q", title="Percent"),
                                                                       detail="measure:N")
                   + dumbbell.mark_circle(size=200, opacity=1).encode(
                       x="percent:Q", color=alt.Color("period:N", title=None, scale=alt.Scale(range=[BLUE, ORANGE]),
                                                      legend=alt.Legend(orient="top")),
                       tooltip=["period:N", "measure:N", alt.Tooltip("percent:Q", format=".1f")]), 200))
    elif name == "analyze_abandonment":
        for period in [k for k in result if k != "how_to_read"]:
            st.markdown(f"**{period}** · overall abandonment {result[period]['overall_abandonment_rate_pct']}%")
            df = pd.DataFrame([{"segment": f"{seg} ({group.replace('_', ' ')})", "points": r["points_vs_overall"],
                                "rate": r["abandonment_rate_pct"], "sessions": r["sessions"]}
                               for group, segs in result[period]["groups"].items() for seg, r in segs.items()])
            df = df.sort_values("points", ascending=False)
            show(clean(alt.Chart(df).mark_bar(size=11, cornerRadius=3).encode(
                x=alt.X("points:Q", title="Points above (+) or below (−) the overall rate"),
                y=alt.Y("segment:N", title=None, sort=list(df["segment"])),
                color=when("datum.points > 0", alt.value(ORANGE), alt.value(BLUE)),
                tooltip=["segment:N", alt.Tooltip("rate:Q", title="Abandonment %", format=".1f"),
                         alt.Tooltip("points:Q", format="+.1f"), alt.Tooltip("sessions:Q", format=",")]),
                16 * len(df) + 30))
    elif name == "plan_incentive_budget":
        st.caption(f"Budget {money(result['budget'])} · spent if all recovered {money(result['spent_if_all_recovered'])} "
                   f"· {result['carts_chosen']} of {result['carts_eligible_for_an_incentive']:,} eligible carts")
        table(pd.DataFrame(result["plan"]))
    elif name == "get_store_policies":
        st.markdown(result["policies"])


def final_action(c, suggested):
    """The action after the code's policy checks (blocked suggestions are marked)."""
    key = agent.canonical_action(suggested)
    if key in agent.RECOVERY_ACTIONS and agent._why_not(c, key, agent.evaluation_day(c), agent._policy_numbers()):
        return "Blocked by policy"
    return key or suggested


def review_charts(review_args):
    rows = []
    for j in review_args.get("carts", []):
        c = agent.BY_ID.get(str(j.get("cart_id")))
        if c:
            score, _, _ = agent.intent(c)
            rows.append({"cart_id": c["cart_id"], "cart_value": max(c["cart_value"], 1), "intent_score": score,
                         "risk": j.get("risk", ""), "suggested": j.get("recommendation", ""),
                         "action": final_action(c, j.get("recommendation", ""))})
    if not rows:
        return
    df = pd.DataFrame(rows)
    left, right = st.columns([1.5, 1])
    with left:
        heading("Where these carts sit", "Intent (computed) against cart value. The orange lines are the "
                f"high-intent score (60) and the high-value cut-off ({money(HV)}).")
        ymax = max(df["cart_value"].max() * 1.6, HV * 2)
        quad = pd.DataFrame([{"x": 80, "y": ymax * .8, "t": "Follow up first"}, {"x": 80, "y": 3, "t": "Keen, small cart"},
                             {"x": 20, "y": ymax * .8, "t": "Big cart, low intent"}, {"x": 20, "y": 3, "t": "Reminder at most"}])
        x = alt.X("intent_score:Q", title="Purchase-intent score", scale=alt.Scale(domain=[0, 100]))
        y = alt.Y("cart_value:Q", title="Cart value", scale=alt.Scale(type="log", domain=[1, ymax]),
                  axis=alt.Axis(format="$,.0f"))
        dots = alt.Chart(df).mark_circle(size=230, opacity=.95, stroke=BG, strokeWidth=2).encode(
            x=x, y=y, color=alt.Color("action:N", title="Action after checks",
                                      scale=alt.Scale(domain=list(ACTION_COLOURS), range=list(ACTION_COLOURS.values())),
                                      legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=["cart_id:N", alt.Tooltip("cart_value:Q", title="Value", format="$,.2f"),
                     alt.Tooltip("intent_score:Q", title="Intent"), "risk:N",
                     alt.Tooltip("suggested:N", title="AI suggested"), alt.Tooltip("action:N", title="After checks")])
        ids = alt.Chart(df).mark_text(dy=-15, fontSize=10).encode(x=x, y=y, text="cart_id:N")
        lines = (alt.Chart(pd.DataFrame({"x": [60]})).mark_rule(strokeDash=[4, 4], color=ORANGE, opacity=.7).encode(x="x:Q")
                 + alt.Chart(pd.DataFrame({"y": [HV]})).mark_rule(strokeDash=[4, 4], color=ORANGE, opacity=.7)
                 .encode(y="y:Q"))
        corner = alt.Chart(quad).mark_text(fontSize=11, opacity=.55, fontStyle="italic").encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100])), y=alt.Y("y:Q", scale=alt.Scale(type="log", domain=[1, ymax])),
            text="t:N")
        show(clean(lines + corner + dots + ids, 320))
    with right:
        heading("Recommendations", "After the code's policy checks.")
        counts = df["action"].value_counts().rename_axis("action").reset_index(name="carts")
        donut = alt.Chart(counts).mark_arc(innerRadius=62, outerRadius=100, cornerRadius=4, padAngle=.03).encode(
            theta="carts:Q",
            color=alt.Color("action:N", title=None, scale=alt.Scale(domain=list(ACTION_COLOURS),
                                                                   range=list(ACTION_COLOURS.values())),
                            legend=alt.Legend(orient="bottom", columns=2)),
            tooltip=["action:N", "carts:Q"])
        centre = alt.Chart(pd.DataFrame({"t": [f"{len(df)} carts"]})).mark_text(fontSize=15, fontWeight=700).encode(
            text="t:N")
        show(clean(donut + centre, 300))


def tool_results(messages):
    calls = {}
    for m in messages:
        for c in m.get("tool_calls") or []:
            calls[c["id"]] = (c["function"]["name"], json.loads(c["function"].get("arguments") or "{}"))
    return [(*calls[m["tool_call_id"]], json.loads(m["content"]))
            for m in messages if m.get("role") == "tool" and m["tool_call_id"] in calls]


def ask(question):
    messages = st.session_state.messages
    before = len(messages)
    messages.append({"role": "user", "content": question})
    agent.LAST_REVIEW = agent.LAST_STRATEGY = None
    try:
        answer = agent.run_agent(messages)
    except Exception as e:
        del messages[before:]   # forget the failed turn so you can retry
        return {"question": question, "error": str(e)}
    if agent.LAST_REVIEW:
        agent.save_review(question, agent.LAST_REVIEW)
    if agent.LAST_STRATEGY:
        agent.save_recommendations(question, agent.LAST_STRATEGY)
    return {"question": question, "answer": answer, "data": tool_results(messages[before:]),
            "full_review": agent.LAST_REVIEW}


def show_turn(turn):
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant", avatar="🛒"):
        if turn.get("error"):
            st.error(turn["error"])
            return
        used = list(dict.fromkeys(name for name, _, _ in turn["data"]))
        if used:
            st.markdown("".join(f'<span class="chip">🔧 {n}</span>' for n in used), unsafe_allow_html=True)
        st.markdown(turn["answer"])
        review = next((a for n, a, r in turn["data"] if n == "submit_review" and isinstance(r, dict) and "report" in r),
                      None)
        if review:
            review_charts(review)
            with st.expander("📄 Full review table, policy checks and alternatives"):
                st.markdown(turn["full_review"].split("## Full table", 1)[-1])
        shown = set()
        for name, _, result in turn["data"]:
            if name in TITLES and name not in shown:
                shown.add(name)
                with st.expander(f"📊 {TITLES[name]}", expanded=name in OPEN):
                    tool_data(name, result)


with chat_tab:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
        st.session_state.turns = []
    if not agent.OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is missing from .env. The charts still work; add your key to chat.")
    elif not st.session_state.turns:
        st.info("Ask a question below or pick one in the sidebar. Charts of the agent's decisions and the data "
                "behind each answer appear under its reply.")
    for turn in st.session_state.turns:
        show_turn(turn)

question = st.chat_input("Ask about your carts, e.g. Review my 3 carts that reached checkout") or picked
if question and agent.OPENAI_API_KEY:
    with chat_tab:
        with st.spinner("The agent is working (this can take up to a minute)..."):
            turn = ask(question)
        st.session_state.turns.append(turn)
        show_turn(turn)
