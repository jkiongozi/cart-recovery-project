"""Ask the Cart Recovery Agent in your browser, and see the data behind each answer.

Run:  streamlit run ask_agent.py
Uses the same agent, tools and policies as `python agent.py`. Needs OPENAI_API_KEY in .env.
"""
import json

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ask the Cart Recovery Agent", page_icon="💬", layout="wide")


@st.cache_resource(show_spinner="Loading carts...")
def load_agent():
    import agent   # loads the prepared data once
    return agent


agent = load_agent()

EXAMPLES = [
    "Review my 5 most recent carts",
    "Review my 5 highest-value carts",
    "Summarize all my carts",
    "How does 2016-17 compare with 2020-21?",
    "How can I reduce cart abandonment?",
]
GROUP_NAMES = {"by_age": "By age", "by_stage": "By checkout stage", "by_device": "By device",
               "by_customer": "By customer type", "by_cart_value": "By cart value"}
MONEY = {"cart_value": st.column_config.NumberColumn("Cart value", format="$%.2f"),
         "value": st.column_config.NumberColumn("Value", format="$%.2f"),
         "lifetime_spend": st.column_config.NumberColumn("Lifetime spend", format="$%.2f"),
         "abandoned_value": st.column_config.NumberColumn("Abandoned value", format="$%.2f")}


# ---------- Showing the data each tool returned ----------
def _table(rows, **kw):
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config=MONEY, **kw)


def _flatten_stats(period):
    """One row per measure for the comparison table."""
    out = {}
    for k, v in period.items():
        if k == "patterns" or isinstance(v, bool):
            continue
        label = k.replace("_", " ")
        if isinstance(v, dict) and "rate_pct" in v:
            out[label + " %"] = v["rate_pct"]
        elif isinstance(v, dict):
            for sub, x in v.items():
                out[f"{label}: {sub}"] = x
        else:
            out[label] = v
    return out


def show_compare(result):
    rows = {name: _flatten_stats(s) for name, s in result.items()}
    df = pd.DataFrame(rows)
    st.dataframe(df.astype(str), use_container_width=True)
    rates = pd.DataFrame({name: {"Abandonment %": s["abandonment_rate_pct"],
                                 "Reached checkout %": s["reached_checkout_pct"],
                                 "Left at checkout %": s["left_at_checkout_pct_of_checkouts"],
                                 "Came back within 30 days %": s["came_back_and_bought_within_30_days"]["rate_pct"]}
                          for name, s in result.items()})
    st.bar_chart(rates, stack=False, y_label="Percent")


def show_summary(result):
    c1, c2, c3 = st.columns(3)
    c1.metric("Open carts", f"{result['total_open_carts']:,}")
    c2.metric("Total value", f"${result['total_value']:,.2f}")
    c3.metric("Average cart (excl. $0)", f"${result['average_cart_excluding_zero']:,.2f}")
    groups = [k for k in GROUP_NAMES if k in result]
    for col, key in zip(st.columns(len(groups)), groups):
        with col:
            st.markdown(f"**{GROUP_NAMES[key]}**")
            df = pd.DataFrame(result[key]).T.rename_axis("group").reset_index()
            _table(df)
            st.bar_chart(df.set_index("group")["carts"], y_label="Carts")


def show_patterns(result):
    periods = [k for k in result if k != "how_to_read"]
    for tab, name in zip(st.tabs(periods), periods):
        with tab:
            st.caption(f"Overall abandonment: {result[name]['overall_abandonment_rate_pct']}%")
            for group, rows in result[name]["groups"].items():   # no expanders: they cannot be nested
                st.markdown(f"**{group.replace('_', ' ').capitalize()}**")
                df = pd.DataFrame(rows).T.rename_axis("segment").reset_index()
                left, right = st.columns([2, 3])
                with left:
                    st.bar_chart(df.set_index("segment")["abandonment_rate_pct"], y_label="Abandonment %",
                                 height=220)
                with right:
                    _table(df)


def show_tool(name, args, result, turn):
    if isinstance(result, dict) and "error" in result:
        st.warning(f"{name}: {result['error']}")
        return
    if name == "list_abandoned_checkouts":
        st.caption(f"{result['total_found']:,} carts match · showing {len(result['carts'])}")
        _table(result["carts"])
    elif name == "get_review_rows":
        st.caption(f"{result['cart_count']} carts · total value ${result['total_value_of_these_carts']:,.2f}")
        _table(result["rows"])
    elif name == "get_checkout":
        _table([result])
    elif name == "calculate_profit":
        st.caption(f"Cart {result['cart_id']} · value ${result['cart_value']:,.2f}")
        _table(result["results"])
    elif name == "summarize_all_carts":
        show_summary(result)
    elif name == "compare_datasets":
        show_compare(result)
    elif name == "analyze_abandonment":
        show_patterns(result)
    elif name == "get_store_policies":
        st.markdown(result["policies"])
    elif name == "submit_review" and turn.get("full_review"):
        st.markdown(turn["full_review"].split("## Full table", 1)[-1])


TITLES = {"list_abandoned_checkouts": "Carts found", "get_review_rows": "Carts reviewed",
          "get_checkout": "Cart details", "calculate_profit": "Profit by action",
          "summarize_all_carts": "Summary of all open carts", "compare_datasets": "2016-17 vs. 2020-21",
          "analyze_abandonment": "Abandonment by group", "get_store_policies": "Store policies used",
          "submit_review": "Full review table"}
OPEN_BY_DEFAULT = {"summarize_all_carts", "compare_datasets", "analyze_abandonment", "submit_review"}


def show_turn(turn):
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        if turn.get("error"):
            st.error(turn["error"])
            return
        st.markdown(turn["answer"])
        shown = set()
        for name, args, result in turn["data"]:
            if name not in TITLES or name == "submit_recommendations":
                continue
            if name == "calculate_profit" and name in shown:   # one profit table is enough
                continue
            shown.add(name)
            with st.expander(f"📊 Data: {TITLES[name]}", expanded=name in OPEN_BY_DEFAULT):
                show_tool(name, args, result, turn)


# ---------- Running the agent ----------
def tool_results(messages):
    """Pair each tool call in these messages with its result, in order."""
    calls = {}
    for m in messages:
        for c in m.get("tool_calls") or []:
            calls[c["id"]] = (c["function"]["name"], json.loads(c["function"].get("arguments") or "{}"))
    out = []
    for m in messages:
        if m.get("role") == "tool" and m["tool_call_id"] in calls:
            name, args = calls[m["tool_call_id"]]
            out.append((name, args, json.loads(m["content"])))
    return out


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


# ---------- Page ----------
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
    st.session_state.turns = []

st.title("💬 Ask the Cart Recovery Agent")
st.caption(f"{len(agent.CHECKOUTS):,} open carts · ages counted from {agent.AS_OF} · "
           f"email subscription {'simulated' if agent.SIMULATED else 'unknown'} · model {agent.MODEL}. "
           "The agent only recommends; every action needs your approval.")

question = None
with st.sidebar:
    st.header("Try a question")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            question = q
    st.divider()
    if st.button("🗑️ Start a new conversation", use_container_width=True):
        del st.session_state["messages"]
        st.rerun()

if not agent.OPENAI_API_KEY:
    st.error("OPENAI_API_KEY is missing from .env. Add your key, save the file and restart this page.")
    st.stop()

typed = st.chat_input("Ask about your carts, e.g. Review my 3 carts that reached checkout")
question = typed or question

for turn in st.session_state.turns:
    show_turn(turn)

if question:
    with st.spinner("The agent is working (this can take up to a minute)..."):
        turn = ask(question)
    st.session_state.turns.append(turn)
    show_turn(turn)
